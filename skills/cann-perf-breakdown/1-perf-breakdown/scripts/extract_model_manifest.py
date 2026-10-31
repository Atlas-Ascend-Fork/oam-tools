#!/usr/bin/env python3
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""
extract_model_manifest.py — statically extract architecture ground truth.

Reads a model's configuration + modeling source with Python AST (NEVER imports or
executes model code) and emits model_manifest.json conforming to
schemas/model_manifest.schema.json.

Every fact carries source_ref + extraction method + confidence. Values that cannot
be resolved statically are recorded as "unknown" and listed in evidence_gaps — the
extractor never guesses architecture numbers.

Usage:
  python scripts/extract_model_manifest.py --model-dir models/ds3.2 -o outputs/model_manifest.json
  python scripts/extract_model_manifest.py --model-dir models/longcat \
      --checkpoint-config checkpoints/longcat/config.json -o outputs/model_manifest.json
  python scripts/extract_model_manifest.py --config models/ds3.2/models/configuration_deepseek.py \
      --modeling models/ds3.2/models/modeling_deepseek.py -o outputs/model_manifest.json
"""
import argparse
import ast
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import adapters  # noqa: E402
from adapters.base import (find_config_class, extract_init_defaults, scan_evidence,  # noqa: E402
                           UNKNOWN)


def read(path):
    # utf-8-sig consumes a leading UTF-8 BOM (EF BB BF) only. The BOM is *valid* UTF-8, so
    # errors='replace' cannot catch it: it decodes to U+FEFF and then breaks ast.parse, or
    # silently defeats the `model_path:` prefix match on runtime.yaml's first line. Interior
    # U+FEFF characters are body content and must survive — see issue #311.
    with open(path, 'r', encoding='utf-8-sig', errors='replace') as f:
        return f.read()


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def strip_inline_comment(raw):
    """Drop a YAML inline comment from a scalar value, honouring quotes.

    ``model_path: "/ckpt" # selected`` is a path followed by a comment, not a path that
    contains one. The previous ``strip('"\\'')`` only trimmed quote characters off both
    ends, so a trailing comment blocked the tail strip while the leading quote was still
    removed, leaving ``/ckpt" # selected`` -- a directory that cannot exist. The
    checkpoint was then silently missed and the layer count fell back to the source
    default (issue #310).

    Inside quotes both ``#`` and spaces are content; in a plain scalar ``#`` opens a
    comment only after whitespace, so ``/ckpt#v2`` and ``/ckpt dir`` stay intact.
    """
    text = raw.strip()
    quote = text[:1]
    if quote in ('"', "'"):
        index = 1
        while index < len(text):
            char = text[index]
            if char == '\\' and quote == '"':
                index += 2
                continue
            if char == quote:
                # A doubled single quote is an escaped quote, not the terminator.
                if quote == "'" and text[index + 1:index + 2] == "'":
                    index += 2
                    continue
                return text[:index + 1]
            index += 1
        # Unterminated quote is not valid YAML: hand the text back untouched and let the
        # caller's existing quote trim decide, instead of guessing where the path ends.
        return text
    for index, char in enumerate(text):
        if char == '#' and (index == 0 or text[index - 1] in ' \t'):
            # The whitespace that opens the comment is a separator, not part of the path.
            return text[:index].rstrip()
    return text


def _validate_checkpoint_numeric_types(adapter, values, path):
    """Reject JSON values that could masquerade as architecture integers."""
    integer_key_attributes = (
        'main_layer_count_keys', 'prediction_count_keys', 'dense_boundary_keys',
        'moe_expert_keys', 'shared_expert_keys', 'experts_per_token_keys')
    integer_keys = {
        key
        for attribute in integer_key_attributes
        for key in (getattr(adapter, attribute, ()) or ())
    }
    for key in sorted(integer_keys & set(values)):
        value = values[key]
        if value is not None and (
                not isinstance(value, int) or isinstance(value, bool)):
            raise ValueError(
                f'checkpoint config.json key {key!r} must be an integer or null, '
                f'got {type(value).__name__}: {path}')


def find_weights_config(model_dir, runtime_config=None, checkpoint_config=None):
    """Resolve the checkpoint config.json a runtime YAML points at.

    Python default args describe the family, not the deployed checkpoint: LongCat's
    config.py defaults to the 61-layer Flash while the YAML loads 14-layer Lite
    weights. The checkpoint config.json is the real source of truth, so when it is
    reachable it must win, and when it is not the caller has to know that the numbers
    came from a fallback.

    Returns (config_json_path_or_None, declared_model_path_or_None).
    """
    if checkpoint_config:
        selected = os.path.realpath(checkpoint_config)
        if not os.path.isfile(selected):
            raise FileNotFoundError(
                f'explicit checkpoint config.json does not exist: {checkpoint_config}')
        return selected, os.path.dirname(selected)
    if not model_dir or not os.path.isdir(model_dir):
        return None, None
    declared = None
    if runtime_config:
        yaml_paths = [runtime_config] if os.path.isfile(runtime_config) else []
    else:
        yaml_paths = []
        for root, _dirs, files in os.walk(model_dir):
            yaml_paths.extend(
                os.path.join(root, fn) for fn in sorted(files)
                if fn.endswith(('.yaml', '.yml')))
    for yaml_path in yaml_paths:
        for line in read(yaml_path).splitlines():
                stripped = line.strip()
                if not stripped.startswith('model_path:'):
                    continue
                value = strip_inline_comment(stripped.split(':', 1)[1]).strip('"\'')
                if not value:
                    continue
                declared = declared or value
                candidate = os.path.join(value, 'config.json')
                if os.path.isfile(candidate):
                    return candidate, value
    # A checkpoint vendored next to the source needs no YAML to be authoritative.
    local = os.path.join(model_dir, 'config.json')
    if os.path.isfile(local):
        return local, model_dir
    return None, declared


def find_source_files(model_dir):
    """Locate configuration_*.py and modeling_*.py under a model dir."""
    config_file = None
    modeling_file = None
    for root, _dirs, files in os.walk(model_dir):
        for fn in files:
            if not fn.endswith('.py'):
                continue
            low = fn.lower()
            full = os.path.join(root, fn)
            if ('config' in low) and config_file is None and 'configuration' in low:
                config_file = full
            elif low.startswith('config_') and config_file is None:
                config_file = full
            if low.startswith('modeling_') and modeling_file is None:
                modeling_file = full
    # fallback: any file with a *Config class / *DecoderLayer class
    return config_file, modeling_file


def build_manifest(config_path, modeling_path, model_name, base_dir, model_dir=None,
                   capture_dir=None, runtime_config=None, checkpoint_config=None):
    config_src = read(config_path) if config_path else ''
    modeling_src = read(modeling_path) if modeling_path else ''

    config_tree = ast.parse(config_src) if config_src else None
    modeling_tree = ast.parse(modeling_src) if modeling_src else None

    config_defaults = {}
    config_class_name = None
    if config_tree is not None:
        cls, init_fn = find_config_class(config_tree, modeling_tree)
        config_class_name = cls.name if cls is not None else None
        if init_fn is not None:
            config_defaults = extract_init_defaults(init_fn)

    evidence = scan_evidence(config_src, modeling_src)
    # An ambiguous match raises rather than resolving by registration order — see
    # adapters.AmbiguousAdapterError. Letting it propagate is deliberate: a manifest naming
    # the wrong family looks exactly as authoritative as a correct one.
    selection = adapters.resolve_adapter(evidence)
    adapter = selection['adapter']

    # The checkpoint config.json, when reachable, overrides Python defaults for every
    # key it declares. Merge before extraction so layer counts and MoE boundaries are
    # derived from the deployed values rather than the family defaults.
    weights_config_path, declared_weights_path = find_weights_config(
        model_dir, runtime_config=runtime_config,
        checkpoint_config=checkpoint_config)
    weights_values = {}
    if weights_config_path:
        try:
            # Same root cause as read(): json.load on a BOM-prefixed stream raises
            # "Unexpected UTF-8 BOM". This call does not go through read(), so the fix
            # there does not cover it.
            with open(weights_config_path, 'r', encoding='utf-8-sig') as f:
                weights_values = json.load(f)
        except (OSError, ValueError) as exc:
            raise ValueError(
                f'checkpoint config.json cannot be read: {weights_config_path}: {exc}') from exc
        if not isinstance(weights_values, dict):
            raise ValueError(
                f'checkpoint config.json must contain a JSON object: {weights_config_path}')
        _validate_checkpoint_numeric_types(adapter, weights_values, weights_config_path)
        for key, value in weights_values.items():
            config_defaults[key] = (value, 1)

    facts, layer_groups, prediction_modules, num_main, gaps = adapter.extract(
        config_tree, modeling_tree, config_defaults, base_dir,
        config_path or 'unknown', modeling_path or 'unknown')

    source_of_truth = []
    for p in (config_path, modeling_path):
        if p:
            rel = os.path.relpath(p, base_dir) if base_dir else p
            source_of_truth.append(f'{rel}:1')

    # Without the checkpoint config every number is a family default. That is a real
    # gap even when the AST resolved cleanly, so it must not be reported as high
    # confidence with an empty gap list — that combination is what makes a wrong layer
    # count invisible downstream.
    if weights_config_path:
        rel = (os.path.relpath(weights_config_path, base_dir)
               if base_dir else weights_config_path)
        source_of_truth.append(f'{rel}:1')
        for fact in facts:
            if fact.key in weights_values:
                fact.source_ref = f'{rel}:1'
                fact.method = 'weights_config_json'
                fact.confidence = 'high'
    else:
        where = declared_weights_path or '未在 YAML 中声明'
        gaps.append(f'checkpoint config.json 不可达（model_path={where}）：'
                    f'以下数值来自 Python 默认参数，可能与实际权重不符')
        for fact in facts:
            if fact.method == 'ast_default_arg' and fact.confidence == 'high':
                fact.confidence = 'low'

    # Capabilities are what gates the family-specific validation rules (D7 and the
    # adapter's dataflow_invariants). They are asserted only where a key is actually
    # present, so an absent key stays unknown instead of becoming a claim.
    capabilities = adapter.capabilities(evidence, config_defaults)
    if selection['confidence'] in ('medium', 'unknown') and selection['name'] != 'generic':
        gaps.append(
            f"适配器 `{selection['name']}` 由 config key 签名匹配（confidence="
            f"{selection['confidence']}），未见该族 class 名：{'; '.join(selection['reasons'])}")
    if selection['name'] == 'generic':
        gaps.append('未匹配任何族适配器：使用 generic 基类，不假设 MoE 边界/预测模块的 '
                    'config key 拼写；相关数值若缺失属未知而非不存在')

    manifest = {
        'schema_version': 1,
        'model_name': model_name,
        'adapter': adapter.name,
        'adapter_selection': {
            'name': selection['name'],
            'confidence': selection['confidence'],
            'reasons': selection['reasons'],
            'candidates': [{'adapter': c['adapter'], 'confidence': c['confidence']}
                           for c in selection['candidates']],
        },
        'capabilities': capabilities,
        # Declarative constraints the adapter asserts, evaluated by check_dataflow (D7).
        # Carried in the manifest rather than hardcoded in the checker so a checker that has
        # never seen this family can still abstain instead of guessing. Only invariants
        # whose gating capability is actually evidenced are emitted.
        'dataflow_invariants': [
            dict(item) for item in (adapter.dataflow_invariants or ())
            if not item.get('requires')
            or item['requires'] in {c['id'] for c in capabilities}
        ],
        'known_deviations': adapter.deviations(),
        # Candidate components and role bindings, for the mapper to confirm against
        # `forward()`. Deliberately proposals: `__init__` declares what exists, not what
        # runs or in what order, and role names are read off attribute spellings. Every
        # role carries confidence='low' and the hint that produced it, so nothing here can
        # be mistaken for the source-derived decomposition.
        'component_candidates': adapter.extract_components(
            modeling_tree, config_defaults, base_dir, modeling_path or 'unknown'),
        'role_candidates': adapter.infer_roles(
            modeling_tree, base_dir, modeling_path or 'unknown'),
        'config_class': config_class_name,
        'weights_config': weights_config_path,
        'weights_config_sha256': (
            _sha256_file(weights_config_path) if weights_config_path else None),
        'declared_model_path': declared_weights_path,
        'source_of_truth': source_of_truth,
        'num_main_layers': num_main,
        'layer_groups': layer_groups,
        'prediction_modules': prediction_modules,
        'facts': [f.as_dict() for f in facts],
        'evidence_gaps': gaps,
    }
    # How much this capture can prove about itself. Scoring reads the tier to decide which
    # checks are legitimately unavailable, so it must be detected rather than declared.
    provenance = detect_capture_provenance(
        model_dir, capture_dir, base_dir,
        weights_config_path=weights_config_path, modeling_path=modeling_path)
    manifest['capture_provenance'] = provenance
    checkpoint = provenance['checkpoint_config']
    if checkpoint.get('evidence_level') == 4:
        gaps.append(
            f'checkpoint config.json 不可达且无运行期记录（{checkpoint.get("method")}）：'
            f'num_main_layers={num_main} 等标量仅有源码默认值支撑，'
            f'部署时可能被覆盖。结论按 tier={provenance["tier"]} 标注，不据此判定拆解错误')
    return manifest


#: Directories that never hold a capture's own provenance.
_PROVENANCE_SKIP_DIRS = frozenset({
    '.git', '__pycache__', 'node_modules', '.pytest_cache', 'tests', 'fixtures'})

#: Files that record a config value printed by a real load, in preference order. A value
#: transcribed from a run of `Config(**json.load(open('config.json')))` is checkpoint evidence
#: even though the checkpoint itself was not delivered.
_RUNTIME_RECORD_SUFFIXES = ('.md', '.log', '.txt')

#: `key: value` as printed by a loaded config, not `key=value` as written in a def signature.
_RUNTIME_RECORD_RE = re.compile(
    r'\b(num_hidden_layers|num_layers|n_layers)\s*:\s*(\d+)\b')


def _find_runtime_config_record(search_root, base_dir):
    """Search for a transcript of a real config load: evidence level 2.

    A checkpoint `config.json` that was not shipped with the capture is still the source of
    truth, and a log line showing what it produced carries that truth. LongCat's real layer
    count (14, against an AST default of 56) is only knowable this way. Declaring an evidence
    gap before searching for this would report a value as unconfirmable while its confirmation
    sits in the bundle.
    """
    if not search_root or not os.path.isdir(search_root):
        return None
    for root, dirs, files in os.walk(search_root):
        dirs[:] = [d for d in dirs if d not in _PROVENANCE_SKIP_DIRS]
        for fn in sorted(files):
            if not fn.endswith(_RUNTIME_RECORD_SUFFIXES):
                continue
            path = os.path.join(root, fn)
            for lineno, line in enumerate(read(path).splitlines(), 1):
                # Skip source lines: a default arg or an attribute assignment is level 4.
                if 'def ' in line or 'self.' in line or '=' in line.split(':', 1)[0]:
                    continue
                match = _RUNTIME_RECORD_RE.search(line)
                if not match:
                    continue
                return {
                    'key': match.group(1),
                    'value': int(match.group(2)),
                    'source_ref': f'{os.path.relpath(path, base_dir)}:{lineno}',
                    'method': 'checkpoint_config_via_runtime_record',
                    'excerpt': line.strip()[:200],
                }
    return None


def detect_capture_provenance(model_dir, capture_dir, base_dir,
                              weights_config_path=None, modeling_path=None):
    """Classify how much this capture can prove about itself.

    The tier is NOT a measure of how much data arrived; it is whether the source can be shown
    to describe the run that produced the trace. A self-captured bundle records the msprof
    command, the environment and a `source_snapshot/` of the code as it was at capture time, so
    "the AST default is the deployed value" has evidence. A third-party delivery has source
    that arrived separately, and nothing ties it to that trace.

    That distinction matters more than the presence of a checkpoint `config.json`: qwen7b has
    no config.json either, yet its snapshot makes its AST defaults trustworthy, while ds3.2's
    identical-looking AST default may be overridden by weights nobody delivered.
    """
    roots = [d for d in (capture_dir, model_dir) if d and os.path.isdir(d)]

    def locate(name, want_dir=False):
        for root in roots:
            for cur, dirs, files in os.walk(root):
                dirs[:] = [d for d in dirs if d not in _PROVENANCE_SKIP_DIRS]
                pool = dirs if want_dir else files
                if name in pool:
                    return os.path.relpath(os.path.join(cur, name), base_dir)
        return None

    capture_manifest = locate('capture_manifest.json')
    source_snapshot = locate('source_snapshot', want_dir=True)
    step_marks = locate('step_marks.json')

    # A model defined by the repo's own source with randomly initialised weights has no
    # checkpoint to disagree with: the source IS the architecture, not a default awaiting
    # override. That is the strongest evidence available, not the weakest.
    self_defined = False
    if modeling_path and os.path.isfile(modeling_path):
        head = read(modeling_path)[:4000].lower()
        self_defined = ('randomly initialised' in head or 'randomly initialized' in head
                        or 'random weights' in head)

    checkpoint = {'present': bool(weights_config_path)}
    if weights_config_path:
        checkpoint.update(evidence_level=1, source_ref=weights_config_path,
                          method='checkpoint_config_json')
    elif self_defined:
        checkpoint.update(evidence_level=1, method='self_defined_source_is_truth',
                          source_ref=(os.path.relpath(modeling_path, base_dir)
                                      if modeling_path else None),
                          note='权重随机初始化，不存在可覆盖源码的 checkpoint：源码即架构真值')
    else:
        record = (_find_runtime_config_record(capture_dir, base_dir)
                  or _find_runtime_config_record(model_dir, base_dir))
        if record:
            checkpoint.update(evidence_level=2, **record)
        elif source_snapshot:
            checkpoint.update(evidence_level='2S', method='ast_default_bound_by_snapshot',
                              source_ref=source_snapshot,
                              note='源码快照与本次采集同源，AST 默认值即本次实际值')
        else:
            checkpoint.update(evidence_level=4, method='ast_default_arg_unbound',
                              note='仅有源码默认参数，且无法证明源码与本次 trace 同源：'
                                   '部署时可能被 checkpoint 覆盖')

    if self_defined:
        tier, tier_reason = 'S0', '模型定义在仓库内、权重随机初始化，源码即唯一真值'
    elif capture_manifest and source_snapshot and step_marks:
        tier, tier_reason = 'S', '自采：capture_manifest + source_snapshot + step_marks 齐备'
    elif modeling_path:
        tier, tier_reason = 'A', '第三方交付：有源码但无采集溯源链，源码与 trace 的同源性无法证明'
    else:
        tier, tier_reason = 'B', '无模型源码：拓扑无法核对'

    return {
        'tier': tier,
        'tier_reason': tier_reason,
        'capture_manifest': capture_manifest,
        'source_snapshot': source_snapshot,
        'step_marks': step_marks,
        'model_source': {
            'present': bool(modeling_path),
            'path': (os.path.relpath(modeling_path, base_dir)
                     if modeling_path and os.path.exists(modeling_path) else None),
            # Only a snapshot (or a self-defined model) ties source to this trace.
            'bound_to_capture': bool(source_snapshot or self_defined),
        },
        'checkpoint_config': checkpoint,
    }


def main():
    parser = argparse.ArgumentParser(description='Static model architecture manifest extractor (AST only)')
    parser.add_argument('--model-dir', help='模型目录（自动定位 configuration_*.py / modeling_*.py）')
    parser.add_argument('--config', help='configuration 源文件')
    parser.add_argument('--modeling', help='modeling 源文件')
    parser.add_argument('--model-name', default=None)
    parser.add_argument('--base-dir', default=None, help='source_ref 相对根目录（默认当前工作目录）')
    parser.add_argument('--capture-dir',
                        help='采集目录：探测 capture_manifest.json / source_snapshot/ / '
                             'step_marks.json 与运行期 config 记录，用于判定采集溯源档位。'
                             '未提供时仅按 --model-dir 探测')
    parser.add_argument('--runtime-config',
                        help='本次采集实际使用的 runtime YAML；有多个 YAML 时禁止猜测')
    parser.add_argument('--checkpoint-config',
                        help='显式部署 checkpoint config.json；优先于 runtime YAML')
    parser.add_argument('-o', '--output', help='输出 model_manifest.json（默认打印）')
    args = parser.parse_args()

    config_path = args.config
    modeling_path = args.modeling
    if args.model_dir:
        c, m = find_source_files(args.model_dir)
        config_path = config_path or c
        modeling_path = modeling_path or m

    if not config_path:
        sys.stderr.write('错误: 未找到 configuration 源文件（--config 或 --model-dir）\n')
        sys.exit(2)

    base_dir = args.base_dir or os.getcwd()
    model_name = args.model_name or (os.path.basename(os.path.normpath(args.model_dir))
                                     if args.model_dir else 'unknown')

    manifest = build_manifest(config_path, modeling_path, model_name, base_dir,
                              model_dir=args.model_dir, capture_dir=args.capture_dir,
                              runtime_config=args.runtime_config,
                              checkpoint_config=args.checkpoint_config)

    text = json.dumps(manifest, indent=2, ensure_ascii=False)
    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(text + '\n')
        print(f'model_manifest 已生成: {args.output}')
        prov = manifest['capture_provenance']
        print(f'adapter={manifest["adapter"]}  num_main_layers={manifest["num_main_layers"]}  '
              f'layer_groups={len(manifest["layer_groups"])}  '
              f'prediction_modules={len(manifest["prediction_modules"])}  gaps={len(manifest["evidence_gaps"])}')
        print(f'tier={prov["tier"]}  '
              f'checkpoint_evidence_level={prov["checkpoint_config"].get("evidence_level")}  '
              f'source_bound_to_capture={prov["model_source"]["bound_to_capture"]}')
    else:
        print(text)


if __name__ == '__main__':
    main()
