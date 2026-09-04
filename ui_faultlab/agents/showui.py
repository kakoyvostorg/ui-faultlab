from __future__ import annotations

import ast
import importlib.util
import json
import time
from pathlib import Path

from ui_faultlab.actions import Action


MODEL_ID = "showlab/ShowUI-2B"
MODEL_REVISION = "cabec4fcc48d15ffd3efe0b33ea9bc7d41509d60"
MIN_PIXELS = 256 * 28 * 28
MAX_PIXELS = 1344 * 28 * 28

SHOWUI_NAV_PROMPT = """You are an assistant trained to navigate the web screen.
Given a task instruction, a screen observation, and an action history sequence,
output the next action and wait for the next observation.
Here is the action space:
1. `CLICK`: Click on an element; value is not applicable and position [x,y] is required.
2. `INPUT`: Type a string into an element; value is the string and position [x,y] is required.
3. `SELECT`: Select an element; value is not applicable and position [x,y] is required.
4. `HOVER`: Hover on an element; value is not applicable and position [x,y] is required.
5. `ANSWER`: Answer the question; value is the answer and position is not applicable.
6. `ENTER`: Press Enter; value and position are not applicable.
7. `SCROLL`: Scroll the screen; value is `up` or `down` and position is not applicable.

Format exactly one action as a dictionary with these keys:
{'action': 'ACTION_TYPE', 'value': 'element', 'position': [x,y]}
If value or position is not applicable, set it to None.
Position contains relative screenshot coordinates scaled to [0,1].
"""


class ShowUIOutputError(ValueError):
    pass


def parse_showui_action(raw_output: str) -> Action:
    """Strictly validate the model's documented Python-dictionary action format."""
    try:
        payload = ast.literal_eval(raw_output.strip())
    except (SyntaxError, ValueError) as error:
        raise ShowUIOutputError(str(error)) from error
    if not isinstance(payload, dict):
        raise ShowUIOutputError("model output must be one dictionary")
    if set(payload) != {"action", "value", "position"}:
        raise ShowUIOutputError("model output must contain exactly action, value, and position")

    kind = payload["action"]
    value = payload["value"]
    position = payload["position"]
    if not isinstance(kind, str):
        raise ShowUIOutputError("action must be a string")
    kind = kind.upper()

    def point() -> tuple[float, float]:
        if not isinstance(position, (list, tuple)) or len(position) != 2:
            raise ShowUIOutputError(f"{kind} requires one [x,y] position")
        x, y = position
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            raise ShowUIOutputError("position coordinates must be numeric")
        return float(x), float(y)

    if kind in {"CLICK", "SELECT"}:
        if value is not None:
            raise ShowUIOutputError(f"{kind} value must be None")
        return Action("tap", *point(), reason=f"ShowUI {kind}").validate()
    if kind == "INPUT":
        if not isinstance(value, str):
            raise ShowUIOutputError("INPUT value must be a string")
        return Action("input", *point(), text=value, reason="ShowUI INPUT").validate()
    if kind == "SCROLL":
        if position is not None or value not in {"up", "down"}:
            raise ShowUIOutputError("SCROLL requires value up/down and position None")
        return Action("scroll", direction=value, reason="ShowUI SCROLL").validate()
    if kind == "ENTER":
        if value is not None or position is not None:
            raise ShowUIOutputError("ENTER requires value and position None")
        return Action("enter", reason="ShowUI ENTER").validate()
    if kind == "ANSWER" and isinstance(value, str) and position is None and any(
        token in value.lower() for token in ("complete", "completed", "done", "success")
    ):
        return Action("finish", reason=value).validate()
    raise ShowUIOutputError(f"unsupported ShowUI action: {kind}")


def dependency_preflight() -> dict:
    required = ("torch", "torchvision", "transformers", "accelerate", "PIL", "qwen_vl_utils")
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

        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA was requested but is not available")
        self.torch = torch
        self.device = device
        if device == "cuda":
            dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        else:
            dtype = torch.float32
        self.processor = AutoProcessor.from_pretrained(
            MODEL_ID, revision=MODEL_REVISION, min_pixels=MIN_PIXELS,
            max_pixels=MAX_PIXELS,
        )
        self.model = Qwen2VLForConditionalGeneration.from_pretrained(
            MODEL_ID,
            revision=MODEL_REVISION,
            dtype=dtype,
            device_map="auto",
        )
        self.model.eval()

    def raw_action(self, screenshot_path: str | Path, instruction: str, history: list[dict]) -> tuple[str, float]:
        from qwen_vl_utils import process_vision_info

        content = [
            {"type": "text", "text": SHOWUI_NAV_PROMPT},
            {"type": "text", "text": "Task: " + instruction},
        ]
        if history:
            rendered_history = "\n".join(str(action) for action in history[-4:])
            content.append({"type": "text", "text": "Action history:\n" + rendered_history})
        content.append({"type": "image", "image": str(screenshot_path), "min_pixels": MIN_PIXELS, "max_pixels": MAX_PIXELS})
        messages = [{"role": "user", "content": content}]
        prompt = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        images, videos = process_vision_info(messages)
        inputs = self.processor(text=[prompt], images=images, videos=videos, padding=True, return_tensors="pt").to(self.device)
        start = time.perf_counter()
        with self.torch.inference_mode():
            generated = self.model.generate(**inputs, max_new_tokens=128, do_sample=False)
        latency = (time.perf_counter() - start) * 1000
        trimmed = [out[len(source):] for source, out in zip(inputs.input_ids, generated, strict=True)]
        return self.processor.batch_decode(trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0], latency

    def action(self, screenshot_path: str | Path, instruction: str, history: list[dict]):
        raw, latency = self.raw_action(screenshot_path, instruction, history)
        return parse_showui_action(raw), raw, latency
