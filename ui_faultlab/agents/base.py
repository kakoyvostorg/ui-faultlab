from __future__ import annotations

from typing import Protocol

from ui_faultlab.actions import Action


class Agent(Protocol):
    name: str
    revision: str

    def actions(self, task_id: str, seed: int) -> list[Action]: ...

