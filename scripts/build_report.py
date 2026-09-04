#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui_faultlab.reporting import build_report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", default="artifacts")
    parser.add_argument("--output", default="report/REPORT.md")
    args = parser.parse_args()
    metrics = build_report(args.artifacts, args.output)
    print(f"Report built from {metrics['episode_count']} episodes: {args.output}")


if __name__ == "__main__":
    main()

