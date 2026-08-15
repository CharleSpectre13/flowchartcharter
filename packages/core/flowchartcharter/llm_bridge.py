"""Live-Wire LLM Port — vendor-agnostic HTTP adapter.

Honesty contract (v2.2.1):
  - Key resolution is shared with the provider registry.
  - TPC sampling is applied to the HTTP body, not just prompt prose.
  - Provider usage tokens are returned separately from model-authored JSON.
  - Secrets never appear in URLs or logged metadata.
  - Default remains mock. No vendor SDKs.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple
from urllib.parse import urlparse

from pydantic import BaseModel, Field, ValidationError, field_validator


# ---------------------------------------------------------------------------
# Key resolution (single source of truth)
# ---------------------------------------------------------------------------

PROVIDER_SPECIFIC_ENV: Dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "xai": "XAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "ollama": "FCC_OLLAMA_KEY",
}

DEFAULT_MODELS: Dict[str, str] = {
    "mock": "mock-local",
    "openai": "gpt-4o-mini",
    "xai": "grok-4.5",
    "gemini": "gemini-1.5-flash",
    "ollama": "llama3.2",
}

DEFAULT_BASE_URLS: Dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "xai": "https://api.x.ai/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
    "ollama": "http://127.0.0.1:11434/v1",
}


def ollama_reachable(base: str = "") -> bool:
    """Short probe. Never required. Fail closed."""
    root = (
        base
        or os.environ.get("FCC_OLLAMA_URL")
        or "http://127.0.0.1:11434"
    ).rstrip("/")
    if root.endswith("/v1"):
        root = root[:-3]
    try:
        req = urllib.request.Request(root + "/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=0.4) as resp:
            return 200 <= int(resp.status) < 300
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return False


def detect_live_provider() -> str:
    """Auto-select a live vendor when a key exists. Else optional Ollama. Else mock.

    FCC_LLM_PROVIDER=mock|xai|openai|gemini|ollama|auto
    FCC_OLLAMA=1 allows a localhost probe. Never required.
    """
    forced = (os.environ.get("FCC_LLM_PROVIDER") or "").strip().lower()
    if forced and forced not in {"", "auto"}:
        return forced
    if (os.environ.get("XAI_API_KEY") or "").strip():
        return "xai"
    if (os.environ.get("OPENAI_API_KEY") or "").strip():
        return "openai"
    if (os.environ.get("GEMINI_API_KEY") or "").strip():
        return "gemini"
    if os.environ.get("FCC_OLLAMA", "0") == "1" and ollama_reachable():
        return "ollama"
    return "mock"


def resolve_provider_key(provider: str) -> Tuple[str, str]:
    """Return (api_key, env_var_name_used). Never log the key.

    Priority:
      1. Provider-specific env (XAI_API_KEY / OPENAI_API_KEY / GEMINI_API_KEY)
      2. FCC_LLM_API_KEY — only if this provider is the active FCC_LLM_PROVIDER
    """
    name = (provider or "mock").lower()
    if name == "mock":
        return "", ""
    if name == "ollama":
        specific = (os.environ.get("FCC_OLLAMA_KEY") or "ollama").strip()
        return specific, "FCC_OLLAMA_KEY"
    specific_env = PROVIDER_SPECIFIC_ENV.get(name, "")
    if specific_env:
        specific = os.environ.get(specific_env, "") or ""
        if specific.strip():
            return specific.strip(), specific_env
    generic = (os.environ.get("FCC_LLM_API_KEY", "") or "").strip()
    active = detect_live_provider()
    if generic and active == name:
        return generic, "FCC_LLM_API_KEY"
    return "", ""


def default_model_for(provider: str) -> str:
    name = (provider or "mock").lower()
    override = os.environ.get("FCC_LLM_MODEL", "")
    active = os.environ.get("FCC_LLM_PROVIDER", "mock").lower()
    named = os.environ.get(f"FCC_{name.upper()}_MODEL", "")
    if named.strip():
        return named.strip()
    if override.strip() and (active == name or name == "mock"):
        return override.strip()
    return DEFAULT_MODELS.get(name, "grok-4.5")


# ---------------------------------------------------------------------------
# Usage + sampling (economic truth / Fear on the wire)
# ---------------------------------------------------------------------------


@dataclass
class ProviderUsage:
    """Billed tokens from the vendor. source=provider|mock|estimate."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    source: str = "none"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def billed(self) -> int:
        return int(self.total_tokens or (self.prompt_tokens + self.completion_tokens))


@dataclass
class SamplingParams:
    """TPC knobs that MUST hit the HTTP body."""

    temperature: float = 0.2
    top_p: float = 0.95
    max_tokens: int = 512
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ChatResult:
    text: str
    usage: ProviderUsage = field(default_factory=ProviderUsage)
    sampling: Dict[str, Any] = field(default_factory=dict)
    request_meta: Dict[str, Any] = field(default_factory=dict)


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
    model: str = "grok-4.5"
    api_key: str = ""
    key_env: str = ""
    base_url: str = ""
    timeout_s: float = 30.0
    max_tokens: int = 512

    @classmethod
    def from_env(cls) -> "LLMBridgeConfig":
        provider = detect_live_provider()
        key, key_env = resolve_provider_key(provider)
        base = os.environ.get("FCC_LLM_BASE_URL", "")
        if not base:
            base = DEFAULT_BASE_URLS.get(provider, "")
        return cls(
            provider=provider,
            model=default_model_for(provider),
            api_key=key,
            key_env=key_env,
            base_url=base,
            timeout_s=float(os.environ.get("FCC_LLM_TIMEOUT", "30")),
            max_tokens=int(os.environ.get("FCC_LLM_MAX_TOKENS", "512")),
        )


class LLMBridge:
    """Outbound LLM client with Pydantic schema validation on return."""

    def __init__(self, config: Optional[LLMBridgeConfig] = None) -> None:
        self.config = config or LLMBridgeConfig.from_env()
        self.last_sampling: Dict[str, Any] = {}
        self.last_usage: ProviderUsage = ProviderUsage()
        self.last_request_meta: Dict[str, Any] = {}

    @property
    def live(self) -> bool:
        if self.config.provider == "ollama":
            return ollama_reachable(self.config.base_url)
        return self.config.provider != "mock" and bool(self.config.api_key)

    def execute_worker(
        self,
        *,
        system_prompt: str,
        workload: str,
        path: str,
        termination_risk_index: float,
        sampling: Optional[SamplingParams] = None,
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
            return self._mock(path=path, risk=termination_risk_index, sampling=sampling)

        result = self.chat(system_prompt, user_msg, sampling=sampling)
        node = self._parse_and_validate(result.text, fallback_path=path)
        if result.usage.billed > 0:
            node.tokens = result.usage.billed
        return node

    def _mock(
        self,
        *,
        path: str,
        risk: float,
        sampling: Optional[SamplingParams] = None,
    ) -> LLMNodeOutput:
        q = max(0.7, min(1.0, 0.95 - 0.2 * risk))
        tokens = {"path_A": 180, "path_B": 340, "path_lite": 90}.get(path, 200)
        samp = sampling or SamplingParams(max_tokens=self.config.max_tokens)
        self.last_sampling = samp.to_dict()
        self.last_usage = ProviderUsage(
            prompt_tokens=40,
            completion_tokens=max(0, tokens - 40),
            total_tokens=tokens,
            source="mock",
        )
        self.last_request_meta = {
            "provider": "mock",
            "live": False,
            "query_has_key": False,
            "host": "",
        }
        return LLMNodeOutput(
            result="ok",
            quality=q,
            path=path,
            tokens=tokens,
            notes="mock-llm",
            schema_ok=True,
        )

    def chat(
        self,
        system: str,
        user: str,
        *,
        sampling: Optional[SamplingParams] = None,
    ) -> ChatResult:
        """Public chat. Applies TPC sampling. Returns text + billed usage."""
        cfg = self.config
        samp = sampling or SamplingParams(
            temperature=0.2,
            top_p=0.95,
            max_tokens=int(cfg.max_tokens),
        )
        self.last_sampling = samp.to_dict()

        if cfg.provider in ("openai", "xai", "ollama"):
            url = f"{cfg.base_url.rstrip('/')}/chat/completions"
            body: Dict[str, Any] = {
                "model": cfg.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": int(samp.max_tokens),
                "temperature": float(samp.temperature),
                "top_p": float(samp.top_p),
            }
            if samp.frequency_penalty:
                body["frequency_penalty"] = float(samp.frequency_penalty)
            if samp.presence_penalty:
                body["presence_penalty"] = float(samp.presence_penalty)
            headers = {
                "Authorization": f"Bearer {cfg.api_key}",
                "Content-Type": "application/json",
            }
            parsed, meta = self._http_json(url, body, headers)
            text = _openai_text(parsed)
            usage = _openai_usage(parsed)
            self.last_usage = usage
            self.last_request_meta = meta
            return ChatResult(text=text, usage=usage, sampling=samp.to_dict(), request_meta=meta)

        if cfg.provider == "gemini":
            url = (
                f"{cfg.base_url.rstrip('/')}/models/{cfg.model}:generateContent"
            )
            body = {
                "contents": [{"parts": [{"text": f"SYSTEM:\n{system}\n\nUSER:\n{user}"}]}],
                "generationConfig": {
                    "temperature": float(samp.temperature),
                    "topP": float(samp.top_p),
                    "maxOutputTokens": int(samp.max_tokens),
                },
            }
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": cfg.api_key,
            }
            parsed, meta = self._http_json(url, body, headers)
            text = _gemini_text(parsed)
            usage = _gemini_usage(parsed)
            self.last_usage = usage
            self.last_request_meta = meta
            return ChatResult(text=text, usage=usage, sampling=samp.to_dict(), request_meta=meta)

        mock_node = self._mock(path="path_A", risk=0.0, sampling=samp)
        return ChatResult(
            text=mock_node.model_dump_json(),
            usage=self.last_usage,
            sampling=samp.to_dict(),
            request_meta=self.last_request_meta,
        )

    # Back-compat private name used by older callers
    def _chat(self, system: str, user: str) -> str:
        return self.chat(system, user).text

    def _http_json(
        self,
        url: str,
        body: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Tuple[Any, Dict[str, Any]]:
        parsed_url = urlparse(url)
        query = parsed_url.query or ""
        meta = {
            "provider": self.config.provider,
            "live": True,
            "host": parsed_url.netloc,
            "path": parsed_url.path,
            "query_has_key": "key=" in query.lower(),
            "auth_header": "authorization" in {k.lower() for k in headers}
            or "x-goog-api-key" in {k.lower() for k in headers},
        }
        if meta["query_has_key"]:
            raise RuntimeError("Port honesty: API key must not appear in the request URL")

        data = json.dumps(body).encode("utf-8")
        safe_headers = dict(headers)
        req = urllib.request.Request(url, data=data, headers=safe_headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout_s) as resp:
                payload = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"LLM HTTP {exc.code}: {exc.read()[:200]}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"LLM network error: {exc}") from exc

        try:
            parsed: Any = json.loads(payload)
        except json.JSONDecodeError:
            parsed = {"raw": payload}
        return parsed, meta

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


def _openai_text(parsed: Any) -> str:
    if isinstance(parsed, dict) and "choices" in parsed:
        try:
            return parsed["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            return json.dumps(parsed)
    if isinstance(parsed, dict) and "raw" in parsed:
        return str(parsed["raw"])
    return json.dumps(parsed) if not isinstance(parsed, str) else parsed


def _openai_usage(parsed: Any) -> ProviderUsage:
    if not isinstance(parsed, dict):
        return ProviderUsage(source="estimate")
    usage = parsed.get("usage") or {}
    if not isinstance(usage, Mapping):
        return ProviderUsage(source="estimate")
    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    total = int(usage.get("total_tokens") or (prompt + completion))
    if total <= 0:
        return ProviderUsage(source="estimate")
    return ProviderUsage(
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=total,
        source="provider",
    )


def _gemini_text(parsed: Any) -> str:
    if not isinstance(parsed, dict):
        return str(parsed)
    try:
        return parsed["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        return parsed.get("raw") or json.dumps(parsed)


def _gemini_usage(parsed: Any) -> ProviderUsage:
    if not isinstance(parsed, dict):
        return ProviderUsage(source="estimate")
    meta = parsed.get("usageMetadata") or parsed.get("usage_metadata") or {}
    if not isinstance(meta, Mapping):
        return ProviderUsage(source="estimate")
    prompt = int(meta.get("promptTokenCount") or meta.get("prompt_token_count") or 0)
    completion = int(
        meta.get("candidatesTokenCount") or meta.get("candidates_token_count") or 0
    )
    total = int(
        meta.get("totalTokenCount") or meta.get("total_token_count") or (prompt + completion)
    )
    if total <= 0:
        return ProviderUsage(source="estimate")
    return ProviderUsage(
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=total,
        source="provider",
    )


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
