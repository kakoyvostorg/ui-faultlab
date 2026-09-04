# Open VLM baseline gate

Checked on 2026-09-03 against the official sources:

- Primary checkpoint: [`showlab/ShowUI-2B`](https://huggingface.co/showlab/ShowUI-2B), pinned to revision `cabec4fcc48d15ffd3efe0b33ea9bc7d41509d60` (latest commit shown by the official commit history at check time).
- Weights/model-card license: MIT. The upstream ShowUI code repository carries Apache-2.0; these are recorded separately rather than conflated.
- Architecture: Qwen2-VL 2B family. Official quick start uses `Qwen2VLForConditionalGeneration` and `AutoProcessor`.
- Official preprocessing: `min_pixels = 256 * 28 * 28`, `max_pixels = 1344 * 28 * 28`.
- Coordinate contract: relative `[x, y]`, origin at the screenshot top-left, each coordinate scaled to `[0, 1]`. UI-FaultLab already uses that convention.
- Official checkpoint size shown by the model repository: approximately 4.43 GB before runtime overhead.

Primary preflight stopped before download/model load because this host has none of `torch`, `transformers`, Pillow, or `qwen_vl_utils`, and no CUDA GPU was detected. The one documented fallback candidate, Qwen2.5-VL 3B Instruct, is blocked by the same missing runtime. Per the stop rule, no model churn or unmonitored multi-gigabyte download was attempted.

This is a failed model gate, not a baseline result. `artifacts/model_smoke_result.json` and `artifacts/model_smoke_fallback_result.json` record zero inference calls, zero paid spend, and the exact blocker. A real model result must not be claimed until model load plus exactly two sequential screenshot inferences succeed.

Official references:

- [ShowUI model card and weights](https://huggingface.co/showlab/ShowUI-2B)
- [ShowUI checkpoint commit history](https://huggingface.co/showlab/ShowUI-2B/commits/main)
- [ShowUI official quick start](https://github.com/showlab/ShowUI/blob/main/QUICK_START.md)
- [ShowUI paper](https://openaccess.thecvf.com/content/CVPR2025/papers/Lin_ShowUI_One_Vision-Language-Action_Model_for_GUI_Visual_Agent_CVPR_2025_paper.pdf)

