"""v1.7 MultiHopReasoner Flow Unit — schema-locked multi-hop factual reasoning.

Treats multi-hop GraphRAG-style reasoning as a rigid corporate process:
  - Every hop must pass HopSchema (entity, relation, evidence, confidence)
  - Hallucinated edges → entanglement_error (Monday firing eligible)
  - Successful trajectories cached in Muscle-Memory (0 LLM tokens on replay)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence

from pydantic import BaseModel, Field, ValidationError, field_validator

from .knowledge_graph import KnowledgeGraph
from .muscle_memory import (
    ExecutionMemoryRecord,
    MuscleMemoryVectorDB,
    encode_state,
)


class HopSchema(BaseModel):
    """Strict intermediate hop contract — any violation is entanglement."""

    entity: str = Field(..., min_length=1, max_length=200)
    relation: str = Field(..., min_length=1, max_length=120)
    evidence: str = Field(..., min_length=1, max_length=2000)
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    hop_index: int = Field(..., ge=0, le=32)
    source_id: str = Field(default="", max_length=120)

    @field_validator("entity", "relation", "evidence")
    @classmethod
    def non_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("field must be non-empty after strip")
        return v


class MultiHopResultSchema(BaseModel):
    """Final MultiHopReasoner output envelope for Boss handoff."""

    answer: str = Field(..., min_length=1, max_length=8000)
    hops: List[HopSchema] = Field(default_factory=list)
    path_entities: List[str] = Field(default_factory=list)
    quality: float = Field(..., ge=0.0, le=1.0)
    tokens: int = Field(..., ge=0)
    muscle_memory_hit: bool = False
    entanglement_errors: int = Field(default=0, ge=0)
    trajectory_id: str = ""


@dataclass
class HopExecution:
    """Internal hop attempt record."""

    hop: Optional[HopSchema]
    valid: bool
    errors: List[str] = field(default_factory=list)
    entanglement_delta: int = 0


@dataclass
class MultiHopReasoner:
    """Rigid multi-hop factual reasoner bound by TPC fear + muscle memory.

    Graph walk uses KnowledgeGraph (local expansion). Vector assist uses
    MuscleMemoryVectorDB for trajectory replay. No open-ended free reasoning.
    """

    kg: Optional[KnowledgeGraph] = None
    muscle: Optional[MuscleMemoryVectorDB] = None
    max_hops: int = 4
    min_hop_confidence: float = 0.55
    token_budget: int = 900
    quiet: bool = True
    entanglement_errors: int = 0
    trajectories_cached: int = 0

    def __post_init__(self) -> None:
        if self.kg is None:
            self.kg = KnowledgeGraph()
        if self.muscle is None:
            self.muscle = MuscleMemoryVectorDB(quiet=True)

    def reason(
        self,
        query: str,
        *,
        seed_entity: Optional[str] = None,
        token_budget: Optional[int] = None,
    ) -> MultiHopResultSchema:
        """Execute multi-hop reasoning with schema gates + memory replay."""
        budget = int(token_budget or self.token_budget)
        payload = {
            "job_type": "multi_hop_reason",
            "query": query,
            "seed": seed_entity or "",
        }

        # 1) Muscle-memory trajectory hit → 0 LLM path tokens
        mem = self.muscle.query_muscle_memory(
            payload,
            similarity_threshold=0.82,
            state_vector=encode_state(payload),
        )
        if mem is not None and mem.successful_flow_path:
            return self._from_memory(query, mem, budget)

        # 2) Graph walk with schema-locked hops
        seed = seed_entity or self._infer_seed(query)
        local = self.kg.local_search(seed, hops=min(self.max_hops, 3))
        entity_index = {n["id"]: n for n in local.get("nodes", [])}
        # also index full graph for edge endpoints
        for e in self.kg.data.get("entities", []):
            entity_index.setdefault(e["id"], e)

        hops: List[HopSchema] = []
        path_entities: List[str] = []
        ent_errors = 0
        tokens_spent = 0

        if seed and seed in entity_index:
            node = entity_index[seed]
            hop0 = self._validate_hop(
                {
                    "entity": node["title"],
                    "relation": "seed",
                    "evidence": node.get("description", node["title"])[:500],
                    "confidence_score": 0.95,
                    "hop_index": 0,
                    "source_id": node["id"],
                }
            )
            if hop0.valid and hop0.hop:
                hops.append(hop0.hop)
                path_entities.append(node["id"])
                tokens_spent += 40
            else:
                ent_errors += hop0.entanglement_delta

        for edge in local.get("edges", [])[: self.max_hops]:
            if tokens_spent >= budget:
                break
            src = entity_index.get(edge["src"], {})
            dst = entity_index.get(edge["dst"], {})
            conf = float(edge.get("strength", 0.8))
            if conf < self.min_hop_confidence:
                ent_errors += 1
                self.entanglement_errors += 1
                continue
            hop_payload = {
                "entity": dst.get("title") or edge["dst"],
                "relation": edge.get("type", "related"),
                "evidence": edge.get("description")
                or (
                    f"{src.get('title', edge['src'])} → "
                    f"{dst.get('title', edge['dst'])}"
                ),
                "confidence_score": conf,
                "hop_index": len(hops),
                "source_id": edge.get("dst", ""),
            }
            result = self._validate_hop(hop_payload)
            tokens_spent += 55
            if not result.valid or result.hop is None:
                ent_errors += result.entanglement_delta
                self.entanglement_errors += result.entanglement_delta
                continue
            hops.append(result.hop)
            path_entities.append(result.hop.source_id or result.hop.entity)

        answer = self._synthesize_answer(query, hops, local)
        quality = self._score_quality(hops, ent_errors)
        trajectory_id = f"MHR-{uuid.uuid4().hex[:10].upper()}"

        out = MultiHopResultSchema(
            answer=answer,
            hops=hops,
            path_entities=path_entities,
            quality=quality,
            tokens=min(budget, tokens_spent),
            muscle_memory_hit=False,
            entanglement_errors=ent_errors,
            trajectory_id=trajectory_id,
        )

        if quality >= 0.90 and ent_errors == 0 and hops:
            self._cache_trajectory(payload, hops, quality, out.tokens)
        return out

    def _validate_hop(self, payload: Mapping[str, Any]) -> HopExecution:
        try:
            hop = HopSchema.model_validate(dict(payload))
            return HopExecution(hop=hop, valid=True, entanglement_delta=0)
        except ValidationError as exc:
            errors = [e["msg"] for e in exc.errors()]
            return HopExecution(
                hop=None,
                valid=False,
                errors=errors,
                entanglement_delta=1,
            )

    def _infer_seed(self, query: str) -> str:
        q = query.lower()
        best_id = "fcc"
        best_score = 0
        for e in self.kg.data["entities"]:
            title = e["title"].lower()
            eid = e["id"].lower()
            score = 0
            for token in title.replace("-", " ").split():
                if len(token) > 3 and token in q:
                    score += 2
            if eid in q.replace(" ", "_"):
                score += 3
            if score > best_score:
                best_score = score
                best_id = e["id"]
        return best_id

    def _synthesize_answer(
        self,
        query: str,
        hops: Sequence[HopSchema],
        local: Mapping[str, Any],
    ) -> str:
        if not hops:
            return (
                f"No schema-valid hops for query={query!r}. "
                "Charter requires evidence-backed relations."
            )
        chain = " → ".join(
            f"{h.entity}[{h.relation}@{h.confidence_score:.2f}]" for h in hops
        )
        evidence = "; ".join(h.evidence[:120] for h in hops[:4])
        return (
            f"Multi-hop answer for: {query}\n"
            f"Path: {chain}\n"
            f"Evidence: {evidence}\n"
            f"Nodes expanded: {len(local.get('nodes', []))}"
        )

    def _score_quality(self, hops: Sequence[HopSchema], ent_errors: int) -> float:
        if not hops:
            return 0.35
        avg_conf = sum(h.confidence_score for h in hops) / len(hops)
        penalty = min(0.5, 0.12 * ent_errors)
        return max(0.0, min(1.0, avg_conf - penalty + 0.05 * min(3, len(hops))))

    def _cache_trajectory(
        self,
        payload: Mapping[str, Any],
        hops: Sequence[HopSchema],
        quality: float,
        tokens: int,
    ) -> None:
        path = [f"hop:{h.hop_index}:{h.source_id or h.entity}" for h in hops]
        path.insert(0, "U_MultiHopReasoner")
        record = ExecutionMemoryRecord(
            memory_id=f"MHR-{uuid.uuid4().hex[:8].upper()}",
            job_type="multi_hop_reason",
            state_vector=encode_state(payload),
            successful_flow_path=path,
            entanglement_score=quality,
            prompt_tweak="schema-locked hops only; no free-form edges",
            quality=quality,
            token_cost=tokens,
            tags=("multi_hop", "v1.7", "graph_walk"),
        )
        self.muscle.commit_memory(record)
        self.trajectories_cached += 1

    def _from_memory(
        self,
        query: str,
        mem: ExecutionMemoryRecord,
        budget: int,
    ) -> MultiHopResultSchema:
        hops: List[HopSchema] = []
        for step in mem.successful_flow_path:
            if step.startswith("U_"):
                continue
            hops.append(
                HopSchema(
                    entity=step,
                    relation="muscle_memory_replay",
                    evidence=f"Cached trajectory {mem.memory_id}",
                    confidence_score=min(1.0, mem.quality),
                    hop_index=len(hops),
                    source_id=step,
                )
            )
        return MultiHopResultSchema(
            answer=(
                f"Muscle-Memory replay (0 LLM path tokens) for: {query}\n"
                f"Path: {' → '.join(mem.successful_flow_path)}\n"
                f"Cheat: {mem.prompt_tweak}"
            ),
            hops=hops,
            path_entities=list(mem.successful_flow_path),
            quality=mem.quality,
            tokens=0,
            muscle_memory_hit=True,
            entanglement_errors=0,
            trajectory_id=mem.memory_id,
        )

    def stats(self) -> Dict[str, Any]:
        return {
            "entanglement_errors": self.entanglement_errors,
            "trajectories_cached": self.trajectories_cached,
            "muscle": self.muscle.stats() if self.muscle else {},
            "max_hops": self.max_hops,
            "min_hop_confidence": self.min_hop_confidence,
        }
