# Open VLM baseline

UI-FaultLab uses [`showlab/ShowUI-2B`](https://huggingface.co/showlab/ShowUI-2B), pinned to revision `cabec4fcc48d15ffd3efe0b33ea9bc7d41509d60`, as its learned visual-action baseline.

The adapter follows the official ShowUI navigation contract:

- one Python-style action dictionary per turn;
- relative `[x, y]` coordinates in `[0, 1]`, origin at the screenshot's top-left;
- official `CLICK`, `INPUT`, `SCROLL`, `ENTER`, and `ANSWER` mappings;
- official pixel preprocessing bounds;
- strict parsing with no output repair.

The final cloud environment used PyTorch 2.6.0 with CUDA 11.8 and the fast Qwen2-VL image processor. Before the full run, a two-inference clean-UI smoke test produced two valid, correctly targeted clicks: opening the create flow and opening the delete target.

## Closed-loop result

The frozen run contains 12 clean episodes: four tasks across deterministic dev, validation, and test seeds. ShowUI received only the task instruction, current screenshot, and the last four raw actions. It made 53 real inference calls.

| task | success | observed behavior |
|---|---:|---|
| `create_event` | 0/3 | found the create flow, then emitted multiple actions in one turn; strict parsing rejected the output |
| `add_attendee` | 0/3 | opened the correct event, but entered the email into the title field |
| `reschedule_event` | 0/3 | opened the correct event, but entered the new time into the date field |
| `delete_event` | 3/3 | completed card → Delete → Confirm in three valid clicks |

Overall success was **3/12 = 25.0%** (Wilson 95% CI 8.9%–53.2%). Because the application was known-good and no application or agent fault injector was enabled, the nine failed tasks are labeled `agent_error`. Successful tasks have no failure label.

This result is deliberately separate from the 36-episode controlled attribution benchmark. It replaces invented examples of agent behavior with observed trajectories, but does not turn the small synthetic run into a general GUI-agent benchmark.

## Preserved evidence

- [`report/SHOWUI_RESULTS.md`](report/SHOWUI_RESULTS.md): metrics, plots, failure analysis, and limitations.
- [`report/showui_results/trace_gallery.html`](report/showui_results/trace_gallery.html): one full visual trajectory per task with raw model outputs.
- [`artifacts/showui_full_summary.json`](artifacts/showui_full_summary.json): machine-readable aggregate and per-episode results.
- [`artifacts/showui_full_run.tar.gz`](artifacts/showui_full_run.tar.gz): all 12 trajectories, 62 screenshots, 53 step records, manifests, and evaluations.
- [`artifacts/model_smoke_result.json`](artifacts/model_smoke_result.json): the final two-call clean-UI smoke result.
- [`artifacts/cost_ledger.csv`](artifacts/cost_ledger.csv): setup, preflight, smoke, and full-job accounting.

The full job ran for 719.132 seconds. Its runtime-derived GPU estimate is 33.66–46.74 RUB; the conservative estimate across every cloud ledger row is 228.64 RUB. Provider billing was still pending when these artifacts were assembled, so neither number is reported as an actual charge.

Official references:

- [ShowUI model card and weights](https://huggingface.co/showlab/ShowUI-2B)
- [ShowUI checkpoint commit history](https://huggingface.co/showlab/ShowUI-2B/commits/main)
- [ShowUI official quick start](https://github.com/showlab/ShowUI/blob/main/QUICK_START.md)
- [ShowUI paper](https://openaccess.thecvf.com/content/CVPR2025/papers/Lin_ShowUI_One_Vision-Language-Action_Model_for_GUI_Visual_Agent_CVPR_2025_paper.pdf)
