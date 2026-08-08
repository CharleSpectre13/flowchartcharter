"""Essential Agent Skills — function-calling tools for FlowChartCharter agents.

1. QueryMuscleMemory
2. EvaluateRhythmMarker
3. ExecuteQuantumCollapse
4. TriggerMondayMorningSync
5. AdjustCorporateRoster
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .agents import Agent, AgentStatus, BossAgent
from .muscle_memory import ExecutionMemoryRecord, MuscleMemoryVectorDB
from .prompts import (
    AGENT_SKILL_SCHEMAS,
    BOSS_ACKNOWLEDGEMENT,
    BOSS_AGENT_SYSTEM_PROMPT,
)
from .quantum import QuantumRouter, contextual_entropy
from .synergy import handoff_synergy


class RosterAction(str, Enum):
    PROMOTE = "PROMOTE"
    DEMOTE = "DEMOTE"
    FIRE = "FIRE"


@dataclass
class MuscleMemoryRecord:
    """Legacy thin record — prefer ExecutionMemoryRecord."""

    charter_id: str
    path: str
    state_vector: tuple
    quality: float
    token_cost: int
    tags: tuple = ()

    def to_execution_record(self) -> ExecutionMemoryRecord:
        return ExecutionMemoryRecord(
            memory_id=f"LEG-{self.charter_id[:8]}",
            job_type=self.charter_id,
            state_vector=list(self.state_vector),
            successful_flow_path=[self.path],
            entanglement_score=min(1.0, max(0.0, self.quality)),
            prompt_tweak="",
            quality=self.quality,
            token_cost=self.token_cost,
            tags=self.tags,
        )


class MuscleMemoryStore:
    """Adapter wrapping MuscleMemoryVectorDB for legacy skill API."""

    def __init__(self, db: Optional[MuscleMemoryVectorDB] = None) -> None:
        self.db = db or MuscleMemoryVectorDB(quiet=True)

    @property
    def records(self) -> List[ExecutionMemoryRecord]:
        return self.db.storage

    def add(self, rec: MuscleMemoryRecord) -> None:
        self.db.commit_memory(rec.to_execution_record())

    def add_execution(self, rec: ExecutionMemoryRecord) -> None:
        self.db.commit_memory(rec)

    def query(
        self,
        current_state_vector: Sequence[float],
        *,
        threshold: float = 0.82,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        return self.db.query_top_k(
            {},
            threshold=threshold,
            top_k=top_k,
            state_vector=current_state_vector,
        )


class AgentSkillRuntime:
    """Programmed skills exposed to the agent LLM environment."""

    def __init__(
        self,
        *,
        router: Optional[QuantumRouter] = None,
        store: Optional[MuscleMemoryStore] = None,
        db: Optional[MuscleMemoryVectorDB] = None,
        boss: Optional[BossAgent] = None,
        roster: Optional[List[Agent]] = None,
    ):
        self.router = router or QuantumRouter()
        self.db = db or MuscleMemoryVectorDB(quiet=True)
        self.store = store or MuscleMemoryStore(self.db)
        self.store.db = self.db
        self.boss = boss
        self.roster = roster or []
        self.last_sync: Dict[str, Any] = {}

    def QueryMuscleMemory(
        self,
        current_state_vector: Sequence[float],
        threshold: float = 0.82,
        *,
        payload: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Replace standard RAG with successful-charter precedent lookup."""
        hits = self.db.query_top_k(
            payload or {},
            threshold=threshold,
            top_k=3,
            state_vector=current_state_vector,
        )
        best = hits[0] if hits else None
        return {
            "skill": "QueryMuscleMemory",
            "hits": hits,
            "hit_count": len(hits),
            "threshold": threshold,
            "fallback": "follow_charter" if not hits else "apply_precedent",
            "recommended_path": (
                best["successful_flow_path"][0]
                if best and best.get("successful_flow_path")
                else None
            ),
            "recommended_flow_path": (best["successful_flow_path"] if best else None),
            "prompt_tweak": best["prompt_tweak"] if best else None,
            "entanglement_score": (best["entanglement_score"] if best else None),
            "memory_id": best["memory_id"] if best else None,
        }

    def EvaluateRhythmMarker(
        self,
        agent_output_json: Mapping[str, Any],
        expected_schema: Mapping[str, Any],
    ) -> Dict[str, Any]:
        """Self-audit intermediate work; route back on schema failure."""
        handoff = handoff_synergy(agent_output_json, expected_schema)
        d = handoff["D"]
        passed = handoff["schema_compliant"]
        errors: List[str] = []
        for key in expected_schema:
            if key not in agent_output_json:
                errors.append(f"missing:{key}")
            elif type(expected_schema[key]) is not type(agent_output_json[key]):
                if not (
                    isinstance(expected_schema[key], (int, float))
                    and isinstance(agent_output_json[key], (int, float))
                ):
                    errors.append(
                        f"type:{key}:expected="
                        f"{type(expected_schema[key]).__name__}"
                        f":got={type(agent_output_json[key]).__name__}"
                    )
        return {
            "skill": "EvaluateRhythmMarker",
            "passed": passed and not errors,
            "Q_s": handoff["Q_s"],
            "D": d,
            "schema_errors": errors,
            "route_back": not (passed and not errors),
            "translation_tokens_needed": handoff["translation_tokens_needed"],
            "formula": handoff["formula"],
        }

    def ExecuteQuantumCollapse(
        self,
        flow_options: Sequence[str],
        context_entropy: float = 0.0,
        *,
        muscle_memory: Optional[Dict[str, float]] = None,
        agent_name: str = "agent",
        charter_id: str = "charter",
        path_costs: Optional[Dict[str, float]] = None,
        remaining_budget: Optional[float] = None,
        margin: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Routing engine: |ψ⟩ + H_ctx + CFO matrix → M|ψ⟩."""
        mm = muscle_memory or {p: 1.0 for p in flow_options}
        for p in flow_options:
            mm.setdefault(p, 1.0)

        result = self.router.route_agent(
            charter_id=charter_id,
            agent_name=agent_name,
            muscle_memory=mm,
            marker="skill_collapse",
            context_entropy=context_entropy,
            path_costs=path_costs,
            remaining_budget=remaining_budget,
            margin=margin,
        )
        result["skill"] = "ExecuteQuantumCollapse"
        result["context_entropy"] = round(float(context_entropy), 4)
        result["H_ctx"] = (
            contextual_entropy(
                {
                    "noise": context_entropy,
                    "missing_ratio": context_entropy * 0.5,
                }
            )
            if context_entropy
            else 0.0
        )
        return result

    def TriggerMondayMorningSync(
        self,
        telemetry_data: Mapping[str, Any],
        *,
        roster: Optional[List[Agent]] = None,
        boss: Optional[BossAgent] = None,
    ) -> Dict[str, Any]:
        """Downtime RLAIF: re-weight paths, talent, commit memories."""
        team = roster if roster is not None else self.roster
        gm = boss or self.boss
        outcomes: Dict[str, str] = {}
        reweights: Dict[str, Dict[str, float]] = {}

        if gm is not None and team:
            outcomes = gm.monday_morning_sync(team)

        path_stats = telemetry_data.get("path_stats") or telemetry_data.get("paths") or {}
        for agent in team:
            if not getattr(agent, "talent_eligible", True):
                continue
            mm = dict(agent.muscle_memory_weights)
            for path, stats in path_stats.items():
                if not isinstance(stats, dict):
                    continue
                success_rate = float(stats.get("success_rate", stats.get("quality", 0.5)))
                prev = mm.get(path, 1.0)
                mm[path] = max(0.05, min(8.0, prev * (0.7 + 0.6 * success_rate)))
            agent.muscle_memory_weights = mm
            reweights[agent.name] = dict(mm)

        for run in telemetry_data.get("successful_runs", []):
            vec = run.get("state_vector") or run.get("vector") or [0.5, 0.5, 0.5, 0.1]
            path = run.get("path") or run.get("flow_path") or "path_A"
            flow_path = path if isinstance(path, list) else [str(path)]
            self.db.commit_memory(
                ExecutionMemoryRecord(
                    memory_id=str(run.get("memory_id", f"RUN-{len(self.db.storage)}")),
                    job_type=str(
                        run.get(
                            "charter_id",
                            run.get("job_type", "unknown"),
                        )
                    ),
                    state_vector=[float(x) for x in vec],
                    successful_flow_path=flow_path,
                    entanglement_score=float(
                        run.get(
                            "entanglement_score",
                            run.get("quality", 0.95),
                        )
                    ),
                    prompt_tweak=str(run.get("prompt_tweak", "")),
                    quality=float(run.get("quality", 0.95)),
                    token_cost=int(run.get("token_cost", 200)),
                    tags=tuple(run.get("tags", ())),
                )
            )

        self.last_sync = {
            "skill": "TriggerMondayMorningSync",
            "outcomes": outcomes,
            "reweights": reweights,
            "store_size": len(self.db.storage),
            "db_stats": self.db.stats(),
            "telemetry_keys": list(telemetry_data.keys()),
        }
        return self.last_sync

    def AdjustCorporateRoster(
        self,
        agent_id: str,
        action: str,
        *,
        roster: Optional[List[Agent]] = None,
    ) -> Dict[str, Any]:
        """Promote / demote / fire by agent id (or name)."""
        team = roster if roster is not None else self.roster
        act = RosterAction(action if isinstance(action, str) else action.value)
        target: Optional[Agent] = None
        for a in team:
            if a.id == agent_id or a.name == agent_id:
                target = a
                break
        if target is None:
            return {
                "skill": "AdjustCorporateRoster",
                "ok": False,
                "error": f"agent not found: {agent_id}",
            }
        if act == RosterAction.PROMOTE:
            target.status = AgentStatus.PROMOTED
            target.corporate_rank = min(10.0, target.corporate_rank + 1.0)
        elif act == RosterAction.DEMOTE:
            target.status = AgentStatus.DEMOTED
            target.corporate_rank = max(0.5, target.corporate_rank - 1.0)
        elif act == RosterAction.FIRE:
            target.status = AgentStatus.FIRED
            target.corporate_rank = 0.0

        if self.boss is not None:
            self.boss.playbook.append(f"{act.value} {target.name} via AdjustCorporateRoster")

        return {
            "skill": "AdjustCorporateRoster",
            "ok": True,
            "agent_id": target.id,
            "agent_name": target.name,
            "action": act.value,
            "status": target.status.value,
            "corporate_rank": target.corporate_rank,
        }

    def tool_schemas(self) -> List[Dict[str, Any]]:
        return list(AGENT_SKILL_SCHEMAS)

    def dispatch(self, name: str, arguments: Mapping[str, Any]) -> Dict[str, Any]:
        """Generic function-call dispatcher."""
        fn = getattr(self, name, None)
        if fn is None or not callable(fn):
            return {"error": f"unknown skill: {name}"}
        return fn(**dict(arguments))


def init_boss_agent(name: str = "Alpha-GM"):
    """Create Boss Agent with exact Head Coach system prompt loaded."""
    boss = BossAgent(name)
    boss.system_prompt = BOSS_AGENT_SYSTEM_PROMPT
    boss.acknowledged = True
    return boss, BOSS_ACKNOWLEDGEMENT
