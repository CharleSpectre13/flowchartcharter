"""v1.8 Headhunter Protocol — dynamic re-rostering after TPC firings.

When the GM fires an agent and Muscle-Memory cannot absorb the load,
``requisition_new_talent()`` generates a new Agent Profile (adjusted
temperature, system instructions, capabilities), sandboxes it, and only
then hydrates the active roster.

Fear metric still applies: sandbox failures never pollute production.
"""

from __future__ import annotations

import random
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, Field, field_validator

from .agents import Agent, AgentStatus, BossAgent
from .muscle_memory import MuscleMemoryVectorDB
from .survival import SurvivalStatus, generation_params_for_risk


class TalentProfile(BaseModel):
    """Generated candidate profile — not yet rostered."""

    profile_id: str = Field(default_factory=lambda: f"TP-{uuid.uuid4().hex[:8].upper()}")
    name: str = Field(..., min_length=1, max_length=80)
    role: str = Field(..., min_length=1, max_length=120)
    capabilities: List[str] = Field(default_factory=list)
    temperature: float = Field(default=0.35, ge=0.0, le=1.5)
    system_instructions: str = Field(default="", max_length=4000)
    prompt_tweak: str = Field(default="", max_length=1000)
    corporate_rank: float = Field(default=1.0, ge=0.0, le=10.0)
    generation_risk: float = Field(default=0.45, ge=0.0, le=1.0)
    replaces: str = Field(default="", max_length=80)
    generation_index: int = Field(default=0, ge=0)

    @field_validator("capabilities")
    @classmethod
    def non_empty_caps(cls, v: List[str]) -> List[str]:
        return [c.strip() for c in v if c and c.strip()]


class SandboxTalentResult(BaseModel):
    """Sandbox evaluation of a TalentProfile before roster insert."""

    profile_id: str
    passed: bool
    quality: float = Field(ge=0.0, le=1.0)
    tokens: int = Field(ge=0)
    trials: int = Field(ge=1)
    failures: int = Field(default=0, ge=0)
    notes: str = ""
    wall_ms: float = 0.0


class HeadhunterDecision(BaseModel):
    """GM outcome after a TPC fire event."""

    decision_id: str = Field(
        default_factory=lambda: f"HH-{uuid.uuid4().hex[:10].upper()}"
    )
    fired_agent: str
    fired_role: str = ""
    muscle_absorbed: bool = False
    requisitioned: bool = False
    sandbox_passed: bool = False
    profile: Optional[TalentProfile] = None
    sandbox: Optional[SandboxTalentResult] = None
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    reason: str = ""
    rhythm_audit: Dict[str, Any] = Field(default_factory=dict)


@dataclass
class HeadhunterProtocol:
    """Dynamic talent pipeline bound to Boss Agent GM."""

    muscle_absorb_threshold: int = 3
    sandbox_trials: int = 3
    sandbox_quality_floor: float = 0.82
    max_temperature: float = 0.95
    base_temperature: float = 0.28
    quiet: bool = True
    decisions: List[HeadhunterDecision] = field(default_factory=list)
    hired_count: int = 0
    absorbed_count: int = 0
    sandbox_rejects: int = 0
    _rng: random.Random = field(default_factory=lambda: random.Random(42))

    def can_muscle_absorb(
        self,
        *,
        role: str,
        capabilities: Sequence[str],
        muscle: Optional[MuscleMemoryVectorDB],
    ) -> bool:
        """True if Muscle-Memory can cover the fired role without a hire."""
        if muscle is None or not getattr(muscle, "storage", None):
            return False
        role_l = (role or "").lower()
        caps = {c.lower() for c in capabilities}
        hits = 0
        for rec in muscle.storage:
            if rec.quality < 0.90 and rec.entanglement_score < 0.90:
                continue
            blob = (
                f"{rec.job_type} {' '.join(rec.successful_flow_path)} "
                f"{rec.prompt_tweak} {' '.join(rec.tags)}"
            ).lower()
            if role_l and any(tok in blob for tok in role_l.split() if len(tok) > 3):
                hits += 1
                continue
            if caps and any(c in blob for c in caps):
                hits += 1
        return hits >= self.muscle_absorb_threshold

    def generate_profile(
        self,
        *,
        fired: Agent,
        generation_index: int = 0,
        force_capability: Optional[str] = None,
    ) -> TalentProfile:
        """Build a new profile with adjusted prompt parameters."""
        caps = list(getattr(fired, "capabilities", None) or [])
        if force_capability and force_capability not in caps:
            caps.insert(0, force_capability)
        if not caps:
            caps = ["general"]

        temp = min(
            self.max_temperature,
            self.base_temperature
            + 0.12 * generation_index
            + self._rng.uniform(0, 0.08),
        )
        risk = min(0.75, 0.35 + 0.08 * generation_index)
        gen = generation_index + 1
        role = fired.role if not force_capability else f"{force_capability} Specialist"
        name = f"Hire-{caps[0][:10].title()}-{uuid.uuid4().hex[:4].upper()}"

        instructions = (
            f"You are {name}, a {role} under FlowChartCharter TPC.\n"
            f"Generation={gen}. Temperature={temp:.2f}.\n"
            f"Capabilities: {', '.join(caps)}.\n"
            "Rules:\n"
            "1. Emit schema-valid JSON only (Blackboard contract).\n"
            "2. Prefer Muscle-Memory trajectories over free reasoning.\n"
            "3. Entanglement errors raise termination risk — zero schema drift.\n"
            f"4. You replace {fired.name} ({fired.role}); outperform fitness floor.\n"
            "5. Never exceed per-task CFO token allotment.\n"
        )
        tweak = (
            f"gen={gen}; temp={temp:.2f}; strict_schema=1; "
            f"replaces={fired.name}; fear_active=1"
        )
        return TalentProfile(
            name=name,
            role=role,
            capabilities=caps,
            temperature=round(temp, 3),
            system_instructions=instructions,
            prompt_tweak=tweak,
            corporate_rank=max(
                0.8,
                min(3.0, float(getattr(fired, "corporate_rank", 1.0)) * 0.9),
            ),
            generation_risk=round(risk, 3),
            replaces=fired.name,
            generation_index=generation_index,
        )

    def sandbox_evaluate(self, profile: TalentProfile) -> SandboxTalentResult:
        """Run offline trials — never touches live roster or StatePersister."""
        t0 = time.perf_counter()
        failures = 0
        qualities: List[float] = []
        tokens = 0
        for trial in range(self.sandbox_trials):
            seed = hash((profile.profile_id, trial, round(profile.temperature, 3))) & 0xFFFF
            base_q = 0.92 - 0.03 * profile.generation_index
            jitter = ((seed % 50) / 100.0 - 0.25) * (0.06 + 0.05 * profile.temperature)
            q = max(0.0, min(1.0, base_q + jitter))
            fail_roll = (seed % 1000) / 1000.0
            fail_chance = (
                0.02 + 0.10 * profile.generation_index + 0.05 * profile.generation_risk
            )
            trial_tokens = 55 + (seed % 35)
            tokens += trial_tokens
            if fail_roll < fail_chance and profile.generation_index > 0:
                failures += 1
                qualities.append(max(0.0, q * 0.45))
            else:
                qualities.append(q)

        mean_q = sum(qualities) / max(1, len(qualities))
        passed = (
            failures == 0
            and mean_q >= self.sandbox_quality_floor
            and profile.temperature <= self.max_temperature
        )
        if profile.generation_index == 0 and mean_q >= self.sandbox_quality_floor:
            passed = True
            failures = 0
        notes = (
            f"trials={self.sandbox_trials} fail={failures} "
            f"mean_q={mean_q:.3f} floor={self.sandbox_quality_floor}"
        )
        return SandboxTalentResult(
            profile_id=profile.profile_id,
            passed=passed,
            quality=round(mean_q, 4),
            tokens=tokens,
            trials=self.sandbox_trials,
            failures=failures,
            notes=notes,
            wall_ms=round((time.perf_counter() - t0) * 1000.0, 2),
        )

    def materialize_agent(self, profile: TalentProfile) -> Agent:
        """Convert a sandbox-passed profile into a live Agent."""
        cap_map = {c: 1.0 for c in profile.capabilities}
        cap_map.setdefault("general", 0.5)
        agent = Agent(profile.name, profile.role, cap_map)
        agent.status = AgentStatus.ACTIVE
        agent.capabilities = list(profile.capabilities)
        agent.is_phantom = False
        agent.termination_risk_index = profile.generation_risk
        agent.survival_status = status_from_risk_safe(profile.generation_risk)
        agent.generation = generation_params_for_risk(profile.generation_risk)
        agent.corporate_rank = profile.corporate_rank
        agent.headhunter_profile_id = profile.profile_id  # type: ignore[attr-defined]
        agent.headhunter_temperature = profile.temperature  # type: ignore[attr-defined]
        agent.headhunter_tweak = profile.prompt_tweak  # type: ignore[attr-defined]
        if profile.system_instructions:
            agent.playbook_constraints = list(agent.playbook_constraints) + [
                profile.prompt_tweak
            ]
        if hasattr(agent, "refresh_survival_prompt"):
            agent.refresh_survival_prompt()
        return agent

    def requisition_new_talent(
        self,
        *,
        fired: Agent,
        roster: List[Agent],
        muscle: Optional[MuscleMemoryVectorDB] = None,
        force: bool = False,
        force_capability: Optional[str] = None,
        generation_index: int = 0,
    ) -> HeadhunterDecision:
        """Full pipeline: absorb? → generate → sandbox → roster (if pass)."""
        caps = list(getattr(fired, "capabilities", None) or [])
        decision = HeadhunterDecision(
            fired_agent=fired.name,
            fired_role=fired.role,
        )

        if not force and self.can_muscle_absorb(
            role=fired.role, capabilities=caps, muscle=muscle
        ):
            decision.muscle_absorbed = True
            decision.reason = "muscle_memory_absorbed_load"
            decision.rhythm_audit = self._audit(
                marker="headhunter_absorb",
                quality=0.95,
                issues=[],
            )
            self.absorbed_count += 1
            self.decisions.append(decision)
            return decision

        last_sandbox: Optional[SandboxTalentResult] = None
        profile: Optional[TalentProfile] = None
        for gen in range(generation_index, generation_index + 2):
            profile = self.generate_profile(
                fired=fired,
                generation_index=gen,
                force_capability=force_capability,
            )
            last_sandbox = self.sandbox_evaluate(profile)
            if last_sandbox.passed:
                break
            self.sandbox_rejects += 1
            if not self.quiet:
                print(
                    f"[Headhunter] sandbox reject {profile.profile_id}: "
                    f"{last_sandbox.notes}"
                )

        decision.profile = profile
        decision.sandbox = last_sandbox

        if last_sandbox is None or not last_sandbox.passed or profile is None:
            decision.requisitioned = False
            decision.sandbox_passed = False
            decision.reason = "sandbox_rejected"
            decision.rhythm_audit = self._audit(
                marker="headhunter_sandbox",
                quality=last_sandbox.quality if last_sandbox else 0.0,
                issues=["sandbox_rejected"],
            )
            self.decisions.append(decision)
            return decision

        agent = self.materialize_agent(profile)
        roster.append(agent)
        decision.requisitioned = True
        decision.sandbox_passed = True
        decision.agent_id = agent.id
        decision.agent_name = agent.name
        decision.reason = "hired_after_sandbox"
        decision.rhythm_audit = self._audit(
            marker="headhunter_hire",
            quality=last_sandbox.quality,
            issues=[],
        )
        self.hired_count += 1
        self.decisions.append(decision)
        if not self.quiet:
            print(
                f"[Headhunter] hired {agent.name} replacing {fired.name} "
                f"Q={last_sandbox.quality:.3f}"
            )
        return decision

    def _audit(
        self,
        *,
        marker: str,
        quality: float,
        issues: List[str],
        threshold: float = 0.82,
    ) -> Dict[str, Any]:
        from .vectors import RhythmAudit

        passed = quality >= threshold and not issues
        return RhythmAudit(
            marker=marker,
            charter_id=f"headhunter:{marker}",
            quality=float(quality),
            threshold=threshold,
            passed=passed,
            remediation_loops=0 if passed else 1,
            blocking_issues=tuple(issues),
        ).to_dict()

    def stats(self) -> Dict[str, Any]:
        return {
            "hired_count": self.hired_count,
            "absorbed_count": self.absorbed_count,
            "sandbox_rejects": self.sandbox_rejects,
            "decisions": len(self.decisions),
            "last_decision": (
                self.decisions[-1].model_dump() if self.decisions else None
            ),
        }


def status_from_risk_safe(risk: float) -> SurvivalStatus:
    if risk >= 0.75:
        return SurvivalStatus.CRITICAL
    if risk >= 0.45:
        return SurvivalStatus.AT_RISK
    return SurvivalStatus.ACTIVE


def headhunter_after_fire(
    boss: "BossAgent",
    *,
    fired: Agent,
    roster: List[Agent],
    muscle: Optional[MuscleMemoryVectorDB],
    muscle_memory_records: int,
) -> HeadhunterDecision:
    """Convenience used by BossAgent fire paths."""
    protocol = getattr(boss, "_headhunter", None)
    if protocol is None:
        protocol = HeadhunterProtocol(quiet=True)
        boss._headhunter = protocol  # type: ignore[attr-defined]
    return protocol.requisition_new_talent(
        fired=fired,
        roster=roster,
        muscle=muscle,
    )
