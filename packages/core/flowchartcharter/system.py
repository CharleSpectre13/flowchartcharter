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
from .quantum import QuantumRouter, quantum_path_select


class FlowChartCharterSystem:
    """Facade: ST-01 … ST-07 + QuantumRouter + executive wire + Brain-1 KG."""

    PATHS = ("path_A", "path_B")

    def __init__(
        self,
        head_coach: str = "Human Systems Engineer",
        seed: Optional[int] = None,
        *,
        deterministic_routing: bool = True,
    ):
        self.head_coach = head_coach
        self.rng = random.Random(seed)
        self.boss = BossAgent("Alpha-GM")
        self.executives = ExecutiveBoard()
        self.knowledge = KnowledgeGraph()
        self.blueprint = blueprint_export()
        self.router = QuantumRouter(
            paths=self.PATHS,
            deterministic=deterministic_routing,
            rng=self.rng,
            quality_floor=0.90,
            lr=0.12,
        )
        self.roster: List[Agent] = [
            Agent("Worker-1", "Key Player - Data Extraction", {"extraction": 1.0, "general": 0.5}),
            Agent("Worker-2", "Key Player - Validation", {"validation": 1.0, "general": 0.5}),
            Agent("Worker-3", "Position Manager - Synthesizer", {"synthesis": 1.0, "general": 0.6}),
            Agent("Auditor-1", "Audit Manager", {"audit": 1.0, "general": 0.4}),
            self.executives.validator,
        ]
        # Slight path bias seeds for demo diversity
        self.roster[0].muscle_memory_weights = {"path_A": 1.4, "path_B": 0.9}
        self.roster[1].muscle_memory_weights = {"path_A": 1.0, "path_B": 1.2}
        self.roster[2].muscle_memory_weights = {"path_A": 1.5, "path_B": 0.7}
        self.blackboard = Blackboard()
        self.checkpointer: List[Dict[str, Any]] = []
        self.last_trust = False
        self.token_budget = 50_000
        self.token_spend = 0

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

    def execute_charter(self, workload_name: str, *, force_quality: Optional[float] = None) -> Dict[str, Any]:
        """ST-01..ST-06 with QuantumRouter collapse at ST-03 and RhythmAudit at ST-04."""
        # Fresh router history per charter (amplitude learning persists on agents)
        self.router.history.clear()
        self.router._pending.clear()

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
        strategy = self.executives.ceo.issue_strategy(workload_name)
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

        # ST-03 super-step: quantum collapse per ops agent
        collected: List[ExecutionMetrics] = []
        path_trace: Dict[str, Any] = {}
        agent_qualities: List[float] = []

        for agent in self.roster:
            if not self._is_ops(agent):
                continue
            rec = self.router.collapse(
                charter_id=workload_name,
                agent_name=agent.name,
                muscle_memory=agent.muscle_memory_weights,
                marker="superstep",
            )
            path = rec.chosen_path
            bias = 0.0 if force_quality is None else (force_quality - 0.85)
            m = agent.execute_flow_unit(
                f"{workload_name} via {path}",
                rng=self.rng,
                quality_bias=bias,
            )
            if m:
                collected.append(m)
                agent_qualities.append(m.quality_score)
                # Reinforce muscle memory from this unit's quality
                agent.muscle_memory_weights = self.router.observe(
                    agent.name,
                    agent.muscle_memory_weights,
                    m.quality_score,
                )
            path_trace[agent.name] = rec.to_dict()

        # ST-04 RhythmAudit (measurement gate)
        quality = force_quality if force_quality is not None else self._audit_quality(collected)
        audit = self.executives.validator.audit(
            workload_name,
            marker="gate",
            quality=quality,
            threshold=0.90,
            remediation_loops=0,
        )
        self.blackboard.post_vector(audit)
        charter.state.quality_score = quality

        # ST-05 remediation — re-collapse with updated amplitudes
        while not audit.passed and charter.state.remediation_loops < charter.state.max_remediation:
            charter.state.remediation_loops += 1
            batch_q: List[float] = []
            for agent in self.roster:
                if not self._is_ops(agent):
                    continue
                rec = self.router.collapse(
                    charter_id=workload_name,
                    agent_name=agent.name,
                    muscle_memory=agent.muscle_memory_weights,
                    marker=f"remediate#{charter.state.remediation_loops}",
                )
                m = agent.execute_flow_unit(
                    f"{workload_name} remediate#{charter.state.remediation_loops} via {rec.chosen_path}",
                    rng=self.rng,
                    quality_bias=0.15,
                )
                if m:
                    collected.append(m)
                    batch_q.append(m.quality_score)
                    agent.muscle_memory_weights = self.router.observe(
                        agent.name,
                        agent.muscle_memory_weights,
                        m.quality_score,
                    )
                path_trace[f"{agent.name}#r{charter.state.remediation_loops}"] = rec.to_dict()
            quality = self._audit_quality(collected[-3:]) if collected else quality
            if batch_q:
                agent_qualities.extend(batch_q)
            audit = self.executives.validator.audit(
                workload_name,
                marker="gate",
                quality=quality,
                threshold=0.90,
                remediation_loops=charter.state.remediation_loops,
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

        entanglement = self.router.team_entanglement(agent_qualities)
        router_summary = self.router.summary()

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
            "foundations_ref": "charter|flow_units|rhythm_markers|muscle_memory|coach_trust",
        }
        self.checkpointer.append(snap)
        self.blackboard.completed_jobs.append(workload_name)
        if workload_name in self.blackboard.active_jobs:
            self.blackboard.active_jobs.remove(workload_name)
        charter.bump()
        return snap

    def downtime_sync(self) -> Dict[str, Any]:
        """ST-07 Monday Morning Sync — talent + RLAIF + quantum path report."""
        outcomes = self.boss.monday_morning_sync(self.roster, rng=self.rng)
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
        kg_global = self.knowledge.global_search("math")
        return {
            "outcomes": outcomes,
            "ops": ops.to_dict(),
            "guidance": [v.to_dict() for v in guidance],
            "vectors": self.blackboard.recent_vectors(16),
            "knowledge_global": kg_global,
            "muscle_memory": muscle_snapshot,
            "quantum_lifetime": self.router.summary(),
            "blueprint_foundations": [f["name"] for f in self.blueprint["foundations"]],
        }

    def ontology_export(self) -> Dict[str, Any]:
        return self.knowledge.export_dict()
