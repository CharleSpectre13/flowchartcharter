"""v2.2.0 Multi-Tenant Namespace Engine (R7).

Isolates CFO ceiling, muscle memory, playbooks, and draft registries
per tenant_id so ORG-ALPHA cannot burn ORG-BETA budget or leak memory.
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class TenantNamespacedEngine:
    """Per-tenant budget + memory isolation."""

    tenant_id: str
    cfo_ceiling: int
    token_spent: int = 0
    muscle_memory_db: List[Dict[str, Any]] = field(default_factory=list)
    active_playbooks: Dict[str, Any] = field(default_factory=dict)
    pending_drafts: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def charge_budget(self, tokens: int) -> bool:
        """Atomically charge tokens; False if over ceiling."""
        tokens = max(0, int(tokens))
        with self._lock:
            if self.token_spent + tokens > self.cfo_ceiling:
                return False
            self.token_spent += tokens
            return True

    def remaining(self) -> int:
        with self._lock:
            return max(0, self.cfo_ceiling - self.token_spent)

    def commit_memory(self, record: Dict[str, Any]) -> None:
        with self._lock:
            rec = dict(record)
            rec["tenant_id"] = self.tenant_id
            self.muscle_memory_db.append(rec)

    def query_memory(
        self,
        *,
        job_type: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            rows = list(self.muscle_memory_db)
        if job_type:
            jt = job_type.lower()
            rows = [
                r
                for r in rows
                if jt in str(r.get("job_type", "")).lower()
            ]
        return rows[-limit:]

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "tenant_id": self.tenant_id,
                "cfo_ceiling": self.cfo_ceiling,
                "token_spent": self.token_spent,
                "remaining": max(0, self.cfo_ceiling - self.token_spent),
                "memory_records": len(self.muscle_memory_db),
                "active_playbooks": len(self.active_playbooks),
                "pending_drafts": len(self.pending_drafts),
            }


class TenantRegistry:
    """Process-wide registry of tenant namespaces."""

    def __init__(self, default_ceiling: int = 12_000) -> None:
        self.default_ceiling = int(default_ceiling)
        self._tenants: Dict[str, TenantNamespacedEngine] = {}
        self._lock = threading.Lock()

    def get_or_create(
        self,
        tenant_id: str,
        *,
        cfo_ceiling: Optional[int] = None,
    ) -> TenantNamespacedEngine:
        tid = (tenant_id or "default").strip() or "default"
        with self._lock:
            if tid not in self._tenants:
                self._tenants[tid] = TenantNamespacedEngine(
                    tenant_id=tid,
                    cfo_ceiling=int(cfo_ceiling or self.default_ceiling),
                )
            elif cfo_ceiling is not None:
                self._tenants[tid].cfo_ceiling = int(cfo_ceiling)
            return self._tenants[tid]

    def list_tenants(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [t.stats() for t in self._tenants.values()]

    def isolate_check(self, tenant_a: str, tenant_b: str) -> bool:
        """True when A and B have independent engines (no shared state)."""
        a = self.get_or_create(tenant_a)
        b = self.get_or_create(tenant_b)
        return a is not b and a.tenant_id != b.tenant_id


_REGISTRY: Optional[TenantRegistry] = None


def get_tenant_registry() -> TenantRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        ceil = int(os.environ.get("FCC_DEFAULT_TENANT_CEILING", "12000"))
        _REGISTRY = TenantRegistry(default_ceiling=ceil)
    return _REGISTRY


def resolve_tenant_id(
    explicit: Optional[str] = None,
    *,
    header: Optional[str] = None,
    env_default: str = "default",
) -> str:
    if explicit and str(explicit).strip():
        return str(explicit).strip()
    if header and str(header).strip():
        return str(header).strip()
    return os.environ.get("FCC_TENANT_ID", env_default) or env_default
