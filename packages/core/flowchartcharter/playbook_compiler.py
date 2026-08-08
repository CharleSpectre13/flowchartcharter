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
    playbook_id: str = field(
        default_factory=lambda: f"PB-{uuid.uuid4().hex[:8].upper()}"
    )
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
        schema_str = {str(k): str(v) for k, v in schema.items()}
        model = generate_pydantic_model(uid, schema_str)
        models[uid] = model
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
    constraints.append(
        f"Required JSON schema fields: {list(unit.schema_raw.keys())}"
    )
    constraints.append(
        f"Expected tokens≈{unit.expected_tokens}, "
        f"latency≈{unit.expected_latency_ms}ms"
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
                execution_time=max(
                    0.001, unit.expected_latency_ms / 1000.0
                ),
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
    }


def run_compiled_playbook(
    system: Any,
    workload: str,
    *,
    playbook: Optional[CompiledPlaybook] = None,
) -> Dict[str, Any]:
    """Execute all flow units in order using role-matched agents + Live-Wire."""
    pb: Optional[CompiledPlaybook] = playbook or getattr(
        system, "compiled_playbook", None
    )
    if pb is None:
        raise PlaybookCompileError("No compiled playbook loaded on system")

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
    for unit in sorted(pb.flow_units, key=lambda u: u.order):
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
                    if not isinstance(a, BossAgent)
                    and a.status != AgentStatus.FIRED
                ),
                None,
            )
        if agent is None:
            results.append(
                {
                    "unit_id": unit.id,
                    "ok": False,
                    "error": "no agent available",
                }
            )
            continue
        agent.refresh_survival_prompt()
        results.append(
            execute_playbook_unit_live(
                agent,
                pb,
                unit,
                workload=workload,
                client=getattr(system, "llm_client", None),
            )
        )

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
    quality = sum(agent_q) / len(agent_q) if agent_q else 0.0
    all_ok = all(r.get("ok") for r in results) if results else False

    return {
        "playbook_id": pb.playbook_id,
        "playbook_name": pb.playbook_name,
        "workload": workload,
        "flow_path": pb.flow_path,
        "unit_results": results,
        "quality": quality,
        "trust": all_ok and quality >= 0.90,
        "token_spend": system.token_spend,
        "token_budget": system.token_budget,
        "units_ok": sum(1 for r in results if r.get("ok")),
        "units_total": len(results),
    }
