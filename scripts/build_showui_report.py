#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
from collections import Counter, defaultdict
from math import ceil
from pathlib import Path
from statistics import mean, median

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui_faultlab.evaluation.attribution import wilson_interval


TASK_LABELS = {
    "create_event": "Create event",
    "add_attendee": "Add attendee",
    "reschedule_event": "Reschedule",
    "delete_event": "Delete event",
}
COLORS = {
    "blue": "#4669E8",
    "navy": "#182542",
    "muted": "#68748B",
    "line": "#D4DAE7",
    "green": "#299770",
    "red": "#CA414B",
    "amber": "#E5A23A",
    "bg": "#F5F7FB",
}


def svg_start(width: int, height: int, title: str, subtitle: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="{COLORS["bg"]}" rx="20"/>',
        f'<text x="40" y="48" font-family="system-ui,sans-serif" font-size="25" font-weight="700" fill="{COLORS["navy"]}">{html.escape(title)}</text>',
        f'<text x="40" y="76" font-family="system-ui,sans-serif" font-size="14" fill="{COLORS["muted"]}">{html.escape(subtitle)}</text>',
    ]


def write_success_chart(summary: dict, path: Path) -> None:
    width, height = 900, 430
    rows = [(task, summary["by_task"][task]) for task in TASK_LABELS]
    parts = svg_start(width, height, "ShowUI task success", "Clean known-good application · 3 deterministic seeds per task")
    x0, max_width = 250, 580
    for index, (task, row) in enumerate(rows):
        y = 120 + index * 68
        rate = row["success_rate"]
        bar_width = max_width * rate
        parts += [
            f'<text x="40" y="{y + 20}" font-family="system-ui,sans-serif" font-size="17" fill="{COLORS["navy"]}">{TASK_LABELS[task]}</text>',
            f'<rect x="{x0}" y="{y}" width="{max_width}" height="30" rx="7" fill="#E7EBF5"/>',
            f'<rect x="{x0}" y="{y}" width="{bar_width}" height="30" rx="7" fill="{COLORS["green"]}"/>',
            f'<text x="{x0 + 12}" y="{y + 21}" font-family="system-ui,sans-serif" font-size="14" font-weight="700" fill="{COLORS["navy"]}">{row["successes"]}/{row["episodes"]} · {100 * rate:.0f}%</text>',
        ]
    parts.append('</svg>')
    path.write_text("\n".join(parts))


def write_stop_chart(summary: dict, path: Path) -> None:
    width, height = 900, 410
    counts = summary["overall"]["stop_reasons"]
    rows = [
        ("Task success", counts.get("task_success", 0), COLORS["green"]),
        ("No-change loop", counts.get("no_change_loop", 0), COLORS["amber"]),
        ("Multi-action parse failure", counts.get("parse_error", 0), COLORS["red"]),
        ("Step budget exhausted", counts.get("max_steps", 0), COLORS["blue"]),
    ]
    parts = svg_start(width, height, "How episodes ended", "Stop reason is recorded online; no manual relabeling")
    x0, scale = 330, 105
    for index, (label, value, color) in enumerate(rows):
        y = 115 + index * 65
        parts += [
            f'<text x="40" y="{y + 21}" font-family="system-ui,sans-serif" font-size="17" fill="{COLORS["navy"]}">{html.escape(label)}</text>',
            f'<rect x="{x0}" y="{y}" width="{value * scale}" height="31" rx="7" fill="{color}"/>',
            f'<text x="{x0 + value * scale + 12}" y="{y + 22}" font-family="system-ui,sans-serif" font-size="15" font-weight="700" fill="{COLORS["navy"]}">{value}</text>',
        ]
    parts.append('</svg>')
    path.write_text("\n".join(parts))


def write_latency_chart(steps_by_task: dict[str, list[dict]], path: Path) -> None:
    width, height = 900, 470
    parts = svg_start(width, height, "Inference latency by task", "Each dot is one model call · first-call warm-up outlier retained")
    plot_top, plot_bottom = 105, 390
    plot_height = plot_bottom - plot_top
    max_seconds = 55
    for tick in (0, 10, 20, 30, 40, 50):
        y = plot_bottom - tick / max_seconds * plot_height
        parts += [
            f'<line x1="85" y1="{y:.1f}" x2="860" y2="{y:.1f}" stroke="{COLORS["line"]}"/>',
            f'<text x="42" y="{y + 5:.1f}" font-family="system-ui,sans-serif" font-size="13" fill="{COLORS["muted"]}">{tick}s</text>',
        ]
    task_order = list(TASK_LABELS)
    for task_index, task in enumerate(task_order):
        center = 170 + task_index * 190
        latencies = [step["latency_ms"] / 1000 for step in steps_by_task[task]]
        for index, seconds in enumerate(latencies):
            jitter = ((index * 37) % 31) - 15
            y = plot_bottom - min(seconds, max_seconds) / max_seconds * plot_height
            parts.append(f'<circle cx="{center + jitter}" cy="{y:.1f}" r="5" fill="{COLORS["blue"]}" opacity="0.70"/>')
        med = median(latencies)
        med_y = plot_bottom - med / max_seconds * plot_height
        parts += [
            f'<line x1="{center - 34}" y1="{med_y:.1f}" x2="{center + 34}" y2="{med_y:.1f}" stroke="{COLORS["red"]}" stroke-width="4"/>',
            f'<text x="{center}" y="425" text-anchor="middle" font-family="system-ui,sans-serif" font-size="14" fill="{COLORS["navy"]}">{TASK_LABELS[task]}</text>',
            f'<text x="{center}" y="446" text-anchor="middle" font-family="system-ui,sans-serif" font-size="12" fill="{COLORS["muted"]}">median {med:.1f}s · n={len(latencies)}</text>',
        ]
    parts.append('</svg>')
    path.write_text("\n".join(parts))


def load_steps(run_root: Path) -> tuple[list[dict], dict[str, list[dict]]]:
    all_steps = []
    by_task = defaultdict(list)
    for episode_dir in sorted((run_root / "episodes").iterdir()):
        evaluation = json.loads((episode_dir / "evaluation.json").read_text())
        for line in (episode_dir / "steps.jsonl").read_text().splitlines():
            step = json.loads(line)
            step["task_id"] = evaluation["task_id"]
            step["episode_id"] = evaluation["episode_id"]
            all_steps.append(step)
            by_task[evaluation["task_id"]].append(step)
    return all_steps, by_task


def write_gallery(summary: dict, run_root: Path, output_dir: Path) -> None:
    assets = output_dir / "trace_assets"
    assets.mkdir(parents=True, exist_ok=True)
    chosen = {}
    for episode in summary["episodes"]:
        chosen.setdefault(episode["task_id"], episode)

    cards = []
    for task in TASK_LABELS:
        episode = chosen[task]
        source_dir = run_root / "episodes" / episode["episode_id"]
        steps = [json.loads(line) for line in (source_dir / "steps.jsonl").read_text().splitlines()]
        frames = []
        for index, screenshot in enumerate(sorted(source_dir.glob("step_*.png"))):
            name = f"{task}_{index:02d}.png"
            shutil.copy2(screenshot, assets / name)
            caption = "Initial screen" if index == 0 else f"After step {index}"
            frames.append(f'<figure><img src="trace_assets/{name}" alt="{html.escape(task)} {index}"><figcaption>{caption}</figcaption></figure>')
        action_rows = []
        for step in steps:
            action = step.get("parsed_action") or {"type": "parse error"}
            detail = step["raw_output"]
            action_rows.append(
                f'<tr><td>{step["index"]}</td><td><code>{html.escape(action["type"])}</code></td>'
                f'<td>{"yes" if step["screen_changed"] else "no"}</td><td><code>{html.escape(detail)}</code></td></tr>'
            )
        outcome = "SUCCESS" if episode["task_success"] else "AGENT ERROR"
        color = COLORS["green"] if episode["task_success"] else COLORS["red"]
        cards.append(
            f'<article><header><div><h2>{TASK_LABELS[task]}</h2><p>seed={episode["seed"]} · split={episode["split"]} · stop={episode["stop_reason"]}</p></div>'
            f'<strong style="color:{color}">{outcome}</strong></header><div class="frames">{"".join(frames)}</div>'
            f'<table><thead><tr><th>step</th><th>parsed</th><th>screen changed</th><th>raw model output</th></tr></thead><tbody>{"".join(action_rows)}</tbody></table></article>'
        )

    page = f'''<!doctype html><html><head><meta charset="utf-8"><title>ShowUI trace gallery</title><style>
body{{font:15px system-ui;background:{COLORS['bg']};color:{COLORS['navy']};margin:0;padding:32px}}main{{max-width:1280px;margin:auto}}article{{background:white;border-radius:16px;padding:24px;margin:24px 0;box-shadow:0 5px 20px #18254216}}article header{{display:flex;justify-content:space-between;align-items:start}}h1,h2{{margin:0 0 8px}}p{{color:{COLORS['muted']}}}.frames{{display:flex;gap:14px;overflow-x:auto;padding:8px 0 18px}}figure{{min-width:360px;margin:0}}img{{width:100%;border:1px solid {COLORS['line']};border-radius:8px}}figcaption{{color:{COLORS['muted']};margin-top:5px}}table{{border-collapse:collapse;width:100%}}th,td{{text-align:left;border-top:1px solid {COLORS['line']};padding:10px;vertical-align:top}}code{{white-space:pre-wrap;word-break:break-word}}
</style></head><body><main><h1>ShowUI-2B closed-loop trace gallery</h1><p>One deterministic seed per task. Raw model outputs are shown without repair.</p>{''.join(cards)}</main></body></html>'''
    (output_dir / "trace_gallery.html").write_text(page)


def write_report(summary: dict, all_steps: list[dict], output_dir: Path, report_path: Path, wall_seconds: float, max_cost: float, expected_cost: float) -> None:
    overall = summary["overall"]
    successes, episodes = overall["successes"], overall["episodes"]
    ci = wilson_interval(successes, episodes)
    latencies = sorted(step["latency_ms"] for step in all_steps)
    p95 = latencies[max(0, ceil(0.95 * len(latencies)) - 1)]
    actions = Counter((step.get("parsed_action") or {}).get("type", "parse_error") for step in all_steps)
    rows = []
    for task in TASK_LABELS:
        row = summary["by_task"][task]
        task_ci = wilson_interval(row["successes"], row["episodes"])
        rows.append(
            f'| `{task}` | {row["successes"]}/{row["episodes"]} | {100 * row["success_rate"]:.1f}% | '
            f'{100 * task_ci[0]:.1f}%–{100 * task_ci[1]:.1f}% | {row["vlm_calls"]} | {row["mean_steps"]:.1f} |'
        )
    report = f'''# ShowUI-2B closed-loop baseline

This is the learned-agent companion to UI-FaultLab's 36-episode controlled attribution benchmark. ShowUI saw only the task text, current screenshot, and the last four raw actions. The application was known-good and had no injected faults, so every failed task is attributable to the agent; successful tasks have no failure label.

## Headline result

**{successes}/{episodes} tasks succeeded ({100 * successes / episodes:.1f}%; Wilson 95% CI {100 * ci[0]:.1f}%–{100 * ci[1]:.1f}%).** All three successes were `delete_event`; the other three task families failed on every seed.

![Success rate by task](showui_results/success_by_task.svg)

| task | successes | rate | Wilson 95% CI | VLM calls | mean steps |
|---|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

## What failed

![Episode stop reasons](showui_results/stop_reasons.svg)

- `create_event`: 3/3 failures. The model found the correct button, then emitted multiple actions in one turn; the strict one-action executor rejected all three traces rather than silently repairing them.
- `add_attendee`: 3/3 failures. It opened the correct event, but placed the email in the title field instead of the attendee field.
- `reschedule_event`: 3/3 failures. It placed the new time in the date field, saved, and then wandered or looped.
- `delete_event`: 3/3 successes, always in three valid clicks: card → Delete → Confirm.

The visual [trace gallery](showui_results/trace_gallery.html) contains one full trajectory per task with screenshots and raw outputs.

## Runtime and action statistics

![Inference latency](showui_results/latency_by_task.svg)

- Episodes: {episodes}; VLM calls: {overall['vlm_calls']}.
- Mean call latency: {mean(latencies) / 1000:.2f}s; median: {median(latencies) / 1000:.2f}s; p95: {p95 / 1000:.2f}s.
- Actions: {', '.join(f'{key}={value}' for key, value in sorted(actions.items()))}.
- Parse failures: {overall['parse_failures']}/{overall['vlm_calls']} ({100 * overall['parse_failures'] / overall['vlm_calls']:.1f}%).
- No-change transitions: {overall['no_change_steps']}/{overall['vlm_calls']} ({100 * overall['no_change_steps'] / overall['vlm_calls']:.1f}%).
- Cloud job wall time: {wall_seconds:.1f}s. Runtime-derived cost range: about {expected_cost:.2f}–{max_cost:.2f} RUB depending on which declared GPU instance was allocated; billing was not yet available when this report was generated.

## Reproducibility boundary

- Model: `showlab/ShowUI-2B`, pinned revision `{summary['model_revision']}`.
- Protocol: `{summary['protocol']}`; task observation version `{summary['task_version']}`.
- Config hash: `{summary['config_hash']}`.
- Deterministic seeds/splits: dev=0, validation=1, test=2.
- Raw outputs are preserved exactly. Invalid multi-action outputs are counted as failures, not repaired.
- The fast Qwen2-VL image processor was used because the checkpoint's current configuration is incompatible with the legacy slow processor. This can affect exact output parity with older releases.

## Interpretation

This run supports a narrow claim: ShowUI-2B can ground salient controls and complete the short delete flow, but it is unreliable on form-heavy multi-step tasks in this synthetic calendar. The 25% rate is not a general GUI-agent benchmark score—the sample is only 12 template-correlated episodes. Its purpose is to replace hypothetical agent errors with reproducible observed trajectories while keeping the causal attribution benchmark separate and controlled.
'''
    report_path.write_text(report)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", required=True)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--cloud-archive", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--wall-seconds", type=float, required=True)
    parser.add_argument("--preferred-rate", type=float, default=168.48)
    parser.add_argument("--fallback-rate", type=float, default=234.0)
    args = parser.parse_args()

    summary = json.loads(Path(args.summary).read_text())
    run_root = Path(args.run_root)
    output_dir = Path(args.output_dir)
    report_path = Path(args.report)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    all_steps, by_task = load_steps(run_root)
    write_success_chart(summary, output_dir / "success_by_task.svg")
    write_stop_chart(summary, output_dir / "stop_reasons.svg")
    write_latency_chart(by_task, output_dir / "latency_by_task.svg")
    write_gallery(summary, run_root, output_dir)
    shutil.copy2(args.summary, output_dir / "showui_full_summary.json")
    shutil.copy2(args.cloud_archive, output_dir / "showui_full_run.tar.gz")
    hours = args.wall_seconds / 3600
    write_report(
        summary, all_steps, output_dir, report_path, args.wall_seconds,
        args.fallback_rate * hours, args.preferred_rate * hours,
    )


if __name__ == "__main__":
    main()
