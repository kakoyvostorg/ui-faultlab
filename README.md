# UI-FaultLab

[![CI](https://github.com/kakoyvostorg/ui-faultlab/actions/workflows/ci.yml/badge.svg)](https://github.com/kakoyvostorg/ui-faultlab/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

UI-FaultLab is a compact executable prototype for a specific GUI-agent reliability question:

> When a visual UI test fails, can trajectory-conditioned replay distinguish an agent mistake from an application defect more reliably than a final-screenshot judgment?

The repository contains a deterministic Mini Calendar, screenshot-only observations, three agent faults, three application faults, resumable artifact logging, execution-based evaluation, a 36-episode controlled mechanism study, a 12-episode ShowUI-2B action baseline, and a frozen 24-case learned-agent differential-replay experiment.

This is a controlled synthetic study inspired by GUI-agent reliability work. It is not a production tester, a general benchmark, or a state-of-the-art claim.

## Current result

### Learned-agent paired attribution

The strongest end-to-end result uses real ShowUI-2B trajectories rather than a scripted actor. ShowUI ran once on each of 24 frozen candidate tasks and made 122 model calls. Every parsed candidate action was then replayed unchanged on a known-good reference, with no extra VLM inference.

Among 21 candidate failures, blind differential replay correctly attributed **20/21 = 95.2%** (Wilson 95% CI 77.3%–99.2%). It identified all 3 causally decisive application regressions, made **0/18 false application-bug reports** on other failures, and returned `ambiguous` for 7/21 failures. An existing terminal-only comparator that calls every failure an application regression was correct on 3/21 and falsely blamed the application on 18/18 non-application failures.

![Paired attribution accuracy](report/paired_results/accuracy_comparison.svg)

This is a small synthetic result, not a general benchmark score: there are only three decisive application-regression cases, and all cases share one calendar UI. Eight faulted failures have conservative `ambiguous` gold because the same actions also failed on the reference. See the [paired results report](report/PAIRED_RESULTS.md), [trace gallery](report/paired_results/trace_gallery.html), [metrics](artifacts/paired_metrics.json), and [validated raw archive](artifacts/paired_same_task_run.tar.gz).

### Controlled mechanism benchmark

The frozen experiment has 36 episodes: 4 tasks × 3 state seeds × clean/agent-fault/application-fault. All report values are rebuilt from `artifacts/episodes/*/evaluation.json`.

| diagnosis | app-bug precision | app-bug recall | accuracy | false bug report rate |
|---|---:|---:|---:|---:|
| terminal-only | 12/24 = 50.0% | 12/12 = 100.0% | 12/24 = 50.0% | 12/12 = 100.0% |
| passive trajectory | 12/16 = 75.0% | 12/12 = 100.0% | 20/24 = 83.3% | 4/12 = 33.3% |
| one-probe active replay | 12/12 = 100.0% | 12/12 = 100.0% | 24/24 = 100.0% | 0/12 = 0.0% |

For the primary active app-bug precision, the Wilson 95% interval is 75.8%–100.0%. The result is exact for these fixtures but small, template-correlated, and synthetic. See [`report/REPORT.md`](report/REPORT.md) for denominators, intervals, paired bootstrap, McNemar, cost, and limitations.

### Earlier clean ShowUI-2B action baseline

The learned-agent baseline ran 12 clean, known-good episodes: 4 tasks × 3 deterministic seeds. It made 53 real model calls and succeeded on 3/12 tasks (25.0%; Wilson 95% CI 8.9%–53.2%). All three successes were the short `delete_event` flow; the three form-heavy task families failed on every seed.

![ShowUI success by task](report/showui_results/success_by_task.svg)

The failures are observed rather than hypothetical: `create_event` produced three strict-protocol parse failures after emitting multiple actions at once, while attendee and rescheduling traces targeted the wrong form fields and then looped or exhausted the step budget. See the full [ShowUI results note](report/SHOWUI_RESULTS.md), [interactive trace gallery](report/showui_results/trace_gallery.html), [machine-readable summary](artifacts/showui_full_summary.json), and [complete trajectory archive](artifacts/showui_full_run.tar.gz).

## Quick start

The runtime itself uses only the Python standard library. Python 3.11+ is required.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install pytest
.venv/bin/pytest -q
```

Run one deterministic episode:

```bash
python3 scripts/run_episode.py \
  --config configs/local_smoke.yaml \
  --agent scripted \
  --task create_event
```

Open the real Mini Calendar web UI:

```bash
python3 -m app.server --host 127.0.0.1 --port 8765
```

Then visit `http://127.0.0.1:8765`. The browser UI exposes only normal application state. It never exposes injected fault labels or evaluator state.

## Reproduce the frozen experiment

Run the splits in order. Validation writes `artifacts/freeze.json`; test refuses to run without both explicit flags and a matching frozen config hash.

```bash
python3 scripts/run_experiment.py --config configs/experiment.yaml --split dev
python3 scripts/run_experiment.py --config configs/experiment.yaml --split validation
python3 scripts/run_experiment.py \
  --config configs/experiment.yaml \
  --split test \
  --evaluate-test \
  --allow-test \
  --test-reason "final evaluation after frozen deterministic-v1 validation"
python3 scripts/build_report.py --artifacts artifacts --output report/REPORT.md
```

Completed episodes with the same config hash are resumed rather than overwritten. Use `--force` only for an intentional regeneration; old runs should be archived first if preservation matters.

## Environment and tasks

Mini Calendar provides four multi-step tasks:

- `create_event`: enter a title, date, and time, then save.
- `add_attendee`: edit Design Review, add an attendee, then save.
- `reschedule_event`: edit Design Review, replace its time, then save.
- `delete_event`: open Deprecated Sync, delete it, and confirm the modal.

Actions use a validated normalized schema: `tap(x,y)`, `input(x,y,text)`, `type(text)`, `scroll(direction)`, `back`, and `finish`. `input` atomically focuses a visible field and enters text, matching ShowUI's official action semantics. Coordinates are `[x,y]` in `[0,1]`, measured from the screenshot's top-left. Reset state, event ordering, task text, and screenshot rendering are deterministic for a given seed.

## Faults and causal labels

Agent faults intercept one intended action and preserve both requested and executed actions in privileged logs:

- `coordinate_jitter`
- `wrong_candidate`
- `duplicate_action`

Application faults modify the actual transition or persisted state:

- `save_noop`
- `value_corruption`
- `confirmation_transition_bug`

Must-have episodes contain exactly one fault family. Gold metadata is saved in `gold.json` only after episode identity is fixed; it is excluded from the agent and main diagnoser serializers.

## Screenshot-only boundary

| consumer | allowed | forbidden |
|---|---|---|
| visual actor | instruction, screenshot path, requested-action history | DOM, accessibility tree, backend state, fault type, target boxes, predicates |
| terminal diagnoser | instruction, final screenshot, failure fact | action history, backend state, gold label |
| passive diagnoser | instruction, screenshots, requested actions, visible transition result | executed-action override, injector metadata, backend state, gold label |
| active diagnoser | passive context plus one replay screenshot | restored state contents, app-fault setting, backend state, gold label |
| oracle/evaluator | all privileged state | n/a; always labeled oracle |

The artifact `steps.jsonl` intentionally retains intended/executed actions for post-hoc auditing, but `public_trajectory()` strips executed actions and injector flags before main diagnosis. Tests fail if forbidden keys cross that boundary.

## Diagnosis modes

1. **Terminal-only** sees only the failed final screenshot and is intentionally weak.
2. **Passive trajectory** inspects visible screenshot/action transitions and selects a first suspected step.
3. **Active replay** restores the environment immediately before that step and executes one intended-action counterfactual under the same application condition. It classifies from visual transition agreement, never from the fault label.
4. **Oracle** reads privileged fault metadata only as an evaluator upper bound.

The three principal diagnosers in the controlled attribution experiment are deterministic and model-free. This cleanly tests the environment and causal replay mechanism. The separate ShowUI run tests learned visual action generation, not learned failure diagnosis.

## Open VLM baseline

The ShowUI-2B checkpoint was checked against official sources and pinned to `cabec4fcc48d15ffd3efe0b33ea9bc7d41509d60`. The adapter follows the official single-action dictionary protocol, normalized `[x,y]` coordinates, and official preprocessing bounds. Raw generations are preserved exactly and parsed with a strict literal parser; malformed or multi-action generations are failures rather than silently repaired.

After dependency and driver preflights, the final cloud environment used PyTorch 2.6.0 with CUDA 11.8 and the fast Qwen2-VL image processor. A clean two-inference smoke test first verified that the model clicked the intended visible controls. The frozen 12-episode run then completed successfully:

- model loaded: yes;
- real model inference calls: 53;
- successful tasks: 3/12, all `delete_event`;
- failure attribution: 9 `agent_error` labels because the application was clean and known-good;
- preserved evidence: every screenshot, raw output, parsed action, latency, transition hash, and stop reason.

This learned baseline is intentionally separate from the 36-episode causal attribution benchmark: it supplies real agent trajectories without weakening the benchmark's controlled labels. See [`VLM_BASELINE.md`](VLM_BASELINE.md) and [`report/SHOWUI_RESULTS.md`](report/SHOWUI_RESULTS.md).

## Artifacts

Each episode contains:

```text
artifacts/episodes/<opaque_episode_id>/
  manifest.json
  gold.json
  steps.jsonl
  step_000.png ...
  probe/*.png
  diagnosis_terminal.json
  diagnosis_trajectory.json
  diagnosis_active.json
  diagnosis_oracle.json
  evaluation.json
```

Global outputs:

- `artifacts/registry.json`: atomic resume registry.
- `artifacts/freeze.json`: pre-test experiment freeze.
- `artifacts/test_access_log.jsonl`: explicit test access audit.
- `artifacts/predictions/<method>/*.json`: machine-readable predictions.
- `artifacts/tables/metrics.json`: source of every report metric.
- `artifacts/tables/attribution_summary.csv`: compact metric export.
- `artifacts/tables/demo_traces.json`: ranked interview traces.
- `artifacts/showui_full_summary.json`: aggregate and per-episode learned-baseline results.
- `artifacts/showui_full_run.tar.gz`: all 12 ShowUI trajectories, including 62 screenshots and 53 step records.
- `artifacts/paired_preregistration.json`: frozen balance, model revision, call cap, and config hashes for the 24-case paired run.
- `artifacts/paired_same_task_summary.json`: all learned-agent candidate/reference outcomes and predictions.
- `artifacts/paired_metrics.json` and `artifacts/paired_metrics.csv`: confusion matrices, intervals, paired comparison, runtime, and cost estimate.
- `artifacts/paired_same_task_run.tar.gz`: validated raw candidate/reference trajectories and quarantined causal gold.
- `artifacts/cost_ledger.csv`: cloud-job ledger with runtime-derived cost estimates; actual billing remains pending.
- `report/failure_gallery/index.html`: six visual counterfactual cases.
- `report/showui_results/trace_gallery.html`: four representative learned-agent traces with raw outputs.
- `report/paired_results/trace_gallery.html`: candidate/reference comparisons for an app regression, agent failure, ambiguous case, and the sole attribution error.

## Repository map

```text
app/                    Mini Calendar state, tasks, faults, server, browser UI
ui_faultlab/actions.py  strict normalized action schema
ui_faultlab/environment.py deterministic executor/snapshot/screenshot boundary
ui_faultlab/faults/     agent interceptors
ui_faultlab/agents/     scripted oracle and gated ShowUI adapter
ui_faultlab/diagnosis/  terminal, trajectory, active replay, oracle
ui_faultlab/evaluation/ metrics, Wilson intervals, paired statistics
ui_faultlab/artifacts/  manifest and atomic resume registry
scripts/                episode, experiment, model gate, gallery, report commands
tests/                  unit and integration acceptance checks
report/showui_results/  learned-baseline charts, trace gallery, summary, raw archive
report/paired_results/  differential-replay charts and candidate/reference gallery
```

## Budget and cloud safety

The operator approved a 600 RUB spend ceiling from a 684 RUB balance, preserving an 84 RUB reserve. The original 12-case ShowUI job ran for 719.132 seconds with a runtime-derived estimate of 33.66–46.74 RUB. The 24-case paired job ran for 1024.101 seconds with an estimate of 47.93–66.57 RUB. Including all setup, failed preflight, smoke, full-run, and paired-run rows, the conservative ledger total is 295.21 RUB—well below the approved ceiling. These are estimates, not confirmed charges; `actual_cost_rub` remains zero until provider billing is available.

Every paid job had a declared runtime cap, and the full runner checkpointed its summary and compressed trajectories after each episode. No additional cloud run is required to reproduce the report from the downloaded artifacts. Credentials and the cloud project ID are not committed.

## Demo

Open `report/paired_results/trace_gallery.html` for the primary learned-agent attribution demo, `report/failure_gallery/index.html` for the controlled mechanism cases, and `report/showui_results/trace_gallery.html` for the earlier clean action baseline. A 60–90 second pitch and personal verification checklist are in [`DEMO.md`](DEMO.md).
