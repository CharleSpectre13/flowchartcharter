#!/usr/bin/env python3
"""Pre-flight patches: state persistence + admin API key."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from fastapi.testclient import TestClient  # noqa: E402


def test_state_persistence_survives_restart() -> None:
    with tempfile.TemporaryDirectory() as td:
        state_path = str(Path(td) / "system_state.json")
        os.environ["FCC_STATE_PATH"] = state_path
        os.environ["FCC_LLM_PROVIDER"] = "mock"
        os.environ["FCC_LIVE_WIRE"] = "1"
        os.environ["FCC_ADMIN_OPEN"] = "1"
        os.environ.pop("FCC_ADMIN_KEY", None)

        # reimport fresh modules with env
        for mod in list(sys.modules):
            if mod.startswith("flowchartcharter"):
                del sys.modules[mod]

        from flowchartcharter.system import FlowChartCharterSystem
        from flowchartcharter.state_persister import StatePersister

        s1 = FlowChartCharterSystem(seed=9)
        s1.execute_charter("Legacy Code Refactor")
        s1.advance_analytics_day()
        s1.execute_charter("Clean messy customer CSV export")
        s1.advance_analytics_day()
        path = s1.persist_state()
        assert Path(path).is_file()
        days_before = s1.analytics.days_ready()
        spend_before = s1.token_spend
        risks = {
            a.name: a.termination_risk_index
            for a in s1.roster
            if a.__class__.__name__ != "BossAgent"
        }
        assert days_before >= 1

        # Simulate container restart
        s2 = FlowChartCharterSystem(seed=99)  # different seed
        report = s2.restore_state()
        assert report.get("restored") is True
        assert s2.analytics.days_ready() == days_before
        assert s2.token_spend == spend_before
        print(
            "OK persistence",
            "days",
            days_before,
            "spend",
            spend_before,
            "ops",
            report.get("ops_restored"),
        )


def test_admin_key_locks_system_routes() -> None:
    with tempfile.TemporaryDirectory() as td:
        os.environ["FCC_STATE_PATH"] = str(Path(td) / "s.json")
        os.environ["FCC_ADMIN_KEY"] = "test-secret-key-001"
        os.environ["FCC_ADMIN_OPEN"] = "0"
        os.environ["FCC_LLM_PROVIDER"] = "mock"
        for mod in list(sys.modules):
            if mod.startswith("flowchartcharter"):
                del sys.modules[mod]

        from flowchartcharter.api_server import create_app

        app = create_app()
        with TestClient(app) as client:
            # workload open
            r = client.post(
                "/workload/submit",
                json={"workload": "Legacy Code Refactor"},
            )
            assert r.status_code == 200, r.text

            # system locked without key
            r = client.post("/system/trigger-monday-sync")
            assert r.status_code == 401, r.text

            r = client.post(
                "/system/advance-analytics?run_eow_if_ready=false"
            )
            assert r.status_code == 401

            # with key
            headers = {"X-API-Key": "test-secret-key-001"}
            r = client.post(
                "/system/trigger-monday-sync", headers=headers
            )
            assert r.status_code == 200, r.text

            r = client.post(
                "/system/advance-analytics?run_eow_if_ready=false",
                headers=headers,
            )
            assert r.status_code == 200, r.text

            # wrong key
            r = client.post(
                "/system/trigger-monday-sync",
                headers={"X-API-Key": "wrong"},
            )
            assert r.status_code == 401
            print("OK admin lock 401/200")


def test_api_restores_on_lifespan() -> None:
    with tempfile.TemporaryDirectory() as td:
        state_path = str(Path(td) / "boot.json")
        os.environ["FCC_STATE_PATH"] = state_path
        os.environ["FCC_ADMIN_KEY"] = "boot-key"
        os.environ["FCC_ADMIN_OPEN"] = "0"
        os.environ["FCC_LLM_PROVIDER"] = "mock"
        for mod in list(sys.modules):
            if mod.startswith("flowchartcharter"):
                del sys.modules[mod]

        from flowchartcharter.system import FlowChartCharterSystem

        s = FlowChartCharterSystem(seed=3)
        for i in range(3):
            s.execute_charter(f"Job {i}")
            s.advance_analytics_day()
        s.persist_state()
        days = s.analytics.days_ready()

        for mod in list(sys.modules):
            if mod.startswith("flowchartcharter"):
                del sys.modules[mod]

        from flowchartcharter.api_server import create_app

        app = create_app()
        with TestClient(app) as client:
            h = client.get("/health")
            assert h.status_code == 200
            assert h.json()["days_ready"] == days
            print("OK lifespan restore days_ready", days)


if __name__ == "__main__":
    test_state_persistence_survives_restart()
    test_admin_key_locks_system_routes()
    test_api_restores_on_lifespan()
    print("ALL_PREFLIGHT_PATCH_TESTS_PASSED")
