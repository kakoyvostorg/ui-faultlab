from __future__ import annotations


def recovery_metrics(evaluations: list[dict]) -> dict:
    failed = [e for e in evaluations if not e["task_success"]]
    corrected = [e for e in failed if e["predictions"]["active"]["label"] == e["gold_label"]]
    probes = sum(e["predictions"]["active"].get("probes_used", 0) for e in evaluations)
    return {
        "failed_episodes": len(failed),
        "diagnostic_recovery_success_count": [len(corrected), len(failed)],
        "diagnostic_recovery_success_rate": len(corrected) / len(failed) if failed else 0.0,
        "active_probes": probes,
        "active_probes_per_episode": probes / len(evaluations) if evaluations else 0.0,
    }

