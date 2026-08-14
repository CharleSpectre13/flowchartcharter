"""v2.3 Gate 1 — honest retrieval Port.

GraphRAG is a callable sub-flow, never the orchestrator.
Results always declare which backend actually ran.
`claimed_graphrag` is True only when an external GraphRAG HTTP call succeeded.

DRIFT (graph-engineering / graphrag-pipeline): primer → local follow-ups
→ reduce, implemented over the in-process KG unless an endpoint is live.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .knowledge_graph import KnowledgeGraph
from .muscle_memory import MuscleMemoryVectorDB


class RetrievalHit(BaseModel):
    id: str = ""
    title: str = ""
    snippet: str = ""
    score: float = 0.0
    source: str = ""


class RetrievalResult(BaseModel):
    backend: str
    mode: str
    hits: List[RetrievalHit] = Field(default_factory=list)
    tokens: int = 0
    claimed_graphrag: bool = False
    reason: str = ""
    drift_phases: List[str] = Field(default_factory=list)
    rhythm_audit: Dict[str, Any] = Field(default_factory=dict)
    delta: bool = False
    rebuild: bool = False
    cited: bool = False
    episode: bool = False
    synthesis: str = ""
    partials: List[Dict[str, Any]] = Field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class RetrievalPort:
    """SIMPLE → muscle; LOCAL/GLOBAL/DRIFT → KG or GraphRAG HTTP."""

    def __init__(
        self,
        *,
        muscle: Optional[MuscleMemoryVectorDB] = None,
        kg: Optional[KnowledgeGraph] = None,
        graphrag_endpoint: Optional[str] = None,
        timeout_s: float = 12.0,
    ) -> None:
        self.muscle = muscle or MuscleMemoryVectorDB(quiet=True)
        self.kg = kg or KnowledgeGraph()
        self.graphrag_endpoint = (
            graphrag_endpoint or os.environ.get("FCC_GRAPHRAG_ENDPOINT", "")
        ).rstrip("/")
        self.timeout_s = timeout_s

    def retrieve(
        self,
        query: str,
        *,
        mode: str = "simple",
        token_budget: int = 180,
        seed_entity: Optional[str] = None,
    ) -> RetrievalResult:
        mode = (mode or "simple").lower()
        if mode in ("simple", "vector", "lookup"):
            result = self._muscle(query, token_budget)
        elif mode in ("lazy", "concept"):
            result = self._kg_lazy(query, token_budget)
        elif mode in ("fusion", "hybrid_memory"):
            result = self._fuse(query, token_budget, seed_entity)
        elif mode in ("units", "passage", "passages"):
            result = self._kg_units(query, token_budget)
        elif self.graphrag_endpoint:
            ext = self._graphrag_http(query, mode, token_budget)
            if ext.claimed_graphrag:
                result = ext
            elif mode in ("global", "theme"):
                result = self._kg_global(query, token_budget)
            elif mode in ("drift", "hybrid", "diagnostic"):
                result = self._kg_drift(query, token_budget, seed_entity)
            else:
                result = self._kg_local(query, token_budget, seed_entity)
        elif mode in ("global", "theme"):
            result = self._kg_global(query, token_budget)
        elif mode in ("drift", "hybrid", "diagnostic"):
            result = self._kg_drift(query, token_budget, seed_entity)
        else:
            result = self._kg_local(query, token_budget, seed_entity)
        return self._stamp_rhythm(result)

    def _stamp_rhythm(self, result: RetrievalResult) -> RetrievalResult:
        """ST-04: Audit Manager grades honesty evidence, not a 0.92 gift."""
        from .rhythm_gate import attach_rhythm, independent_audit

        payload = {
            "ok": True,
            "blocked": False,
            "dry_run": True,
            "gate": {"valid": True},
            "claimed_graphrag": result.claimed_graphrag,
            "backend": result.backend,
            "delta": result.delta,
            "rebuild": result.rebuild,
        }
        issues_extra: List[str] = []
        ungrounded = [h for h in result.hits if not str(h.source or "").strip()]
        if ungrounded:
            payload["ok"] = False
            payload["gate"] = {"valid": False}
            issues_extra.append("ungrounded_hit")
        result.cited = bool(result.hits) and not ungrounded
        stale = []
        try:
            invalid = self.kg.invalid_unit_ids()
            stale = [
                h
                for h in result.hits
                if h.source in invalid or h.id in invalid
            ]
        except Exception:  # noqa: BLE001
            stale = []
        if stale:
            payload["ok"] = False
            payload["gate"] = {"valid": False}
            issues_extra.append("stale_hit")
        if result.synthesis:
            allowed = set()
            for part in result.partials or []:
                for sent in part.get("sentences") or []:
                    allowed.add(str(sent).strip().lower()[:80])
            for hit in result.hits:
                allowed.add(str(hit.snippet or "").strip().lower()[:80])
            invented = False
            for sent in re.split(r"(?<=[.!?])\s+", result.synthesis):
                key = sent.strip().lower()[:80]
                if key and key not in allowed:
                    invented = True
                    break
            if invented:
                payload["ok"] = False
                payload["gate"] = {"valid": False}
                issues_extra.append("reduce_invented")
        if result.claimed_graphrag and result.backend != "graphrag_http":
            payload["ok"] = False
            payload["blocked"] = True
            payload["gate"] = {"valid": False}
            issues_extra.append("claimed_graphrag_without_http")
        if result.backend == "graphrag_http_failed":
            payload["ok"] = False
            payload["gate"] = {"valid": False}
            issues_extra.append("graphrag_http_failed")
        audit = independent_audit(
            result=payload,
            charter_id=f"retrieval:{result.mode}:{result.backend}",
            implementor_role="Retrieval Port",
            auditor_role="Audit Manager",
            marker="gate",
        )
        blob = attach_rhythm(payload, audit)["rhythm_audit"]
        if issues_extra:
            issues = list(blob.get("blocking_issues") or [])
            for item in issues_extra:
                if item not in issues:
                    issues.append(item)
            blob["blocking_issues"] = issues
            blob["passed"] = False
        blob["evidence"] = {
            **(blob.get("evidence") or {}),
            "backend": result.backend,
            "delta": result.delta,
            "rebuild": result.rebuild,
            "claimed_graphrag": result.claimed_graphrag,
            "cited": result.cited,
            "valid": not bool(stale),
        }
        result.rhythm_audit = blob
        return result

    def _fuse(
        self,
        query: str,
        budget: int,
        seed_entity: Optional[str],
    ) -> RetrievalResult:
        """Cross-store fusion. Not GraphRAG. SIMPLE stays muscle-only."""
        lanes = [
            self._muscle(query, min(40, budget)),
            self._kg_units(query, min(80, budget)),
            self._kg_lazy(query, min(80, budget)),
            self._kg_local(query, min(80, budget), seed_entity),
        ]
        merged: Dict[str, RetrievalHit] = {}
        for lane, weight in zip(lanes, (1.0, 0.9, 0.6, 0.8)):
            for hit in lane.hits:
                key = (hit.id or hit.title or hit.snippet)[:80]
                if not key:
                    continue
                scored = RetrievalHit(
                    id=hit.id,
                    title=hit.title,
                    snippet=hit.snippet,
                    score=float(hit.score) * weight,
                    source=hit.source,
                )
                prev = merged.get(key)
                if prev is None or scored.score > prev.score:
                    merged[key] = scored
        hits = sorted(merged.values(), key=lambda h: -h.score)[:12]
        return RetrievalResult(
            backend="fcc_fusion",
            mode="fusion",
            hits=hits,
            tokens=min(160, budget),
            claimed_graphrag=False,
            reason="fused muscle+units+lazy; not Microsoft GraphRAG",
            delta=bool((getattr(self.kg, "data", {}) or {}).get("text_units")),
            rebuild=False,
            cited=bool(hits) and all(h.source for h in hits),
        )

    def _kg_units(self, query: str, budget: int) -> RetrievalResult:
        pack = self.kg.search_units(query, top_k=8)
        try:
            from .production import EmbeddingProvider

            emb = EmbeddingProvider(dims=32)
            qv = emb.embed({"q": query})
            for item in pack.get("units") or []:
                pv = emb.embed({"q": str(item.get("description") or "")})
                dot = sum(a * b for a, b in zip(qv, pv))
                item["score"] = float(item.get("score") or 0) + max(0.0, dot)
        except Exception:  # noqa: BLE001
            pass
        hits = _hits_from_pack(pack)
        for hit in hits:
            if not hit.source:
                hit.source = hit.id
        return RetrievalResult(
            backend="fcc_units",
            mode="units",
            hits=hits[:8],
            tokens=min(60, budget),
            claimed_graphrag=False,
            reason="passage search over TextUnits; not Microsoft GraphRAG",
            delta=True,
            rebuild=False,
            cited=bool(hits) and all(h.source for h in hits),
        )

    def _delta_backend(self) -> str:
        units = (getattr(self.kg, "data", {}) or {}).get("text_units") or []
        return "fcc_kg_delta" if units else "fcc_kg_subflow"

    def _kg_lazy(self, query: str, budget: int) -> RetrievalResult:
        pack = self.kg.lazy_search(query, top_k=8)
        hits = _hits_from_pack(pack)
        return RetrievalResult(
            backend="fcc_lazy",
            mode="lazy",
            hits=hits[:8],
            tokens=min(80, budget),
            claimed_graphrag=False,
            reason="query-time concept overlap; not Microsoft GraphRAG",
            delta=True,
            rebuild=False,
        )

    def _muscle(self, query: str, budget: int) -> RetrievalResult:
        hit = self.muscle.query_muscle_memory(
            {"task": query, "lane": "simple"},
            similarity_threshold=0.80,
        )
        hits: List[RetrievalHit] = []
        if hit is not None:
            mid = str(getattr(hit, "memory_id", "") or "muscle")
            hits.append(
                RetrievalHit(
                    id=mid,
                    title="muscle_memory",
                    snippet="|".join(
                        list(getattr(hit, "successful_flow_path", []) or [])
                    ),
                    score=float(getattr(hit, "similarity", 0.9) or 0.9),
                    source=f"muscle:{mid}",
                )
            )
        return RetrievalResult(
            backend="muscle_memory",
            mode="simple",
            hits=hits,
            tokens=min(40, budget),
            claimed_graphrag=False,
            reason="vector/muscle first; GraphRAG not invoked on SIMPLE",
        )

    def _kg_local(
        self, query: str, budget: int, seed_entity: Optional[str]
    ) -> RetrievalResult:
        seed = seed_entity or _guess_entity(self.kg, query)
        pack = self.kg.local_search(seed, hops=2) if seed else {}
        hits = _hits_from_pack(pack)
        return RetrievalResult(
            backend=self._delta_backend(),
            mode="local",
            hits=hits[:8],
            tokens=min(120, budget),
            claimed_graphrag=False,
            reason="in-process KG neighborhood walk; not Microsoft GraphRAG",
            delta=bool((getattr(self.kg, "data", {}) or {}).get("text_units")),
            rebuild=False,
        )

    def _kg_global(self, query: str, budget: int) -> RetrievalResult:
        qfs = self.kg.qfs_search(query)
        if qfs.get("units"):
            hits = _hits_from_pack(qfs)
            for hit in hits:
                if not hit.source:
                    hit.source = hit.id
            return RetrievalResult(
                backend="fcc_qfs",
                mode="global",
                hits=hits[:8],
                tokens=min(180, budget),
                claimed_graphrag=False,
                reason="extractive QFS map-reduce; not Microsoft GraphRAG",
                delta=True,
                rebuild=False,
                cited=bool(hits) and all(h.source for h in hits),
                synthesis=str(qfs.get("synthesis") or ""),
                partials=list(qfs.get("partials") or []),
            )
        pack = self.kg.global_search(query)
        hits = _hits_from_pack(pack)
        return RetrievalResult(
            backend=self._delta_backend(),
            mode="global",
            hits=hits[:8],
            tokens=min(180, budget),
            claimed_graphrag=False,
            reason="in-process community summaries; not Microsoft GraphRAG",
            delta=bool((getattr(self.kg, "data", {}) or {}).get("text_units")),
            rebuild=False,
        )

    def _kg_drift(
        self,
        query: str,
        budget: int,
        seed_entity: Optional[str],
    ) -> RetrievalResult:
        """DRIFT-shaped sub-flow: primer → local follow-ups → reduce.

        Uses the FCC KG. Does not claim Leiden or Microsoft GraphRAG.
        """
        primer = self.kg.global_search(query)
        primer_hits = _hits_from_pack(primer)[:5]
        follow: List[RetrievalHit] = []
        seeds = [seed_entity] if seed_entity else []
        for h in primer_hits[:3]:
            if h.id:
                seeds.append(h.id)
        if not seeds:
            seeds.append(_guess_entity(self.kg, query))
        spent = min(60, budget)
        for seed in seeds[:3]:
            if spent >= budget:
                break
            pack = self.kg.local_search(seed, hops=2)
            follow.extend(_hits_from_pack(pack)[:3])
            spent = min(budget, spent + 40)
        seen: set[str] = set()
        reduced: List[RetrievalHit] = []
        for hit in primer_hits + follow:
            key = hit.id or hit.title
            if key in seen:
                continue
            seen.add(key)
            reduced.append(hit)
        return RetrievalResult(
            backend=self._delta_backend(),
            mode="drift",
            hits=reduced[:12],
            tokens=spent,
            claimed_graphrag=False,
            reason=(
                "DRIFT-shaped KG sub-flow (primer+local+reduce); "
                "not Microsoft GraphRAG / not Leiden"
            ),
            drift_phases=["primer", "follow_up", "reduce"],
            delta=bool((getattr(self.kg, "data", {}) or {}).get("text_units")),
            rebuild=False,
        )

    def _graphrag_http(
        self, query: str, mode: str, budget: int
    ) -> RetrievalResult:
        url = f"{self.graphrag_endpoint}/query"
        body = json.dumps(
            {"query": query, "mode": mode, "token_budget": budget}
        ).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            json.JSONDecodeError,
        ):
            return RetrievalResult(
                backend="graphrag_http_failed",
                mode=mode,
                claimed_graphrag=False,
                reason="FCC_GRAPHRAG_ENDPOINT set but call failed; not claimed",
            )
        hits = []
        for raw in payload.get("hits") or payload.get("answers") or []:
            if isinstance(raw, dict):
                hits.append(
                    RetrievalHit(
                        id=str(raw.get("id") or ""),
                        title=str(
                            raw.get("title") or raw.get("community") or ""
                        ),
                        snippet=str(
                            raw.get("text") or raw.get("snippet") or ""
                        )[:400],
                        score=float(raw.get("score") or 0.0),
                        source="graphrag_http",
                    )
                )
        return RetrievalResult(
            backend="graphrag_http",
            mode=str(payload.get("mode") or mode),
            hits=hits[:12],
            tokens=int(payload.get("tokens") or min(200, budget)),
            claimed_graphrag=True,
            reason="external GraphRAG sub-flow succeeded",
        )


def _guess_entity(kg: KnowledgeGraph, query: str) -> str:
    q = (query or "").lower()
    data = getattr(kg, "data", {}) or {}
    entities = data.get("entities") or []
    if isinstance(entities, dict):
        entities = list(entities.values())
    for ent in entities:
        if not isinstance(ent, dict):
            continue
        title = str(ent.get("title") or ent.get("id") or "").lower()
        eid = str(ent.get("id") or "")
        if title and title in q:
            return eid
        if eid and eid.lower() in q:
            return eid
    if entities and isinstance(entities[0], dict):
        return str(entities[0].get("id") or "fcc")
    return "fcc"


def _hits_from_pack(pack: Dict[str, Any]) -> List[RetrievalHit]:
    hits: List[RetrievalHit] = []
    if not isinstance(pack, dict):
        return hits
    for key in (
        "entities",
        "communities",
        "reports",
        "neighbors",
        "hits",
        "nodes",
        "units",
    ):
        blob = pack.get(key)
        if isinstance(blob, dict):
            blob = list(blob.values())
        if not isinstance(blob, list):
            continue
        for item in blob:
            if not isinstance(item, dict):
                continue
            eid = str(item.get("id") or item.get("community_id") or "")
            srcs = item.get("sources") or []
            if isinstance(srcs, list) and srcs:
                source = str(srcs[0])
            elif item.get("source"):
                source = str(item.get("source"))
            elif eid:
                source = f"entity:{eid}"
            else:
                source = f"ontology:{key}"
            hits.append(
                RetrievalHit(
                    id=eid,
                    title=str(item.get("title") or item.get("name") or key),
                    snippet=str(
                        item.get("executive_summary")
                        or item.get("description")
                        or item.get("summary")
                        or ""
                    )[:400],
                    score=float(
                        item.get("importance") or item.get("score") or 0.5
                    ),
                    source=source,
                )
            )
    return hits
