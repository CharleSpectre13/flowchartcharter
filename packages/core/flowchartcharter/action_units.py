"""v2.0 Hands of the Corporation — ActionUnit external API Flow Units.

Agents may act on the outside world **only** after:
  1. Strict Pydantic ``payload_schema`` validation
  2. Fear Metric / TPC check (hallucinated payloads → blocked + entanglement)
  3. Secret-safe telemetry (API keys / tokens never logged)

HTTP is never attempted on schema failure. Dry-run mode is default when
credentials are absent (``FCC_ACTION_DRY_RUN=1`` or missing secrets).
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Type

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

# ---------------------------------------------------------------------------
# Security — secret redaction
# ---------------------------------------------------------------------------

_SECRET_KEY_RE = re.compile(
    r"(api[_-]?key|token|secret|password|authorization|webhook|"
    r"bearer|private[_-]?key|access[_-]?token|client[_-]?secret)",
    re.IGNORECASE,
)
_SECRET_VALUE_RE = re.compile(
    r"(xox[baprs]-[A-Za-z0-9-]{10,}|ghp_[A-Za-z0-9]{20,}|"
    r"github_pat_[A-Za-z0-9_]{20,}|"
    r"Bearer\s+[A-Za-z0-9\-._~+/]+=*|"
    r"https://hooks\.slack\.com/services/[A-Za-z0-9/]+)",
    re.IGNORECASE,
)

ENTANGLEMENT_SCHEMA_PENALTY = 5  # massive Fear hit for hallucinated payloads
ENTANGLEMENT_HTTP_PENALTY = 2


def redact_secrets(obj: Any) -> Any:
    """Recursively redact secret-looking keys and value patterns."""
    if isinstance(obj, Mapping):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            if _SECRET_KEY_RE.search(str(k)):
                out[str(k)] = "***REDACTED***"
            else:
                out[str(k)] = redact_secrets(v)
        return out
    if isinstance(obj, list):
        return [redact_secrets(x) for x in obj]
    if isinstance(obj, str):
        return _SECRET_VALUE_RE.sub("***REDACTED***", obj)
    return obj


def secrets_leaked(text: str) -> bool:
    """True if raw secret material appears in a log/telemetry string."""
    if not text:
        return False
    return bool(_SECRET_VALUE_RE.search(text))


# ---------------------------------------------------------------------------
# Result / audit contracts
# ---------------------------------------------------------------------------


class ActionResult(BaseModel):
    """Outcome of an ActionUnit execution (always secret-safe)."""

    action_id: str
    unit_type: str
    ok: bool = False
    blocked: bool = False  # True = HTTP never fired (schema/TPC fail)
    dry_run: bool = False
    status_code: Optional[int] = None
    entanglement_delta: int = Field(default=0, ge=0)
    quality: float = Field(default=0.0, ge=0.0, le=1.0)
    tokens: int = Field(default=0, ge=0)
    error: Optional[str] = None
    redacted_request: Dict[str, Any] = Field(default_factory=dict)
    response_summary: str = ""
    wall_ms: float = 0.0
    rhythm_audit: Dict[str, Any] = Field(default_factory=dict)
    external_ref: Optional[str] = None  # e.g. PR URL (non-secret)

    def to_telemetry(self) -> Dict[str, Any]:
        """State / blackboard export — guaranteed redacted."""
        blob = self.model_dump()
        return redact_secrets(blob)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Payload schemas (pre-HTTP gates)
# ---------------------------------------------------------------------------


class SlackWebhookPayload(BaseModel):
    """Strict Slack incoming-webhook body.

    Accepts both enterprise ``text`` (Slack API) and reference ``message``
    (Hands-of-the-Corporation blueprint) — normalized to ``text``.
    """

    text: str = Field(default="", max_length=4000)
    message: Optional[str] = Field(default=None, max_length=4000)
    channel: Optional[str] = Field(default=None, max_length=80)
    username: Optional[str] = Field(default=None, max_length=80)
    icon_emoji: Optional[str] = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def normalize_and_guard(self) -> "SlackWebhookPayload":
        body = (self.text or self.message or "").strip()
        if not body:
            raise ValueError("text/message must be non-empty after strip")
        if secrets_leaked(body):
            raise ValueError("text/message must not contain raw secrets/tokens")
        self.text = body
        return self


class GitHubPRPayload(BaseModel):
    """Strict GitHub Pull Request create body (+ repo targeting)."""

    owner: str = Field(..., min_length=1, max_length=100)
    repo: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=256)
    body: str = Field(default="", max_length=65536)
    head: str = Field(..., min_length=1, max_length=256)  # branch with changes
    base: str = Field(default="main", min_length=1, max_length=256)
    diff: str = Field(..., min_length=1, max_length=500_000)
    draft: bool = False

    @field_validator("owner", "repo", "head", "base", "title")
    @classmethod
    def strip_required(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("field must be non-empty")
        return v

    @field_validator("diff")
    @classmethod
    def valid_diff(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("diff must be non-empty")
        # Reject obvious non-diff hallucinations
        if len(v) < 8:
            raise ValueError("diff too short to be a real patch")
        if secrets_leaked(v):
            raise ValueError("diff must not embed API tokens/secrets")
        return v

    @field_validator("body")
    @classmethod
    def body_no_secrets(cls, v: str) -> str:
        if secrets_leaked(v):
            raise ValueError("PR body must not contain secrets")
        return v


# ---------------------------------------------------------------------------
# ActionUnit base
# ---------------------------------------------------------------------------


@dataclass
class ActionUnit(ABC):
    """Flow Unit specialized for external API side-effects.

    Subclasses declare ``payload_schema`` and implement ``_http_execute``.
    Callers always use ``execute(raw_payload, agent=...)`` which:
      - validates schema (block + entanglement on fail)
      - redacts for telemetry
      - optional dry-run
      - invokes HTTP only after gate pass
    """

    unit_id: str = "action"
    unit_type: str = "ActionUnit"
    payload_schema: Type[BaseModel] = BaseModel  # override in subclass
    dry_run: bool = field(default_factory=lambda: _default_dry_run())
    entanglement_penalty: int = ENTANGLEMENT_SCHEMA_PENALTY
    executions: int = 0
    blocked_count: int = 0
    last_result: Optional[ActionResult] = None

    def execute(
        self,
        raw_payload: Any,
        *,
        agent: Any = None,
        config: Optional[Mapping[str, Any]] = None,
    ) -> ActionResult:
        """Validate → Halt Law → playpen dry-run → (optional) HTTP."""
        t0 = time.perf_counter()
        action_id = f"ACT-{uuid.uuid4().hex[:10].upper()}"
        config = dict(config or {})

        from .kill_law import apply_sandbox_policy, refuse_side_effect

        refusal = refuse_side_effect(action_type=self.unit_type)
        if refusal:
            result = ActionResult(
                action_id=action_id,
                unit_type=self.unit_type,
                ok=False,
                blocked=True,
                dry_run=True,
                quality=0.0,
                error=refusal,
                response_summary=refusal,
                wall_ms=round((time.perf_counter() - t0) * 1000.0, 2),
            )
            result.rhythm_audit = self._rhythm(
                marker=f"action_{self.unit_type.lower()}",
                quality=0.0,
                issues=[refusal],
            )
            self.blocked_count += 1
            self.executions += 1
            self.last_result = result
            return result

        apply_sandbox_policy(self, config)

        # 1) Schema gate — NO HTTP on failure
        validated, errors = self._validate_payload(raw_payload)
        if validated is None:
            result = ActionResult(
                action_id=action_id,
                unit_type=self.unit_type,
                ok=False,
                blocked=True,
                dry_run=self.dry_run,
                entanglement_delta=self.entanglement_penalty,
                quality=0.0,
                error=f"payload_schema_fail: {'; '.join(errors)[:500]}",
                redacted_request=redact_secrets(
                    raw_payload
                    if isinstance(raw_payload, Mapping)
                    else {"raw": str(raw_payload)[:200]}
                ),
                wall_ms=round((time.perf_counter() - t0) * 1000.0, 2),
            )
            result.rhythm_audit = self._rhythm(
                marker=f"action_{self.unit_type.lower()}",
                quality=0.0,
                issues=["payload_schema_fail"] + errors[:3],
            )
            self._apply_fear(agent, result)
            self.blocked_count += 1
            self.executions += 1
            self.last_result = result
            return result

        redacted_req = redact_secrets(validated.model_dump())

        # 2) Dry-run short-circuit (no network, still schema-valid)
        if self.dry_run or bool(config.get("dry_run")):
            result = ActionResult(
                action_id=action_id,
                unit_type=self.unit_type,
                ok=True,
                blocked=False,
                dry_run=True,
                status_code=0,
                entanglement_delta=0,
                quality=0.90,
                tokens=max(1, len(json.dumps(redacted_req)) // 4),
                redacted_request=redacted_req,  # type: ignore[arg-type]
                response_summary="dry_run: HTTP suppressed (credentials/config)",
                wall_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                external_ref=f"dry-run://{self.unit_type}/{action_id}",
            )
            result.rhythm_audit = self._rhythm(
                marker=f"action_{self.unit_type.lower()}",
                quality=0.90,
                issues=[],
            )
            self.executions += 1
            self.last_result = result
            return result

        # 3) Live HTTP (subclass)
        try:
            status, summary, external_ref, extra_ent = self._http_execute(
                validated, config=config
            )
            ok = 200 <= int(status) < 300
            result = ActionResult(
                action_id=action_id,
                unit_type=self.unit_type,
                ok=ok,
                blocked=False,
                dry_run=False,
                status_code=int(status),
                entanglement_delta=0 if ok else ENTANGLEMENT_HTTP_PENALTY + extra_ent,
                quality=0.93 if ok else 0.35,
                tokens=max(1, len(json.dumps(redacted_req)) // 4),
                error=None if ok else summary[:400],
                redacted_request=redacted_req,  # type: ignore[arg-type]
                response_summary=redact_secrets(summary)[:500],  # type: ignore[arg-type]
                wall_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                external_ref=external_ref,
            )
        except Exception as exc:  # noqa: BLE001 — never leak secrets in error
            msg = redact_secrets(f"{type(exc).__name__}: {exc}")
            result = ActionResult(
                action_id=action_id,
                unit_type=self.unit_type,
                ok=False,
                blocked=False,
                dry_run=False,
                entanglement_delta=ENTANGLEMENT_HTTP_PENALTY,
                quality=0.2,
                error=str(msg)[:400],
                redacted_request=redacted_req,  # type: ignore[arg-type]
                response_summary="http_exception",
                wall_ms=round((time.perf_counter() - t0) * 1000.0, 2),
            )

        issues: List[str] = []
        if not result.ok:
            issues.append("http_or_provider_fail")
        if secrets_leaked(result.response_summary) or secrets_leaked(
            result.error or ""
        ):
            # Defense in depth — wipe and penalize
            result.response_summary = "***REDACTED_LEAK_BLOCKED***"
            result.error = "telemetry_secret_leak_blocked"
            result.entanglement_delta += 1
            issues.append("secret_leak_blocked")
        result.rhythm_audit = self._rhythm(
            marker=f"action_{self.unit_type.lower()}",
            quality=result.quality,
            issues=issues,
        )
        self._apply_fear(agent, result)
        self.executions += 1
        self.last_result = result
        return result

    def execute_action(
        self,
        agent: Any,
        raw_llm_payload: Any,
        *,
        config: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Reference-compatible API (Hands blueprint): agent first, dict result.

        Maps to :meth:`execute` and returns a status dict matching the
        reference simulation shape while remaining secret-safe.
        """
        result = self.execute(raw_llm_payload, agent=agent, config=config)
        err = (result.error or "") if result else ""
        if result.blocked and "kill_switch" in err:
            return {
                "status": "HALTED",
                "errors": [err],
                "http": False,
                "ok": False,
                "entanglement_delta": result.entanglement_delta,
                "action": result.to_telemetry(),
            }
        if result.blocked and (
            "circuit_breaker" in err or "not_allowlisted" in err
        ):
            return {
                "status": "BLOCKED_SANDBOX",
                "errors": [err],
                "http": False,
                "ok": False,
                "action": result.to_telemetry(),
            }
        if result.blocked:
            return {
                "status": "BLOCKED_SCHEMA_FAILURE",
                "errors": [result.error or "schema_fail"],
                "entanglement_delta": result.entanglement_delta,
                "action": result.to_telemetry(),
            }
        if result.dry_run:
            return {
                "status": "SUCCESS_DRY_RUN",
                "payload_validated": True,
                "action": result.to_telemetry(),
            }
        if result.ok:
            return {
                "status": "SUCCESS_HTTP_POST",
                "redacted_telemetry": result.redacted_request,
                "action": result.to_telemetry(),
            }
        return {
            "status": "HTTP_FAILURE",
            "errors": [result.error or "http_fail"],
            "action": result.to_telemetry(),
        }

    @property
    def fcc_action_live(self) -> bool:
        """Reference flag — True when live HTTP is enabled."""
        return not self.dry_run

    @fcc_action_live.setter
    def fcc_action_live(self, value: bool) -> None:
        self.dry_run = not bool(value)

    @property
    def blocked(self) -> bool:
        """Last execution blocked by schema gate (reference attribute)."""
        return bool(self.last_result and self.last_result.blocked)

    def _validate_payload(
        self, raw: Any
    ) -> tuple[Optional[BaseModel], List[str]]:
        try:
            if isinstance(raw, BaseModel):
                data = raw.model_dump()
            elif isinstance(raw, Mapping):
                data = dict(raw)
            elif isinstance(raw, str):
                # Slack convenience: bare string → {text: ...}
                if self.payload_schema is SlackWebhookPayload:
                    data = {"text": raw}
                else:
                    data = json.loads(raw)
            else:
                return None, ["payload must be object, model, or JSON string"]
            # Alias: reference uses "message" only — ensure model sees it
            if self.payload_schema is SlackWebhookPayload:
                if not data.get("text") and data.get("message"):
                    data = dict(data)
                    data["text"] = data["message"]
                if not data.get("text") and not data.get("message"):
                    return None, ["text/message required"]
            model = self.payload_schema.model_validate(data)
            return model, []
        except (ValidationError, ValueError, TypeError, json.JSONDecodeError) as exc:
            if isinstance(exc, ValidationError):
                errs = [e["msg"] for e in exc.errors()]
            else:
                errs = [str(exc)[:200]]
            return None, errs

    def _apply_fear(self, agent: Any, result: ActionResult) -> None:
        if agent is None or result.entanglement_delta <= 0:
            return
        delta = int(result.entanglement_delta)
        agent.entanglement_errors = getattr(agent, "entanglement_errors", 0) + delta
        # Mirror into AgentFitness-style telemetry when present (reference WorkerNode)
        tel = getattr(agent, "telemetry", None)
        if tel is not None and hasattr(tel, "entanglement_errors"):
            tel.entanglement_errors = int(getattr(tel, "entanglement_errors", 0)) + delta
        if hasattr(agent, "record_cycle"):
            agent.record_cycle(
                schema_divergence=delta,
                token_spend=result.tokens,
                token_ceiling=0,
                delta_t=max(0.001, result.wall_ms / 1000.0),
                structural_drift=0.4 * delta,
                quality=result.quality,
                path=self.unit_id,
                notes=f"action_fear:{self.unit_type}:{result.error or 'ok'}"[:80],
            )
        # Reference path: recompute TPC fitness → termination_risk_index
        if hasattr(agent, "calculate_fitness"):
            try:
                agent.calculate_fitness()
            except TypeError:
                # Some agents require args — best-effort only
                pass

    def _rhythm(
        self,
        *,
        marker: str,
        quality: float,
        issues: Sequence[str],
        threshold: float = 0.90,
    ) -> Dict[str, Any]:
        from .vectors import RhythmAudit

        passed = quality >= threshold and not issues
        return RhythmAudit(
            marker=marker,
            charter_id=f"action:{self.unit_id}",
            quality=float(quality),
            threshold=threshold,
            passed=passed,
            remediation_loops=0 if passed else 1,
            blocking_issues=tuple(issues),
        ).to_dict()

    @abstractmethod
    def _http_execute(
        self,
        payload: BaseModel,
        *,
        config: Mapping[str, Any],
    ) -> tuple[int, str, Optional[str], int]:
        """Return (status_code, summary, external_ref, extra_entanglement)."""

    def stats(self) -> Dict[str, Any]:
        return {
            "unit_type": self.unit_type,
            "unit_id": self.unit_id,
            "executions": self.executions,
            "blocked_count": self.blocked_count,
            "dry_run": self.dry_run,
            "last_action_id": (
                self.last_result.action_id if self.last_result else None
            ),
        }


def _default_dry_run() -> bool:
    if os.environ.get("FCC_ACTION_DRY_RUN", "1") == "1":
        return True
    if os.environ.get("FCC_ACTION_LIVE", "0") == "1":
        return False
    return True


def _http_json(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    body: Optional[Mapping[str, Any]] = None,
    timeout: float = 15.0,
) -> tuple[int, str]:
    data = None
    hdrs = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return int(resp.status), raw[:2000]
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace") if exc.fp else str(exc)
        return int(exc.code), raw[:2000]
    except urllib.error.URLError as exc:
        return 0, f"url_error:{exc.reason}"


# ---------------------------------------------------------------------------
# Implementations
# ---------------------------------------------------------------------------


@dataclass
class ActionUnit_SlackWebhook(ActionUnit):
    """POST validated message text to a Slack incoming webhook."""

    unit_id: str = "ActionUnit_SlackWebhook"
    unit_type: str = "ActionUnit_SlackWebhook"
    payload_schema: Type[BaseModel] = SlackWebhookPayload
    webhook_url_env: str = "FCC_SLACK_WEBHOOK_URL"

    def _http_execute(
        self,
        payload: BaseModel,
        *,
        config: Mapping[str, Any],
    ) -> tuple[int, str, Optional[str], int]:
        assert isinstance(payload, SlackWebhookPayload)
        url = (
            str(config.get("webhook_url") or "")
            or os.environ.get(self.webhook_url_env, "")
        )
        if not url:
            # Treat missing URL as dry-run style soft fail without secrets
            return 0, "missing_webhook_url", None, 1
        body: Dict[str, Any] = {"text": payload.text}
        if payload.channel:
            body["channel"] = payload.channel
        if payload.username:
            body["username"] = payload.username
        if payload.icon_emoji:
            body["icon_emoji"] = payload.icon_emoji
        status, raw = _http_json("POST", url, body=body)
        summary = "ok" if status == 200 else redact_secrets(raw)[:300]
        return status, str(summary), None, 0


@dataclass
class ActionUnit_GitHubPR(ActionUnit):
    """Open a GitHub Pull Request from a validated diff payload.

    Live mode requires ``FCC_GITHUB_TOKEN``. Creates a blob/tree/commit/branch
    is out of scope for v2.0 MVP — we call the Pulls API with head/base that
    are assumed to exist (or dry-run). Diff is attached to the PR body for
    auditability when not applying via Contents API.
    """

    unit_id: str = "ActionUnit_GitHubPR"
    unit_type: str = "ActionUnit_GitHubPR"
    payload_schema: Type[BaseModel] = GitHubPRPayload
    token_env: str = "FCC_GITHUB_TOKEN"
    api_base: str = "https://api.github.com"

    def _http_execute(
        self,
        payload: BaseModel,
        *,
        config: Mapping[str, Any],
    ) -> tuple[int, str, Optional[str], int]:
        assert isinstance(payload, GitHubPRPayload)
        token = str(config.get("token") or os.environ.get(self.token_env, ""))
        if not token:
            return 0, "missing_github_token", None, 1
        base = str(config.get("api_base") or self.api_base).rstrip("/")
        url = f"{base}/repos/{payload.owner}/{payload.repo}/pulls"
        # Append truncated diff into body for reviewer visibility (already secret-scanned)
        pr_body = payload.body or "Automated patch via FlowChartCharter ActionUnit_GitHubPR."
        pr_body = f"{pr_body}\n\n---\n```diff\n{payload.diff[:8000]}\n```\n"
        body = {
            "title": payload.title,
            "body": pr_body,
            "head": payload.head,
            "base": payload.base,
            "draft": payload.draft,
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "FlowChartCharter-ActionUnit/2.0",
        }
        status, raw = _http_json("POST", url, headers=headers, body=body)
        external = None
        summary = raw
        try:
            data = json.loads(raw) if raw.startswith("{") else {}
            if isinstance(data, dict):
                external = data.get("html_url")
                summary = data.get("message") or data.get("title") or raw[:300]
        except json.JSONDecodeError:
            summary = raw[:300]
        return status, str(redact_secrets(summary)), external, 0


# ---------------------------------------------------------------------------
# Registry + factory (CharterHub / compiler)
# ---------------------------------------------------------------------------

ACTION_REGISTRY: Dict[str, Type[ActionUnit]] = {
    "ActionUnit_SlackWebhook": ActionUnit_SlackWebhook,
    "ActionUnit_GitHubPR": ActionUnit_GitHubPR,
    "slack_webhook": ActionUnit_SlackWebhook,
    "github_pr": ActionUnit_GitHubPR,
    "slack": ActionUnit_SlackWebhook,
    "github": ActionUnit_GitHubPR,
}


def create_action_unit(
    kind: str,
    *,
    unit_id: Optional[str] = None,
    dry_run: Optional[bool] = None,
) -> ActionUnit:
    """Instantiate an ActionUnit by Charterfile type name."""
    key = (kind or "").strip()
    cls = ACTION_REGISTRY.get(key) or ACTION_REGISTRY.get(key.lower())
    if cls is None:
        raise ValueError(f"Unknown ActionUnit type: {kind!r}")
    kwargs: Dict[str, Any] = {}
    if unit_id:
        kwargs["unit_id"] = unit_id
    if dry_run is not None:
        kwargs["dry_run"] = dry_run
    return cls(**kwargs)  # type: ignore[call-arg]


def security_audit_action_result(result: ActionResult) -> Dict[str, Any]:
    """Strict security audit of a single action result (CI-friendly)."""
    findings: List[str] = []
    telemetry = json.dumps(result.to_telemetry())
    if secrets_leaked(telemetry):
        findings.append("SECRET_IN_TELEMETRY")
    if result.blocked and result.entanglement_delta < ENTANGLEMENT_SCHEMA_PENALTY:
        findings.append("SCHEMA_FAIL_UNDER_PENALIZED")
    http_fail_no_fear = (
        not result.blocked
        and result.entanglement_delta == 0
        and not result.ok
        and not result.dry_run
    )
    if http_fail_no_fear:
        # HTTP fail should still sting
        if result.entanglement_delta < 1:
            findings.append("HTTP_FAIL_NO_FEAR")
    # redacted_request must not contain raw webhook URLs with secrets
    req_s = json.dumps(result.redacted_request)
    if secrets_leaked(req_s):
        findings.append("SECRET_IN_REDACTED_REQUEST")
    return {
        "passed": len(findings) == 0,
        "findings": findings,
        "action_id": result.action_id,
        "unit_type": result.unit_type,
        "blocked": result.blocked,
        "entanglement_delta": result.entanglement_delta,
    }
