from __future__ import annotations
import uuid
import random
from enum import Enum
from typing import Dict, List, Optional
from .metrics import ExecutionMetrics
from .fitness import fitness, INDUSTRY_BENCHMARK
from .prompts import BOSS_AGENT_SYSTEM_PROMPT, BOSS_ACKNOWLEDGEMENT


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
        self.muscle_memory_weights: Dict[str, float] = {
            "path_A": 1.0,
            "path_B": 1.0,
            "path_lite": 1.0,
        }
        self.capability_vector = capability_vector or {"general": 1.0}
        self.corporate_rank = 1.0
        self.load = 0.0
        self.talent_eligible = True

    def execute_flow_unit(
        self,
        task: str,
        *,
        rng: Optional[random.Random] = None,
        quality_bias: float = 0.0,
        path: str = "path_A",
    ) -> Optional[ExecutionMetrics]:
        if self.status not in (AgentStatus.ACTIVE, AgentStatus.PROMOTED):
            return None
        r = rng or random
        # path-aware cost model (aligns with CFO path_costs)
        if path == "path_lite":
            cost = r.randint(60, 120)
        elif path == "path_B":
            cost = r.randint(280, 450)
        else:
            cost = r.randint(140, 280)
        time = r.uniform(0.4, 2.2)
        quality = min(1.0, max(0.0, r.uniform(0.72, 1.0) + quality_bias))
        # cleansing path slightly better quality on messy jobs (encoded in bias by caller)
        synergy = r.uniform(0.82, 1.0)
        metrics = ExecutionMetrics(cost, time, quality, synergy)
        self.history.append(metrics)
        self.load = min(1.0, self.load + 0.1)
        return metrics

    def calculate_fitness(self) -> float:
        return fitness(self.history)

    def volunteer_score(self, task_embedding: Dict[str, float], temperature: float = 1.0) -> float:
        if self.status == AgentStatus.FIRED:
            return 0.0
        score = 0.0
        for k, v in task_embedding.items():
            score += v * self.capability_vector.get(k, 0.0)
        score *= self.corporate_rank
        score /= (1.0 + self.load) * max(temperature, 1e-6)
        return score


class BossAgent(Agent):
    """General Manager — initialized with exact Head Coach system prompt."""

    def __init__(self, name: str):
        super().__init__(name, "General Manager (Boss)")
        self.corporate_rank = 10.0
        self.playbook: List[str] = []
        self.talent_eligible = False
        self.system_prompt = BOSS_AGENT_SYSTEM_PROMPT
        self.acknowledged = False

    def acknowledge_directive(self) -> str:
        self.acknowledged = True
        return BOSS_ACKNOWLEDGEMENT

    def monday_morning_sync(
        self,
        team: List[Agent],
        *,
        benchmark: float = INDUSTRY_BENCHMARK,
        rng: Optional[random.Random] = None,
    ) -> Dict[str, str]:
        """ST-07 Downtime Team Sync — talent management on operational roster only."""
        r = rng or random
        outcomes: Dict[str, str] = {}
        for agent in team:
            if isinstance(agent, BossAgent):
                continue
            if not getattr(agent, "talent_eligible", True):
                continue
            if not agent.history:
                continue
            f = agent.calculate_fitness()
            if f >= benchmark * 1.2:
                agent.status = AgentStatus.PROMOTED
                agent.corporate_rank = min(10.0, agent.corporate_rank + 1.0)
                outcomes[agent.name] = "PROMOTED"
                self.playbook.append(f"Promote {agent.name}: fitness={f:.3f}")
            elif f < benchmark * 0.55:
                agent.status = AgentStatus.FIRED
                outcomes[agent.name] = "FIRED"
                self.playbook.append(f"Fire {agent.name}: fitness={f:.3f}")
            elif f < benchmark * 0.75:
                agent.status = AgentStatus.DEMOTED
                agent.corporate_rank = max(0.5, agent.corporate_rank - 0.5)
                outcomes[agent.name] = "DEMOTED"
                self.playbook.append(f"Demote {agent.name}: fitness={f:.3f}")
            else:
                agent.status = AgentStatus.ACTIVE
                for p in list(agent.muscle_memory_weights.keys()):
                    agent.muscle_memory_weights[p] = max(
                        0.1,
                        agent.muscle_memory_weights.get(p, 1.0) + r.uniform(-0.05, 0.12),
                    )
                outcomes[agent.name] = "RETAINED"
        return outcomes
