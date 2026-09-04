from __future__ import annotations


LABELS = {"application_regression", "agent_or_harness", "ambiguous", "no_failure"}


def diagnose_differential(
    *,
    candidate_success: bool,
    reference_success: bool,
    candidate_final_sha256: str,
    reference_final_sha256: str,
) -> dict:
    """Attribute a failure using only public paired-run evidence."""
    if candidate_success:
        label = "no_failure"
        reason = "candidate completed the task"
    elif reference_success:
        label = "application_regression"
        reason = "identical executed actions succeed on the known-good reference"
    elif candidate_final_sha256 == reference_final_sha256:
        label = "agent_or_harness"
        reason = "candidate and reference fail with the same terminal observation"
    else:
        label = "ambiguous"
        reason = "both runs fail but their terminal observations diverge"
    return {"label": label, "reason": reason, "uses_hidden_condition": False}


def establish_gold(
    *,
    candidate_success: bool,
    reference_success: bool,
    configured_fault: str | None,
    fault_reached: bool,
) -> dict:
    """Establish gold from quarantined condition and causal-reach evidence."""
    if candidate_success:
        label = "no_failure"
    elif configured_fault is None or not fault_reached:
        label = "agent_or_harness"
    elif reference_success:
        label = "application_regression"
    else:
        label = "ambiguous"
    return {
        "label": label,
        "configured_fault": configured_fault,
        "fault_reached": fault_reached,
        "counterfactual_reference_success": reference_success,
    }
