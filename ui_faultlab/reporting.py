from __future__ import annotations

import csv
import html
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

from ui_faultlab.evaluation.attribution import attribution_metrics, wilson_interval
from ui_faultlab.evaluation.recovery import recovery_metrics
from ui_faultlab.evaluation.statistics import mcnemar_exact, paired_bootstrap_accuracy_difference
from ui_faultlab.instrumentation import atomic_write_json


def load_evaluations(artifacts_root: str | Path) -> list[dict]:
    root = Path(artifacts_root)
    return [json.loads(path.read_text()) for path in sorted((root / "episodes").glob("*/evaluation.json"))]


def compute_report(evaluations: list[dict]) -> dict:
    failed = [e for e in evaluations if not e["task_success"] and e["gold_label"] in {"agent_error", "application_bug"}]
    metrics = {}
    for method in ("terminal", "trajectory", "active", "oracle"):
        gold = [e["gold_label"] for e in failed]
        pred = [e["predictions"][method]["label"] for e in failed]
        metrics[method] = attribution_metrics(gold, pred)
    clean = [e for e in evaluations if e["condition"] == "clean"]
    faulted = [e for e in evaluations if e["condition"] != "clean"]
    clean_success = sum(e["task_success"] for e in clean)
    fault_success = sum(e["task_success"] for e in faulted)
    by_split = {}
    for split in sorted({e["split"] for e in evaluations}):
        subset = [e for e in failed if e["split"] == split]
        by_split[split] = {}
        for method in ("terminal", "trajectory", "active"):
            by_split[split][method] = attribution_metrics(
                [e["gold_label"] for e in subset],
                [e["predictions"][method]["label"] for e in subset],
            )
    gold = [e["gold_label"] for e in failed]
    terminal = [e["predictions"]["terminal"]["label"] for e in failed]
    active = [e["predictions"]["active"]["label"] for e in failed]
    return {
        "episode_count": len(evaluations),
        "failed_attribution_episode_count": len(failed),
        "condition_counts": dict(Counter(e["condition"] for e in evaluations)),
        "split_counts": dict(Counter(e["split"] for e in evaluations)),
        "task_metrics": {
            "clean_success_rate": clean_success / len(clean) if clean else 0.0,
            "clean_success_count": [clean_success, len(clean)],
            "clean_success_wilson95": wilson_interval(clean_success, len(clean)),
            "faulted_success_rate": fault_success / len(faulted) if faulted else 0.0,
            "faulted_success_count": [fault_success, len(faulted)],
            "faulted_success_wilson95": wilson_interval(fault_success, len(faulted)),
            "invalid_action_rate": sum(e["invalid_actions"] for e in evaluations) / max(1, sum(e["steps"] for e in evaluations)),
            "parse_failure_rate": sum(e["parse_failures"] for e in evaluations) / max(1, sum(e["steps"] for e in evaluations)),
            "loop_repetition_rate": sum(e["loop_repetitions"] for e in evaluations) / max(1, sum(e["steps"] for e in evaluations)),
            "mean_steps": mean([e["steps"] for e in evaluations]) if evaluations else 0.0,
        },
        "attribution": metrics,
        "by_split": by_split,
        "recovery": recovery_metrics(evaluations),
        "paired_terminal_to_active": paired_bootstrap_accuracy_difference(gold, terminal, active),
        "mcnemar_terminal_to_active": mcnemar_exact(gold, terminal, active),
        "cost_latency": {
            "vlm_calls": sum(e["vlm_calls"] for e in evaluations),
            "estimated_cost_rub": sum(e["estimated_cost_rub"] for e in evaluations),
            "mean_execution_latency_ms": mean([e["latency_ms"]["execution"] for e in evaluations]) if evaluations else 0.0,
            "mean_active_probe_latency_ms": mean([e["latency_ms"]["active_probe"] for e in evaluations]) if evaluations else 0.0,
            "gpu_wall_clock_seconds": 0.0,
        },
    }


def _pct(value: float) -> str:
    return f"{100 * value:.1f}%"


def _ci(values: list[float]) -> str:
    return f"[{100 * values[0]:.1f}%, {100 * values[1]:.1f}%]"


def write_summary_csv(metrics: dict, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["method", "n", "bug_precision", "bug_recall", "macro_f1", "accuracy", "false_bug_report_rate", "ambiguous_rate"])
        for method, row in metrics["attribution"].items():
            writer.writerow([method, row["n"], row["application_bug_precision"], row["application_bug_recall"], row["macro_f1"], row["accuracy"], row["false_bug_report_rate"], row["ambiguous_rate"]])


def build_report(artifacts_root: str | Path, output: str | Path) -> dict:
    artifacts_root, output = Path(artifacts_root), Path(output)
    evaluations = load_evaluations(artifacts_root)
    metrics = compute_report(evaluations)
    atomic_write_json(artifacts_root / "tables" / "metrics.json", metrics)
    write_summary_csv(metrics, artifacts_root / "tables" / "attribution_summary.csv")
    gallery = build_failure_gallery(evaluations, output.parent / "failure_gallery")
    rows = []
    for method in ("terminal", "trajectory", "active", "oracle"):
        m = metrics["attribution"][method]
        bp_num, bp_den = m["application_bug_precision_count"]
        fb_num, fb_den = m["false_bug_report_count"]
        acc_num, acc_den = m["accuracy_count"]
        rows.append(f"| {method} | {bp_num}/{bp_den} ({_pct(m['application_bug_precision'])}) | {m['application_bug_recall_count'][0]}/{m['application_bug_recall_count'][1]} ({_pct(m['application_bug_recall'])}) | {_pct(m['macro_f1'])} | {acc_num}/{acc_den} ({_pct(m['accuracy'])}) | {fb_num}/{fb_den} ({_pct(m['false_bug_report_rate'])}) | {_pct(m['ambiguous_rate'])} |")
    primary = metrics["attribution"]["active"]
    clean = metrics["task_metrics"]
    paired = metrics["paired_terminal_to_active"]
    mcnemar = metrics["mcnemar_terminal_to_active"]
    text = f"""# UI-FaultLab Experimental Report

Generated automatically from machine-readable episode artifacts. No result below was copied by hand.

## Scope and protocol

- Episodes: **{metrics['episode_count']}** ({', '.join(f'{k}={v}' for k, v in sorted(metrics['condition_counts'].items()))}).
- Splits: {', '.join(f'{k}={v}' for k, v in sorted(metrics['split_counts'].items()))}.
- Attribution denominator: **{metrics['failed_attribution_episode_count']} failed episodes**; clean successes are excluded from attribution scores.
- Actor: scripted oracle (`builtin-v1`) for controlled environment validation, **not a learned research baseline**.
- Diagnosers: deterministic terminal-only, passive-trajectory, and one-probe active replay; oracle is a privileged upper bound.
- Primary metric fixed before test access: application-bug precision.

## Results

| method | application-bug precision | application-bug recall | macro-F1 | accuracy | false bug report rate | abstention |
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

Primary result: active replay application-bug precision was **{primary['application_bug_precision_count'][0]}/{primary['application_bug_precision_count'][1]} = {_pct(primary['application_bug_precision'])}**, Wilson 95% CI {_ci(primary['application_bug_precision_wilson95'])}. Its false bug report rate was **{primary['false_bug_report_count'][0]}/{primary['false_bug_report_count'][1]} = {_pct(primary['false_bug_report_rate'])}**, Wilson 95% CI {_ci(primary['false_bug_report_wilson95'])}.

Terminal-to-active paired accuracy difference was **{100 * paired['difference']:+.1f} pp**, episode bootstrap 95% CI {_ci(paired['ci95'])}. McNemar had {mcnemar['discordant']} discordant pairs (exact two-sided p={mcnemar['exact_p_two_sided']:.4f}); {"power is low and this is descriptive, not proof" if mcnemar['low_power_warning'] else "this remains a small synthetic study"}.

## Task execution and cost

- Clean task success: {clean['clean_success_count'][0]}/{clean['clean_success_count'][1]} = {_pct(clean['clean_success_rate'])}, Wilson 95% CI {_ci(clean['clean_success_wilson95'])}.
- Faulted task success: {clean['faulted_success_count'][0]}/{clean['faulted_success_count'][1]} = {_pct(clean['faulted_success_rate'])}.
- Mean steps per episode: {clean['mean_steps']:.2f}; invalid action rate: {_pct(clean['invalid_action_rate'])}; parse failure rate: {_pct(clean['parse_failure_rate'])}.
- Active probes: {metrics['recovery']['active_probes']} total, {metrics['recovery']['active_probes_per_episode']:.2f} per episode overall; hard cap was one per failed episode.
- VLM calls: {metrics['cost_latency']['vlm_calls']}; GPU wall-clock: {metrics['cost_latency']['gpu_wall_clock_seconds']:.1f}s; estimated spend: **{metrics['cost_latency']['estimated_cost_rub']:.2f} RUB**.
- Mean local episode execution latency: {metrics['cost_latency']['mean_execution_latency_ms']:.1f} ms; mean active-probe latency: {metrics['cost_latency']['mean_active_probe_latency_ms']:.1f} ms.

## Failure gallery

The generated [failure gallery](failure_gallery/index.html) contains {gallery['count']} cases with pre/post/probe screenshots and all three predictions. Recommended demo traces are listed in `artifacts/tables/demo_traces.json`.

## Interpretation

Within this controlled synthetic calendar, terminal-only diagnosis over-reported application bugs because a failed final screen cannot reveal whether the requested interaction was actually executed. Passive history recovered visible no-op divergences but missed some semantically wrong targets. A single replay of the intended action separated all represented clean agent faults from application transition faults in this experiment. This is an operational prototype result, not evidence of generalization to arbitrary applications.

## Limitations

- The actor and three principal diagnosers are deterministic, model-free baselines. A real open VLM baseline is separately gated and was not substituted with invented outputs.
- Screenshots come from a deterministic renderer synchronized with the same UI transition model as the local web app; browser-pixel parity still requires Playwright/Node on the demo machine.
- The application, tasks, and faults are synthetic, with one fault family per episode and three state seeds.
- Confidence intervals quantify binomial uncertainty in this small fixture set; episodes share templates and are not independent real-world products.
- Active replay restores an internal snapshot through the environment service, while its attribution decision receives only the replay screenshot/hash—not backend state or the gold label.
"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text)
    return metrics


def build_failure_gallery(evaluations: list[dict], output_dir: str | Path, count: int = 6) -> dict:
    output_dir = Path(output_dir)
    assets = output_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    candidates = [e for e in evaluations if not e["task_success"] and e["predictions"]["active"]["label"] == e["gold_label"]]
    candidates.sort(key=lambda e: (e["predictions"]["trajectory"]["label"] == e["gold_label"], e["predictions"]["terminal"]["label"] == e["gold_label"], e["task_id"], e["episode_id"]))
    priority = ["wrong_candidate", "duplicate_action", "confirmation_transition_bug", "coordinate_jitter", "save_noop", "value_corruption"]
    chosen = []
    for fault_type in priority:
        match = next((e for e in candidates if e["gold_fault_type"] == fault_type), None)
        if match is not None and match not in chosen:
            chosen.append(match)
    chosen.extend(e for e in candidates if e not in chosen)
    chosen = chosen[:count]
    cards = []
    demo = []
    for index, episode in enumerate(chosen, 1):
        evidence = episode["predictions"]["active"].get("evidence", [])
        copied = []
        for frame_index, source in enumerate(evidence[:2]):
            source_path = Path(source)
            if not source_path.is_absolute():
                source_path = Path.cwd() / source_path
            name = f"case_{index:02d}_{frame_index}.png"
            if source_path.exists():
                shutil.copy2(source_path, assets / name)
                copied.append(f"assets/{name}")
        images = "".join(f'<figure><img src="{html.escape(path)}" alt="evidence screenshot"><figcaption>{"Observed" if j == 0 else "Counterfactual replay"}</figcaption></figure>' for j, path in enumerate(copied))
        cards.append(f"<article><h2>Case {index}: {html.escape(episode['task_id'])}</h2><p><b>Gold:</b> {html.escape(episode['gold_label'])} / {html.escape(str(episode['gold_fault_type']))}</p><p><b>Terminal:</b> {episode['predictions']['terminal']['label']} · <b>Trajectory:</b> {episode['predictions']['trajectory']['label']} · <b>Active:</b> {episode['predictions']['active']['label']}</p><div class='frames'>{images}</div><p>{html.escape(episode['predictions']['active'].get('hypothesis',''))}</p></article>")
        demo.append({"rank": index, "episode_id": episode["episode_id"], "task_id": episode["task_id"], "fault_type": episode["gold_fault_type"], "gold_label": episode["gold_label"], "why": "terminal/trajectory comparison plus one visual counterfactual"})
    page = """<!doctype html><html><head><meta charset='utf-8'><title>UI-FaultLab failure gallery</title><style>body{font:16px system-ui;background:#f5f7fb;color:#182542;margin:0;padding:32px}header,article{max-width:1120px;margin:0 auto 28px}article{background:#fff;padding:24px;border-radius:14px;box-shadow:0 3px 18px #18254218}.frames{display:grid;grid-template-columns:1fr 1fr;gap:18px}img{width:100%;border:1px solid #d4dae7;border-radius:8px}figcaption{color:#68748b;margin-top:6px}@media(max-width:800px){.frames{grid-template-columns:1fr}}</style></head><body><header><h1>UI-FaultLab: visual failure gallery</h1><p>Observed failure versus one counterfactual replay. Gold labels appear only in this post-evaluation view.</p></header>""" + "".join(cards) + "</body></html>"
    (output_dir / "index.html").write_text(page)
    if evaluations:
        artifacts_root = Path(evaluations[0]["predictions"]["terminal"]["evidence"][0]).parents[2]
        if not artifacts_root.is_absolute():
            artifacts_root = Path.cwd() / artifacts_root
        atomic_write_json(artifacts_root / "tables" / "demo_traces.json", demo[:3])
    return {"count": len(chosen), "episodes": [e["episode_id"] for e in chosen]}
