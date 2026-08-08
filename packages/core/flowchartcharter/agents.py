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
    """General Manager — executes Board dossier; day-to-day ops only."""

    def __init__(self, name: str):
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


# Architectural alias (reference engine naming)
WorkerNode = Agent
