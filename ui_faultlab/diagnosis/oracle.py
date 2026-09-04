from __future__ import annotations


def diagnose_oracle(gold_label: str) -> dict:
    return {"label": gold_label, "confidence": 1.0, "evidence": ["privileged fault metadata"], "mode": "oracle_only"}

