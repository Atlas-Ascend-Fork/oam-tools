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
"""Convert a completed Skill 1 bundle and optionally assemble the Skill 3 report.

    python3 run_pipeline.py --breakdown DIR --model-id NAME --out DIR

The breakdown directory must already contain Skill 1's five formal files. This script starts at
readiness and never reproduces mapping, critique, validation, or scoring. Auxiliary raw-op and
trace files remain necessary for attribution and report assembly, but cannot grant readiness.
"""
import argparse
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STAGE2 = os.path.dirname(HERE)
SKILL_COLLECTION = os.path.dirname(STAGE2)


def read_skill_name(skill_md):
    with open(skill_md, "r", encoding="utf-8") as fh:
        lines = fh.readlines()
    if not lines or lines[0].strip() != "---":
        return None
    try:
        end = next(index for index, line in enumerate(lines[1:], start=1)
                   if line.strip() == "---")
    except StopIteration:
        return None
    for line in lines[1:end]:
        key, separator, value = line.partition(":")
        if separator and key.strip() == "name":
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                value = value[1:-1]
            return value or None
    return None


def find_peer_skill(skill_name, collection=SKILL_COLLECTION):
    matches = []
    for entry in os.scandir(collection):
        if entry.is_symlink() or not entry.is_dir(follow_symlinks=False):
            continue
        skill_md = os.path.join(entry.path, "SKILL.md")
        if not os.path.isfile(skill_md):
            continue
        if read_skill_name(skill_md) == skill_name:
            matches.append(entry.path)
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one peer skill named {skill_name!r} in "
            f"{collection}, found {matches}"
        )
    return matches[0]


STAGE1 = find_peer_skill("cann-perf-breakdown")
# The preserved UI skill keeps its original frontmatter name. Resolve it from the
# unified collection rather than assuming the later workflow alias.
STAGE3 = find_peer_skill("cann-perf-ui-json-report")

sys.path.insert(0, HERE)
import breakdown_paths  # noqa: E402


def run(cmd, **kwargs):
    print("$ " + " ".join(str(c) for c in cmd), file=sys.stderr)
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kwargs)


def die(status, stage, message, **extra):
    print(json.dumps({"status": status, "stage": stage, "message": message, **extra},
                      ensure_ascii=False, indent=1))
    sys.exit(0 if status.startswith("awaiting") else 1)


def find_one(root, name, explicit=None, stages=None):
    """Resolve one capture file: an explicit path wins, otherwise the candidate must be unique.

    A multi-rank capture directory holds one such file per rank, so taking the
    lexicographically first hit would silently analyse whichever rank sorts first. The report
    then cannot prove it used the intended capture, so ambiguity is reported with every
    candidate path instead of guessed at. validate_conversion.find_one already refuses to
    guess; capture discovery has to hold the same line.

    The search root is a caller-supplied path, so it is escaped before becoming part of the glob
    pattern: a capture directory legitimately named ``capture[0]`` would otherwise be read as a
    character class and match nothing, reporting a present file as missing, while ``capture*2026``
    would widen the search to unrelated sibling captures.
    """
    if explicit:
        return explicit
    hits = sorted(glob.glob(os.path.join(glob.escape(root), "**", name), recursive=True))
    if len(hits) > 1:
        die("failed", "conversion_inputs",
            f"ambiguous {name} under {root}: found {len(hits)} candidates {hits}; "
            f"pass an explicit path to select the intended rank",
            candidates=hits, stages=stages)
    return hits[0] if hits else None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--breakdown", required=True,
                    help="directory containing Skill 1's five formal files and raw op facts")
    ap.add_argument("--capture-dir",
                    help="profiling capture directory for trace/HBM inputs; defaults to "
                         "--breakdown")
    ap.add_argument("--model-id", required=True, help="report model id, e.g. longcat-flash-lite")
    ap.add_argument("--out", required=True, help="work + output directory")
    ap.add_argument("--trace", help="trace_view.json (default: found under --capture-dir)")
    ap.add_argument("--raw-ops",
                    help="raw_ops.json; defaults to <breakdown>/raw_ops.json")
    ap.add_argument("--raw-ops-details",
                    help="raw_ops_details.json; defaults to <breakdown>/raw_ops_details.json")
    ap.add_argument("--device-freq",
                    help="device_freq.json; defaults to <breakdown>/device_freq.json when present")
    ap.add_argument("--hbm-dir", action="append", default=[],
                    help="directory holding HBM sample exports. Repeatable, because a capture "
                         "splits them: hbm_*_timeline.csv + hbm_summary.json under derived/hbm, "
                         "sample_op_mix.csv under derived/correlation, while build-hbm-data.mjs "
                         "wants all four in ONE directory. Default: discovered under "
                         "--capture-dir. Without them the report still renders, but its HBM "
                         "panel is an empty series -- the capture's measured bandwidth and "
                         "occupancy are simply absent rather than reported as unavailable.")
    ap.add_argument("--breakdown-config",
                    help="explicit config path; use only for legacy analysis_config_v2.json")
    ap.add_argument("--rename-group", action="append", default=[],
                    help="StructureKey=node-name, repeatable")
    ap.add_argument("--report-id", help="default: <model-id>/from-breakdown")
    ap.add_argument("--peak-bf16-tflops", default="376")
    ap.add_argument("--dtype-bytes", default="2")
    ap.add_argument("--ep-rank", type=int,
                    help="expert-parallel rank of this capture. Only resolves WHICH expert "
                         "indices are resident in the expert inventory; the capture itself "
                         "does not record it.")
    ap.add_argument("--model-source",
                    help="model source provenance for the Skill 3 handoff; defaults to the "
                         "first architecture.source_of_truth entry")
    ap.add_argument("--extractor-model",
                    help="agent/model that produced the reviewed breakdown; defaults to the "
                         "breakdown generation provenance or perf-breakdown-skill")
    args = ap.parse_args()

    out = os.path.abspath(args.out)
    work = os.path.join(out, "work")
    facts = os.path.join(out, "ui_facts")
    repo = os.path.join(out, "ui-report")
    for d in (work, facts, repo):
        os.makedirs(d, exist_ok=True)
    stages = {}
    breakdown = os.path.abspath(args.breakdown)
    capture_dir = os.path.abspath(args.capture_dir or breakdown)
    config = breakdown_paths.resolve_config(breakdown, args.breakdown_config)

    # --- Stage 2: readiness -> node index -> attribution -> facts -------------------------
    S2 = os.path.join(STAGE2, "scripts")
    r = run([sys.executable, os.path.join(S2, "check_breakdown_ready.py"),
             "--breakdown", breakdown]
            + (["--config", config] if config else [])
            + [
             "--out", os.path.join(work, "readiness.json")])
    if r.returncode:
        die("failed", "readiness", r.stdout[-1200:], stages=stages)
    stages["readiness"] = "ready"

    raw = args.raw_ops or os.path.join(breakdown, "raw_ops.json")
    raw_details = args.raw_ops_details or os.path.join(breakdown, "raw_ops_details.json")
    if not os.path.exists(raw):
        die("failed", "conversion_inputs",
            f"no raw_ops.json at {raw}; Skill 2 needs representative-step kernels",
            stages=stages)
    trace = find_one(capture_dir, "trace_view.json", args.trace, stages=stages)
    device_freq = args.device_freq or os.path.join(breakdown, "device_freq.json")
    if not os.path.exists(device_freq):
        device_freq = None
    stages["conversion_inputs"] = {
        "breakdown": breakdown,
        "config": config,
        "raw_ops": raw,
        "raw_ops_details": raw_details if os.path.exists(raw_details) else None,
        "device_freq": device_freq,
        "trace": trace,
    }

    nodes = os.path.join(work, "node_index.json")
    cmd = [sys.executable, os.path.join(S2, "build_node_index.py"), "--breakdown", breakdown,
           "--config", config, "--namespace", f"model/{args.model_id}", "--out", nodes]
    for rename in args.rename_group:
        cmd += ["--rename-group", rename]
    r = run(cmd)
    if r.returncode:
        die("failed", "node_index", r.stderr[-800:], stages=stages)
    stages["node_index"] = "ok"

    attribution = os.path.join(work, "kernel_attribution.json")
    r = run([sys.executable, os.path.join(S2, "attribute_kernels.py"),
             "--breakdown", breakdown, "--config", config, "--nodes", nodes,
             "--kernels", raw, "--kernel-details", raw_details, "--out", attribution])
    if r.returncode:
        # Unequal invocation spans land here. Translating anyway would misattribute silently.
        die("failed", "attribution",
            (r.stderr or r.stdout)[-800:], stages=stages,
            hint="unequal invocation spans mean the group shares a template it should not; "
                 "split the differing layer into its own layer_group in stage 1")
    stages["attribution"] = "100% accounted"

    r = run([sys.executable, os.path.join(S2, "emit_ui_facts.py"), "--breakdown", breakdown,
             "--config", config, "--nodes", nodes, "--attribution", attribution,
             "--model-id", args.model_id,
             "--report-id", args.report_id or f"{args.model_id}/from-breakdown",
             "--peak-bf16-tflops", args.peak_bf16_tflops,
             "--dtype-bytes", args.dtype_bytes, "--out", facts]
            + (["--device-freq", device_freq] if device_freq else []))
    if r.returncode:
        die("failed", "emit_facts", r.stderr[-800:], stages=stages)
    stages["ui_facts"] = facts

    graph = os.path.join(repo, "report/outputs/model_architecture_graph.json")
    analysis_fact = os.path.join(facts, f"{args.model_id}_analysis_config.json")
    perf_fact = os.path.join(facts, f"{args.model_id}_perf_data.json")
    timeline_fact = os.path.join(facts, f"{args.model_id}_timeline.json")

    # MoE expert inventory. Only written for a model that declares experts; a dense model
    # produces nothing and that is not a failure.
    inventory_path = os.path.join(facts, f"{args.model_id}_expert_inventory.json")
    inventory_cmd = [sys.executable, os.path.join(S2, "build_expert_inventory.py"),
                     "--breakdown", breakdown, "--config", config,
                     "--performance", perf_fact, "--attribution", attribution,
                     "--out", inventory_path]
    if args.ep_rank is not None:
        inventory_cmd += ["--ep-rank", str(args.ep_rank)]
    r = run(inventory_cmd)
    stages["expert_inventory"] = (
        (r.stdout.strip().splitlines()[-1] if r.stdout else "ok") if r.returncode == 0
        else f"skipped: {(r.stderr or r.stdout)[-200:]}")

    r = run([sys.executable, os.path.join(S2, "build_architecture_graph.py"),
             "--analysis", analysis_fact, "--performance", perf_fact,
             "--breakdown", config, "--out", graph])
    if r.returncode:
        die("failed", "graph", (r.stderr or r.stdout)[-800:], stages=stages)
    stages["graph"] = "ok"

    # Stage 1 owns the graph/config consistency checks (layer coverage, repeat counts,
    # residual direction) but cannot run them at validation time: the graph does not exist
    # until the line above. Re-run that one check now, with the graph it was written for --
    # otherwise G2/G3/G7 are dead code for every capture driven through this pipeline.
    graph_report = os.path.join(work, "graph_consistency.json")
    r = run([sys.executable, os.path.join(STAGE1, "scripts/check_graph_consistency.py"),
             "-g", graph, "-c", config, "-o", graph_report])
    # Recording the outcome is not enforcing it. Without the die() below, a graph that drops a
    # declared layer (G3), disagrees with the config on group count (G2) or inverts a residual
    # (G7) still produced a finished report -- the 8.7ex run shipped with four such errors. G4
    # is a warning by design and stays non-blocking; only errors stop the run.
    graph_errors = []
    if os.path.exists(graph_report):
        try:
            with open(graph_report, "r", encoding="utf-8") as fh:
                graph_doc = json.load(fh)
            graph_errors = [i for i in (graph_doc.get("issues") or [])
                            if i.get("severity") == "error"]
        except (OSError, ValueError):
            graph_errors = []
    if graph_errors or r.returncode:
        codes = sorted({str(i.get("id") or i.get("code")) for i in graph_errors})
        stages["graph_consistency"] = f"errors {codes}" if codes else "failed"
        die("failed", "graph_consistency",
            "the rendered graph contradicts the config; a report built from it would show a "
            "structure the breakdown does not claim",
            report=graph_report, error_codes=codes,
            errors=[i.get("message") for i in graph_errors[:4]], stages=stages)
    stages["graph_consistency"] = "passed"

    r = run([sys.executable, os.path.join(S2, "validate_conversion.py"),
             "--out", facts, "--graph", graph, "--attribution", attribution])
    stages["conversion_validation"] = "passed" if r.returncode == 0 else "failed"
    if r.returncode:
        die("failed", "conversion_validation", r.stdout[-1200:], stages=stages)

    # --- Stage 3: assemble the interactive report -----------------------------------------
    if not trace:
        die("failed", "ui_report",
            "no trace_view.json in the capture; stage 3 requires the raw trace and it cannot "
            "be reconstructed after the fact", stages=stages)

    import shutil
    for fact in (analysis_fact, perf_fact, timeline_fact):
        shutil.copy(fact, repo)
    # The report renders one step, but a raw capture spans the whole run. Stage 3 inlines the
    # trace into a single JS string, so an unnarrowed multi-hundred-MB capture dies on Node's
    # max string length. Narrow to the representative step's window first; bindings and the
    # pager then operate on exactly the trace the report loads.
    staged_trace = os.path.join(repo, "trace_view.json")
    r = run([sys.executable, os.path.join(S2, "narrow_trace_window.py"),
             "--trace", trace, "--raw-ops", raw, "--output", staged_trace])
    if r.returncode:
        die("failed", "trace_window", (r.stderr or r.stdout)[-800:], stages=stages)
    try:
        stages["trace_window"] = json.loads(r.stdout)
    except (ValueError, TypeError):
        stages["trace_window"] = "narrowed"

    template = os.path.join(STAGE3, "assets/report-template")
    for root, _, files in os.walk(template):
        target = os.path.join(repo, "report", os.path.relpath(root, template))
        os.makedirs(target, exist_ok=True)
        for name in files:
            shutil.copy(os.path.join(root, name), os.path.join(target, name))

    # --- Real HBM series, before the empty placeholder gets a chance to exist ---------------
    # `build_overlay_and_config.py --write-empty-hbm` only writes when the file is absent, so
    # producing the real one first makes the placeholder a genuine fallback instead of the
    # default outcome. Previously nothing ever called build-hbm-data.mjs, so every report
    # shipped an empty series while the capture's samples sat unused on disk.
    hbm_outputs = os.path.join(repo, "report", "outputs")
    os.makedirs(hbm_outputs, exist_ok=True)
    hbm_needed = ["hbm_bandwidth_timeline.csv", "hbm_occupancy_timeline.csv",
                  "sample_op_mix.csv", "hbm_summary.json"]
    search_dirs = list(args.hbm_dir)
    if not search_dirs:
        for probe in ("derived/hbm", "derived/correlation", "derived"):
            candidate = os.path.join(capture_dir, probe)
            if os.path.isdir(candidate):
                search_dirs.append(candidate)
    found = {}
    for name in hbm_needed:
        for directory in search_dirs:
            candidate = os.path.join(directory, name)
            if os.path.isfile(candidate):
                found[name] = candidate
                break
    missing_hbm = [n for n in hbm_needed if n not in found]
    if missing_hbm:
        # Say which ones are missing. An empty panel with no explanation reads as "this
        # capture has no HBM data", which is a different claim from "they were not found".
        stages["hbm"] = f"empty series: missing {missing_hbm} under {search_dirs}"
    else:
        staged = os.path.join(work, "hbm_inputs")
        os.makedirs(staged, exist_ok=True)
        for name, src in found.items():
            shutil.copy(src, os.path.join(staged, name))
        r = run(["node", os.path.join(STAGE3, "scripts/build-hbm-data.mjs"),
                 "--input-dir", staged, "--out", os.path.join(hbm_outputs, "hbm_series.json")])
        if r.returncode:
            die("failed", "hbm", (r.stderr or r.stdout)[-800:], stages=stages)
        try:
            series = json.load(open(os.path.join(hbm_outputs, "hbm_series.json")))
            stages["hbm"] = {
                "bandwidth_points": len(series.get("bandwidth", {}).get("points") or []),
                "occupancy_points": len(series.get("occupancy", {}).get("points") or []),
                "peak_gbs": series.get("bandwidth", {}).get("peak_gbs"),
            }
        except (OSError, ValueError):
            stages["hbm"] = "built"

    r = run([sys.executable, os.path.join(S2, "build_overlay_and_config.py"),
             "--analysis", analysis_fact, "--performance", perf_fact, "--graph", graph,
             "--repo", repo, "--file-prefix", args.model_id, "--write-empty-hbm"]
            + (["--model-source", args.model_source] if args.model_source else [])
            + (["--extractor-model", args.extractor_model] if args.extractor_model else [])
            + (["--expert-inventory", inventory_path]
               if os.path.isfile(inventory_path) else []))
    if r.returncode:
        die("failed", "overlay", (r.stderr or r.stdout)[-800:], stages=stages)

    # Enrich in place: the pager reads `args.layer_index` off the trace the report loads, so the
    # enriched copy has to BE that trace, not a sidecar.
    r = run([sys.executable, os.path.join(S2, "build_trace_bindings.py"),
             "--timeline", timeline_fact, "--attribution", attribution,
             "--trace", os.path.join(repo, "trace_view.json"),
             "--enrich-trace", os.path.join(repo, "trace_view.json"),
             "--out", os.path.join(repo, "report/outputs/trace_bindings.json")])
    if r.returncode:
        die("failed", "bindings", (r.stderr or r.stdout)[-800:], stages=stages)
    stages["bindings"] = "ok"

    handoff = os.path.join(repo, "ui-report-handoff.json")
    r = run(["node", os.path.join(STAGE3, "scripts/generate-report.mjs"),
             "--repo", repo, "--handoff", handoff, "--refresh-template"])
    if r.returncode:
        die("failed", "ui_generation", (r.stderr or r.stdout)[-1200:], stages=stages)
    stages["ui_validation"] = "deterministic_passed"

    print(json.dumps({
        "status": "pending_manual_validation",
        "stages": stages,
        "breakdown_report": None,
        "ui_report": os.path.join(repo, "report/index.html"),
        "serve": f"cd {repo} && python3 -m http.server 8081   # then open /report/",
    }, ensure_ascii=False, indent=1))
    sys.exit(0)


if __name__ == "__main__":
    main()
