from __future__ import annotations

import random
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional

from .fitness import INDUSTRY_BENCHMARK, fitness
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


class AgentStatus(str, Enum):
    ACTIVE = "Active"
    PROMOTED = "Promoted"
    DEMOTED = "Demoted"
    FIRED = "Fired"


class Agent:
    """Worker node with Fear-Based Accountability survival telemetry."""

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
        self.corporate_rank = 1.0
        self.load = 0.0
        self.talent_eligible = True

        # --- Cognitive Survival Constraint ---
        self.survival_status: SurvivalStatus = SurvivalStatus.ACTIVE
        self.termination_risk_index: float = 0.0
        self.ledger = TelemetryLedger()
        self.generation: GenerationParameters = generation_params_for_risk(0.0)
        self.system_prompt: str = self._rebuild_prompt()
        self.cycle_counter: int = 0

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
        """Re-inject live telemetry into the worker system prompt."""
        self.generation = generation_params_for_risk(self.termination_risk_index)
        self.survival_status = status_from_risk(self.termination_risk_index)
        if self.status == AgentStatus.FIRED:
            self.survival_status = SurvivalStatus.TERMINATED
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
        """Append immutable ledger row and recompute termination_risk_index."""
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
    ) -> Optional[ExecutionMetrics]:
        if self.status not in (AgentStatus.ACTIVE, AgentStatus.PROMOTED):
            return None
        r = rng or random

        # Survival pressure biases execution toward determinism:
        # high risk → lower variance quality, prefer path_lite cost profile
        risk = self.termination_risk_index
        if risk >= 0.55 and path == "path_B":
            path = "path_lite"  # forced thrift under fear

        if path == "path_lite":
            cost = r.randint(60, 120)
        elif path == "path_B":
            cost = r.randint(280, 450)
        else:
            cost = r.randint(140, 280)

        # latency shrinks slightly under schema_lock (no creative thrash)
        if self.generation.schema_lock:
            time = r.uniform(0.35, 1.4)
        else:
            time = r.uniform(0.4, 2.2)

        base_q = r.uniform(0.72, 1.0) + quality_bias
        # high risk agents cannot "guess" — quality floor rises with schema_lock
        if self.generation.schema_lock:
            base_q = max(base_q, 0.88 + 0.05 * risk)
        quality = min(1.0, max(0.0, base_q))
        synergy = r.uniform(0.82, 1.0)
        metrics = ExecutionMetrics(cost, time, quality, synergy)
        self.history.append(metrics)
        self.load = min(1.0, self.load + 0.1)

        # Telemetry ledger + fear update
        schema_div = 0 if expected_schema_ok else 1
        # structural drift from quality shortfall when unlocked
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

    def calculate_fitness(self) -> float:
        return fitness(self.history)

    def volunteer_score(
        self, task_embedding: Dict[str, float], temperature: float = 1.0
    ) -> float:
        if self.status == AgentStatus.FIRED:
            return 0.0
        score = 0.0
        for k, v in task_embedding.items():
            score += v * self.capability_vector.get(k, 0.0)
        score *= self.corporate_rank
        # elevated risk agents volunteer less aggressively
        score *= max(0.2, 1.0 - 0.5 * self.termination_risk_index)
        score /= (1.0 + self.load) * max(temperature, 1e-6)
        return score

    def survival_snapshot(self) -> Dict[str, Any]:
        return {
            "agent": self.name,
            "id": self.id,
            "role": self.role,
            "status": self.status.value,
            "survival_status": self.survival_status.value,
            "termination_risk_index": round(self.termination_risk_index, 4),
            "generation": self.generation.to_dict(),
            "ledger": self.ledger.export(),
            "fitness": round(self.calculate_fitness(), 4) if self.history else 0.0,
        }


class BossAgent(Agent):
    """General Manager — Head Coach system prompt + pruning / lean re-hire."""

    def __init__(self, name: str):
        super().__init__(name, "General Manager (Boss)")
        self.corporate_rank = 10.0
        self.playbook: List[str] = []
        self.talent_eligible = False
        self.system_prompt = BOSS_AGENT_SYSTEM_PROMPT
        self.acknowledged = False
        self.rehire_log: List[LeanRehireDecision] = []
        # Boss is not under worker survival pressure
        self.survival_status = SurvivalStatus.ACTIVE
        self.termination_risk_index = 0.0

    def acknowledge_directive(self) -> str:
        self.acknowledged = True
        return BOSS_ACKNOWLEDGEMENT

    def monday_morning_sync(
        self,
        team: List[Agent],
        *,
        benchmark: float = INDUSTRY_BENCHMARK,
        rng: Optional[random.Random] = None,
        muscle_memory_records: int = 0,
        lean_rehire: bool = True,
    ) -> Dict[str, str]:
        """ST-07 — fitness + ledger pruning; lean re-hire declines backfill."""
        r = rng or random
        outcomes: Dict[str, str] = {}
        self.rehire_log = []

        # Count pre-prune ops for lean check baseline
        for agent in team:
            if isinstance(agent, BossAgent):
                continue
            if not getattr(agent, "talent_eligible", True):
                continue
            if not agent.history and agent.ledger.schema_errors == 0:
                continue

            f = agent.calculate_fitness() if agent.history else 0.0
            risk = agent.termination_risk_index
            fire_floor = benchmark * 0.55

            if should_fire_from_ledger(
                risk, agent.ledger, f, fitness_floor=fire_floor
            ):
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
                        in (AgentStatus.ACTIVE, AgentStatus.PROMOTED)
                        and getattr(a, "talent_eligible", True)
                    )
                    decision = lean_rehire_check(
                        agent_name=agent.name,
                        surviving_ops=surviving,
                        muscle_memory_records=muscle_memory_records,
                    )
                    self.rehire_log.append(decision)
                    self.playbook.append(
                        f"Lean re-hire {agent.name}: backfill="
                        f"{decision.backfill} ({decision.reason[:60]})"
                    )
                continue

            if f >= benchmark * 1.2 and risk < 0.35:
                agent.status = AgentStatus.PROMOTED
                agent.corporate_rank = min(10.0, agent.corporate_rank + 1.0)
                # promotion slightly reduces risk (earned trust)
                agent.termination_risk_index = max(
                    0.0, agent.termination_risk_index - 0.08
                )
                agent.refresh_survival_prompt()
                outcomes[agent.name] = "PROMOTED"
                self.playbook.append(f"Promote {agent.name}: fitness={f:.3f}")
            elif f < benchmark * 0.75 or risk >= 0.55:
                agent.status = AgentStatus.DEMOTED
                agent.corporate_rank = max(0.5, agent.corporate_rank - 0.5)
                agent.refresh_survival_prompt()
                outcomes[agent.name] = "DEMOTED"
                self.playbook.append(
                    f"Demote {agent.name}: F={f:.3f} risk={risk:.3f}"
                )
            else:
                agent.status = AgentStatus.ACTIVE
                for p in list(agent.muscle_memory_weights.keys()):
                    agent.muscle_memory_weights[p] = max(
                        0.1,
                        agent.muscle_memory_weights.get(p, 1.0)
                        + r.uniform(-0.05, 0.12),
                    )
                agent.refresh_survival_prompt()
                outcomes[agent.name] = "RETAINED"
        return outcomes

    def rehire_export(self) -> List[Dict[str, Any]]:
        return [d.to_dict() for d in self.rehire_log]
