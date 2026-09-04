#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tarfile
from collections import Counter
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui_faultlab.instrumentation import atomic_write_json


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate(summary_path: Path, archive_path: Path, expected_hash: str, expected_cases: int, max_calls: int) -> dict:
    summary = json.loads(summary_path.read_text())
    if summary.get("status") != "completed":
        raise ValueError("summary is not completed")
    if summary.get("config_hash") != expected_hash:
        raise ValueError("summary config hash differs from preregistration")
    rows = summary.get("cases", [])
    if len(rows) != expected_cases or summary.get("overall", {}).get("cases") != expected_cases:
        raise ValueError("unexpected case count")
    case_ids = [row["case_id"] for row in rows]
    if len(set(case_ids)) != expected_cases:
        raise ValueError("duplicate case IDs")
    calls = sum(row["candidate"]["vlm_calls"] for row in rows)
    if calls != summary["overall"]["vlm_calls"] or calls > max_calls:
        raise ValueError("invalid inference-call count")
    if any(row["reference"]["vlm_calls"] != 0 for row in rows):
        raise ValueError("reference replay unexpectedly used the VLM")

    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        names = {member.name for member in members}
        for member in members:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"unsafe archive path: {member.name}")
            if member.issym() or member.islnk() or member.isdev():
                raise ValueError(f"unsafe archive member type: {member.name}")
        for case_id in case_ids:
            required = {
                f"paired_same_task_run/cases/{case_id}/manifest.json",
                f"paired_same_task_run/cases/{case_id}/evaluation.json",
                f"paired_same_task_run/cases/{case_id}/diagnosis.json",
                f"paired_same_task_run/cases/{case_id}/hidden/gold.json",
                f"paired_same_task_run/cases/{case_id}/candidate/steps.jsonl",
                f"paired_same_task_run/cases/{case_id}/reference/steps.jsonl",
            }
            missing = required - names
            if missing:
                raise ValueError(f"missing archive members for {case_id}: {sorted(missing)}")

    return {
        "status": "validated",
        "config_hash": expected_hash,
        "case_count": expected_cases,
        "candidate_successes": sum(row["candidate"]["task_success"] for row in rows),
        "failure_count": sum(row["gold_label"] != "no_failure" for row in rows),
        "vlm_calls": calls,
        "gold_labels": dict(sorted(Counter(row["gold_label"] for row in rows).items())),
        "predictions": dict(sorted(Counter(row["prediction"] for row in rows).items())),
        "summary_sha256": sha256(summary_path),
        "archive_sha256": sha256(archive_path),
        "archive_members": len(members),
        "archive_safe": True,
        "reference_vlm_calls": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate paired ShowUI cloud outputs")
    parser.add_argument("--summary", required=True)
    parser.add_argument("--archive", required=True)
    parser.add_argument("--expected-config-hash", required=True)
    parser.add_argument("--expected-cases", type=int, default=24)
    parser.add_argument("--max-calls", type=int, default=160)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = validate(
        Path(args.summary), Path(args.archive), args.expected_config_hash,
        args.expected_cases, args.max_calls,
    )
    atomic_write_json(args.output, result)
    print(json.dumps({key: result[key] for key in ("status", "case_count", "vlm_calls", "candidate_successes", "failure_count")}))


if __name__ == "__main__":
    main()
