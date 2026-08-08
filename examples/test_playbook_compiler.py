#!/usr/bin/env python3
"""Phase 3 — Playbook Compiler + dynamic Pydantic + load-playbook API."""
from __future__ import annotations

import gc
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from fastapi.testclient import TestClient  # noqa: E402

from flowchartcharter.playbook_compiler import (  # noqa: E402
    compile_playbook,
    generate_pydantic_model,
    hydrate_system,
    enforce_unit_schema,
    PlaybookCompiler,
    PlaybookCompileError,
)
from flowchartcharter import FlowChartCharterSystem  # noqa: E402
from flowchartcharter.api_server import create_app  # noqa: E402

CHARTER = ROOT / "examples" / "charterfiles" / "legacy_auth_refactor.yaml"


def test_dynamic_pydantic() -> None:
    Model = generate_pydantic_model(
        "U1",
        {"clean_code": "string", "variables_found": "list[string]"},
    )
    obj = Model(clean_code="x=1", variables_found=["x"])
    assert obj.clean_code == "x=1"
    try:
        Model(clean_code=1, variables_found="nope")  # type: ignore[arg-type]
        raise AssertionError("should fail")
    except Exception:
        pass
    print("OK dynamic pydantic", Model.__name__)


def test_compile_yaml_file() -> None:
    pb = compile_playbook(CHARTER)
    assert pb.playbook_name == "Legacy Auth Refactor"
    assert pb.global_cfo_ceiling == 3500
    assert len(pb.flow_units) == 2
    assert pb.flow_path == ["U1_Ingest_Clean", "U2_Secure_Tokens"]
    u1 = pb.unit_by_id("U1_Ingest_Clean")
    assert u1 is not None
    ok, model, errs = u1.validate_output(
        {"clean_code": "def f(): pass", "variables_found": ["f"]}
    )
    assert ok and model is not None
    bad_ok, _, bad_errs = u1.validate_output({"clean_code": 123})
    assert not bad_ok and bad_errs
    print("OK compile", pb.playbook_id, [u.pydantic_model.__name__ for u in pb.flow_units])


def test_hydrate_and_execute() -> None:
    system = FlowChartCharterSystem(seed=4)
    meta = system.load_playbook(CHARTER)
    assert meta["token_budget"] == 3500
    assert "Data-Sanitizer" in meta["ops_roster"] or any(
        "Sanitizer" in n for n in meta["ops_roster"]
    )
    assert system.compiled_playbook is not None
    result = system.execute_compiled("Refactor legacy auth module")
    assert result["units_total"] == 2
    assert result["units_ok"] >= 1
    assert result["mode"] == "compiled_playbook"
    print(
        "OK execute_compiled",
        result["units_ok"],
        "/",
        result["units_total"],
        "Q=",
        round(result["quality"], 3),
    )


def test_schema_failure_entanglement() -> None:
    system = FlowChartCharterSystem(seed=5)
    system.load_playbook(CHARTER)
    pb = system.compiled_playbook
    agent = next(a for a in system.roster if "Sanitizer" in a.role or "Sanitizer" in a.name)
    before = getattr(agent, "entanglement_errors", 0)
    gate = enforce_unit_schema(
        pb,
        "U1_Ingest_Clean",
        {"clean_code": 999, "variables_found": "bad"},
        agent=agent,
    )
    assert gate["valid"] is False
    assert agent.entanglement_errors >= before + 1
    print("OK entanglement on schema fail", agent.entanglement_errors)


def test_hot_reload_memory_safe() -> None:
    system = FlowChartCharterSystem(seed=6)
    c = system.compiler
    c.compile_and_hydrate(system, CHARTER)
    id1 = system.active_playbook_id
    # second load
    c.compile_and_hydrate(system, CHARTER)
    id2 = system.active_playbook_id
    assert id1 != id2
    assert c.load_count == 2
    gc.collect()
    print("OK hot-reload", id1, "→", id2, "loads", c.load_count)


def test_invalid_charterfile() -> None:
    try:
        compile_playbook({"playbook_name": "x"})  # missing roster/units
        raise AssertionError("should fail")
    except PlaybookCompileError:
        pass
    print("OK invalid charter rejected")


def test_api_load_playbook() -> None:
    app = create_app()
    with TestClient(app) as client:
        with open(CHARTER, "rb") as fh:
            r = client.post(
                "/system/load-playbook",
                files={"file": ("legacy_auth_refactor.yaml", fh, "application/yaml")},
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["playbook_name"] == "Legacy Auth Refactor"
        assert body["token_budget"] == 3500
        assert len(body["flow_path"]) == 2
        print("OK API load-playbook", body["playbook_id"], body["models"])

        r2 = client.post(
            "/system/execute-compiled",
            json={"workload": "Run legacy auth refactor"},
        )
        assert r2.status_code == 200, r2.text
        out = r2.json()
        assert out["units_total"] == 2
        print("OK API execute-compiled", out["units_ok"], out.get("quality"))

        r3 = client.get("/system/playbook")
        assert r3.status_code == 200
        assert r3.json()["current"] is not None
        print("OK API get playbook")


if __name__ == "__main__":
    test_dynamic_pydantic()
    test_compile_yaml_file()
    test_hydrate_and_execute()
    test_schema_failure_entanglement()
    test_hot_reload_memory_safe()
    test_invalid_charterfile()
    test_api_load_playbook()
    print("ALL_PLAYBOOK_COMPILER_TESTS_PASSED")
