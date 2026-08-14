from __future__ import annotations

import random
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .fitness import INDUSTRY_BENCHMARK, fitness
from .production import (
    LLMExecutionClient,
    LLMExecutionRequest,
    apply_execution_to_agent,
    WorkerTaskResult,
)
from .metrics import ExecutionMetrics
from .prompts import BOSS_ACKNOWLEDGEMENT, BOSS_AGENT_SYSTEM_PROMPT
from .survival import (
    GenerationParameters,
    LedgerEntry,
    LeanRehireDecision,
    SurvivalStatus,
    TelemetryLedger,
    build_worker_system_prompt,
    generation_params_for_risk,
    lean_rehire_check,
    risk_from_ledger,
    should_fire_from_ledger,
    status_from_risk,
)

if TYPE_CHECKING:
    from .analytics import RosterRecommendationDossier
    from .headhunter import HeadhunterDecision, HeadhunterProtocol
    from .hybrid_router import HybridBossRouter, RouteDecision
    from .knowledge_graph import KnowledgeGraph
    from .multi_hop_reasoner import MultiHopReasoner, MultiHopResultSchema
    from .muscle_memory import MuscleMemoryVectorDB
    from .swarm_manager import SwarmManager, SwarmReportSchema
    from .synthesis_squad import GlobalSynthesisReport, LazyGlobalSynthesisSquad


PATH_EXPECTED = {
    "path_A": {"tokens": 210, "time": 1.2},
    "path_B": {"tokens": 360, "time": 1.8},
    "path_lite": {"tokens": 90, "time": 0.7},
}


class AgentStatus(str, Enum):
    ACTIVE = "Active"
    PROMOTED = "Promoted"
    DEMOTED = "Demoted"
    FIRED = "Fired"
    PHANTOM = "Phantom"


class Agent:
    """Worker node with Fear-Based Accountability + patched fitness telemetry."""

    def __init__(
        self,
        name: str,
        role: str,
        capability_vector: Optional[Dict[str, float]] = None,
    ):
        self.id = str(uuid.uuid4())[:8]
        self.name = name
        self.role = role
        self.history: List[ExecutionMetrics] = []
        self.status = AgentStatus.ACTIVE
        self.muscle_memory_weights: Dict[str, float] = {
            "path_A": 1.0,
            "path_B": 1.0,
            "path_lite": 1.0,
        }
        self.capability_vector = capability_vector or {"general": 1.0}
        if capability_vector:
            self.capabilities: List[str] = list(capability_vector.keys())
        else:
            self.capabilities = ["general"]
        self.corporate_rank = 1.0
        self.load = 0.0
        self.talent_eligible = True
        self.is_phantom = False

        self.survival_status: SurvivalStatus = SurvivalStatus.ACTIVE
        self.termination_risk_index: float = 0.0
        self.ledger = TelemetryLedger()
        self.generation: GenerationParameters = generation_params_for_risk(0.0)
        self.system_prompt: str = self._rebuild_prompt()
        self.cycle_counter: int = 0
        self.llm_client = LLMExecutionClient()
        self.entanglement_errors: int = 0
        self.playbook_constraints: List[str] = [
            "Typed Flow Unit schema is mandatory",
            "Do not invent keys outside the contract",
            "Prefer Muscle-Memory path when provided",
        ]

    def _rebuild_prompt(self) -> str:
        return build_worker_system_prompt(
            agent_name=self.name,
            role=self.role,
            survival_status=self.survival_status.value,
            termination_risk_index=self.termination_risk_index,
            generation=self.generation,
            schema_errors=self.ledger.schema_errors,
        )

    def refresh_survival_prompt(self) -> str:
        self.generation = generation_params_for_risk(self.termination_risk_index)
        self.survival_status = status_from_risk(self.termination_risk_index)
        if self.status == AgentStatus.FIRED:
            self.survival_status = SurvivalStatus.TERMINATED
        elif self.is_phantom or self.status == AgentStatus.PHANTOM:
            self.survival_status = SurvivalStatus.AT_RISK
        self.system_prompt = self._rebuild_prompt()
        return self.system_prompt

    def record_cycle(
        self,
        *,
        schema_divergence: int,
        token_spend: int,
        token_ceiling: int,
        delta_t: float,
        structural_drift: float,
        quality: float,
        path: str = "",
        notes: str = "",
    ) -> float:
        self.cycle_counter += 1
        entry = LedgerEntry(
            cycle_id=f"{self.id}-C{self.cycle_counter}",
            schema_divergence=max(0, int(schema_divergence)),
            token_spend=max(0, int(token_spend)),
            token_ceiling=max(0, int(token_ceiling)),
            delta_t=float(delta_t),
            structural_drift=max(0.0, float(structural_drift)),
            quality=float(quality),
            path=path,
            notes=notes,
        )
        self.ledger.commit(entry)
        self.termination_risk_index = risk_from_ledger(
            self.ledger,
            prior_risk=self.termination_risk_index,
        )
        self.refresh_survival_prompt()
        return self.termination_risk_index

    def execute_flow_unit(
        self,
        task: str,
        *,
        rng: Optional[random.Random] = None,
        quality_bias: float = 0.0,
        path: str = "path_A",
        token_ceiling: int = 400,
        expected_schema_ok: bool = True,
        structural_drift: float = 0.0,
        expected_tokens: Optional[int] = None,
        expected_time: Optional[float] = None,
    ) -> Optional[ExecutionMetrics]:
        if self.status not in (
            AgentStatus.ACTIVE,
            AgentStatus.PROMOTED,
            AgentStatus.PHANTOM,
        ):
            if not self.is_phantom or self.status == AgentStatus.FIRED:
                return None

        r = rng or random
        risk = self.termination_risk_index
        if risk >= 0.55 and path == "path_B":
            path = "path_lite"

        baseline = PATH_EXPECTED.get(path, PATH_EXPECTED["path_A"])
        exp_tok = expected_tokens if expected_tokens is not None else int(baseline["tokens"])
        exp_time = expected_time if expected_time is not None else float(baseline["time"])

        if path == "path_lite":
            cost = r.randint(60, 120)
        elif path == "path_B":
            cost = r.randint(280, 450)
        else:
            cost = r.randint(140, 280)

        if self.generation.schema_lock:
            time = r.uniform(0.35, 1.4)
        else:
            time = r.uniform(0.4, 2.2)

        base_q = r.uniform(0.72, 1.0) + quality_bias
        if self.generation.schema_lock:
            base_q = max(base_q, 0.88 + 0.05 * risk)
        quality = min(1.0, max(0.0, base_q))
        synergy = r.uniform(0.82, 1.0)

        metrics = ExecutionMetrics(
            token_cost=cost,
            execution_time=time,
            quality_score=quality,
            synergy_score=synergy,
            expected_token_cost=exp_tok,
            expected_time=exp_time,
        )
        self.history.append(metrics)
        self.load = min(1.0, self.load + 0.1)

        schema_div = 0 if expected_schema_ok else 1
        drift = structural_drift
        if not expected_schema_ok:
            drift = max(drift, 0.4)
        elif quality < 0.85:
            drift = max(drift, 0.15)

        self.record_cycle(
            schema_divergence=schema_div,
            token_spend=cost,
            token_ceiling=token_ceiling,
            delta_t=time,
            structural_drift=drift,
            quality=quality,
            path=path,
            notes=task[:80],
        )
        return metrics

    def execute_live(
        self,
        workload: str,
        *,
        path: str = "path_A",
        expected_output_keys: Optional[List[str]] = None,
        playbook_constraints: Optional[List[str]] = None,
    ) -> Optional[ExecutionMetrics]:
        """Production path: LLMExecutionClient + schema gate + TPC inject.

        On schema violation, entanglement_errors increments before Boss sees data.
        """
        from .kill_law import refuse_side_effect

        if refuse_side_effect(action_type="llm_live"):
            return None
        if self.status not in (
            AgentStatus.ACTIVE,
            AgentStatus.PROMOTED,
            AgentStatus.PHANTOM,
        ):
            if not self.is_phantom or self.status == AgentStatus.FIRED:
                return None

        constraints = playbook_constraints or self.playbook_constraints
        req = LLMExecutionRequest(
            workload=workload,
            path=path,
            termination_risk_index=self.termination_risk_index,
            system_prompt=self.system_prompt,
            playbook_constraints=constraints,
            expected_output_keys=expected_output_keys or ["result", "quality", "path", "tokens"],
            agent_name=self.name,
            role=self.role,
        )
        resp = self.llm_client.execute(req)
        if resp.entanglement_errors_delta:
            self.entanglement_errors += resp.entanglement_errors_delta
        # apply via shared helper (history + ledger)
        apply_execution_to_agent(
            self,
            WorkerTaskResult(
                agent_name=self.name,
                response=resp,
                wall_ms=resp.latency_ms,
            ),
        )
        return self.history[-1] if self.history else None

    def calculate_fitness(self) -> float:
        return fitness(self.history)

    def volunteer_score(self, task_embedding: Dict[str, float], temperature: float = 1.0) -> float:
        if self.status == AgentStatus.FIRED:
            return 0.0
        score = 0.0
        for k, v in task_embedding.items():
            score += v * self.capability_vector.get(k, 0.0)
        score *= self.corporate_rank
        score *= max(0.2, 1.0 - 0.5 * self.termination_risk_index)
        score /= (1.0 + self.load) * max(temperature, 1e-6)
        return score

    def survival_snapshot(self) -> Dict[str, Any]:
        fit = round(self.calculate_fitness(), 4) if self.history else 0.0
        return {
            "agent": self.name,
            "id": self.id,
            "role": self.role,
            "status": self.status.value,
            "is_phantom": self.is_phantom,
            "survival_status": self.survival_status.value,
            "termination_risk_index": round(self.termination_risk_index, 4),
            "generation": self.generation.to_dict(),
            "ledger": self.ledger.export(),
            "fitness": fit,
            "capabilities": list(getattr(self, "capabilities", [])),
        }


class BossAgent(Agent):
    """General Manager — executes Board dossier; day-to-day ops only.

    v1.7: Hybrid Boss Router is the default nervous system. GraphRAG-class
    capabilities (multi-hop, global synthesis) are sub-flows under CFO caps.
    """

    def __init__(self, name: str, *, cfo_ceiling: int = 3500):
        super().__init__(name, "General Manager (Boss)")
        self.corporate_rank = 10.0
        self.playbook: List[str] = []
        self.talent_eligible = False
        self.system_prompt = BOSS_AGENT_SYSTEM_PROMPT
        self.acknowledged = False
        self.rehire_log: List[LeanRehireDecision] = []
        self.survival_status = SurvivalStatus.ACTIVE
        self.termination_risk_index = 0.0
        self.is_phantom = False
        self.last_dossier_id: Optional[str] = None
        self.cfo_ceiling = int(cfo_ceiling)
        # Lazy-init hybrid stack (v1.7) — imported on first use to keep cold start light
        self._hybrid_router: Optional["HybridBossRouter"] = None
        self._multi_hop: Optional["MultiHopReasoner"] = None
        self._synthesis: Optional["LazyGlobalSynthesisSquad"] = None
        self._kg: Optional["KnowledgeGraph"] = None
        self._muscle: Optional["MuscleMemoryVectorDB"] = None
        self.route_log: List[Dict[str, Any]] = []
        # v1.8 Autonomous Scaling Horizon
        self._swarm: Optional["SwarmManager"] = None
        self._headhunter: Optional["HeadhunterProtocol"] = None
        self.headhunter_log: List[Dict[str, Any]] = []
        # v2.1 Coach Trust Hand-Off
        self.pending_charters: Dict[str, Dict[str, Any]] = {}
        self.charter_synthesis_log: List[Dict[str, Any]] = []

    def _ensure_hybrid_stack(self) -> None:
        if self._hybrid_router is not None:
            return
        from .hybrid_router import HybridBossRouter
        from .knowledge_graph import KnowledgeGraph
        from .multi_hop_reasoner import MultiHopReasoner
        from .muscle_memory import MuscleMemoryVectorDB
        from .synthesis_squad import LazyGlobalSynthesisSquad

        self._kg = KnowledgeGraph()
        self._muscle = MuscleMemoryVectorDB(quiet=True)
        self._hybrid_router = HybridBossRouter(cfo_ceiling=self.cfo_ceiling)
        self._multi_hop = MultiHopReasoner(
            kg=self._kg,
            muscle=self._muscle,
            token_budget=min(900, self.cfo_ceiling),
        )
        self._synthesis = LazyGlobalSynthesisSquad(
            kg=self._kg,
            muscle=self._muscle,
            cfo_ceiling=min(2200, self.cfo_ceiling),
            llm_client=getattr(self, "llm_client", None),
        )

    def acknowledge_directive(self) -> str:
        self.acknowledged = True
        return BOSS_ACKNOWLEDGEMENT

    def route_workload(
        self,
        workload: str,
        *,
        hint: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "RouteDecision":
        """v1.7 tri-state classify only (no execution)."""
        self._ensure_hybrid_stack()
        assert self._hybrid_router is not None
        decision = self._hybrid_router.classify(
            workload,
            hint=hint,
            metadata=metadata,
        )
        self.route_log.append(decision.to_dict())
        self.playbook.append(
            f"Route {decision.lane.value} conf={decision.confidence:.2f} "
            f"budget={decision.estimated_token_budget}"
        )
        return decision

    def handle_workload(
        self,
        workload: str,
        *,
        hint: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        seed_entity: Optional[str] = None,
    ) -> Dict[str, Any]:
        """v1.7 Hybrid GM entrypoint: classify → execute lane → return envelope.

        Lanes:
          SIMPLE    → Muscle-Memory / vector path (path_lite)
          MULTI_HOP → MultiHopReasoner schema-locked graph walk
          GLOBAL    → LazyGlobalSynthesisSquad map-reduce under CFO ceiling
        """
        self._ensure_hybrid_stack()
        assert self._hybrid_router is not None
        assert self._multi_hop is not None
        assert self._synthesis is not None
        assert self._muscle is not None

        decision = self.route_workload(workload, hint=hint, metadata=metadata)
        envelope: Dict[str, Any] = {
            "route": decision.to_dict(),
            "lane": decision.lane.value,
            "version": "2.0.0",
        }

        if decision.lane.value == "simple":
            # Honest retrieval Port: muscle-memory first; never claim GraphRAG
            from .retrieval_port import RetrievalPort
            port = RetrievalPort(muscle=self._muscle)
            retrieved = port.retrieve(
                workload, mode="simple", token_budget=decision.estimated_token_budget
            )
            hit = self._muscle.query_muscle_memory(
                {"task": workload, "lane": "simple"},
                similarity_threshold=0.80,
            )
            metrics = self.execute_flow_unit(
                workload,
                path="path_lite",
                token_ceiling=decision.estimated_token_budget,
                expected_tokens=min(180, decision.estimated_token_budget),
                expected_time=0.7,
            )
            quality = metrics.quality_score if metrics else 0.0
            envelope["result"] = {
                "mode": "vector_retrieval",
                "muscle_memory_hit": hit is not None,
                "memory_id": hit.memory_id if hit else None,
                "flow_path": list(hit.successful_flow_path) if hit else ["path_lite"],
                "tokens": metrics.token_cost if metrics else 0,
                "quality": quality,
            }
            envelope["retrieval"] = retrieved.to_dict()
            envelope["rhythm_audit"] = self._hybrid_rhythm_gate(
                marker="hybrid_simple",
                quality=quality,
                issues=[] if quality >= 0.90 else ["simple_lane_quality_below_gate"],
            )
            return envelope

        if decision.lane.value == "multi_hop":
            mhr: "MultiHopResultSchema" = self._multi_hop.reason(
                workload,
                seed_entity=seed_entity,
                token_budget=decision.estimated_token_budget,
            )
            if mhr.entanglement_errors:
                self.entanglement_errors += mhr.entanglement_errors
                self.record_cycle(
                    schema_divergence=mhr.entanglement_errors,
                    token_spend=mhr.tokens,
                    token_ceiling=decision.estimated_token_budget,
                    delta_t=0.01 * max(1, len(mhr.hops)),
                    structural_drift=0.2 * mhr.entanglement_errors,
                    quality=mhr.quality,
                    path="multi_hop",
                    notes=workload[:80],
                )
            else:
                self.record_cycle(
                    schema_divergence=0,
                    token_spend=mhr.tokens,
                    token_ceiling=decision.estimated_token_budget,
                    delta_t=0.01 * max(1, len(mhr.hops)),
                    structural_drift=0.0,
                    quality=mhr.quality,
                    path="multi_hop",
                    notes=workload[:80],
                )
            envelope["result"] = mhr.model_dump()
            from .retrieval_port import RetrievalPort
            envelope["retrieval"] = RetrievalPort(
                muscle=self._muscle, kg=getattr(self._multi_hop, "kg", None)
            ).retrieve(
                workload,
                mode="drift",
                token_budget=decision.estimated_token_budget,
                seed_entity=seed_entity,
            ).to_dict()
            issues = []
            if mhr.entanglement_errors:
                issues.append(f"entanglement_errors={mhr.entanglement_errors}")
            if not mhr.hops:
                issues.append("no_schema_valid_hops")
            if mhr.quality < 0.90:
                issues.append("multi_hop_quality_below_gate")
            envelope["rhythm_audit"] = self._hybrid_rhythm_gate(
                marker="hybrid_multi_hop",
                quality=mhr.quality,
                issues=issues,
            )
            return envelope

        # GLOBAL
        report: "GlobalSynthesisReport" = self._synthesis.synthesize(
            workload,
            cfo_ceiling=decision.estimated_token_budget,
            commit_playbook=True,
        )
        self.record_cycle(
            schema_divergence=0 if report.under_budget else 1,
            token_spend=report.tokens,
            token_ceiling=decision.estimated_token_budget,
            delta_t=report.duration_ms / 1000.0,
            structural_drift=0.0 if report.under_budget else 0.25,
            quality=report.quality,
            path="global_synthesis",
            notes=workload[:80],
        )
        if report.playbook_committed:
            self.playbook.append(f"Committed global report {report.report_id}")
        envelope["result"] = report.model_dump()
        from .retrieval_port import RetrievalPort
        envelope["retrieval"] = RetrievalPort(
            muscle=self._muscle, kg=self._kg
        ).retrieve(
            workload, mode="global", token_budget=decision.estimated_token_budget
        ).to_dict()
        issues = []
        if not report.under_budget:
            issues.append("cfo_ceiling_breach")
        if report.quality < 0.90:
            issues.append("global_quality_below_gate")
        if not report.communities:
            issues.append("no_community_maps")
        envelope["rhythm_audit"] = self._hybrid_rhythm_gate(
            marker="hybrid_global",
            quality=report.quality,
            issues=issues,
        )
        return envelope

    def _hybrid_rhythm_gate(
        self,
        *,
        marker: str,
        quality: float,
        issues: List[str],
        threshold: float = 0.90,
    ) -> Dict[str, Any]:
        """ST-04 Rhythm Marker gate for hybrid lanes (maker-checker JSON only)."""
        from .vectors import RhythmAudit

        passed = quality >= threshold and not issues
        audit = RhythmAudit(
            marker=marker,
            charter_id=f"hybrid:{marker}",
            quality=float(quality),
            threshold=threshold,
            passed=passed,
            remediation_loops=0 if passed else 1,
            blocking_issues=tuple(issues),
        )
        payload = audit.to_dict()
        self.playbook.append(
            f"RhythmAudit {marker} passed={passed} Q={quality:.3f}"
        )
        return payload

    def hybrid_stats(self) -> Dict[str, Any]:
        self._ensure_hybrid_stack()
        assert self._hybrid_router is not None
        assert self._multi_hop is not None
        assert self._synthesis is not None
        return {
            "router": self._hybrid_router.route_stats(),
            "multi_hop": self._multi_hop.stats(),
            "synthesis": self._synthesis.stats(),
            "routes_logged": len(self.route_log),
            "entanglement_errors": self.entanglement_errors,
            "cfo_ceiling": self.cfo_ceiling,
        }

    # ------------------------------------------------------------------ v1.8
    def _ensure_v18_stack(self) -> None:
        if self._swarm is not None and self._headhunter is not None:
            return
        from .headhunter import HeadhunterProtocol
        from .swarm_manager import SwarmManager

        if self._swarm is None:
            self._swarm = SwarmManager(
                cfo_ceiling=max(self.cfo_ceiling, 5000),
                max_workers=8,
                quiet=True,
            )
        if self._headhunter is None:
            self._headhunter = HeadhunterProtocol(quiet=True)

    def run_swarm(
        self,
        dataset: Any,
        *,
        max_workers: Optional[int] = None,
        cfo_ceiling: Optional[int] = None,
    ) -> Dict[str, Any]:
        """v1.8 SwarmManager entry — parallel dataset under CFO ceiling."""
        self._ensure_v18_stack()
        assert self._swarm is not None
        ceiling = int(cfo_ceiling if cfo_ceiling is not None else self.cfo_ceiling)
        report = self._swarm.run(
            dataset,
            max_workers=max_workers,
            cfo_ceiling=ceiling,
        )
        self.playbook.append(
            f"Swarm {report.swarm_id} ok={report.succeeded}/{report.total} "
            f"tok={report.tokens}/{report.cfo_ceiling}"
        )
        self.record_cycle(
            schema_divergence=report.failed,
            token_spend=report.tokens,
            token_ceiling=report.cfo_ceiling,
            delta_t=report.wall_ms / 1000.0,
            structural_drift=0.05 * report.failed,
            quality=report.quality,
            path="swarm",
            notes=report.swarm_id,
        )
        return report.model_dump()

    async def run_swarm_async(
        self,
        dataset: Any,
        *,
        max_workers: Optional[int] = None,
        cfo_ceiling: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Async swarm path — safe inside FastAPI event loop."""
        self._ensure_v18_stack()
        assert self._swarm is not None
        ceiling = int(cfo_ceiling if cfo_ceiling is not None else self.cfo_ceiling)
        report = await self._swarm.run_async(
            dataset,
            max_workers=max_workers,
            cfo_ceiling=ceiling,
        )
        self.playbook.append(
            f"SwarmAsync {report.swarm_id} ok={report.succeeded}/{report.total}"
        )
        return report.model_dump()

    def requisition_new_talent(
        self,
        *,
        fired: "Agent",
        roster: List["Agent"],
        muscle: Optional["MuscleMemoryVectorDB"] = None,
        force: bool = False,
        force_capability: Optional[str] = None,
    ) -> Dict[str, Any]:
        """v1.8 Headhunter Protocol — generate / sandbox / hire after TPC fire."""
        self._ensure_v18_stack()
        assert self._headhunter is not None
        if muscle is None:
            self._ensure_hybrid_stack()
            muscle = self._muscle
        decision = self._headhunter.requisition_new_talent(
            fired=fired,
            roster=roster,
            muscle=muscle,
            force=force,
            force_capability=force_capability,
        )
        blob = decision.model_dump()
        self.headhunter_log.append(blob)
        self.playbook.append(
            f"Headhunter {decision.decision_id}: {decision.reason} "
            f"for {fired.name}"
        )
        return blob

    def _maybe_headhunt_after_fire(
        self,
        *,
        fired: "Agent",
        team: List["Agent"],
        muscle_memory_records: int,
    ) -> None:
        """Invoke Headhunter when Muscle-Memory cannot absorb the load."""
        self._ensure_v18_stack()
        assert self._headhunter is not None
        # Lean rehire already recorded; Headhunter decides absorb vs hire
        muscle = None
        try:
            self._ensure_hybrid_stack()
            muscle = self._muscle
        except Exception:  # noqa: BLE001
            muscle = None
        # Force hire path when muscle store is thin
        force = muscle_memory_records < self._headhunter.muscle_absorb_threshold
        decision = self._headhunter.requisition_new_talent(
            fired=fired,
            roster=team,
            muscle=muscle,
            force=force,
        )
        self.headhunter_log.append(decision.model_dump())
        self.playbook.append(
            f"Headhunter post-fire {fired.name}: {decision.reason}"
        )

    def v18_stats(self) -> Dict[str, Any]:
        self._ensure_v18_stack()
        assert self._swarm is not None
        assert self._headhunter is not None
        return {
            "version": "2.0.0",
            "swarm": self._swarm.stats(),
            "headhunter": self._headhunter.stats(),
            "headhunter_log_len": len(self.headhunter_log),
            "cfo_ceiling": self.cfo_ceiling,
        }

    def monday_morning_sync(
        self,
        team: List[Agent],
        *,
        benchmark: float = INDUSTRY_BENCHMARK,
        rng: Optional[random.Random] = None,
        muscle_memory_records: int = 0,
        lean_rehire: bool = True,
        dossier: Optional["RosterRecommendationDossier"] = None,
    ) -> Dict[str, str]:
        """ST-07 — prefer Analytics Chief 5-day dossier over local guesses.

        When ``dossier`` is provided, the GM **executes** Board recommendations.
        Fallback (no dossier): legacy fitness/ledger pruning.
        """
        if dossier is not None:
            return self._execute_dossier(
                team,
                dossier,
                muscle_memory_records=muscle_memory_records,
                lean_rehire=lean_rehire,
            )
        return self._legacy_fitness_sync(
            team,
            benchmark=benchmark,
            rng=rng,
            muscle_memory_records=muscle_memory_records,
            lean_rehire=lean_rehire,
        )

    def _execute_dossier(
        self,
        team: List[Agent],
        dossier: "RosterRecommendationDossier",
        *,
        muscle_memory_records: int,
        lean_rehire: bool,
    ) -> Dict[str, str]:
        """Execute RosterRecommendationDossier — zero local guessing."""
        outcomes: Dict[str, str] = {}
        self.rehire_log = []
        self.last_dossier_id = dossier.dossier_id
        action_map = dossier.action_map()
        by_name = {a.name: a for a in team if not isinstance(a, BossAgent)}

        self.playbook.append(
            f"Ingest dossier {dossier.dossier_id} "
            f"(week={dossier.week_index}, days={dossier.days_covered})"
        )

        for name, action in action_map.items():
            agent = by_name.get(name)
            if agent is None:
                continue
            if not getattr(agent, "talent_eligible", True):
                continue

            if action == "TERMINATE":
                agent.status = AgentStatus.FIRED
                agent.survival_status = SurvivalStatus.TERMINATED
                agent.corporate_rank = 0.0
                agent.refresh_survival_prompt()
                outcomes[name] = "FIRED"
                self.playbook.append(f"Board TERMINATE {name} via {dossier.dossier_id}")
                if lean_rehire:
                    surviving = sum(
                        1
                        for a in team
                        if not isinstance(a, BossAgent)
                        and a.status
                        in (
                            AgentStatus.ACTIVE,
                            AgentStatus.PROMOTED,
                            AgentStatus.PHANTOM,
                        )
                        and getattr(a, "talent_eligible", True)
                    )
                    decision = lean_rehire_check(
                        agent_name=name,
                        surviving_ops=surviving,
                        muscle_memory_records=muscle_memory_records,
                    )
                    self.rehire_log.append(decision)
                # v1.8 Headhunter — absorb or requisition
                self._maybe_headhunt_after_fire(
                    fired=agent,
                    team=team,
                    muscle_memory_records=muscle_memory_records,
                )
            elif action == "PROMOTE":
                agent.status = AgentStatus.PROMOTED
                agent.corporate_rank = min(10.0, agent.corporate_rank + 1.0)
                agent.termination_risk_index = max(0.0, agent.termination_risk_index - 0.08)
                if getattr(agent, "is_phantom", False):
                    agent.is_phantom = False
                agent.refresh_survival_prompt()
                outcomes[name] = "PROMOTED"
                self.playbook.append(f"Board PROMOTE {name} via {dossier.dossier_id}")
            elif action == "DEMOTE":
                agent.status = AgentStatus.DEMOTED
                agent.corporate_rank = max(0.5, agent.corporate_rank - 0.5)
                agent.refresh_survival_prompt()
                outcomes[name] = "DEMOTED"
                self.playbook.append(f"Board DEMOTE {name} via {dossier.dossier_id}")
            else:
                agent.status = AgentStatus.ACTIVE
                agent.refresh_survival_prompt()
                outcomes[name] = "RETAINED"
                self.playbook.append(f"Board RETAIN {name} via {dossier.dossier_id}")

        # Agents not in dossier but on team: retain if active history
        for agent in team:
            if isinstance(agent, BossAgent):
                continue
            if agent.name in outcomes:
                continue
            if not getattr(agent, "talent_eligible", True):
                continue
            if agent.status == AgentStatus.FIRED:
                continue
            outcomes[agent.name] = "RETAINED"

        return outcomes

    def _legacy_fitness_sync(
        self,
        team: List[Agent],
        *,
        benchmark: float,
        rng: Optional[random.Random],
        muscle_memory_records: int,
        lean_rehire: bool,
    ) -> Dict[str, str]:
        """Fallback when no Analytics dossier is available."""
        r = rng or random
        outcomes: Dict[str, str] = {}
        self.rehire_log = []

        for agent in team:
            if isinstance(agent, BossAgent):
                continue
            if not getattr(agent, "talent_eligible", True):
                continue
            if not agent.history and agent.ledger.schema_errors == 0:
                if getattr(agent, "is_phantom", False):
                    agent.status = AgentStatus.FIRED
                    agent.survival_status = SurvivalStatus.TERMINATED
                    outcomes[agent.name] = "FIRED"
                    self.playbook.append(f"Fire unproven phantom {agent.name}")
                continue

            f = agent.calculate_fitness() if agent.history else 0.0
            risk = agent.termination_risk_index
            fire_floor = benchmark * 0.55

            if should_fire_from_ledger(risk, agent.ledger, f, fitness_floor=fire_floor):
                agent.status = AgentStatus.FIRED
                agent.survival_status = SurvivalStatus.TERMINATED
                agent.corporate_rank = 0.0
                agent.refresh_survival_prompt()
                outcomes[agent.name] = "FIRED"
                self.playbook.append(
                    f"Fire {agent.name}: F={f:.3f} risk={risk:.3f} "
                    f"errors={agent.ledger.schema_errors}"
                )
                if lean_rehire:
                    surviving = sum(
                        1
                        for a in team
                        if not isinstance(a, BossAgent)
                        and a.status
                        in (
                            AgentStatus.ACTIVE,
                            AgentStatus.PROMOTED,
                            AgentStatus.PHANTOM,
                        )
                        and getattr(a, "talent_eligible", True)
                    )
                    decision = lean_rehire_check(
                        agent_name=agent.name,
                        surviving_ops=surviving,
                        muscle_memory_records=muscle_memory_records,
                    )
                    self.rehire_log.append(decision)
                self._maybe_headhunt_after_fire(
                    fired=agent,
                    team=team,
                    muscle_memory_records=muscle_memory_records,
                )
                continue

            if getattr(agent, "is_phantom", False) and f >= benchmark * 1.15:
                agent.status = AgentStatus.PROMOTED
                agent.is_phantom = False
                agent.termination_risk_index = max(0.0, agent.termination_risk_index - 0.3)
                agent.refresh_survival_prompt()
                outcomes[agent.name] = "PHANTOM_HIRED"
                continue

            if f >= benchmark * 1.2 and risk < 0.35:
                agent.status = AgentStatus.PROMOTED
                agent.corporate_rank = min(10.0, agent.corporate_rank + 1.0)
                agent.termination_risk_index = max(0.0, agent.termination_risk_index - 0.08)
                agent.refresh_survival_prompt()
                outcomes[agent.name] = "PROMOTED"
            elif f < benchmark * 0.75 or risk >= 0.55:
                agent.status = AgentStatus.DEMOTED
                agent.corporate_rank = max(0.5, agent.corporate_rank - 0.5)
                agent.refresh_survival_prompt()
                outcomes[agent.name] = "DEMOTED"
            else:
                agent.status = AgentStatus.ACTIVE
                for p in list(agent.muscle_memory_weights.keys()):
                    agent.muscle_memory_weights[p] = max(
                        0.1,
                        agent.muscle_memory_weights.get(p, 1.0) + r.uniform(-0.05, 0.12),
                    )
                agent.refresh_survival_prompt()
                outcomes[agent.name] = "RETAINED"
        return outcomes

    def rehire_export(self) -> List[Dict[str, Any]]:
        return [d.to_dict() for d in self.rehire_log]

    # ------------------------------------------------------------------
    # v2.1 Coach Trust — pending charter state machine
    # ------------------------------------------------------------------

    def register_pending_charter(self, draft_public: Dict[str, Any]) -> None:
        """Hold synthesized draft until Head Coach approves (no execute)."""
        draft_id = str(draft_public.get("draft_id") or "")
        if not draft_id:
            return
        self.pending_charters[draft_id] = {
            **draft_public,
            "status": "PENDING_COACH_APPROVAL",
            "boss": self.name,
        }
        self.charter_synthesis_log.append(
            {
                "event": "synthesize",
                "draft_id": draft_id,
                "goal": draft_public.get("goal"),
                "cfo_passed": (draft_public.get("cfo_audit") or {}).get("passed"),
            }
        )
        self.playbook.append(
            f"Pending coach approval: {draft_id} — {draft_public.get('playbook_name')}"
        )

    def clear_pending_charter(self, draft_id: str) -> None:
        self.pending_charters.pop(draft_id, None)

    def pending_charter_ids(self) -> List[str]:
        return list(self.pending_charters.keys())

    def assert_no_unapproved_execute(self, draft_id: Optional[str] = None) -> None:
        """Hard gate: refuse execute while draft still pending."""
        if draft_id and draft_id in self.pending_charters:
            st = self.pending_charters[draft_id].get("status")
            if st == "PENDING_COACH_APPROVAL":
                raise RuntimeError(
                    f"Charter {draft_id} is PENDING_COACH_APPROVAL — "
                    "POST /system/approve-charter first"
                )


# Architectural alias (reference engine naming)
WorkerNode = Agent
