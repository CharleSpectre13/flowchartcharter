"""Quantum-inspired path routing — |ψ⟩ superposition and Charter measurement M."""
from __future__ import annotations
import math
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class PathAmplitude:
    path: str
    amplitude: float  # c_i (unnormalized weight from muscle memory)
    probability: float  # |c_i|² / Z after normalization


@dataclass(frozen=True)
class SuperpositionState:
    """|ψ⟩ = Σ c_i |FlowUnit_i⟩"""
    amplitudes: Tuple[PathAmplitude, ...]
    entropy: float

    def dominant(self) -> PathAmplitude:
        return max(self.amplitudes, key=lambda a: a.probability)


def build_superposition(
    paths: Sequence[str],
    muscle_memory: Dict[str, float],
) -> SuperpositionState:
    """Construct |ψ⟩ from muscle-memory success weights (c_i)."""
    raw = [max(1e-9, float(muscle_memory.get(p, 1.0))) for p in paths]
    # Probability ∝ |c_i|² in pure quantum; here weights already encode success → use as |c|²
    total = sum(raw)
    amps: List[PathAmplitude] = []
    for p, w in zip(paths, raw):
        c = math.sqrt(w)  # recover amplitude scale
        amps.append(PathAmplitude(path=p, amplitude=c, probability=w / total))
    # Shannon entropy of path distribution (bits)
    ent = 0.0
    for a in amps:
        if a.probability > 0:
            ent -= a.probability * math.log2(a.probability)
    return SuperpositionState(amplitudes=tuple(amps), entropy=ent)


def measure(
    state: SuperpositionState,
    *,
    rng: Optional[random.Random] = None,
    deterministic: bool = False,
) -> Tuple[str, SuperpositionState]:
    """Charter measurement M: collapse |ψ⟩ → |ExecutedPath⟩ with 100% confidence post-measure.

    deterministic=True always picks max probability (default for enterprise charters).
    """
    r = rng or random
    if deterministic or not state.amplitudes:
        chosen = state.dominant().path if state.amplitudes else "path_A"
    else:
        paths = [a.path for a in state.amplitudes]
        weights = [a.probability for a in state.amplitudes]
        chosen = r.choices(paths, weights=weights, k=1)[0]
    # Post-measurement: collapsed pure state
    collapsed = SuperpositionState(
        amplitudes=(PathAmplitude(path=chosen, amplitude=1.0, probability=1.0),),
        entropy=0.0,
    )
    return chosen, collapsed


def quantum_path_select(
    paths: Sequence[str],
    muscle_memory: Dict[str, float],
    *,
    rng: Optional[random.Random] = None,
    deterministic: bool = True,
) -> Dict[str, object]:
    """Full pipeline: superposition → measurement → collapsed path."""
    psi = build_superposition(paths, muscle_memory)
    chosen, collapsed = measure(psi, rng=rng, deterministic=deterministic)
    return {
        "chosen_path": chosen,
        "pre_measurement": {
            "amplitudes": [
                {"path": a.path, "c": round(a.amplitude, 4), "p": round(a.probability, 4)}
                for a in psi.amplitudes
            ],
            "entropy": round(psi.entropy, 4),
        },
        "post_measurement": {
            "path": chosen,
            "confidence": 1.0,
            "entropy": 0.0,
        },
        "operator": "M = Charter @ RhythmMarker",
    }
