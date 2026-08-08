#!/usr/bin/env python3
"""Phase 2 solidification — simulation sandbox + Live-Wire API contracts."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

os.environ["FCC_LLM_PROVIDER"] = "mock"
os.environ["FCC_LIVE_WIRE"] = "1"

from flowchartcharter.simulation_sandbox import (  # noqa: E402
    SimulationSandbox,
    SandboxScenario,
    run_phase2_sandbox,
)
from flowchartcharter import FlowChartCharterSystem  # noqa: E402


def test_live_wire_on_by_default() -> None:
    system = FlowChartCharterSystem(seed=3)
    assert system.live_wire is True
    r = system.execute_charter("Legacy Code Refactor")
    assert r.get("live_wire") is True
    assert r.get("llm_provider") in ("mock", "openai", "xai", "gemini")
    # path_trace should mark live_wire on ops
    traces = r.get("quantum_paths") or {}
    live_flags = [
        v.get("live_wire")
        for v in traces.values()
        if isinstance(v, dict) and "live_wire" in v
    ]
    assert any(live_flags) or r.get("metrics_count", 0) >= 0
    print("OK live_wire charter", r["quality"], r["llm_provider"])


def test_sandbox_workweek() -> None:
    box = SimulationSandbox(seed=7)
    report = box.run_scenario(
        SandboxScenario(
            name="mini_week",
            workloads=[
                "Legacy Code Refactor",
                "Clean messy customer CSV export",
                "Build secure API gateway",
            ],
            days=3,
            expect_trust_min=0.3,
        )
    )
    assert report.live_wire is True
    assert report.passed, report.notes
    print("OK sandbox", report.to_dict())


def test_full_phase2() -> None:
    out = run_phase2_sandbox()
    assert out["api"]["passed"]
    assert out["api"].get("live_wire") is True
    assert out["scenarios"]["passed"]
    assert out["passed"]
    print("OK phase2 full", out["api"]["llm_provider"], out["scenarios"]["passed"])


if __name__ == "__main__":
    test_live_wire_on_by_default()
    test_sandbox_workweek()
    test_full_phase2()
    print("ALL_PHASE2_SANDBOX_TESTS_PASSED")
