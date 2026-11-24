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
"""Refuse to convert a breakdown that has not earned it.

A conversion inherits every claim the breakdown makes. Exploratory runs, migrated
legacy configs, and stale critiques all produce a report that looks
authoritative while resting on unverified attribution, so they are rejected here
rather than downstream.
"""
import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import breakdown_paths  # noqa: E402

REQUIRED_CONFIG_KEYS = ("schema_version", "architecture", "trace_scope",
                        "structures", "stages", "runtime_auxiliary")
VALID_SCOPE_KINDS = ("full_model", "rank_local", "pipeline_stage_local", "unknown")

def jload(path):
    with open(path) as handle:
        return json.load(handle)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check(breakdown_dir, config_override=None):
    """Return (checks, blockers). A blocker means do not convert."""
    checks, blockers = [], []

    def record(ok, label, detail=""):
        checks.append({"ok": bool(ok), "check": label, "detail": detail})
        if not ok:
            blockers.append(f"{label}{f': {detail}' if detail else ''}")
        return ok

    config_path = breakdown_paths.resolve_config(breakdown_dir, config_override)
    label = f"{os.path.basename(config_path)} exists" if config_path else "breakdown config exists"
    if not record(config_path and os.path.exists(config_path), label,
                  config_path or f"none of {' / '.join(breakdown_paths.CONFIG_NAMES)} in {breakdown_dir}"):
        return checks, blockers
    config = jload(config_path)

    record(config.get("schema_version") == 2, "config is schema v2",
           f"found {config.get('schema_version')!r}")

    missing = [key for key in REQUIRED_CONFIG_KEYS if key not in config]
    record(not missing, "config declares every required block",
           f"missing {missing}" if missing else "")

    # A migrated v1 config is a structural lift, not a re-validation. Converting
    # one would present unverified layer attribution as measured fact.
    migration = config.get("migration") or {}
    if migration:
        record(migration.get("status") != "legacy_unverified",
               "config is not an unverified legacy migration",
               f"migration.status={migration.get('status')!r}")

    unmapped = config.get("unmapped_ops") or []
    record(not unmapped, "unmapped_ops is empty",
           f"{len(unmapped)} unmapped ops" if unmapped else "")

    scope = (config.get("trace_scope") or {}).get("kind")
    record(scope in VALID_SCOPE_KINDS, "trace_scope.kind is declared",
           f"found {scope!r}")

    validation_path = os.path.join(breakdown_dir, "validation_report.json")
    if record(os.path.exists(validation_path), "validation_report.json exists"):
        validation = jload(validation_path)
        status = validation.get("status")
        record(status == "passed", "validation status passed", f"status={status!r}")

    critique_path = os.path.join(breakdown_dir, "critique_report.json")
    critique = None
    if record(os.path.exists(critique_path), "critique_report.json exists"):
        critique = jload(critique_path)
        record(critique.get("status") == "passed", "critique status passed",
               f"status={critique.get('status')!r}")

    critique_validation_path = os.path.join(breakdown_dir, "critique_validation.json")
    if record(os.path.exists(critique_validation_path), "critique_validation.json exists"):
        critique_validation = jload(critique_validation_path)
        record(critique_validation.get("status") == "passed",
               "critique validation status passed",
               f"status={critique_validation.get('status')!r}")
        clears_candidate = ((critique_validation.get("detail") or {})
                            .get("clears_candidate"))
        record(clears_candidate is True, "critique validation clears candidate",
               f"detail.clears_candidate={clears_candidate!r}")

    score_path = os.path.join(breakdown_dir, "breakdown_score.json")
    if record(os.path.exists(score_path), "breakdown_score.json exists"):
        score = jload(score_path)
        record(breakdown_paths.is_convertible_score(score),
               "score formal gates passed",
               f"passed_at_cap={score.get('passed_at_cap')!r} "
               f"convertible={score.get('convertible')!r} "
               f"hard_gates.passed={(score.get('hard_gates') or {}).get('passed')!r} "
               f"critique_gates.passed="
               f"{(score.get('critique_gates') or {}).get('passed')!r}")

    if critique is not None:
        bound = breakdown_paths.review_config_sha256(critique)
        if bound:
            actual = sha256(config_path)
            record(bound == actual, "critique still matches the config",
                   "review was produced for a different config revision"
                   if bound != actual else "")
        else:
            # A critique with no recorded digest cannot be shown to describe THIS config, and an
            # unverifiable binding is exactly the silent skip this skill forbids elsewhere:
            # recording `ok: True` here claimed the staleness defence had run when it had not.
            record(False, "critique is bound to the config by SHA256",
                   "review records no config_sha256, so staleness cannot be verified; "
                   "re-run the review preparation against the current config")

    return checks, blockers


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--breakdown", required=True,
                        help="directory holding the breakdown config and its reports")
    parser.add_argument("--config",
                        help="explicit config path; defaults to "
                             f"{' or '.join(breakdown_paths.CONFIG_NAMES)} in --breakdown")
    parser.add_argument("--out", help="write the readiness record here")
    args = parser.parse_args()

    checks, blockers = check(args.breakdown, args.config)
    ready = not blockers
    record = {
        "schema_version": 1,
        "breakdown": os.path.abspath(args.breakdown),
        "ready": ready,
        "checks": checks,
        "blockers": blockers,
    }
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w") as handle:
            json.dump(record, handle, ensure_ascii=False, indent=1)
            handle.write("\n")

    for item in checks:
        print(f"{'PASS' if item['ok'] else 'FAIL'}  {item['check']}"
              + (f"  — {item['detail']}" if item["detail"] else ""))
    print()
    if ready:
        print(f"READY  {len(checks)} checks passed; conversion may proceed")
        return 0
    print(f"NOT READY  {len(blockers)} blocker(s):")
    for blocker in blockers:
        print(f"  - {blocker}")
    print("Fix the breakdown. Do not convert an unverified breakdown.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
