"""v1.7 Hybrid Boss Router — tri-state nervous system for GraphRAG absorption.

Routes every incoming workload to exactly one lane under CFO economics:

  SIMPLE      → pure Vector Retrieval (Qdrant / Muscle-Memory)
  MULTI_HOP   → MultiHopReasoner Flow Unit (graph walk + vector)
  GLOBAL      → temporary Synthesis Squad (lazy map-reduce)

FCC owns process, economics, and knowledge. GraphRAG is a sub-flow tool only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence


class RouteLane(str, Enum):
    """Tri-state routing decision for the Boss Agent GM."""

    SIMPLE = "simple"
    MULTI_HOP = "multi_hop"
    GLOBAL = "global"


# Global-theme cues (map-reduce / community sensemaking)
_GLOBAL_PATTERNS = (
    r"\bglobal\b",
    r"\btheme\b",
    r"\bacross (all|the|every)\b",
    r"\boverall\b",
    r"\bsummariz",
    r"\bsynthesis\b",
    r"\blandscape\b",
    r"\bholistic\b",
    r"\benterprise[- ]wide\b",
    r"\bmap[- ]reduce\b",
    r"\bcommunity report",
    r"\ball communities\b",
)

# Multi-hop factual reasoning cues
_MULTI_HOP_PATTERNS = (
    r"\bwhy\b",
    r"\bhow does\b",
    r"\bhow do\b",
    r"\brelationship\b",
    r"\bconnect(ed|ion)?\b",
    r"\bwho owns\b",
    r"\bwho reports\b",
    r"\bcaused by\b",
    r"\bleads to\b",
    r"\bdepends on\b",
    r"\bmulti[- ]hop\b",
    r"\btrace\b",
    r"\bpath from\b",
    r"\bbetween .+ and\b",
    r"\bchain\b",
)

# Simple lookup / single-entity retrieval cues
_SIMPLE_PATTERNS = (
    r"\bwhat is\b",
    r"\bdefine\b",
    r"\blookup\b",
    r"\bfetch\b",
    r"\bretrieve\b",
    r"\bshow me\b",
    r"\bget\b",
    r"\bfind entity\b",
)


def _count_hits(text: str, patterns: Sequence[str]) -> int:
    return sum(1 for p in patterns if re.search(p, text, re.IGNORECASE))


@dataclass
class RouteDecision:
    """Immutable GM routing verdict for a single workload."""

    lane: RouteLane
    confidence: float
    rationale: str
    estimated_token_budget: int
    signals: Dict[str, int] = field(default_factory=dict)
    workload_fingerprint: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lane": self.lane.value,
            "confidence": round(self.confidence, 4),
            "rationale": self.rationale,
            "estimated_token_budget": self.estimated_token_budget,
            "signals": dict(self.signals),
            "workload_fingerprint": self.workload_fingerprint,
        }


@dataclass
class HybridBossRouter:
    """Default nervous system for v1.7 Boss Agent routing.

    Heuristic classifier first; optional CFO ceiling clamps budgets before
    any GraphRAG sub-flow is spun up.
    """

    cfo_ceiling: int = 3500
    simple_budget: int = 180
    multi_hop_budget: int = 900
    global_budget: int = 2200
    history: List[RouteDecision] = field(default_factory=list)

    def classify(
        self,
        workload: str,
        *,
        hint: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> RouteDecision:
        """Classify workload into SIMPLE | MULTI_HOP | GLOBAL."""
        text = (workload or "").strip()
        meta = metadata or {}
        force = (hint or meta.get("route_hint") or "").strip().lower()

        if force in ("simple", "vector", "lookup"):
            return self._decide(
                RouteLane.SIMPLE,
                1.0,
                "explicit route_hint=simple",
                text,
            )
        if force in ("multi_hop", "multihop", "graph", "reason"):
            return self._decide(
                RouteLane.MULTI_HOP,
                1.0,
                "explicit route_hint=multi_hop",
                text,
            )
        if force in ("global", "synthesis", "theme"):
            return self._decide(
                RouteLane.GLOBAL,
                1.0,
                "explicit route_hint=global",
                text,
            )

        g = _count_hits(text, _GLOBAL_PATTERNS)
        m = _count_hits(text, _MULTI_HOP_PATTERNS)
        s = _count_hits(text, _SIMPLE_PATTERNS)
        # entity-pair or hop count hints from structured metadata
        hop_hint = int(meta.get("expected_hops") or 0)
        entity_count = int(meta.get("entity_count") or 0)
        if hop_hint >= 2 or entity_count >= 2:
            m += 2
        if meta.get("global_theme"):
            g += 2

        signals = {"global": g, "multi_hop": m, "simple": s}
        total = g + m + s

        if total == 0:
            # Default lean: pure vector — never open GraphRAG on silence
            return self._decide(
                RouteLane.SIMPLE,
                0.55,
                "no strong signals; default vector retrieval",
                text,
                signals,
            )

        if g >= m and g >= s and g > 0:
            conf = min(0.99, 0.55 + 0.12 * g)
            return self._decide(
                RouteLane.GLOBAL,
                conf,
                f"global/theme signals={g} dominate",
                text,
                signals,
            )
        if m > s:
            conf = min(0.99, 0.55 + 0.12 * m)
            return self._decide(
                RouteLane.MULTI_HOP,
                conf,
                f"multi-hop/relational signals={m} dominate",
                text,
                signals,
            )
        conf = min(0.99, 0.55 + 0.12 * s)
        return self._decide(
            RouteLane.SIMPLE,
            conf,
            f"simple lookup signals={s} dominate",
            text,
            signals,
        )

    def _decide(
        self,
        lane: RouteLane,
        confidence: float,
        rationale: str,
        text: str,
        signals: Optional[Dict[str, int]] = None,
    ) -> RouteDecision:
        budgets = {
            RouteLane.SIMPLE: self.simple_budget,
            RouteLane.MULTI_HOP: self.multi_hop_budget,
            RouteLane.GLOBAL: self.global_budget,
        }
        budget = min(budgets[lane], max(50, self.cfo_ceiling))
        fp = f"{lane.value}:{hash(text) & 0xFFFFFFFF:08x}"
        decision = RouteDecision(
            lane=lane,
            confidence=confidence,
            rationale=rationale,
            estimated_token_budget=budget,
            signals=signals or {},
            workload_fingerprint=fp,
        )
        self.history.append(decision)
        return decision

    def route_stats(self) -> Dict[str, Any]:
        counts = {lane.value: 0 for lane in RouteLane}
        for d in self.history:
            counts[d.lane.value] += 1
        return {
            "total": len(self.history),
            "by_lane": counts,
            "cfo_ceiling": self.cfo_ceiling,
        }
