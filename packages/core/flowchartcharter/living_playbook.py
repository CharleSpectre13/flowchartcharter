"""Living Playbook & Automation Ascension Model.

Cross-generational operational memory — decoupled from hard-coded agent models.

Layers:
  1. Ascended Memory Vector — Objective Signature, KPIs, Capability Map, Evolution
  2. Personnel-agnostic trajectory remapping (capability matching)
  3. Muscle-Memory Horizon — pattern interpolation + zero-shot FlowChart synthesis
  4. Ascension Protocol — nodes "become the coach" above critical mass
"""
from __future__ import annotations

import hashlib
import math
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .muscle_memory import (
    ExecutionMemoryRecord,
    MuscleMemoryVectorDB,
    cosine_similarity,
    encode_state,
)


# ---------------------------------------------------------------------------
# Ascended schema
# ---------------------------------------------------------------------------

# Objective signature dims (normalized 0..1):
# [domain, complexity, risk, latency_sensitivity, token_budget_band, novelty]
OBJECTIVE_DIMS = 6

# Default KPI keys stored with every trajectory
DEFAULT_KPI_KEYS = (
    "quality",
    "token_efficiency",
    "latency_ratio",
    "schema_compliance",
    "entanglement",
)


@dataclass
class AbstractedKPIs:
    """Why a trajectory worked — personnel-agnostic success metrics."""

    quality: float = 0.95
    token_efficiency: float = 0.9  # 1 − bloat_ratio
    latency_ratio: float = 0.9  # expected/actual (capped)
    schema_compliance: float = 1.0
    entanglement: float = 0.95

    def as_vector(self) -> List[float]:
        return [
            float(self.quality),
            float(self.token_efficiency),
            float(self.latency_ratio),
            float(self.schema_compliance),
            float(self.entanglement),
        ]

    def to_dict(self) -> Dict[str, float]:
        return {
            "quality": self.quality,
            "token_efficiency": self.token_efficiency,
            "latency_ratio": self.latency_ratio,
            "schema_compliance": self.schema_compliance,
            "entanglement": self.entanglement,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AbstractedKPIs":
        return cls(
            quality=float(data.get("quality", 0.95)),
            token_efficiency=float(data.get("token_efficiency", 0.9)),
            latency_ratio=float(data.get("latency_ratio", 0.9)),
            schema_compliance=float(data.get("schema_compliance", 1.0)),
            entanglement=float(data.get("entanglement", 0.95)),
        )


@dataclass
class AscendedMemoryRecord:
    """Living playbook entry — personnel-agnostic trajectory + KPIs.

    Ascended Memory Vector:
      [Objective Signature, Required KPIs, Capability Map, Evolution Iteration]
    """

    memory_id: str
    job_type: str
    # Legacy state embedding (entropy, size, complexity, error_weight)
    state_vector: List[float]
    successful_flow_path: List[str]
    # Ascended fields
    objective_signature: List[float]
    kpis: AbstractedKPIs
    capability_map: Dict[str, float]  # capability → weight used
    evolution_iteration: int = 1
    # Bookkeeping
    entanglement_score: float = 0.95
    prompt_tweak: str = ""
    quality: float = 0.95
    token_cost: int = 0
    expected_token_cost: int = 0
    tags: Tuple[str, ...] = ()
    origin_model_class: str = "generic"  # e.g. "70B", "1T", "generic"
    success_rationale: str = ""  # why it worked (short)

    def __post_init__(self) -> None:
        if not self.memory_id:
            self.memory_id = f"LPB-{uuid.uuid4().hex[:8].upper()}"
        self.state_vector = [float(x) for x in self.state_vector]
        self.objective_signature = [
            max(0.0, min(1.0, float(x))) for x in self.objective_signature
        ]
        while len(self.objective_signature) < OBJECTIVE_DIMS:
            self.objective_signature.append(0.5)
        self.objective_signature = self.objective_signature[:OBJECTIVE_DIMS]
        self.successful_flow_path = [str(p) for p in self.successful_flow_path]
        self.capability_map = {
            str(k): float(v) for k, v in self.capability_map.items()
        }
        self.evolution_iteration = max(1, int(self.evolution_iteration))
        if not 0.0 <= self.quality <= 1.0:
            raise ValueError("quality must be in [0, 1]")

    def ascended_vector(self) -> List[float]:
        """Flat vector for similarity: objective + KPIs + evolution scale."""
        evo = min(1.0, self.evolution_iteration / 20.0)
        return (
            list(self.objective_signature)
            + self.kpis.as_vector()
            + [evo]
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["kpis"] = self.kpis.to_dict()
        d["tags"] = list(self.tags)
        d["ascended_vector"] = self.ascended_vector()
        return d

    def to_execution_record(self) -> ExecutionMemoryRecord:
        return ExecutionMemoryRecord(
            memory_id=self.memory_id,
            job_type=self.job_type,
            state_vector=list(self.state_vector),
            successful_flow_path=list(self.successful_flow_path),
            entanglement_score=self.entanglement_score,
            prompt_tweak=self.prompt_tweak,
            quality=self.quality,
            token_cost=self.token_cost,
            tags=self.tags,
        )


def objective_signature_from_payload(
    payload: Mapping[str, Any],
    *,
    entropy: float = 0.3,
) -> List[float]:
    """Derive 6-dim objective signature from workload text + features."""
    text = str(
        payload.get("task")
        or payload.get("job")
        or payload.get("workload")
        or payload
    ).lower()
    # domain buckets (hash-stable pseudo embedding of keywords)
    domains = {
        "data": ("csv", "json", "clean", "parse", "sanitize", "etl"),
        "code": ("refactor", "code", "python", "ast", "legacy", "migrate"),
        "security": ("auth", "token", "security", "oauth", "bearer"),
        "sql": ("sql", "query", "database", "warehouse", "index"),
        "api": ("api", "gateway", "rest", "endpoint", "http"),
    }
    domain_score = 0.5
    for i, (_name, keys) in enumerate(domains.items()):
        if any(k in text for k in keys):
            domain_score = (i + 1) / len(domains)
            break
    complexity = min(1.0, len(text) / 200.0)
    risk = 0.7 if any(k in text for k in ("security", "auth", "prod")) else 0.3
    latency_sens = 0.8 if any(k in text for k in ("realtime", "fast", "low-lat")) else 0.4
    token_band = min(1.0, float(payload.get("priority", 0.5)))
    novelty = float(entropy) if entropy is not None else 0.3
    if any(k in text for k in ("novel", "unprecedented", "unknown")):
        novelty = max(novelty, 0.85)
    return [
        domain_score,
        complexity,
        risk,
        latency_sens,
        token_band,
        max(0.0, min(1.0, novelty)),
    ]


def capability_map_from_path(
    flow_path: Sequence[str],
    agent_caps: Optional[Mapping[str, float]] = None,
) -> Dict[str, float]:
    """Map flow units / path ids → capability weights (personnel-agnostic)."""
    caps: Dict[str, float] = {}
    for step in flow_path:
        s = str(step).lower()
        if "clean" in s or "sanit" in s or "ingest" in s:
            caps["json_parsing"] = max(caps.get("json_parsing", 0.0), 0.8)
            caps["regex_sanitize"] = max(caps.get("regex_sanitize", 0.0), 0.7)
        if "schema" in s or "type" in s:
            caps["json_parsing"] = max(caps.get("json_parsing", 0.0), 0.9)
        if "refactor" in s or "ast" in s or "code" in s:
            caps["python_ast"] = max(caps.get("python_ast", 0.0), 0.9)
            caps["refactoring"] = max(caps.get("refactoring", 0.0), 0.85)
        if "secure" in s or "token" in s or "auth" in s:
            caps["security_audit"] = max(caps.get("security_audit", 0.0), 0.9)
        if "sql" in s or "query" in s:
            caps["sql_optimization"] = max(caps.get("sql_optimization", 0.0), 0.9)
        if s.startswith("path_"):
            caps["general"] = max(caps.get("general", 0.0), 0.6)
    if agent_caps:
        for k, v in agent_caps.items():
            caps[k] = max(caps.get(k, 0.0), float(v))
    if not caps:
        caps["general"] = 1.0
    return caps


def kpis_from_run(
    *,
    quality: float,
    token_cost: int,
    expected_tokens: int,
    actual_time: float,
    expected_time: float,
    schema_ok: bool,
    entanglement: float,
) -> AbstractedKPIs:
    exp_tok = expected_tokens if expected_tokens > 0 else max(token_cost, 1)
    bloat = max(0, token_cost - exp_tok) / exp_tok
    token_eff = max(0.0, 1.0 - bloat)
    exp_t = expected_time if expected_time > 0 else max(actual_time, 1e-6)
    lat_ratio = min(2.0, exp_t / max(actual_time, 1e-6))
    lat_ratio = min(1.0, lat_ratio)  # cap at 1 for "as fast or faster"
    return AbstractedKPIs(
        quality=max(0.0, min(1.0, quality)),
        token_efficiency=token_eff,
        latency_ratio=lat_ratio,
        schema_compliance=1.0 if schema_ok else 0.0,
        entanglement=max(0.0, min(1.0, entanglement)),
    )


# ---------------------------------------------------------------------------
# Living Playbook store
# ---------------------------------------------------------------------------


@dataclass
class LivingPlaybook:
    """Cross-generational playbook store with capability remapping + ascension."""

    records: List[AscendedMemoryRecord] = field(default_factory=list)
    evolution_iteration: int = 1
    model_class: str = "generic"  # current personnel generation
    ascension_threshold: int = 12  # critical mass of high-quality records
    quiet: bool = True

    def commit(
        self,
        record: AscendedMemoryRecord,
        *,
        promote_to_muscle: Optional[MuscleMemoryVectorDB] = None,
    ) -> None:
        """Store ascended trajectory; optionally mirror into classic MM VDB."""
        record.evolution_iteration = max(
            record.evolution_iteration, self.evolution_iteration
        )
        self.records.append(record)
        if promote_to_muscle is not None and record.quality >= 0.90:
            promote_to_muscle.commit_memory(record.to_execution_record())
        if not self.quiet:
            print(
                f"[LivingPlaybook] Committed {record.memory_id} "
                f"iter={record.evolution_iteration}"
            )

    def commit_from_execution(
        self,
        *,
        job_type: str,
        flow_path: Sequence[str],
        payload: Mapping[str, Any],
        quality: float,
        token_cost: int,
        expected_tokens: int = 0,
        actual_time: float = 1.0,
        expected_time: float = 1.0,
        entanglement: float = 0.95,
        schema_ok: bool = True,
        prompt_tweak: str = "",
        agent_caps: Optional[Mapping[str, float]] = None,
        entropy: float = 0.3,
        muscle_db: Optional[MuscleMemoryVectorDB] = None,
        rationale: str = "",
    ) -> AscendedMemoryRecord:
        state = encode_state(payload if payload else {"task": job_type})
        kpis = kpis_from_run(
            quality=quality,
            token_cost=token_cost,
            expected_tokens=expected_tokens or token_cost,
            actual_time=actual_time,
            expected_time=expected_time,
            schema_ok=schema_ok,
            entanglement=entanglement,
        )
        rec = AscendedMemoryRecord(
            memory_id=f"LPB-{uuid.uuid4().hex[:8].upper()}",
            job_type=job_type,
            state_vector=state,
            successful_flow_path=list(flow_path),
            objective_signature=objective_signature_from_payload(
                payload if payload else {"task": job_type},
                entropy=entropy,
            ),
            kpis=kpis,
            capability_map=capability_map_from_path(flow_path, agent_caps),
            evolution_iteration=self.evolution_iteration,
            entanglement_score=entanglement,
            prompt_tweak=prompt_tweak,
            quality=quality,
            token_cost=token_cost,
            expected_token_cost=expected_tokens or token_cost,
            tags=(job_type.split()[0].lower(),) if job_type else (),
            origin_model_class=self.model_class,
            success_rationale=rationale
            or f"quality={quality:.2f} token_eff={kpis.token_efficiency:.2f}",
        )
        self.commit(rec, promote_to_muscle=muscle_db)
        return rec

    def query(
        self,
        payload: Mapping[str, Any],
        *,
        entropy: float = 0.3,
        threshold: float = 0.72,
        top_k: int = 5,
    ) -> List[Tuple[float, AscendedMemoryRecord]]:
        """Similarity over ascended vectors (objective + KPIs)."""
        sig = objective_signature_from_payload(payload, entropy=entropy)
        # synthetic query vector: objective + neutral KPIs + current evo
        evo = min(1.0, self.evolution_iteration / 20.0)
        qvec = sig + [0.9, 0.9, 0.9, 1.0, 0.9] + [evo]
        scored: List[Tuple[float, AscendedMemoryRecord]] = []
        for rec in self.records:
            sim = cosine_similarity(qvec, rec.ascended_vector())
            # boost KPI quality
            sim = 0.85 * sim + 0.15 * rec.kpis.quality
            if sim >= threshold:
                scored.append((sim, rec))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:top_k]

    # ----- Cross-generational remapping ------------------------------------

    def remap_to_personnel(
        self,
        record: AscendedMemoryRecord,
        *,
        available_capabilities: Mapping[str, float],
        new_model_class: str,
    ) -> Dict[str, Any]:
        """Translate historical trajectory for a new model generation.

        Maps required capabilities → best available node skills without
        rewriting the success KPIs (the *why* stays constant).
        """
        mapped_path: List[str] = []
        substitutions: Dict[str, str] = {}
        missing: List[str] = []

        for step in record.successful_flow_path:
            # keep structural path ids; remap capability-named units
            caps_needed = capability_map_from_path([step])
            best_cap = None
            best_score = -1.0
            for need, weight in caps_needed.items():
                have = float(available_capabilities.get(need, 0.0))
                # soft match: general can cover light needs
                if have <= 0 and "general" in available_capabilities:
                    have = 0.4 * float(available_capabilities["general"])
                score = have * weight
                if score > best_score:
                    best_score = score
                    best_cap = need
            if best_cap and best_score > 0.15:
                # annotate step with personnel capability
                new_step = step
                if best_cap not in step.lower():
                    new_step = f"{step}@{best_cap}"
                    substitutions[step] = new_step
                mapped_path.append(new_step)
            else:
                missing.append(step)
                mapped_path.append(step)  # keep; phantom may fill

        remapped = AscendedMemoryRecord(
            memory_id=f"{record.memory_id}-G{self.evolution_iteration}",
            job_type=record.job_type,
            state_vector=list(record.state_vector),
            successful_flow_path=mapped_path,
            objective_signature=list(record.objective_signature),
            kpis=AbstractedKPIs(**record.kpis.to_dict()),
            capability_map=dict(available_capabilities),
            evolution_iteration=self.evolution_iteration + 1,
            entanglement_score=record.entanglement_score,
            prompt_tweak=record.prompt_tweak,
            quality=record.quality,
            token_cost=record.token_cost,
            expected_token_cost=record.expected_token_cost,
            tags=record.tags + ("remapped",),
            origin_model_class=new_model_class,
            success_rationale=(
                f"Remapped from {record.origin_model_class} → {new_model_class}; "
                f"KPIs preserved: {record.success_rationale}"
            ),
        )
        return {
            "source_id": record.memory_id,
            "remapped": remapped,
            "mapped_path": mapped_path,
            "substitutions": substitutions,
            "missing_steps": missing,
            "kpis_preserved": record.kpis.to_dict(),
            "new_model_class": new_model_class,
        }

    def upgrade_generation(
        self,
        new_model_class: str,
        available_capabilities: Mapping[str, float],
    ) -> Dict[str, Any]:
        """Boss Agent call when enterprise upgrades model tier (70B → 1T)."""
        remaps = []
        for rec in list(self.records):
            result = self.remap_to_personnel(
                rec,
                available_capabilities=available_capabilities,
                new_model_class=new_model_class,
            )
            remaps.append(
                {
                    "source": result["source_id"],
                    "path": result["mapped_path"],
                    "missing": result["missing_steps"],
                }
            )
            self.records.append(result["remapped"])
        self.model_class = new_model_class
        self.evolution_iteration += 1
        return {
            "model_class": new_model_class,
            "evolution_iteration": self.evolution_iteration,
            "remapped_count": len(remaps),
            "remaps": remaps[:20],
        }

    # ----- Automation Ascension --------------------------------------------

    @property
    def horizon_reached(self) -> bool:
        """Critical mass: enough high-quality trajectories for zero-shot."""
        strong = sum(1 for r in self.records if r.quality >= 0.90)
        return strong >= self.ascension_threshold

    def interpolate_patterns(
        self,
        payload: Mapping[str, Any],
        *,
        entropy: float = 0.5,
        min_parts: int = 2,
    ) -> Optional[Dict[str, Any]]:
        """Pattern interpolation — stitch Job A (80%) + Job B (20%) style path.

        When no single HIT exists, blend top similar trajectories into a
        zero-shot FlowChart.
        """
        hits = self.query(payload, entropy=entropy, threshold=0.55, top_k=4)
        if len(hits) < min_parts and not self.horizon_reached:
            return None
        if not hits:
            return None

        # Weight paths by similarity
        total_w = sum(s for s, _ in hits) or 1.0
        # Prefer longer high-quality prefixes from best match, suffix from next
        primary_sim, primary = hits[0]
        secondary = hits[1][1] if len(hits) > 1 else primary
        secondary_sim = hits[1][0] if len(hits) > 1 else 0.0

        p_path = list(primary.successful_flow_path)
        s_path = list(secondary.successful_flow_path)
        # 80/20 style blend: take first 80% of primary steps, last 20% unique
        # from secondary
        cut = max(1, int(math.ceil(len(p_path) * 0.8))) if p_path else 0
        blended = list(p_path[:cut])
        for step in s_path:
            if step not in blended:
                blended.append(step)
                if len(blended) >= max(len(p_path), 3):
                    break
        if not blended:
            blended = p_path or s_path or ["U1_Ingest", "U9_DeterministicExecute"]

        # Blend KPIs
        w1 = primary_sim / total_w
        w2 = secondary_sim / total_w if secondary_sim else 0.0
        w2 = w2 if w2 > 0 else (1.0 - w1)
        blended_kpis = AbstractedKPIs(
            quality=w1 * primary.kpis.quality + w2 * secondary.kpis.quality,
            token_efficiency=(
                w1 * primary.kpis.token_efficiency
                + w2 * secondary.kpis.token_efficiency
            ),
            latency_ratio=(
                w1 * primary.kpis.latency_ratio
                + w2 * secondary.kpis.latency_ratio
            ),
            schema_compliance=min(
                primary.kpis.schema_compliance,
                secondary.kpis.schema_compliance,
            ),
            entanglement=(
                w1 * primary.kpis.entanglement
                + w2 * secondary.kpis.entanglement
            ),
        )

        chart_id = "ZC-" + hashlib.sha1(
            ("|".join(blended) + str(payload)).encode()
        ).hexdigest()[:8].upper()

        return {
            "zero_shot": True,
            "ascension": self.horizon_reached,
            "chart_id": chart_id,
            "synthesized_path": blended,
            "weights": {
                primary.memory_id: round(w1, 4),
                secondary.memory_id: round(w2, 4),
            },
            "sources": [h[1].memory_id for h in hits],
            "similarities": [round(h[0], 4) for h in hits],
            "blended_kpis": blended_kpis.to_dict(),
            "prompt_tweak": primary.prompt_tweak or secondary.prompt_tweak,
            "rationale": (
                f"Interpolated {primary.job_type!r} ({w1:.0%}) + "
                f"{secondary.job_type!r} ({w2:.0%}); "
                f"horizon={'ON' if self.horizon_reached else 'building'}"
            ),
        }

    def synthesize_charter(
        self,
        payload: Mapping[str, Any],
        *,
        entropy: float = 0.5,
        force_zero_shot: bool = False,
    ) -> Dict[str, Any]:
        """Boss Agent entry: resolve path via HIT or zero-shot synthesis.

        Returns mode: hit | zero_shot | miss
        """
        hits = self.query(payload, entropy=entropy, threshold=0.78, top_k=1)
        if hits and not force_zero_shot:
            sim, rec = hits[0]
            return {
                "mode": "hit",
                "path": list(rec.successful_flow_path),
                "memory_id": rec.memory_id,
                "similarity": round(sim, 4),
                "kpis": rec.kpis.to_dict(),
                "prompt_tweak": rec.prompt_tweak,
                "ascension": self.horizon_reached,
                "rationale": rec.success_rationale,
            }

        synthetic = self.interpolate_patterns(
            payload, entropy=entropy, min_parts=1 if force_zero_shot else 2
        )
        if synthetic:
            return {
                "mode": "zero_shot",
                "path": synthetic["synthesized_path"],
                "memory_id": synthetic["chart_id"],
                "similarity": synthetic["similarities"][0]
                if synthetic["similarities"]
                else 0.0,
                "kpis": synthetic["blended_kpis"],
                "prompt_tweak": synthetic["prompt_tweak"],
                "ascension": synthetic["ascension"],
                "rationale": synthetic["rationale"],
                "sources": synthetic["sources"],
                "weights": synthetic["weights"],
            }

        return {
            "mode": "miss",
            "path": None,
            "memory_id": None,
            "similarity": 0.0,
            "kpis": None,
            "prompt_tweak": "",
            "ascension": self.horizon_reached,
            "rationale": "No living-playbook precedent; fall back to Charter quantum pathing.",
        }

    def export(self) -> Dict[str, Any]:
        return {
            "model_class": self.model_class,
            "evolution_iteration": self.evolution_iteration,
            "record_count": len(self.records),
            "horizon_reached": self.horizon_reached,
            "ascension_threshold": self.ascension_threshold,
            "records": [r.to_dict() for r in self.records[-50:]],
        }


def seed_living_playbook(playbook: LivingPlaybook) -> None:
    """Seed representative trajectories for demo / tests."""
    seeds = [
        (
            "Legacy Code Refactor",
            ["U1_Ingest", "U4_TypeSanitize", "U8_DeterministicRefactor"],
            {"task": "Legacy Code Refactor", "code": "function x(){}"},
            0.98,
            ["python_ast", "refactoring"],
            "Strict camelCase + type sanitize worked",
            0.4,
        ),
        (
            "Refactor legacy authentication module with modern tokens",
            ["U1_Ingest", "U2_Sanitize", "U5_SecureTokenReplace"],
            {
                "task": "Refactor legacy authentication module with modern tokens",
            },
            0.97,
            ["security_audit", "refactoring"],
            "Bearer schema validation was the key",
            0.35,
        ),
        (
            "Clean messy customer CSV export",
            ["U1_Ingest", "U3_DataCleanse", "U9_DeterministicExecute"],
            {"task": "Clean messy customer CSV export"},
            0.94,
            ["json_parsing", "regex_sanitize"],
            "Cleansing path under high entropy",
            0.75,
        ),
        (
            "Build secure API gateway",
            ["U1_Ingest", "U4_SchemaEnforce", "U9_DeterministicExecute"],
            {"task": "Build secure API gateway"},
            0.93,
            ["api_gateway", "security_audit"],
            "Schema-first gateway",
            0.45,
        ),
        (
            "Migrate old database tables",
            ["U1_Ingest", "U4_SchemaEnforce", "U8_DeterministicRefactor"],
            {"task": "Migrate old database tables"},
            0.92,
            ["sql_optimization", "refactoring"],
            "Schema enforce before migrate",
            0.5,
        ),
    ]
    for job, path, payload, q, caps, why, ent in seeds:
        playbook.commit_from_execution(
            job_type=job,
            flow_path=path,
            payload=payload,
            quality=q,
            token_cost=300,
            expected_tokens=300,
            actual_time=1.0,
            expected_time=1.2,
            entanglement=0.96,
            schema_ok=True,
            prompt_tweak=why,
            agent_caps={c: 1.0 for c in caps},
            entropy=ent,
            rationale=why,
        )
    # Extra seeds to approach horizon
    for i in range(8):
        playbook.commit_from_execution(
            job_type=f"Batch workload pattern {i}",
            flow_path=["U1_Ingest", "U4_SchemaEnforce", "U9_DeterministicExecute"],
            payload={"task": f"Batch workload pattern {i}", "n": i},
            quality=0.91 + (i % 5) * 0.01,
            token_cost=200 + i * 10,
            expected_tokens=200 + i * 10,
            entanglement=0.94,
            agent_caps={"general": 1.0},
            entropy=0.2 + i * 0.05,
            rationale="Stable batch pattern",
        )
