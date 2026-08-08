from __future__ import annotations
from typing import Any, Callable, Dict, List
from .reducers import merge_snapshots


class SuperStepEngine:
    """BSP-style barrier: run workers, then deterministic reduce."""

    def __init__(self) -> None:
        self.step = 0

    def run(
        self,
        state: Dict[str, Any],
        workers: List[Callable[[Dict[str, Any]], Dict[str, Any]]],
    ) -> Dict[str, Any]:
        local_updates: List[Dict[str, Any]] = []
        for w in workers:
            local_updates.append(w(dict(state)))
        merged = merge_snapshots(state, local_updates)
        self.step += 1
        merged["_superstep"] = self.step
        return merged
