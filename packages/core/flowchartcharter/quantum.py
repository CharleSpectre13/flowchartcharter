"""Tensor-Based Routing Engine — quantum-inspired path routing with production upgrades.

Mathematical model:

    |ψ⟩ = Σᵢ cᵢ |FlowUnitᵢ⟩
    |ExecutedPath⟩ = M |ψ⟩     # M = Charter @ Rhythm Marker

Enhancements (Advanced System Blueprint):
  A. Contextual State Entropy H_ctx — messy data collapses toward cleansing units
  B. Synergy Q_s = exp(−k·D) — see synergy.py
  C. CFO Token Economics Override — budget constraint matrix before measurement
"""
from __future__ import annotations
import math
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


# Default playbook paths
PATH_STANDARD = "path_A"       # standard execution
PATH_CLEANSING = "path_B"      # data-cleansing (high H_ctx)
PATH_LITE = "path_lite"        # CFO forced simplified / cheap
DEFAULT_PATHS = (PATH_STANDARD, PATH_CLEANSING, PATH_LITE)

# Affinity of each path to high context entropy (0 = prefer clean, 1 = prefer messy)
PATH_ENTROPY_AFFINITY: Dict[str, float] = {
    PATH_STANDARD: 0.15,
    PATH_CLEANSING: 0.95,
    PATH_LITE: 0.40,
}

# Default historical token cost estimates per path (CFO matrix)
DEFAULT_PATH_COSTS: Dict[str, float] = {
    PATH_STANDARD: 220.0,
    PATH_CLEANSING: 380.0,
    PATH_LITE: 90.0,
}


# ── Data types ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PathAmplitude:
    path: str
    amplitude: float
    probability: float
    success_weight: float


@dataclass(frozen=True)
class SuperpositionState:
    """|ψ⟩ = Σ cᵢ |FlowUnitᵢ⟩"""
    amplitudes: Tuple[PathAmplitude, ...]
    entropy: float
    context_entropy: float = 0.0
    normalized: bool = True
    cfo_override: bool = False
    blocked_paths: Tuple[str, ...] = ()

    def dominant(self) -> PathAmplitude:
        if not self.amplitudes:
            return PathAmplitude(PATH_STANDARD, 1.0, 1.0, 1.0)
        return max(self.amplitudes, key=lambda a: a.probability)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "amplitudes": [
                {
                    "path": a.path,
                    "c": round(a.amplitude, 6),
                    "p": round(a.probability, 6),
                    "weight": round(a.success_weight, 6),
                }
                for a in self.amplitudes
            ],
            "entropy": round(self.entropy, 6),
            "context_entropy": round(self.context_entropy, 6),
            "dominant": self.dominant().path if self.amplitudes else None,
            "cfo_override": self.cfo_override,
            "blocked_paths": list(self.blocked_paths),
        }


@dataclass
class MeasurementRecord:
    charter_id: str
    agent: str
    marker: str
    chosen_path: str
    pre: SuperpositionState
    post: SuperpositionState
    confidence: float = 1.0
    quality_outcome: Optional[float] = None
    context_entropy: float = 0.0
    cfo_forced: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "charter_id": self.charter_id,
            "agent": self.agent,
            "marker": self.marker,
            "chosen_path": self.chosen_path,
            "confidence": self.confidence,
            "quality_outcome": self.quality_outcome,
            "context_entropy": round(self.context_entropy, 4),
            "cfo_forced": self.cfo_forced,
            "pre_measurement": self.pre.to_dict(),
            "post_measurement": self.post.to_dict(),
            "operator": "M = Charter @ RhythmMarker",
        }


# ── Pure functions ───────────────────────────────────────────────────────────

def shannon_entropy(probs: Sequence[float]) -> float:
    ent = 0.0
    for p in probs:
        if p > 1e-15:
            ent -= p * math.log2(p)
    return ent


def contextual_entropy(
    payload: Optional[Mapping[str, Any]] = None,
    *,
    features: Optional[Sequence[float]] = None,
    explicit: Optional[float] = None,
) -> float:
    """H_ctx ∈ [0, 1] — uncertainty of the current data payload.

    Higher when:
      - missing fields ratio high
      - noise / variance high
      - feature distribution near-uniform (max entropy)
    """
    if explicit is not None:
        return max(0.0, min(1.0, float(explicit)))

    if features:
        vals = [float(x) for x in features]
        if not vals:
            return 0.0
        # normalize to simplex-ish bins
        s = sum(abs(v) for v in vals) or 1.0
        probs = [abs(v) / s for v in vals]
        h = shannon_entropy(probs)
        h_max = math.log2(len(probs)) if len(probs) > 1 else 1.0
        return max(0.0, min(1.0, h / h_max if h_max else 0.0))

    if not payload:
        return 0.0

    noise = float(payload.get("noise", payload.get("uncertainty", 0.0)))
    missing = float(payload.get("missing_ratio", 0.0))
    variance = float(payload.get("variance", 0.0))
    raw = 0.45 * max(0.0, min(1.0, noise)) + 0.35 * max(0.0, min(1.0, missing)) + 0.20 * max(0.0, min(1.0, variance))
    return max(0.0, min(1.0, raw))


def entropy_affinity_weight(path: str, h_ctx: float) -> float:
    """Boost paths aligned with current context entropy.

    High H_ctx → boost cleansing path; low H_ctx → boost standard path.
    """
    affinity = PATH_ENTROPY_AFFINITY.get(path, 0.5)
    # weight multiplier ∈ [0.4, 2.0]
    # when h_ctx high and affinity high → boost; when mismatch → dampen
    match = 1.0 - abs(affinity - h_ctx)
    return 0.4 + 1.6 * match


def apply_cfo_budget_matrix(
    weights: Dict[str, float],
    path_costs: Mapping[str, float],
    *,
    remaining_budget: float,
    margin: float,
    force_lite_path: str = PATH_LITE,
) -> Tuple[Dict[str, float], List[str], bool]:
    """CFO hard interrupt before Measurement.

    If a Flow Unit's historical token cost exceeds current margin,
    zero its amplitude. If all expensive paths blocked, force path_lite.
    """
    blocked: List[str] = []
    adjusted = dict(weights)
    affordable_margin = max(0.0, remaining_budget - margin)

    for path, cost in path_costs.items():
        if path not in adjusted:
            continue
        if cost > affordable_margin and remaining_budget < cost:
            adjusted[path] = 0.0
            blocked.append(path)

    # If nothing left with weight, force lite
    forced = False
    if sum(adjusted.values()) <= 1e-12:
        adjusted = {p: (1.0 if p == force_lite_path else 0.0) for p in adjusted}
        if force_lite_path not in adjusted:
            adjusted[force_lite_path] = 1.0
        forced = True
        if force_lite_path not in blocked:
            pass  # lite is the escape hatch
    elif all(adjusted.get(p, 0) <= 1e-12 for p in adjusted if p != force_lite_path):
        # only lite remains
        forced = force_lite_path in adjusted

    return adjusted, blocked, forced


def build_superposition(
    paths: Sequence[str],
    muscle_memory: Dict[str, float],
    *,
    floor: float = 1e-9,
    context_entropy: float = 0.0,
    path_costs: Optional[Mapping[str, float]] = None,
    remaining_budget: Optional[float] = None,
    margin: float = 0.0,
) -> SuperpositionState:
    """Construct |ψ⟩ from muscle-memory × contextual entropy affinity × CFO matrix.

    Convention: muscle_memory[path] stores |c|²-proportional success weight.
    Contextual boost: weight *= entropy_affinity_weight(path, H_ctx)
    CFO: zero weights that exceed budget margin before normalization.
    """
    if not paths:
        paths = DEFAULT_PATHS

    raw_map: Dict[str, float] = {}
    for p in paths:
        base = max(floor, float(muscle_memory.get(p, 1.0)))
        raw_map[p] = base * entropy_affinity_weight(p, context_entropy)

    blocked: List[str] = []
    cfo_override = False
    if path_costs is not None and remaining_budget is not None:
        raw_map, blocked, cfo_override = apply_cfo_budget_matrix(
            raw_map,
            path_costs,
            remaining_budget=remaining_budget,
            margin=margin,
        )

    # drop zero-weight paths for normalization but keep lite if forced
    active = {p: w for p, w in raw_map.items() if w > floor}
    if not active:
        active = {PATH_LITE: 1.0}
        cfo_override = True

    total = sum(active.values())
    amps: List[PathAmplitude] = []
    probs: List[float] = []
    for p, w in active.items():
        c = math.sqrt(w)
        pr = w / total
        amps.append(PathAmplitude(path=p, amplitude=c, probability=pr, success_weight=w))
        probs.append(pr)

    return SuperpositionState(
        amplitudes=tuple(amps),
        entropy=shannon_entropy(probs),
        context_entropy=context_entropy,
        normalized=True,
        cfo_override=cfo_override,
        blocked_paths=tuple(blocked),
    )


def measure(
    state: SuperpositionState,
    *,
    rng: Optional[random.Random] = None,
    deterministic: bool = True,
    temperature: float = 1.0,
) -> Tuple[str, SuperpositionState]:
    """Charter measurement M: collapse |ψ⟩ → |ExecutedPath⟩ (confidence 1.0)."""
    if not state.amplitudes:
        pure = SuperpositionState(
            amplitudes=(PathAmplitude(PATH_STANDARD, 1.0, 1.0, 1.0),),
            entropy=0.0,
            context_entropy=state.context_entropy,
            cfo_override=state.cfo_override,
        )
        return PATH_STANDARD, pure

    r = rng or random
    if deterministic or temperature <= 0:
        chosen = state.dominant().path
    else:
        logits = [math.log(max(a.probability, 1e-15)) / max(temperature, 1e-6) for a in state.amplitudes]
        m = max(logits)
        exps = [math.exp(x - m) for x in logits]
        z = sum(exps)
        weights = [e / z for e in exps]
        chosen = r.choices([a.path for a in state.amplitudes], weights=weights, k=1)[0]

    collapsed = SuperpositionState(
        amplitudes=(PathAmplitude(path=chosen, amplitude=1.0, probability=1.0, success_weight=1.0),),
        entropy=0.0,
        context_entropy=state.context_entropy,
        cfo_override=state.cfo_override,
        blocked_paths=state.blocked_paths,
    )
    return chosen, collapsed


def reinforce(
    muscle_memory: Dict[str, float],
    path: str,
    *,
    quality: float,
    quality_floor: float = 0.90,
    lr: float = 0.12,
    decay: float = 0.02,
    min_weight: float = 0.05,
    max_weight: float = 8.0,
) -> Dict[str, float]:
    """Update muscle-memory amplitudes after quality outcome."""
    updated = dict(muscle_memory)
    updated.setdefault(path, 1.0)
    for p in list(updated.keys()):
        updated[p] = max(min_weight, float(updated[p]))

    if quality >= quality_floor:
        updated[path] = min(max_weight, updated[path] * (1.0 + lr * quality))
        for p in updated:
            if p != path:
                updated[p] = max(min_weight, updated[p] * (1.0 - decay))
    else:
        penalty = lr * (quality_floor - quality + 0.1)
        updated[path] = max(min_weight, updated[path] * (1.0 - penalty))
        boost = decay * 2
        for p in updated:
            if p != path:
                updated[p] = min(max_weight, updated[p] * (1.0 + boost))
    return updated


def entanglement_score(
    upstream_quality: float,
    downstream_quality: float,
    contract_match: float = 1.0,
) -> float:
    """Legacy geometric-mean synergy (prefer synergy.synergy_score for schema D)."""
    u = max(0.0, min(1.0, upstream_quality))
    d = max(0.0, min(1.0, downstream_quality))
    c = max(0.0, min(1.0, contract_match))
    return math.sqrt(u * d) * c


# ── QuantumRouter ────────────────────────────────────────────────────────────

class QuantumRouter:
    """Stateful tensor-based path router with H_ctx + CFO override."""

    DEFAULT_PATHS = DEFAULT_PATHS

    def __init__(
        self,
        *,
        paths: Sequence[str] = DEFAULT_PATHS,
        deterministic: bool = True,
        temperature: float = 1.0,
        rng: Optional[random.Random] = None,
        quality_floor: float = 0.90,
        lr: float = 0.12,
        path_costs: Optional[Dict[str, float]] = None,
    ):
        self.paths = tuple(paths) if paths else self.DEFAULT_PATHS
        self.deterministic = deterministic
        self.temperature = temperature
        self.rng = rng or random.Random()
        self.quality_floor = quality_floor
        self.lr = lr
        self.path_costs = dict(path_costs or DEFAULT_PATH_COSTS)
        self.history: List[MeasurementRecord] = []
        self._pending: Dict[str, MeasurementRecord] = {}

    def prepare(
        self,
        agent_name: str,
        muscle_memory: Dict[str, float],
        *,
        context_entropy: float = 0.0,
        remaining_budget: Optional[float] = None,
        margin: float = 0.0,
    ) -> SuperpositionState:
        return build_superposition(
            self.paths,
            muscle_memory,
            context_entropy=context_entropy,
            path_costs=self.path_costs,
            remaining_budget=remaining_budget,
            margin=margin,
        )

    def collapse(
        self,
        *,
        charter_id: str,
        agent_name: str,
        muscle_memory: Dict[str, float],
        marker: str = "gate",
        context_entropy: float = 0.0,
        remaining_budget: Optional[float] = None,
        margin: float = 0.0,
        path_costs: Optional[Mapping[str, float]] = None,
    ) -> MeasurementRecord:
        """Measure at Rhythm Marker with optional CFO budget gate."""
        costs = path_costs if path_costs is not None else self.path_costs
        pre = build_superposition(
            self.paths,
            muscle_memory,
            context_entropy=context_entropy,
            path_costs=costs,
            remaining_budget=remaining_budget,
            margin=margin,
        )
        chosen, post = measure(
            pre,
            rng=self.rng,
            deterministic=self.deterministic,
            temperature=self.temperature,
        )
        rec = MeasurementRecord(
            charter_id=charter_id,
            agent=agent_name,
            marker=marker,
            chosen_path=chosen,
            pre=pre,
            post=post,
            confidence=1.0,
            context_entropy=context_entropy,
            cfo_forced=pre.cfo_override,
        )
        self.history.append(rec)
        self._pending[agent_name] = rec
        return rec

    def observe(
        self,
        agent_name: str,
        muscle_memory: Dict[str, float],
        quality: float,
    ) -> Dict[str, float]:
        rec = self._pending.pop(agent_name, None)
        path = rec.chosen_path if rec else self.paths[0]
        if rec is not None:
            rec.quality_outcome = quality
        return reinforce(
            muscle_memory,
            path,
            quality=quality,
            quality_floor=self.quality_floor,
            lr=self.lr,
        )

    def route_agent(
        self,
        *,
        charter_id: str,
        agent_name: str,
        muscle_memory: Dict[str, float],
        marker: str = "superstep",
        context_entropy: float = 0.0,
        path_costs: Optional[Mapping[str, float]] = None,
        remaining_budget: Optional[float] = None,
        margin: Optional[float] = None,
    ) -> Dict[str, Any]:
        rec = self.collapse(
            charter_id=charter_id,
            agent_name=agent_name,
            muscle_memory=muscle_memory,
            marker=marker,
            context_entropy=context_entropy,
            remaining_budget=remaining_budget,
            margin=margin or 0.0,
            path_costs=path_costs,
        )
        return {
            "chosen_path": rec.chosen_path,
            "pre_measurement": rec.pre.to_dict(),
            "post_measurement": {
                "path": rec.chosen_path,
                "confidence": rec.confidence,
                "entropy": 0.0,
            },
            "operator": "M = Charter @ RhythmMarker",
            "agent": agent_name,
            "marker": marker,
            "context_entropy": rec.context_entropy,
            "cfo_forced": rec.cfo_forced,
            "blocked_paths": list(rec.pre.blocked_paths),
        }

    def team_entanglement(self, qualities: Sequence[float]) -> float:
        if len(qualities) < 2:
            return float(qualities[0]) if qualities else 0.0
        scores = [
            entanglement_score(qualities[i], qualities[i + 1])
            for i in range(len(qualities) - 1)
        ]
        return sum(scores) / len(scores)

    def summary(self) -> Dict[str, Any]:
        collapses = len(self.history)
        if not collapses:
            return {"collapses": 0, "mean_pre_entropy": 0.0, "mean_h_ctx": 0.0, "paths": {}, "cfo_forced": 0}
        mean_ent = sum(r.pre.entropy for r in self.history) / collapses
        mean_h = sum(r.context_entropy for r in self.history) / collapses
        path_counts: Dict[str, int] = {}
        cfo_n = 0
        for r in self.history:
            path_counts[r.chosen_path] = path_counts.get(r.chosen_path, 0) + 1
            if r.cfo_forced:
                cfo_n += 1
        return {
            "collapses": collapses,
            "mean_pre_entropy": round(mean_ent, 4),
            "mean_h_ctx": round(mean_h, 4),
            "paths": path_counts,
            "cfo_forced": cfo_n,
            "records": [r.to_dict() for r in self.history[-12:]],
        }


def quantum_path_select(
    paths: Sequence[str],
    muscle_memory: Dict[str, float],
    *,
    rng: Optional[random.Random] = None,
    deterministic: bool = True,
    temperature: float = 1.0,
    agent: str = "agent",
    charter_id: str = "charter",
    marker: str = "gate",
    context_entropy: float = 0.0,
    remaining_budget: Optional[float] = None,
    path_costs: Optional[Mapping[str, float]] = None,
) -> Dict[str, object]:
    """Stateless convenience pipeline."""
    router = QuantumRouter(
        paths=paths,
        deterministic=deterministic,
        temperature=temperature,
        rng=rng,
        path_costs=dict(path_costs) if path_costs else None,
    )
    return router.route_agent(
        charter_id=charter_id,
        agent_name=agent,
        muscle_memory=muscle_memory,
        marker=marker,
        context_entropy=context_entropy,
        remaining_budget=remaining_budget,
        path_costs=path_costs,
    )
