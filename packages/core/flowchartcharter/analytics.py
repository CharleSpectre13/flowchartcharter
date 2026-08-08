"""Analytics Chief — 5-Day End-of-Week Analytics Protocol (capstone node).

Separates macro-trend optimization from day-to-day GM execution.

- Asynchronous relative to super-steps
- 5-day moving averages for statistical maturity (no 1–2 day over-correction)
- RosterRecommendationDossier → Monday Morning Sync (GM executes, does not guess)
- Cheat-code extraction into Muscle-Memory / Living Playbook when runs beat baseline
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .agents import Agent, AgentStatus, BossAgent
from .fitness import INDUSTRY_BENCHMARK
from .living_playbook import LivingPlaybook
from .muscle_memory import (
    ExecutionMemoryRecord,
    MuscleMemoryVectorDB,
)

WORKWEEK_DAYS = 5
MIN_SAMPLES_FOR_TREND = 2
PROMOTE_MA_MULTIPLIER = 1.15
TERMINATE_MA_MULTIPLIER = 0.55
CHEAT_CODE_TOKEN_BEAT = 0.15
CHEAT_CODE_LATENCY_BEAT = 0.15
CHEAT_CODE_QUALITY_FLOOR = 0.93


@dataclass
class DailyTelemetrySnapshot:
    """One agent-day of immutable telemetry (memory-safe handoff unit)."""

    day_index: int
    agent_name: str
    agent_id: str
    role: str
    fitness: float
    quality: float
    token_spend: int
    expected_tokens: int
    latency: float
    expected_latency: float
    schema_errors: int
    termination_risk: float
    status: str
    path: str = ""
    flow_path: Tuple[str, ...] = ()
    prompt_tweak: str = ""
    workload: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["flow_path"] = list(self.flow_path)
        return d


@dataclass
class AgentTrend:
    """5-day moving averages for one agent."""

    agent_name: str
    agent_id: str
    role: str
    samples: int
    fitness_ma: float
    quality_ma: float
    token_ma: float
    expected_token_ma: float
    latency_ma: float
    expected_latency_ma: float
    risk_ma: float
    schema_errors_total: int
    token_bloat_ratio: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RosterActionRec:
    """Single Board-level recommendation."""

    agent_name: str
    agent_id: str
    action: str  # PROMOTE | TERMINATE | RETAIN | DEMOTE
    confidence: float
    fitness_ma: float
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CheatCodeExtraction:
    """Trajectory that beat baseline — inject into Muscle-Memory."""

    memory_id: str
    job_type: str
    flow_path: List[str]
    prompt_tweak: str
    quality: float
    token_cost: int
    expected_tokens: int
    savings_ratio: float
    source_day: int
    agent_name: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RosterRecommendationDossier:
    """5-day end-of-week deliverable for Monday Morning Sync."""

    dossier_id: str
    week_index: int
    days_covered: int
    generated_at_cycle: int
    recommendations: List[RosterActionRec] = field(default_factory=list)
    trends: List[AgentTrend] = field(default_factory=list)
    cheat_codes: List[CheatCodeExtraction] = field(default_factory=list)
    baseline_quality: float = 0.90
    baseline_fitness: float = INDUSTRY_BENCHMARK
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dossier_id": self.dossier_id,
            "week_index": self.week_index,
            "days_covered": self.days_covered,
            "generated_at_cycle": self.generated_at_cycle,
            "recommendations": [r.to_dict() for r in self.recommendations],
            "trends": [t.to_dict() for t in self.trends],
            "cheat_codes": [c.to_dict() for c in self.cheat_codes],
            "baseline_quality": self.baseline_quality,
            "baseline_fitness": self.baseline_fitness,
            "notes": list(self.notes),
            "promote": [r.agent_name for r in self.recommendations if r.action == "PROMOTE"],
            "terminate": [r.agent_name for r in self.recommendations if r.action == "TERMINATE"],
        }

    def action_map(self) -> Dict[str, str]:
        return {r.agent_name: r.action for r in self.recommendations}


class AnalyticsChief:
    """Capstone node — macro-trend optimization on a 5-day cadence."""

    def __init__(
        self,
        name: str = "Analytics-Chief",
        *,
        workweek_days: int = WORKWEEK_DAYS,
        industry_benchmark: float = INDUSTRY_BENCHMARK,
    ) -> None:
        self.name = name
        self.role = "Analytics Chief (Board Staff)"
        self.workweek_days = max(1, int(workweek_days))
        self.industry_benchmark = industry_benchmark
        self.talent_eligible = False
        self.status = AgentStatus.ACTIVE

        self._day_ledger: List[List[DailyTelemetrySnapshot]] = []
        self._current_day: List[DailyTelemetrySnapshot] = []
        self.day_counter: int = 0
        self.week_index: int = 0
        self.cycle_counter: int = 0
        self.last_dossier: Optional[RosterRecommendationDossier] = None
        self.dossier_history: List[RosterRecommendationDossier] = []
        self.audit_log: List[str] = []

    def ingest_cycle(
        self,
        *,
        agents: Sequence[Agent],
        workload: str = "",
        path_trace: Optional[Mapping[str, Any]] = None,
        quality: float = 0.0,
        flow_path: Optional[Sequence[str]] = None,
    ) -> None:
        """Record one charter-cycle snapshot per operational agent."""
        self.cycle_counter += 1
        path_trace = path_trace or {}
        fp = tuple(flow_path or ())
        for agent in agents:
            if isinstance(agent, BossAgent):
                continue
            if not getattr(agent, "talent_eligible", True):
                continue
            if not agent.history and agent.ledger.schema_errors == 0:
                continue

            last = agent.history[-1] if agent.history else None
            token_spend = int(last.token_cost) if last else 0
            expected_tokens = (
                int(last.expected_token_cost)
                if last and last.expected_token_cost > 0
                else token_spend
            )
            latency = float(last.execution_time) if last else 0.0
            expected_latency = (
                float(last.expected_time) if last and last.expected_time > 0 else max(latency, 1e-6)
            )
            q = float(last.quality_score) if last else quality
            fit = agent.calculate_fitness() if agent.history else 0.0

            path = ""
            tweak = ""
            if agent.name in path_trace and isinstance(path_trace[agent.name], dict):
                tr = path_trace[agent.name]
                path = str(tr.get("chosen_path") or "")
                tweak = str(tr.get("prompt_tweak") or "")
                if not fp and tr.get("flow_path"):
                    fp = tuple(tr["flow_path"])

            snap = DailyTelemetrySnapshot(
                day_index=self.day_counter,
                agent_name=agent.name,
                agent_id=agent.id,
                role=agent.role,
                fitness=fit,
                quality=q,
                token_spend=token_spend,
                expected_tokens=expected_tokens,
                latency=latency,
                expected_latency=expected_latency,
                schema_errors=agent.ledger.schema_errors,
                termination_risk=agent.termination_risk_index,
                status=agent.status.value,
                path=path,
                flow_path=fp,
                prompt_tweak=tweak,
                workload=workload,
            )
            self._current_day.append(snap)

    def close_day(self) -> int:
        """Seal current day into the 5-day ring buffer."""
        self._day_ledger.append(list(self._current_day))
        self._current_day = []
        self.day_counter += 1
        max_days = self.workweek_days * 2
        if len(self._day_ledger) > max_days:
            self._day_ledger = self._day_ledger[-max_days:]
        return self.day_counter - 1

    def days_ready(self) -> int:
        return len(self._day_ledger)

    def workweek_complete(self) -> bool:
        return self.days_ready() >= self.workweek_days

    def _window_snapshots(self) -> List[DailyTelemetrySnapshot]:
        window = self._day_ledger[-self.workweek_days :]
        out: List[DailyTelemetrySnapshot] = []
        for day in window:
            out.extend(day)
        return out

    def _compute_trends(self, snaps: Sequence[DailyTelemetrySnapshot]) -> List[AgentTrend]:
        by_agent: Dict[str, List[DailyTelemetrySnapshot]] = defaultdict(list)
        for s in snaps:
            by_agent[s.agent_name].append(s)

        trends: List[AgentTrend] = []
        for name, rows in by_agent.items():
            n = len(rows)
            if n < 1:
                continue
            fit_ma = sum(r.fitness for r in rows) / n
            q_ma = sum(r.quality for r in rows) / n
            tok_ma = sum(r.token_spend for r in rows) / n
            exp_tok_ma = sum(r.expected_tokens for r in rows) / n
            lat_ma = sum(r.latency for r in rows) / n
            exp_lat_ma = sum(r.expected_latency for r in rows) / n
            risk_ma = sum(r.termination_risk for r in rows) / n
            err_tot = rows[-1].schema_errors
            exp = exp_tok_ma if exp_tok_ma > 0 else max(tok_ma, 1.0)
            bloat = max(0.0, tok_ma - exp) / exp
            trends.append(
                AgentTrend(
                    agent_name=name,
                    agent_id=rows[-1].agent_id,
                    role=rows[-1].role,
                    samples=n,
                    fitness_ma=round(fit_ma, 4),
                    quality_ma=round(q_ma, 4),
                    token_ma=round(tok_ma, 2),
                    expected_token_ma=round(exp_tok_ma, 2),
                    latency_ma=round(lat_ma, 4),
                    expected_latency_ma=round(exp_lat_ma, 4),
                    risk_ma=round(risk_ma, 4),
                    schema_errors_total=err_tot,
                    token_bloat_ratio=round(bloat, 4),
                )
            )
        trends.sort(key=lambda t: t.fitness_ma, reverse=True)
        return trends

    def _recommend(self, trends: Sequence[AgentTrend]) -> List[RosterActionRec]:
        recs: List[RosterActionRec] = []
        bench = self.industry_benchmark
        for t in trends:
            if t.samples < MIN_SAMPLES_FOR_TREND:
                recs.append(
                    RosterActionRec(
                        agent_name=t.agent_name,
                        agent_id=t.agent_id,
                        action="RETAIN",
                        confidence=0.4,
                        fitness_ma=t.fitness_ma,
                        rationale=(
                            f"Insufficient samples ({t.samples}) for "
                            f"{self.workweek_days}-day trend — retain"
                        ),
                    )
                )
                continue

            if (
                t.fitness_ma < bench * TERMINATE_MA_MULTIPLIER
                or t.schema_errors_total >= 5
                or t.risk_ma >= 0.85
            ):
                conf = min(
                    1.0,
                    0.55 + (bench * TERMINATE_MA_MULTIPLIER - t.fitness_ma) + 0.1 * t.risk_ma,
                )
                recs.append(
                    RosterActionRec(
                        agent_name=t.agent_name,
                        agent_id=t.agent_id,
                        action="TERMINATE",
                        confidence=round(max(0.5, conf), 3),
                        fitness_ma=t.fitness_ma,
                        rationale=(
                            f"5-day fitness MA={t.fitness_ma:.3f} "
                            f"(floor={bench * TERMINATE_MA_MULTIPLIER:.3f}); "
                            f"errors={t.schema_errors_total}; "
                            f"risk_ma={t.risk_ma:.3f}"
                        ),
                    )
                )
            elif (
                t.fitness_ma >= bench * PROMOTE_MA_MULTIPLIER
                and t.quality_ma >= 0.92
                and t.risk_ma < 0.35
                and t.token_bloat_ratio < 0.2
            ):
                conf = min(
                    1.0,
                    0.6 + (t.fitness_ma - bench * PROMOTE_MA_MULTIPLIER),
                )
                recs.append(
                    RosterActionRec(
                        agent_name=t.agent_name,
                        agent_id=t.agent_id,
                        action="PROMOTE",
                        confidence=round(conf, 3),
                        fitness_ma=t.fitness_ma,
                        rationale=(
                            f"5-day fitness MA={t.fitness_ma:.3f} "
                            f"quality_ma={t.quality_ma:.3f} "
                            f"bloat={t.token_bloat_ratio:.3f}"
                        ),
                    )
                )
            elif t.fitness_ma < bench * 0.75 or t.risk_ma >= 0.55:
                recs.append(
                    RosterActionRec(
                        agent_name=t.agent_name,
                        agent_id=t.agent_id,
                        action="DEMOTE",
                        confidence=0.65,
                        fitness_ma=t.fitness_ma,
                        rationale=(
                            f"Soft underperformance MA={t.fitness_ma:.3f} "
                            f"risk_ma={t.risk_ma:.3f}"
                        ),
                    )
                )
            else:
                recs.append(
                    RosterActionRec(
                        agent_name=t.agent_name,
                        agent_id=t.agent_id,
                        action="RETAIN",
                        confidence=0.7,
                        fitness_ma=t.fitness_ma,
                        rationale=f"Stable 5-day MA={t.fitness_ma:.3f}",
                    )
                )
        return recs

    def _extract_cheat_codes(
        self, snaps: Sequence[DailyTelemetrySnapshot]
    ) -> List[CheatCodeExtraction]:
        codes: List[CheatCodeExtraction] = []
        seen: set = set()
        for s in snaps:
            if s.quality < CHEAT_CODE_QUALITY_FLOOR:
                continue
            if s.expected_tokens <= 0 or s.token_spend <= 0:
                continue
            token_beat = 1.0 - (s.token_spend / max(1, s.expected_tokens))
            lat_beat = 0.0
            if s.expected_latency > 0 and s.latency > 0:
                lat_beat = 1.0 - (s.latency / s.expected_latency)
            if token_beat < CHEAT_CODE_TOKEN_BEAT and lat_beat < CHEAT_CODE_LATENCY_BEAT:
                continue
            if not s.flow_path and not s.path:
                continue
            flow = list(s.flow_path) if s.flow_path else [s.path]
            key = (s.workload or s.agent_name, tuple(flow), s.prompt_tweak)
            if key in seen:
                continue
            seen.add(key)
            savings = max(token_beat, lat_beat)
            tweak = s.prompt_tweak or (
                f"Beat baseline by {savings:.0%}: prefer path "
                f"{' → '.join(flow)}; keep schema lock."
            )
            codes.append(
                CheatCodeExtraction(
                    memory_id=f"CC-{uuid.uuid4().hex[:8].upper()}",
                    job_type=s.workload or f"path:{s.path}",
                    flow_path=flow,
                    prompt_tweak=tweak,
                    quality=s.quality,
                    token_cost=s.token_spend,
                    expected_tokens=s.expected_tokens,
                    savings_ratio=round(savings, 4),
                    source_day=s.day_index,
                    agent_name=s.agent_name,
                )
            )
        codes.sort(key=lambda c: c.savings_ratio, reverse=True)
        return codes[:12]

    def execute_end_of_week_audit(
        self,
        *,
        muscle_db: Optional[MuscleMemoryVectorDB] = None,
        living_playbook: Optional[LivingPlaybook] = None,
        force: bool = False,
    ) -> Optional[RosterRecommendationDossier]:
        """Triggered every 5 days. Produces dossier + injects cheat codes."""
        if not force and not self.workweek_complete():
            self.audit_log.append(
                f"Audit deferred: days={self.days_ready()}/" f"{self.workweek_days}"
            )
            return None

        snaps = self._window_snapshots()
        if force and not snaps and self._current_day:
            snaps = list(self._current_day)

        trends = self._compute_trends(snaps)
        recs = self._recommend(trends)
        cheats = self._extract_cheat_codes(snaps)

        self.week_index += 1
        dossier = RosterRecommendationDossier(
            dossier_id=(f"DOSS-{self.week_index:04d}-{uuid.uuid4().hex[:6].upper()}"),
            week_index=self.week_index,
            days_covered=min(self.workweek_days, max(1, self.days_ready())),
            generated_at_cycle=self.cycle_counter,
            recommendations=recs,
            trends=trends,
            cheat_codes=cheats,
            baseline_fitness=self.industry_benchmark,
            notes=[
                f"5-day MA window; samples={len(snaps)}",
                f"promotions={sum(1 for r in recs if r.action == 'PROMOTE')}",
                f"terminations=" f"{sum(1 for r in recs if r.action == 'TERMINATE')}",
                f"cheat_codes={len(cheats)}",
            ],
        )

        injected = self._inject_cheat_codes(
            cheats, muscle_db=muscle_db, living_playbook=living_playbook
        )
        dossier.notes.append(f"cheat_codes_injected={injected}")

        self.last_dossier = dossier
        self.dossier_history.append(dossier)
        self.audit_log.append(
            f"EOW audit week={self.week_index} dossier={dossier.dossier_id} "
            f"recs={len(recs)} cheats={injected}"
        )
        return dossier

    def _inject_cheat_codes(
        self,
        cheats: Sequence[CheatCodeExtraction],
        *,
        muscle_db: Optional[MuscleMemoryVectorDB],
        living_playbook: Optional[LivingPlaybook],
    ) -> int:
        count = 0
        for cc in cheats:
            if muscle_db is not None:
                muscle_db.commit_memory(
                    ExecutionMemoryRecord(
                        memory_id=cc.memory_id,
                        job_type=cc.job_type,
                        state_vector=[0.5, 0.3, 3.0, 0.05],
                        successful_flow_path=list(cc.flow_path),
                        entanglement_score=min(1.0, cc.quality),
                        prompt_tweak=cc.prompt_tweak,
                        quality=cc.quality,
                        token_cost=cc.token_cost,
                        tags=("cheat_code", "analytics_eow"),
                    )
                )
                count += 1
            if living_playbook is not None:
                living_playbook.commit_from_execution(
                    job_type=cc.job_type,
                    flow_path=cc.flow_path,
                    payload={"task": cc.job_type, "source": "analytics_eow"},
                    quality=cc.quality,
                    token_cost=cc.token_cost,
                    expected_tokens=cc.expected_tokens,
                    entanglement=cc.quality,
                    prompt_tweak=cc.prompt_tweak,
                    agent_caps={"general": 1.0},
                    entropy=0.25,
                    rationale=(
                        f"EOW cheat code savings={cc.savings_ratio:.0%} " f"from {cc.agent_name}"
                    ),
                )
        return count

    def export(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "day_counter": self.day_counter,
            "days_ready": self.days_ready(),
            "week_index": self.week_index,
            "cycle_counter": self.cycle_counter,
            "workweek_days": self.workweek_days,
            "workweek_complete": self.workweek_complete(),
            "last_dossier": (self.last_dossier.to_dict() if self.last_dossier else None),
            "audit_log": list(self.audit_log[-20:]),
        }
