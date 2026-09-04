#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tarfile
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.tasks import TASKS
from ui_faultlab.agents.showui import (
    MODEL_ID,
    MODEL_REVISION,
    ShowUIAgent,
    ShowUIOutputError,
    parse_showui_action,
)
from ui_faultlab.environment import BrowserEnvironment
from ui_faultlab.instrumentation import append_jsonl, atomic_write_json, canonical_hash
from ui_faultlab.runner import load_config


def episode_id(split: str, task_id: str, seed: int, config_hash: str) -> str:
    digest = canonical_hash({"split": split, "task": task_id, "seed": seed, "config": config_hash})[:12]
    return f"showui_{digest}"


def run_episode(*, agent, task_id: str, seed: int, split: str, run_root: Path, config: dict, config_hash: str) -> dict:
    identity = episode_id(split, task_id, seed, config_hash)
    episode_dir = run_root / "episodes" / identity
    env = BrowserEnvironment(task_id, seed, episode_dir, application_fault=None, resolution=tuple(config["resolution"]))
    before = env.reset()
    history: list[str] = []
    steps: list[dict] = []
    parse_failures = 0
    invalid_actions = 0
    no_change_streak = 0
    stop_reason = "max_steps"

    manifest = {
        "episode_id": identity,
        "task_id": task_id,
        "task_version": TASKS[task_id].version,
        "seed": seed,
        "split": split,
        "condition": "clean",
        "known_good_application": True,
        "model": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "config_hash": config_hash,
        "resolution": config["resolution"],
        "status": "started",
    }
    atomic_write_json(episode_dir / "manifest.json", manifest)

    for index in range(TASKS[task_id].max_steps):
        raw, latency_ms = agent.raw_action(before["screenshot_path"], env.instruction, history)
        step = {
            "episode_id": identity,
            "step_id": f"{identity}_s{index:03d}",
            "index": index,
            "instruction": env.instruction,
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
            parse_failures += 1
            invalid_actions += 1
            steps.append(step)
            append_jsonl(episode_dir / "steps.jsonl", step)
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
        append_jsonl(episode_dir / "steps.jsonl", step)
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

    task_success = env.succeeded()
    evaluation = {
        "episode_id": identity,
        "task_id": task_id,
        "seed": seed,
        "split": split,
        "condition": "clean",
        "known_good_application": True,
        "task_success": task_success,
        "gold_label": None if task_success else "agent_error",
        "stop_reason": stop_reason,
        "steps": len(steps),
        "vlm_calls": len(steps),
        "parse_failures": parse_failures,
        "invalid_actions": invalid_actions,
        "no_change_steps": sum(not step["screen_changed"] for step in steps),
        "loop_repetitions": sum(
            a.get("parsed_action") == b.get("parsed_action") and a.get("parsed_action") is not None
            for a, b in zip(steps, steps[1:])
        ),
        "latency_ms": {
            "total": sum(step["latency_ms"] for step in steps),
            "mean": mean(step["latency_ms"] for step in steps) if steps else 0.0,
        },
        "final_screenshot": before["screenshot_path"],
        "final_sha256": before["screenshot_sha256"],
    }
    atomic_write_json(episode_dir / "evaluation.json", evaluation)
    manifest.update({"status": "completed", "task_success": task_success, "stop_reason": stop_reason})
    atomic_write_json(episode_dir / "manifest.json", manifest)
    return evaluation


def build_summary(evaluations: list[dict], config: dict, config_hash: str) -> dict:
    by_task = defaultdict(list)
    by_split = defaultdict(list)
    for row in evaluations:
        by_task[row["task_id"]].append(row)
        by_split[row["split"]].append(row)

    def aggregate(rows: list[dict]) -> dict:
        successes = sum(row["task_success"] for row in rows)
        calls = sum(row["vlm_calls"] for row in rows)
        return {
            "episodes": len(rows),
            "successes": successes,
            "success_rate": successes / len(rows) if rows else 0.0,
            "vlm_calls": calls,
            "mean_steps": mean(row["steps"] for row in rows) if rows else 0.0,
            "parse_failures": sum(row["parse_failures"] for row in rows),
            "invalid_actions": sum(row["invalid_actions"] for row in rows),
            "no_change_steps": sum(row["no_change_steps"] for row in rows),
            "loop_repetitions": sum(row["loop_repetitions"] for row in rows),
            "mean_inference_latency_ms": (
                sum(row["latency_ms"]["total"] for row in rows) / calls if calls else 0.0
            ),
            "stop_reasons": dict(Counter(row["stop_reason"] for row in rows)),
        }

    return {
        "status": "completed",
        "config_hash": config_hash,
        "model": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "task_version": config["task_version"],
        "protocol": config["prompt"],
        "known_good_application": True,
        "overall": aggregate(evaluations),
        "by_task": {key: aggregate(value) for key, value in sorted(by_task.items())},
        "by_split": {key: aggregate(value) for key, value in sorted(by_split.items())},
        "episodes": evaluations,
    }


def write_archive(run_root: Path, archive_path: Path) -> None:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(run_root, arcname=run_root.name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the preregistered ShowUI clean closed-loop baseline")
    parser.add_argument("--config", default="configs/showui_full.yaml")
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--archive", required=True)
    args = parser.parse_args()

    config = load_config(args.config)
    config_hash = canonical_hash(config)
    run_root = Path(args.run_root)
    summary_path = Path(args.summary)
    archive_path = Path(args.archive)
    evaluations: list[dict] = []
    agent = ShowUIAgent(device="cuda")

    for split in ("dev", "validation", "test"):
        for seed in config["seeds_by_split"][split]:
            for task_id in config["tasks"]:
                calls_used = sum(row["vlm_calls"] for row in evaluations)
                if calls_used >= int(config["max_total_calls"]):
                    raise RuntimeError("maximum total inference-call budget reached")
                result = run_episode(
                    agent=agent,
                    task_id=task_id,
                    seed=seed,
                    split=split,
                    run_root=run_root,
                    config=config,
                    config_hash=config_hash,
                )
                evaluations.append(result)
                summary = build_summary(evaluations, config, config_hash)
                summary["status"] = "running"
                atomic_write_json(summary_path, summary)
                write_archive(run_root, archive_path)
                print(json.dumps({"episode": result["episode_id"], "task": task_id, "split": split, "success": result["task_success"], "calls": result["vlm_calls"], "stop": result["stop_reason"]}))

    summary = build_summary(evaluations, config, config_hash)
    atomic_write_json(summary_path, summary)
    write_archive(run_root, archive_path)
    print(json.dumps(summary["overall"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
