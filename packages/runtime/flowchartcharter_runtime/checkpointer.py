from __future__ import annotations
from typing import Any, Dict, List, Optional


class MemoryCheckpointer:
    def __init__(self) -> None:
        self._thread: Dict[str, List[Dict[str, Any]]] = {}

    def put(self, thread_id: str, snapshot: Dict[str, Any]) -> None:
        self._thread.setdefault(thread_id, []).append(dict(snapshot))

    def latest(self, thread_id: str) -> Optional[Dict[str, Any]]:
        hist = self._thread.get(thread_id) or []
        return dict(hist[-1]) if hist else None

    def history(self, thread_id: str) -> List[Dict[str, Any]]:
        return list(self._thread.get(thread_id, []))
