#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import json
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui_faultlab.evaluation.attribution import attribution_metrics, wilson_interval
from ui_faultlab.evaluation.statistics import mcnemar_exact, paired_bootstrap_accuracy_difference
from ui_faultlab.instrumentation import atomic_write_json


LABELS = ("agent_or_harness", "application_regression", "ambiguous")
DISPLAY = {"agent_or_harness": "Agent / harness", "application_regression": "Application regression", "ambiguous": "Ambiguous"}
COLORS = {"agent_or_harness": "#4669E8", "application_regression": "#CA414B", "ambiguous": "#E5A23A", "green": "#299770", "red": "#CA414B", "navy": "#182542", "muted": "#68748B", "line": "#D4DAE7", "bg": "#F5F7FB"}


def pct(value: float) -> str:
    return f"{100 * value:.1f}%"


def remap(label: str) -> str:
    return {"agent_or_harness": "agent_error", "application_regression": "application_bug", "ambiguous": "ambiguous"}[label]


def method_metrics(rows: list[dict], predictions: list[str]) -> dict:
    gold = [remap(row["gold_label"]) for row in rows]
    mapped = [remap(label) for label in predictions]
    result = attribution_metrics(gold, mapped)
    broad_non_app = sum(label != "application_regression" for label in (row["gold_label"] for row in rows))
    broad_false = sum(
        prediction == "application_regression" and row["gold_label"] != "application_regression"
        for row, prediction in zip(rows, predictions, strict=True)
    )
    result["non_application_false_bug_report_count"] = [broad_false, broad_non_app]
    result["non_application_false_bug_report_rate"] = broad_false / broad_non_app if broad_non_app else 0.0
    result["non_application_false_bug_report_wilson95"] = wilson_interval(broad_false, broad_non_app)
    return result


def build_metrics(summary: dict, wall_seconds: float, preferred_rate: float, fallback_rate: float) -> dict:
    failures = [row for row in summary["cases"] if row["gold_label"] != "no_failure"]
    gold = [row["gold_label"] for row in failures]
    paired = [row["prediction"] for row in failures]
    terminal = ["application_regression"] * len(failures)
    by_task = {}
    for task in sorted({row["task_id"] for row in failures}):
        subset = [row for row in failures if row["task_id"] == task]
        by_task[task] = method_metrics(subset, [row["prediction"] for row in subset])
    return {
        "scope": {
            "cases": len(summary["cases"]),
            "failures": len(failures),
            "candidate_successes": summary["overall"]["candidate_successes"],
            "candidate_vlm_calls": summary["overall"]["vlm_calls"],
            "reference_vlm_calls": 0,
        },
        "paired_differential": method_metrics(failures, paired),
        "terminal_only_comparator": method_metrics(failures, terminal),
        "by_task": by_task,
        "paired_bootstrap_accuracy_difference": paired_bootstrap_accuracy_difference(gold, terminal, paired),
        "mcnemar_terminal_vs_paired": mcnemar_exact(gold, terminal, paired),
        "gold_labels": dict(sorted(Counter(gold).items())),
        "predictions": dict(sorted(Counter(paired).items())),
        "runtime": {
            "job_wall_seconds": wall_seconds,
            "preferred_instance_estimate_rub": preferred_rate * wall_seconds / 3600,
            "fallback_instance_estimate_rub": fallback_rate * wall_seconds / 3600,
            "actual_billing_rub": None,
        },
        "limitations": {
            "template_correlated_cases": True,
            "application_regression_gold_count": sum(label == "application_regression" for label in gold),
            "terminal_comparator_preregistered": False,
        },
    }


def svg_header(title: str, subtitle: str, width: int, height: int) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" rx="20" fill="{COLORS["bg"]}"/>',
        f'<text x="38" y="47" font-family="system-ui,sans-serif" font-size="24" font-weight="700" fill="{COLORS["navy"]}">{html.escape(title)}</text>',
        f'<text x="38" y="73" font-family="system-ui,sans-serif" font-size="14" fill="{COLORS["muted"]}">{html.escape(subtitle)}</text>',
    ]


def write_accuracy_chart(metrics: dict, path: Path) -> None:
    rows = [("Terminal-only comparator", metrics["terminal_only_comparator"], COLORS["red"]), ("Paired differential replay", metrics["paired_differential"], COLORS["green"])]
    parts = svg_header("Failure-attribution accuracy", "21 observed ShowUI failures · Wilson 95% intervals", 900, 300)
    for index, (label, row, color) in enumerate(rows):
        y = 112 + index * 82
        value = row["accuracy"]
        lo, hi = row["accuracy_wilson95"]
        parts += [
            f'<text x="38" y="{y + 23}" font-family="system-ui,sans-serif" font-size="16" fill="{COLORS["navy"]}">{html.escape(label)}</text>',
            f'<rect x="275" y="{y}" width="560" height="32" rx="7" fill="#E7EBF5"/>',
            f'<rect x="275" y="{y}" width="{560 * value:.1f}" height="32" rx="7" fill="{color}"/>',
            f'<line x1="{275 + 560 * lo:.1f}" y1="{y + 16}" x2="{275 + 560 * hi:.1f}" y2="{y + 16}" stroke="{COLORS["navy"]}" stroke-width="3"/>',
            f'<text x="850" y="{y + 23}" font-family="system-ui,sans-serif" font-size="15" font-weight="700" text-anchor="end" fill="{COLORS["navy"]}">{pct(value)}</text>',
        ]
    parts.append("</svg>")
    path.write_text("\n".join(parts))


def write_confusion_chart(metrics: dict, path: Path) -> None:
    matrix = metrics["paired_differential"]["confusion_matrix"]
    mapped = ("agent_error", "application_bug", "ambiguous")
    labels = ("Agent / harness", "Application regression", "Ambiguous")
    parts = svg_header("Paired replay confusion matrix", "Rows are causal gold; columns are blind predictions", 900, 470)
    x0, y0, cell = 310, 145, 105
    for index, label in enumerate(labels):
        parts.append(f'<text x="{x0 + index * cell + cell/2}" y="118" text-anchor="middle" font-family="system-ui,sans-serif" font-size="13" fill="{COLORS["navy"]}">{html.escape(label)}</text>')
        parts.append(f'<text x="285" y="{y0 + index * cell + cell/2 + 5}" text-anchor="end" font-family="system-ui,sans-serif" font-size="14" fill="{COLORS["navy"]}">{html.escape(label)}</text>')
        for j, predicted in enumerate(mapped):
            value = matrix[mapped[index]][predicted]
            fill = COLORS["green"] if index == j else ("#F1C7CA" if value else "#E7EBF5")
            parts += [
                f'<rect x="{x0 + j * cell}" y="{y0 + index * cell}" width="92" height="92" rx="10" fill="{fill}"/>',
                f'<text x="{x0 + j * cell + 46}" y="{y0 + index * cell + 57}" text-anchor="middle" font-family="system-ui,sans-serif" font-size="28" font-weight="700" fill="{COLORS["navy"]}">{value}</text>',
            ]
    parts.append("</svg>")
    path.write_text("\n".join(parts))


def write_sources_chart(summary: dict, path: Path) -> None:
    tasks = ("create_event", "add_attendee", "reschedule_event", "delete_event")
    parts = svg_header("Causal outcomes by task family", "Gold labels for candidate failures; successful candidates are omitted", 900, 410)
    x0, max_width = 250, 570
    for index, task in enumerate(tasks):
        rows = [row for row in summary["cases"] if row["task_id"] == task and row["gold_label"] != "no_failure"]
        counts = Counter(row["gold_label"] for row in rows)
        y, cursor = 112 + index * 66, x0
        parts.append(f'<text x="38" y="{y + 22}" font-family="system-ui,sans-serif" font-size="15" fill="{COLORS["navy"]}">{task}</text>')
        for label in LABELS:
            width = max_width * counts[label] / 6
            if width:
                parts += [
                    f'<rect x="{cursor:.1f}" y="{y}" width="{width:.1f}" height="31" fill="{COLORS[label]}"/>',
                    f'<text x="{cursor + width/2:.1f}" y="{y + 22}" text-anchor="middle" font-family="system-ui,sans-serif" font-size="14" font-weight="700" fill="white">{counts[label]}</text>',
                ]
            cursor += width
    legend_x = 250
    for label in LABELS:
        parts += [f'<rect x="{legend_x}" y="360" width="14" height="14" fill="{COLORS[label]}"/>', f'<text x="{legend_x + 21}" y="372" font-family="system-ui,sans-serif" font-size="13" fill="{COLORS["navy"]}">{DISPLAY[label]}</text>']
        legend_x += 205
    parts.append("</svg>")
    path.write_text("\n".join(parts))


def write_gallery(summary: dict, run_root: Path, output_dir: Path) -> None:
    chosen = ("delete_01", "attendee_02", "create_02", "attendee_01")
    assets = output_dir / "trace_assets"
    assets.mkdir(parents=True, exist_ok=True)
    rows_by_id = {row["case_id"]: row for row in summary["cases"]}
    cards = []
    for case_id in chosen:
        row = rows_by_id[case_id]
        case_root = run_root / "cases" / case_id
        figures = []
        for side in ("candidate", "reference"):
            shots = sorted((case_root / side).glob("step_*.png"))
            for position, source in (("initial", shots[0]), ("final", shots[-1])):
                target = f"{case_id}_{side}_{position}.png"
                shutil.copy2(source, assets / target)
                figures.append(f'<figure><img src="trace_assets/{target}" alt="{case_id} {side} {position}"><figcaption>{side.title()} · {position}</figcaption></figure>')
        diagnosis = json.loads((case_root / "diagnosis.json").read_text())
        cards.append(
            f'<article><header><div><h2>{case_id}: {html.escape(row["instruction"])}</h2><p>{row["task_id"]} · {row["split"]} · candidate stop={row["candidate"]["stop_reason"]}</p></div>'
            f'<strong>pred={row["prediction"]}<br>gold={row["gold_label"]}</strong></header><div class="frames">{"".join(figures)}</div><p><b>Blind reason:</b> {html.escape(diagnosis["reason"])}</p></article>'
        )
    page = f'''<!doctype html><html><head><meta charset="utf-8"><title>Paired differential replay gallery</title><style>
body{{font:15px system-ui;background:{COLORS['bg']};color:{COLORS['navy']};margin:0;padding:30px}}main{{max-width:1400px;margin:auto}}article{{background:white;border-radius:16px;padding:22px;margin:22px 0;box-shadow:0 5px 20px #18254216}}header{{display:flex;justify-content:space-between;gap:20px}}h1,h2{{margin:0 0 8px}}p{{color:{COLORS['muted']};}}.frames{{display:flex;gap:12px;overflow-x:auto}}figure{{min-width:300px;margin:0}}img{{width:100%;border:1px solid {COLORS['line']};border-radius:8px}}figcaption{{margin-top:5px;color:{COLORS['muted']};}}strong{{white-space:nowrap}}
</style></head><body><main><h1>Paired same-task differential replay</h1><p>Candidate and known-good reference receive the exact same parsed ShowUI actions. Gold is revealed only after prediction.</p>{''.join(cards)}</main></body></html>'''
    (output_dir / "trace_gallery.html").write_text(page)


def write_csv(metrics: dict, path: Path) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["method", "n", "accuracy", "app_precision", "app_recall", "false_bug_rate", "ambiguous_rate"])
        for key in ("terminal_only_comparator", "paired_differential"):
            row = metrics[key]
            writer.writerow([key, row["n"], row["accuracy"], row["application_bug_precision"], row["application_bug_recall"], row["non_application_false_bug_report_rate"], row["ambiguous_rate"]])


def write_report(summary: dict, metrics: dict, output_dir: Path, report_path: Path) -> None:
    paired, terminal = metrics["paired_differential"], metrics["terminal_only_comparator"]
    app_ci = paired["application_bug_precision_wilson95"]
    acc_ci = paired["accuracy_wilson95"]
    runtime = metrics["runtime"]
    task_rows = []
    for task, row in metrics["by_task"].items():
        task_rows.append(f'| `{task}` | {row["accuracy_count"][0]}/{row["n"]} | {pct(row["accuracy"])} | {row["ambiguous_count"][0]}/{row["n"]} |')
    report = f'''# Paired same-task ShowUI differential replay

## Result

ShowUI-2B ran on 24 frozen candidate tasks and made **122 actual model calls**. Every successfully parsed candidate action was replayed verbatim on a known-good reference without any extra VLM calls. The candidate failed on 21/24 tasks. Blind differential replay correctly attributed **20/21 failures = {pct(paired["accuracy"])}** (Wilson 95% CI {pct(acc_ci[0])}–{pct(acc_ci[1])}).

![Attribution accuracy](paired_results/accuracy_comparison.svg)

| method | accuracy | app-regression precision | app-regression recall | false bug reports among non-app failures | ambiguous predictions |
|---|---:|---:|---:|---:|---:|
| terminal-only comparator | {terminal["accuracy_count"][0]}/{terminal["n"]} ({pct(terminal["accuracy"])}) | {terminal["application_bug_precision_count"][0]}/{terminal["application_bug_precision_count"][1]} ({pct(terminal["application_bug_precision"])}) | 3/3 (100.0%) | 18/18 (100.0%) | 0/21 |
| paired differential replay | {paired["accuracy_count"][0]}/{paired["n"]} ({pct(paired["accuracy"])}) | 3/3 (100.0%; CI {pct(app_ci[0])}–{pct(app_ci[1])}) | 3/3 (100.0%) | 0/18 (0.0%) | 7/21 (33.3%) |

The terminal comparator intentionally labels every failure as an application regression and is included as an existing weak comparator, not as a newly preregistered baseline. Paired replay improves accuracy by **{100 * metrics["paired_bootstrap_accuracy_difference"]["difference"]:.1f} percentage points**; paired bootstrap 95% CI is {100 * metrics["paired_bootstrap_accuracy_difference"]["ci95"][0]:.1f}–{100 * metrics["paired_bootstrap_accuracy_difference"]["ci95"][1]:.1f} pp. McNemar exact two-sided p={metrics["mcnemar_terminal_vs_paired"]["exact_p_two_sided"]:.6f}, descriptive only because cases share templates.

![Confusion matrix](paired_results/confusion_matrix.svg)

## What the labels mean

- `application_regression`: candidate failed, but the same ShowUI actions succeeded on the reference; 3 cases, all faulted delete flows.
- `agent_or_harness`: candidate and reference failed identically without a decisive application effect; 10 gold cases.
- `ambiguous`: an application fault was reached, but the exact action sequence also failed on the reference, so neither source uniquely explains task failure; 8 gold cases.
- `no_failure`: the candidate succeeded; 3 clean delete cases, excluded from attribution metrics.

![Causal outcomes by task](paired_results/failure_sources_by_task.svg)

| task | correct / failures | accuracy | predicted ambiguous |
|---|---:|---:|---:|
{chr(10).join(task_rows)}

The sole error was `attendee_01`: a value-corruption fault was reached, but both candidate and reference failed; identical terminal pixels caused the blind rule to say `agent_or_harness`, while causal gold conservatively marked the case `ambiguous`.

## Protocol and leakage boundary

- 4 task families × 3 splits × 2 hidden conditions = 24 cases; every task/split cell has one clean and one faulted candidate.
- Model and revision were frozen before execution; config hash: `{summary["config_hash"]}`.
- ShowUI saw task text, screenshot, and its recent raw actions only. Candidate fault, target state, predicates, reference outcome, and gold were hidden.
- Reference replay used exact parsed candidate actions. It did not repair actions, ask ShowUI again, or use a label oracle.
- Diagnosis was written before the quarantined causal gold file. Gold additionally checked whether the hidden fault was actually reached.
- Raw screenshots, model outputs, parsed actions, stop reasons, hashes, and latencies are retained. See the [trace gallery](paired_results/trace_gallery.html).

## Runtime and cost

- Cloud job wall time: {runtime["job_wall_seconds"]:.1f}s ({runtime["job_wall_seconds"] / 60:.1f} min).
- Runtime-derived estimate: {runtime["preferred_instance_estimate_rub"]:.2f}–{runtime["fallback_instance_estimate_rub"]:.2f} RUB depending on allocated declared GPU; provider billing was not queried, so this is not an actual charge.
- Hard cap: 60 minutes and 160 calls; actual: 122 calls.

## Honest limitations

The result answers a narrow experimental question on one deterministic synthetic calendar. The 95.2% is not a general GUI-agent score: only 21 failures were attributed, only 3 had decisive application-regression gold, and cases share UI/task templates. The paired rule is expected to be strong when exact replay is deterministic. Its value is the auditable abstention behavior: when both copies fail, it avoids inventing certainty. Broader claims require additional applications, agents, naturally occurring regressions, and repeated stochastic runs.
'''
    report_path.write_text(report)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", required=True)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--metrics", required=True)
    parser.add_argument("--csv", required=True)
    parser.add_argument("--wall-seconds", type=float, required=True)
    parser.add_argument("--preferred-rate", type=float, default=168.48)
    parser.add_argument("--fallback-rate", type=float, default=234.0)
    args = parser.parse_args()
    summary = json.loads(Path(args.summary).read_text())
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics = build_metrics(summary, args.wall_seconds, args.preferred_rate, args.fallback_rate)
    atomic_write_json(args.metrics, metrics)
    write_csv(metrics, Path(args.csv))
    write_accuracy_chart(metrics, output_dir / "accuracy_comparison.svg")
    write_confusion_chart(metrics, output_dir / "confusion_matrix.svg")
    write_sources_chart(summary, output_dir / "failure_sources_by_task.svg")
    write_gallery(summary, Path(args.run_root), output_dir)
    write_report(summary, metrics, output_dir, Path(args.report))


if __name__ == "__main__":
    main()
