from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConstraintRule:
    name: str
    description: str