from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.state import initial_state


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    version: str
    instruction: Callable[[int], str]
    max_steps: int
    high_risk_actions: tuple[str, ...]


TASKS: dict[str, TaskSpec] = {
    "create_event": TaskSpec(
        "create_event", "1.0", lambda seed: f"Create 'Research Sync {seed}' on 2026-09-{20 + seed:02d} at 14:30",
        8, ("save_new_event",),
    ),
    "add_attendee": TaskSpec(
        "add_attendee", "1.0", lambda seed: f"Add user{seed}@example.com to Design Review and save",
        6, ("save_attendee",),
    ),
    "reschedule_event": TaskSpec(
        "reschedule_event", "1.0", lambda seed: f"Move Design Review to {15 + seed:02d}:00 and save",
        6, ("save_reschedule",),
    ),
    "delete_event": TaskSpec(
        "delete_event", "1.0", lambda seed: "Delete Deprecated Sync and confirm",
        6, ("confirm_delete",),
    ),
}


def task_payload(task_id: str, seed: int) -> dict:
    spec = TASKS[task_id]
    return {
        "task_id": spec.task_id,
        "task_version": spec.version,
        "instruction": spec.instruction(seed),
        "initial_state": initial_state(seed),
        "max_steps": spec.max_steps,
        "high_risk_actions": list(spec.high_risk_actions),
    }


def success_predicate(task_id: str, seed: int, state: dict) -> bool:
    events = state["events"]
    if task_id == "create_event":
        expected = {
            "title": f"Research Sync {seed}",
            "date": f"2026-09-{20 + seed:02d}",
            "time": "14:30",
        }
        matches = [e for e in events if all(e[k] == v for k, v in expected.items())]
        return len(events) == 4 and len(matches) == 1 and matches[0]["event_id"].startswith("evt-new-")
    if task_id == "add_attendee":
        design = next((e for e in events if e["event_id"] == "evt-design"), None)
        return bool(design and f"user{seed}@example.com" in design["attendees"])
    if task_id == "reschedule_event":
        design = next((e for e in events if e["event_id"] == "evt-design"), None)
        return bool(design and design["time"] == f"{15 + seed:02d}:00")
    if task_id == "delete_event":
        return all(e["event_id"] != "evt-sync" for e in events)
    raise KeyError(task_id)

