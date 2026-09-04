#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui_faultlab.artifacts.schema import utc_now
from ui_faultlab.instrumentation import append_jsonl, atomic_write_json, canonical_hash
from ui_faultlab.runner import load_config, run_episode


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/experiment.yaml")
    parser.add_argument("--split", choices=["dev", "validation", "test"], required=True)
    parser.add_argument("--artifacts", default="artifacts")
    parser.add_argument("--evaluate-test", action="store_true")
    parser.add_argument("--allow-test", action="store_true")
    parser.add_argument("--test-reason", default="post-freeze final evaluation")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    root = Path(args.artifacts)
    config_hash = canonical_hash(config)
    if args.split == "test":
        if not (args.evaluate_test and args.allow_test):
            raise SystemExit("Test is closed: both --evaluate-test and --allow-test are required")
        freeze_path = root / "freeze.json"
        if not freeze_path.exists():
            raise SystemExit("Test is closed: artifacts/freeze.json must be created by the validation run")
        freeze = load_config(freeze_path)
        if freeze["config_hash"] != config_hash:
            raise SystemExit("Test is closed: config hash differs from the frozen experiment")
        append_jsonl(root / "test_access_log.jsonl", {"timestamp": utc_now(), "config_hash": config_hash, "reason": args.test_reason, "flags": ["evaluate-test", "allow-test"]})
    evaluations = []
    seeds = config["seeds_by_split"][args.split]
    for seed in seeds:
        for task in config["tasks"]:
            for condition in config["conditions"]:
                result = run_episode(config=config, artifacts_root=root, split=args.split, task_id=task, seed=seed, condition=condition, force=args.force)
                evaluations.append(result)
                print(f"{args.split} {task} seed={seed} {condition}: success={result['task_success']}")
    if args.split == "validation":
        frozen = {
            "timestamp": utc_now(), "config_hash": config_hash,
            "model_revision": config["agent"]["revision"], "prompts": "deterministic-v1",
            "coordinate_preprocessing": "normalized [0,1] to viewport pixels",
            "fault_taxonomy": {"agent": config["agent_faults"], "application": config["application_faults"]},
            "thresholds": {}, "max_probes": config["max_probes"], "parser": config["parser"],
            "primary_metric": config["primary_metric"], "report_schema": "report-v1",
        }
        atomic_write_json(root / "freeze.json", frozen)
        print(f"Experiment frozen: {config_hash}")
    print(f"Completed/resumed {len(evaluations)} episodes")


if __name__ == "__main__":
    main()
