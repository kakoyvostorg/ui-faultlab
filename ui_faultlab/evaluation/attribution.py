from __future__ import annotations

import math


LABELS = ("agent_error", "application_bug", "ambiguous")


def confusion_matrix(gold: list[str], predicted: list[str]) -> dict[str, dict[str, int]]:
    if len(gold) != len(predicted):
        raise ValueError("gold and predicted lengths differ")
    matrix = {g: {p: 0 for p in LABELS} for g in LABELS}
    for g, p in zip(gold, predicted, strict=True):
        if g not in LABELS or p not in LABELS:
            raise ValueError(f"unknown label: {g}/{p}")
        matrix[g][p] += 1
    return matrix


def safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total == 0:
        return (0.0, 0.0)
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def attribution_metrics(gold: list[str], predicted: list[str]) -> dict:
    matrix = confusion_matrix(gold, predicted)
    tp_bug = matrix["application_bug"]["application_bug"]
    pred_bug = sum(matrix[g]["application_bug"] for g in LABELS)
    gold_bug = sum(matrix["application_bug"].values())
    total = len(gold)
    correct = sum(matrix[label][label] for label in LABELS)
    per_class_f1 = []
    for label in LABELS:
        tp = matrix[label][label]
        precision = safe_div(tp, sum(matrix[g][label] for g in LABELS))
        recall = safe_div(tp, sum(matrix[label].values()))
        per_class_f1.append(safe_div(2 * precision * recall, precision + recall))
    false_bug = matrix["agent_error"]["application_bug"]
    agent_total = sum(matrix["agent_error"].values())
    ambiguous = sum(matrix[g]["ambiguous"] for g in LABELS)
    precision = safe_div(tp_bug, pred_bug)
    recall = safe_div(tp_bug, gold_bug)
    accuracy = safe_div(correct, total)
    return {
        "n": total,
        "confusion_matrix": matrix,
        "application_bug_precision": precision,
        "application_bug_precision_count": [tp_bug, pred_bug],
        "application_bug_precision_wilson95": wilson_interval(tp_bug, pred_bug),
        "application_bug_recall": recall,
        "application_bug_recall_count": [tp_bug, gold_bug],
        "application_bug_recall_wilson95": wilson_interval(tp_bug, gold_bug),
        "macro_f1": sum(per_class_f1) / len(per_class_f1),
        "accuracy": accuracy,
        "accuracy_count": [correct, total],
        "accuracy_wilson95": wilson_interval(correct, total),
        "false_bug_report_rate": safe_div(false_bug, agent_total),
        "false_bug_report_count": [false_bug, agent_total],
        "false_bug_report_wilson95": wilson_interval(false_bug, agent_total),
        "ambiguous_rate": safe_div(ambiguous, total),
        "ambiguous_count": [ambiguous, total],
    }

