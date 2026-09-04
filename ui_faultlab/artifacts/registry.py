from __future__ import annotations

import json
from pathlib import Path

from ui_faultlab.instrumentation import atomic_write_json


class ArtifactRegistry:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.data = json.loads(self.path.read_text()) if self.path.exists() else {"episodes": {}}

    def should_run(self, episode_id: str, config_hash: str) -> bool:
        record = self.data["episodes"].get(episode_id)
        return not (record and record.get("status") == "completed" and record.get("config_hash") == config_hash)

    def update(self, episode_id: str, record: dict) -> None:
        self.data["episodes"][episode_id] = record
        atomic_write_json(self.path, self.data)

