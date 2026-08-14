"""v2.3 Gate 2 — live golden evals under a hard CFO ceiling.

Default remains mock. Live xAI only when a real key resolves.
Never silently spend. Halt when billed tokens hit the ceiling.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Sequence

from .llm_bridge import LLMBridgeConfig, resolve_provider_key
from .llm_providers import DEFAULT_GOLDEN_TASKS, GoldenTask
from .production import LLMExecutionClient, LLMExecutionRequest
from .survival import generation_params_for_risk


def _live_ready(provider: str) -> Dict[str, Any]:
    key, env_used = resolve_provider_key(provider)
    return {
        "provider": provider,
        "live": bool(key) and provider != "mock",
        "key_env_used": env_used,
        "model": os.environ.get("FCC_LLM_MODEL")
        or os.environ.get(f"FCC_{provider.upper()}_MODEL")
        or "",
    }


def run_live_goldens(
    *,
    cfo_ceiling: int = 2500,
    provider: str = "xai",
    tasks: Optional[Sequence[GoldenTask]] = None,
    client: Optional[LLMExecutionClient] = None,
    force_live: bool = False,
) -> Dict[str, Any]:
    """Execute G1–G3 under a unified CFO cap.

    If the Port is not live, returns an honest receipt (no fake scores)
    plus a contract probe that the request *would* carry TPC sampling.
    """
    provider = (provider or "xai").lower()
    tasks = list(tasks or DEFAULT_GOLDEN_TASKS)[:3]
    ready = _live_ready(provider)
    t0 = time.perf_counter()

    if client is None:
        prev = os.environ.get("FCC_LLM_PROVIDER")
        os.environ["FCC_LLM_PROVIDER"] = provider if ready["live"] else "mock"
        try:
            client = LLMExecutionClient(
                config=LLMBridgeConfig.from_env()
                if ready["live"]
                else LLMBridgeConfig(provider="mock")
            )
        finally:
            if prev is None:
                os.environ.pop("FCC_LLM_PROVIDER", None)
            else:
                os.environ["FCC_LLM_PROVIDER"] = prev

    live = bool(client.bridge.live)
    if force_live and not live:
        return {
            "version": "2.3.0",
            "gate": "live_inference",
            "live": False,
            "halted": True,
            "reason": "force_live_requested_but_port_not_live",
            "cfo_ceiling": cfo_ceiling,
            "billed_tokens": 0,
            "under_budget": True,
            "passed": 0,
            "total": len(tasks),
            "results": [],
            "ready": ready,
        }

    billed = 0
    results: List[Dict[str, Any]] = []
    halted = False
    halt_reason = ""

    for task in tasks:
        if billed >= cfo_ceiling:
            halted = True
            halt_reason = "cfo_ceiling"
            break
        remaining = cfo_ceiling - billed
        gen = generation_params_for_risk(0.15)
        req = LLMExecutionRequest(
            workload=task.workload,
            path="path_A",
            termination_risk_index=0.15,
            system_prompt=(
                "You are a schema-strict FlowChartCharter worker. "
                "Return only the FlowUnitResult JSON envelope."
            ),
            playbook_constraints=[
                "JSON envelope only",
                f"CFO remaining tokens={remaining}",
            ],
            expected_output_keys=list(task.expected_keys),
            agent_name="Live-Golden",
            role="Evaluator",
        )
        resp = client.execute(req)
        spend = int(resp.billed_tokens or 0)
        billed += spend
        over = billed > cfo_ceiling
        if over:
            halted = True
            halt_reason = "cfo_ceiling"
        ok = bool(resp.ok) and not over
        results.append(
            {
                "task_id": task.task_id,
                "ok": ok,
                "mock": resp.mock,
                "billed_tokens": spend,
                "usage_source": (resp.usage or {}).get("source"),
                "sampling_temperature": (resp.sampling or {}).get("temperature"),
                "quality": (resp.output.quality if resp.output else 0.0),
                "errors": list(resp.validation.errors) if resp.validation else [],
            }
        )
        if over:
            break

    passed = sum(1 for r in results if r["ok"])
    return {
        "version": "2.3.0",
        "gate": "live_inference",
        "live": live,
        "reason": halt_reason
        or ("live_ok" if live else "port_not_live_mock_contract"),
        "halted": halted,
        "cfo_ceiling": cfo_ceiling,
        "billed_tokens": billed,
        "under_budget": billed <= cfo_ceiling,
        "passed": passed,
        "total": len(tasks),
        "pass_rate": round(passed / max(1, len(results)), 4) if results else 0.0,
        "duration_ms": round((time.perf_counter() - t0) * 1000.0, 2),
        "results": results,
        "ready": ready,
        "generation_probe": generation_params_for_risk(0.15).to_dict(),
    }
