from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable

from app.faults import corrupt_draft
from app.state import clone_state, initial_state, public_state
from app.tasks import TASKS, success_predicate
from ui_faultlab.actions import Action
from ui_faultlab.rendering import render_calendar
from ui_faultlab.snapshots import restore_snapshot, take_snapshot


class BrowserEnvironment:
    """Deterministic browser-compatible state machine with screenshot-only observations."""

    def __init__(
        self,
        task_id: str,
        seed: int,
        artifact_dir: str | Path,
        application_fault: str | None = None,
        resolution=(960, 640),
        *,
        instruction: str | None = None,
        initial_state_override: dict | None = None,
        success_check: Callable[[dict], bool] | None = None,
    ):
        if task_id not in TASKS:
            raise KeyError(task_id)
        self.task_id = task_id
        self.seed = seed
        self.instruction = instruction or TASKS[task_id].instruction(seed)
        self.artifact_dir = Path(artifact_dir)
        self.application_fault = application_fault
        self.width, self.height = resolution
        self._initial_state = clone_state(initial_state_override) if initial_state_override is not None else initial_state(seed)
        self._success_check = success_check
        self.state = clone_state(self._initial_state)
        self.step_index = 0
        self.fault_trace: list[dict] = []

    def reset(self) -> dict:
        self.state = clone_state(self._initial_state)
        self.step_index = 0
        self.fault_trace = []
        return self.observe()

    def snapshot(self) -> dict:
        return take_snapshot(self.state)

    def restore(self, snapshot: dict) -> dict:
        self.state = restore_snapshot(snapshot)
        return self.observe(prefix="probe_restore")

    def _path(self, prefix: str = "step") -> Path:
        return self.artifact_dir / f"{prefix}_{self.step_index:03d}.png"

    def observe(self, prefix: str = "step") -> dict:
        path = self._path(prefix)
        render_calendar(self.state, self.instruction, path, self.width, self.height)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return {
            "task_id": self.task_id,
            "instruction": self.instruction,
            "screenshot_path": str(path),
            "screenshot_sha256": digest,
            "viewport": {"width": self.width, "height": self.height, "device_scale_factor": 1},
        }

    def serialize_agent_input(self, history: list[dict] | None = None) -> dict:
        obs = self.observe()
        obs["history"] = history or []
        return obs

    def apply(self, action: Action) -> tuple[dict, dict]:
        action.validate()
        before = take_snapshot(self.state)
        result = self._transition(action)
        changed = before != self.state
        self.step_index += 1
        obs = self.observe()
        result.update({"screen_changed": changed, "status": "screen_changed" if changed else "no_change"})
        return obs, result

    def _transition(self, action: Action) -> dict:
        self.state["toast"] = None
        if action.type in {"finish", "scroll", "enter"}:
            return {}
        if action.type == "back":
            self.state.update({"screen": "calendar", "draft": None, "focus": None, "confirm_delete": False})
            return {}
        if action.type == "type":
            if self.state["screen"] != "edit" or not self.state["focus"]:
                return {}
            self._set_focused_value(action.text)
            return {}
        if action.type == "input":
            if self.state["screen"] != "edit":
                return {}
            self._focus_edit_field(action.y)
            if self.state["focus"]:
                self._set_focused_value(action.text)
            return {}
        if self.state["confirm_delete"]:
            if action.y >= 0.55 and action.x >= 0.45:
                if self.application_fault != "confirmation_transition_bug":
                    selected = self.state["selected_event_id"]
                    self.state["events"] = [e for e in self.state["events"] if e["event_id"] != selected]
                else:
                    self.fault_trace.append({"fault": self.application_fault, "step_index": self.step_index})
                self.state.update({"screen": "calendar", "draft": None, "focus": None, "confirm_delete": False, "toast": "Deleted"})
            return {}
        if self.state["screen"] == "calendar":
            if action.y < 0.28 and action.x > 0.65:
                self.state.update({"screen": "edit", "selected_event_id": None, "draft": {"title": "", "date": "", "time": "", "attendees": []}, "focus": None})
                return {}
            cards = [(0.28, 0.44), (0.44, 0.62), (0.62, 0.80)]
            for idx, (lo, hi) in enumerate(cards):
                if lo <= action.y < hi and idx < len(self.state["events"]):
                    event = clone_state(self.state["events"][idx])
                    self.state.update({"screen": "edit", "selected_event_id": event["event_id"], "draft": event, "focus": None})
                    return {}
            return {}
        if self.state["screen"] == "edit":
            if 0.29 <= action.y < 0.43:
                self.state["focus"] = "title"
            elif 0.43 <= action.y < 0.56:
                self.state["focus"] = "date"
            elif 0.56 <= action.y < 0.69:
                self.state["focus"] = "time"
            elif 0.69 <= action.y < 0.82:
                self.state["focus"] = "attendees"
            elif action.y >= 0.82 and action.x > 0.52:
                self._save()
            elif action.y >= 0.82 and action.x < 0.48 and self.state["selected_event_id"]:
                self.state["confirm_delete"] = True
            return {}
        return {}

    def _focus_edit_field(self, y: float) -> None:
        if 0.29 <= y < 0.43:
            self.state["focus"] = "title"
        elif 0.43 <= y < 0.56:
            self.state["focus"] = "date"
        elif 0.56 <= y < 0.69:
            self.state["focus"] = "time"
        elif 0.69 <= y < 0.82:
            self.state["focus"] = "attendees"

    def _set_focused_value(self, text: str) -> None:
        key = self.state["focus"]
        if key == "attendees":
            self.state["draft"][key] = [v.strip() for v in text.split(",") if v.strip()]
        else:
            self.state["draft"][key] = text

    def _save(self) -> None:
        if self.application_fault == "save_noop":
            self.fault_trace.append({"fault": self.application_fault, "step_index": self.step_index})
            self.state.update({"screen": "calendar", "draft": None, "focus": None, "selected_event_id": None, "toast": "Saved"})
            return
        draft = clone_state(self.state["draft"])
        if self.application_fault == "value_corruption":
            self.fault_trace.append({"fault": self.application_fault, "step_index": self.step_index})
            if self.task_id == "reschedule_event":
                draft["time"] = "09:99"
            elif self.task_id == "add_attendee":
                draft["attendees"] = ["corrupted@example.invalid"]
            else:
                draft = corrupt_draft(draft)
        selected = self.state["selected_event_id"]
        if selected:
            self.state["events"] = [draft if e["event_id"] == selected else e for e in self.state["events"]]
        else:
            draft["event_id"] = f"evt-new-{self.state['next_id']}"
            self.state["next_id"] += 1
            self.state["events"].append(draft)
        self.state.update({"screen": "calendar", "draft": None, "focus": None, "selected_event_id": None, "toast": "Saved"})

    def succeeded(self) -> bool:
        if self._success_check is not None:
            return self._success_check(self.state)
        return success_predicate(self.task_id, self.seed, self.state)

    def privileged_evaluation_state(self) -> dict:
        return clone_state(self.state)

    def public_web_state(self) -> dict:
        return public_state(self.state)
