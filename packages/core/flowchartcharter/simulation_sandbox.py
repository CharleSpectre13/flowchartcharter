"""Scenario sandbox — scripted multi-day enterprise validation.

This is NOT the ExecutionSandbox playpen (see execution_sandbox.py).
Alias: ScenarioSandbox == SimulationSandbox (historical name).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SandboxScenario:
    name: str
    workloads: List[str]
    days: int = 5
    entropy: Optional[float] = None
    expect_trust_min: float = 0.5  # fraction of jobs with trust


@dataclass
class SandboxReport:
    scenario: str
    jobs: int
    trust_rate: float
    live_wire: bool
    llm_provider: str
    dossier_driven: bool
    mean_quality: float
    wall_ms: float
    playbook_modes: Dict[str, int] = field(default_factory=dict)
    passed: bool = False
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario": self.scenario,
            "jobs": self.jobs,
            "trust_rate": self.trust_rate,
            "live_wire": self.live_wire,
            "llm_provider": self.llm_provider,
            "dossier_driven": self.dossier_driven,
            "mean_quality": self.mean_quality,
            "wall_ms": self.wall_ms,
            "playbook_modes": dict(self.playbook_modes),
            "passed": self.passed,
            "notes": list(self.notes),
        }


DEFAULT_SCENARIOS: List[SandboxScenario] = [
    SandboxScenario(
        name="enterprise_workweek",
        workloads=[
            "Legacy Code Refactor",
            "Clean messy customer CSV export",
            "Build secure API gateway",
            "Migrate old database tables",
            "Legacy Code Refactor",
        ],
        days=5,
        expect_trust_min=0.4,
    ),
    SandboxScenario(
        name="high_entropy_burst",
        workloads=[
            "Novel sql_optimization for warehouse queries",
            "Refactor legacy authentication module with modern tokens",
            "Hybrid secure API refactor with data cleanse",
        ],
        days=3,
        entropy=0.8,
        expect_trust_min=0.3,
    ),
]


class SimulationSandbox:
    """In-process Phase 2 validation against FlowChartCharterSystem."""

    def __init__(self, *, seed: int = 11, live_wire: bool = True) -> None:
        # Ensure mock provider for deterministic sandbox
        os.environ.setdefault("FCC_LLM_PROVIDER", "mock")
        os.environ["FCC_LIVE_WIRE"] = "1" if live_wire else "0"
        from .system import FlowChartCharterSystem

        self.system = FlowChartCharterSystem(seed=seed)
        self.live_wire = live_wire

    def run_scenario(self, scenario: SandboxScenario) -> SandboxReport:
        t0 = time.perf_counter()
        qualities: List[float] = []
        trusts = 0
        modes: Dict[str, int] = {}
        notes: List[str] = []

        for i, job in enumerate(scenario.workloads):
            result = self.system.execute_charter(
                job,
                context_entropy=scenario.entropy,
            )
            q = float(result.get("quality") or 0.0)
            qualities.append(q)
            if result.get("trust"):
                trusts += 1
            mode = str(result.get("playbook_mode") or "miss")
            modes[mode] = modes.get(mode, 0) + 1
            # advance analytics day to align with workweek protocol
            if scenario.days > 0:
                self.system.advance_analytics_day()

        # End-of-week / Monday
        eow = self.system.run_end_of_week_protocol(force=True)
        dossier_driven = bool(eow.get("dossier_driven"))
        if not dossier_driven:
            notes.append("dossier not driven (check analytics days)")

        jobs = len(scenario.workloads)
        trust_rate = trusts / max(1, jobs)
        mean_q = sum(qualities) / max(1, len(qualities))
        wall = (time.perf_counter() - t0) * 1000.0

        passed = (
            trust_rate >= scenario.expect_trust_min
            and mean_q >= 0.7
            and bool(self.system.live_wire) == self.live_wire
        )
        if not passed:
            notes.append(
                f"trust_rate={trust_rate:.2f} mean_q={mean_q:.2f} "
                f"need trust>={scenario.expect_trust_min}"
            )

        return SandboxReport(
            scenario=scenario.name,
            jobs=jobs,
            trust_rate=round(trust_rate, 4),
            live_wire=bool(self.system.live_wire),
            llm_provider=self.system.llm_client.bridge.config.provider,
            dossier_driven=dossier_driven,
            mean_quality=round(mean_q, 4),
            wall_ms=round(wall, 2),
            playbook_modes=modes,
            passed=passed,
            notes=notes,
        )

    def run_all(self, scenarios: Optional[List[SandboxScenario]] = None) -> Dict[str, Any]:
        scenarios = scenarios or DEFAULT_SCENARIOS
        reports = [self.run_scenario(s) for s in scenarios]
        return {
            "passed": all(r.passed for r in reports),
            "reports": [r.to_dict() for r in reports],
            "engine_live_wire": self.system.live_wire,
            "roster": len(self.system.roster),
        }

    def run_api_contract_smoke(self) -> Dict[str, Any]:
        """Optional FastAPI TestClient contract check."""
        from fastapi.testclient import TestClient
        from .api_server import create_app

        app = create_app()
        with TestClient(app) as client:
            h = client.get("/health")
            w = client.post(
                "/workload/submit",
                json={
                    "workload": "Legacy Code Refactor",
                    "context_entropy": 0.3,
                },
            )
            r = client.get("/roster/status")
            m = client.post("/system/trigger-monday-sync")
            a = client.post("/system/advance-analytics?run_eow_if_ready=false")
        body = w.json() if w.status_code == 200 else {}
        return {
            "health": h.status_code == 200,
            "submit": w.status_code == 200,
            "live_wire": body.get("live_wire"),
            "llm_provider": body.get("llm_provider"),
            "roster": r.status_code == 200,
            "monday": m.status_code == 200,
            "analytics": a.status_code == 200,
            "passed": all(x.status_code == 200 for x in (h, w, r, m, a)),
        }


def run_phase2_sandbox() -> Dict[str, Any]:
    """CLI entry for Phase 2 solidification."""
    box = SimulationSandbox(seed=11, live_wire=True)
    scenarios = box.run_all()
    api = box.run_api_contract_smoke()
    return {
        "scenarios": scenarios,
        "api": api,
        "passed": scenarios["passed"] and api["passed"],
    }


# Historical name kept; ExecutionSandbox is the playpen.
ScenarioSandbox = SimulationSandbox


if __name__ == "__main__":
    import json

    out = run_phase2_sandbox()
    print(json.dumps(out, indent=2))
    raise SystemExit(0 if out["passed"] else 1)
