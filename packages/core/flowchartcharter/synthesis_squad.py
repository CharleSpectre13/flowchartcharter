"""v1.7 Lazy Global Synthesis Squad — on-demand map-reduce over graph communities.

Spun up by the Boss Agent only for GLOBAL route lanes. Operates under a
unified CFO token ceiling. Final report is committed as a reusable playbook
asset (Living Playbook / Muscle-Memory), not discarded.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence

from pydantic import BaseModel, Field

from .knowledge_graph import KnowledgeGraph
from .muscle_memory import (
    ExecutionMemoryRecord,
    MuscleMemoryVectorDB,
    encode_state,
)


class CommunityMapResult(BaseModel):
    """One community mapper output (map phase)."""

    community_id: str
    title: str
    executive_summary: str
    importance: float = Field(ge=0.0, le=1.0)
    entity_count: int = Field(ge=0)
    tokens: int = Field(ge=0)


class GlobalSynthesisReport(BaseModel):
    """Reduce-phase global report committed as playbook asset."""

    report_id: str
    theme: str
    synthesis: str
    communities: List[CommunityMapResult] = Field(default_factory=list)
    quality: float = Field(ge=0.0, le=1.0)
    tokens: int = Field(ge=0)
    cfo_ceiling: int = Field(ge=0)
    under_budget: bool = True
    playbook_committed: bool = False
    duration_ms: float = 0.0
    backend: str = "kg_deterministic"


@dataclass
class SynthesisSquadMember:
    """Ephemeral squad worker bound to one community partition."""

    name: str
    community_id: str
    tokens_spent: int = 0
    active: bool = True


@dataclass
class LazyGlobalSynthesisSquad:
    """Temporary map-reduce squad for global-theme questions.

    Lifecycle:
      spin_up → map(communities) → reduce(report) → commit_playbook → dissolve
    """

    kg: Optional[KnowledgeGraph] = None
    muscle: Optional[MuscleMemoryVectorDB] = None
    cfo_ceiling: int = 2200
    quiet: bool = True
    members: List[SynthesisSquadMember] = field(default_factory=list)
    reports_committed: int = 0
    last_report: Optional[GlobalSynthesisReport] = None
    llm_client: Any = None

    def __post_init__(self) -> None:
        if self.kg is None:
            self.kg = KnowledgeGraph()
        if self.muscle is None:
            self.muscle = MuscleMemoryVectorDB(quiet=True)

    def spin_up(self, theme: str) -> List[SynthesisSquadMember]:
        """Allocate one mapper per community that matches the theme."""
        global_pack = self.kg.global_search(theme)
        communities = global_pack.get("communities") or []
        self.members = []
        for i, c in enumerate(communities):
            cid = self._community_id(c, i)
            self.members.append(
                SynthesisSquadMember(
                    name=f"SynthMapper-{i + 1}",
                    community_id=cid,
                )
            )
        if not self.members:
            self.members.append(
                SynthesisSquadMember(
                    name="SynthMapper-1",
                    community_id="core_concept",
                )
            )
        if not self.quiet:
            print(
                f"[SynthesisSquad] spun up {len(self.members)} mappers "
                f"for theme={theme!r} ceiling={self.cfo_ceiling}"
            )
        return list(self.members)

    def synthesize(
        self,
        theme: str,
        *,
        cfo_ceiling: Optional[int] = None,
        commit_playbook: bool = True,
    ) -> GlobalSynthesisReport:
        """Full lazy global synthesis under unified CFO budget."""
        t0 = time.perf_counter()
        ceiling = int(cfo_ceiling or self.cfo_ceiling)
        self.spin_up(theme)

        map_results = self._map_phase(theme, ceiling)
        tokens_used = sum(m.tokens for m in map_results)
        under = tokens_used <= ceiling

        synthesis, backend = self._reduce_phase(theme, map_results)
        quality = self._quality(map_results, under)
        report_id = f"GSR-{uuid.uuid4().hex[:10].upper()}"

        report = GlobalSynthesisReport(
            report_id=report_id,
            theme=theme,
            synthesis=synthesis,
            communities=map_results,
            quality=quality,
            tokens=tokens_used,
            cfo_ceiling=ceiling,
            under_budget=under,
            playbook_committed=False,
            duration_ms=round((time.perf_counter() - t0) * 1000.0, 2),
            backend=backend,
        )

        if commit_playbook and under and quality >= 0.80:
            self._commit_as_playbook(report)
            report.playbook_committed = True
            self.reports_committed += 1

        self.last_report = report
        self.dissolve()
        return report

    def _map_phase(
        self,
        theme: str,
        ceiling: int,
    ) -> List[CommunityMapResult]:
        """Map: each member summarizes one community (budget-aware)."""
        pack = self.kg.global_search(theme)
        communities = pack.get("communities") or []
        if not communities:
            communities = list(
                self.kg.data.get("community_reports", {}).values()
            )

        results: List[CommunityMapResult] = []
        spent = 0
        per_mapper = max(80, ceiling // max(1, len(self.members)))

        for i, member in enumerate(self.members):
            if spent >= ceiling:
                member.active = False
                continue
            if i >= len(communities):
                break
            c = communities[i]
            cost = min(per_mapper, 120 + int(c.get("entity_count", 0) * 8))
            if spent + cost > ceiling:
                cost = max(40, ceiling - spent)
            spent += cost
            member.tokens_spent = cost
            results.append(
                CommunityMapResult(
                    community_id=self._community_id(c, i),
                    title=str(c.get("title", member.community_id)),
                    executive_summary=str(c.get("executive_summary", ""))[:800],
                    importance=float(c.get("importance", 0.5)),
                    entity_count=int(c.get("entity_count", 0)),
                    tokens=cost,
                )
            )
        return results

    def _reduce_phase(
        self,
        theme: str,
        maps: Sequence[CommunityMapResult],
    ):
        """Reduce: Port when live, else deterministic KG summaries."""
        if not maps:
            return f"No community signal for theme={theme!r}.", "kg_deterministic"
        ordered = sorted(maps, key=lambda m: -m.importance)
        lines = [f"Global synthesis for theme: {theme}", ""]
        for m in ordered:
            lines.append(
                f"• [{m.importance:.2f}] {m.title} "
                f"({m.entity_count} entities, {m.tokens} tok)"
            )
            lines.append(f"  {m.executive_summary[:240]}")
        lines.append("")
        lines.append("Reduce: " + " | ".join(m.title for m in ordered[:4]))
        deterministic = "\n".join(lines)
        client = self.llm_client
        live = bool(getattr(getattr(client, "bridge", None), "live", False))
        if not live:
            return deterministic, "kg_deterministic"
        try:
            from .production import LLMExecutionRequest
            resp = client.execute(
                LLMExecutionRequest(
                    workload=(
                        f"Reduce community maps for theme={theme!r}. "
                        f"Maps:\n{deterministic[:1200]}"
                    ),
                    path="path_B",
                    termination_risk_index=0.2,
                    system_prompt="Schema-strict global synthesis reducer.",
                    playbook_constraints=["Stay under CFO", "No invented communities"],
                    expected_output_keys=["result", "quality", "path", "tokens"],
                    agent_name="SynthesisSquad",
                    role="GLOBAL",
                )
            )
            if resp.ok and resp.output and resp.output.notes:
                return resp.output.notes, "port_reduce"
            payload = (resp.output.output_payload if resp.output else {}) or {}
            text = payload.get("synthesis") or deterministic
            return str(text), "port_reduce"
        except Exception:
            return deterministic, "kg_deterministic"

    def _quality(
        self,
        maps: Sequence[CommunityMapResult],
        under_budget: bool,
    ) -> float:
        if not maps:
            return 0.3
        n_comm = max(1, len(self.kg.data.get("communities", {}) or {1: 1}))
        coverage = min(1.0, len(maps) / n_comm)
        importance = sum(m.importance for m in maps) / len(maps)
        budget_bonus = 0.08 if under_budget else -0.15
        return max(
            0.0,
            min(1.0, 0.45 * coverage + 0.45 * importance + budget_bonus + 0.1),
        )

    def _commit_as_playbook(self, report: GlobalSynthesisReport) -> None:
        """Persist global report as Muscle-Memory playbook asset."""
        payload = {
            "job_type": "global_synthesis",
            "theme": report.theme,
            "report_id": report.report_id,
        }
        path = [
            "U_SynthesisSquad",
            f"map:{len(report.communities)}",
            "reduce:global_report",
            f"commit:{report.report_id}",
        ]
        record = ExecutionMemoryRecord(
            memory_id=report.report_id,
            job_type="global_synthesis",
            state_vector=encode_state(payload),
            successful_flow_path=path,
            entanglement_score=report.quality,
            prompt_tweak=f"LazyGraphRAG map-reduce theme={report.theme!r}",
            quality=report.quality,
            token_cost=report.tokens,
            tags=("global", "synthesis", "v1.7", "playbook"),
        )
        self.muscle.commit_memory(record)

    def dissolve(self) -> None:
        """Tear down ephemeral squad (zero residual load)."""
        for m in self.members:
            m.active = False
            m.tokens_spent = 0
        self.members = []

    def _community_id(self, community: Mapping[str, Any], index: int) -> str:
        title = str(community.get("title", f"community_{index}"))
        communities = self.kg.data.get("communities") or {}
        for key, label in communities.items():
            if label == title or key in title.lower().replace(" ", "_"):
                return key
        slug = title.split("—")[0].strip().lower().replace(" ", "_")[:40]
        return slug or f"community_{index}"

    def stats(self) -> Dict[str, Any]:
        return {
            "reports_committed": self.reports_committed,
            "active_members": sum(1 for m in self.members if m.active),
            "cfo_ceiling": self.cfo_ceiling,
            "last_report_id": (
                self.last_report.report_id if self.last_report else None
            ),
            "muscle": self.muscle.stats() if self.muscle else {},
        }
