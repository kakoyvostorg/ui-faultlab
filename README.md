# UI-FaultLab

UI-FaultLab is a compact executable prototype for a specific GUI-agent reliability question:

> When a visual UI test fails, can trajectory-conditioned replay distinguish an agent mistake from an application defect more reliably than a final-screenshot judgment?

The repository contains a deterministic Mini Calendar, screenshot-only observations, three agent faults, three application faults, resumable artifact logging, execution-based evaluation, terminal/passive/active attribution, a 36-episode paired experiment, confidence intervals, and a six-case visual failure gallery.

This is a controlled synthetic study inspired by GUI-agent reliability work. It is not a production tester, a general benchmark, or a state-of-the-art claim.

## Current result

The frozen experiment has 36 episodes: 4 tasks × 3 state seeds × clean/agent-fault/application-fault. All report values are rebuilt from `artifacts/episodes/*/evaluation.json`.

| diagnosis | app-bug precision | app-bug recall | accuracy | false bug report rate |
|---|---:|---:|---:|---:|
| terminal-only | 12/24 = 50.0% | 12/12 = 100.0% | 12/24 = 50.0% | 12/12 = 100.0% |
| passive trajectory | 12/16 = 75.0% | 12/12 = 100.0% | 20/24 = 83.3% | 4/12 = 33.3% |
| one-probe active replay | 12/12 = 100.0% | 12/12 = 100.0% | 24/24 = 100.0% | 0/12 = 0.0% |

For the primary active app-bug precision, the Wilson 95% interval is 75.8%–100.0%. The result is exact for these fixtures but small, template-correlated, and synthetic. See [`report/REPORT.md`](report/REPORT.md) for denominators, intervals, paired bootstrap, McNemar, cost, and limitations.

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

Actions use a validated normalized schema: `tap(x,y)`, `type(text)`, `scroll(direction)`, `back`, and `finish`. Coordinates are `[x,y]` in `[0,1]`, measured from the screenshot's top-left. Reset state, event ordering, task text, and screenshot rendering are deterministic for a given seed.

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

The current three principal diagnosers are deterministic and model-free. This cleanly tests the environment and causal replay mechanism, but it is not evidence about VLM reasoning quality.

## Open VLM gate

The preferred ShowUI 2B checkpoint was checked against official sources and pinned to `cabec4fcc48d15ffd3efe0b33ea9bc7d41509d60`. Its official contract matches normalized `[x,y]` coordinates; official preprocessing constants are encoded in `ui_faultlab/agents/showui.py`.

The local model gate stopped before checkpoint download: this host lacks PyTorch, Transformers, Pillow, `qwen_vl_utils`, and CUDA. One pre-declared Qwen2.5-VL fallback was blocked by the same runtime. Therefore:

- model loaded: no;
- real model inference calls: 0;
- VLM claims in the report: none;
- paid compute: 0 RUB;
- model churn: stopped after the primary plus one fallback preflight.

See [`VLM_BASELINE.md`](VLM_BASELINE.md) and the two `artifacts/model_smoke*_result.json` files. Do not relabel the scripted actor as a VLM baseline.

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
- `artifacts/cost_ledger.csv`: paid-compute ledger; currently 0 RUB.
- `report/failure_gallery/index.html`: six visual counterfactual cases.

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
```

## Budget and cloud safety

No DataSphere job was launched. The current workspace has no DataSphere CLI, project ID, or credential environment, so current price, remaining balance, and active jobs could not be queried. The job templates are disabled placeholders.

Before any paid launch, the operator must verify the exact project, authentication, current hourly price, and remaining balance; calculate `floor((700 RUB - 100 RUB reserve) / hourly_rate)`; append the forecast to `artifacts/cost_ledger.csv`; run one job only; and stop after exactly two model inferences. Never commit credentials.

## Demo

Open `report/failure_gallery/index.html`, then use the three ranked cases in `artifacts/tables/demo_traces.json`. A 60–90 second pitch and personal verification checklist are in [`DEMO.md`](DEMO.md).

