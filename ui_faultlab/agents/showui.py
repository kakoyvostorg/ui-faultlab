from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path

from ui_faultlab.agents.generic_vlm import ACTION_PROMPT, parse_action_json


MODEL_ID = "showlab/ShowUI-2B"
MODEL_REVISION = "cabec4fcc48d15ffd3efe0b33ea9bc7d41509d60"
MIN_PIXELS = 256 * 28 * 28
MAX_PIXELS = 1344 * 28 * 28


def dependency_preflight() -> dict:
    required = ("torch", "transformers", "PIL", "qwen_vl_utils")
    availability = {name: bool(importlib.util.find_spec(name)) for name in required}
    return {"dependencies": availability, "ready": all(availability.values())}


class ShowUIAgent:
    name = "showui_2b"
    revision = MODEL_REVISION

    def __init__(self, device: str = "cuda"):
        preflight = dependency_preflight()
        if not preflight["ready"]:
            missing = [k for k, value in preflight["dependencies"].items() if not value]
            raise RuntimeError(f"ShowUI runtime dependencies missing: {', '.join(missing)}")
        import torch
        from transformers import AutoProcessor, Qwen2VLForConditionalGeneration

        self.torch = torch
        self.device = device
        self.processor = AutoProcessor.from_pretrained(MODEL_ID, revision=MODEL_REVISION, min_pixels=MIN_PIXELS, max_pixels=MAX_PIXELS)
        self.model = Qwen2VLForConditionalGeneration.from_pretrained(MODEL_ID, revision=MODEL_REVISION, torch_dtype=torch.bfloat16, device_map="auto")

    def raw_action(self, screenshot_path: str | Path, instruction: str, history: list[dict]) -> tuple[str, float]:
        from qwen_vl_utils import process_vision_info

        messages = [{"role": "user", "content": [
            {"type": "text", "text": ACTION_PROMPT + "\nTask: " + instruction + "\nHistory: " + json.dumps(history[-4:])},
            {"type": "image", "image": str(screenshot_path), "min_pixels": MIN_PIXELS, "max_pixels": MAX_PIXELS},
        ]}]
        prompt = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        images, videos = process_vision_info(messages)
        inputs = self.processor(text=[prompt], images=images, videos=videos, padding=True, return_tensors="pt").to(self.device)
        start = time.perf_counter()
        generated = self.model.generate(**inputs, max_new_tokens=128)
        latency = (time.perf_counter() - start) * 1000
        trimmed = [out[len(source):] for source, out in zip(inputs.input_ids, generated, strict=True)]
        return self.processor.batch_decode(trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0], latency

    def action(self, screenshot_path: str | Path, instruction: str, history: list[dict]):
        raw, latency = self.raw_action(screenshot_path, instruction, history)
        return parse_action_json(raw), raw, latency

