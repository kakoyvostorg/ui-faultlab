#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui_faultlab.reporting import build_failure_gallery, load_evaluations


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", default="artifacts")
    parser.add_argument("--output", default="report/failure_gallery")
    parser.add_argument("--count", type=int, default=6)
    args = parser.parse_args()
    result = build_failure_gallery(load_evaluations(args.artifacts), args.output, args.count)
    print(f"Gallery built with {result['count']} cases: {args.output}/index.html")


if __name__ == "__main__":
    main()

