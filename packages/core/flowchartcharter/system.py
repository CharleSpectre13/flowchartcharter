from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Sequence

from .agents import Agent, AgentStatus, BossAgent
from .analytics import AnalyticsChief
from .blackboard import Blackboard, TaskRequest
from .charter import Charter, FlowUnit
from .elastic import ElasticRequisitionBoard
from .executive import ExecutiveBoard
from .foundations import blueprint_export
from .knowledge_graph import KnowledgeGraph
from .living_playbook import LivingPlaybook, seed_living_playbook
from .metrics import ExecutionMetrics
from .muscle_memory import (
    ExecutionMemoryRecord,
    MuscleMemoryVectorDB,
    seed_legacy_refactor,
)
from .production import ProductionMuscleMemory, LLMExecutionClient
from .playbook_compiler import PlaybookCompiler, run_compiled_playbook
from .state_persister import get_persister
import os
from .quantum import (
    DEFAULT_PATHS,
    QuantumRouter,
    contextual_entropy,
    quantum_path_select,
)
from .skills import (
    AgentSkillRuntime,
    MuscleMemoryRecord,
    MuscleMemoryStore,
    init_boss_agent,
)
from .synergy import mean_pair_synergy


class FlowChartCharterSystem:
    """Facade: ST-01…ST-07 + Living Playbook + Ascension + Survival."""

    PATHS = DEFAULT_PATHS

    def __init__(
        self,
        head_coach: str = "Human Systems Engineer",
        seed: Optional[int] = None,
        *,
        deterministic_routing: bool = True,
        model_class: str = "generic",
    ):
        self.head_coach = head_coach
        self.rng = random.Random(seed)
        self.boss, self.boss_ack = init_boss_agent("Alpha-GM")
        self.executives = ExecutiveBoard()
        self.knowledge = KnowledgeGraph()
        self.blueprint = blueprint_export()
        self.router = QuantumRouter(
            paths=self.PATHS,
            deterministic=deterministic_routing,
            rng=self.rng,
            quality_floor=0.90,
            lr=0.12,
            path_costs=dict(self.executives.cfo.path_costs),
        )
        if os.environ.get("FCC_VECTOR_BACKEND", "memory").lower() in (
            "qdrant",
            "pinecone",
            "production",
            "auto",
        ):
            self.muscle_db = ProductionMuscleMemory.from_env(quiet=True)
            # seed via classic adapter if production has storage
            if hasattr(self.muscle_db, "storage"):
                seed_legacy_refactor(self.muscle_db)  # type: ignore[arg-type]
        else:
            self.muscle_db = MuscleMemoryVectorDB(quiet=True)
            seed_legacy_refactor(self.muscle_db)
        self.memory_store = MuscleMemoryStore(self.muscle_db)
        self.playbook = LivingPlaybook(
            model_class=model_class,
            quiet=True,
            ascension_threshold=12,
        )
        seed_living_playbook(self.playbook)
        self.elastic = ElasticRequisitionBoard()
        self.analytics = AnalyticsChief()
        self.roster: List[Agent] = [
            Agent(
                "Worker-1",
                "Key Player - Data Extraction",
                {"extraction": 1.0, "json_parsing": 0.9, "general": 0.5},
            ),
            Agent(
                "Worker-2",
                "Key Player - Validation",
                {"validation": 1.0, "json_parsing": 0.8, "general": 0.5},
            ),
            Agent(
                "Worker-3",
                "Position Manager - Synthesizer",
                {
                    "synthesis": 1.0,
                    "python_ast": 0.9,
                    "refactoring": 0.8,
                    "general": 0.6,
                },
            ),
            Agent("Auditor-1", "Audit Manager", {"audit": 1.0, "general": 0.4}),
            self.executives.validator,
        ]
        for a in self.roster:
            self.elastic.register_agent(a)
        self.roster[0].muscle_memory_weights = {
            "path_A": 1.4,
            "path_B": 0.9,
            "path_lite": 0.8,
        }
        self.roster[1].muscle_memory_weights = {
            "path_A": 1.0,
            "path_B": 1.2,
            "path_lite": 0.9,
        }
        self.roster[2].muscle_memory_weights = {
            "path_A": 1.5,
            "path_B": 0.7,
            "path_lite": 1.0,
        }
        self.skills = AgentSkillRuntime(
            router=self.router,
            store=self.memory_store,
            db=self.muscle_db,
            boss=self.boss,
            roster=self.roster,
        )
        self.blackboard = Blackboard()
        self.checkpointer: List[Dict[str, Any]] = []
        self.last_trust = False
        self.token_budget = 50_000
        self.token_spend = 0
        # Live-Wire: always route ops through LLMExecutionClient
        # (mock provider offline; real provider when FCC_LLM_PROVIDER set)
        self.live_wire = os.environ.get("FCC_LIVE_WIRE", "1") != "0"
        self.llm_client = LLMExecutionClient()
        self.last_live_wire: Dict[str, Any] = {}
        self.compiler = PlaybookCompiler()
        self.compiled_playbook = None
        self.active_playbook_id = None
        self.playbook_routing: Dict[str, Any] = {}
        self.playbook_flow_path: List[str] = []
        self.persister = get_persister()
        self.memory_store.add(
            MuscleMemoryRecord(
                charter_id="seed-migration",
                path="path_A",
                state_vector=(0.8, 0.2, 0.1, 0.9),
                quality=0.96,
                token_cost=180,
                tags=("migration", "clean"),
            )
        )
        self.memory_store.add(
            MuscleMemoryRecord(
                charter_id="seed-messy",
                path="path_B",
                state_vector=(0.2, 0.9, 0.85, 0.3),
                quality=0.93,
                token_cost=340,
                tags=("cleansing", "high-entropy"),
            )
        )

    def roster_capability_map(self) -> Dict[str, float]:
        caps: Dict[str, float] = {}
        for a in self.roster:
            if a.status == AgentStatus.FIRED:
                continue
            for k, v in a.capability_vector.items():
                caps[k] = max(caps.get(k, 0.0), float(v))
            for c in getattr(a, "capabilities", []):
                caps.setdefault(c, 0.7)
        return caps

    def upgrade_personnel(self, new_model_class: str) -> Dict[str, Any]:
        """Cross-generational playbook translation (e.g. 70B → 1T)."""
        result = self.playbook.upgrade_generation(
            new_model_class,
            self.roster_capability_map(),
        )
        self.boss.playbook.append(
            f"Personnel upgrade → {new_model_class}; "
            f"remapped {result['remapped_count']} trajectories"
        )
        return result

    def quantum_path_selection(self, agent: Agent, paths: Sequence[str]) -> str:
        result = self.router.route_agent(
            charter_id="adhoc",
            agent_name=agent.name,
            muscle_memory=agent.muscle_memory_weights,
            marker="adhoc",
        )
        return str(result["chosen_path"])

    def quantum_path_detail(self, agent: Agent, paths: Sequence[str]) -> Dict[str, object]:
        return quantum_path_select(
            paths or self.PATHS,
            agent.muscle_memory_weights,
            rng=self.rng,
            deterministic=self.router.deterministic,
            agent=agent.name,
        )

    def _audit_quality(self, metrics: List[ExecutionMetrics]) -> float:
        if not metrics:
            return 0.0
        return sum(m.quality_score for m in metrics) / len(metrics)

    def _token_sum(self, metrics: List[ExecutionMetrics]) -> int:
        return sum(m.token_cost for m in metrics)

    def _is_ops(self, agent: Agent) -> bool:
        if agent.status not in (
            AgentStatus.ACTIVE,
            AgentStatus.PROMOTED,
            AgentStatus.PHANTOM,
        ):
            if not (getattr(agent, "is_phantom", False) and agent.status != AgentStatus.FIRED):
                return False
        role = agent.role
        if any(x in role for x in ("Audit", "Validator", "Chief", "Board", "General Manager")):
            return False
        return True

    def _payload_entropy(self, workload_name: str) -> float:
        lower = workload_name.lower()
        base = 0.25
        if any(k in lower for k in ("security", "audit", "messy", "legacy", "migration")):
            base = 0.72
        elif any(k in lower for k in ("api", "integration", "realtime", "telemetry")):
            base = 0.45
        elif "sql" in lower or "novel" in lower:
            base = 0.85
        noise = self.rng.uniform(-0.08, 0.08)
        return max(0.0, min(1.0, base + noise))

    def _per_agent_ceiling(self) -> int:
        ops = max(1, sum(1 for a in self.roster if self._is_ops(a)))
        return max(200, int((self.token_budget - self.token_spend) / ops))

    def _path_to_router(self, flow_path: List[str], h_ctx: float) -> str:
        """Map playbook unit ids onto path_A/B/lite for local execution."""
        joined = " ".join(flow_path).lower()
        if any(k in joined for k in ("clean", "sanit", "messy")):
            return "path_B"
        if "lite" in joined:
            return "path_lite"
        if h_ctx >= 0.55:
            return "path_B"
        return "path_A"

    def execute_charter(
        self,
        workload_name: str,
        *,
        force_quality: Optional[float] = None,
        context_entropy: Optional[float] = None,
        payload: Optional[Dict[str, Any]] = None,
        force_capability: Optional[str] = None,
        force_zero_shot: bool = False,
    ) -> Dict[str, Any]:
        """ST-01..ST-06 + Living Playbook ascension + Muscle-Memory."""
        self.router.history.clear()
        self.router._pending.clear()

        h_ctx = (
            context_entropy
            if context_entropy is not None
            else (contextual_entropy(payload) if payload else self._payload_entropy(workload_name))
        )

        phantom = self.elastic.evaluate(
            workload_name,
            self.roster,
            force_capability=force_capability,
        )
        if phantom is not None:
            self.skills.roster = self.roster

        charter = Charter(
            name=workload_name,
            units=[
                FlowUnit("ST-01", "Init", "start"),
                FlowUnit("ST-02", "Bind", "bind"),
                FlowUnit("ST-03", "Execute", "superstep"),
                FlowUnit("ST-04", "Audit", "gate", exit_threshold=0.90),
                FlowUnit("ST-05", "Remediate", "loop"),
                FlowUnit("ST-06", "Synthesize", "handoff"),
            ],
        )
        strategy = self.executives.ceo.issue_strategy(
            workload_name, budget_cap_tokens=self.token_budget
        )
        self.blackboard.post_vector(strategy)
        self.blackboard.active_jobs.append(workload_name)
        self.blackboard.post(
            TaskRequest(
                "t-extract",
                f"{workload_name}:extract",
                {"extraction": 1.0, "general": 0.2},
            )
        )
        self.blackboard.post(
            TaskRequest(
                "t-validate",
                f"{workload_name}:validate",
                {"validation": 1.0, "general": 0.2},
            )
        )
        self.blackboard.post(
            TaskRequest(
                "t-synth",
                f"{workload_name}:synth",
                {"synthesis": 1.0, "general": 0.2},
            )
        )

        assignments = self.blackboard.volunteer_bind(self.roster)
        ceiling = self._per_agent_ceiling()

        state_vec = [h_ctx, 1.0 - h_ctx, 0.5, strategy.priority]
        payload_for_mm = payload or {
            "task": workload_name,
            "h_ctx": h_ctx,
            "priority": strategy.priority,
        }

        # Living Playbook: hit | zero_shot | miss
        living = self.playbook.synthesize_charter(
            payload_for_mm,
            entropy=h_ctx,
            force_zero_shot=force_zero_shot,
        )
        precedent = self.skills.QueryMuscleMemory(state_vec, threshold=0.70, payload=payload_for_mm)
        trajectory = self.muscle_db.query_muscle_memory(
            payload_for_mm,
            similarity_threshold=0.70,
            state_vector=state_vec,
        )

        living_hit = living["mode"] in ("hit", "zero_shot") and living.get("path")
        accelerated = living_hit or trajectory is not None

        collected: List[ExecutionMetrics] = []
        path_trace: Dict[str, Any] = {}
        agent_qualities: List[float] = []
        cfo_reports: List[Dict[str, Any]] = []
        schema_results: List[Dict[str, Any]] = []
        divergences: List[float] = []
        survival_snaps: List[Dict[str, Any]] = []
        remaining = float(self.token_budget - self.token_spend)

        for agent in self.roster:
            if not self._is_ops(agent):
                continue

            _, cfo_report = self.executives.cfo.pre_collapse_gate(
                token_spend=self.token_spend + self._token_sum(collected),
                token_budget=self.token_budget,
                muscle_memory=agent.muscle_memory_weights,
            )
            cfo_reports.append({"agent": agent.name, **cfo_report})
            agent.refresh_survival_prompt()

            if living_hit and living.get("path"):
                flow_path = list(living["path"])
                path = self._path_to_router(flow_path, h_ctx)
                collapse = {
                    "chosen_path": path,
                    "source": f"living_playbook:{living['mode']}",
                    "memory_id": living.get("memory_id"),
                    "prompt_tweak": living.get("prompt_tweak") or "",
                    "flow_path": flow_path,
                    "post_measurement": {"confidence": 1.0, "entropy": 0.0},
                    "pre_measurement": {"entropy": 0.0, "amplitudes": []},
                    "context_entropy": h_ctx,
                    "cfo_forced": False,
                    "ascension": living.get("ascension"),
                    "rationale": living.get("rationale"),
                }
            elif trajectory is not None:
                path = trajectory.successful_flow_path[0]
                if path not in self.PATHS and not path.startswith("path_"):
                    path = "path_A" if h_ctx < 0.5 else "path_B"
                collapse = {
                    "chosen_path": path,
                    "source": "muscle_memory",
                    "memory_id": trajectory.memory_id,
                    "prompt_tweak": trajectory.prompt_tweak,
                    "flow_path": list(trajectory.successful_flow_path),
                    "post_measurement": {"confidence": 1.0, "entropy": 0.0},
                    "pre_measurement": {"entropy": 0.0, "amplitudes": []},
                    "context_entropy": h_ctx,
                    "cfo_forced": False,
                }
            else:
                collapse = self.skills.ExecuteQuantumCollapse(
                    list(self.PATHS),
                    context_entropy=h_ctx,
                    muscle_memory=agent.muscle_memory_weights,
                    agent_name=agent.name,
                    charter_id=workload_name,
                    path_costs=self.executives.cfo.path_costs,
                    remaining_budget=remaining - self._token_sum(collected),
                    margin=self.executives.cfo.reserve_margin,
                )
                path = str(collapse["chosen_path"])

            bias = 0.0 if force_quality is None else (force_quality - 0.85)
            if path == "path_B" and h_ctx >= 0.55:
                bias += 0.06
            elif path == "path_A" and h_ctx < 0.4:
                bias += 0.04
            elif path == "path_lite":
                bias -= 0.03
            if accelerated:
                bias += 0.05
            if living.get("mode") == "zero_shot":
                bias += 0.03  # synthesized chart still high confidence
            if getattr(agent, "is_phantom", False):
                bias += 0.08

            schema_ok_hint = agent.termination_risk_index < 0.55
            exec_path = path if path in ("path_A", "path_B", "path_lite") else "path_A"
            # Live-Wire production path (TPC inject + Pydantic schema gate)
            if self.live_wire and force_quality is None:
                constraints = list(getattr(agent, "playbook_constraints", []))
                if living.get("prompt_tweak"):
                    constraints.append(str(living["prompt_tweak"]))
                if trajectory is not None and trajectory.prompt_tweak:
                    constraints.append(trajectory.prompt_tweak)
                m = agent.execute_live(
                    f"{workload_name} via {path}",
                    path=exec_path,
                    playbook_constraints=constraints or None,
                )
                collapse = {
                    **collapse,
                    "live_wire": True,
                    "provider": getattr(agent.llm_client.bridge.config, "provider", "mock"),
                }
            else:
                m = agent.execute_flow_unit(
                    f"{workload_name} via {path}",
                    rng=self.rng,
                    quality_bias=bias,
                    path=exec_path,
                    token_ceiling=ceiling,
                    expected_schema_ok=schema_ok_hint or accelerated,
                )
            if m:
                collected.append(m)
                agent_qualities.append(m.quality_score)
                if not accelerated:
                    agent.muscle_memory_weights = self.router.observe(
                        agent.name,
                        agent.muscle_memory_weights,
                        m.quality_score,
                    )
                output = {
                    "result": "ok",
                    "quality": m.quality_score,
                    "path": path,
                    "tokens": m.token_cost,
                }
                expected = {
                    "result": "ok",
                    "quality": 0.9,
                    "path": "path_A",
                    "tokens": 100,
                }
                eval_rm = self.skills.EvaluateRhythmMarker(output, expected)
                schema_results.append(eval_rm)
                divergences.append(float(eval_rm["D"]))
                if not eval_rm.get("passed", True):
                    agent.record_cycle(
                        schema_divergence=1,
                        token_spend=0,
                        token_ceiling=ceiling,
                        delta_t=0.1,
                        structural_drift=float(eval_rm.get("D", 0.5)),
                        quality=m.quality_score,
                        path=path,
                        notes="rhythm_marker_fail",
                    )

            path_trace[agent.name] = {
                **collapse,
                "termination_risk_index": agent.termination_risk_index,
                "survival_status": agent.survival_status.value,
                "generation": agent.generation.to_dict(),
                "is_phantom": getattr(agent, "is_phantom", False),
            }
            survival_snaps.append(agent.survival_snapshot())

        quality = force_quality if force_quality is not None else self._audit_quality(collected)
        mean_qs = (
            sum(float(s["Q_s"]) for s in schema_results) / len(schema_results)
            if schema_results
            else 1.0
        )
        schema_ok = all(s.get("passed", True) for s in schema_results) if schema_results else True

        audit = self.executives.validator.audit(
            workload_name,
            marker="gate",
            quality=quality,
            threshold=0.90,
            remediation_loops=0,
            schema_ok=schema_ok,
            qs=mean_qs,
        )
        self.blackboard.post_vector(audit)
        charter.state.quality_score = quality

        while not audit.passed and charter.state.remediation_loops < charter.state.max_remediation:
            charter.state.remediation_loops += 1
            batch_q: List[float] = []
            for agent in self.roster:
                if not self._is_ops(agent):
                    continue
                agent.refresh_survival_prompt()
                collapse = self.skills.ExecuteQuantumCollapse(
                    list(self.PATHS),
                    context_entropy=h_ctx,
                    muscle_memory=agent.muscle_memory_weights,
                    agent_name=agent.name,
                    charter_id=workload_name,
                    path_costs=self.executives.cfo.path_costs,
                    remaining_budget=remaining - self._token_sum(collected),
                    margin=self.executives.cfo.reserve_margin,
                )
                path = str(collapse["chosen_path"])
                m = agent.execute_flow_unit(
                    f"{workload_name} remediate#" f"{charter.state.remediation_loops} via {path}",
                    rng=self.rng,
                    quality_bias=0.15,
                    path=path,
                    token_ceiling=ceiling,
                    expected_schema_ok=True,
                )
                if m:
                    collected.append(m)
                    batch_q.append(m.quality_score)
                    agent.muscle_memory_weights = self.router.observe(
                        agent.name,
                        agent.muscle_memory_weights,
                        m.quality_score,
                    )
                path_trace[f"{agent.name}#r{charter.state.remediation_loops}"] = collapse
            quality = self._audit_quality(collected[-3:]) if collected else quality
            if batch_q:
                agent_qualities.extend(batch_q)
            audit = self.executives.validator.audit(
                workload_name,
                marker="gate",
                quality=quality,
                threshold=0.90,
                remediation_loops=charter.state.remediation_loops,
                schema_ok=True,
                qs=1.0,
            )
            self.blackboard.post_vector(audit)
            charter.state.quality_score = quality

        spend = self._token_sum(collected)
        self.token_spend += spend
        budget_vec = self.executives.cfo.issue_budget(
            workload_name,
            token_spend=self.token_spend,
            token_budget=self.token_budget,
        )
        self.blackboard.post_vector(budget_vec)

        trust = audit.passed and quality >= 0.90
        gov = self.executives.board.review_hand_off(workload_name, trust=trust, quality=quality)
        self.blackboard.post_vector(gov)
        charter.state.trust_signal = gov.approve_hand_off
        self.last_trust = gov.approve_hand_off

        entanglement = mean_pair_synergy(agent_qualities, divergences)
        router_summary = self.router.summary()

        flow_path_used: List[str] = []
        if living_hit and living.get("path"):
            flow_path_used = list(living["path"])
        elif trajectory is not None:
            flow_path_used = list(trajectory.successful_flow_path)
        else:
            for v in path_trace.values():
                if isinstance(v, dict) and v.get("chosen_path"):
                    flow_path_used.append(str(v["chosen_path"]))

        if trust and quality >= 0.90:
            self.muscle_db.commit_memory(
                ExecutionMemoryRecord(
                    memory_id=f"MEM-{workload_name[:12].replace(' ', '')}",
                    job_type=workload_name,
                    state_vector=list(state_vec),
                    successful_flow_path=flow_path_used or ["path_A"],
                    entanglement_score=min(1.0, max(0.0, entanglement)),
                    prompt_tweak=str(living.get("prompt_tweak") or ""),
                    quality=quality,
                    token_cost=spend,
                    tags=(workload_name.split()[0].lower(),),
                )
            )
            # Living playbook commit (why it worked + capability map)
            self.playbook.commit_from_execution(
                job_type=workload_name,
                flow_path=flow_path_used or ["path_A"],
                payload=payload_for_mm,
                quality=quality,
                token_cost=spend,
                expected_tokens=max(200, spend // max(1, len(collected) or 1)),
                actual_time=1.0,
                expected_time=1.2,
                entanglement=entanglement,
                schema_ok=schema_ok,
                prompt_tweak=str(living.get("prompt_tweak") or ""),
                agent_caps=self.roster_capability_map(),
                entropy=h_ctx,
                muscle_db=self.muscle_db,
                rationale=(f"trust={trust} Q={quality:.3f} mode={living.get('mode')}"),
            )

        snap: Dict[str, Any] = {
            "workload": workload_name,
            "quality": quality,
            "trust": gov.approve_hand_off,
            "remediation_loops": charter.state.remediation_loops,
            "assignments": assignments,
            "metrics_count": len(collected),
            "token_spend": self.token_spend,
            "rhythm_audit": audit.to_dict(),
            "governance": gov.to_dict(),
            "budget_halt": budget_vec.halt_if_over,
            "quantum_paths": path_trace,
            "quantum_summary": router_summary,
            "entanglement": round(entanglement, 4),
            "Q_s_mean": round(mean_qs, 4),
            "context_entropy": round(h_ctx, 4),
            "cfo_gates": cfo_reports,
            "precedent": precedent,
            "muscle_memory_hit": trajectory is not None,
            "muscle_memory_id": trajectory.memory_id if trajectory else None,
            "living_playbook": living,
            "playbook_mode": living.get("mode"),
            "ascension": living.get("ascension"),
            "prompt_tweak": living.get("prompt_tweak")
            or (trajectory.prompt_tweak if trajectory else None),
            "flow_path_reused": flow_path_used or None,
            "muscle_db_stats": self.muscle_db.stats(),
            "playbook_export": {
                "records": len(self.playbook.records),
                "horizon": self.playbook.horizon_reached,
                "iteration": self.playbook.evolution_iteration,
                "model_class": self.playbook.model_class,
            },
            "schema_audits": schema_results,
            "survival": survival_snaps,
            "phantom_spawned": phantom.name if phantom else None,
            "live_wire": self.live_wire,
            "llm_provider": self.llm_client.bridge.config.provider,
            "elastic": self.elastic.export(),
            "boss_prompt_loaded": bool(self.boss.system_prompt),
            "foundations_ref": (
                "charter|living_playbook|ascension|muscle_memory|" "fear_survival|elastic_phantom"
            ),
        }
        # Analytics Chief — immutable cycle handoff (async ledger)
        self.analytics.ingest_cycle(
            agents=self.roster,
            workload=workload_name,
            path_trace=path_trace,
            quality=quality,
            flow_path=flow_path_used,
        )
        snap["analytics"] = {
            "days_ready": self.analytics.days_ready(),
            "day_counter": self.analytics.day_counter,
            "workweek_complete": self.analytics.workweek_complete(),
        }
        self.checkpointer.append(snap)
        self.blackboard.completed_jobs.append(workload_name)
        if workload_name in self.blackboard.active_jobs:
            self.blackboard.active_jobs.remove(workload_name)
        charter.bump()
        try:
            self.persist_state()
        except Exception:
            pass
        return snap

    def downtime_sync(self, telemetry: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        tel = telemetry or {
            "path_stats": {
                "path_A": {"success_rate": 0.92},
                "path_B": {"success_rate": 0.88},
                "path_lite": {"success_rate": 0.80},
            },
            "successful_runs": [
                {
                    "charter_id": s["workload"],
                    "path": (s.get("flow_path_reused") or ["path_A"])[0],
                    "flow_path": s.get("flow_path_reused") or ["path_A"],
                    "state_vector": [
                        s.get("context_entropy", 0.3),
                        0.5,
                        0.5,
                        0.7,
                    ],
                    "quality": s["quality"],
                    "entanglement_score": s.get("entanglement", 0.95),
                    "token_cost": 200,
                    "prompt_tweak": s.get("prompt_tweak") or "",
                }
                for s in self.checkpointer
                if s.get("trust")
            ],
        }
        # Close analytics day (each downtime_sync ≈ end of enterprise day)
        self.analytics.close_day()
        dossier = self.analytics.execute_end_of_week_audit(
            muscle_db=self.muscle_db,
            living_playbook=self.playbook,
            force=self.analytics.workweek_complete(),
        )
        mm_count = len(self.muscle_db.storage)
        outcomes = self.boss.monday_morning_sync(
            self.roster,
            rng=self.rng,
            muscle_memory_records=mm_count,
            lean_rehire=True,
            dossier=dossier,
        )
        phantom_outcomes = self.elastic.resolve_phantoms(self.roster)
        skill_result = self.skills.TriggerMondayMorningSync(tel, roster=self.roster, boss=None)
        skill_result["outcomes"] = outcomes
        skill_result["phantom_outcomes"] = phantom_outcomes
        # Ascension tick: evolution iteration advances on sync
        if self.playbook.horizon_reached:
            self.playbook.evolution_iteration += 1
            self.boss.playbook.append(
                f"Ascension active — living playbook iter " f"{self.playbook.evolution_iteration}"
            )

        fitness_snap = {
            a.name: round(a.calculate_fitness(), 4)
            for a in self.roster
            if not isinstance(a, BossAgent) and getattr(a, "talent_eligible", True) and a.history
        }
        survival_board = [
            a.survival_snapshot()
            for a in self.roster
            if not isinstance(a, BossAgent) and getattr(a, "talent_eligible", True)
        ]
        muscle_snapshot = {
            a.name: dict(a.muscle_memory_weights)
            for a in self.roster
            if self._is_ops(a) or a.history
        }
        ops = self.executives.gm_ops_vector(
            "downtime-sync",
            outcomes,
            fitness_snap,
            self.boss.playbook,
        )
        self.blackboard.post_vector(ops)
        last_q = self.checkpointer[-1]["quality"] if self.checkpointer else 0.0
        guidance = self.executives.monday_guidance(
            "downtime-sync",
            token_spend=self.token_spend,
            token_budget=self.token_budget,
            trust=self.last_trust,
            quality=last_q,
        )
        for v in guidance:
            self.blackboard.post_vector(v)

        active_ops = sum(1 for a in self.roster if self._is_ops(a))
        _sync_result = {
            "outcomes": outcomes,
            "ops": ops.to_dict(),
            "guidance": [v.to_dict() for v in guidance],
            "vectors": self.blackboard.recent_vectors(16),
            "muscle_memory": muscle_snapshot,
            "muscle_db": self.muscle_db.export_dict(),
            "living_playbook": self.playbook.export(),
            "dossier": dossier.to_dict() if dossier else None,
            "analytics": self.analytics.export(),
            "dossier_driven": dossier is not None,
            "ascension": self.playbook.horizon_reached,
            "quantum_lifetime": self.router.summary(),
            "skill_sync": skill_result,
            "lean_rehire": self.boss.rehire_export(),
            "phantom_outcomes": phantom_outcomes,
            "elastic": self.elastic.export(),
            "survival_board": survival_board,
            "active_ops_after_prune": active_ops,
            "boss_ack": self.boss_ack,
            "tool_schemas": [s["name"] for s in self.skills.tool_schemas()],
            "blueprint_foundations": [f["name"] for f in self.blueprint["foundations"]],
        }
        try:
            self.persist_state()
        except Exception:
            pass
        return _sync_result

    def persist_state(self) -> str:
        """Serialize engine state to disk (post-workload / post-sync)."""
        return self.persister.save(self)

    def restore_state(self) -> dict:
        """Re-hydrate from FCC_STATE_PATH if present."""
        return self.persister.restore(self)

    def load_playbook(self, source, **kwargs) -> Dict[str, Any]:
        """Compile Charterfile YAML and hydrate GM / roster / CFO state."""
        return self.compiler.compile_and_hydrate(self, source, **kwargs)

    def execute_compiled(self, workload_name: str, **kwargs) -> Dict[str, Any]:
        """Run active compiled playbook units via Live-Wire + dynamic schemas."""
        if self.compiled_playbook is None:
            # fall back to standard charter
            return self.execute_charter(workload_name, **kwargs)
        result = run_compiled_playbook(self, workload_name)
        # analytics ingest for ops agents
        self.analytics.ingest_cycle(
            agents=self.roster,
            workload=workload_name,
            quality=float(result.get("quality") or 0.0),
            flow_path=result.get("flow_path") or [],
        )
        snap = {
            **result,
            "live_wire": self.live_wire,
            "llm_provider": self.llm_client.bridge.config.provider,
            "mode": "compiled_playbook",
            "analytics": {
                "days_ready": self.analytics.days_ready(),
                "day_counter": self.analytics.day_counter,
            },
        }
        self.checkpointer.append(snap)
        try:
            self.persist_state()
        except Exception:
            pass
        return snap

    def ontology_export(self) -> Dict[str, Any]:
        return self.knowledge.export_dict()

    def skill_catalog(self) -> List[Dict[str, Any]]:
        return self.skills.tool_schemas()

    def advance_analytics_day(self) -> int:
        """Seal one analytics day without full talent sync."""
        day = self.analytics.close_day()
        try:
            self.persist_state()
        except Exception:
            pass
        return day

    def run_end_of_week_protocol(self, *, force: bool = False) -> Dict[str, Any]:
        """Analytics Chief EOW audit + GM dossier execution (Monday Sync)."""
        if force and self.analytics.days_ready() < self.analytics.workweek_days:
            # pad empty days for protocol demos
            while self.analytics.days_ready() < self.analytics.workweek_days:
                self.analytics.close_day()
        dossier = self.analytics.execute_end_of_week_audit(
            muscle_db=self.muscle_db,
            living_playbook=self.playbook,
            force=force or self.analytics.workweek_complete(),
        )
        mm_count = len(self.muscle_db.storage)
        outcomes = self.boss.monday_morning_sync(
            self.roster,
            muscle_memory_records=mm_count,
            lean_rehire=True,
            dossier=dossier,
        )
        phantom_outcomes = self.elastic.resolve_phantoms(self.roster)
        return {
            "dossier": dossier.to_dict() if dossier else None,
            "outcomes": outcomes,
            "phantom_outcomes": phantom_outcomes,
            "analytics": self.analytics.export(),
            "lean_rehire": self.boss.rehire_export(),
            "dossier_driven": dossier is not None,
        }
