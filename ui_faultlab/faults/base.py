from __future__ import annotations

from dataclasses import dataclass

from ui_faultlab.actions import Action


@dataclass(frozen=True)
class InjectionResult:
    intended: Action
    executed: Action
    injected: bool

