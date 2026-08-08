#!/usr/bin/env python3
"""API Nervous System tests (FastAPI TestClient + lifespan)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from fastapi.testclient import TestClient  # noqa: E402

from flowchartcharter.api_server import create_app  # noqa: E402
from flowchartcharter.llm_bridge import (  # noqa: E402
    LLMBridge,
    LLMNodeOutput,
    LLMBridgeConfig,
)


def test_llm_schema_validation() -> None:
    out = LLMNodeOutput(
        result="ok", quality=0.95, path="path_A", tokens=120, schema_ok=True
    )
    assert out.quality == 0.95
    bridge = LLMBridge(LLMBridgeConfig(provider="mock"))
    mock = bridge.execute_worker(
        system_prompt="You are a worker.",
        workload="test",
        path="path_lite",
        termination_risk_index=0.1,
    )
    assert mock.schema_ok
    assert mock.tokens > 0
    print("OK llm bridge mock", mock.model_dump())


def test_api_endpoints() -> None:
    app = create_app()
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

        r = client.get("/")
        assert "endpoints" in r.json()

        r = client.post(
            "/workload/submit",
            json={
                "workload": "Legacy Code Refactor",
                "context_entropy": 0.35,
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["workload"] == "Legacy Code Refactor"
        assert 0.0 <= body["quality"] <= 1.0
        assert "request_id" in body
        print("OK submit", body["request_id"], body["quality"], body["playbook_mode"])

        r = client.get("/roster/status")
        assert r.status_code == 200
        roster = r.json()
        assert len(roster["roster"]) >= 3
        assert "termination_risk_index" in roster["roster"][0]
        assert "fitness" in roster["roster"][0]
        print("OK roster", len(roster["roster"]), "ops", roster["active_ops"])

        r = client.post("/system/advance-analytics?run_eow_if_ready=false")
        assert r.status_code == 200
        adv = r.json()
        assert adv["days_ready"] >= 1
        print("OK advance-analytics", adv["day_closed"], adv["days_ready"])

        # pad to 5 days
        for _ in range(4):
            client.post("/workload/submit", json={"workload": "Batch pattern"})
            client.post("/system/advance-analytics?run_eow_if_ready=false")

        r = client.post("/system/end-of-week?force=true")
        assert r.status_code == 200
        eow = r.json()
        assert eow["dossier"] is not None or eow["days_ready"] >= 0
        print("OK end-of-week", eow.get("dossier_driven"), eow["analytics"]["week_index"])

        r = client.post("/system/trigger-monday-sync")
        assert r.status_code == 200
        sync = r.json()
        assert "outcomes" in sync
        print("OK monday-sync", sync["outcomes"], "dossier_driven", sync["dossier_driven"])

        r = client.post(
            "/system/upgrade-personnel",
            json={"model_class": "1T"},
        )
        assert r.status_code == 200
        assert r.json()["model_class"] == "1T"
        print("OK upgrade-personnel")

        # validation error
        r = client.post("/workload/submit", json={"workload": ""})
        assert r.status_code == 422
        print("OK schema reject empty workload")


if __name__ == "__main__":
    test_llm_schema_validation()
    test_api_endpoints()
    print("ALL_API_SERVER_TESTS_PASSED")
