from __future__ import annotations
import random
from typing import Any, Dict, List, Optional, Sequence
from .agents import Agent, BossAgent, AgentStatus
from .blackboard import Blackboard, TaskRequest
from .charter import Charter, FlowUnit
from .executive import ExecutiveBoard
from .foundations import blueprint_export
from .knowledge_graph import KnowledgeGraph
from .metrics import ExecutionMetrics
from .prompts import BOSS_AGENT_SYSTEM_PROMPT
from .quantum import (
    DEFAULT_PATHS,
    QuantumRouter,
    contextual_entropy,
    quantum_path_select,
)
from .skills import AgentSkillRuntime, MuscleMemoryRecord, MuscleMemoryStore, init_boss_agent
from .synergy import handoff_synergy, mean_pair_synergy


class FlowChartCharterSystem:
    """Facade: ST-01…ST-07 + Tensor Routing + Agent Skills + CFO gate + Brain-1 KG."""

    PATHS = DEFAULT_PATHS

    def __init__(
        self,
        head_coach: str = "Human Systems Engineer",
        seed: Optional[int] = None,
        *,
        deterministic_routing: bool = True,
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
        self.memory_store = MuscleMemoryStore()
        self.roster: List[Agent] = [
            Agent("Worker-1", "Key Player - Data Extraction", {"extraction": 1.0, "general": 0.5}),
            Agent("Worker-2", "Key Player - Validation", {"validation": 1.0, "general": 0.5}),
            Agent("Worker-3", "Position Manager - Synthesizer", {"synthesis": 1.0, "general": 0.6}),
            Agent("Auditor-1", "Audit Manager", {"audit": 1.0, "general": 0.4}),
            self.executives.validator,
        ]
        self.roster[0].muscle_memory_weights = {"path_A": 1.4, "path_B": 0.9, "path_lite": 0.8}
        self.roster[1].muscle_memory_weights = {"path_A": 1.0, "path_B": 1.2, "path_lite": 0.9}
        self.roster[2].muscle_memory_weights = {"path_A": 1.5, "path_B": 0.7, "path_lite": 1.0}
        self.skills = AgentSkillRuntime(
            router=self.router,
            store=self.memory_store,
            boss=self.boss,
            roster=self.roster,
        )
        self.blackboard = Blackboard()
        self.checkpointer: List[Dict[str, Any]] = []
        self.last_trust = False
        self.token_budget = 50_000
        self.token_spend = 0
        # seed a few successful precedents
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
        if agent.status not in (AgentStatus.ACTIVE, AgentStatus.PROMOTED):
            return False
        role = agent.role
        if any(x in role for x in ("Audit", "Validator", "Chief", "Board", "General Manager")):
            return False
        return True

    def _payload_entropy(self, workload_name: str) -> float:
        """Derive H_ctx from workload name hash + optional noise (deterministic per seed)."""
        # Keywords imply messiness
        lower = workload_name.lower()
        base = 0.25
        if any(k in lower for k in ("security", "audit", "messy", "legacy", "migration")):
            base = 0.72
        elif any(k in lower for k in ("api", "integration", "realtime", "telemetry")):
            base = 0.45
        noise = self.rng.uniform(-0.08, 0.08)
        return max(0.0, min(1.0, base + noise))

    def execute_charter(
        self,
        workload_name: str,
        *,
        force_quality: Optional[float] = None,
        context_entropy: Optional[float] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """ST-01..ST-06 with H_ctx routing, CFO pre-collapse gate, skills, RhythmAudit."""
        self.router.history.clear()
        self.router._pending.clear()

        h_ctx = (
            context_entropy
            if context_entropy is not None
            else contextual_entropy(payload) if payload else self._payload_entropy(workload_name)
        )

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
        strategy = self.executives.ceo.issue_strategy(workload_name, budget_cap_tokens=self.token_budget)
        self.blackboard.post_vector(strategy)
        self.blackboard.active_jobs.append(workload_name)
        self.blackboard.post(
            TaskRequest("t-extract", f"{workload_name}:extract", {"extraction": 1.0, "general": 0.2})
        )
        self.blackboard.post(
            TaskRequest("t-validate", f"{workload_name}:validate", {"validation": 1.0, "general": 0.2})
        )
        self.blackboard.post(
            TaskRequest("t-synth", f"{workload_name}:synth", {"synthesis": 1.0, "general": 0.2})
        )

        assignments = self.blackboard.volunteer_bind(self.roster)

        # Muscle-memory precedent for this workload state vector
        state_vec = [h_ctx, 1.0 - h_ctx, 0.5, strategy.priority]
        precedent = self.skills.QueryMuscleMemory(state_vec, threshold=0.75)

        collected: List[ExecutionMetrics] = []
        path_trace: Dict[str, Any] = {}
        agent_qualities: List[float] = []
        cfo_reports: List[Dict[str, Any]] = []
        schema_results: List[Dict[str, Any]] = []
        divergences: List[float] = []

        remaining = float(self.token_budget - self.token_spend)

        for agent in self.roster:
            if not self._is_ops(agent):
                continue

            # CFO budget matrix before collapse
            _, cfo_report = self.executives.cfo.pre_collapse_gate(
                token_spend=self.token_spend + self._token_sum(collected),
                token_budget=self.token_budget,
                muscle_memory=agent.muscle_memory_weights,
            )
            cfo_reports.append({"agent": agent.name, **cfo_report})

            # Skill: ExecuteQuantumCollapse
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

            # Bias quality: cleansing path better when H_ctx high
            bias = 0.0 if force_quality is None else (force_quality - 0.85)
            if path == "path_B" and h_ctx >= 0.55:
                bias += 0.06
            elif path == "path_A" and h_ctx < 0.4:
                bias += 0.04
            elif path == "path_lite":
                bias -= 0.03  # cheaper but slightly lower quality

            m = agent.execute_flow_unit(
                f"{workload_name} via {path}",
                rng=self.rng,
                quality_bias=bias,
                path=path,
            )
            if m:
                collected.append(m)
                agent_qualities.append(m.quality_score)
                agent.muscle_memory_weights = self.router.observe(
                    agent.name,
                    agent.muscle_memory_weights,
                    m.quality_score,
                )
                # Simulate schema hand-off between agents
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
                # intentional: tokens/path types match; all keys present → D≈0
                eval_rm = self.skills.EvaluateRhythmMarker(output, expected)
                schema_results.append(eval_rm)
                divergences.append(float(eval_rm["D"]))

            path_trace[agent.name] = collapse

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
                    f"{workload_name} remediate#{charter.state.remediation_loops} via {path}",
                    rng=self.rng,
                    quality_bias=0.15,
                    path=path,
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
            workload_name, token_spend=self.token_spend, token_budget=self.token_budget
        )
        self.blackboard.post_vector(budget_vec)

        trust = audit.passed and quality >= 0.90
        gov = self.executives.board.review_hand_off(
            workload_name, trust=trust, quality=quality
        )
        self.blackboard.post_vector(gov)
        charter.state.trust_signal = gov.approve_hand_off
        self.last_trust = gov.approve_hand_off

        entanglement = mean_pair_synergy(agent_qualities, divergences)
        router_summary = self.router.summary()

        # Store success in muscle memory
        if trust and quality >= 0.90:
            dominant_path = "path_A"
            if path_trace:
                first = next(iter(path_trace.values()))
                if isinstance(first, dict):
                    dominant_path = str(first.get("chosen_path", "path_A"))
            self.memory_store.add(
                MuscleMemoryRecord(
                    charter_id=workload_name,
                    path=dominant_path,
                    state_vector=tuple(state_vec),
                    quality=quality,
                    token_cost=spend,
                    tags=(workload_name.split()[0].lower(),),
                )
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
            "schema_audits": schema_results,
            "boss_prompt_loaded": bool(self.boss.system_prompt),
            "foundations_ref": "charter|flow_units|rhythm_markers|muscle_memory|coach_trust",
        }
        self.checkpointer.append(snap)
        self.blackboard.completed_jobs.append(workload_name)
        if workload_name in self.blackboard.active_jobs:
            self.blackboard.active_jobs.remove(workload_name)
        charter.bump()
        return snap

    def downtime_sync(self, telemetry: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """ST-07 via TriggerMondayMorningSync skill."""
        tel = telemetry or {
            "path_stats": {
                "path_A": {"success_rate": 0.92},
                "path_B": {"success_rate": 0.88},
                "path_lite": {"success_rate": 0.80},
            },
            "successful_runs": [
                {
                    "charter_id": s["workload"],
                    "path": "path_A",
                    "state_vector": [s.get("context_entropy", 0.3), 0.5, 0.5, 0.7],
                    "quality": s["quality"],
                    "token_cost": 200,
                }
                for s in self.checkpointer
                if s.get("trust")
            ],
        }
        skill_result = self.skills.TriggerMondayMorningSync(tel, roster=self.roster, boss=self.boss)
        outcomes = skill_result.get("outcomes") or self.boss.monday_morning_sync(self.roster, rng=self.rng)

        fitness_snap = {
            a.name: round(a.calculate_fitness(), 4)
            for a in self.roster
            if not isinstance(a, BossAgent)
            and getattr(a, "talent_eligible", True)
            and a.history
        }
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
        return {
            "outcomes": outcomes,
            "ops": ops.to_dict(),
            "guidance": [v.to_dict() for v in guidance],
            "vectors": self.blackboard.recent_vectors(16),
            "muscle_memory": muscle_snapshot,
            "quantum_lifetime": self.router.summary(),
            "skill_sync": skill_result,
            "boss_ack": self.boss_ack,
            "tool_schemas": [s["name"] for s in self.skills.tool_schemas()],
            "blueprint_foundations": [f["name"] for f in self.blueprint["foundations"]],
        }

    def ontology_export(self) -> Dict[str, Any]:
        return self.knowledge.export_dict()

    def skill_catalog(self) -> List[Dict[str, Any]]:
        return self.skills.tool_schemas()
