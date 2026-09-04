#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui_faultlab.runner import load_config, run_episode


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/local_smoke.yaml")
    parser.add_argument("--agent", default="scripted")
    parser.add_argument("--task", default="create_event")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--condition", choices=["clean", "agent_fault", "application_fault"], default="clean")
    parser.add_argument("--artifacts", default="artifacts")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.agent != "scripted":
        raise SystemExit("Only the verified scripted actor is enabled in the local runner; see VLM_BASELINE.md")
    result = run_episode(config=load_config(args.config), artifacts_root=Path(args.artifacts), split="dev", task_id=args.task, seed=args.seed, condition=args.condition, force=args.force)
    print(f"{result['episode_id']} success={result['task_success']} condition={result['condition']}")


if __name__ == "__main__":
    main()
