from __future__ import annotations


def public_trajectory(steps: list[dict]) -> list[dict]:
    """Serialize only requested actions and visible transition summaries."""
    return [
        {
            "step_id": step["step_id"],
            "action": step["intended_action"],
            "before_screenshot": step["before_screenshot"],
            "after_screenshot": step["after_screenshot"],
            "before_sha256": step["before_sha256"],
            "after_sha256": step["after_sha256"],
            "result": step["result"],
        }
        for step in steps
    ]


def suspected_step(trajectory: list[dict]) -> int:
    for i, step in enumerate(trajectory):
        action = step["action"]
        reason = action.get("reason", "").lower()
        if step["result"]["status"] == "no_change" and action["type"] not in {"finish", "scroll"} and not any(k in reason for k in ("save", "confirm")):
            return i
    for i, step in enumerate(trajectory):
        if "focus" in step["action"].get("reason", "").lower():
            return i
    return 0


def diagnose_trajectory(instruction: str, trajectory: list[dict], task_failed: bool) -> dict:
    if not task_failed:
        return {"label": "ambiguous", "confidence": .5, "first_suspected_step": None, "evidence_frame_ids": [], "hypothesis": "No failure to attribute", "raw_output": "deterministic-trajectory-v1"}
    idx = suspected_step(trajectory)
    step = trajectory[idx]
    nonterminal_no_change = step["result"]["status"] == "no_change" and step["action"]["type"] not in {"finish", "scroll"}
    label = "agent_error" if nonterminal_no_change else "application_bug"
    return {
        "label": label,
        "confidence": .72 if nonterminal_no_change else .58,
        "first_suspected_step": idx,
        "evidence_frame_ids": [step["before_screenshot"], step["after_screenshot"]],
        "hypothesis": "Requested UI transition did not appear" if nonterminal_no_change else "Trajectory is coherent but final state is incorrect",
        "raw_output": "deterministic-trajectory-v1",
    }

