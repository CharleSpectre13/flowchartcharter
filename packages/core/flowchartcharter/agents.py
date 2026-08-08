from __future__ import annotations
import uuid
import random
from enum import Enum
from typing import Dict, List, Optional
from .metrics import ExecutionMetrics
from .fitness import fitness, INDUSTRY_BENCHMARK


class AgentStatus(str, Enum):
    ACTIVE = "Active"
    PROMOTED = "Promoted"
    DEMOTED = "Demoted"
    FIRED = "Fired"


class Agent:
    def __init__(self, name: str, role: str, capability_vector: Optional[Dict[str, float]] = None):
        self.id = str(uuid.uuid4())[:8]
        self.name = name
        self.role = role
        self.history: List[ExecutionMetrics] = []
        self.status = AgentStatus.ACTIVE
        self.muscle_memory_weights: Dict[str, float] = {"path_A": 1.0, "path_B": 1.0}
        self.capability_vector = capability_vector or {"general": 1.0}
        self.corporate_rank = 1.0
        self.load = 0.0

    def execute_flow_unit(
        self,
        task: str,
        *,
        rng: Optional[random.Random] = None,
        quality_bias: float = 0.0,
    ) -> Optional[ExecutionMetrics]:
        if self.status not in (AgentStatus.ACTIVE, AgentStatus.PROMOTED):
            return None
        r = rng or random
        cost = r.randint(100, 500)
        time = r.uniform(0.5, 2.5)
        quality = min(1.0, max(0.0, r.uniform(0.7, 1.0) + quality_bias))
        synergy = r.uniform(0.8, 1.0)
        metrics = ExecutionMetrics(cost, time, quality, synergy)
        self.history.append(metrics)
        self.load = min(1.0, self.load + 0.1)
        return metrics

    def calculate_fitness(self) -> float:
        return fitness(self.history)

    def volunteer_score(self, task_embedding: Dict[str, float], temperature: float = 1.0) -> float:
        """P(A_j, T_k) style activation: capability match × rank / (1+load)."""
        if self.status == AgentStatus.FIRED:
            return 0.0
        score = 0.0
        for k, v in task_embedding.items():
            score += v * self.capability_vector.get(k, 0.0)
        score *= self.corporate_rank
        score /= (1.0 + self.load) * max(temperature, 1e-6)
        return score


class BossAgent(Agent):
    def __init__(self, name: str):
        super().__init__(name, "General Manager (Boss)")
        self.corporate_rank = 10.0
        self.playbook: List[str] = []

    def monday_morning_sync(
        self,
        team: List[Agent],
        *,
        benchmark: float = INDUSTRY_BENCHMARK,
        rng: Optional[random.Random] = None,
    ) -> Dict[str, str]:
        """ST-07 Downtime Team Sync — talent management."""
        r = rng or random
        outcomes: Dict[str, str] = {}
        for agent in team:
            if isinstance(agent, BossAgent):
                continue
            f = agent.calculate_fitness()
            if f >= benchmark * 1.2:
                agent.status = AgentStatus.PROMOTED
                agent.corporate_rank = min(10.0, agent.corporate_rank + 1.0)
                outcomes[agent.name] = "PROMOTED"
                self.playbook.append(f"Promote {agent.name}: fitness={f:.3f}")
            elif f < benchmark * 0.7:
                agent.status = AgentStatus.FIRED
                outcomes[agent.name] = "FIRED"
                self.playbook.append(f"Fire {agent.name}: fitness={f:.3f}")
            else:
                agent.status = AgentStatus.ACTIVE
                agent.muscle_memory_weights["path_A"] = max(
                    0.1, agent.muscle_memory_weights.get("path_A", 1.0) + r.uniform(-0.1, 0.2)
                )
                outcomes[agent.name] = "RETAINED"
        return outcomes
