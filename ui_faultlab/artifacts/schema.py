from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_manifest(manifest: dict) -> None:
    required = {
        "episode_id", "task_id", "task_version", "seed", "split", "condition",
        "model", "model_revision", "config_hash", "resolution", "start_timestamp", "status",
    }
    missing = required - set(manifest)
    if missing:
        raise ValueError(f"manifest missing: {sorted(missing)}")
    if manifest["status"] not in {"started", "completed", "failed", "interrupted"}:
        raise ValueError("invalid manifest status")

