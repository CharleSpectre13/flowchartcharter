from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class FlowUnit:
    id: str
    name: str
    rhythm_marker: str
    exit_threshold: float = 0.90
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CharterState:
    version: int = 0
    snapshot: Dict[str, Any] = field(default_factory=dict)
    quality_score: float = 0.0
    trust_signal: bool = False
    remediation_loops: int = 0
    max_remediation: int = 3


@dataclass
class Charter:
    name: str
    units: List[FlowUnit]
    state: CharterState = field(default_factory=CharterState)
    version: str = "0.1.0"

    def bump(self) -> None:
        self.state.version += 1
