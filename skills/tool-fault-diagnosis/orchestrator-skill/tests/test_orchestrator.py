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
"""Regression tests for the orchestrator-owned routing and clean stages."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_pipeline.py"
spec = importlib.util.spec_from_file_location("run_pipeline", SCRIPT)
run_pipeline = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(SCRIPT.parent))
spec.loader.exec_module(run_pipeline)

UNRELATED_CASE = (
    "# Test fixture only\n\n"
    "## CASE-100：通信超时\n\n"
    "**关键日志特征**\n```\n"
    "[ERROR][HCCL] EI0002 Communication_Error_Timeout\n```\n"
)


def load_detector():
    script = SCRIPT.parent / "detect_scenario.py"
    detector_spec = importlib.util.spec_from_file_location("detect_scenario", script)
    module = importlib.util.module_from_spec(detector_spec)
    detector_spec.loader.exec_module(module)
    return module


class RoutingTests(unittest.TestCase):
    def test_miss_and_unknown_still_have_full_route(self):
        detector = load_detector()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "normal.txt"
            path.write_text("INFO job step completed\n", encoding="utf-8")
            library = Path(temp) / "cases.md"
            library.write_text(UNRELATED_CASE, encoding="utf-8")
            scan = detector.scan_input(path)
            lookup = detector.lookup_cases(scan, "training interrupted", case_library=library)
            plan = detector.build_plan(path, "training interrupted", case_library=library,
                                       case_lookup_result=lookup)
        self.assertEqual(lookup["status"], "miss")
        self.assertEqual(lookup["cases_examined"], 1)
        self.assertEqual(plan["case_lookup"]["status"], "miss")
        self.assertEqual(plan["primary"], "unknown")
        self.assertEqual(plan["route"]["pipeline_stages"], list(run_pipeline.STAGE_IDS))

    def test_unavailable_library_still_classifies(self):
        detector = load_detector()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "oom.txt"
            path.write_text("ERROR Memory_Allocation_Failure HBM alloc failed\n", encoding="utf-8")
            scan = detector.scan_input(path)
            missing_library = Path(temp) / "cases.md"
            lookup = detector.lookup_cases(scan, "training interrupted", case_library=missing_library)
            plan = detector.build_plan(path, "training interrupted",
                                       case_library=missing_library,
                                       case_lookup_result=lookup)
        self.assertEqual(lookup["status"], "unavailable")
        self.assertEqual(plan["case_lookup"]["status"], "unavailable")
        self.assertEqual(plan["primary"], "oom")
        self.assertEqual(plan["route"]["pipeline_stages"], list(run_pipeline.STAGE_IDS))



    def test_generic_log_report_request_enters_orchestrator(self):
        """Regression: a generic report request must expose orchestrator first."""
        detector = load_detector()
        request = "分析当前目录日志，生成诊断报告"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "current.log"
            path.write_text("INFO job step completed\n", encoding="utf-8")
            plan = detector.build_plan(path, request)
        route = plan["route"]
        self.assertEqual(route["entry_skill"], "orchestrator-skill")
        self.assertEqual(route["downstream_skills"], ["eval-skill", "trace-skill", "metric-skill"])
        self.assertEqual(route["skills"], ["orchestrator-skill", "eval-skill", "trace-skill", "metric-skill"])
        self.assertEqual(route["pipeline_stages"], list(run_pipeline.STAGE_IDS))
        self.assertEqual(route["pipeline_stages"][:2], ["case_lookup", "detect"])
        self.assertTrue(plan["uncertain"])

        # A fault token in the raw log must not turn a generic request into an
        # eval shortcut; only the user's explicit request selects a specialist.
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "current.log"
            path.write_text("[ERROR] AI Core Error\n", encoding="utf-8")
            plan = detector.build_plan(path, request)
        self.assertEqual(plan["route"]["entry_skill"], "orchestrator-skill")

    def test_explicit_eval_request_can_use_specialist_entry(self):
        detector = load_detector()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "aicore.log"
            path.write_text("[ERROR][AI_CORE] EZ9999 AICORE error\n", encoding="utf-8")
            plan = detector.build_plan(path, "请用 eval-skill 分析 AI Core Error")
            scenario_plan = detector.build_plan(path, "分析 AI Core Error 日志")
        self.assertEqual(plan["route"]["entry_skill"], "eval-skill")
        self.assertEqual(plan["route"]["downstream_skills"], [])
        self.assertEqual(scenario_plan["route"]["entry_skill"], "eval-skill")

    def test_existing_diagnosis_can_enter_metric_for_html(self):
        detector = load_detector()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "current.log"
            path.write_text("INFO report input\n", encoding="utf-8")
            plan = detector.build_plan(path, "根据已有 diagnosis.md 生成 HTML 报告")
        self.assertEqual(plan["route"]["entry_skill"], "metric-skill")
        self.assertEqual(plan["route"]["downstream_skills"], [])


class CaseLookupRuleTests(unittest.TestCase):
    def test_cann_timestamp_is_extracted(self):
        detector = load_detector()
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "plog.log"
            source.write_text(
                "[ERROR] ROCE(23799,hccp_service.bin):"
                "2024-07-14-23:23:39.191.542 reg ai mr failed\n",
                encoding="utf-8",
            )
            scan = detector.scan_input(source)

        self.assertEqual(len(scan["errors"]), 1)
        self.assertEqual(
            scan["errors"][0]["timestamp"], "2024-07-14-23:23:39.191.542"
        )

    def _temporary_library(self, temp, signatures):
        path = Path(temp) / "cases.md"
        path.write_text("# Accepted cases" + "\n\n" + signatures, encoding="utf-8")
        return path

    def test_strong_error_code_hits_but_remains_candidate_only(self):
        detector = load_detector()
        with tempfile.TemporaryDirectory() as temp:
            library = self._temporary_library(
                temp,
                "## CASE-100：通信超时" + "\n\n**关键日志特征**\n```\n"
                "[ERROR][HCCL] EI0002 Communication_Error_Timeout\n```\n",
            )
            source = Path(temp) / "event.log"
            source.write_text(
                "[ERROR][HCCL] EI0002 Communication_Error_Timeout\n",
                encoding="utf-8",
            )
            scan = detector.scan_input(source)
            lookup = detector.lookup_cases(
                scan, "communication timeout", case_library=library
            )
        self.assertEqual(lookup["status"], "hit")
        self.assertEqual(lookup["cases_examined"], 1)
        self.assertEqual(len(lookup["matches"]), 1)
        self.assertEqual(lookup["matches"][0]["case_id"], "CASE-100")
        self.assertIn("strong_error_code", lookup["matches"][0]["match_methods"])
        self.assertEqual(lookup["matches"][0]["root_cause_status"], "candidate_only")

    def test_ez9999_and_generic_words_do_not_hit(self):
        detector = load_detector()
        with tempfile.TemporaryDirectory() as temp:
            library = self._temporary_library(
                temp,
                "## CASE-101：AI Core Error" + "\n\n**关键日志特征**\n```\n"
                "[ERROR][GE] EZ9999 aicore error\n"
                "[ERROR][MEM] HBM allocation failed timeout\n```\n",
            )
            source = Path(temp) / "event.log"
            source.write_text(
                "[ERROR][GE] EZ9999 aicore error\n"
                "[ERROR][MEM] HBM allocation failed timeout\n",
                encoding="utf-8",
            )
            scan = detector.scan_input(source)
            lookup = detector.lookup_cases(scan, "aicore error", case_library=library)
        self.assertEqual(lookup["status"], "miss")
        self.assertEqual(lookup["cases_examined"], 1)
        self.assertEqual(lookup["matches"], [])

    def test_pending_library_is_rejected(self):
        detector = load_detector()
        with tempfile.TemporaryDirectory() as temp:
            pending = Path(temp) / "cases-pending.md"
            pending.write_text("## PCASE-100：candidate\n", encoding="utf-8")
            source = Path(temp) / "event.log"
            source.write_text(
                "[ERROR][HCCL] EI0002 Communication_Error_Timeout\n",
                encoding="utf-8",
            )
            scan = detector.scan_input(source)
            with self.assertRaises(ValueError):
                detector.lookup_cases(
                    scan, "communication timeout", case_library=pending
                )

    def test_indexed_category_file_loaded_once_per_link(self):
        detector = load_detector()
        with tempfile.TemporaryDirectory() as temp:
            library = self._temporary_library(
                temp,
                "| 分类 | 案例文件 | 编号 |\n| --- | --- | --- |\n"
                "| 进程卡住 | [cases-hang.md](cases-hang.md) | CASE-HANG-001 |\n"
                "| 进程卡住 | [cases-hang.md](cases-hang.md) | CASE-HANG-001 |\n"
                "| 进程卡住 | [cases-hang.md](cases-hang.md) | CASE-HANG-001 |\n",
            )
            category = Path(temp) / "cases-hang.md"
            source = Path(temp) / "event.log"
            source.write_text(
                "[ERROR][HCCL] EI0002 Communication_Error_Timeout\n",
                encoding="utf-8",
            )
            scan = detector.scan_input(source)
            # The linked category file is absent; the index itself has no CASE block.
            lookup = detector.lookup_cases(scan, "communication timeout", case_library=library)
            self.assertEqual(lookup["status"], "unavailable")
            self.assertEqual(lookup["cases_examined"], 0)
            category.write_text(
                "# 进程卡住 案例集\n\n## CASE-HANG-001：通信超时\n\n"
                "**关键日志特征**\n```\n[ERROR][HCCL] EI0002 Communication_Error_Timeout\n```\n",
                encoding="utf-8",
            )
            lookup = detector.lookup_cases(scan, "communication timeout", case_library=library)
            self.assertEqual(lookup["status"], "hit")
            # Three index rows link the same file, but its cases are examined once.
            self.assertEqual(lookup["cases_examined"], 1)
            self.assertEqual(len(lookup["matches"]), 1)
            self.assertEqual(lookup["matches"][0]["case_id"], "CASE-HANG-001")

    def test_pipeline_library_hash_matches_lookup_with_bom_and_crlf(self):
        detector = load_detector()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            index = root / "cases.md"
            category = root / "cases-hang.md"
            index.write_text(
                "| 分类 | 案例文件 | 编号 |\n| --- | --- | --- |\n"
                "| 进程卡住 | [cases-hang.md](cases-hang.md) | CASE-HANG-001 |\n",
                encoding="utf-8-sig")
            category.write_bytes(
                b"\xef\xbb\xbf# Hang\r\n\r\n## CASE-HANG-001\r\n")
            source = root / "event.log"
            source.write_bytes(
                b"\xef\xbb\xbf[ERROR][HCCL] EI0002 Communication_Error_Timeout\r\n")
            scan = detector.scan_input(source)
            lookup = detector.lookup_cases(
                scan, "communication timeout", case_library=index)
            self.assertEqual(
                run_pipeline.library_hash(index), lookup["library_sha256"])

    def test_library_hash_changes_when_category_file_changes(self):
        detector = load_detector()
        with tempfile.TemporaryDirectory() as temp:
            library = self._temporary_library(
                temp,
                "| 分类 | 案例文件 | 编号 |\n| --- | --- | --- |\n"
                "| 进程卡住 | [cases-hang.md](cases-hang.md) | CASE-HANG-001 |\n",
            )
            category = Path(temp) / "cases-hang.md"
            category.write_text(
                "# 进程卡住 案例集\n\n## CASE-HANG-001：通信超时\n\n"
                "**关键日志特征**\n```\n[ERROR][HCCL] EI0002 Communication_Error_Timeout\n```\n",
                encoding="utf-8",
            )
            source = Path(temp) / "event.log"
            source.write_text("[ERROR][HCCL] EI0002 Communication_Error_Timeout\n", encoding="utf-8")
            scan = detector.scan_input(source)
            first = detector.lookup_cases(scan, "communication timeout", case_library=library)
            category.write_text(
                "# 进程卡住 案例集\n\n## CASE-HANG-001：通信超时\n\n"
                "**关键日志特征**\n```\n[ERROR][HCCL] EI0002 Communication_Error_Timeout changed\n```\n",
                encoding="utf-8",
            )
            second = detector.lookup_cases(scan, "communication timeout", case_library=library)
            self.assertNotEqual(first["library_sha256"], second["library_sha256"])

    def test_pipeline_library_hash_matches_lookup_digest(self):
        detector = load_detector()
        with tempfile.TemporaryDirectory() as temp:
            original = Path(temp)
            index = original / "cases.md"
            category = original / "cases-hang.md"
            index.write_text(
                "| 分类 | 案例文件 | 编号 |\n| --- | --- | --- |\n"
                "| 进程卡住 | [cases-hang.md](cases-hang.md) | CASE-HANG-001 |\n",
                encoding="utf-8",
            )
            category.write_text(
                "# 进程卡住 案例集\n\n## CASE-HANG-001：通信超时\n",
                encoding="utf-8",
            )
            source = original / "event.log"
            source.write_text(
                "[ERROR][HCCL] EI0002 Communication_Error_Timeout\n",
                encoding="utf-8",
            )
            scan = detector.scan_input(source)
            lookup = detector.lookup_cases(
                scan, "communication timeout", case_library=index
            )
            self.assertEqual(
                run_pipeline.library_hash(index), lookup["library_sha256"]
            )
            # Even callers that pass a relative path must use the same whole-library
            # digest; otherwise publication receipts and case_lookup fingerprints
            # silently fall back to different hash domains.
            relative = Path(os.path.relpath(index, original.cwd()))
            self.assertEqual(
                run_pipeline.library_hash(relative), lookup["library_sha256"]
            )

    def test_missing_category_file_surfaces_limitation(self):
        detector = load_detector()
        with tempfile.TemporaryDirectory() as temp:
            library = self._temporary_library(
                temp,
                "[cases-hang.md](cases-hang.md)\n\n## CASE-HANG-001：通信超时" +
                "\n\n**关键日志特征**\n```\n"
                "[ERROR][HCCL] EI0002 Communication_Error_Timeout\n```\n",
            )
            source = Path(temp) / "event.log"
            source.write_text(
                "[ERROR][HCCL] EI0002 Communication_Error_Timeout\n",
                encoding="utf-8",
            )
            scan = detector.scan_input(source)
            lookup = detector.lookup_cases(scan, "communication timeout", case_library=library)
            self.assertTrue(any(
                "cases-hang.md" in note and "missing or unreadable" in note
                for note in lookup["limitations"]))

    def test_pending_category_link_is_not_loaded(self):
        detector = load_detector()
        with tempfile.TemporaryDirectory() as temp:
            library = self._temporary_library(temp, "[cases-pending.md](cases-pending.md)\n")
            pending = Path(temp) / "cases-pending.md"
            pending.write_text("## CASE-HANG-001：candidate\n\n**关键日志特征**\n```\n[ERROR][HCCL] EI0002 Communication_Error_Timeout\n```\n", encoding="utf-8")
            source = Path(temp) / "event.log"
            source.write_text("[ERROR][HCCL] EI0002 Communication_Error_Timeout\n", encoding="utf-8")
            scan = detector.scan_input(source)
            lookup = detector.lookup_cases(scan, "communication timeout", case_library=library)
            self.assertEqual(lookup["cases_examined"], 0)
            self.assertEqual(lookup["status"], "unavailable")


class CleanTests(unittest.TestCase):
    def test_conservative_clean_separates_files_without_final_newline(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / "first.log"
            second = root / "second.log"
            first.write_bytes(b"ERROR first")
            second.write_bytes(b"ERROR second\n")
            output = root / "cleaned.log"
            audit = root / "clean-audit.md"
            run_pipeline.conservative_clean([first, second], output, audit)
            self.assertEqual(output.read_bytes(), b"ERROR first\nERROR second\n")
            records = json.loads(audit.read_text(encoding="utf-8").split("```json", 1)[1].split("```", 1)[0])["records"]
            self.assertEqual([record["output_line"] for record in records], [1, 2])

    def test_conservative_clean_keeps_same_heartbeat_from_distinct_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / "first.log"
            second = root / "second.log"
            first.write_bytes(b"DEBUG heartbeat ready\n")
            second.write_bytes(b"DEBUG heartbeat ready\n")
            result = run_pipeline.conservative_clean(
                [first, second], root / "cleaned.log", root / "clean-audit.md")
            self.assertEqual(result["collapsed_lines"], 0)
            self.assertEqual((root / "cleaned.log").read_bytes(),
                             b"DEBUG heartbeat ready\nDEBUG heartbeat ready\n")

    def test_conservative_clean_preserves_original_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "input.log"
            original = b"ERROR raw byte \xff\nDEBUG heartbeat ready\nDEBUG heartbeat ready\n"
            source.write_bytes(original)
            output = root / "cleaned.log"
            audit = root / "clean-audit.md"
            result = run_pipeline.conservative_clean([source], output, audit)
            self.assertEqual(output.read_bytes(), b"ERROR raw byte \xff\nDEBUG heartbeat ready\n")
            self.assertEqual(result["collapsed_lines"], 1)

    def test_conservative_clean_preserves_evidence_and_maps_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "input.log"
            source.write_text(
                "ERROR first failure\n"
                "ERROR first failure\n"
                "\n"
                "DEBUG heartbeat ready\n"
                "DEBUG heartbeat ready\n"
                "DEBUG heartbeat ready\n"
                "ERROR second failure\n",
                encoding="utf-8",
            )
            output = root / "cleaned.log"
            audit = root / "clean-audit.md"
            result = run_pipeline.conservative_clean([source], output, audit)
            cleaned_text = output.read_text(encoding="utf-8")
            audit_text = audit.read_text(encoding="utf-8")
        self.assertEqual(result["input_lines"], 7)
        self.assertEqual(result["kept_lines"], 5)
        self.assertEqual(result["collapsed_lines"], 2)
        self.assertEqual(result["input_lines"], result["kept_lines"] + result["collapsed_lines"])
        self.assertNotIn("clean", run_pipeline.SCRIPTS)
        self.assertEqual(cleaned_text.splitlines(),
                         ["ERROR first failure", "ERROR first failure", "",
                          "DEBUG heartbeat ready", "ERROR second failure"])
        audit_data = json.loads(audit_text.split("```json", 1)[1].split("```", 1)[0])
        self.assertEqual(len(audit_data["records"]), 7)
        self.assertEqual(sum(r["action"] == "collapsed" for r in audit_data["records"]), 2)
        self.assertEqual(audit_data["records"][0]["source"], str(source.resolve()))


class PipelineTests(unittest.TestCase):
    def test_miss_unknown_clean_then_complete_auto_pipeline(self):
        detector = load_detector()
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "normal.txt"
            source.write_text("INFO job step completed\n", encoding="utf-8")
            library = Path(temp) / "cases.md"
            library.write_text(UNRELATED_CASE, encoding="utf-8")
            state = Path(temp) / "state"
            plan = Path(temp) / "plan.json"
            lookup = detector.lookup_cases(source, "training interrupted", case_library=library)
            self.assertEqual(lookup["status"], "miss")
            self.assertEqual(lookup["cases_examined"], 1)
            plan.write_text(json.dumps({
                "input": {"path": str(source), "request": "training interrupted"},
                "case_lookup": {"library_path": str(library)},
                "stages": {"clean": {"level": "DEBUG"}, "promote": {"enabled": False},
                           "diagnose": {"execution": "evidence_only"}},
            }, ensure_ascii=False), encoding="utf-8")
            command = [sys.executable, str(SCRIPT), "--plan", str(plan), "--state-dir", str(state)]
            first = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=30)
            second = subprocess.run(command + ["--resume"], capture_output=True, text=True, encoding="utf-8", timeout=30)
            state_data = json.loads((state / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(first.returncode, 0)
        self.assertEqual(second.returncode, 0)
        self.assertEqual(state_data["stages"]["case_lookup"]["status"], "success")
        self.assertEqual(state_data["stages"]["detect"]["status"], "success")
        self.assertEqual(state_data["stages"]["clean"]["status"], "success")
        self.assertEqual(state_data["stages"]["diagnose"]["status"], "success")
        self.assertEqual(state_data["stages"]["confidence"]["status"], "success")
        self.assertEqual(state_data["stages"]["promote"]["status"], "skipped")
        self.assertEqual(state_data["stages"]["report"]["status"], "success")
        self.assertFalse((state / "attempts").exists())


class PromotionTests(unittest.TestCase):
    def test_accept_promotion_commits_category_and_index(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cases = root / "cases"
            cases.mkdir()
            index = cases / "cases.md"
            category = cases / "cases-hang.md"
            index.write_text("# 常见问题案例库\n\n| 分类 | 案例文件 | 编号 |\n| --- | --- | --- |\n| 进程卡住 | [cases-hang.md](cases-hang.md) | CASE-HANG-001 |\n", encoding="utf-8")
            category.write_text("# 进程卡住 案例集\n\n## CASE-HANG-001：old\n", encoding="utf-8")
            work = root / "work"
            work.mkdir()
            report = work / "diagnosis.md"
            diagnosis_contract = {
                "schema_version": "1.0",
                "run_id": "test-run",
                "stage": "diagnose",
                "owner_skill": "eval-skill",
                "status": "success",
                "attempt": 1,
                "started_at": "2026-11-10T00:00:00+00:00",
                "finished_at": "2026-11-10T00:00:01+00:00",
                "inputs": {"fingerprint": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "materials": [], "upstream": [], "parameters": {}},
                "outputs": [],
                "summary": "test",
                "evidence_gaps": [],
                "error": None,
                "next_action": "complete",
                "result": {},
            }
            report.write_text("```json\n" + json.dumps(diagnosis_contract, ensure_ascii=False, indent=2) + "\n```\n\n# Diagnosis\n\n## 问题摘要\n\n进程卡住 timeout\n\n## 关键日志\n\nERROR timeout\n\n## 根因分析\n\nhang\n\n## 修复建议\n\nfix\n", encoding="utf-8")
            confidence = work / "confidence.json"
            contract = {
                "schema_version": "1.0",
                "run_id": "test-run",
                "stage": "confidence",
                "owner_skill": "eval-skill",
                "status": "success",
                "attempt": 1,
                "started_at": "2026-11-10T00:00:00+00:00",
                "finished_at": "2026-11-10T00:00:01+00:00",
                "inputs": {"fingerprint": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "materials": [], "upstream": [], "parameters": {}},
                "outputs": [],
                "summary": "test",
                "evidence_gaps": [],
                "error": None,
                "next_action": "complete",
                "result": {"case_gate": "accept", "final_score": 90, "level": "HIGH"},
            }
            confidence.write_text("```json\n" + json.dumps(contract, ensure_ascii=False, indent=2) + "\n```\n", encoding="utf-8")
            state_dir = root / "state"
            state_dir.mkdir()
            class Plan:
                state_dir = Path(root) / "state"
                library = index
                def params(self, sid):
                    return {"enabled": True, "cases_dir": str(cases)}
                def artifact(self, sid):
                    return confidence if sid == "confidence" else report
            artifact = {"result": {}, "outputs": []}
            state = {"run_id": "test-run"}
            result = run_pipeline.promote(Plan(), state, artifact, work)
            self.assertIn("CASE-HANG-002", result)
            self.assertIn("CASE-HANG-002", category.read_text(encoding="utf-8"))
            self.assertIn("CASE-HANG-002", index.read_text(encoding="utf-8"))
            # Promotion must append, never overwrite: the pre-existing case stays.
            self.assertIn("CASE-HANG-001", category.read_text(encoding="utf-8"))
            self.assertIn("CASE-HANG-001", index.read_text(encoding="utf-8"))
            index_lines = index.read_text(encoding="utf-8").splitlines()
            self.assertTrue(index_lines[-1].startswith("| 进程卡住 |"))
            self.assertIn("| CASE-HANG-002 |", index_lines[-1])
            self.assertTrue(index_lines[-2].startswith("| 进程卡住 |"))
            self.assertEqual(artifact["result"]["target"], ["cases-hang.md", "cases.md"])
            self.assertEqual(artifact["result"]["decision"], "committed")

    def test_accept_promotion_creates_missing_category_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cases = root / "cases"
            cases.mkdir()
            index = cases / "cases.md"
            index.write_text("# 常见问题案例库\n\n| 分类 | 案例文件 | 编号 |\n| --- | --- | --- |\n| 进程卡住 | [cases-hang.md](cases-hang.md) | CASE-HANG-001 |\n", encoding="utf-8")
            (cases / "cases-hang.md").write_text("# 进程卡住 案例集\n\n## CASE-HANG-001：old\n", encoding="utf-8")
            self.assertFalse((cases / "cases-ub.md").exists())
            work = root / "work"
            work.mkdir()
            report = work / "diagnosis.md"
            diagnosis_contract = {
                "schema_version": "1.0", "run_id": "test-run", "stage": "diagnose",
                "owner_skill": "eval-skill", "status": "success", "attempt": 1,
                "started_at": "2026-11-10T00:00:00+00:00", "finished_at": "2026-11-10T00:00:01+00:00",
                "inputs": {"fingerprint": "a" * 64, "materials": [], "upstream": [], "parameters": {}},
                "outputs": [], "summary": "test", "evidence_gaps": [], "error": None,
                "next_action": "complete", "result": {},
            }
            report.write_text("```json\n" + json.dumps(diagnosis_contract, ensure_ascii=False, indent=2) + "\n```\n\n# Diagnosis\n\n## 问题摘要\n\nUB 链路故障\n\n## 关键日志\n\nERROR rtCqErrorCode[196610] DfxLinkType::UB\n\n## 根因分析\n\nUB 链路 CQE 错误\n\n## 修复建议\n\n检查 UB 交换\n", encoding="utf-8")
            confidence = work / "confidence.json"
            contract = dict(diagnosis_contract, stage="confidence",
                            result={"case_gate": "accept", "final_score": 90, "level": "HIGH"})
            confidence.write_text("```json\n" + json.dumps(contract, ensure_ascii=False, indent=2) + "\n```\n", encoding="utf-8")
            state_dir = root / "state"
            state_dir.mkdir()
            class Plan:
                state_dir = Path(root) / "state"
                library = index
                def params(self, sid):
                    return {"enabled": True, "cases_dir": str(cases)}
                def artifact(self, sid):
                    return confidence if sid == "confidence" else report
            artifact = {"result": {}, "outputs": []}
            result = run_pipeline.promote(Plan(), {"run_id": "test-run"}, artifact, work)
            ub = cases / "cases-ub.md"
            self.assertIn("CASE-UB-001", result)
            self.assertTrue(ub.is_file())
            self.assertIn("CASE-UB-001", ub.read_text(encoding="utf-8"))
            self.assertIn("CASE-UB-001", index.read_text(encoding="utf-8"))
            self.assertEqual(artifact["result"]["decision"], "committed")

    def test_publication_keeps_case_lookup_dependency_resolvable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cases = root / "cases"
            cases.mkdir()
            index = cases / "cases.md"
            category = cases / "cases-hang.md"
            index.write_text("# 常见问题案例库\n\n| 分类 | 案例文件 | 编号 |\n| --- | --- | --- |\n| 进程卡住 | [cases-hang.md](cases-hang.md) | CASE-HANG-001 |\n", encoding="utf-8")
            category.write_text("# 进程卡住 案例集\n\n## CASE-HANG-001：old\n", encoding="utf-8")
            work = root / "work"
            work.mkdir()
            state_dir = root / "state"
            artifacts = state_dir / "artifacts"
            artifacts.mkdir(parents=True)
            report = artifacts / "diagnosis.md"
            diagnosis_contract = {
                "schema_version": "1.0", "run_id": "test-run", "stage": "diagnose",
                "owner_skill": "eval-skill", "status": "success", "attempt": 1,
                "started_at": "2026-11-10T00:00:00+00:00", "finished_at": "2026-11-10T00:00:01+00:00",
                "inputs": {"fingerprint": "a" * 64, "materials": [], "upstream": [], "parameters": {}},
                "outputs": [], "summary": "test", "evidence_gaps": [], "error": None,
                "next_action": "complete", "result": {},
            }
            report.write_text("```json\n" + json.dumps(diagnosis_contract, ensure_ascii=False, indent=2) + "\n```\n\n# Diagnosis\n\n## 问题摘要\n\n进程卡住 timeout\n\n## 关键日志\n\nERROR timeout\n\n## 根因分析\n\nhang\n\n## 修复建议\n\nfix\n", encoding="utf-8")
            confidence = artifacts / "confidence.json"
            contract = dict(diagnosis_contract, stage="confidence",
                            result={"case_gate": "accept", "final_score": 90, "level": "HIGH"})
            confidence.write_text("```json\n" + json.dumps(contract, ensure_ascii=False, indent=2) + "\n```\n", encoding="utf-8")
            # Baseline must come from a real lookup_cases() run so the hash
            # domain matches: the combined index+categories digest, not a
            # single-file hash of cases.md.
            detector = load_detector()
            log = work / "log.txt"
            log.write_text("ERROR timeout\n", encoding="utf-8")
            scan = detector.scan_input(log)
            lookup = detector.lookup_cases(scan, "communication timeout", case_library=index)
            baseline = lookup["library_sha256"]
            lookup_contract = {
                "schema_version": "1.0", "run_id": "test-run", "stage": "case_lookup",
                "owner_skill": "orchestrator-skill", "status": "success", "attempt": 1,
                "started_at": "2026-11-10T00:00:00+00:00", "finished_at": "2026-11-10T00:00:01+00:00",
                "inputs": {"fingerprint": "a" * 64, "materials": [], "upstream": [], "parameters": {},
                           "dependencies": {"revision": "rev-1",
                                            "case_library": {"path": str(index), "sha256": baseline}}},
                "outputs": [], "summary": "test", "evidence_gaps": [], "error": None,
                "next_action": "complete", "result": {},
            }
            (artifacts / "case_lookup.md").write_text("```json\n" + json.dumps(lookup_contract, ensure_ascii=False, indent=2) + "\n```\n", encoding="utf-8")
            state = {"run_id": "test-run", "stages": {"case_lookup": {"revision": "rev-1"}}}
            class Plan:
                state_dir = Path(root) / "state"
                library = index
                def params(self, sid):
                    return {"enabled": True, "cases_dir": str(cases)}
                def artifact(self, sid):
                    if sid == "confidence":
                        return confidence
                    if sid == "case_lookup":
                        return artifacts / "case_lookup.md"
                    return report
            artifact = {"result": {}, "outputs": []}
            run_pipeline.promote(Plan(), state, artifact, work)
            self.assertEqual(artifact["result"]["decision"], "committed")
            # The run's own publication must not invalidate its earlier lookup:
            # lookup_library_hash resolves the mutated library back to the baseline.
            self.assertNotEqual(run_pipeline.file_hash(index), baseline)
            self.assertEqual(run_pipeline.lookup_library_hash(Plan(), state), baseline)

    def test_legacy_publication_receipt_remains_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cases = root / "cases"
            cases.mkdir()
            index = cases / "cases.md"
            index.write_text("# Cases\n", encoding="utf-8")
            work = root / "work"
            work.mkdir()
            state = root / "state"
            state.mkdir()
            receipt_id = "a" * 64
            receipt_path = state / "mutations" / (receipt_id + ".json")
            receipt_path.parent.mkdir(parents=True)
            receipt_path.write_text(json.dumps({
                "mutation_id": receipt_id,
                "run_id": "legacy-run",
                "target": "cases.md",
                "before_sha256": None,
                "after_sha256": run_pipeline.file_hash(index),
                "case_id": "CASE-HANG-001",
                "status": "committed",
            }), encoding="utf-8")
            diagnosis = work / "diagnosis.md"
            confidence = work / "confidence.json"
            diagnosis.write_text("```json\n" + json.dumps({
                "schema_version": "1.0", "run_id": "legacy-run", "stage": "diagnose",
                "owner_skill": "eval-skill", "status": "success", "attempt": 1,
                "started_at": "2026-01-01T00:00:00+00:00", "finished_at": "2026-01-01T00:00:01+00:00",
                "inputs": {"fingerprint": "a" * 64, "materials": [], "upstream": [], "parameters": {}},
                "outputs": [], "summary": "test", "evidence_gaps": [], "error": None,
                "next_action": "complete", "result": {},
            }, ensure_ascii=False) + "\n```\n", encoding="utf-8")
            confidence.write_text("```json\n" + json.dumps({
                "schema_version": "1.0", "run_id": "legacy-run", "stage": "confidence",
                "owner_skill": "eval-skill", "status": "success", "attempt": 1,
                "started_at": "2026-01-01T00:00:00+00:00", "finished_at": "2026-01-01T00:00:01+00:00",
                "inputs": {"fingerprint": "a" * 64, "materials": [], "upstream": [], "parameters": {}},
                "outputs": [], "summary": "test", "evidence_gaps": [], "error": None,
                "next_action": "complete",
                "result": {"case_gate": "accept", "final_score": 90, "level": "HIGH"},
            }, ensure_ascii=False) + "\n```\n", encoding="utf-8")
            artifact = {"result": {}, "outputs": []}
            class Plan:
                state_dir = state
                library = index
                def params(self, sid):
                    return {"enabled": True, "cases_dir": str(cases)}
                def artifact(self, sid):
                    return confidence if sid == "confidence" else diagnosis
            with mock.patch.object(run_pipeline, "digest", return_value=receipt_id):
                run_pipeline.promote(Plan(), {"run_id": "legacy-run"}, artifact, work)
            self.assertEqual(artifact["result"]["decision"], "already_committed")

    def test_pending_promotion_creates_missing_pending_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cases = root / "cases"
            cases.mkdir()
            index = cases / "cases.md"
            index.write_text("# 常见问题案例库\n\n| 分类 | 案例文件 | 编号 |\n| --- | --- | --- |\n", encoding="utf-8")
            self.assertFalse((cases / "cases-pending.md").exists())
            work = root / "work"
            work.mkdir()
            report = work / "diagnosis.md"
            report.write_text("```json\n" + json.dumps({
                "schema_version": "1.0",
                "run_id": "pending-run",
                "stage": "diagnose",
                "owner_skill": "eval-skill",
                "status": "success",
                "attempt": 1,
                "started_at": "2026-11-10T00:00:00+00:00",
                "finished_at": "2026-11-10T00:00:01+00:00",
                "inputs": {"fingerprint": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "materials": [], "upstream": [], "parameters": {}},
                "outputs": [],
                "summary": "test",
                "evidence_gaps": [],
                "error": None,
                "next_action": "complete",
                "result": {},
            }, ensure_ascii=False, indent=2) + "\n```\n\n# Diagnosis\n\n## 问题摘要\n\n进程卡住 timeout\n\n## 关键日志\n\nERROR timeout\n\n## 根因分析\n\nhang\n\n## 修复建议\n\nfix\n", encoding="utf-8")
            confidence = work / "confidence.json"
            contract = {
                "schema_version": "1.0",
                "run_id": "pending-run",
                "stage": "confidence",
                "owner_skill": "eval-skill",
                "status": "success",
                "attempt": 1,
                "started_at": "2026-11-10T00:00:00+00:00",
                "finished_at": "2026-11-10T00:00:01+00:00",
                "inputs": {"fingerprint": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "materials": [], "upstream": [], "parameters": {}},
                "outputs": [],
                "summary": "test",
                "evidence_gaps": [],
                "error": None,
                "next_action": "complete",
                "result": {"case_gate": "pending", "final_score": 75, "level": "MEDIUM"},
            }
            confidence.write_text("```json\n" + json.dumps(contract, ensure_ascii=False, indent=2) + "\n```" + chr(10), encoding="utf-8")
            state_dir = root / "state"
            state_dir.mkdir()
            class Plan:
                state_dir = Path(root) / "state"
                library = index
                def params(self, sid):
                    return {"enabled": True, "cases_dir": str(cases)}
                def artifact(self, sid):
                    return confidence if sid == "confidence" else report
            artifact = {"result": {}, "outputs": []}
            state = {"run_id": "pending-run"}
            report_body = report.read_text(encoding="utf-8")
            confidence_body = confidence.read_text(encoding="utf-8")
            result = run_pipeline.promote(Plan(), state, artifact, work)
            pending = cases / "cases-pending.md"
            self.assertIn("PCASE-001", result)
            self.assertTrue(pending.is_file())
            self.assertIn("PCASE-001", pending.read_text(encoding="utf-8"))
            receipt_path = state_dir / "mutations"
            receipts = list(receipt_path.glob("*.json"))
            self.assertEqual(len(receipts), 1)
            receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
            self.assertEqual(receipt["targets"]["cases-pending.md"]["before_sha256"], None)
            artifact2 = {"result": {}, "outputs": []}
            work2 = root / "work2"
            work2.mkdir()
            report2 = work2 / "diagnosis.md"
            confidence2 = work2 / "confidence.json"
            report2.write_text(report_body, encoding="utf-8")
            confidence2.write_text(confidence_body, encoding="utf-8")
            class Plan2:
                state_dir = Path(root) / "state"
                def params(self, sid):
                    return {"enabled": True, "cases_dir": str(cases)}
                def artifact(self, sid):
                    return confidence2 if sid == "confidence" else report2
            run_pipeline.promote(Plan2(), state, artifact2, work2)
            self.assertEqual(artifact2["result"]["decision"], "already_committed")


if __name__ == "__main__":
    unittest.main()
