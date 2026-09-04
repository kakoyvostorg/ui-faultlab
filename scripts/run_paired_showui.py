#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import tarfile
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.tasks import TASKS
from ui_faultlab.actions import Action
from ui_faultlab.agents.showui import MODEL_ID, MODEL_REVISION, ShowUIAgent, ShowUIOutputError, parse_showui_action
from ui_faultlab.diagnosis.differential import diagnose_differential, establish_gold
from ui_faultlab.environment import BrowserEnvironment
from ui_faultlab.instrumentation import append_jsonl, atomic_write_json, canonical_hash
from ui_faultlab.paired import PairedCase, validate_case_balance
from ui_faultlab.runner import load_config


def _environment(case: PairedCase, root: Path, config: dict, fault: str | None) -> BrowserEnvironment:
    return BrowserEnvironment(
        case.task_id,
        case.seed,
        root,
        application_fault=fault,
        resolution=tuple(config["resolution"]),
        instruction=case.instruction,
        initial_state_override=case.initial_state(),
        success_check=case.succeeded,
    )


def _run_candidate(agent, case: PairedCase, root: Path, config: dict) -> tuple[dict, list[dict], BrowserEnvironment]:
    env = _environment(case, root, config, case.candidate_fault)
    before = env.reset()
    history: list[str] = []
    steps: list[dict] = []
    no_change_streak = 0
    stop_reason = "max_steps"

    for index in range(TASKS[case.task_id].max_steps):
        raw, latency_ms = agent.raw_action(before["screenshot_path"], case.instruction, history)
        step = {
            "index": index,
            "before_screenshot": before["screenshot_path"],
            "before_sha256": before["screenshot_sha256"],
            "raw_output": raw,
            "parsed_action": None,
            "parse_error": None,
            "latency_ms": latency_ms,
            "after_screenshot": None,
            "after_sha256": None,
            "screen_changed": False,
        }
        try:
            action = parse_showui_action(raw)
            step["parsed_action"] = action.to_dict()
        except ShowUIOutputError as error:
            step["parse_error"] = str(error)
            steps.append(step)
            append_jsonl(root / "steps.jsonl", step)
            stop_reason = "parse_error"
            break
        after, transition = env.apply(action)
        step.update({
            "after_screenshot": after["screenshot_path"],
            "after_sha256": after["screenshot_sha256"],
            "screen_changed": transition["screen_changed"],
            "transition_status": transition["status"],
        })
        steps.append(step)
        append_jsonl(root / "steps.jsonl", step)
        history.append(raw)
        no_change_streak = 0 if transition["screen_changed"] else no_change_streak + 1
        before = after
        if env.succeeded():
            stop_reason = "task_success"
            break
        if action.type == "finish":
            stop_reason = "agent_finish"
            break
        if no_change_streak >= int(config["max_consecutive_no_change"]):
            stop_reason = "no_change_loop"
            break

    return ({
        "task_success": env.succeeded(),
        "stop_reason": stop_reason,
        "final_screenshot": before["screenshot_path"],
        "final_sha256": before["screenshot_sha256"],
        "vlm_calls": len(steps),
        "parse_failures": sum(step["parse_error"] is not None for step in steps),
        "latency_ms": sum(step["latency_ms"] for step in steps),
    }, steps, env)


def _replay_reference(case: PairedCase, root: Path, config: dict, candidate_steps: list[dict]) -> dict:
    env = _environment(case, root, config, None)
    before = env.reset()
    replayed = 0
    for index, source in enumerate(candidate_steps):
        payload = source.get("parsed_action")
        if payload is None:
            break
        action = Action.from_dict(payload)
        after, transition = env.apply(action)
        step = {
            "index": index,
            "replayed_action": payload,
            "source_raw_output": source["raw_output"],
            "before_screenshot": before["screenshot_path"],
            "before_sha256": before["screenshot_sha256"],
            "after_screenshot": after["screenshot_path"],
            "after_sha256": after["screenshot_sha256"],
            "screen_changed": transition["screen_changed"],
        }
        append_jsonl(root / "steps.jsonl", step)
        before = after
        replayed += 1
    return {
        "task_success": env.succeeded(),
        "actions_replayed": replayed,
        "vlm_calls": 0,
        "final_screenshot": before["screenshot_path"],
        "final_sha256": before["screenshot_sha256"],
    }


def run_case(*, agent, case: PairedCase, run_root: Path, config: dict, config_hash: str, force: bool = False) -> dict:
    case_root = run_root / "cases" / case.case_id
    evaluation_path = case_root / "evaluation.json"
    if evaluation_path.exists() and not force:
        return json.loads(evaluation_path.read_text())

    atomic_write_json(case_root / "manifest.json", {
        **case.public_manifest(),
        "config_hash": config_hash,
        "model": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "condition_blinded": True,
        "status": "started",
    })
    candidate, steps, candidate_env = _run_candidate(agent, case, case_root / "candidate", config)
    reference = _replay_reference(case, case_root / "reference", config, steps)
    prediction = diagnose_differential(
        candidate_success=candidate["task_success"],
        reference_success=reference["task_success"],
        candidate_final_sha256=candidate["final_sha256"],
        reference_final_sha256=reference["final_sha256"],
    )
    gold = establish_gold(
        candidate_success=candidate["task_success"],
        reference_success=reference["task_success"],
        configured_fault=case.candidate_fault,
        fault_reached=bool(candidate_env.fault_trace),
    )
    atomic_write_json(case_root / "diagnosis.json", prediction)
    atomic_write_json(case_root / "hidden" / "gold.json", gold)
    evaluation = {
        **case.public_manifest(),
        "candidate": candidate,
        "reference": reference,
        "prediction": prediction["label"],
        "gold_label": gold["label"],
        "correct": prediction["label"] == gold["label"],
    }
    atomic_write_json(evaluation_path, evaluation)
    atomic_write_json(case_root / "manifest.json", {
        **case.public_manifest(),
        "config_hash": config_hash,
        "model": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "condition_blinded": True,
        "status": "completed",
    })
    return evaluation


def build_summary(rows: list[dict], config_hash: str) -> dict:
    failures = [row for row in rows if row["gold_label"] != "no_failure"]
    by_task: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_task[row["task_id"]].append(row)

    def aggregate(items: list[dict]) -> dict:
        failed = [row for row in items if row["gold_label"] != "no_failure"]
        return {
            "cases": len(items),
            "candidate_successes": sum(row["candidate"]["task_success"] for row in items),
            "failures": len(failed),
            "correct_attributions": sum(row["correct"] for row in failed),
            "attribution_accuracy": sum(row["correct"] for row in failed) / len(failed) if failed else None,
            "gold_labels": dict(Counter(row["gold_label"] for row in items)),
            "predictions": dict(Counter(row["prediction"] for row in items)),
            "vlm_calls": sum(row["candidate"]["vlm_calls"] for row in items),
            "mean_candidate_latency_ms": mean(row["candidate"]["latency_ms"] for row in items) if items else 0.0,
        }

    return {
        "status": "completed",
        "config_hash": config_hash,
        "protocol": "showui-candidate-exact-action-reference-replay-v1",
        "model": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "overall": aggregate(rows),
        "failure_count": len(failures),
        "by_task": {key: aggregate(value) for key, value in sorted(by_task.items())},
        "cases": rows,
    }


def _archive(run_root: Path, archive_path: Path) -> None:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(run_root, arcname=run_root.name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run blinded paired same-task ShowUI differential replay")
    parser.add_argument("--config", default="configs/paired_same_task_v1.json")
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--archive", required=True)
    parser.add_argument("--expected-config-hash")
    args = parser.parse_args()
    config = load_config(args.config)
    config_hash = canonical_hash(config)
    if args.expected_config_hash and config_hash != args.expected_config_hash:
        raise RuntimeError("paired config hash does not match the frozen preregistration")
    cases = [PairedCase.from_dict(row) for row in config["cases"]]
    validate_case_balance(cases)
    run_root = Path(args.run_root)
    rows: list[dict] = []
    agent = ShowUIAgent(device="cuda")
    for case in cases:
        if sum(row["candidate"]["vlm_calls"] for row in rows) >= int(config["max_total_calls"]):
            raise RuntimeError("maximum total inference-call budget reached")
        result = run_case(agent=agent, case=case, run_root=run_root, config=config, config_hash=config_hash)
        rows.append(result)
        summary = build_summary(rows, config_hash)
        summary["status"] = "running"
        atomic_write_json(args.summary, summary)
        _archive(run_root, Path(args.archive))
        print(json.dumps({"case": case.case_id, "success": result["candidate"]["task_success"], "prediction": result["prediction"], "gold": result["gold_label"], "calls": result["candidate"]["vlm_calls"]}))
    summary = build_summary(rows, config_hash)
    atomic_write_json(args.summary, summary)
    _archive(run_root, Path(args.archive))
    print(json.dumps(summary["overall"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
