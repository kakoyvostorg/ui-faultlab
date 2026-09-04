from __future__ import annotations

from dataclasses import dataclass

from app.state import clone_state, initial_state


@dataclass(frozen=True)
class PairedCase:
    case_id: str
    task_id: str
    split: str
    seed: int
    instruction: str
    target_event_id: str | None
    expected: dict
    candidate_fault: str | None

    @classmethod
    def from_dict(cls, payload: dict) -> "PairedCase":
        return cls(
            case_id=payload["case_id"],
            task_id=payload["task_id"],
            split=payload["split"],
            seed=int(payload["seed"]),
            instruction=payload["instruction"],
            target_event_id=payload.get("target_event_id"),
            expected=clone_state(payload["expected"]),
            candidate_fault=payload.get("candidate_fault"),
        )

    def initial_state(self) -> dict:
        return initial_state(self.seed)

    def succeeded(self, state: dict) -> bool:
        events = state["events"]
        if self.task_id == "create_event":
            matches = [event for event in events if all(event.get(k) == v for k, v in self.expected.items())]
            return len(events) == 4 and len(matches) == 1 and matches[0]["event_id"].startswith("evt-new-")
        event = next((item for item in events if item["event_id"] == self.target_event_id), None)
        if self.task_id == "add_attendee":
            return bool(event and self.expected["attendee"] in event["attendees"])
        if self.task_id == "reschedule_event":
            return bool(event and event["time"] == self.expected["time"])
        if self.task_id == "delete_event":
            return event is None
        raise KeyError(self.task_id)

    def public_manifest(self) -> dict:
        return {
            "case_id": self.case_id,
            "task_id": self.task_id,
            "split": self.split,
            "seed": self.seed,
            "instruction": self.instruction,
        }


def validate_case_balance(cases: list[PairedCase]) -> None:
    by_task: dict[str, list[PairedCase]] = {}
    for case in cases:
        by_task.setdefault(case.task_id, []).append(case)
    if not by_task:
        raise ValueError("paired case manifest is empty")
    for task_id, rows in by_task.items():
        clean = sum(row.candidate_fault is None for row in rows)
        faulted = len(rows) - clean
        if clean != faulted:
            raise ValueError(f"unbalanced candidate conditions for {task_id}: {clean} clean, {faulted} faulted")
        if len({row.case_id for row in rows}) != len(rows):
            raise ValueError(f"duplicate case id in {task_id}")
