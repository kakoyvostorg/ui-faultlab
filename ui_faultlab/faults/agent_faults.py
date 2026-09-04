from __future__ import annotations

from ui_faultlab.actions import Action
from ui_faultlab.faults.base import InjectionResult


AGENT_FAULTS = ("coordinate_jitter", "wrong_candidate", "duplicate_action")


class AgentFaultInjector:
    """Intercept exactly one intended action; metadata stays outside public inputs."""

    def __init__(self, fault_type: str | None, task_id: str):
        if fault_type is not None and fault_type not in AGENT_FAULTS:
            raise ValueError(fault_type)
        self.fault_type = fault_type
        self.task_id = task_id
        self.used = False
        self.previous: Action | None = None

    def intercept(self, intended: Action, step_index: int) -> InjectionResult:
        executed = intended
        inject_now = False
        if not self.used and self.fault_type == "coordinate_jitter" and step_index == 0:
            executed = Action("tap", .03, .96, reason="executed coordinate")
            inject_now = True
        elif not self.used and self.fault_type == "wrong_candidate":
            if self.task_id == "delete_event" and step_index == 0:
                executed = Action("tap", .30, .34, reason="executed candidate")
                inject_now = True
            elif self.task_id != "delete_event" and step_index == 1:
                replacement_y = {"create_event": .49, "add_attendee": .62, "reschedule_event": .49}[self.task_id]
                executed = Action("tap", .40, replacement_y, reason="executed candidate")
                inject_now = True
        elif not self.used and self.fault_type == "duplicate_action" and step_index == 2 and self.previous:
            executed = self.previous
            inject_now = True
        if inject_now:
            self.used = True
        self.previous = executed
        return InjectionResult(intended, executed, inject_now)


def select_agent_fault(task_id: str, seed: int) -> str:
    order = ["create_event", "add_attendee", "reschedule_event", "delete_event"]
    return AGENT_FAULTS[(order.index(task_id) + seed) % len(AGENT_FAULTS)]


def select_application_fault(task_id: str) -> str:
    return {
        "create_event": "save_noop",
        "add_attendee": "value_corruption",
        "reschedule_event": "value_corruption",
        "delete_event": "confirmation_transition_bug",
    }[task_id]

