"""Muscle-Memory Vector DB — structured execution trajectories (not raw text RAG).

Blueprint quadrants per record:
  1. State Embedding   (state_vector)     — payload characteristics
  2. Contextual Action (flow_path)        — verified Flow Unit sequence
  3. Synergy Fingerprint (entanglement)   — Q_entanglement of the run
  4. Cheat Code        (prompt_tweak)     — historical prompt/format insight

GraphRAG: unstructured graph → chunks → reason from scratch → high cost/latency
Muscle-Memory: execution vectors → deterministic playbook → execute immediately
"""

from __future__ import annotations

import json
import math
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

# =============================================================================
# SCHEMA
# =============================================================================


@dataclass
class ExecutionMemoryRecord:
    """One successful execution trajectory stored for cheat-sheet retrieval."""

    memory_id: str
    job_type: str
    state_vector: List[float]
    successful_flow_path: List[str]
    entanglement_score: float
    prompt_tweak: str = ""
    quality: float = 0.95
    token_cost: int = 0
    tags: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.memory_id:
            self.memory_id = f"MEM-{uuid.uuid4().hex[:8].upper()}"
        if not 0.0 <= self.entanglement_score <= 1.0:
            raise ValueError("entanglement_score must be in [0, 1]")
        if not 0.0 <= self.quality <= 1.0:
            raise ValueError("quality must be in [0, 1]")
        if self.token_cost < 0:
            raise ValueError("token_cost must be non-negative")
        # normalize vector to list[float]
        self.state_vector = [float(x) for x in self.state_vector]
        self.successful_flow_path = [str(p) for p in self.successful_flow_path]

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["tags"] = list(self.tags)
        return d

    def cosine(self, other: Sequence[float]) -> float:
        return cosine_similarity(self.state_vector, other)


def cosine_similarity(v1: Sequence[float], v2: Sequence[float]) -> float:
    """Vector alignment for identical or near-identical past jobs."""
    if not v1 or not v2:
        return 0.0
    n = min(len(v1), len(v2))
    a = [float(x) for x in v1[:n]]
    b = [float(x) for x in v2[:n]]
    dot = sum(x * y for x, y in zip(a, b))
    mag1 = math.sqrt(sum(x * x for x in a))
    mag2 = math.sqrt(sum(x * x for x in b))
    if mag1 == 0.0 or mag2 == 0.0:
        return 0.0
    return max(-1.0, min(1.0, dot / (mag1 * mag2)))


def encode_state(data_payload: Mapping[str, Any]) -> List[float]:
    """Encode workload payload → state vector.

    Features:
      [0] entropy_level            — charset diversity / length
      [1] payload_size_kb          — serialized size
      [2] schema_complexity_score  — top-level key count
      [3] historical_error_weight  — optional prior error signal
    """
    text_content = json.dumps(data_payload, sort_keys=True, default=str)
    entropy = len(set(text_content)) / max(1, len(text_content))
    size_kb = len(text_content) / 1024.0
    complexity = float(len(data_payload.keys())) if data_payload else 0.0
    err_weight = float(data_payload.get("_error_weight", 0.1))
    return [entropy, size_kb, complexity, err_weight]


# =============================================================================
# VECTOR DATABASE
# =============================================================================


@dataclass
class MuscleMemoryVectorDB:
    """High-speed repository of verified execution trajectories.

    Replaces open-graph RAG under charter pressure: retrieve a proven
    Flow Unit sequence + prompt tweak instead of re-reasoning from chunks.
    """

    storage: List[ExecutionMemoryRecord] = field(default_factory=list)
    quiet: bool = True
    hits: int = 0
    misses: int = 0

    def __post_init__(self) -> None:
        if not self.quiet:
            print("[Muscle-Memory DB] Initialized high-speed vector " "memory repository.")

    def encode_state(self, data_payload: Mapping[str, Any]) -> List[float]:
        return encode_state(data_payload)

    def cosine_similarity(self, v1: Sequence[float], v2: Sequence[float]) -> float:
        return cosine_similarity(v1, v2)

    def commit_memory(self, record: ExecutionMemoryRecord) -> None:
        """Commit a successful job trajectory (live run or Monday Sync)."""
        if record.quality < 0.90 and record.entanglement_score < 0.85:
            return  # only store trustworthy trajectories
        self.storage.append(record)
        if not self.quiet:
            print(
                f"[Muscle-Memory] Committed trajectory [{record.memory_id}] "
                f"for job type: {record.job_type}"
            )

    def query_muscle_memory(
        self,
        current_payload: Mapping[str, Any],
        similarity_threshold: float = 0.85,
        *,
        state_vector: Optional[Sequence[float]] = None,
    ) -> Optional[ExecutionMemoryRecord]:
        """Find near-identical past job; return cheat sheet or None (charter fallback)."""
        current_vector = (
            list(state_vector) if state_vector is not None else self.encode_state(current_payload)
        )
        if not self.storage:
            self.misses += 1
            if not self.quiet:
                print(
                    "[Muscle-Memory MISS] Empty store. " "Falling back to standard Charter pathing."
                )
            return None

        best_match: Optional[ExecutionMemoryRecord] = None
        highest_score = -float("inf")

        for record in self.storage:
            score = self.cosine_similarity(current_vector, record.state_vector)
            if score > highest_score:
                highest_score = score
                best_match = record

        if best_match is not None and highest_score >= similarity_threshold:
            self.hits += 1
            if not self.quiet:
                print(
                    f"[Muscle-Memory HIT!] similarity={highest_score:.3f} "
                    f"path={best_match.successful_flow_path}"
                )
            return best_match

        self.misses += 1
        if not self.quiet:
            print(
                f"[Muscle-Memory MISS] similarity={highest_score:.3f} "
                f"below threshold={similarity_threshold}. "
                "Falling back to standard Charter pathing."
            )
        return None

    def query_top_k(
        self,
        current_payload: Mapping[str, Any],
        *,
        threshold: float = 0.70,
        top_k: int = 3,
        state_vector: Optional[Sequence[float]] = None,
    ) -> List[Dict[str, Any]]:
        """Multi-hit query for skill / system integration."""
        current_vector = (
            list(state_vector) if state_vector is not None else self.encode_state(current_payload)
        )
        scored: List[Tuple[float, ExecutionMemoryRecord]] = []
        for record in self.storage:
            sim = self.cosine_similarity(current_vector, record.state_vector)
            if sim >= threshold:
                scored.append((sim, record))
        scored.sort(key=lambda x: x[0], reverse=True)
        out: List[Dict[str, Any]] = []
        for sim, rec in scored[:top_k]:
            out.append(
                {
                    "memory_id": rec.memory_id,
                    "job_type": rec.job_type,
                    "similarity": round(sim, 4),
                    "successful_flow_path": list(rec.successful_flow_path),
                    "entanglement_score": rec.entanglement_score,
                    "prompt_tweak": rec.prompt_tweak,
                    "quality": rec.quality,
                    "token_cost": rec.token_cost,
                    "tags": list(rec.tags),
                }
            )
        return out

    def stats(self) -> Dict[str, Any]:
        total = self.hits + self.misses
        return {
            "records": len(self.storage),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / total, 4) if total else 0.0,
        }

    def export_dict(self) -> Dict[str, Any]:
        return {
            "records": [r.to_dict() for r in self.storage],
            "stats": self.stats(),
        }


def seed_legacy_refactor(db: MuscleMemoryVectorDB) -> ExecutionMemoryRecord:
    """Seed MEM-9921 from the architectural reference simulation."""
    record = ExecutionMemoryRecord(
        memory_id="MEM-9921",
        job_type="Legacy Code Refactor",
        state_vector=[0.45, 12.5, 4.0, 0.1],
        successful_flow_path=[
            "U1_Ingest",
            "U4_TypeSanitize",
            "U8_DeterministicRefactor",
        ],
        entanglement_score=0.98,
        prompt_tweak=("Ensure strict camelCase enforcement during token parsing."),
        quality=0.98,
        token_cost=420,
        tags=("legacy", "refactor"),
    )
    db.commit_memory(record)
    return record


def run_muscle_memory_simulation(*, quiet: bool = False) -> Dict[str, Any]:
    """Reference simulation: seed → query near-match → accelerated path."""
    db = MuscleMemoryVectorDB(quiet=quiet)
    seed_legacy_refactor(db)

    # Near-identical vector to force a HIT under threshold 0.70
    incoming_workload = {
        "task": "Legacy Code Refactor",
        "codebase_snippet": "function test() { var x = 1; }",
        "metadata": {"source": "legacy_repo"},
    }

    # Also query with the exact seeded vector for guaranteed HIT demo
    exact = db.query_muscle_memory(
        incoming_workload,
        similarity_threshold=0.70,
        state_vector=[0.45, 12.5, 4.0, 0.1],
    )

    encoded = db.encode_state(incoming_workload)
    encoded_match = db.query_muscle_memory(
        incoming_workload,
        similarity_threshold=0.50,
    )

    return {
        "exact_hit": exact is not None,
        "exact_path": list(exact.successful_flow_path) if exact else None,
        "exact_tweak": exact.prompt_tweak if exact else None,
        "encoded_vector": encoded,
        "encoded_hit": encoded_match is not None,
        "stats": db.stats(),
        "records": len(db.storage),
    }
