# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
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
# ----------------------------------------------------------------------------

import copy
import json
from pathlib import Path
import sys
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from fault_trace_core import build_trace, validate_trace  # noqa: E402
from fault_trace_core.component_chain import build_component_chain_summary  # noqa: E402
from fault_trace_core.pipeline import TraceValidationError  # noqa: E402


def observed_event(
    event_id: str,
    component: str,
    offset_us: int,
    *,
    level: str = "ERROR",
    interaction: str | None = None,
    message: str | None = None,
) -> dict[str, object]:
    event: dict[str, object] = {
        "id": event_id,
        "kind": "observed",
        "level": level,
        "component": component,
        "raw_component": component,
        "message": message or f"{component} event",
        "location": "host",
        "execution": {"process": "app", "pid": "7"},
        "timestamp": {
            "raw": f"2026-09-21-10:00:00.{offset_us:06d}",
            "clock_domain_id": "clock-host",
            "offset_us": offset_us,
            "precision": "microsecond",
        },
        "evidence_ids": [f"evidence-{event_id}"],
    }
    if interaction is not None:
        event["interaction"] = interaction
    return event


def relationship(
    relationship_id: str,
    source: str,
    target: str,
    *,
    kind: str,
    strength: str,
) -> dict[str, object]:
    return {
        "id": relationship_id,
        "source_event_id": source,
        "target_event_id": target,
        "kind": kind,
        "strength": strength,
        "rule_id": f"{kind}-test-v1",
        "evidence_ids": [f"evidence-{source}", f"evidence-{target}"],
    }


class ComponentChainContractTest(unittest.TestCase):
    def test_summary_uses_normal_call_direction_and_preserves_strength(self):
        events = [
            observed_event("app", "Application", 40, message="ERR00100 call failed"),
            observed_event("runtime", "Runtime", 20, interaction="error-propagation"),
            observed_event(
                "hccl",
                "HCCL",
                10,
                interaction="error-source",
                message="channel connect timeout hcclRet=9",
            ),
            observed_event("aicpu", "AICPU", 30, level="INFO"),
        ]
        relationships = [
            relationship(
                "rel-app-runtime",
                "app",
                "runtime",
                kind="same-execution",
                strength="proven",
            ),
            relationship(
                "rel-runtime-hccl",
                "runtime",
                "hccl",
                kind="hypothesis",
                strength="inferred",
            ),
            relationship(
                "rel-hccl-aicpu",
                "hccl",
                "aicpu",
                kind="same-execution",
                strength="proven",
            ),
            relationship(
                "rel-hccl-app-error",
                "hccl",
                "app",
                kind="error-propagation",
                strength="proven",
            ),
        ]

        summary = build_component_chain_summary(
            events,
            relationships,
            "app",
            [event["id"] for event in events],
        )

        self.assertEqual(summary["schema_version"], "1.0.0")
        self.assertEqual(
            [node["component"] for node in summary["nodes"]],
            ["Application", "Runtime", "HCCL", "AICPU"],
        )
        self.assertEqual(
            {
                (edge["source_component"], edge["target_component"]): edge["strength"]
                for edge in summary["edges"]
            },
            {
                ("Application", "Runtime"): "proven",
                ("Runtime", "HCCL"): "inferred",
                ("HCCL", "AICPU"): "proven",
            },
        )
        roles = {node["component"]: node["fault_role"] for node in summary["nodes"]}
        self.assertEqual(roles["Application"], "business-error")
        self.assertEqual(roles["HCCL"], "fault-source")
        app = summary["nodes"][0]
        self.assertEqual(
            app["deep_link"],
            {
                "view": "fault",
                "anchor": "app",
                "component": "Application",
                "event": "app",
            },
        )
        self.assertEqual(summary["gaps"], [])

    def test_normal_context_expands_chain_only_without_cross_component_chain(self):
        events = [
            observed_event("acl", "AscendCL", 10, level="INFO"),
            observed_event("runtime", "Runtime", 30, level="INFO"),
            observed_event("driver", "Driver", 60, level="INFO"),
        ]
        relationships = [
            relationship(
                "rel-acl-runtime",
                "acl",
                "runtime",
                kind="hypothesis",
                strength="inferred",
            ),
            relationship(
                "rel-runtime-driver",
                "runtime",
                "driver",
                kind="hypothesis",
                strength="inferred",
            ),
        ]

        summary = build_component_chain_summary(
            events,
            relationships,
            "acl",
            ["acl"],
            ["runtime", "driver"],
        )

        self.assertEqual(
            [node["component"] for node in summary["nodes"]],
            ["AscendCL", "Runtime", "Driver"],
        )
        self.assertEqual(
            {
                (edge["source_component"], edge["target_component"]): edge["strength"]
                for edge in summary["edges"]
            },
            {
                ("AscendCL", "Runtime"): "inferred",
                ("Runtime", "Driver"): "inferred",
            },
        )
        self.assertEqual(summary["gaps"], [])

    def test_fault_chain_ignores_context_when_cross_component_chain_exists(self):
        events = [
            observed_event("app", "Application", 40),
            observed_event("hccl", "HCCL", 10, interaction="error-source"),
            observed_event("driver", "Driver", 100, level="INFO"),
        ]
        relationships = [
            relationship(
                "rel-app-hccl",
                "app",
                "hccl",
                kind="error-propagation",
                strength="proven",
            ),
            relationship(
                "rel-hccl-driver",
                "hccl",
                "driver",
                kind="hypothesis",
                strength="inferred",
            ),
        ]

        summary = build_component_chain_summary(
            events,
            relationships,
            "app",
            ["app", "hccl"],
            ["driver"],
        )

        self.assertEqual(
            [node["component"] for node in summary["nodes"]],
            ["Application", "HCCL"],
        )
        self.assertTrue(summary["edges"])

    def test_summary_keeps_observed_components_when_relationships_are_missing(self):
        events = [
            observed_event("runtime", "Runtime", 1, interaction="error-source"),
            observed_event("hccl", "HCCL", 2),
        ]

        summary = build_component_chain_summary(
            events,
            [],
            "runtime",
            ["runtime", "hccl"],
        )

        self.assertEqual(
            [node["component"] for node in summary["nodes"]],
            ["Runtime", "HCCL"],
        )
        self.assertEqual(summary["edges"], [])
        self.assertEqual(summary["gaps"], ["call_relationship_evidence_insufficient"])

    def test_build_trace_publishes_derivable_component_chain(self):
        trace = build_trace(SKILL_ROOT / "tests" / "fixtures" / "minimal-plog")

        self.assertEqual(trace["component_chain"]["anchor_id"], trace["selected_anchor_id"])
        self.assertTrue(trace["component_chain"]["nodes"])
        self.assertEqual(trace["component_chain"]["gaps"], [])
        validate_trace(trace)

        invalid = copy.deepcopy(trace)
        invalid["component_chain"]["nodes"][0]["component"] = "ArchitectureOnlyGhost"
        with self.assertRaises(TraceValidationError):
            validate_trace(invalid)

    def test_schema_publishes_component_chain_and_current_error_fields(self):
        schema = json.loads(
            (SKILL_ROOT / "schemas" / "fault-trace-v1.schema.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(schema["properties"]["component_chain"]["$ref"], "#/$defs/componentChain")
        self.assertNotIn("component_chain", schema["required"])
        self.assertIn(
            "error-propagation",
            schema["$defs"]["relationship"]["properties"]["kind"]["enum"],
        )
        self.assertIn(
            "error-source",
            schema["$defs"]["event"]["properties"]["interaction"]["enum"],
        )
        correlation_names = schema["$defs"]["event"]["properties"]["correlation"][
            "propertyNames"
        ]["enum"]
        for name in ("error_code", "hccl_ret", "rank_id"):
            self.assertIn(name, correlation_names)


if __name__ == "__main__":
    unittest.main()
