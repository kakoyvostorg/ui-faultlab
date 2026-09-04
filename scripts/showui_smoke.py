#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.tasks import TASKS
from ui_faultlab.agents.showui import (
    MODEL_ID, MODEL_REVISION, ShowUIAgent, ShowUIOutputError,
    dependency_preflight, parse_showui_action,
)
from ui_faultlab.artifacts.schema import utc_now
from ui_faultlab.environment import BrowserEnvironment
from ui_faultlab.instrumentation import atomic_write_json


SMOKE_CASES = (("create_event", 1), ("delete_event", 1))


def build_cases(root: Path) -> list[dict]:
    cases = []
    for task_id, seed in SMOKE_CASES:
        environment = BrowserEnvironment(task_id, seed, root / f"{task_id}_{seed}")
        observation = environment.observe()
        cases.append({
            "task_id": task_id,
            "seed": seed,
            "instruction": TASKS[task_id].instruction(seed),
            "screenshot_path": observation["screenshot_path"],
            "screenshot_sha256": observation["screenshot_sha256"],
        })
    return cases


def run_two_inference_smoke(agent: ShowUIAgent, cases: list[dict]) -> list[dict]:
    if len(cases) != 2:
        raise ValueError("the smoke gate requires exactly two cases")
    outputs = []
    for case in cases:
        raw, latency_ms = agent.raw_action(case["screenshot_path"], case["instruction"], [])
        record = {**case, "raw_output": raw, "latency_ms": latency_ms, "parsed_action": None, "parse_error": None}
        try:
            record["parsed_action"] = parse_showui_action(raw).to_dict()
        except ShowUIOutputError as error:
            record["parse_error"] = str(error)
        outputs.append(record)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Exactly-two-inference ShowUI runtime gate")
    parser.add_argument("--output", default="artifacts/model_smoke_result.json")
    parser.add_argument("--input-dir", default="work/model_smoke_inputs")
    parser.add_argument("--allow-download", action="store_true", help="Allow the pinned 4.43 GB checkpoint download")
    args = parser.parse_args()
    preflight = dependency_preflight()
    result = {
        "timestamp": utc_now(), "candidate": MODEL_ID,
        "revision": MODEL_REVISION,
        "platform": platform.platform(), "machine": platform.machine(),
        "preflight": preflight, "allow_download": args.allow_download,
        "inference_calls": 0, "model_loaded": False, "status": "blocked",
        "reason": None, "results": [],
    }
    if not preflight["ready"]:
        result["reason"] = "missing ShowUI runtime dependencies"
    elif not args.allow_download:
        result["reason"] = "checkpoint download intentionally disabled pending a suitable GPU/runtime"
    else:
        try:
            cases = build_cases(Path(args.input_dir))
            agent = ShowUIAgent(device="cuda")
            result["model_loaded"] = True
            result["results"] = run_two_inference_smoke(agent, cases)
            result["inference_calls"] = len(result["results"])
            result["status"] = "completed"
            result["reason"] = None
        except Exception as error:
            result["status"] = "failed"
            result["reason"] = f"{type(error).__name__}: {error}"
    atomic_write_json(args.output, result)
    print(json.dumps(result, indent=2))
    if result["status"] != "completed":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
