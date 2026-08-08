from __future__ import annotations
import random
from typing import Dict, List, Optional, Sequence
from .agents import Agent, BossAgent, AgentStatus
from .blackboard import Blackboard, TaskRequest
from .charter import Charter, FlowUnit, CharterState
from .metrics import ExecutionMetrics


class FlowChartCharterSystem:
    """Facade: ST-01 … ST-07 lifecycle for a multi-agent charter run."""

    def __init__(self, head_coach: str = "Human Systems Engineer", seed: Optional[int] = None):
        self.head_coach = head_coach
        self.rng = random.Random(seed)
        self.boss = BossAgent("Alpha-GM")
        self.roster: List[Agent] = [
            Agent("Worker-1", "Key Player - Data Extraction", {"extraction": 1.0, "general": 0.5}),
            Agent("Worker-2", "Key Player - Validation", {"validation": 1.0, "general": 0.5}),
            Agent("Worker-3", "Position Manager - Synthesizer", {"synthesis": 1.0, "general": 0.6}),
            Agent("Auditor-1", "Audit Manager", {"audit": 1.0, "general": 0.4}),
        ]
        self.blackboard = Blackboard()
        self.checkpointer: List[Dict] = []
        self.last_trust = False

    def quantum_path_selection(self, agent: Agent, paths: Sequence[str]) -> str:
        total = sum(agent.muscle_memory_weights.get(p, 1.0) for p in paths)
        weights = [agent.muscle_memory_weights.get(p, 1.0) / total for p in paths]
        return self.rng.choices(list(paths), weights=weights, k=1)[0]

    def _audit_quality(self, metrics: List[ExecutionMetrics]) -> float:
        if not metrics:
            return 0.0
        return sum(m.quality_score for m in metrics) / len(metrics)

    def execute_charter(self, workload_name: str, *, force_quality: Optional[float] = None) -> Dict:
        """Run ST-01..ST-06 for one workload."""
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
        # ST-01 intake
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

        # ST-02 bind
        assignments = self.blackboard.volunteer_bind(self.roster)

        # ST-03 super-step
        collected: List[ExecutionMetrics] = []
        for agent in self.roster:
            if agent.status not in (AgentStatus.ACTIVE, AgentStatus.PROMOTED):
                continue
            if "Audit" in agent.role:
                continue
            path = self.quantum_path_selection(agent, ["path_A", "path_B"])
            bias = 0.0 if force_quality is None else (force_quality - 0.85)
            m = agent.execute_flow_unit(f"{workload_name} via {path}", rng=self.rng, quality_bias=bias)
            if m:
                collected.append(m)

        # ST-04 audit gate
        quality = force_quality if force_quality is not None else self._audit_quality(collected)
        charter.state.quality_score = quality

        # ST-05 remediation if needed
        while quality < 0.90 and charter.state.remediation_loops < charter.state.max_remediation:
            charter.state.remediation_loops += 1
            for agent in self.roster:
                if agent.status in (AgentStatus.ACTIVE, AgentStatus.PROMOTED) and "Audit" not in agent.role:
                    m = agent.execute_flow_unit(
                        f"{workload_name} remediate#{charter.state.remediation_loops}",
                        rng=self.rng,
                        quality_bias=0.15,
                    )
                    if m:
                        collected.append(m)
            quality = self._audit_quality(collected[-3:]) if collected else quality
            charter.state.quality_score = quality

        # ST-06 trust hand-off
        trust = quality >= 0.90
        charter.state.trust_signal = trust
        self.last_trust = trust
        snap = {
            "workload": workload_name,
            "quality": quality,
            "trust": trust,
            "remediation_loops": charter.state.remediation_loops,
            "assignments": assignments,
            "metrics_count": len(collected),
        }
        self.checkpointer.append(snap)
        self.blackboard.completed_jobs.append(workload_name)
        if workload_name in self.blackboard.active_jobs:
            self.blackboard.active_jobs.remove(workload_name)
        charter.bump()
        return snap

    def downtime_sync(self) -> Dict[str, str]:
        """ST-07 Monday Morning Sync."""
        return self.boss.monday_morning_sync(self.roster, rng=self.rng)
