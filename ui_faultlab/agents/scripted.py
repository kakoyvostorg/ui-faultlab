from __future__ import annotations

from ui_faultlab.actions import Action


class ScriptedOracleAgent:
    """Privileged reference policy used only to validate environment execution."""

    name = "scripted_oracle"
    revision = "builtin-v1"

    def actions(self, task_id: str, seed: int) -> list[Action]:
        if task_id == "create_event":
            return [
                Action("tap", .82, .15, reason="open new event"),
                Action("tap", .40, .35, reason="focus title"),
                Action("type", text=f"Research Sync {seed}", reason="enter title"),
                Action("tap", .40, .49, reason="focus date"),
                Action("type", text=f"2026-09-{20 + seed:02d}", reason="enter date"),
                Action("tap", .40, .62, reason="focus time"),
                Action("type", text="14:30", reason="enter time"),
                Action("tap", .72, .88, reason="save event"),
                Action("finish", reason="task complete"),
            ]
        if task_id == "add_attendee":
            return [
                Action("tap", .30, .34, reason="open Design Review"),
                Action("tap", .40, .75, reason="focus attendees"),
                Action("type", text=f"Mira,user{seed}@example.com", reason="enter attendees"),
                Action("tap", .72, .88, reason="save attendee"),
                Action("finish", reason="task complete"),
            ]
        if task_id == "reschedule_event":
            return [
                Action("tap", .30, .34, reason="open Design Review"),
                Action("tap", .40, .62, reason="focus time"),
                Action("type", text=f"{15 + seed:02d}:00", reason="enter time"),
                Action("tap", .72, .88, reason="save reschedule"),
                Action("finish", reason="task complete"),
            ]
        if task_id == "delete_event":
            return [
                Action("tap", .30, .52, reason="open Deprecated Sync"),
                Action("tap", .25, .88, reason="delete event"),
                Action("tap", .65, .65, reason="confirm delete"),
                Action("finish", reason="task complete"),
            ]
        raise KeyError(task_id)

