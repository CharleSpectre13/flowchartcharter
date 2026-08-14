"""FlowChartCharter API Nervous System — FastAPI microservice wrapper.

Phase 2–3 Live Launch: expose the engine so dashboards and enterprise
tools can submit JSON workloads, load Charterfile YAML playbooks, and
drive Monday Sync / Analytics over HTTP.

Global application state keeps GM, Muscle-Memory VDB, Living Playbook,
Analytics Chief, and PlaybookCompiler resident between requests.
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from .agents import AgentStatus, BossAgent
from .system import FlowChartCharterSystem
from .observability import get_metrics_hub
from .security import ensure_admin_key_on_boot, require_admin_key
from .state_persister import get_persister

try:
    from . import __version__ as ENGINE_VERSION
except Exception:  # noqa: BLE001
    ENGINE_VERSION = "1.7.0"


def _repo_root() -> Path:
    # packages/core/flowchartcharter/api_server.py → repo root
    return Path(__file__).resolve().parents[3]


def _dashboard_dir() -> Path:
    env = os.environ.get("FCC_DASHBOARD_DIR")
    if env:
        return Path(env)
    cand = _repo_root() / "dashboard"
    if cand.is_dir():
        return cand
    return Path(__file__).resolve().parent / "static_dashboard"


def _library_dir() -> Path:
    env = os.environ.get("FCC_LIBRARY_DIR")
    if env:
        return Path(env)
    cand = _repo_root() / "library"
    if cand.is_dir():
        return cand
    return Path(__file__).resolve().parent / "library"


class WorkloadSubmitRequest(BaseModel):
    """POST /workload/submit body."""

    workload: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Human-readable job description routed to the Boss Agent",
    )
    context_entropy: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional H_ctx override in [0, 1]",
    )
    payload: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional structured payload for state encoding",
    )
    force_capability: Optional[str] = Field(
        default=None,
        description="Force Elastic Requisition for this capability",
    )
    force_zero_shot: bool = Field(
        default=False,
        description="Force Living Playbook zero-shot synthesis",
    )
    force_quality: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Test-only quality override",
    )

    @field_validator("workload")
    @classmethod
    def strip_workload(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("workload must be non-empty")
        return v


class HybridRouteRequest(BaseModel):
    """POST /hybrid/route — classify only (v1.7)."""

    workload: str = Field(..., min_length=1, max_length=2000)
    hint: Optional[str] = Field(
        default=None,
        description="Force lane: simple | multi_hop | global",
    )
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("workload")
    @classmethod
    def strip_workload(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("workload must be non-empty")
        return v


class HybridWorkloadRequest(BaseModel):
    """POST /hybrid/workload — full tri-state execute (v1.7)."""

    workload: str = Field(..., min_length=1, max_length=2000)
    hint: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    seed_entity: Optional[str] = None
    cfo_ceiling: Optional[int] = Field(default=None, ge=50, le=50000)

    @field_validator("workload")
    @classmethod
    def strip_workload(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("workload must be non-empty")
        return v


class SwarmRunRequest(BaseModel):
    """POST /swarm/run — parallel dataset under CFO ceiling (v1.8)."""

    items: List[Any] = Field(..., min_length=1, max_length=5000)
    max_workers: Optional[int] = Field(default=None, ge=1, le=64)
    cfo_ceiling: Optional[int] = Field(default=None, ge=50, le=500_000)
    mode: str = Field(default="thread", description="thread | asyncio")


class HeadhunterRequest(BaseModel):
    """POST /system/headhunter/requisition."""

    fired_name: Optional[str] = None
    force: bool = True
    force_capability: Optional[str] = None


class ActionExecuteRequest(BaseModel):
    """POST /action/execute — schema-gated external ActionUnit."""

    action: str = Field(
        ...,
        min_length=1,
        max_length=80,
        description="ActionUnit_SlackWebhook | ActionUnit_GitHubPR | aliases",
    )
    payload: Dict[str, Any] = Field(default_factory=dict)
    dry_run: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None
    agent_name: Optional[str] = None


class SynthesizeCharterRequest(BaseModel):
    """POST /system/synthesize-charter — v2.1 Coach Trust draft."""

    goal: str = Field(..., min_length=3, max_length=2000)
    coach_ceiling: Optional[int] = Field(default=None, ge=100, le=5_000_000)
    playbook_name: Optional[str] = Field(default=None, max_length=160)


class ApproveCharterRequest(BaseModel):
    """POST /system/approve-charter — 1-click Head Coach hand-off."""

    draft_id: str = Field(..., min_length=3, max_length=64)
    approved_by: str = Field(default="Head Coach", max_length=120)
    execute_workload: Optional[str] = Field(default=None, max_length=2000)


class RejectCharterRequest(BaseModel):
    draft_id: str = Field(..., min_length=3, max_length=64)
    reason: str = Field(default="coach_rejected", max_length=400)


class TenantEnsureRequest(BaseModel):
    """POST /system/tenant — ensure tenant namespace."""

    tenant_id: str = Field(..., min_length=1, max_length=80)
    cfo_ceiling: Optional[int] = Field(default=None, ge=100, le=5_000_000)


class WorkloadSubmitResponse(BaseModel):
    request_id: str
    workload: str
    quality: float
    trust: bool
    playbook_mode: Optional[str] = None
    context_entropy: float
    token_spend: int
    muscle_memory_hit: bool
    ascension: Optional[bool] = None
    phantom_spawned: Optional[str] = None
    remediation_loops: int = 0
    flow_path_reused: Optional[List[str]] = None
    analytics: Optional[Dict[str, Any]] = None
    live_wire: bool = True
    llm_provider: str = "mock"
    entanglement_mean: float = 0.0
    elapsed_ms: float


class RosterNodeStatus(BaseModel):
    name: str
    id: str
    role: str
    status: str
    fitness: float
    termination_risk_index: float
    survival_status: str
    is_phantom: bool
    corporate_rank: float
    capabilities: List[str]
    cycles: int


class RosterStatusResponse(BaseModel):
    roster: List[RosterNodeStatus]
    boss: Dict[str, Any]
    active_ops: int
    token_spend: int
    token_budget: int
    muscle_memory_records: int
    living_playbook_records: int
    analytics: Dict[str, Any]
    engine_version: str


class MondaySyncResponse(BaseModel):
    outcomes: Dict[str, str]
    dossier_driven: bool
    dossier: Optional[Dict[str, Any]] = None
    lean_rehire: List[Dict[str, Any]] = Field(default_factory=list)
    active_ops_after_prune: int
    ascension: bool
    analytics: Dict[str, Any]


class AdvanceAnalyticsResponse(BaseModel):
    day_closed: int
    days_ready: int
    workweek_complete: bool
    dossier: Optional[Dict[str, Any]] = None
    outcomes: Optional[Dict[str, str]] = None
    dossier_driven: bool
    analytics: Dict[str, Any]


class HealthResponse(BaseModel):
    status: str
    engine: str
    version: str
    uptime_s: float
    days_ready: int
    roster_size: int


class LoadPlaybookResponse(BaseModel):
    playbook_id: str
    playbook_name: str
    version: str
    ops_roster: List[str]
    token_budget: int
    flow_path: List[str]
    models: List[str]
    load_count: int


class PersonnelUpgradeRequest(BaseModel):
    model_class: str = Field(..., min_length=1, max_length=64)


class EngineState:
    """Process-global FlowChartCharter engine — persists across requests."""

    def __init__(self) -> None:
        seed_env = os.environ.get("FCC_SEED")
        seed = int(seed_env) if seed_env is not None else 42
        model_class = os.environ.get("FCC_MODEL_CLASS", "generic")
        self.system = FlowChartCharterSystem(
            seed=seed,
            model_class=model_class,
            deterministic_routing=True,
        )
        self.started_at = time.time()
        self.request_count = 0
        self.hybrid_request_count = 0
        self.restore_report: Dict[str, Any] = {}
        try:
            self.restore_report = self.system.restore_state()
        except Exception as exc:  # noqa: BLE001
            self.restore_report = {"restored": False, "error": str(exc)}

    @property
    def uptime_s(self) -> float:
        return time.time() - self.started_at


_STATE: Optional[EngineState] = None


def get_state() -> EngineState:
    if _STATE is None:
        raise RuntimeError("Engine state not initialized — lifespan not started")
    return _STATE


def _roster_nodes(system: FlowChartCharterSystem) -> List[RosterNodeStatus]:
    nodes: List[RosterNodeStatus] = []
    for agent in system.roster:
        if isinstance(agent, BossAgent):
            continue
        snap = agent.survival_snapshot()
        nodes.append(
            RosterNodeStatus(
                name=agent.name,
                id=agent.id,
                role=agent.role,
                status=agent.status.value,
                fitness=float(snap.get("fitness") or 0.0),
                termination_risk_index=agent.termination_risk_index,
                survival_status=agent.survival_status.value,
                is_phantom=bool(getattr(agent, "is_phantom", False)),
                corporate_rank=float(agent.corporate_rank),
                capabilities=list(getattr(agent, "capabilities", [])),
                cycles=int(agent.cycle_counter),
            )
        )
    return nodes


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _STATE
    boot_security = ensure_admin_key_on_boot()
    app.state.admin_security = boot_security
    if boot_security.get("generated"):
        # Ephemeral key printed once for operator (not in response bodies)
        print(
            "[FCC SECURITY] Generated ephemeral FCC_ADMIN_KEY="
            f"{boot_security.get('key')} — set FCC_ADMIN_KEY in production"
        )
    _STATE = EngineState()
    if _STATE.restore_report.get("restored"):
        print("[FCC STATE] Re-hydrated engine from disk: " f"{_STATE.restore_report}")
    else:
        print("[FCC STATE] Fresh engine (no prior state): " f"{_STATE.restore_report}")
    yield
    # Final flush before shutdown
    try:
        if _STATE is not None:
            _STATE.system.persist_state()
    except Exception as exc:  # noqa: BLE001
        print(f"[FCC STATE] shutdown flush failed: {exc}")
    _STATE = None


def create_app() -> FastAPI:
    """Production FastAPI app factory."""
    app = FastAPI(
        title="FlowChartCharter Engine API",
        description=(
            "Execution-first multi-agent nervous system (v1.7 Hybrid). "
            "Submit workloads, hybrid-route GraphRAG sub-flows under CFO caps, "
            "load Charterfile YAML playbooks, query roster TPC, trigger Monday "
            "Sync and Analytics Chief."
        ),
        version=ENGINE_VERSION,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.environ.get("FCC_CORS_ORIGINS", "*").split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={
                "error": type(exc).__name__,
                "detail": str(exc),
                "path": str(request.url.path),
            },
        )

    @app.get("/health", response_model=HealthResponse, tags=["ops"])
    async def health() -> HealthResponse:
        st = get_state()
        return HealthResponse(
            status="ok",
            engine="FlowChartCharterSystem",
            version=ENGINE_VERSION,
            uptime_s=round(st.uptime_s, 3),
            days_ready=st.system.analytics.days_ready(),
            roster_size=len(st.system.roster),
        )

    @app.get("/system/harness", tags=["system"])
    async def harness_status(
        _auth: str = Depends(require_admin_key),
    ) -> Dict[str, Any]:
        st = get_state()
        h = getattr(st.system, "harness", None)
        if h is None:
            return {"ok": False, "reason": "no_harness"}
        snap = h.snapshot()
        snap["version"] = ENGINE_VERSION
        return snap

    @app.post("/system/harness/halt", tags=["system"])
    async def harness_halt(
        _auth: str = Depends(require_admin_key),
    ) -> Dict[str, Any]:
        st = get_state()
        h = getattr(st.system, "harness", None)
        if h is None:
            return {"ok": False, "reason": "no_harness"}
        h.halt("api")
        return {"ok": True, **h.snapshot()}

    @app.post("/system/harness/arm", tags=["system"])
    async def harness_arm(
        _auth: str = Depends(require_admin_key),
    ) -> Dict[str, Any]:
        st = get_state()
        h = getattr(st.system, "harness", None)
        if h is None:
            return {"ok": False, "reason": "no_harness"}
        h.arm()
        return {"ok": True, **h.snapshot()}

    @app.get("/", tags=["ops"])
    async def root() -> Dict[str, Any]:
        return {
            "service": "FlowChartCharter Engine",
            "version": ENGINE_VERSION,
            "hybrid": "v1.7",
            "docs": "/docs",
            "endpoints": [
                "POST /workload/submit",
                "POST /hybrid/route",
                "POST /hybrid/workload",
                "GET /hybrid/stats",
                "POST /swarm/run",
                "POST /system/headhunter/requisition",
                "GET /system/v18/stats",
                "POST /action/execute",
                "GET /action/security-audit",
                "POST /system/synthesize-charter",
                "POST /system/approve-charter",
                "POST /system/reject-charter",
                "GET /system/pending-charters",
                "GET /system/tenants",
                "POST /system/tenant",
                "GET /system/llm/providers",
                "POST /system/llm/golden-eval",
                "GET /roster/status",
                "POST /system/trigger-monday-sync",
                "POST /system/advance-analytics",
                "POST /system/end-of-week",
                "POST /system/upgrade-personnel",
                "POST /system/load-playbook",
                "POST /system/execute-compiled",
                "GET /system/playbook",
                "GET /health",
                "GET /metrics",
                "GET /library",
                "GET /ui/",
            ],
        }

    @app.post(
        "/workload/submit",
        response_model=WorkloadSubmitResponse,
        tags=["workload"],
    )
    async def submit_workload(body: WorkloadSubmitRequest) -> WorkloadSubmitResponse:
        """Route a JSON workload to the Boss Agent for charter execution."""
        st = get_state()
        st.request_count += 1
        request_id = f"REQ-{uuid.uuid4().hex[:10].upper()}"
        t0 = time.perf_counter()

        try:
            result = await asyncio.to_thread(
                st.system.execute_charter,
                body.workload,
                context_entropy=body.context_entropy,
                payload=body.payload or {"task": body.workload},
                force_capability=body.force_capability,
                force_zero_shot=body.force_zero_shot,
                force_quality=body.force_quality,
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=400,
                detail=f"Charter execution failed: {exc}",
            ) from exc

        elapsed = (time.perf_counter() - t0) * 1000.0
        hub = get_metrics_hub()
        hub.sync_from_system(st.system)
        hub.observe_workload(
            quality=float(result.get("quality", 0.0)),
            trust=bool(result.get("trust", False)),
            token_delta=int(result.get("token_spend", 0) or 0),
            playbook_id=str(getattr(st.system, "active_playbook_id", None) or "default_charter"),
            latency_s=elapsed / 1000.0,
            endpoint="workload_submit",
        )
        risks = [
            float(a.termination_risk_index)
            for a in st.system.roster
            if not isinstance(a, BossAgent) and a.history
        ]
        return WorkloadSubmitResponse(
            request_id=request_id,
            workload=str(result.get("workload", body.workload)),
            quality=float(result.get("quality", 0.0)),
            trust=bool(result.get("trust", False)),
            playbook_mode=result.get("playbook_mode"),
            context_entropy=float(result.get("context_entropy", 0.0)),
            token_spend=int(result.get("token_spend", 0)),
            muscle_memory_hit=bool(result.get("muscle_memory_hit", False)),
            ascension=result.get("ascension"),
            phantom_spawned=result.get("phantom_spawned"),
            remediation_loops=int(result.get("remediation_loops", 0)),
            flow_path_reused=result.get("flow_path_reused"),
            analytics=result.get("analytics"),
            live_wire=bool(result.get("live_wire", True)),
            llm_provider=str(result.get("llm_provider") or "mock"),
            entanglement_mean=(round(sum(risks) / len(risks), 4) if risks else 0.0),
            elapsed_ms=round(elapsed, 2),
        )

    # ── v1.7 Hybrid Knowledge Expansion ─────────────────────────────────

    @app.post("/hybrid/route", tags=["hybrid"])
    async def hybrid_route(body: HybridRouteRequest) -> Dict[str, Any]:
        """Classify workload into SIMPLE | MULTI_HOP | GLOBAL (no execution)."""
        st = get_state()
        st.hybrid_request_count += 1
        decision = await asyncio.to_thread(
            st.system.boss.route_workload,
            body.workload,
            hint=body.hint,
            metadata=body.metadata,
        )
        return {
            "version": ENGINE_VERSION,
            "route": decision.to_dict(),
            "lane": decision.lane.value,
        }

    @app.post("/hybrid/workload", tags=["hybrid"])
    async def hybrid_workload(body: HybridWorkloadRequest) -> Dict[str, Any]:
        """Full Hybrid GM entry: classify → execute lane under CFO ceiling."""
        st = get_state()
        st.hybrid_request_count += 1
        st.request_count += 1
        t0 = time.perf_counter()

        if body.cfo_ceiling is not None:
            st.system.boss.cfo_ceiling = int(body.cfo_ceiling)
            st.system.boss._hybrid_router = None  # noqa: SLF001 — re-init budgets

        try:
            envelope = await asyncio.to_thread(
                st.system.boss.handle_workload,
                body.workload,
                hint=body.hint,
                metadata=body.metadata,
                seed_entity=body.seed_entity,
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=400,
                detail=f"Hybrid workload failed: {exc}",
            ) from exc

        elapsed = (time.perf_counter() - t0) * 1000.0
        return {
            "request_id": f"HYB-{uuid.uuid4().hex[:10].upper()}",
            "elapsed_ms": round(elapsed, 2),
            **envelope,
        }

    @app.get("/hybrid/stats", tags=["hybrid"])
    async def hybrid_stats() -> Dict[str, Any]:
        """Router / MultiHop / Synthesis squad telemetry."""
        st = get_state()
        stats = st.system.boss.hybrid_stats()
        return {
            "version": ENGINE_VERSION,
            "hybrid_requests": st.hybrid_request_count,
            **stats,
        }

    # ── v1.8 Autonomous Scaling Horizon ─────────────────────────────────

    @app.post("/swarm/run", tags=["swarm"])
    async def swarm_run(body: SwarmRunRequest) -> Dict[str, Any]:
        """Parallel SwarmManager over dataset; single post-persist (no races)."""
        st = get_state()
        st.request_count += 1
        t0 = time.perf_counter()
        try:
            if (body.mode or "thread").lower() == "asyncio":
                report = await st.system.run_swarm_async(
                    body.items,
                    max_workers=body.max_workers,
                    cfo_ceiling=body.cfo_ceiling,
                )
            else:
                report = await asyncio.to_thread(
                    st.system.run_swarm,
                    body.items,
                    max_workers=body.max_workers,
                    cfo_ceiling=body.cfo_ceiling,
                )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=400,
                detail=f"Swarm failed: {exc}",
            ) from exc
        elapsed = (time.perf_counter() - t0) * 1000.0
        return {
            "request_id": f"SW-{uuid.uuid4().hex[:10].upper()}",
            "elapsed_ms": round(elapsed, 2),
            "version": ENGINE_VERSION,
            **report,
        }

    @app.post("/system/headhunter/requisition", tags=["system"])
    async def headhunter_requisition(
        body: HeadhunterRequest,
        _auth: str = Depends(require_admin_key),
    ) -> Dict[str, Any]:
        """Force Headhunter pipeline (sandbox → roster)."""
        st = get_state()
        decision = await asyncio.to_thread(
            st.system.requisition_new_talent,
            fired_name=body.fired_name,
            force=body.force,
            force_capability=body.force_capability,
        )
        return {"version": ENGINE_VERSION, **decision}

    @app.get("/system/v18/stats", tags=["system"])
    async def v18_stats() -> Dict[str, Any]:
        st = get_state()
        return st.system.v18_stats()

    @app.post("/action/execute", tags=["action"])
    async def action_execute(body: ActionExecuteRequest) -> Dict[str, Any]:
        """Execute ActionUnit with schema gate + secret-safe telemetry (v2.0)."""
        from .action_units import create_action_unit, security_audit_action_result
        from .agents import BossAgent

        st = get_state()
        st.request_count += 1
        try:
            unit = create_action_unit(body.action)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        cfg = dict(body.config or {})
        if body.dry_run is not None:
            # Record intent only. Playpen still forces dry-run.
            cfg["requested_dry_run"] = body.dry_run
        agent = None
        if body.agent_name:
            for a in st.system.roster:
                if a.name == body.agent_name or a.id == body.agent_name:
                    agent = a
                    break
        if agent is None:
            agent = next(
                (
                    a
                    for a in st.system.roster
                    if not isinstance(a, BossAgent)
                ),
                None,
            )
        harness = getattr(st.system, "harness", None)
        if harness is not None:
            out = await asyncio.to_thread(
                harness.run_action,
                body.action,
                agent,
                body.payload,
                unit_id=body.action,
                config=cfg,
            )
            raw_action = out.get("action")
            action_tel = raw_action if isinstance(raw_action, dict) else out
            return {
                "version": ENGINE_VERSION,
                "action": action_tel,
                "status": out.get("status"),
                "kill_state": out.get("kill_state"),
                "halted": out.get("status") == "HALTED",
                "security_audit": (
                    security_audit_action_result(unit.last_result)
                    if getattr(unit, "last_result", None)
                    else {"passed": out.get("status") != "HALTED"}
                ),
                "agent": getattr(agent, "name", None),
                "entanglement_errors": getattr(agent, "entanglement_errors", 0),
            }
        result = await asyncio.to_thread(
            unit.execute, body.payload, agent=agent, config=cfg
        )
        audit = security_audit_action_result(result)
        return {
            "version": ENGINE_VERSION,
            "action": result.to_telemetry(),
            "security_audit": audit,
            "agent": getattr(agent, "name", None),
            "entanglement_errors": getattr(agent, "entanglement_errors", 0),
        }

    @app.get("/action/security-audit", tags=["action"])
    async def action_security_audit_probe() -> Dict[str, Any]:
        """Run static security probe: schema fail + redaction guarantees."""
        from .action_units import (
            ActionUnit_GitHubPR,
            ActionUnit_SlackWebhook,
            security_audit_action_result,
        )
        from .agents import Agent

        probe_agent = Agent("Audit-Probe", "Security Auditor")
        slack = ActionUnit_SlackWebhook(dry_run=True)
        bad = slack.execute({"text": ""}, agent=probe_agent)
        good = slack.execute({"text": "probe ok"}, agent=probe_agent)
        gh = ActionUnit_GitHubPR(dry_run=True)
        gh_bad = gh.execute(
            {
                "owner": "o",
                "repo": "r",
                "title": "t",
                "head": "h",
                "base": "main",
                "diff": "ghp_abcdefghijklmnopqrstuvwxyz12 secret",
            },
            agent=probe_agent,
        )
        audits = [
            security_audit_action_result(bad),
            security_audit_action_result(good),
            security_audit_action_result(gh_bad),
        ]
        return {
            "version": ENGINE_VERSION,
            "passed": all(a["passed"] for a in audits),
            "audits": audits,
            "entanglement_errors": probe_agent.entanglement_errors,
            "notes": [
                "Schema failures block HTTP and apply Fear penalty",
                "Telemetry redacts tokens/webhooks",
            ],
        }

    @app.get(
        "/roster/status",
        response_model=RosterStatusResponse,
        tags=["roster"],
    )
    async def roster_status() -> RosterStatusResponse:
        """Corporate roster with fitness and termination_risk_index (TPC)."""
        st = get_state()
        system = st.system
        nodes = _roster_nodes(system)
        active = sum(
            1
            for a in system.roster
            if not isinstance(a, BossAgent)
            and a.status in (AgentStatus.ACTIVE, AgentStatus.PROMOTED, AgentStatus.PHANTOM)
            and system._is_ops(a)
        )
        return RosterStatusResponse(
            roster=nodes,
            boss={
                "name": system.boss.name,
                "role": system.boss.role,
                "acknowledged": system.boss.acknowledged,
                "last_dossier_id": system.boss.last_dossier_id,
                "playbook_tail": system.boss.playbook[-12:],
            },
            active_ops=active,
            token_spend=system.token_spend,
            token_budget=system.token_budget,
            muscle_memory_records=len(system.muscle_db.storage),
            living_playbook_records=len(system.playbook.records),
            analytics=system.analytics.export(),
            engine_version=ENGINE_VERSION,
        )

    @app.post(
        "/system/trigger-monday-sync",
        response_model=MondaySyncResponse,
        tags=["system"],
    )
    async def trigger_monday_sync(
        _auth: str = Depends(require_admin_key),
    ) -> MondaySyncResponse:
        """Force GM Monday Morning Sync (closes analytics day + optional EOW)."""
        st = get_state()
        result = await asyncio.to_thread(st.system.downtime_sync)
        return MondaySyncResponse(
            outcomes=dict(result.get("outcomes") or {}),
            dossier_driven=bool(result.get("dossier_driven")),
            dossier=result.get("dossier"),
            lean_rehire=list(result.get("lean_rehire") or []),
            active_ops_after_prune=int(result.get("active_ops_after_prune") or 0),
            ascension=bool(result.get("ascension")),
            analytics=result.get("analytics") or st.system.analytics.export(),
        )

    @app.post(
        "/system/advance-analytics",
        response_model=AdvanceAnalyticsResponse,
        tags=["system"],
    )
    async def advance_analytics(
        run_eow_if_ready: bool = Query(
            True,
            description=("If workweek complete, run end-of-week audit + dossier sync"),
        ),
        _auth: str = Depends(require_admin_key),
    ) -> AdvanceAnalyticsResponse:
        """Advance Analytics Chief by one day; optionally run 5-day audit."""
        st = get_state()
        day = await asyncio.to_thread(st.system.advance_analytics_day)
        dossier_data: Optional[Dict[str, Any]] = None
        outcomes: Optional[Dict[str, str]] = None
        dossier_driven = False

        if run_eow_if_ready and st.system.analytics.workweek_complete():
            eow = await asyncio.to_thread(st.system.run_end_of_week_protocol, force=False)
            dossier_data = eow.get("dossier")
            outcomes = eow.get("outcomes")
            dossier_driven = bool(eow.get("dossier_driven"))

        return AdvanceAnalyticsResponse(
            day_closed=day,
            days_ready=st.system.analytics.days_ready(),
            workweek_complete=st.system.analytics.workweek_complete(),
            dossier=dossier_data,
            outcomes=outcomes,
            dossier_driven=dossier_driven,
            analytics=st.system.analytics.export(),
        )

    @app.post(
        "/system/end-of-week",
        response_model=AdvanceAnalyticsResponse,
        tags=["system"],
    )
    async def end_of_week(
        force: bool = Query(True, description="Pad days and force EOW audit"),
        _auth: str = Depends(require_admin_key),
    ) -> AdvanceAnalyticsResponse:
        """Explicit Analytics Chief end-of-week protocol."""
        st = get_state()
        eow = await asyncio.to_thread(st.system.run_end_of_week_protocol, force=force)
        return AdvanceAnalyticsResponse(
            day_closed=st.system.analytics.day_counter - 1,
            days_ready=st.system.analytics.days_ready(),
            workweek_complete=st.system.analytics.workweek_complete(),
            dossier=eow.get("dossier"),
            outcomes=eow.get("outcomes"),
            dossier_driven=bool(eow.get("dossier_driven")),
            analytics=eow.get("analytics") or st.system.analytics.export(),
        )

    @app.post(
        "/system/load-playbook",
        response_model=LoadPlaybookResponse,
        tags=["system"],
    )
    async def load_playbook(
        file: UploadFile = File(..., description="Charterfile YAML"),
        _auth: str = Depends(require_admin_key),
    ) -> LoadPlaybookResponse:
        """Upload Charterfile.yaml → compile → hydrate GM/roster/CFO."""
        st = get_state()
        raw = await file.read()
        if not raw:
            raise HTTPException(status_code=400, detail="Empty playbook file")
        try:
            meta = await asyncio.to_thread(
                st.system.load_playbook, raw, source_path=file.filename or ""
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=400,
                detail=f"Playbook compile failed: {exc}",
            ) from exc
        try:
            st.system.persist_state()
        except Exception:
            pass
        return LoadPlaybookResponse(
            playbook_id=str(meta["playbook_id"]),
            playbook_name=str(meta["playbook_name"]),
            version=str(meta["version"]),
            ops_roster=list(meta["ops_roster"]),
            token_budget=int(meta["token_budget"]),
            flow_path=list(meta["flow_path"]),
            models=list(meta["models"]),
            load_count=int(meta.get("load_count") or 0),
        )

    @app.post("/system/execute-compiled", tags=["workload"])
    async def execute_compiled(body: WorkloadSubmitRequest) -> Dict[str, Any]:
        """Execute the active compiled Charterfile against a workload."""
        st = get_state()
        if st.system.compiled_playbook is None:
            raise HTTPException(
                status_code=409,
                detail="No playbook loaded — POST /system/load-playbook first",
            )
        try:
            result = await asyncio.to_thread(
                st.system.execute_compiled,
                body.workload,
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return result

    @app.get("/system/playbook", tags=["system"])
    async def get_playbook(
        _auth: str = Depends(require_admin_key),
    ) -> Dict[str, Any]:
        st = get_state()
        return st.system.compiler.export()

    @app.post("/system/synthesize-charter", tags=["system"])
    async def synthesize_charter(
        body: SynthesizeCharterRequest,
        _auth: str = Depends(require_admin_key),
    ) -> Dict[str, Any]:
        """v2.1 — Boss synthesizes YAML from Muscle-Memory; pending approval."""
        st = get_state()
        try:
            result = await asyncio.to_thread(
                st.system.synthesize_charter,
                body.goal,
                coach_ceiling=body.coach_ceiling,
                playbook_name=body.playbook_name,
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return result

    @app.post("/system/approve-charter", tags=["system"])
    async def approve_charter(
        body: ApproveCharterRequest,
        _auth: str = Depends(require_admin_key),
    ) -> Dict[str, Any]:
        """v2.1 — Head Coach 1-click approval (loads playbook; optional execute)."""
        st = get_state()
        try:
            result = await asyncio.to_thread(
                st.system.approve_charter,
                body.draft_id,
                approved_by=body.approved_by,
                execute_workload=body.execute_workload,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        try:
            st.system.persist_state()
        except Exception:
            pass
        return result

    @app.post("/system/reject-charter", tags=["system"])
    async def reject_charter(
        body: RejectCharterRequest,
        _auth: str = Depends(require_admin_key),
    ) -> Dict[str, Any]:
        st = get_state()
        try:
            return await asyncio.to_thread(
                st.system.reject_charter,
                body.draft_id,
                reason=body.reason,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/system/pending-charters", tags=["system"])
    async def pending_charters(
        _auth: str = Depends(require_admin_key),
    ) -> Dict[str, Any]:
        st = get_state()
        return st.system.list_pending_charters()

    @app.get("/system/tenants", tags=["system"])
    async def list_tenants(
        _auth: str = Depends(require_admin_key),
    ) -> Dict[str, Any]:
        """v2.2 multi-tenant registry snapshot."""
        from .tenant import get_tenant_registry

        st = get_state()
        reg = get_tenant_registry()
        return {
            "version": ENGINE_VERSION,
            "active_tenant": getattr(st.system, "tenant_id", "default"),
            "tenants": reg.list_tenants(),
        }

    @app.post("/system/tenant", tags=["system"])
    async def ensure_tenant(
        body: TenantEnsureRequest,
        _auth: str = Depends(require_admin_key),
    ) -> Dict[str, Any]:
        from .tenant import get_tenant_registry

        st = get_state()
        reg = get_tenant_registry()
        eng = reg.get_or_create(body.tenant_id, cfo_ceiling=body.cfo_ceiling)
        # Optionally switch live system tenant context
        st.system.tenant_id = eng.tenant_id
        st.system.tenant = eng
        return {"version": ENGINE_VERSION, "tenant": eng.stats()}

    @app.get("/system/llm/providers", tags=["system"])
    async def llm_providers(
        _auth: str = Depends(require_admin_key),
    ) -> Dict[str, Any]:
        from .llm_providers import active_provider_name, list_providers

        return {
            "version": ENGINE_VERSION,
            "active": active_provider_name(),
            "providers": [
                {
                    "name": p.name,
                    "live": p.live,
                    "available": getattr(p, "available", True),
                    "env_key": p.env_key,
                    "key_env_used": getattr(p, "key_env_used", ""),
                    "model": p.model,
                }
                for p in list_providers()
            ],
        }

    @app.post("/system/llm/golden-eval", tags=["system"])
    async def llm_golden_eval(
        _auth: str = Depends(require_admin_key),
    ) -> Dict[str, Any]:
        """Run golden-task structured-output suite (mock-safe)."""
        from .llm_providers import run_golden_evals

        st = get_state()
        return await asyncio.to_thread(
            run_golden_evals,
            client=getattr(st.system, "llm_client", None),
        )

    @app.post("/system/llm/live-golden", tags=["system"])
    async def llm_live_golden(
        _auth: str = Depends(require_admin_key),
    ) -> Dict[str, Any]:
        """Gate 2: live goldens under CFO ceiling. Honest if Port is not live."""
        from .live_golden import run_live_goldens

        st = get_state()
        return await asyncio.to_thread(
            run_live_goldens,
            cfo_ceiling=min(2500, int(getattr(st.system, "token_budget", 2500))),
            client=getattr(st.system, "llm_client", None),
        )

    @app.post("/system/upgrade-personnel", tags=["system"])
    async def upgrade_personnel(
        body: PersonnelUpgradeRequest,
        _auth: str = Depends(require_admin_key),
    ) -> Dict[str, Any]:
        """Cross-generational Living Playbook remap (e.g. 70B → 1T)."""
        st = get_state()
        return st.system.upgrade_personnel(body.model_class)

    @app.get("/system/export", tags=["system"])
    async def system_export(
        _auth: str = Depends(require_admin_key),
    ) -> Dict[str, Any]:
        """Debug export: analytics + playbook + muscle stats."""
        st = get_state()
        return {
            "analytics": st.system.analytics.export(),
            "living_playbook": {
                "records": len(st.system.playbook.records),
                "horizon": st.system.playbook.horizon_reached,
                "model_class": st.system.playbook.model_class,
                "iteration": st.system.playbook.evolution_iteration,
            },
            "compiled_playbook": st.system.compiler.export(),
            "muscle_db": st.system.muscle_db.stats(),
            "hybrid": st.system.boss.hybrid_stats(),
            "requests": st.request_count,
            "hybrid_requests": st.hybrid_request_count,
            "uptime_s": round(st.uptime_s, 3),
            "version": ENGINE_VERSION,
            "state_persistence": {
                "path": str(get_persister().path),
                "restore": st.restore_report,
                "saves": get_persister().save_count,
            },
        }

    @app.get("/metrics", tags=["ops"])
    async def prometheus_metrics() -> Response:
        """Prometheus scrape endpoint — CPU-only, non-blocking."""
        st = get_state()
        hub = get_metrics_hub()
        # snapshot gauges (no I/O, no LLM)
        hub.sync_from_system(st.system)
        return Response(content=hub.export(), media_type=hub.content_type)

    @app.get("/library", tags=["library"])
    async def list_library() -> Dict[str, Any]:
        lib = _library_dir()
        files = sorted(lib.glob("*.yaml")) + sorted(lib.glob("*.yml"))
        return {
            "path": str(lib),
            "playbooks": [f.name for f in files if f.is_file()],
        }

    @app.get("/library/{name}", tags=["library"])
    async def get_library_playbook(name: str) -> FileResponse:
        """Serve a production Charterfile from the enterprise library."""
        if "/" in name or ".." in name or not name.endswith((".yaml", ".yml")):
            raise HTTPException(status_code=400, detail="invalid playbook name")
        path = _library_dir() / name
        if not path.is_file():
            raise HTTPException(status_code=404, detail="playbook not found")
        return FileResponse(
            path,
            media_type="application/yaml",
            filename=name,
        )

    # Dashboard static (html=True) under /ui — API routes registered first
    dash = _dashboard_dir()
    if dash.is_dir():
        index = dash / "index.html"

        @app.get("/sandbox", include_in_schema=False)
        @app.get("/app", include_in_schema=False)
        async def sandbox_index():
            if index.is_file():
                return FileResponse(index)
            raise HTTPException(status_code=404, detail="dashboard missing")

        app.mount(
            "/ui",
            StaticFiles(directory=str(dash), html=True),
            name="dashboard",
        )

    return app


app = create_app()


def main() -> None:
    """CLI entry: uvicorn on 0.0.0.0:8090 (or FCC_PORT)."""
    import uvicorn

    host = os.environ.get("FCC_HOST", "0.0.0.0")
    port = int(os.environ.get("FCC_PORT", "8090"))
    uvicorn.run(
        "flowchartcharter.api_server:app",
        host=host,
        port=port,
        reload=os.environ.get("FCC_RELOAD", "0") == "1",
        log_level=os.environ.get("FCC_LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()
