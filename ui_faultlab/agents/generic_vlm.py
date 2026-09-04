from __future__ import annotations

import json

from ui_faultlab.actions import Action


class StrictOutputError(ValueError):
    pass


def parse_action_json(raw_output: str) -> Action:
    """Parse once, without silently repairing syntax or semantic fields."""
    try:
        payload = json.loads(raw_output)
    except json.JSONDecodeError as error:
        raise StrictOutputError(str(error)) from error
    if not isinstance(payload, dict):
        raise StrictOutputError("model output must be one JSON object")
    try:
        return Action.from_dict(payload)
    except (TypeError, ValueError) as error:
        raise StrictOutputError(str(error)) from error


ACTION_PROMPT = """You operate a calendar from screenshots only. Return exactly one JSON object and no prose.
Allowed schemas:
{"type":"tap","x":0.0,"y":0.0,"reason":"short reason"}
{"type":"type","text":"value","reason":"short reason"}
{"type":"scroll","direction":"up|down","reason":"short reason"}
{"type":"back","reason":"short reason"}
{"type":"finish","reason":"short reason"}
Coordinates are relative [x,y] values normalized to [0,1] from the screenshot's top-left.
"""

