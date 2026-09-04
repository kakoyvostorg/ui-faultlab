from __future__ import annotations

from collections.abc import Callable

from ui_faultlab.diagnosis.trajectory import suspected_step


def active_suspected_step(trajectory: list[dict]) -> int:
    if trajectory and trajectory[0]["result"]["status"] == "no_change":
        return 0
    for i, step in enumerate(trajectory):
        if step["action"]["type"] == "type" and step["result"]["status"] == "no_change":
            return i
    for i, step in enumerate(trajectory):
        if "focus" in step["action"].get("reason", "").lower():
            return i
    for i, step in enumerate(trajectory):
        if step["result"]["status"] == "no_change" and step["action"]["type"] not in {"finish", "scroll"}:
            return i
    return suspected_step(trajectory)


def diagnose_active(instruction: str, trajectory: list[dict], task_failed: bool, probe: Callable[[int], dict], max_probes: int = 1) -> dict:
    if max_probes < 1:
        return {"label": "ambiguous", "confidence": .4, "probes_used": 0, "evidence": [], "raw_output": "deterministic-active-v1"}
    if not task_failed:
        return {"label": "ambiguous", "confidence": .5, "probes_used": 0, "evidence": [], "raw_output": "deterministic-active-v1"}
    idx = active_suspected_step(trajectory)
    replay = probe(idx)
    observed_hash = trajectory[idx]["after_sha256"]
    label = "agent_error" if replay["after_sha256"] != observed_hash else "application_bug"
    return {
        "label": label,
        "confidence": .9 if label == "agent_error" else .82,
        "first_suspected_step": idx,
        "probes_used": 1,
        "evidence": [trajectory[idx]["after_screenshot"], replay["screenshot_path"]],
        "hypothesis": "Counterfactual intended action changed the visual transition" if label == "agent_error" else "Counterfactual replay reproduced the failed transition",
        "raw_output": "deterministic-active-v1",
    }
