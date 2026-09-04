#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import inspect
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.faults import APPLICATION_FAULTS
from app.tasks import TASKS
from ui_faultlab.agents.showui import MODEL_ID, MODEL_REVISION
from ui_faultlab.diagnosis.differential import diagnose_differential
from ui_faultlab.instrumentation import atomic_write_json, canonical_hash
from ui_faultlab.paired import PairedCase, validate_case_balance
from ui_faultlab.runner import load_config


def audit(config_path: Path) -> dict:
    config = load_config(config_path)
    cases = [PairedCase.from_dict(row) for row in config["cases"]]
    validate_case_balance(cases)
    ids = [case.case_id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("case ids must be globally unique")
    if set(case.task_id for case in cases) != set(TASKS):
        raise ValueError("paired manifest must cover every task family")
    if set(case.split for case in cases) != {"dev", "validation", "test"}:
        raise ValueError("paired manifest must cover dev, validation, and test")
    if any(case.candidate_fault not in {None, *APPLICATION_FAULTS} for case in cases):
        raise ValueError("unknown candidate fault")
    if config["model"] != MODEL_ID or config["model_revision"] != MODEL_REVISION:
        raise ValueError("model identity differs from pinned runtime")
    max_possible_calls = sum(TASKS[case.task_id].max_steps for case in cases)
    if int(config["max_total_calls"]) < max_possible_calls:
        raise ValueError("inference-call cap cannot complete the preregistered cases")
    public_keys = set().union(*(case.public_manifest() for case in cases))
    forbidden = {"candidate_fault", "expected", "target_event_id", "gold_label"}
    if public_keys & forbidden:
        raise ValueError(f"hidden fields leaked into public manifests: {sorted(public_keys & forbidden)}")
    diagnosis_parameters = set(inspect.signature(diagnose_differential).parameters)
    if diagnosis_parameters & forbidden:
        raise ValueError("blind diagnosis accepts hidden condition fields")

    task_counts = Counter(case.task_id for case in cases)
    split_counts = Counter(case.split for case in cases)
    condition_counts = Counter("clean" if case.candidate_fault is None else "faulted" for case in cases)
    task_split_condition = Counter(
        f"{case.task_id}/{case.split}/{'clean' if case.candidate_fault is None else 'faulted'}"
        for case in cases
    )
    if set(task_split_condition.values()) != {1}:
        raise ValueError("each task/split cell must contain exactly one clean and one faulted case")
    return {
        "status": "frozen",
        "protocol": config["protocol"],
        "config_path": str(config_path),
        "config_hash": canonical_hash(config),
        "config_file_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "model": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "case_count": len(cases),
        "task_counts": dict(sorted(task_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "condition_counts": dict(sorted(condition_counts.items())),
        "task_split_condition_counts": dict(sorted(task_split_condition.items())),
        "max_possible_calls": max_possible_calls,
        "max_total_calls": int(config["max_total_calls"]),
        "hard_runtime_cap_minutes": int(config["hard_runtime_cap_minutes"]),
        "label_isolation": {
            "public_manifest_hidden_fields_absent": True,
            "diagnosis_hidden_parameters_absent": True,
            "gold_output_quarantined": "cases/<case_id>/hidden/gold.json",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit and freeze the paired same-task protocol")
    parser.add_argument("--config", default="configs/paired_same_task_v1.json")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = audit(Path(args.config))
    atomic_write_json(args.output, result)
    print(result["config_hash"])


if __name__ == "__main__":
    main()
