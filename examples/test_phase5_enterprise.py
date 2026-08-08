#!/usr/bin/env python3
"""Phase 5 — Prometheus metrics, playbook library, sandbox UI bridge."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))
os.environ["FCC_DASHBOARD_DIR"] = str(ROOT / "dashboard")
os.environ["FCC_LIBRARY_DIR"] = str(ROOT / "library")
os.environ["FCC_LLM_PROVIDER"] = "mock"
os.environ["FCC_LIVE_WIRE"] = "1"

from fastapi.testclient import TestClient  # noqa: E402

from flowchartcharter.api_server import create_app  # noqa: E402
from flowchartcharter.observability import MetricsHub, get_metrics_hub  # noqa: E402
from flowchartcharter.playbook_compiler import compile_playbook  # noqa: E402
from flowchartcharter.simulation_sandbox import SimulationSandbox  # noqa: E402


def test_prometheus_metrics_nonblocking() -> None:
    app = create_app()
    with TestClient(app) as client:
        client.post(
            "/workload/submit",
            json={"workload": "Legacy Code Refactor", "context_entropy": 0.3},
        )
        r = client.get("/metrics")
        assert r.status_code == 200
        body = r.text
        assert "fcc_active_nodes" in body
        assert "fcc_node_fear_index" in body
        assert "fcc_entanglement_errors_total" in body
        assert "fcc_token_spend_total" in body
        assert "fcc_workloads_total" in body
        # second scrape still works (counter deltas)
        r2 = client.get("/metrics")
        assert r2.status_code == 200
        print("OK /metrics", len(body), "bytes")


def test_metrics_hub_no_prom_fallback() -> None:
    hub = get_metrics_hub()
    assert hub.enabled is True
    raw = hub.export()
    assert isinstance(raw, (bytes, bytearray))
    print("OK metrics hub export", len(raw))


def test_enterprise_library_yaml() -> None:
    lib = ROOT / "library"
    required = [
        "secops_vulnerability_audit.yaml",
        "legacy_to_react_migration.yaml",
        "unstructured_data_etl.yaml",
    ]
    for name in required:
        path = lib / name
        assert path.is_file(), name
        pb = compile_playbook(path)
        assert pb.flow_units, name
        assert pb.global_cfo_ceiling > 0
        # every unit has dynamic pydantic model + schema
        for u in pb.flow_units:
            assert u.schema_raw
            assert u.pydantic_model is not None
        print("OK library", name, pb.playbook_name, len(pb.flow_units), "units")


def test_library_api_and_load() -> None:
    app = create_app()
    with TestClient(app) as client:
        listing = client.get("/library")
        assert listing.status_code == 200
        names = listing.json()["playbooks"]
        assert "secops_vulnerability_audit.yaml" in names

        raw = client.get("/library/secops_vulnerability_audit.yaml")
        assert raw.status_code == 200
        assert b"playbook_name" in raw.content

        up = client.post(
            "/system/load-playbook",
            files={
                "file": (
                    "secops_vulnerability_audit.yaml",
                    raw.content,
                    "application/yaml",
                )
            },
        )
        assert up.status_code == 200, up.text
        assert up.json()["playbook_name"] == "SecOps Vulnerability Audit"

        run = client.post(
            "/system/execute-compiled",
            json={"workload": "Weekly vuln sweep"},
        )
        assert run.status_code == 200, run.text
        assert run.json()["units_total"] >= 3
        print(
            "OK library→compile→execute",
            run.json()["units_ok"],
            "/",
            run.json()["units_total"],
        )


def test_dashboard_served() -> None:
    app = create_app()
    with TestClient(app) as client:
        for path in ("/ui/", "/ui/index.html", "/sandbox", "/app"):
            r = client.get(path)
            # StaticFiles html may redirect
            assert r.status_code in (200, 307, 308), path
            if r.status_code == 200:
                assert b"FlowChartCharter" in r.content or b"html" in r.content[:200].lower()
        print("OK dashboard routes")


def test_phase5_simulation_sandbox() -> None:
    """Ultimate proving ground — multi-playbook enterprise workweek."""
    box = SimulationSandbox(seed=21, live_wire=True)
    # load each library playbook and run one compiled job
    results = []
    for name in (
        "unstructured_data_etl.yaml",
        "secops_vulnerability_audit.yaml",
        "legacy_to_react_migration.yaml",
    ):
        path = ROOT / "library" / name
        meta = box.system.load_playbook(path)
        out = box.system.execute_compiled(meta["playbook_name"])
        results.append(out)
        box.system.advance_analytics_day()
    eow = box.system.run_end_of_week_protocol(force=True)
    trust_rate = sum(1 for r in results if r.get("trust")) / len(results)
    mean_q = sum(float(r.get("quality") or 0) for r in results) / len(results)
    assert mean_q >= 0.7
    assert all(r.get("units_ok", 0) >= 1 for r in results)
    print(
        "OK phase5 sandbox",
        "trust_rate",
        round(trust_rate, 2),
        "mean_q",
        round(mean_q, 3),
        "dossier",
        eow.get("dossier_driven"),
    )


if __name__ == "__main__":
    test_prometheus_metrics_nonblocking()
    test_metrics_hub_no_prom_fallback()
    test_enterprise_library_yaml()
    test_library_api_and_load()
    test_dashboard_served()
    test_phase5_simulation_sandbox()
    print("ALL_PHASE5_ENTERPRISE_TESTS_PASSED")
