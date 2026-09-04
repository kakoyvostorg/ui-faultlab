from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


ALLOWED_TYPES = {"tap", "input", "type", "scroll", "enter", "back", "finish"}


@dataclass(frozen=True)
class Action:
    type: str
    x: float | None = None
    y: float | None = None
    text: str | None = None
    direction: str | None = None
    reason: str | None = None

    def validate(self) -> "Action":
        if self.type not in ALLOWED_TYPES:
            raise ValueError(f"unsupported action type: {self.type}")
        if self.type == "tap":
            if self.x is None or self.y is None:
                raise ValueError("tap requires x and y")
            if not (0.0 <= self.x <= 1.0 and 0.0 <= self.y <= 1.0):
                raise ValueError("tap coordinates must be normalized to [0, 1]")
            if any(v is not None for v in (self.text, self.direction)):
                raise ValueError("tap is incompatible with text/direction")
        elif self.type == "input":
            if self.x is None or self.y is None or self.text is None:
                raise ValueError("input requires x, y, and text")
            if not (0.0 <= self.x <= 1.0 and 0.0 <= self.y <= 1.0):
                raise ValueError("input coordinates must be normalized to [0, 1]")
            if self.direction is not None:
                raise ValueError("input is incompatible with direction")
        elif self.type == "type":
            if self.text is None:
                raise ValueError("type requires text")
            if any(v is not None for v in (self.x, self.y, self.direction)):
                raise ValueError("type is incompatible with coordinates/direction")
        elif self.type == "scroll":
            if self.direction not in {"up", "down"}:
                raise ValueError("scroll direction must be up or down")
            if any(v is not None for v in (self.x, self.y, self.text)):
                raise ValueError("scroll is incompatible with coordinates/text")
        else:
            if any(v is not None for v in (self.x, self.y, self.text, self.direction)):
                raise ValueError(f"{self.type} takes no action fields")
        return self

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Action":
        allowed = {"type", "x", "y", "text", "direction", "reason"}
        extra = set(payload) - allowed
        if extra:
            raise ValueError(f"unexpected action fields: {sorted(extra)}")
        return cls(**payload).validate()


def normalized_to_pixels(x: float, y: float, width: int, height: int) -> tuple[int, int]:
    if not (0 <= x <= 1 and 0 <= y <= 1):
        raise ValueError("coordinates outside [0, 1]")
    if width <= 0 or height <= 0:
        raise ValueError("viewport must be positive")
    return min(width - 1, round(x * (width - 1))), min(height - 1, round(y * (height - 1)))
