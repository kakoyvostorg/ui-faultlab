# UI-FaultLab Experimental Report

Generated automatically from machine-readable episode artifacts. No result below was copied by hand.

## Scope and protocol

- Episodes: **36** (agent_fault=12, application_fault=12, clean=12).
- Splits: dev=12, test=12, validation=12.
- Attribution denominator: **24 failed episodes**; clean successes are excluded from attribution scores.
- Actor: scripted oracle (`builtin-v1`) for controlled environment validation, **not a learned research baseline**.
- Diagnosers: deterministic terminal-only, passive-trajectory, and one-probe active replay; oracle is a privileged upper bound.
- Primary metric fixed before test access: application-bug precision.

## Results

| method | application-bug precision | application-bug recall | macro-F1 | accuracy | false bug report rate | abstention |
|---|---:|---:|---:|---:|---:|---:|
| terminal | 12/24 (50.0%) | 12/12 (100.0%) | 22.2% | 12/24 (50.0%) | 12/12 (100.0%) | 0.0% |
| trajectory | 12/16 (75.0%) | 12/12 (100.0%) | 55.2% | 20/24 (83.3%) | 4/12 (33.3%) | 0.0% |
| active | 12/12 (100.0%) | 12/12 (100.0%) | 66.7% | 24/24 (100.0%) | 0/12 (0.0%) | 0.0% |
| oracle | 12/12 (100.0%) | 12/12 (100.0%) | 66.7% | 24/24 (100.0%) | 0/12 (0.0%) | 0.0% |

Primary result: active replay application-bug precision was **12/12 = 100.0%**, Wilson 95% CI [75.8%, 100.0%]. Its false bug report rate was **0/12 = 0.0%**, Wilson 95% CI [0.0%, 24.2%].

Terminal-to-active paired accuracy difference was **+50.0 pp**, episode bootstrap 95% CI [29.2%, 70.8%]. McNemar had 12 discordant pairs (exact two-sided p=0.0005); this remains a small synthetic study.

## Task execution and cost

- Clean task success: 12/12 = 100.0%, Wilson 95% CI [75.8%, 100.0%].
- Faulted task success: 0/24 = 0.0%.
- Mean steps per episode: 5.75; invalid action rate: 0.0%; parse failure rate: 0.0%.
- Active probes: 24 total, 0.67 per episode overall; hard cap was one per failed episode.
- Controlled-benchmark VLM calls: 0; GPU wall-clock: 0.0s; estimated spend: **0.00 RUB**.
- Mean local episode execution latency: 65.8 ms; mean active-probe latency: 7.5 ms.

## Learned-agent companion

A separate clean, known-good ShowUI-2B run made **53 real VLM calls** across 12 episodes. It completed **3/12 = 25.0%** tasks, Wilson 95% CI [8.9%, 53.2%]. Failed tasks are labeled `agent_error` because no application fault or agent-fault injector was active.

| task | successes | rate | VLM calls | stop reasons |
|---|---:|---:|---:|---|
| `add_attendee` | 0/3 | 0.0% | 18 | max_steps=1, no_change_loop=2 |
| `create_event` | 0/3 | 0.0% | 8 | parse_error=3 |
| `delete_event` | 3/3 | 100.0% | 9 | task_success=3 |
| `reschedule_event` | 0/3 | 0.0% | 18 | max_steps=1, no_change_loop=2 |

This companion run supplies observed learned-agent trajectories; it does not replace the controlled attribution denominator above. See [`SHOWUI_RESULTS.md`](SHOWUI_RESULTS.md) for plots, raw-output analysis, and the visual trace gallery.

## Learned-agent paired attribution

A subsequent frozen experiment ran ShowUI-2B on 24 candidate tasks and replayed every parsed action unchanged on a known-good reference. The candidate failed on 21 tasks. Blind differential replay correctly attributed 20/21 failures (95.2%; Wilson 95% CI 77.3%–99.2%), identified all 3 causally decisive application regressions, and made 0/18 false application-bug reports across the remaining failures.

Seven predictions abstained as `ambiguous`. This is material rather than cosmetic: in those cases an injected application fault was reached, but the same action sequence also failed on the reference, so the experiment could not isolate a unique cause. See [`PAIRED_RESULTS.md`](PAIRED_RESULTS.md) for the confusion matrix, paired comparator, gallery, runtime, and limitations.


## Failure gallery

The generated [failure gallery](failure_gallery/index.html) contains 6 cases with pre/post/probe screenshots and all three predictions. Recommended demo traces are listed in `artifacts/tables/demo_traces.json`.

## Interpretation

Within this controlled synthetic calendar, terminal-only diagnosis over-reported application bugs because a failed final screen cannot reveal whether the requested interaction was actually executed. Passive history recovered visible no-op divergences but missed some semantically wrong targets. A single replay of the intended action separated all represented clean agent faults from application transition faults in this experiment. This is an operational prototype result, not evidence of generalization to arbitrary applications.

## Limitations

- The controlled actor and three principal diagnosers are deterministic, model-free baselines. The ShowUI companion is a learned actor baseline, not a learned attribution method.
- The later paired study does use a learned actor for attribution, but contains only 21 failed cases and 3 decisive application regressions on one synthetic application.
- Screenshots come from a deterministic renderer synchronized with the same UI transition model as the local web app; browser-pixel parity still requires Playwright/Node on the demo machine.
- The application, tasks, and faults are synthetic, with one fault family per episode and three state seeds.
- Confidence intervals quantify binomial uncertainty in this small fixture set; episodes share templates and are not independent real-world products.
- Active replay restores an internal snapshot through the environment service, while its attribution decision receives only the replay screenshot/hash—not backend state or the gold label.
