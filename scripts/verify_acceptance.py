#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui_faultlab.instrumentation import atomic_write_json
from ui_faultlab.reporting import load_evaluations


def main() -> None:
    root = Path("artifacts")
    evaluations = load_evaluations(root)
    failures = [e for e in evaluations if not e["task_success"]]
    episode_dirs = [root / "episodes" / e["episode_id"] for e in evaluations]
    with (root / "cost_ledger.csv").open() as handle:
        spend = sum(float(row["actual_cost_rub"]) for row in csv.DictReader(handle))
    gallery_cases = (Path("report/failure_gallery/index.html").read_text().count("<article>"))
    checks = {
        "episode_count_at_least_36": len(evaluations) >= 36,
        "four_tasks": len({e["task_id"] for e in evaluations}) >= 4,
        "three_agent_faults": len({e["gold_fault_type"] for e in failures if e["gold_label"] == "agent_error"}) >= 3,
        "three_application_faults": len({e["gold_fault_type"] for e in failures if e["gold_label"] == "application_bug"}) >= 3,
        "all_clean_tasks_succeed": all(e["task_success"] for e in evaluations if e["condition"] == "clean"),
        "all_fault_fixtures_change_outcome": all(not e["task_success"] for e in evaluations if e["condition"] != "clean"),
        "three_diagnoses_for_same_failures": all(all((directory / f"diagnosis_{method}.json").exists() for method in ("terminal", "trajectory", "active")) for directory in episode_dirs if json.loads((directory / "evaluation.json").read_text())["task_success"] is False),
        "complete_machine_readable_bundles": all((directory / "manifest.json").exists() and (directory / "steps.jsonl").exists() and (directory / "evaluation.json").exists() for directory in episode_dirs),
        "failure_gallery_at_least_six": gallery_cases >= 6,
        "freeze_exists": (root / "freeze.json").exists(),
        "test_access_logged": (root / "test_access_log.jsonl").exists() and bool((root / "test_access_log.jsonl").read_text().strip()),
        "report_metrics_exist": (root / "tables" / "metrics.json").exists(),
        "spend_within_700_rub": spend <= 700,
    }
    model_gate = json.loads((root / "model_smoke_result.json").read_text())
    output = {
        "local_acceptance_checks": checks,
        "local_acceptance_passed": all(checks.values()),
        "open_vlm_gate": model_gate,
        "open_vlm_baseline_completed": model_gate["status"] == "completed" and model_gate["inference_calls"] >= 2,
        "actual_spend_rub": spend,
        "active_cloud_job_status": "not_queryable_no_datasphere_access; no job launched by this project",
    }
    atomic_write_json(root / "acceptance.json", output)
    print(json.dumps(output, indent=2))
    if not output["local_acceptance_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

