#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui_faultlab.agents.showui import MODEL_ID, MODEL_REVISION, dependency_preflight
from ui_faultlab.artifacts.schema import utc_now
from ui_faultlab.instrumentation import atomic_write_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Two-inference ShowUI gate; never launches paid compute")
    parser.add_argument("--candidate", choices=["showui", "qwen25vl"], default="showui")
    parser.add_argument("--output", default="artifacts/model_smoke_result.json")
    parser.add_argument("--allow-download", action="store_true", help="Allow the pinned 4.43 GB checkpoint download")
    args = parser.parse_args()
    selected = MODEL_ID if args.candidate == "showui" else "Qwen/Qwen2.5-VL-3B-Instruct"
    preflight = dependency_preflight()
    result = {
        "timestamp": utc_now(), "candidate": selected,
        "revision": MODEL_REVISION if args.candidate == "showui" else None,
        "platform": platform.platform(), "machine": platform.machine(),
        "preflight": preflight, "allow_download": args.allow_download,
        "inference_calls": 0, "model_loaded": False, "status": "blocked",
        "reason": None, "paid_compute_started": False, "estimated_cost_rub": 0.0,
    }
    if not preflight["ready"]:
        result["reason"] = "missing local torch/transformers/Pillow/qwen_vl_utils runtime"
    elif not args.allow_download:
        result["reason"] = "checkpoint download intentionally disabled pending a suitable GPU/runtime"
    else:
        result["reason"] = "runner is intentionally limited to preflight until screenshot pair and monitored GPU are provided"
    atomic_write_json(args.output, result)
    print(json.dumps(result, indent=2))
    raise SystemExit(2)


if __name__ == "__main__":
    main()

