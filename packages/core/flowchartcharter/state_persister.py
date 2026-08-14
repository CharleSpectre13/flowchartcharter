"""State persistence — defeat ephemeral amnesia on container restart.

Serializes EngineState (roster TPC, ledgers, Analytics film room, muscle
memory, living playbook, token counters) to a local JSON file after each
workload. FastAPI lifespan re-hydrates on boot so 5-day cycles survive
Thursday night restarts.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_STATE_PATH = os.environ.get(
    "FCC_STATE_PATH",
    str(Path(os.environ.get("FCC_DATA_DIR", "data")) / "system_state.json"),
)


class StatePersister:
    """Thread-safe JSON state store for FlowChartCharterSystem."""

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = Path(path or DEFAULT_STATE_PATH)
        self._lock = threading.Lock()
        self.save_count = 0
        self.load_count = 0
        self.last_error: Optional[str] = None

    def ensure_dir(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ dump
    def dump_system(self, system: Any) -> Dict[str, Any]:
        """Build a JSON-serializable snapshot of the live engine."""
        from .agents import BossAgent

        roster_blob: List[Dict[str, Any]] = []
        for agent in system.roster:
            if isinstance(agent, BossAgent):
                roster_blob.append(
                    {
                        "kind": "boss",
                        "name": agent.name,
                        "role": agent.role,
                        "playbook": list(getattr(agent, "playbook", [])[-50:]),
                        "acknowledged": bool(getattr(agent, "acknowledged", False)),
                        "last_dossier_id": getattr(agent, "last_dossier_id", None),
                    }
                )
                continue
            snap = agent.survival_snapshot()
            ledger = []
            for entry in list(
                getattr(agent, "ledger", {}).entries
                if hasattr(getattr(agent, "ledger", None), "entries")
                else []
            )[-40:]:
                if hasattr(entry, "to_dict"):
                    ledger.append(entry.to_dict())
                elif isinstance(entry, dict):
                    ledger.append(entry)
            # TelemetryLedger may store differently
            if not ledger and hasattr(agent, "ledger"):
                led = agent.ledger
                if hasattr(led, "export"):
                    ledger = led.export() if callable(led.export) else []
                elif hasattr(led, "to_list"):
                    ledger = led.to_list()
                elif hasattr(led, "history"):
                    ledger = [
                        e.to_dict() if hasattr(e, "to_dict") else dict(e)
                        for e in list(led.history)[-40:]
                    ]

            hist = []
            for m in list(getattr(agent, "history", []))[-30:]:
                if hasattr(m, "__dict__"):
                    hist.append(
                        {
                            "token_cost": getattr(m, "token_cost", 0),
                            "execution_time": getattr(m, "execution_time", 0.0),
                            "quality_score": getattr(m, "quality_score", 0.0),
                            "synergy_score": getattr(m, "synergy_score", 0.0),
                            "expected_token_cost": getattr(m, "expected_token_cost", 0),
                            "expected_time": getattr(m, "expected_time", 0.0),
                        }
                    )

            roster_blob.append(
                {
                    "kind": "ops",
                    "id": getattr(agent, "id", ""),
                    "name": agent.name,
                    "role": agent.role,
                    "status": (
                        agent.status.value if hasattr(agent.status, "value") else str(agent.status)
                    ),
                    "capabilities": list(getattr(agent, "capabilities", [])),
                    "capability_vector": dict(getattr(agent, "capability_vector", {}) or {}),
                    "termination_risk_index": float(
                        getattr(agent, "termination_risk_index", 0.0) or 0.0
                    ),
                    "entanglement_errors": int(getattr(agent, "entanglement_errors", 0) or 0),
                    "cycle_counter": int(getattr(agent, "cycle_counter", 0) or 0),
                    "corporate_rank": float(getattr(agent, "corporate_rank", 0.0) or 0.0),
                    "is_phantom": bool(getattr(agent, "is_phantom", False)),
                    "survival": snap,
                    "history": hist,
                    "muscle_memory_weights": dict(
                        getattr(agent, "muscle_memory_weights", {}) or {}
                    ),
                }
            )

        muscle = []
        mm = getattr(system, "muscle_db", None)
        if mm is not None:
            for rec in list(getattr(mm, "storage", []))[-200:]:
                if hasattr(rec, "to_dict"):
                    muscle.append(rec.to_dict())
                elif isinstance(rec, dict):
                    muscle.append(rec)

        living = []
        pb = getattr(system, "playbook", None)
        if pb is not None and hasattr(pb, "records"):
            for rec in list(pb.records)[-100:]:
                if hasattr(rec, "to_dict"):
                    living.append(rec.to_dict())
                elif isinstance(rec, dict):
                    living.append(rec)

        analytics = {}
        if getattr(system, "analytics", None) is not None:
            analytics = system.analytics.export()
            analytics["day_counter"] = int(system.analytics.day_counter)
            analytics["cycle_counter"] = int(getattr(system.analytics, "cycle_counter", 0) or 0)
            analytics["week_index"] = int(getattr(system.analytics, "week_index", 0) or 0)
            if hasattr(system.analytics, "audit_log"):
                analytics["audit_log"] = list(system.analytics.audit_log)[-50:]
            # Full film-room ring buffer (survives weekend restarts)
            ledger = []
            for day in list(getattr(system.analytics, "_day_ledger", []) or []):
                ledger.append([s.to_dict() if hasattr(s, "to_dict") else dict(s) for s in day])
            analytics["day_ledger"] = ledger
            cur = list(getattr(system.analytics, "_current_day", []) or [])
            analytics["current_day"] = [
                s.to_dict() if hasattr(s, "to_dict") else dict(s) for s in cur
            ]

        compiled = None
        if getattr(system, "compiled_playbook", None) is not None:
            try:
                compiled = system.compiled_playbook.to_dict()
            except Exception:  # noqa: BLE001
                compiled = {
                    "playbook_id": getattr(system.compiled_playbook, "playbook_id", None),
                    "playbook_name": getattr(system.compiled_playbook, "playbook_name", None),
                }

        return {
            "version": "1.6.1",
            "saved_at": time.time(),
            "token_spend": int(getattr(system, "token_spend", 0) or 0),
            "token_budget": int(getattr(system, "token_budget", 0) or 0),
            "active_playbook_id": getattr(system, "active_playbook_id", None),
            "playbook_flow_path": list(getattr(system, "playbook_flow_path", []) or []),
            "playbook_routing": dict(getattr(system, "playbook_routing", {}) or {}),
            "roster": roster_blob,
            "muscle_memory": muscle,
            "living_playbook": living,
            "living_meta": {
                "model_class": getattr(pb, "model_class", "generic") if pb else "generic",
                "horizon_reached": bool(getattr(pb, "horizon_reached", False)) if pb else False,
                "evolution_iteration": int(getattr(pb, "evolution_iteration", 0) or 0) if pb else 0,
            },
            "analytics": analytics,
            "compiled_playbook": compiled,
            "muscle_stats": {
                "hits": int(getattr(mm, "hits", 0) or 0) if mm else 0,
                "misses": int(getattr(mm, "misses", 0) or 0) if mm else 0,
            },
        }

    def save(self, system: Any) -> str:
        """Atomically write scrubbed system snapshot to disk. Returns path.

        v2.2.0 R1: SecretScrubber runs at write-time so tokens/webhooks never
        land in system_state.json.
        """
        from .secret_vault import SecretScrubber

        with self._lock:
            try:
                self.ensure_dir()
                payload = self.dump_system(system)
                # Tenant metadata if present
                if hasattr(system, "tenant_id"):
                    payload["tenant_id"] = getattr(system, "tenant_id", "default")
                safe = SecretScrubber.scrub(payload)
                tmp = self.path.with_suffix(self.path.suffix + ".tmp")
                tmp.write_text(
                    json.dumps(safe, indent=2, default=str),
                    encoding="utf-8",
                )
                tmp.replace(self.path)
                self.save_count += 1
                self.last_error = None
                return str(self.path)
            except Exception as exc:  # noqa: BLE001
                self.last_error = str(exc)
                raise

    def load_raw(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            if not self.path.is_file():
                return None
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.load_count += 1
                return data if isinstance(data, dict) else None
            except Exception as exc:  # noqa: BLE001
                self.last_error = str(exc)
                return None

    def restore(self, system: Any) -> Dict[str, Any]:
        """Re-hydrate system from disk. Returns restore report."""
        data = self.load_raw()
        if not data:
            return {"restored": False, "reason": "no_state_file", "path": str(self.path)}

        report: Dict[str, Any] = {
            "restored": True,
            "path": str(self.path),
            "saved_at": data.get("saved_at"),
            "version": data.get("version"),
        }

        system.token_spend = int(data.get("token_spend") or 0)
        if data.get("token_budget"):
            system.token_budget = int(data["token_budget"])
        system.active_playbook_id = data.get("active_playbook_id")
        system.playbook_flow_path = list(data.get("playbook_flow_path") or [])
        system.playbook_routing = dict(data.get("playbook_routing") or {})

        # Analytics film room
        analytics = data.get("analytics") or {}
        if analytics and getattr(system, "analytics", None) is not None:
            from .analytics import DailyTelemetrySnapshot

            system.analytics.day_counter = int(analytics.get("day_counter") or 0)
            if "cycle_counter" in analytics:
                system.analytics.cycle_counter = int(analytics["cycle_counter"])
            if "week_index" in analytics:
                system.analytics.week_index = int(analytics["week_index"])
            if "audit_log" in analytics and hasattr(system.analytics, "audit_log"):
                system.analytics.audit_log = list(analytics["audit_log"])

            def _snap(row: dict) -> DailyTelemetrySnapshot:
                fp = row.get("flow_path") or ()
                if isinstance(fp, list):
                    fp = tuple(fp)
                return DailyTelemetrySnapshot(
                    day_index=int(row.get("day_index") or 0),
                    agent_name=str(row.get("agent_name") or ""),
                    agent_id=str(row.get("agent_id") or ""),
                    role=str(row.get("role") or ""),
                    fitness=float(row.get("fitness") or 0.0),
                    quality=float(row.get("quality") or 0.0),
                    token_spend=int(row.get("token_spend") or 0),
                    expected_tokens=int(row.get("expected_tokens") or 0),
                    latency=float(row.get("latency") or 0.0),
                    expected_latency=float(row.get("expected_latency") or 0.0),
                    schema_errors=int(row.get("schema_errors") or 0),
                    termination_risk=float(row.get("termination_risk") or 0.0),
                    status=str(row.get("status") or "ACTIVE"),
                    path=str(row.get("path") or ""),
                    flow_path=fp,
                    prompt_tweak=str(row.get("prompt_tweak") or ""),
                    workload=str(row.get("workload") or ""),
                )

            if "day_ledger" in analytics:
                restored_ledger = []
                for day in analytics["day_ledger"]:
                    restored_ledger.append([_snap(r) for r in day if isinstance(r, dict)])
                system.analytics._day_ledger = restored_ledger
            if "current_day" in analytics:
                system.analytics._current_day = [
                    _snap(r) for r in analytics["current_day"] if isinstance(r, dict)
                ]
            report["analytics_days"] = system.analytics.days_ready()

        # Muscle-Memory
        from .muscle_memory import ExecutionMemoryRecord

        mm = getattr(system, "muscle_db", None)
        muscle_rows = data.get("muscle_memory") or []
        if mm is not None and muscle_rows:
            mm.storage = []
            for row in muscle_rows:
                try:
                    if hasattr(mm, "commit_memory"):
                        rec = ExecutionMemoryRecord(
                            memory_id=str(row.get("memory_id") or "MEM-R"),
                            job_type=str(row.get("job_type") or "unknown"),
                            state_vector=list(row.get("state_vector") or [0.5, 0.5, 1.0, 0.1]),
                            successful_flow_path=list(
                                row.get("successful_flow_path") or ["path_A"]
                            ),
                            entanglement_score=float(row.get("entanglement_score") or 0.9),
                            prompt_tweak=str(row.get("prompt_tweak") or ""),
                            quality=float(row.get("quality") or 0.9),
                            token_cost=int(row.get("token_cost") or 0),
                            tags=tuple(row.get("tags") or ()),
                        )
                        # bypass quality gate on restore
                        mm.storage.append(rec)
                except Exception:  # noqa: BLE001
                    continue
            stats = data.get("muscle_stats") or {}
            mm.hits = int(stats.get("hits") or 0)
            mm.misses = int(stats.get("misses") or 0)
            report["muscle_records"] = len(mm.storage)

        # Living playbook records (best-effort)
        living_rows = data.get("living_playbook") or []
        living_meta = data.get("living_meta") or {}
        pb = getattr(system, "playbook", None)
        if pb is not None:
            for attr, key, cast in (
                ("model_class", "model_class", str),
                ("_horizon_reached", "horizon_reached", bool),
                ("horizon_reached", "horizon_reached", bool),
                ("evolution_iteration", "evolution_iteration", int),
            ):
                if key in living_meta and hasattr(pb, attr):
                    try:
                        setattr(pb, attr, cast(living_meta[key]))
                    except Exception:
                        pass
            report["living_records"] = len(living_rows)

        # Roster TPC / fear indices
        from .agents import Agent, AgentStatus, BossAgent
        from .metrics import ExecutionMetrics

        name_map = {a.name: a for a in system.roster if not isinstance(a, BossAgent)}
        restored_ops = 0
        for row in data.get("roster") or []:
            if row.get("kind") == "boss":
                for a in system.roster:
                    if isinstance(a, BossAgent):
                        a.playbook = list(row.get("playbook") or a.playbook)
                        a.acknowledged = bool(row.get("acknowledged", a.acknowledged))
                        if row.get("last_dossier_id"):
                            a.last_dossier_id = row["last_dossier_id"]
                continue
            agent = name_map.get(row.get("name"))
            if agent is None:
                # recreate missing ops agent
                try:
                    agent = Agent(
                        name=str(row.get("name") or "Restored"),
                        role=str(row.get("role") or "Key Player"),
                        capability_vector=dict(row.get("capability_vector") or {"general": 1.0}),
                    )
                    agent.capabilities = list(row.get("capabilities") or ["general"])
                    system.roster.append(agent)
                    name_map[agent.name] = agent
                except Exception:  # noqa: BLE001
                    continue
            agent.termination_risk_index = float(row.get("termination_risk_index") or 0.0)
            agent.entanglement_errors = int(row.get("entanglement_errors") or 0)
            agent.cycle_counter = int(row.get("cycle_counter") or 0)
            if "corporate_rank" in row:
                agent.corporate_rank = float(row["corporate_rank"] or 0.0)
            agent.is_phantom = bool(row.get("is_phantom", False))
            st = str(row.get("status") or "ACTIVE")
            try:
                agent.status = AgentStatus(st)
            except Exception:  # noqa: BLE001
                pass
            agent.muscle_memory_weights = dict(row.get("muscle_memory_weights") or {})
            # rebuild history metrics
            agent.history = []
            for h in row.get("history") or []:
                try:
                    agent.history.append(
                        ExecutionMetrics(
                            token_cost=int(h.get("token_cost") or 0),
                            execution_time=float(h.get("execution_time") or 0.001),
                            quality_score=float(h.get("quality_score") or 0.0),
                            synergy_score=float(h.get("synergy_score") or 1.0),
                            expected_token_cost=int(h.get("expected_token_cost") or 0),
                            expected_time=float(h.get("expected_time") or 0.001),
                        )
                    )
                except Exception:  # noqa: BLE001
                    continue
            # refresh survival prompt from restored risk
            if hasattr(agent, "refresh_survival_prompt"):
                try:
                    agent.refresh_survival_prompt()
                except Exception:  # noqa: BLE001
                    pass
            restored_ops += 1

        report["ops_restored"] = restored_ops
        return report


# Process singleton
_PERSISTER: Optional[StatePersister] = None


def get_persister(path: Optional[str] = None) -> StatePersister:
    global _PERSISTER
    if _PERSISTER is None or (path and str(_PERSISTER.path) != str(path)):
        _PERSISTER = StatePersister(path)
    return _PERSISTER
