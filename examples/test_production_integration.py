#!/usr/bin/env python3
"""Production integration: LLMExecutionClient, schema gate, vector backends."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from flowchartcharter.production import (  # noqa: E402
    LLMExecutionClient,
    LLMExecutionRequest,
    validate_llm_output,
    ProductionMuscleMemory,
    InMemoryVectorBackend,
    EmbeddingProvider,
    run_workers_parallel,
    WorkerTask,
    build_vector_backend,
)
from flowchartcharter.agents import WorkerNode  # noqa: E402
from flowchartcharter.muscle_memory import ExecutionMemoryRecord  # noqa: E402


def test_schema_valid() -> None:
    model, report = validate_llm_output(
        {
            "result": "ok",
            "quality": 0.94,
            "path": "path_A",
            "tokens": 120,
            "schema_ok": True,
        }
    )
    assert report.valid and model is not None
    assert model.quality == 0.94
    print("OK schema valid")


def test_schema_violation_increments_entanglement() -> None:
    model, report = validate_llm_output('{"result":"ok","quality":2.5}')
    assert not report.valid
    assert report.entanglement_increment == 1
    assert model is None
    print("OK schema violation", report.errors[:2])


def test_llm_client_injects_tpc() -> None:
    client = LLMExecutionClient()
    req = LLMExecutionRequest(
        workload="Refactor auth",
        path="path_A",
        termination_risk_index=0.82,
        system_prompt="You are a worker.",
        playbook_constraints=["Schema lock mandatory"],
        agent_name="W1",
        role="Key Player",
    )
    system = client.build_system_prompt(req)
    assert "termination_risk_index: 0.8200" in system
    assert "Schema lock mandatory" in system
    gen = client.generation_for_risk(0.82)
    assert gen.temperature < 0.2  # high risk cools sampling
    assert gen.schema_lock is True
    # extreme risk → exact zero
    assert client.generation_for_risk(1.0).temperature == 0.0
    resp = client.execute(req)
    assert resp.ok
    assert resp.generation["schema_lock"] is True
    print("OK TPC inject", resp.latency_ms, "ms", resp.provider, gen.temperature)


def test_worker_node_execute_live() -> None:
    node = WorkerNode("Prod-1", "Key Player - Code", {"python_ast": 1.0})
    assert isinstance(node.llm_client, LLMExecutionClient)
    m = node.execute_live("Legacy Code Refactor", path="path_A")
    assert m is not None
    assert m.quality_score > 0
    _, report = validate_llm_output(
        {"result": "nope", "quality": 0.5, "tokens": 1}
    )
    assert report.entanglement_increment == 1
    node.entanglement_errors += report.entanglement_increment
    assert node.entanglement_errors >= 1
    print("OK WorkerNode live", m.token_cost, "entangle", node.entanglement_errors)


def test_production_vector_db() -> None:
    mm = ProductionMuscleMemory(
        backend_name="memory",
        backend=InMemoryVectorBackend(),
        embedder=EmbeddingProvider(dims=32),
        quiet=True,
    )
    rec = ExecutionMemoryRecord(
        memory_id="MEM-PROD1",
        job_type="Legacy Code Refactor",
        state_vector=[0.8, 0.2, 0.1, 0.9],
        successful_flow_path=["U1_Ingest", "U8_DeterministicRefactor"],
        entanglement_score=0.97,
        prompt_tweak="camelCase only",
        quality=0.98,
        token_cost=200,
        tags=("refactor",),
    )
    mm.commit_memory(rec)
    hit = mm.query_muscle_memory(
        {"task": "Legacy Code Refactor", "code": "function x(){}"},
        similarity_threshold=0.5,
    )
    assert hit is not None
    assert "U1_Ingest" in hit.successful_flow_path
    print("OK production MM hit", hit.memory_id, mm.stats())


def test_embed_stable() -> None:
    emb = EmbeddingProvider(dims=16)
    a = emb.embed({"task": "hello"})
    b = emb.embed({"task": "hello"})
    c = emb.embed({"task": "world"})
    assert a == b
    assert a != c
    assert abs(sum(x * x for x in a) - 1.0) < 1e-6
    print("OK embed stable dims", len(a))


def test_parallel_superstep() -> None:
    tasks = [
        WorkerTask(
            agent_name=f"W{i}",
            workload="job",
            path="path_A",
            system_prompt="You are a worker.",
            termination_risk_index=0.1 * i,
            playbook_constraints=("schema lock",),
        )
        for i in range(4)
    ]
    results = run_workers_parallel(tasks, max_workers=4)
    assert len(results) == 4
    assert all(r.response.ok for r in results)
    wall = max(r.wall_ms for r in results)
    print("OK parallel superstep n=4 max_wall_ms", wall)


def test_backend_factory() -> None:
    name, backend = build_vector_backend(prefer="memory")
    assert name == "memory"
    assert isinstance(backend, InMemoryVectorBackend)
    print("OK backend factory", name)


if __name__ == "__main__":
    test_schema_valid()
    test_schema_violation_increments_entanglement()
    test_llm_client_injects_tpc()
    test_worker_node_execute_live()
    test_production_vector_db()
    test_embed_stable()
    test_parallel_superstep()
    test_backend_factory()
    print("ALL_PRODUCTION_INTEGRATION_TESTS_PASSED")
