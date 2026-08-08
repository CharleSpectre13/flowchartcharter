"""Essential Agent Skills — function-calling tools for FlowChartCharter agents.

1. QueryMuscleMemory
2. EvaluateRhythmMarker
3. ExecuteQuantumCollapse
4. TriggerMondayMorningSync
5. AdjustCorporateRoster
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .agents import Agent, AgentStatus, BossAgent
from .fitness import INDUSTRY_BENCHMARK
from .prompts import AGENT_SKILL_SCHEMAS, BOSS_ACKNOWLEDGEMENT, BOSS_AGENT_SYSTEM_PROMPT
from .quantum import QuantumRouter, contextual_entropy, build_superposition
from .synergy import handoff_synergy, structural_divergence


class RosterAction(str, Enum):
    PROMOTE = "PROMOTE"
    DEMOTE = "DEMOTE"
    FIRE = "FIRE"


@dataclass
class MuscleMemoryRecord:
    """One successful charter completion stored for precedent lookup."""
    charter_id: str
    path: str
    state_vector: Tuple[float, ...]
    quality: float
    token_cost: int
    tags: Tuple[str, ...] = ()

    def cosine(self, other: Sequence[float]) -> float:
        if not self.state_vector or not other:
            return 0.0
        n = min(len(self.state_vector), len(other))
        a = self.state_vector[:n]
        b = tuple(float(x) for x in other[:n])
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a)) or 1e-12
        nb = math.sqrt(sum(x * x for x in b)) or 1e-12
        return max(-1.0, min(1.0, dot / (na * nb)))


@dataclass
class MuscleMemoryStore:
    """VectorDB-lite of past successful FlowChart completions (cheat codes)."""
    records: List[MuscleMemoryRecord] = field(default_factory=list)

    def add(self, rec: MuscleMemoryRecord) -> None:
        if rec.quality >= 0.90:
            self.records.append(rec)

    def query(
        self,
        current_state_vector: Sequence[float],
        *,
        threshold: float = 0.82,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        scored: List[Tuple[float, MuscleMemoryRecord]] = []
        for rec in self.records:
            sim = rec.cosine(current_state_vector)
            if sim >= threshold:
                scored.append((sim, rec))
        scored.sort(key=lambda x: x[0], reverse=True)
        out: List[Dict[str, Any]] = []
        for sim, rec in scored[:top_k]:
            out.append({
                "charter_id": rec.charter_id,
                "path": rec.path,
                "similarity": round(sim, 4),
                "quality": rec.quality,
                "token_cost": rec.token_cost,
                "tags": list(rec.tags),
            })
        return out


class AgentSkillRuntime:
    """Programmed skills exposed to the agent LLM environment."""

    def __init__(
        self,
        *,
        router: Optional[QuantumRouter] = None,
        store: Optional[MuscleMemoryStore] = None,
        boss: Optional[BossAgent] = None,
        roster: Optional[List[Agent]] = None,
    ):
        self.router = router or QuantumRouter()
        self.store = store or MuscleMemoryStore()
        self.boss = boss
        self.roster = roster or []
        self.last_sync: Dict[str, Any] = {}

    # ── 1. QueryMuscleMemory ────────────────────────────────────────────────

    def QueryMuscleMemory(
        self,
        current_state_vector: Sequence[float],
        threshold: float = 0.82,
    ) -> Dict[str, Any]:
        """Replace standard RAG with successful-charter precedent lookup."""
        hits = self.store.query(current_state_vector, threshold=threshold)
        return {
            "skill": "QueryMuscleMemory",
            "hits": hits,
            "hit_count": len(hits),
            "threshold": threshold,
            "fallback": "follow_charter" if not hits else "apply_precedent",
            "recommended_path": hits[0]["path"] if hits else None,
        }

    # ── 2. EvaluateRhythmMarker ─────────────────────────────────────────────

    def EvaluateRhythmMarker(
        self,
        agent_output_json: Mapping[str, Any],
        expected_schema: Mapping[str, Any],
    ) -> Dict[str, Any]:
        """Self-audit intermediate work; route back on schema failure."""
        handoff = handoff_synergy(agent_output_json, expected_schema)
        d = handoff["D"]
        passed = handoff["schema_compliant"] and handoff["Q_s"] >= math.exp(-1e-9)
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
                        f"type:{key}:expected={type(expected_schema[key]).__name__}"
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

    # ── 3. ExecuteQuantumCollapse ───────────────────────────────────────────

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
        # ensure all options present
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
        result["H_ctx"] = contextual_entropy(
            {"noise": context_entropy, "missing_ratio": context_entropy * 0.5}
        ) if context_entropy else 0.0
        return result

    # ── 4. TriggerMondayMorningSync ─────────────────────────────────────────

    def TriggerMondayMorningSync(
        self,
        telemetry_data: Mapping[str, Any],
        *,
        roster: Optional[List[Agent]] = None,
        boss: Optional[BossAgent] = None,
    ) -> Dict[str, Any]:
        """Downtime RLAIF: re-weight paths, talent actions from telemetry."""
        team = roster if roster is not None else self.roster
        gm = boss or self.boss
        outcomes: Dict[str, str] = {}
        reweights: Dict[str, Dict[str, float]] = {}

        if gm is not None and team:
            outcomes = gm.monday_morning_sync(team)

        # Re-weight historical success from telemetry path stats
        path_stats = telemetry_data.get("path_stats") or telemetry_data.get("paths") or {}
        for agent in team:
            if not getattr(agent, "talent_eligible", True):
                continue
            mm = dict(agent.muscle_memory_weights)
            for path, stats in path_stats.items():
                if not isinstance(stats, dict):
                    continue
                success_rate = float(stats.get("success_rate", stats.get("quality", 0.5)))
                # pull weights toward observed success
                prev = mm.get(path, 1.0)
                mm[path] = max(0.05, min(8.0, prev * (0.7 + 0.6 * success_rate)))
            agent.muscle_memory_weights = mm
            reweights[agent.name] = dict(mm)

        # Ingest successful runs into muscle memory store
        for run in telemetry_data.get("successful_runs", []):
            vec = run.get("state_vector") or run.get("vector") or [0.5, 0.5, 0.5]
            self.store.add(
                MuscleMemoryRecord(
                    charter_id=str(run.get("charter_id", "unknown")),
                    path=str(run.get("path", "path_A")),
                    state_vector=tuple(float(x) for x in vec),
                    quality=float(run.get("quality", 0.95)),
                    token_cost=int(run.get("token_cost", 200)),
                    tags=tuple(run.get("tags", ())),
                )
            )

        self.last_sync = {
            "skill": "TriggerMondayMorningSync",
            "outcomes": outcomes,
            "reweights": reweights,
            "store_size": len(self.store.records),
            "telemetry_keys": list(telemetry_data.keys()),
        }
        return self.last_sync

    # ── 5. AdjustCorporateRoster ────────────────────────────────────────────

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


def init_boss_agent(name: str = "Alpha-GM") -> Tuple[BossAgent, str]:
    """Create Boss Agent with exact Head Coach system prompt loaded."""
    boss = BossAgent(name)
    boss.system_prompt = BOSS_AGENT_SYSTEM_PROMPT
    boss.acknowledged = True
    return boss, BOSS_ACKNOWLEDGEMENT
