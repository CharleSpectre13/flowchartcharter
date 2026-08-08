"""Quantum-inspired path routing — |ψ⟩ superposition and Charter measurement M.

Mathematical model (from FlowChartCharter Architectural Spec):

    |ψ⟩ = Σᵢ cᵢ |FlowUnitᵢ⟩
    |ExecutedPath⟩ = M |ψ⟩     # M = Charter @ Rhythm Marker

cᵢ are probability amplitudes derived from Muscle-Memory historical success weights.
Post-measurement confidence is always 1.0 (pure collapsed state).
"""
from __future__ import annotations
import math
import random
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Sequence, Tuple


# ── Data types ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PathAmplitude:
    """Single basis component cᵢ |path⟩."""
    path: str
    amplitude: float       # cᵢ  (real; success-encoded)
    probability: float     # |cᵢ|² / Z
    success_weight: float  # raw muscle-memory weight before sqrt


@dataclass(frozen=True)
class SuperpositionState:
    """|ψ⟩ = Σ cᵢ |FlowUnitᵢ⟩"""
    amplitudes: Tuple[PathAmplitude, ...]
    entropy: float  # Shannon entropy in bits
    normalized: bool = True

    def dominant(self) -> PathAmplitude:
        if not self.amplitudes:
            return PathAmplitude("path_A", 1.0, 1.0, 1.0)
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
            "dominant": self.dominant().path if self.amplitudes else None,
        }


@dataclass
class MeasurementRecord:
    """One collapse event at a Rhythm Marker."""
    charter_id: str
    agent: str
    marker: str
    chosen_path: str
    pre: SuperpositionState
    post: SuperpositionState
    confidence: float = 1.0
    quality_outcome: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "charter_id": self.charter_id,
            "agent": self.agent,
            "marker": self.marker,
            "chosen_path": self.chosen_path,
            "confidence": self.confidence,
            "quality_outcome": self.quality_outcome,
            "pre_measurement": self.pre.to_dict(),
            "post_measurement": self.post.to_dict(),
            "operator": "M = Charter @ RhythmMarker",
        }


# ── Core pure functions ──────────────────────────────────────────────────────

def shannon_entropy(probs: Sequence[float]) -> float:
    ent = 0.0
    for p in probs:
        if p > 1e-15:
            ent -= p * math.log2(p)
    return ent


def build_superposition(
    paths: Sequence[str],
    muscle_memory: Dict[str, float],
    *,
    floor: float = 1e-9,
) -> SuperpositionState:
    """Construct |ψ⟩ from muscle-memory success weights.

    Convention: muscle_memory[path] stores |c|²-proportional success weight.
    Amplitude c = √w; probability p = w / Σw.
    """
    if not paths:
        paths = ("path_A",)
    raw = [max(floor, float(muscle_memory.get(p, 1.0))) for p in paths]
    total = sum(raw)
    amps: List[PathAmplitude] = []
    probs: List[float] = []
    for p, w in zip(paths, raw):
        c = math.sqrt(w)
        pr = w / total
        amps.append(PathAmplitude(path=p, amplitude=c, probability=pr, success_weight=w))
        probs.append(pr)
    return SuperpositionState(
        amplitudes=tuple(amps),
        entropy=shannon_entropy(probs),
        normalized=True,
    )


def measure(
    state: SuperpositionState,
    *,
    rng: Optional[random.Random] = None,
    deterministic: bool = True,
    temperature: float = 1.0,
) -> Tuple[str, SuperpositionState]:
    """Charter measurement M: collapse |ψ⟩ → |ExecutedPath⟩.

    deterministic=True (enterprise default): pick argmax probability → 100% confident.
    deterministic=False: sample from |c|² with optional temperature soft-max.
    Post-measurement state is always pure (entropy = 0, confidence = 1).
    """
    if not state.amplitudes:
        pure = SuperpositionState(
            amplitudes=(PathAmplitude("path_A", 1.0, 1.0, 1.0),),
            entropy=0.0,
        )
        return "path_A", pure

    r = rng or random
    if deterministic or temperature <= 0:
        chosen = state.dominant().path
    else:
        # Softmax over log-prob / temperature for exploration during training
        logits = [math.log(max(a.probability, 1e-15)) / max(temperature, 1e-6) for a in state.amplitudes]
        m = max(logits)
        exps = [math.exp(x - m) for x in logits]
        z = sum(exps)
        weights = [e / z for e in exps]
        chosen = r.choices([a.path for a in state.amplitudes], weights=weights, k=1)[0]

    collapsed = SuperpositionState(
        amplitudes=(PathAmplitude(path=chosen, amplitude=1.0, probability=1.0, success_weight=1.0),),
        entropy=0.0,
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
    """Update muscle-memory amplitudes after outcome (learning step).

    Success (quality ≥ floor): boost chosen path, slight decay on alternatives.
    Failure: penalize chosen path, mild boost on alternatives (exploration).
    """
    updated = dict(muscle_memory)
    # Ensure path exists
    updated.setdefault(path, 1.0)
    for p in list(updated.keys()):
        updated[p] = max(min_weight, float(updated[p]))

    if quality >= quality_floor:
        updated[path] = min(max_weight, updated[path] * (1.0 + lr * quality))
        for p in updated:
            if p != path:
                updated[p] = max(min_weight, updated[p] * (1.0 - decay))
    else:
        # Failure: reduce chosen, rediscover alternatives
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
    """Q_entanglement: how seamlessly one agent's output feeds the next.

    Geometric mean of qualities × contract_match ∈ [0, 1].
    """
    u = max(0.0, min(1.0, upstream_quality))
    d = max(0.0, min(1.0, downstream_quality))
    c = max(0.0, min(1.0, contract_match))
    return math.sqrt(u * d) * c


# ── QuantumRouter (stateful engine) ──────────────────────────────────────────

class QuantumRouter:
    """Stateful quantum path router for a charter run.

    Lifecycle:
      1. prepare(agent)  → build |ψ⟩ from muscle memory
      2. collapse(...)   → M|ψ⟩ at Rhythm Marker → chosen path
      3. observe(...)    → reinforce amplitudes from quality outcome
      4. team_entanglement(...) → synergy across sequential agents
    """

    DEFAULT_PATHS = ("path_A", "path_B")

    def __init__(
        self,
        *,
        paths: Sequence[str] = DEFAULT_PATHS,
        deterministic: bool = True,
        temperature: float = 1.0,
        rng: Optional[random.Random] = None,
        quality_floor: float = 0.90,
        lr: float = 0.12,
    ):
        self.paths = tuple(paths) if paths else self.DEFAULT_PATHS
        self.deterministic = deterministic
        self.temperature = temperature
        self.rng = rng or random.Random()
        self.quality_floor = quality_floor
        self.lr = lr
        self.history: List[MeasurementRecord] = []
        self._pending: Dict[str, MeasurementRecord] = {}

    def prepare(self, agent_name: str, muscle_memory: Dict[str, float]) -> SuperpositionState:
        """Build |ψ⟩ for an agent without collapsing."""
        return build_superposition(self.paths, muscle_memory)

    def collapse(
        self,
        *,
        charter_id: str,
        agent_name: str,
        muscle_memory: Dict[str, float],
        marker: str = "gate",
    ) -> MeasurementRecord:
        """Measure at Rhythm Marker: |ψ⟩ → |ExecutedPath⟩."""
        pre = build_superposition(self.paths, muscle_memory)
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
        """Feed quality outcome back into muscle-memory amplitudes."""
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
    ) -> Dict[str, Any]:
        """One-shot: collapse + return selection dict (compat with quantum_path_select)."""
        rec = self.collapse(
            charter_id=charter_id,
            agent_name=agent_name,
            muscle_memory=muscle_memory,
            marker=marker,
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
        }

    def team_entanglement(self, qualities: Sequence[float]) -> float:
        """Mean pairwise entanglement across sequential agent qualities."""
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
            return {"collapses": 0, "mean_pre_entropy": 0.0, "paths": {}}
        mean_ent = sum(r.pre.entropy for r in self.history) / collapses
        path_counts: Dict[str, int] = {}
        for r in self.history:
            path_counts[r.chosen_path] = path_counts.get(r.chosen_path, 0) + 1
        return {
            "collapses": collapses,
            "mean_pre_entropy": round(mean_ent, 4),
            "paths": path_counts,
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
) -> Dict[str, object]:
    """Stateless convenience: superposition → measurement → collapsed path dict."""
    router = QuantumRouter(
        paths=paths,
        deterministic=deterministic,
        temperature=temperature,
        rng=rng,
    )
    return router.route_agent(
        charter_id=charter_id,
        agent_name=agent,
        muscle_memory=muscle_memory,
        marker=marker,
    )
