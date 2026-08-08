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
from .quantum import quantum_path_select


class FlowChartCharterSystem:
    """Facade: ST-01 … ST-07 + executive wire + RhythmAudit + Brain-1 KG."""

    def __init__(self, head_coach: str = "Human Systems Engineer", seed: Optional[int] = None):
        self.head_coach = head_coach
        self.rng = random.Random(seed)
        self.boss = BossAgent("Alpha-GM")
        self.executives = ExecutiveBoard()
        self.knowledge = KnowledgeGraph()
        self.blueprint = blueprint_export()
        self.roster: List[Agent] = [
            Agent("Worker-1", "Key Player - Data Extraction", {"extraction": 1.0, "general": 0.5}),
            Agent("Worker-2", "Key Player - Validation", {"validation": 1.0, "general": 0.5}),
            Agent("Worker-3", "Position Manager - Synthesizer", {"synthesis": 1.0, "general": 0.6}),
            Agent("Auditor-1", "Audit Manager", {"audit": 1.0, "general": 0.4}),
            self.executives.validator,
        ]
        self.blackboard = Blackboard()
        self.checkpointer: List[Dict[str, Any]] = []
        self.last_trust = False
        self.token_budget = 50_000
        self.token_spend = 0

    def quantum_path_selection(self, agent: Agent, paths: Sequence[str]) -> str:
        result = quantum_path_select(
            paths,
            agent.muscle_memory_weights,
            rng=self.rng,
            deterministic=True,
        )
        return str(result["chosen_path"])

    def quantum_path_detail(self, agent: Agent, paths: Sequence[str]) -> Dict[str, object]:
        return quantum_path_select(
            paths,
            agent.muscle_memory_weights,
            rng=self.rng,
            deterministic=True,
        )

    def _audit_quality(self, metrics: List[ExecutionMetrics]) -> float:
        if not metrics:
            return 0.0
        return sum(m.quality_score for m in metrics) / len(metrics)

    def _token_sum(self, metrics: List[ExecutionMetrics]) -> int:
        return sum(m.token_cost for m in metrics)

    def execute_charter(self, workload_name: str, *, force_quality: Optional[float] = None) -> Dict[str, Any]:
        """Run ST-01..ST-06 with RhythmAudit at ST-04 and quantum path collapse."""
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

        collected: List[ExecutionMetrics] = []
        path_trace: Dict[str, Any] = {}
        for agent in self.roster:
            if agent.status not in (AgentStatus.ACTIVE, AgentStatus.PROMOTED):
                continue
            if "Audit" in agent.role or "Validator" in agent.role or "Chief" in agent.role or "Board" in agent.role:
                continue
            detail = self.quantum_path_detail(agent, ["path_A", "path_B"])
            path = str(detail["chosen_path"])
            path_trace[agent.name] = detail
            bias = 0.0 if force_quality is None else (force_quality - 0.85)
            m = agent.execute_flow_unit(f"{workload_name} via {path}", rng=self.rng, quality_bias=bias)
            if m:
                collected.append(m)

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

        while not audit.passed and charter.state.remediation_loops < charter.state.max_remediation:
            charter.state.remediation_loops += 1
            for agent in self.roster:
                if agent.status not in (AgentStatus.ACTIVE, AgentStatus.PROMOTED):
                    continue
                if "Audit" in agent.role or "Validator" in agent.role:
                    continue
                if "Chief" in agent.role or "Board" in agent.role:
                    continue
                m = agent.execute_flow_unit(
                    f"{workload_name} remediate#{charter.state.remediation_loops}",
                    rng=self.rng,
                    quality_bias=0.15,
                )
                if m:
                    collected.append(m)
            quality = self._audit_quality(collected[-3:]) if collected else quality
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
            "foundations_ref": "charter|flow_units|rhythm_markers|muscle_memory|coach_trust",
        }
        self.checkpointer.append(snap)
        self.blackboard.completed_jobs.append(workload_name)
        if workload_name in self.blackboard.active_jobs:
            self.blackboard.active_jobs.remove(workload_name)
        charter.bump()
        return snap

    def downtime_sync(self) -> Dict[str, Any]:
        """ST-07 Monday Morning Sync — async RLAIF + talent + KG global report."""
        outcomes = self.boss.monday_morning_sync(self.roster, rng=self.rng)
        fitness_snap = {
            a.name: round(a.calculate_fitness(), 4)
            for a in self.roster
            if not isinstance(a, BossAgent)
            and "Chief" not in a.role
            and "Board" not in a.role
            and getattr(a, "talent_eligible", True)
            and a.history
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
        kg_global = self.knowledge.global_search("operations")
        return {
            "outcomes": outcomes,
            "ops": ops.to_dict(),
            "guidance": [v.to_dict() for v in guidance],
            "vectors": self.blackboard.recent_vectors(16),
            "knowledge_global": kg_global,
            "blueprint_foundations": [f["name"] for f in self.blueprint["foundations"]],
        }

    def ontology_export(self) -> Dict[str, Any]:
        return self.knowledge.export_dict()
