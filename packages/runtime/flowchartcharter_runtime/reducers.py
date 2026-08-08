from __future__ import annotations
from typing import Any, Dict, List


def channel_add(left: List[Any], right: List[Any]) -> List[Any]:
    return list(left) + list(right)


def channel_override(left: Any, right: Any) -> Any:
    return right if right is not None else left


def merge_snapshots(base: Dict[str, Any], updates: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Deterministic merge: sort keys of each update, apply in order."""
    out = dict(base)
    for upd in updates:
        for k in sorted(upd.keys()):
            v = upd[k]
            if isinstance(v, list) and isinstance(out.get(k), list):
                out[k] = channel_add(out[k], v)
            else:
                out[k] = channel_override(out.get(k), v)
    return out
