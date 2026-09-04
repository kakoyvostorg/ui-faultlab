from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, asdict, field


@dataclass
class Event:
    event_id: str
    title: str
    date: str
    time: str
    attendees: list[str] = field(default_factory=list)


def initial_state(seed: int) -> dict:
    """Return deterministic state with stable ordering and seed-specific values."""
    day = 10 + seed
    events = [
        Event("evt-design", "Design Review", f"2026-09-{day:02d}", "11:00", ["Mira"]),
        Event("evt-sync", "Deprecated Sync", f"2026-09-{day + 1:02d}", "16:00", ["Oleg"]),
        Event("evt-planning", "Planning", f"2026-09-{day + 2:02d}", "10:00", []),
    ]
    return {
        "seed": seed,
        "events": [asdict(event) for event in events],
        "next_id": 100 + seed,
        "screen": "calendar",
        "selected_event_id": None,
        "focus": None,
        "draft": None,
        "toast": None,
        "confirm_delete": False,
    }


def clone_state(state: dict) -> dict:
    return deepcopy(state)


def public_state(state: dict) -> dict:
    """State used by the web client. Never includes fault or evaluator metadata."""
    return deepcopy(state)

