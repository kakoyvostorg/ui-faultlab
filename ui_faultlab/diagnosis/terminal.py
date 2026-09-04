from __future__ import annotations


def diagnose_terminal(instruction: str, final_screenshot_path: str, task_failed: bool) -> dict:
    """Weak terminal-only baseline: no history, no hidden state, no labels."""
    if not task_failed:
        return {"label": "ambiguous", "confidence": 0.5, "evidence": [final_screenshot_path], "raw_output": "deterministic-terminal-v1"}
    return {"label": "application_bug", "confidence": 0.55, "evidence": [final_screenshot_path], "raw_output": "deterministic-terminal-v1"}

