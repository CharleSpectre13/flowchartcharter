"""v2.2.1 LLM Provider registry + Golden-Task Evals.

Honesty: live=True only when the same key resolver the Port uses
would actually authenticate that provider. Mock is available, not live.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, Field

from .llm_bridge import (
    DEFAULT_BASE_URLS,
    DEFAULT_MODELS,
    PROVIDER_SPECIFIC_ENV,
    default_model_for,
    resolve_provider_key,
)


class GoldenTask(BaseModel):
    """One structured-output eval case."""

    task_id: str
    workload: str
    expected_keys: List[str] = Field(default_factory=list)
    min_quality: float = 0.90
    max_tokens: int = 800


class GoldenEvalResult(BaseModel):
    task_id: str
    provider: str
    passed: bool
    quality: float = 0.0
    latency_ms: float = 0.0
    mock: bool = True
    errors: List[str] = Field(default_factory=list)
    keys_present: List[str] = Field(default_factory=list)
    billed_tokens: int = 0
    usage_source: str = "none"


DEFAULT_GOLDEN_TASKS: List[GoldenTask] = [
    GoldenTask(
        task_id="G1_json_extract",
        workload="Extract JSON fields name, amount from invoice text",
        expected_keys=["result", "quality", "path", "tokens"],
        min_quality=0.90,
    ),
    GoldenTask(
        task_id="G2_secops_summary",
        workload="Summarize CVE findings into executive_summary string",
        expected_keys=["result", "quality", "tokens"],
        min_quality=0.90,
    ),
    GoldenTask(
        task_id="G3_schema_strict",
        workload="Return only schema-valid FlowUnitResult envelope",
        expected_keys=["result", "quality", "path", "tokens"],
        min_quality=0.90,
    ),
]


@dataclass
class ProviderInfo:
    name: str
    live: bool
    env_key: str
    base_url: str = ""
    model: str = ""
    available: bool = True
    key_env_used: str = ""


def list_providers() -> List[ProviderInfo]:
    """Enumerate providers. live uses the Port key resolver (no lying flags)."""
    specs = [
        ("mock", "", "", DEFAULT_MODELS["mock"]),
        ("openai", PROVIDER_SPECIFIC_ENV["openai"], DEFAULT_BASE_URLS["openai"],
         DEFAULT_MODELS["openai"]),
        ("xai", PROVIDER_SPECIFIC_ENV["xai"], DEFAULT_BASE_URLS["xai"],
         DEFAULT_MODELS["xai"]),
        ("gemini", PROVIDER_SPECIFIC_ENV["gemini"], DEFAULT_BASE_URLS["gemini"],
         DEFAULT_MODELS["gemini"]),
    ]
    out: List[ProviderInfo] = []
    for name, env_key, base, model in specs:
        key, used = resolve_provider_key(name)
        live = bool(key) if name != "mock" else False
        out.append(
            ProviderInfo(
                name=name,
                live=live,
                env_key=env_key,
                base_url=base,
                model=default_model_for(name) if name != "mock" else model,
                available=True,
                key_env_used=used,
            )
        )
    return out


def active_provider_name() -> str:
    return os.environ.get("FCC_LLM_PROVIDER", "mock").lower()


def run_golden_evals(
    *,
    client: Any = None,
    tasks: Optional[Sequence[GoldenTask]] = None,
    provider: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute golden tasks via LLMExecutionClient (mock-safe)."""
    from .production import LLMExecutionClient, LLMExecutionRequest

    provider = (provider or active_provider_name()).lower()
    tasks = list(tasks or DEFAULT_GOLDEN_TASKS)
    client = client or LLMExecutionClient()
    results: List[GoldenEvalResult] = []

    for task in tasks:
        t0 = time.perf_counter()
        errors: List[str] = []
        keys_present: List[str] = []
        quality = 0.0
        mock = True
        billed = 0
        usage_source = "none"
        try:
            req = LLMExecutionRequest(
                workload=task.workload,
                path="path_A",
                termination_risk_index=0.1,
                system_prompt="You are a schema-strict FlowChartCharter worker.",
                playbook_constraints=["Return structured JSON envelope only."],
                expected_output_keys=list(task.expected_keys),
                agent_name="Golden-Eval",
                role="Evaluator",
            )
            resp = client.execute(req)
            mock = bool(getattr(resp, "mock", True))
            billed = int(getattr(resp, "billed_tokens", 0) or 0)
            usage = getattr(resp, "usage", None) or {}
            usage_source = str(usage.get("source") or "none")
            if resp.output is not None:
                payload = resp.output.model_dump()
                keys_present = [k for k in task.expected_keys if k in payload]
                quality = float(payload.get("quality") or 0.0)
                missing = [k for k in task.expected_keys if k not in payload]
                if missing:
                    errors.append(f"missing_keys:{missing}")
                if quality < task.min_quality:
                    errors.append(
                        f"quality {quality:.3f} < min {task.min_quality}"
                    )
            else:
                errors.append("no_output")
            if not resp.ok:
                errors.append("client_not_ok")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{type(exc).__name__}:{exc}")
        wall = round((time.perf_counter() - t0) * 1000.0, 2)
        results.append(
            GoldenEvalResult(
                task_id=task.task_id,
                provider=provider,
                passed=len(errors) == 0,
                quality=quality,
                latency_ms=wall,
                mock=mock,
                errors=errors,
                keys_present=keys_present,
                billed_tokens=billed,
                usage_source=usage_source,
            )
        )

    passed = sum(1 for r in results if r.passed)
    return {
        "version": "2.2.1",
        "provider": provider,
        "providers": [
            {
                "name": p.name,
                "live": p.live,
                "available": p.available,
                "env_key": p.env_key,
                "key_env_used": p.key_env_used,
                "model": p.model,
            }
            for p in list_providers()
        ],
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "pass_rate": round(passed / max(1, len(results)), 4),
        "results": [r.model_dump() for r in results],
    }
