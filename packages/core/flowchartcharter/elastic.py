"""Elastic Requisition / Phantom Node Protocol (Audit V3).

When lean re-hire has shrunk the roster and a novel high-entropy workload
arrives requiring a missing capability, the GM spins a temporary Phantom
Node. Success → promote to ACTIVE full-time. Failure → terminate.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set

from .agents import Agent, AgentStatus, BossAgent
from .survival import SurvivalStatus, generation_params_for_risk


# Capability keywords inferred from workload text
CAPABILITY_KEYWORDS: Dict[str, List[str]] = {
    "sql_optimization": ["sql", "query", "database optimize", "index"],
    "json_parsing": ["json", "parse", "schema"],
    "regex_sanitize": ["regex", "sanitize", "cleanse", "csv"],
    "python_ast": ["python", "ast", "refactor", "code"],
    "refactoring": ["refactor", "legacy", "migrate"],
    "security_audit": ["security", "auth", "token", "oauth", "bearer"],
    "api_gateway": ["api", "gateway", "endpoint", "rest"],
}


@dataclass
class PhantomRecord:
    node_id: str
    capability: str
    role: str
    converted: bool = False
    terminated: bool = False
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ElasticRequisitionBoard:
    """Tracks known capabilities + phantom lifecycle."""

    known_capabilities: Set[str] = field(default_factory=set)
    phantoms: List[PhantomRecord] = field(default_factory=list)
    log: List[str] = field(default_factory=list)

    def register_agent(self, agent: Agent, capabilities: Optional[List[str]] = None) -> None:
        caps = capabilities or _infer_caps_from_role(agent.role)
        self.known_capabilities.update(caps)
        # store on agent for later
        if not hasattr(agent, "capabilities"):
            agent.capabilities = list(caps)  # type: ignore[attr-defined]
        else:
            for c in caps:
                if c not in agent.capabilities:  # type: ignore[attr-defined]
                    agent.capabilities.append(c)  # type: ignore[attr-defined]

    def rebuild_from_roster(self, roster: List[Agent]) -> None:
        self.known_capabilities = set()
        for agent in roster:
            if agent.status == AgentStatus.FIRED:
                continue
            if isinstance(agent, BossAgent):
                continue
            caps = getattr(agent, "capabilities", None) or _infer_caps_from_role(
                agent.role
            )
            self.known_capabilities.update(caps)

    def required_capability(self, workload: str) -> Optional[str]:
        lower = workload.lower()
        for cap, keys in CAPABILITY_KEYWORDS.items():
            if any(k in lower for k in keys):
                if cap not in self.known_capabilities:
                    return cap
        # generic novel high-entropy marker
        if any(
            k in lower
            for k in ("novel", "unprecedented", "unknown", "sql_optimization")
        ):
            return "sql_optimization"
        return None

    def evaluate(
        self,
        workload: str,
        roster: List[Agent],
        *,
        force_capability: Optional[str] = None,
    ) -> Optional[Agent]:
        """Spin Phantom Node if capability gap exists."""
        self.rebuild_from_roster(roster)
        cap = force_capability or self.required_capability(workload)
        if cap is None or cap in self.known_capabilities:
            return None

        self.log.append(
            f"Elastic requisition: missing capability '{cap}' for '{workload}'"
        )
        phantom = Agent(
            f"Phantom-{cap[:12]}",
            f"Ad-Hoc {cap} Specialist",
            {cap: 1.0, "general": 0.4},
        )
        phantom.status = AgentStatus.ACTIVE
        phantom.capabilities = [cap]  # type: ignore[attr-defined]
        phantom.is_phantom = True  # type: ignore[attr-defined]
        phantom.termination_risk_index = 0.8  # must prove worth instantly
        phantom.survival_status = SurvivalStatus.AT_RISK
        phantom.generation = generation_params_for_risk(0.8)
        phantom.corporate_rank = 0.8
        phantom.refresh_survival_prompt()

        roster.append(phantom)
        self.known_capabilities.add(cap)
        rec = PhantomRecord(
            node_id=phantom.id,
            capability=cap,
            role=phantom.role,
            reason="elastic_requisition",
        )
        self.phantoms.append(rec)
        self.log.append(
            f"Phantom Node {phantom.name} ({phantom.id}) spun for {cap}"
        )
        return phantom

    def resolve_phantoms(
        self,
        roster: List[Agent],
        *,
        fitness_hire: float = 0.9,
        fitness_fire: float = 0.55,
    ) -> List[Dict[str, Any]]:
        """After Monday Sync: convert successful phantoms or terminate flops."""
        outcomes: List[Dict[str, Any]] = []
        for agent in roster:
            if not getattr(agent, "is_phantom", False):
                continue
            if agent.status == AgentStatus.FIRED:
                continue
            f = agent.calculate_fitness() if agent.history else 0.0
            if f >= fitness_hire:
                agent.is_phantom = False  # type: ignore[attr-defined]
                agent.status = AgentStatus.PROMOTED
                agent.termination_risk_index = max(
                    0.0, agent.termination_risk_index - 0.3
                )
                agent.refresh_survival_prompt()
                outcomes.append(
                    {
                        "agent": agent.name,
                        "action": "CONVERT_FULL_TIME",
                        "fitness": round(f, 4),
                    }
                )
                self.log.append(
                    f"Phantom {agent.name} converted to full-time (F={f:.3f})"
                )
                for p in self.phantoms:
                    if p.node_id == agent.id:
                        p.converted = True
            elif f < fitness_fire or not agent.history:
                agent.status = AgentStatus.FIRED
                agent.survival_status = SurvivalStatus.TERMINATED
                agent.refresh_survival_prompt()
                outcomes.append(
                    {
                        "agent": agent.name,
                        "action": "TERMINATE_PHANTOM",
                        "fitness": round(f, 4),
                    }
                )
                self.log.append(
                    f"Phantom {agent.name} terminated (F={f:.3f})"
                )
                for p in self.phantoms:
                    if p.node_id == agent.id:
                        p.terminated = True
        self.rebuild_from_roster(roster)
        return outcomes

    def export(self) -> Dict[str, Any]:
        return {
            "known_capabilities": sorted(self.known_capabilities),
            "phantoms": [p.to_dict() for p in self.phantoms],
            "log": list(self.log[-32:]),
        }


def _infer_caps_from_role(role: str) -> List[str]:
    lower = role.lower()
    caps: List[str] = []
    if "extract" in lower or "data" in lower or "clean" in lower:
        caps.extend(["json_parsing", "regex_sanitize"])
    if "valid" in lower or "qa" in lower:
        caps.append("json_parsing")
    if "synth" in lower or "generat" in lower or "code" in lower:
        caps.extend(["python_ast", "refactoring"])
    if "security" in lower or "auth" in lower:
        caps.append("security_audit")
    if "api" in lower:
        caps.append("api_gateway")
    if not caps:
        caps.append("general")
    return caps
