from __future__ import annotations

import hashlib
import json
from copy import deepcopy


def take_snapshot(state: dict) -> dict:
    return deepcopy(state)


def restore_snapshot(snapshot: dict) -> dict:
    return deepcopy(snapshot)


def snapshot_hash(snapshot: dict) -> str:
    raw = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()

