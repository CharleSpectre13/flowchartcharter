"""Rigorous synergy metric Q_s.

Q_s is highest when Agent A's output perfectly matches Agent B's expected
input schema without transformation / translation tokens.

    Q_s = exp(−k · D)

where D ∈ [0, 1] is structural divergence (schema error rate between hand-offs).
As D → 0, Q_s → 1. As D → 1, Q_s → exp(−k).
"""

from __future__ import annotations
import math
from typing import Any, Dict, Mapping, Optional, Sequence, Set, Tuple

DEFAULT_K = 3.0  # steeper decay → stricter hand-off contracts


def schema_keys(schema: Mapping[str, Any], prefix: str = "") -> Set[str]:
    """Flatten expected schema keys (supports nested dicts one level)."""
    keys: Set[str] = set()
    for k, v in schema.items():
        path = f"{prefix}.{k}" if prefix else str(k)
        keys.add(path)
        if isinstance(v, dict):
            keys |= schema_keys(v, path)
    return keys


def structural_divergence(
    agent_output: Mapping[str, Any],
    expected_schema: Mapping[str, Any],
    *,
    required: Optional[Sequence[str]] = None,
) -> float:
    """D ∈ [0, 1]: fraction of expected fields missing, wrong-type, or extra-critical.

    D = 0  → perfect contract match
    D = 1  → total schema failure
    """
    if not expected_schema and not required:
        return 0.0

    expected = set(required) if required else set(expected_schema.keys())
    if not expected:
        expected = schema_keys(expected_schema)
        # only top-level for scoring simplicity when nested
        expected = {k for k in expected if "." not in k} or set(expected_schema.keys())

    if not expected:
        return 0.0

    missing = 0
    type_mismatch = 0
    for key in expected:
        if key not in agent_output:
            missing += 1
            continue
        exp_val = expected_schema.get(key)
        got = agent_output.get(key)
        if exp_val is not None and got is not None and type(exp_val) is not type(got):
            # allow int/float cross
            if not (isinstance(exp_val, (int, float)) and isinstance(got, (int, float))):
                type_mismatch += 1

    errors = missing + type_mismatch
    d = errors / max(len(expected), 1)
    return max(0.0, min(1.0, d))


def synergy_score(
    agent_output: Mapping[str, Any],
    expected_schema: Mapping[str, Any],
    *,
    k: float = DEFAULT_K,
    required: Optional[Sequence[str]] = None,
) -> Tuple[float, float]:
    """Return (Q_s, D) where Q_s = exp(−k · D)."""
    d = structural_divergence(agent_output, expected_schema, required=required)
    qs = math.exp(-k * d)
    return qs, d


def handoff_synergy(
    upstream_output: Mapping[str, Any],
    downstream_schema: Mapping[str, Any],
    *,
    k: float = DEFAULT_K,
) -> Dict[str, Any]:
    """Full hand-off evaluation for Rhythm Marker gate."""
    qs, d = synergy_score(upstream_output, downstream_schema, k=k)
    compliant = d == 0.0  # 100% schema compliance
    return {
        "Q_s": round(qs, 6),
        "D": round(d, 6),
        "k": k,
        "formula": "Q_s = exp(-k * D)",
        "schema_compliant": compliant,
        "translation_tokens_needed": 0 if compliant else int(math.ceil(d * 50)),
    }


def mean_pair_synergy(
    qualities: Sequence[float],
    divergences: Optional[Sequence[float]] = None,
    *,
    k: float = DEFAULT_K,
) -> float:
    """Team-level synergy from sequential hand-off divergences (or quality proxy)."""
    if divergences:
        scores = [math.exp(-k * max(0.0, min(1.0, d))) for d in divergences]
        return sum(scores) / len(scores) if scores else 0.0
    if len(qualities) < 2:
        return float(qualities[0]) if qualities else 0.0
    # proxy: D ≈ 1 − geometric_mean(q_i, q_{i+1})
    scores = []
    for i in range(len(qualities) - 1):
        u = max(0.0, min(1.0, qualities[i]))
        dwn = max(0.0, min(1.0, qualities[i + 1]))
        d_proxy = 1.0 - math.sqrt(u * dwn)
        scores.append(math.exp(-k * d_proxy))
    return sum(scores) / len(scores)
