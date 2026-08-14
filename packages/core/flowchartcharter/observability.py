"""Enterprise observability — Prometheus exporters for TPC telemetry.

Design (async-safe):
  - All metric objects are module-level prometheus_client collectors
  - Updates happen on the request path with O(roster) cheap arithmetic
  - /metrics only serializes already-computed values (no engine lock, no I/O)
  - scrape never calls execute_charter / LLM / vector DB

Gauges refresh from a snapshot; counters only increase.
"""

from __future__ import annotations

import time
from typing import Any, Dict

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )

    _PROM = True
except ImportError:  # pragma: no cover
    _PROM = False
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"


class MetricsHub:
    """Process-global Prometheus registry for FlowChartCharter."""

    def __init__(self) -> None:
        self.enabled = _PROM
        self._last_sync = 0.0
        if not _PROM:
            self.registry = None
            return

        self.registry = CollectorRegistry()
        self.active_nodes = Gauge(
            "fcc_active_nodes",
            "Count of operational agents (ACTIVE/PROMOTED/PHANTOM)",
            registry=self.registry,
        )
        self.node_fear = Gauge(
            "fcc_node_fear_index",
            "Teleological Performance Constraint termination_risk_index",
            ["node_id", "node_name", "role"],
            registry=self.registry,
        )
        self.node_fitness = Gauge(
            "fcc_node_fitness",
            "Latest AgentFitness score F(x)",
            ["node_id", "node_name"],
            registry=self.registry,
        )
        self.entanglement_errors = Counter(
            "fcc_entanglement_errors_total",
            "Cumulative schema / entanglement failures",
            ["node_id", "node_name"],
            registry=self.registry,
        )
        self.token_spend = Counter(
            "fcc_token_spend_total",
            "Cumulative token spend by playbook",
            ["playbook_id"],
            registry=self.registry,
        )
        self.workloads_total = Counter(
            "fcc_workloads_total",
            "Workloads submitted to Boss Agent",
            ["result"],  # trust|fail
            registry=self.registry,
        )
        self.quality = Gauge(
            "fcc_last_workload_quality",
            "Quality of most recent workload",
            registry=self.registry,
        )
        self.token_budget = Gauge(
            "fcc_token_budget",
            "Current CFO global token ceiling",
            registry=self.registry,
        )
        self.token_spend_gauge = Gauge(
            "fcc_token_spend_current",
            "Current period token spend",
            registry=self.registry,
        )
        self.analytics_days = Gauge(
            "fcc_analytics_days_ready",
            "Analytics Chief film-room days ready (0-5)",
            registry=self.registry,
        )
        self.muscle_hits = Counter(
            "fcc_muscle_memory_hits_total",
            "Muscle-Memory trajectory hits",
            registry=self.registry,
        )
        self.muscle_misses = Counter(
            "fcc_muscle_memory_misses_total",
            "Muscle-Memory trajectory misses",
            registry=self.registry,
        )
        self.request_latency = Histogram(
            "fcc_request_latency_seconds",
            "Charter / API request latency",
            ["endpoint"],
            buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0),
            registry=self.registry,
        )
        # v2.2.0 R7 SLOs
        self.action_blocked = Counter(
            "fcc_action_blocked_total",
            "ActionUnit schema blocks (Fear path)",
            ["unit_type"],
            registry=self.registry,
        )
        self.action_ok = Counter(
            "fcc_action_ok_total",
            "ActionUnit successful executions",
            ["unit_type"],
            registry=self.registry,
        )
        self.rhythm_pass = Counter(
            "fcc_rhythm_pass_total",
            "RhythmAudit passed gates",
            ["marker"],
            registry=self.registry,
        )
        self.rhythm_fail = Counter(
            "fcc_rhythm_fail_total",
            "RhythmAudit failed gates",
            ["marker"],
            registry=self.registry,
        )
        self.pending_charters = Gauge(
            "fcc_pending_charters",
            "Charter drafts awaiting coach approval",
            registry=self.registry,
        )
        self.tenant_token_spent = Gauge(
            "fcc_tenant_token_spent",
            "Per-tenant token spend",
            ["tenant_id"],
            registry=self.registry,
        )
        self.tenant_cfo_ceiling = Gauge(
            "fcc_tenant_cfo_ceiling",
            "Per-tenant CFO ceiling",
            ["tenant_id"],
            registry=self.registry,
        )
        # track last known counter levels to emit deltas safely
        self._entangle_seen: Dict[str, int] = {}
        self._token_seen: Dict[str, int] = {}
        self._mm_hits = 0
        self._mm_misses = 0

    def sync_from_system(self, system: Any) -> None:
        """Refresh gauges from live engine snapshot (CPU-only, non-blocking)."""
        if not self.enabled:
            return
        from .agents import AgentStatus, BossAgent

        active = 0
        for agent in system.roster:
            if isinstance(agent, BossAgent):
                continue
            node_id = str(getattr(agent, "id", agent.name))
            name = str(agent.name)
            role = str(agent.role)
            status = agent.status
            if status in (
                AgentStatus.ACTIVE,
                AgentStatus.PROMOTED,
                AgentStatus.PHANTOM,
            ):
                active += 1
            fear = float(getattr(agent, "termination_risk_index", 0.0) or 0.0)
            self.node_fear.labels(node_id=node_id, node_name=name, role=role).set(fear)
            try:
                fit = float(agent.calculate_fitness())
            except Exception:  # noqa: BLE001
                fit = 0.0
            self.node_fitness.labels(node_id=node_id, node_name=name).set(fit)

            ent = int(getattr(agent, "entanglement_errors", 0) or 0)
            prev = self._entangle_seen.get(node_id, 0)
            if ent > prev:
                self.entanglement_errors.labels(node_id=node_id, node_name=name).inc(ent - prev)
                self._entangle_seen[node_id] = ent
            elif node_id not in self._entangle_seen:
                self._entangle_seen[node_id] = ent

        self.active_nodes.set(active)
        self.token_budget.set(float(getattr(system, "token_budget", 0) or 0))
        self.token_spend_gauge.set(float(getattr(system, "token_spend", 0) or 0))

        pb_id = str(getattr(system, "active_playbook_id", None) or "default_charter")
        spend = int(getattr(system, "token_spend", 0) or 0)
        prev_t = self._token_seen.get(pb_id, 0)
        if spend > prev_t:
            self.token_spend.labels(playbook_id=pb_id).inc(spend - prev_t)
            self._token_seen[pb_id] = spend
        elif pb_id not in self._token_seen:
            self._token_seen[pb_id] = spend

        analytics = getattr(system, "analytics", None)
        if analytics is not None:
            self.analytics_days.set(float(analytics.days_ready()))

        mm = getattr(system, "muscle_db", None)
        if mm is not None:
            hits = int(getattr(mm, "hits", 0) or 0)
            misses = int(getattr(mm, "misses", 0) or 0)
            if hits > self._mm_hits:
                self.muscle_hits.inc(hits - self._mm_hits)
                self._mm_hits = hits
            if misses > self._mm_misses:
                self.muscle_misses.inc(misses - self._mm_misses)
                self._mm_misses = misses

        # v2.2 pending charters + tenant gauges
        synth = getattr(system, "synthesizer", None)
        if synth is not None and hasattr(synth, "list_pending"):
            try:
                self.pending_charters.set(float(len(synth.list_pending())))
            except Exception:  # noqa: BLE001
                pass
        tenant = getattr(system, "tenant", None)
        if tenant is not None:
            tid = str(getattr(tenant, "tenant_id", "default"))
            self.tenant_token_spent.labels(tenant_id=tid).set(
                float(getattr(tenant, "token_spent", 0) or 0)
            )
            self.tenant_cfo_ceiling.labels(tenant_id=tid).set(
                float(getattr(tenant, "cfo_ceiling", 0) or 0)
            )

        self._last_sync = time.time()

    def observe_workload(
        self,
        *,
        quality: float,
        trust: bool,
        token_delta: int = 0,
        playbook_id: str = "default_charter",
        latency_s: float = 0.0,
        endpoint: str = "workload_submit",
    ) -> None:
        if not self.enabled:
            return
        self.quality.set(quality)
        self.workloads_total.labels(result="trust" if trust else "fail").inc()
        if token_delta > 0:
            self.token_spend.labels(playbook_id=playbook_id or "default_charter").inc(token_delta)
            prev = self._token_seen.get(playbook_id, 0)
            self._token_seen[playbook_id] = prev + token_delta
        if latency_s > 0:
            self.request_latency.labels(endpoint=endpoint).observe(latency_s)

    def observe_rhythm(self, audits: list) -> None:
        """Increment rhythm pass/fail counters from audit dicts."""
        if not self.enabled:
            return
        for a in audits or []:
            if not isinstance(a, dict):
                continue
            marker = str(a.get("marker") or "gate")
            if a.get("passed"):
                self.rhythm_pass.labels(marker=marker).inc()
            else:
                self.rhythm_fail.labels(marker=marker).inc()

    def observe_actions(self, unit_results: list) -> None:
        """Increment action blocked/ok from playbook unit results."""
        if not self.enabled:
            return
        for r in unit_results or []:
            if not isinstance(r, dict):
                continue
            if r.get("unit_kind") != "action":
                continue
            ut = str(r.get("action_type") or "ActionUnit")
            if r.get("blocked"):
                self.action_blocked.labels(unit_type=ut).inc()
            elif r.get("ok"):
                self.action_ok.labels(unit_type=ut).inc()

    def export(self) -> bytes:
        """Serialize metrics — pure memory, never blocks on engine work."""
        if not self.enabled or self.registry is None:
            body = (
                "# HELP fcc_metrics_unavailable prometheus_client not installed\n"
                "# TYPE fcc_metrics_unavailable gauge\n"
                "fcc_metrics_unavailable 1\n"
            )
            return body.encode("utf-8")
        return generate_latest(self.registry)

    @property
    def content_type(self) -> str:
        return CONTENT_TYPE_LATEST


# Singleton hub (process-wide)
HUB = MetricsHub()


def get_metrics_hub() -> MetricsHub:
    return HUB
