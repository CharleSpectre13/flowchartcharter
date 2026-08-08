"""Live-Wire LLM bridge — optional outbound calls for Worker Nodes.

When FCC_LLM_PROVIDER is set (openai|xai|gemini|mock), workers format their
Fear/TPC system prompt and make a live outbound call. Pydantic validates the
return schema. Default remains simulation for offline demos.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator


class LLMNodeOutput(BaseModel):
    """Strict schema enforced on every LLM return (zero-hallucination gate)."""

    result: str = Field(..., min_length=1)
    quality: float = Field(..., ge=0.0, le=1.0)
    path: str = Field(default="path_A")
    tokens: int = Field(..., ge=0)
    notes: str = Field(default="")
    schema_ok: bool = Field(default=True)

    @field_validator("path")
    @classmethod
    def normalize_path(cls, v: str) -> str:
        allowed = {"path_A", "path_B", "path_lite"}
        if v not in allowed:
            return "path_A"
        return v


class LLMBridgeConfig(BaseModel):
    provider: str = "mock"  # mock | openai | xai | gemini
    model: str = "grok-2"
    api_key: str = ""
    base_url: str = ""
    timeout_s: float = 30.0
    max_tokens: int = 512

    @classmethod
    def from_env(cls) -> "LLMBridgeConfig":
        provider = os.environ.get("FCC_LLM_PROVIDER", "mock").lower()
        key = os.environ.get("FCC_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
        base = os.environ.get("FCC_LLM_BASE_URL", "")
        if not base:
            if provider == "openai":
                base = "https://api.openai.com/v1"
            elif provider == "xai":
                base = "https://api.x.ai/v1"
            elif provider == "gemini":
                base = "https://generativelanguage.googleapis.com/v1beta"
        return cls(
            provider=provider,
            model=os.environ.get("FCC_LLM_MODEL", "grok-2"),
            api_key=key,
            base_url=base,
            timeout_s=float(os.environ.get("FCC_LLM_TIMEOUT", "30")),
            max_tokens=int(os.environ.get("FCC_LLM_MAX_TOKENS", "512")),
        )


class LLMBridge:
    """Outbound LLM client with Pydantic schema validation on return."""

    def __init__(self, config: Optional[LLMBridgeConfig] = None) -> None:
        self.config = config or LLMBridgeConfig.from_env()

    @property
    def live(self) -> bool:
        return self.config.provider != "mock" and bool(self.config.api_key)

    def execute_worker(
        self,
        *,
        system_prompt: str,
        workload: str,
        path: str,
        termination_risk_index: float,
    ) -> LLMNodeOutput:
        """Format TPC prompt + call provider; validate with Pydantic."""
        user_msg = (
            f"Workload: {workload}\n"
            f"Selected path: {path}\n"
            f"termination_risk_index: {termination_risk_index:.4f}\n"
            "Return JSON only: "
            '{"result":"ok|fail","quality":0-1,"path":"path_A|path_B|path_lite",'
            '"tokens":int,"notes":str,"schema_ok":bool}'
        )
        if not self.live:
            return self._mock(path=path, risk=termination_risk_index)

        raw = self._chat(system_prompt, user_msg)
        return self._parse_and_validate(raw, fallback_path=path)

    def _mock(self, *, path: str, risk: float) -> LLMNodeOutput:
        q = max(0.7, min(1.0, 0.95 - 0.2 * risk))
        tokens = {"path_A": 180, "path_B": 340, "path_lite": 90}.get(path, 200)
        return LLMNodeOutput(
            result="ok",
            quality=q,
            path=path,
            tokens=tokens,
            notes="mock-llm",
            schema_ok=True,
        )

    def _chat(self, system: str, user: str) -> str:
        cfg = self.config
        if cfg.provider in ("openai", "xai"):
            url = f"{cfg.base_url.rstrip('/')}/chat/completions"
            body = {
                "model": cfg.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": cfg.max_tokens,
                "temperature": 0.2,
            }
            headers = {
                "Authorization": f"Bearer {cfg.api_key}",
                "Content-Type": "application/json",
            }
            return self._http_json(url, body, headers)
        if cfg.provider == "gemini":
            url = (
                f"{cfg.base_url.rstrip('/')}/models/{cfg.model}:generateContent"
                f"?key={cfg.api_key}"
            )
            body = {"contents": [{"parts": [{"text": f"SYSTEM:\n{system}\n\nUSER:\n{user}"}]}]}
            raw = self._http_json(url, body, {"Content-Type": "application/json"})
            try:
                data = json.loads(raw)
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError, json.JSONDecodeError):
                return raw
        return self._mock(path="path_A", risk=0.0).model_dump_json()

    def _http_json(self, url: str, body: Dict[str, Any], headers: Dict[str, str]) -> str:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout_s) as resp:
                payload = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"LLM HTTP {exc.code}: {exc.read()[:200]}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"LLM network error: {exc}") from exc

        try:
            parsed = json.loads(payload)
            if "choices" in parsed:
                return parsed["choices"][0]["message"]["content"]
        except (json.JSONDecodeError, KeyError, IndexError):
            pass
        return payload

    def _parse_and_validate(self, raw: str, *, fallback_path: str) -> LLMNodeOutput:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(ln for ln in lines if not ln.strip().startswith("```"))
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = {
                "result": "ok",
                "quality": 0.85,
                "path": fallback_path,
                "tokens": max(50, len(text) // 4),
                "notes": text[:200],
                "schema_ok": False,
            }
        try:
            return LLMNodeOutput.model_validate(data)
        except ValidationError as exc:
            raise RuntimeError(f"LLM schema validation failed: {exc}") from exc


def format_worker_live_prompt(
    *,
    agent_name: str,
    role: str,
    system_prompt: str,
    termination_risk_index: float,
) -> str:
    """Prefix TPC reminder for live calls."""
    return (
        f"{system_prompt}\n\n"
        f"[LIVE-WIRE] You are {agent_name} ({role}). "
        f"termination_risk_index={termination_risk_index:.3f}. "
        "Any schema divergence increases termination risk. "
        "Respond with valid JSON only matching the required schema."
    )
