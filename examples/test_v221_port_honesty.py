#!/usr/bin/env python3
"""v2.2.1 Port Honesty — keys, TPC on the wire, billed usage, no secret URLs."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from flowchartcharter import (  # noqa: E402
    ProviderUsage,
    SamplingParams,
    __version__,
    list_providers,
    resolve_provider_key,
    run_golden_evals,
)
from flowchartcharter.agents import WorkerNode  # noqa: E402
from flowchartcharter.llm_bridge import LLMBridge, LLMBridgeConfig  # noqa: E402
from flowchartcharter.production import (  # noqa: E402
    LLMExecutionClient,
    LLMExecutionRequest,
    apply_execution_to_agent,
)
from flowchartcharter.production import WorkerTaskResult  # noqa: E402
from flowchartcharter.survival import generation_params_for_risk  # noqa: E402


def _clear_keys() -> None:
    for k in (
        "FCC_LLM_API_KEY",
        "OPENAI_API_KEY",
        "XAI_API_KEY",
        "GEMINI_API_KEY",
        "FCC_LLM_PROVIDER",
        "FCC_LLM_MODEL",
    ):
        os.environ.pop(k, None)


def test_version() -> None:
    assert __version__ >= "2.2.1", __version__
    print("OK version", __version__)


def test_h1_key_isolation() -> None:
    _clear_keys()
    os.environ["XAI_API_KEY"] = "xai-test-key-not-real"
    os.environ["FCC_LLM_PROVIDER"] = "mock"
    providers = {p.name: p for p in list_providers()}
    assert providers["xai"].live is True
    assert providers["openai"].live is False
    assert providers["gemini"].live is False
    assert providers["xai"].key_env_used == "XAI_API_KEY"
    key, used = resolve_provider_key("xai")
    assert key == "xai-test-key-not-real" and used == "XAI_API_KEY"
    key_o, used_o = resolve_provider_key("openai")
    assert key_o == "" and used_o == ""
    _clear_keys()
    print("OK H1 key isolation")


def test_h1b_generic_key_only_active() -> None:
    _clear_keys()
    os.environ["FCC_LLM_API_KEY"] = "generic-secret"
    os.environ["FCC_LLM_PROVIDER"] = "xai"
    assert resolve_provider_key("xai")[1] == "FCC_LLM_API_KEY"
    assert resolve_provider_key("openai")[0] == ""
    providers = {p.name: p for p in list_providers()}
    assert providers["xai"].live is True
    assert providers["openai"].live is False
    _clear_keys()
    print("OK H1b generic key scoped to active provider")


def test_h2_mock_not_live() -> None:
    _clear_keys()
    os.environ["FCC_LLM_PROVIDER"] = "mock"
    providers = {p.name: p for p in list_providers()}
    assert providers["mock"].live is False
    assert providers["mock"].available is True
    bridge = LLMBridge()
    assert bridge.live is False
    print("OK H2 mock is not live")


def test_h3_tpc_sampling_on_wire() -> None:
    _clear_keys()
    os.environ["FCC_LLM_PROVIDER"] = "mock"
    client = LLMExecutionClient()
    high = generation_params_for_risk(0.82)
    req = LLMExecutionRequest(
        workload="Refactor auth",
        path="path_A",
        termination_risk_index=0.82,
        system_prompt="You are a worker.",
        playbook_constraints=["Schema lock mandatory"],
        agent_name="W1",
        role="Key Player",
    )
    resp = client.execute(req)
    assert resp.ok
    assert abs(resp.sampling["temperature"] - high.temperature) < 1e-9
    assert resp.sampling["temperature"] != 0.2
    assert resp.sampling["max_tokens"] == high.max_tokens
    assert client.bridge.last_sampling["temperature"] == high.temperature
    print("OK H3 TPC sampling applied", resp.sampling["temperature"])


def test_h4_billed_tokens_override_self_report() -> None:
    """CFO must bill provider usage, not model-authored tokens."""
    _clear_keys()
    os.environ["FCC_LLM_PROVIDER"] = "mock"
    client = LLMExecutionClient()

    class _FakeBridge:
        def __init__(self) -> None:
            self.config = LLMBridgeConfig(provider="xai", api_key="k", model="grok-4.5")
            self.last_sampling: Dict[str, Any] = {}
            self.last_usage = ProviderUsage(
                prompt_tokens=100, completion_tokens=50, total_tokens=150, source="provider"
            )
            self.last_request_meta = {"query_has_key": False, "provider": "xai"}

        @property
        def live(self) -> bool:
            return True

        def chat(self, system: str, user: str, *, sampling: Optional[SamplingParams] = None):
            from flowchartcharter.llm_bridge import ChatResult

            self.last_sampling = (sampling or SamplingParams()).to_dict()
            # Model lies: tokens=12. Provider billed 150.
            text = (
                '{"result":"ok","quality":0.94,"path":"path_A",'
                '"tokens":12,"notes":"lie","schema_ok":true}'
            )
            return ChatResult(
                text=text,
                usage=self.last_usage,
                sampling=self.last_sampling,
                request_meta=self.last_request_meta,
            )

    client.bridge = _FakeBridge()  # type: ignore[assignment]
    req = LLMExecutionRequest(
        workload="Invoice extract",
        path="path_A",
        termination_risk_index=0.1,
        system_prompt="worker",
    )
    resp = client.execute(req)
    assert resp.ok
    assert resp.billed_tokens == 150
    assert resp.output is not None
    assert resp.output.tokens == 150
    assert resp.usage["source"] == "provider"

    node = WorkerNode("Bill-1", "Key Player", {"x": 1.0})
    apply_execution_to_agent(
        node,
        WorkerTaskResult(agent_name="Bill-1", response=resp, wall_ms=1.0),
    )
    assert node.history[-1].token_cost == 150
    assert node.ledger.entries[-1].token_spend == 150
    print("OK H4 billed tokens override self-report")


def test_h5_gemini_url_has_no_key() -> None:
    _clear_keys()
    cfg = LLMBridgeConfig(
        provider="gemini",
        api_key="secret-gemini-key",
        key_env="GEMINI_API_KEY",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        model="gemini-1.5-flash",
    )
    bridge = LLMBridge(cfg)

    captured: Dict[str, Any] = {}

    def _http_json(
        url: str, body: Dict[str, Any], headers: Dict[str, str]
    ) -> Tuple[Any, Dict[str, Any]]:
        captured["url"] = url
        captured["headers"] = {k.lower(): "set" for k in headers}
        captured["body"] = body
        parsed_q = "key=" in url.lower()
        meta = {
            "query_has_key": parsed_q,
            "provider": "gemini",
            "host": "generativelanguage.googleapis.com",
        }
        if parsed_q:
            raise RuntimeError(
                "Port honesty: API key must not appear in the request URL"
            )
        envelope = (
            '{"result":"ok","quality":0.9,"path":"path_A",'
            '"tokens":1,"schema_ok":true}'
        )
        return (
            {
                "candidates": [
                    {"content": {"parts": [{"text": envelope}]}}
                ],
                "usageMetadata": {
                    "promptTokenCount": 10,
                    "candidatesTokenCount": 5,
                    "totalTokenCount": 15,
                },
            },
            meta,
        )

    bridge._http_json = _http_json  # type: ignore[method-assign]
    result = bridge.chat(
        "sys",
        "user",
        sampling=SamplingParams(temperature=0.1, top_p=0.5, max_tokens=256),
    )
    assert "key=" not in captured["url"]
    assert captured["headers"].get("x-goog-api-key") == "set"
    assert "authorization" not in captured["url"].lower()
    assert captured["body"]["generationConfig"]["temperature"] == 0.1
    assert result.usage.billed == 15
    assert result.request_meta["query_has_key"] is False
    print("OK H5 Gemini key not in URL")


def test_h6_golden_mock() -> None:
    _clear_keys()
    os.environ["FCC_LLM_PROVIDER"] = "mock"
    report = run_golden_evals()
    assert report["total"] >= 3
    assert report["passed"] == report["total"]
    print("OK H6 golden", report["passed"], "/", report["total"])


def test_h7_no_new_vendor_deps() -> None:
    req = (ROOT / "pyproject.toml").read_text()
    for banned in ("openai", "anthropic", "google-genai", "litellm", "google-generativeai"):
        # dependency names only — allow comments/strings mentioning brands in descriptions
        for line in req.splitlines():
            s = line.strip()
            if s.startswith('"') and banned in s.split(">=")[0].split("==")[0].strip('"').lower():
                if banned == s.strip('",'):
                    raise AssertionError(f"banned dep {banned} in pyproject: {s}")
            if s.startswith(banned) or s.startswith(f'"{banned}'):
                raise AssertionError(f"banned dep line: {s}")
    print("OK H7 no vendor SDK deps")


def test_default_xai_model() -> None:
    _clear_keys()
    os.environ["FCC_LLM_PROVIDER"] = "xai"
    os.environ["XAI_API_KEY"] = "k"
    cfg = LLMBridgeConfig.from_env()
    assert cfg.model == "grok-4.5"
    _clear_keys()
    print("OK default xai model grok-4.5")


def main() -> None:
    test_version()
    test_h1_key_isolation()
    test_h1b_generic_key_only_active()
    test_h2_mock_not_live()
    test_h3_tpc_sampling_on_wire()
    test_h4_billed_tokens_override_self_report()
    test_h5_gemini_url_has_no_key()
    test_h6_golden_mock()
    test_h7_no_new_vendor_deps()
    test_default_xai_model()
    print("ALL v2.2.1 PORT HONESTY TESTS PASSED")


if __name__ == "__main__":
    main()
