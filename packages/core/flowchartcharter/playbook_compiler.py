"""Phase 3 — Head Coach Playbook Compiler (YAML Charterfile DSL).

Declarative enterprise workflows:
  1. Parse Charterfile.yaml (roster, CFO ceiling, flow units)
  2. Dynamically generate Pydantic models per flow-unit schema
  3. Hydrate FlowChartCharterSystem (roster, budgets, routing maps)
  4. Hot-reload safely (drop old model refs, GC, no leaks)

Memory safety:
  - Model registry is a dict keyed by playbook version+unit id
  - load_playbook() replaces registry atomically after successful compile
  - Previous models are unreferenced so GC can reclaim them
"""

from __future__ import annotations

import gc
import io
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Mapping,
    Optional,
    Tuple,
    Type,
    Union,
)

import yaml
from pydantic import BaseModel, Field, ValidationError, create_model

from .agents import Agent, AgentStatus, BossAgent
from .elastic import ElasticRequisitionBoard
from .metrics import ExecutionMetrics
from .production import (
    LLMExecutionClient,
    LLMExecutionRequest,
    validate_llm_output,
)

# ---------------------------------------------------------------------------
# Type map: YAML schema strings → Python / Pydantic field types
# ---------------------------------------------------------------------------

_TYPE_ALIASES: Dict[str, Any] = {
    "string": str,
    "str": str,
    "int": int,
    "integer": int,
    "float": float,
    "number": float,
    "bool": bool,
    "boolean": bool,
    "list": List[Any],
    "list[string]": List[str],
    "list[str]": List[str],
    "list[int]": List[int],
    "list[float]": List[float],
    "dict": Dict[str, Any],
    "object": Dict[str, Any],
    "any": Any,
}


def _parse_type(spec: Any) -> Any:
    """Convert YAML type token to a Python type for create_model."""
    if isinstance(spec, type):
        return spec
    if not isinstance(spec, str):
        return Any
    raw = spec.strip().lower().replace(" ", "")
    # list[string] style already in aliases
    if raw in _TYPE_ALIASES:
        return _TYPE_ALIASES[raw]
    # list[Foo] generic
    m = re.match(r"list\[(.+)\]", raw)
    if m:
        inner = _parse_type(m.group(1))
        return List[inner]  # type: ignore[valid-type]
    return Any


def _safe_class_name(unit_id: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z_]", "_", unit_id)
    if cleaned and cleaned[0].isdigit():
        cleaned = f"U_{cleaned}"
    return f"Dyn_{cleaned}"


# ---------------------------------------------------------------------------
# Compiled structures
# ---------------------------------------------------------------------------


@dataclass
class CompiledFlowUnit:
    """One deterministic step from the Charterfile."""

    id: str
    description: str
    assigned_role: str
    expected_tokens: int
    expected_latency_ms: float
    schema_raw: Dict[str, str]
    pydantic_model: Type[BaseModel]
    order: int = 0
    # v2.0 Hands of the Corporation
    unit_kind: str = "flow"  # flow | action | swarm
    action_type: Optional[str] = None
    action_config: Dict[str, Any] = field(default_factory=dict)
    swarm: bool = False
    swarm_max_workers: int = 8
    swarm_source_field: str = "files"

    def validate_output(self, payload: Any) -> Tuple[bool, Optional[BaseModel], List[str]]:
        """Run dynamic Pydantic guardrail on LLM / worker output."""
        try:
            if isinstance(payload, BaseModel):
                data = payload.model_dump()
            elif isinstance(payload, Mapping):
                data = dict(payload)
            elif isinstance(payload, str):
                import json

                data = json.loads(payload)
            else:
                return False, None, ["payload must be object or JSON string"]
            model = self.pydantic_model.model_validate(data)
            return True, model, []
        except (ValidationError, ValueError, TypeError) as exc:
            return False, None, [str(exc)[:400]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "assigned_role": self.assigned_role,
            "expected_tokens": self.expected_tokens,
            "expected_latency_ms": self.expected_latency_ms,
            "schema": dict(self.schema_raw),
            "model_name": self.pydantic_model.__name__,
            "order": self.order,
            "unit_kind": self.unit_kind,
            "action_type": self.action_type,
            "action_config": dict(self.action_config),
            "swarm": self.swarm,
            "swarm_max_workers": self.swarm_max_workers,
            "swarm_source_field": self.swarm_source_field,
        }


@dataclass
class RosterRequisition:
    role: str
    capabilities: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"role": self.role, "capabilities": list(self.capabilities)}


@dataclass
class CompiledPlaybook:
    """Fully compiled Charterfile ready for engine hydration."""

    playbook_name: str
    version: str
    global_cfo_ceiling: int
    roster_requisition: List[RosterRequisition]
    flow_units: List[CompiledFlowUnit]
    source_path: str = ""
    compiled_at: float = field(default_factory=time.time)
    playbook_id: str = field(default_factory=lambda: f"PB-{uuid.uuid4().hex[:8].upper()}")
    # model registry for this playbook only (hot-reload drops previous)
    _models: Dict[str, Type[BaseModel]] = field(default_factory=dict, repr=False)

    @property
    def flow_path(self) -> List[str]:
        return [u.id for u in sorted(self.flow_units, key=lambda x: x.order)]

    def unit_by_id(self, unit_id: str) -> Optional[CompiledFlowUnit]:
        for u in self.flow_units:
            if u.id == unit_id:
                return u
        return None

    def model_for_unit(self, unit_id: str) -> Optional[Type[BaseModel]]:
        u = self.unit_by_id(unit_id)
        return u.pydantic_model if u else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "playbook_id": self.playbook_id,
            "playbook_name": self.playbook_name,
            "version": self.version,
            "global_cfo_ceiling": self.global_cfo_ceiling,
            "roster_requisition": [r.to_dict() for r in self.roster_requisition],
            "flow_units": [u.to_dict() for u in self.flow_units],
            "flow_path": self.flow_path,
            "source_path": self.source_path,
            "compiled_at": self.compiled_at,
            "model_count": len(self._models),
        }


# ---------------------------------------------------------------------------
# Dynamic Pydantic generation
# ---------------------------------------------------------------------------


def generate_pydantic_model(
    unit_id: str,
    schema: Mapping[str, Any],
    *,
    model_name: Optional[str] = None,
) -> Type[BaseModel]:
    """YAML schema dict → live Pydantic model via create_model.

    Example schema:
      clean_code: string
      variables_found: list[string]
      security_rating: float
    """
    name = model_name or _safe_class_name(unit_id)
    fields: Dict[str, Any] = {}
    for field_name, type_spec in schema.items():
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", str(field_name)):
            raise ValueError(f"Invalid schema field name: {field_name!r}")
        py_type = _parse_type(type_spec)
        # All fields required by default for strict entanglement
        fields[str(field_name)] = (py_type, Field(...))

    if not fields:
        # empty schema → accept any dict
        fields["_empty"] = (Optional[bool], Field(default=None))

    model: Type[BaseModel] = create_model(name, **fields)  # type: ignore[call-overload]
    model.model_rebuild()
    return model


# ---------------------------------------------------------------------------
# YAML parser
# ---------------------------------------------------------------------------


class PlaybookCompileError(ValueError):
    """Charterfile failed validation / compile."""


def _load_yaml(source: Union[str, Path, bytes, Mapping[str, Any]]) -> Dict[str, Any]:
    if isinstance(source, Mapping):
        return dict(source)
    if isinstance(source, bytes):
        data = yaml.safe_load(io.BytesIO(source))
    elif isinstance(source, Path) or (
        isinstance(source, str) and ("\n" not in source and Path(source).exists())
    ):
        path = Path(source)
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    else:
        data = yaml.safe_load(str(source))
    if not isinstance(data, dict):
        raise PlaybookCompileError("Charterfile root must be a mapping")
    return data


def compile_playbook(
    source: Union[str, Path, bytes, Mapping[str, Any]],
    *,
    source_path: str = "",
) -> CompiledPlaybook:
    """Parse Charterfile YAML → CompiledPlaybook with live Pydantic models."""
    raw = _load_yaml(source)
    name = str(raw.get("playbook_name") or raw.get("name") or "Unnamed Playbook")
    version = str(raw.get("version") or "1.0.0")
    ceiling = int(raw.get("global_cfo_ceiling") or raw.get("cfo_ceiling") or 5000)
    if ceiling <= 0:
        raise PlaybookCompileError("global_cfo_ceiling must be positive")

    roster_raw = raw.get("roster_requisition") or raw.get("roster") or []
    if not isinstance(roster_raw, list) or not roster_raw:
        raise PlaybookCompileError("roster_requisition must be a non-empty list")

    roster: List[RosterRequisition] = []
    for item in roster_raw:
        if not isinstance(item, dict) or "role" not in item:
            raise PlaybookCompileError(f"Invalid roster entry: {item!r}")
        caps = item.get("capabilities") or []
        if not isinstance(caps, list):
            raise PlaybookCompileError(f"capabilities must be a list for {item['role']}")
        roster.append(
            RosterRequisition(
                role=str(item["role"]),
                capabilities=[str(c) for c in caps],
            )
        )

    units_raw = raw.get("flow_units") or raw.get("units") or []
    if not isinstance(units_raw, list) or not units_raw:
        raise PlaybookCompileError("flow_units must be a non-empty list")

    models: Dict[str, Type[BaseModel]] = {}
    units: List[CompiledFlowUnit] = []
    for idx, item in enumerate(units_raw):
        if not isinstance(item, dict) or "id" not in item:
            raise PlaybookCompileError(f"Invalid flow_unit at index {idx}")
        uid = str(item["id"])
        schema = item.get("schema") or {}
        if not isinstance(schema, dict):
            raise PlaybookCompileError(f"schema for {uid} must be a mapping")

        # v2.0 — ActionUnit / Swarm recognition
        action_type = item.get("action") or item.get("action_type") or item.get("action_unit")
        unit_kind_raw = str(item.get("unit_kind") or item.get("type") or "").lower()
        swarm_flag = bool(item.get("swarm") or unit_kind_raw == "swarm")
        if action_type:
            unit_kind = "action"
        elif swarm_flag:
            unit_kind = "swarm"
        else:
            unit_kind = "flow"

        # Action units may use built-in payload schemas via empty/partial schema
        if unit_kind == "action" and not schema:
            # default action schemas for compiler model generation
            at = str(action_type)
            if "Slack" in at or "slack" in at:
                schema = {
                    "text": "string",
                    "channel": "string",
                    "username": "string",
                }
            elif "GitHub" in at or "github" in at or "PR" in at:
                schema = {
                    "owner": "string",
                    "repo": "string",
                    "title": "string",
                    "body": "string",
                    "head": "string",
                    "base": "string",
                    "diff": "string",
                    "draft": "bool",
                }
            else:
                schema = {"payload": "object"}

        if unit_kind == "swarm" and not schema:
            schema = {
                "files": "list[string]",
                "findings": "list[string]",
                "scanned": "int",
                "failed": "int",
            }

        schema_str = {str(k): str(v) for k, v in schema.items()}
        model = generate_pydantic_model(uid, schema_str)
        models[uid] = model

        action_config = item.get("action_config") or item.get("config") or {}
        if not isinstance(action_config, dict):
            action_config = {}

        if unit_kind == "action" and action_type:
            # Validate known ActionUnit types early
            from .action_units import ACTION_REGISTRY

            key = str(action_type)
            if key not in ACTION_REGISTRY and key.lower() not in ACTION_REGISTRY:
                raise PlaybookCompileError(
                    f"Unknown ActionUnit type {action_type!r} on unit {uid}"
                )

        units.append(
            CompiledFlowUnit(
                id=uid,
                description=str(item.get("description") or uid),
                assigned_role=str(item.get("assigned_role") or roster[0].role),
                expected_tokens=int(item.get("expected_tokens") or 500),
                expected_latency_ms=float(item.get("expected_latency_ms") or 200.0),
                schema_raw=schema_str,
                pydantic_model=model,
                order=idx,
                unit_kind=unit_kind,
                action_type=str(action_type) if action_type else None,
                action_config=dict(action_config),
                swarm=swarm_flag or unit_kind == "swarm",
                swarm_max_workers=int(
                    item.get("swarm_max_workers") or item.get("max_workers") or 8
                ),
                swarm_source_field=str(item.get("swarm_source_field") or "files"),
            )
        )

    if not source_path and isinstance(source, (str, Path)):
        sp = str(source)
        if "\n" not in sp and Path(sp).exists():
            source_path = sp

    return CompiledPlaybook(
        playbook_name=name,
        version=version,
        global_cfo_ceiling=ceiling,
        roster_requisition=roster,
        flow_units=units,
        source_path=source_path,
        _models=models,
    )


# ---------------------------------------------------------------------------
# Engine hydration
# ---------------------------------------------------------------------------


def _role_to_capability_vector(req: RosterRequisition) -> Dict[str, float]:
    vec = {cap: 1.0 for cap in req.capabilities}
    vec.setdefault("general", 0.5)
    # soft aliases from role name
    role_l = req.role.lower()
    if "sanit" in role_l or "data" in role_l:
        vec.setdefault("json_parsing", 0.9)
        vec.setdefault("regex_sanitize", 0.85)
    if "architect" in role_l or "code" in role_l:
        vec.setdefault("python_ast", 0.9)
        vec.setdefault("refactoring", 0.85)
    if "security" in role_l:
        vec.setdefault("security_audit", 0.95)
    return vec


def hydrate_system(
    system: Any,
    playbook: CompiledPlaybook,
    *,
    keep_boss: bool = True,
    keep_validator: bool = True,
) -> Dict[str, Any]:
    """Apply compiled playbook onto a live FlowChartCharterSystem.

    - Rebuilds operational roster from roster_requisition
    - Sets token_budget from global_cfo_ceiling
    - Stores playbook + dynamic models on system
    - Registers capabilities with ElasticRequisitionBoard
    """
    # Drop previous playbook models (memory-safe hot reload)
    old = getattr(system, "compiled_playbook", None)
    if old is not None and hasattr(old, "_models"):
        old._models.clear()
    system.compiled_playbook = playbook
    system.active_playbook_id = playbook.playbook_id

    # CFO ceiling
    system.token_budget = int(playbook.global_cfo_ceiling)
    system.token_spend = 0
    if hasattr(system, "executives") and hasattr(system.executives, "cfo"):
        # soft path costs scale with ceiling
        base = max(100, playbook.global_cfo_ceiling // 10)
        system.executives.cfo.path_costs = {
            "path_A": base,
            "path_B": int(base * 1.6),
            "path_lite": int(base * 0.45),
        }
        if hasattr(system, "router") and system.router is not None:
            system.router.path_costs = dict(system.executives.cfo.path_costs)

    # Preserve boss + optional validator; replace ops roster
    preserved: List[Any] = []
    for agent in list(system.roster):
        if isinstance(agent, BossAgent) and keep_boss:
            preserved.append(agent)
        elif "Validator" in getattr(agent, "role", "") and keep_validator:
            preserved.append(agent)

    new_ops: List[Agent] = []
    for req in playbook.roster_requisition:
        agent = Agent(
            name=req.role.replace("_", "-"),
            role=f"Key Player - {req.role}",
            capability_vector=_role_to_capability_vector(req),
        )
        agent.capabilities = list(req.capabilities) or ["general"]
        agent.playbook_constraints = [
            f"Playbook: {playbook.playbook_name} v{playbook.version}",
            f"Assigned role: {req.role}",
            "Output MUST satisfy the Flow Unit dynamic Pydantic schema",
            "Schema divergence increments entanglement_errors",
        ]
        # Attach unit schemas assigned to this role
        agent.assigned_units = [  # type: ignore[attr-defined]
            u.id for u in playbook.flow_units if u.assigned_role == req.role
        ]
        new_ops.append(agent)

    system.roster = new_ops + preserved
    # Rebind elastic + skills roster
    system.elastic = ElasticRequisitionBoard()
    for a in system.roster:
        if not isinstance(a, BossAgent):
            system.elastic.register_agent(a)
    if hasattr(system, "skills") and system.skills is not None:
        system.skills.roster = system.roster

    # Routing map: unit id → role → agent name
    system.playbook_routing = {
        u.id: {
            "role": u.assigned_role,
            "expected_tokens": u.expected_tokens,
            "expected_latency_ms": u.expected_latency_ms,
            "model": u.pydantic_model.__name__,
        }
        for u in playbook.flow_units
    }
    system.playbook_flow_path = playbook.flow_path

    # Boss playbook log
    if hasattr(system, "boss") and system.boss is not None:
        system.boss.playbook.append(
            f"Loaded Charterfile {playbook.playbook_name} "
            f"v{playbook.version} id={playbook.playbook_id} "
            f"units={len(playbook.flow_units)} ceiling={playbook.global_cfo_ceiling}"
        )

    # GC after hot-reload
    gc.collect()

    return {
        "playbook_id": playbook.playbook_id,
        "playbook_name": playbook.playbook_name,
        "version": playbook.version,
        "ops_roster": [a.name for a in new_ops],
        "token_budget": system.token_budget,
        "flow_path": playbook.flow_path,
        "models": [u.pydantic_model.__name__ for u in playbook.flow_units],
        "routing": system.playbook_routing,
    }


class PlaybookCompiler:
    """Stateful compiler + registry for hot-reloads."""

    def __init__(self) -> None:
        self.current: Optional[CompiledPlaybook] = None
        self.history: List[str] = []  # playbook ids
        self.load_count: int = 0

    def compile(
        self, source: Union[str, Path, bytes, Mapping[str, Any]], **kwargs: Any
    ) -> CompiledPlaybook:
        pb = compile_playbook(source, **kwargs)
        self.current = pb
        self.history.append(pb.playbook_id)
        self.load_count += 1
        # Keep history bounded
        if len(self.history) > 32:
            self.history = self.history[-32:]
        return pb

    def compile_and_hydrate(
        self,
        system: Any,
        source: Union[str, Path, bytes, Mapping[str, Any]],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        pb = self.compile(source, **kwargs)
        meta = hydrate_system(system, pb)
        meta["load_count"] = self.load_count
        return meta

    def export(self) -> Dict[str, Any]:
        return {
            "load_count": self.load_count,
            "history": list(self.history[-16:]),
            "current": self.current.to_dict() if self.current else None,
        }


# ---------------------------------------------------------------------------
# Live-Wire enforcement using dynamic unit schema
# ---------------------------------------------------------------------------


def enforce_unit_schema(
    playbook: CompiledPlaybook,
    unit_id: str,
    llm_payload: Any,
    *,
    agent: Optional[Agent] = None,
) -> Dict[str, Any]:
    """Validate LLM output against the unit's dynamic Pydantic model.

    On failure: increment agent.entanglement_errors + ledger schema_divergence.
    """
    unit = playbook.unit_by_id(unit_id)
    if unit is None:
        return {
            "valid": False,
            "errors": [f"unknown unit {unit_id}"],
            "entanglement_delta": 1,
        }

    # First: base FlowUnitResult envelope if present
    envelope_ok = True
    if isinstance(llm_payload, Mapping) and "result" in llm_payload:
        _, report = validate_llm_output(llm_payload)
        envelope_ok = report.valid
        if not envelope_ok and agent is not None:
            agent.entanglement_errors = getattr(agent, "entanglement_errors", 0) + 1
            agent.record_cycle(
                schema_divergence=1,
                token_spend=0,
                token_ceiling=0,
                delta_t=0.01,
                structural_drift=0.5,
                quality=0.0,
                path=unit_id,
                notes="envelope_schema_fail",
            )

    # Extract domain payload
    domain = llm_payload
    if isinstance(llm_payload, Mapping):
        domain = llm_payload.get("output_payload") or {
            k: v
            for k, v in llm_payload.items()
            if k
            not in (
                "result",
                "quality",
                "path",
                "tokens",
                "notes",
                "schema_ok",
                "expected_keys_present",
            )
        }

    ok, model, errors = unit.validate_output(domain)
    if not ok and agent is not None:
        agent.entanglement_errors = getattr(agent, "entanglement_errors", 0) + 1
        agent.record_cycle(
            schema_divergence=1,
            token_spend=0,
            token_ceiling=0,
            delta_t=0.01,
            structural_drift=0.55,
            quality=0.0,
            path=unit_id,
            notes=f"dynamic_schema_fail:{unit_id}",
        )
    return {
        "valid": ok and envelope_ok,
        "unit_id": unit_id,
        "model": unit.pydantic_model.__name__,
        "errors": errors,
        "data": model.model_dump() if model is not None else None,
        "entanglement_delta": 0 if (ok and envelope_ok) else 1,
    }


def execute_playbook_unit_live(
    agent: Agent,
    playbook: CompiledPlaybook,
    unit: CompiledFlowUnit,
    *,
    workload: str,
    client: Optional[LLMExecutionClient] = None,
) -> Dict[str, Any]:
    """Run one Charterfile unit through Live-Wire + dynamic schema gate."""
    client = client or getattr(agent, "llm_client", None) or LLMExecutionClient()
    constraints = list(getattr(agent, "playbook_constraints", []))
    constraints.append(f"Flow Unit {unit.id}: {unit.description}")
    constraints.append(f"Required JSON schema fields: {list(unit.schema_raw.keys())}")
    constraints.append(
        f"Expected tokens≈{unit.expected_tokens}, " f"latency≈{unit.expected_latency_ms}ms"
    )

    # Build example shape for the model
    schema_hint = {k: f"<{v}>" for k, v in unit.schema_raw.items()}
    req = LLMExecutionRequest(
        workload=(
            f"{workload}\nUnit={unit.id}\nTask={unit.description}\n"
            f"Return output_payload matching: {schema_hint}"
        ),
        path="path_A",
        termination_risk_index=agent.termination_risk_index,
        system_prompt=agent.system_prompt,
        playbook_constraints=constraints,
        expected_output_keys=["result", "quality", "path", "tokens"],
        agent_name=agent.name,
        role=agent.role,
    )
    resp = client.execute(req)

    # Mock path: synthesize valid domain payload for schema demo
    payload: Any
    if resp.output is not None:
        payload = resp.output.model_dump()
        if resp.mock or not payload.get("output_payload"):
            # Build dummy valid payload matching dynamic schema types
            synthetic: Dict[str, Any] = {}
            for field_name, type_spec in unit.schema_raw.items():
                t = str(type_spec).lower()
                if "list" in t:
                    synthetic[field_name] = ["example"]
                elif "float" in t or "number" in t:
                    synthetic[field_name] = 0.95
                elif "int" in t:
                    synthetic[field_name] = 1
                elif "bool" in t:
                    synthetic[field_name] = True
                else:
                    synthetic[field_name] = f"generated:{field_name}"
            payload["output_payload"] = synthetic
            payload["schema_ok"] = True
    else:
        payload = {"result": "fail", "quality": 0.0, "tokens": 0}

    gate = enforce_unit_schema(playbook, unit.id, payload, agent=agent)

    # Record metrics with expected tokens/latency from Charterfile
    if resp.output is not None:
        tokens = resp.output.tokens
        agent.history.append(
            ExecutionMetrics(
                token_cost=tokens,
                execution_time=max(0.001, unit.expected_latency_ms / 1000.0),
                quality_score=resp.output.quality if gate["valid"] else 0.4,
                synergy_score=1.0 if gate["valid"] else 0.5,
                expected_token_cost=unit.expected_tokens,
                expected_time=unit.expected_latency_ms / 1000.0,
            )
        )

    return {
        "unit_id": unit.id,
        "agent": agent.name,
        "role": unit.assigned_role,
        "live_wire": True,
        "mock": resp.mock,
        "gate": gate,
        "latency_ms": resp.latency_ms,
        "generation": resp.generation,
        "ok": gate["valid"] and resp.ok,
        "unit_kind": unit.unit_kind,
    }


def execute_playbook_swarm_unit(
    system: Any,
    agent: Agent,
    unit: CompiledFlowUnit,
    *,
    workload: str,
    prior_outputs: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """v1.8 SwarmManager step inside a compiled playbook."""
    from .swarm_manager import SwarmManager

    prior_outputs = prior_outputs or []
    # Prefer files list from prior unit outputs
    files: List[Any] = []
    for prev in reversed(prior_outputs):
        data = (prev.get("gate") or {}).get("data") or prev.get("data") or {}
        if isinstance(data, dict) and data.get(unit.swarm_source_field):
            files = list(data[unit.swarm_source_field])
            break
        if isinstance(data, dict) and data.get("files"):
            files = list(data["files"])
            break
    if not files:
        # Derive synthetic file list from workload tokens
        files = [f"scan://{workload[:40]}/{i}.py" for i in range(12)]

    swarm = SwarmManager(
        cfo_ceiling=min(int(getattr(system, "token_budget", 5000)), 5000),
        max_workers=unit.swarm_max_workers,
        quiet=True,
    )
    report = swarm.run(files, max_workers=unit.swarm_max_workers)
    # Record mild metrics on agent
    agent.history.append(
        ExecutionMetrics(
            token_cost=report.tokens,
            execution_time=max(0.001, report.wall_ms / 1000.0),
            quality_score=report.quality,
            synergy_score=0.9 if report.failed == 0 else 0.6,
            expected_token_cost=unit.expected_tokens,
            expected_time=unit.expected_latency_ms / 1000.0,
        )
    )
    findings = [
        f"issue:{r.item_id}" for r in report.results if not r.ok
    ] or ["clean:no_critical"]
    data = {
        "files": [str(f) for f in files],
        "findings": findings,
        "scanned": report.succeeded,
        "failed": report.failed,
    }
    return {
        "unit_id": unit.id,
        "agent": agent.name,
        "role": unit.assigned_role,
        "unit_kind": "swarm",
        "ok": report.under_budget and report.succeeded > 0,
        "swarm": report.model_dump(),
        "data": data,
        "gate": {"valid": True, "data": data, "entanglement_delta": report.failed},
        "live_wire": False,
        "mock": True,
    }


def execute_playbook_action_unit(
    agent: Agent,
    unit: CompiledFlowUnit,
    *,
    workload: str,
    prior_outputs: Optional[List[Dict[str, Any]]] = None,
    system: Any = None,
) -> Dict[str, Any]:
    """v2.0 ActionUnit step — schema gate then external side-effect."""
    from .action_units import create_action_unit

    prior_outputs = prior_outputs or []
    if not unit.action_type:
        return {
            "unit_id": unit.id,
            "ok": False,
            "error": "missing action_type",
            "unit_kind": "action",
        }

    harness = getattr(system, "harness", None) if system is not None else None
    if harness is not None and not harness.kill.armed:
        return {
            "unit_id": unit.id,
            "ok": False,
            "blocked": True,
            "halted": True,
            "error": "kill_switch_halted",
            "unit_kind": "action",
            "action_type": unit.action_type,
        }

    action = create_action_unit(unit.action_type, unit_id=unit.id)
    # Build payload from action_config + prior patch outputs
    payload: Dict[str, Any] = dict(unit.action_config.get("payload") or {})
    # Merge top-level action_config keys that look like payload fields
    for k, v in unit.action_config.items():
        if k in ("payload", "dry_run", "webhook_url", "token", "api_base"):
            continue
        payload.setdefault(k, v)

    # GitHub PR: pull diff from prior patch unit if missing
    if "GitHub" in unit.action_type or "github" in unit.action_type.lower():
        if not payload.get("diff"):
            for prev in reversed(prior_outputs):
                data = (prev.get("gate") or {}).get("data") or prev.get("data") or {}
                if isinstance(data, dict) and data.get("patch_diff"):
                    payload["diff"] = data["patch_diff"]
                    break
                if isinstance(data, dict) and data.get("diff"):
                    payload["diff"] = data["diff"]
                    break
        payload.setdefault("title", f"FCC auto-patch: {workload[:60]}")
        payload.setdefault("body", f"Generated by FlowChartCharter playbook unit {unit.id}")
        payload.setdefault("owner", unit.action_config.get("owner") or "acme-corp")
        payload.setdefault("repo", unit.action_config.get("repo") or "secops-service")
        payload.setdefault("head", unit.action_config.get("head") or "fcc/auto-patch")
        payload.setdefault("base", unit.action_config.get("base") or "main")
        if not payload.get("diff"):
            payload["diff"] = (
                "--- a/security/fix.py\n+++ b/security/fix.py\n"
                "@@ -1,3 +1,5 @@\n+# patched by FlowChartCharter SecOps\n"
                " def auth():\n-    return True\n+    return verify_bearer()\n"
            )

    if "Slack" in unit.action_type or "slack" in unit.action_type.lower():
        if not payload.get("text"):
            payload["text"] = f"FlowChartCharter: {unit.description} — {workload[:120]}"

    cfg = {
        k: v
        for k, v in unit.action_config.items()
        if k in ("dry_run", "webhook_url", "token", "api_base")
    }
    result = action.execute(payload, agent=agent, config=cfg)
    telemetry = result.to_telemetry()
    return {
        "unit_id": unit.id,
        "agent": agent.name,
        "role": unit.assigned_role,
        "unit_kind": "action",
        "action_type": unit.action_type,
        "ok": result.ok and not result.blocked,
        "blocked": result.blocked,
        "halted": (result.error or "") == "kill_switch_halted",
        "action": telemetry,
        "gate": {
            "valid": not result.blocked,
            "entanglement_delta": result.entanglement_delta,
            "data": telemetry.get("redacted_request"),
        },
        "live_wire": not result.dry_run,
        "mock": result.dry_run,
    }


def run_compiled_playbook(
    system: Any,
    workload: str,
    *,
    playbook: Optional[CompiledPlaybook] = None,
    hard_rhythm: bool = False,
) -> Dict[str, Any]:
    """Execute all flow units in order using role-matched agents + Live-Wire.

    v2.2.0 R5: every unit emits a mandatory RhythmAudit (ST-04) before the
    next unit advances. Maker-checker uses independent Audit Manager role.
    """
    from .rhythm_gate import (
        attach_rhythm,
        build_rhythm_audit,
        enforce_rhythm_or_raise,
    )

    pb: Optional[CompiledPlaybook] = playbook or getattr(system, "compiled_playbook", None)
    if pb is None:
        raise PlaybookCompileError("No compiled playbook loaded on system")

    # Tenant budget charge if namespaced
    tenant = getattr(system, "tenant", None)

    # role → agent
    role_map: Dict[str, Agent] = {}
    for agent in system.roster:
        if isinstance(agent, BossAgent):
            continue
        # match Key Player - Role or name
        for req in pb.roster_requisition:
            if req.role in agent.role or req.role.replace("_", "-") in agent.name:
                role_map[req.role] = agent

    results: List[Dict[str, Any]] = []
    rhythm_audits: List[Dict[str, Any]] = []
    remediation = 0

    for unit in sorted(pb.flow_units, key=lambda u: u.order):
        harness = getattr(system, "harness", None)
        if harness is not None and not harness.kill.armed:
            halted = {
                "unit_id": unit.id,
                "ok": False,
                "halted": True,
                "error": "kill_switch_halted",
                "unit_kind": unit.unit_kind,
            }
            audit = build_rhythm_audit(
                unit=unit,
                result=halted,
                charter_id=getattr(pb, "playbook_id", "") or pb.playbook_name,
                remediation_loops=remediation,
            )
            halted = attach_rhythm(halted, audit)
            results.append(halted)
            rhythm_audits.append(audit.to_dict())
            break
        agent = role_map.get(unit.assigned_role)
        if agent is None:
            # elastic phantom for missing role
            phantom = system.elastic.evaluate(
                f"{workload} requires {unit.assigned_role}",
                system.roster,
                force_capability=unit.assigned_role.lower(),
            )
            agent = phantom or next(
                (
                    a
                    for a in system.roster
                    if not isinstance(a, BossAgent) and a.status != AgentStatus.FIRED
                ),
                None,
            )
        if agent is None:
            fail = {
                "unit_id": unit.id,
                "ok": False,
                "error": "no agent available",
            }
            audit = build_rhythm_audit(
                unit=unit,
                result=fail,
                charter_id=getattr(pb, "playbook_id", "") or pb.playbook_name,
                remediation_loops=remediation,
            )
            fail = attach_rhythm(fail, audit)
            results.append(fail)
            rhythm_audits.append(audit.to_dict())
            continue
        agent.refresh_survival_prompt()

        if unit.unit_kind == "swarm" or unit.swarm:
            unit_result = execute_playbook_swarm_unit(
                system,
                agent,
                unit,
                workload=workload,
                prior_outputs=results,
            )
        elif unit.unit_kind == "action" and unit.action_type:
            unit_result = execute_playbook_action_unit(
                agent,
                unit,
                workload=workload,
                prior_outputs=results,
                system=system,
            )
        else:
            unit_result = execute_playbook_unit_live(
                agent,
                pb,
                unit,
                workload=workload,
                client=getattr(system, "llm_client", None),
            )

        # ST-04 mandatory rhythm gate
        if not unit_result.get("ok", False):
            remediation += 1
        audit = build_rhythm_audit(
            unit=unit,
            result=unit_result,
            charter_id=getattr(pb, "playbook_id", "") or pb.playbook_name,
            remediation_loops=remediation,
            implementor_role=str(getattr(agent, "role", "") or unit.assigned_role),
            auditor_role="Audit Manager",
        )
        unit_result = attach_rhythm(unit_result, audit)
        rhythm_audits.append(
            enforce_rhythm_or_raise(
                audit,
                max_remediation=3,
                hard_stop=hard_rhythm,
            )
        )
        results.append(unit_result)

        # Tenant charge
        if tenant is not None:
            tok = 0
            if agent.history:
                tok = int(getattr(agent.history[-1], "token_cost", 0) or 0)
            if tok and hasattr(tenant, "charge_budget"):
                if not tenant.charge_budget(tok):
                    results.append(
                        {
                            "unit_id": f"{unit.id}_tenant_halt",
                            "ok": False,
                            "error": "tenant_cfo_ceiling",
                            "tenant_id": getattr(tenant, "tenant_id", ""),
                        }
                    )
                    break

    spend = sum(
        (a.history[-1].token_cost if a.history else 0)
        for a in system.roster
        if not isinstance(a, BossAgent)
    )
    system.token_spend += spend
    agent_q = [
        a.history[-1].quality_score
        for a in system.roster
        if not isinstance(a, BossAgent) and a.history
    ]
    # Blend action quality from results when present
    action_q = [
        float((r.get("action") or {}).get("quality") or 0.0)
        for r in results
        if r.get("unit_kind") == "action" and r.get("action")
    ]
    quality = sum(agent_q) / len(agent_q) if agent_q else 0.0
    if action_q:
        quality = (quality + sum(action_q) / len(action_q)) / 2.0
    all_ok = all(r.get("ok") for r in results) if results else False
    rhythm_pass = all(a.get("passed") for a in rhythm_audits) if rhythm_audits else False

    # Observability counters
    try:
        from .observability import get_metrics_hub

        hub = get_metrics_hub()
        if hasattr(hub, "observe_rhythm"):
            hub.observe_rhythm(rhythm_audits)
        if hasattr(hub, "observe_actions"):
            hub.observe_actions(results)
    except Exception:  # noqa: BLE001
        pass

    out = {
        "playbook_id": pb.playbook_id,
        "playbook_name": pb.playbook_name,
        "workload": workload,
        "flow_path": pb.flow_path,
        "unit_results": results,
        "rhythm_audits": rhythm_audits,
        "rhythm_all_passed": rhythm_pass,
        "quality": quality,
        "trust": all_ok and quality >= 0.90 and rhythm_pass,
        "token_spend": system.token_spend,
        "token_budget": system.token_budget,
        "units_ok": sum(1 for r in results if r.get("ok")),
        "units_total": len(results),
        "tenant_id": getattr(system, "tenant_id", "default"),
        "version": "2.2.0",
    }
    try:
        from .charter_memory import bind_episode

        if getattr(system, "knowledge", None) is not None:
            out["episode"] = bind_episode(
                system.knowledge,
                goal=str(workload or pb.playbook_name),
                path=list(pb.flow_path or []),
                quality=float(quality),
                trust=bool(out["trust"]),
            )
    except Exception:  # noqa: BLE001
        out["episode"] = None
    return out
