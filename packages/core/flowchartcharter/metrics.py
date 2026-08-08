from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionMetrics:
    token_cost: int
    execution_time: float
    quality_score: float
    synergy_score: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.quality_score <= 1.0:
            raise ValueError("quality_score must be in [0, 1]")
        if not 0.0 <= self.synergy_score <= 1.0:
            raise ValueError("synergy_score must be in [0, 1]")
        if self.token_cost < 0 or self.execution_time < 0:
            raise ValueError("cost and time must be non-negative")
