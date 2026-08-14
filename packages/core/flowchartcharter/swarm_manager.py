"""v1.8 SwarmManager Flow Unit — parallel dataset processing under CFO ceiling.

Design (loop-engineer + advanced-coding):
  - Fan-out over an iterable dataset with a bounded worker pool
  - Unified CFO_Ceiling token counter (thread-safe + asyncio-safe)
  - Individual worker failures isolated — swarm never crashes on one bad item
  - StatePersister-safe: workers never write system state; caller persists once
  - asyncio.gather + Semaphore for native async loop integration
  - ThreadPoolExecutor fallback for sync / blocking processors
"""

from __future__ import annotations

import asyncio
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Union,
)

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Contracts
# ---------------------------------------------------------------------------


class SwarmItemSchema(BaseModel):
    """One unit of work handed to a swarm worker."""

    item_id: str = Field(..., min_length=1, max_length=200)
    payload: Dict[str, Any] = Field(default_factory=dict)
    index: int = Field(default=0, ge=0)


class SwarmItemResultSchema(BaseModel):
    """Per-item outcome — always returned, even on failure."""

    index: int = Field(..., ge=0)
    item_id: str
    ok: bool = True
    tokens: int = Field(default=0, ge=0)
    quality: float = Field(default=0.0, ge=0.0, le=1.0)
    error: Optional[str] = None
    output: Dict[str, Any] = Field(default_factory=dict)
    worker_id: str = ""
    wall_ms: float = 0.0


class SwarmReportSchema(BaseModel):
    """Aggregate swarm report for Boss / Rhythm Marker gate."""

    swarm_id: str
    total: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    skipped_budget: int = Field(default=0, ge=0)
    tokens: int = Field(ge=0)
    cfo_ceiling: int = Field(ge=0)
    under_budget: bool = True
    quality: float = Field(ge=0.0, le=1.0)
    max_workers: int = Field(ge=1)
    wall_ms: float = 0.0
    results: List[SwarmItemResultSchema] = Field(default_factory=list)
    rhythm_audit: Dict[str, Any] = Field(default_factory=dict)
    mode: str = "thread"  # thread | asyncio


WorkerFn = Callable[[SwarmItemSchema], SwarmItemResultSchema]
AsyncWorkerFn = Callable[[SwarmItemSchema], Awaitable[SwarmItemResultSchema]]


# ---------------------------------------------------------------------------
# Token ledger (race-safe)
# ---------------------------------------------------------------------------


class TokenLedger:
    """Unified CFO token counter shared across swarm workers.

    Thread-safe via ``threading.Lock``. Async paths use the same lock only
    around integer updates (non-blocking duration) so the asyncio loop is
    never starved. Never touches StatePersister.
    """

    def __init__(self, ceiling: int) -> None:
        self.ceiling = max(0, int(ceiling))
        self._spent = 0
        self._lock = threading.Lock()
        self.rejections = 0

    @property
    def spent(self) -> int:
        with self._lock:
            return self._spent

    @property
    def remaining(self) -> int:
        with self._lock:
            return max(0, self.ceiling - self._spent)

    def try_reserve(self, estimate: int) -> bool:
        """Atomically reserve tokens; False if ceiling would be breached."""
        estimate = max(0, int(estimate))
        with self._lock:
            if self._spent + estimate > self.ceiling:
                self.rejections += 1
                return False
            self._spent += estimate
            return True

    def release(self, amount: int) -> None:
        """Return unused reservation (actual < estimate)."""
        amount = max(0, int(amount))
        if amount == 0:
            return
        with self._lock:
            self._spent = max(0, self._spent - amount)

    def charge_exact(self, estimate: int, actual: int) -> int:
        """Adjust reservation to actual spend; returns tokens recorded."""
        actual = max(0, int(actual))
        estimate = max(0, int(estimate))
        with self._lock:
            # undo estimate, apply actual (net delta)
            self._spent = max(0, self._spent - estimate + actual)
            if self._spent > self.ceiling:
                # clamp reporting; do not raise — graceful degrade
                over = self._spent - self.ceiling
                self._spent = self.ceiling
                return max(0, actual - over)
            return actual


# ---------------------------------------------------------------------------
# Default item processor (deterministic mock)
# ---------------------------------------------------------------------------


def default_item_processor(item: SwarmItemSchema) -> SwarmItemResultSchema:
    """CPU-light default worker — schema-safe, no I/O, no state writes."""
    t0 = time.perf_counter()
    text = str(item.payload.get("text") or item.payload.get("body") or item.item_id)
    # Deterministic pseudo-cost from content length
    tokens = min(200, 40 + (len(text) % 80))
    # Fail closed on explicit poison markers without raising
    if item.payload.get("force_fail") or text.startswith("FAIL:"):
        return SwarmItemResultSchema(
            index=item.index,
            item_id=item.item_id,
            ok=False,
            tokens=min(20, tokens),
            quality=0.0,
            error="forced_worker_failure",
            output={},
            worker_id=f"W-{item.index}",
            wall_ms=round((time.perf_counter() - t0) * 1000.0, 3),
        )
    quality = min(1.0, 0.75 + (hash(text) % 25) / 100.0)
    return SwarmItemResultSchema(
        index=item.index,
        item_id=item.item_id,
        ok=True,
        tokens=tokens,
        quality=quality,
        error=None,
        output={"digest": text[:120], "len": len(text)},
        worker_id=f"W-{item.index}",
        wall_ms=round((time.perf_counter() - t0) * 1000.0, 3),
    )


async def default_async_processor(item: SwarmItemSchema) -> SwarmItemResultSchema:
    """Async wrapper of default processor (yields to event loop)."""
    await asyncio.sleep(0)
    return default_item_processor(item)


# ---------------------------------------------------------------------------
# SwarmManager Flow Unit
# ---------------------------------------------------------------------------


@dataclass
class SwarmManager:
    """Parallel Flow Unit — process N documents under one CFO ceiling.

    Race / persistence contract:
      * Workers must be pure w.r.t. system state (no StatePersister calls).
      * TokenLedger is the only shared mutable structure during fan-out.
      * Callers persist engine state **once** after ``run`` / ``run_async``.
    """

    cfo_ceiling: int = 5000
    max_workers: int = 8
    per_item_token_estimate: int = 120
    min_quality_gate: float = 0.90
    quiet: bool = True
    swarms_run: int = 0
    last_report: Optional[SwarmReportSchema] = None
    _history: List[Dict[str, Any]] = field(default_factory=list)

    def normalize_items(
        self,
        dataset: Union[Iterable[Any], Sequence[Any]],
    ) -> List[SwarmItemSchema]:
        """Coerce free-form iterables into SwarmItemSchema list."""
        items: List[SwarmItemSchema] = []
        for i, raw in enumerate(dataset):
            if isinstance(raw, SwarmItemSchema):
                item = raw.model_copy(update={"index": i})
            elif isinstance(raw, dict):
                item = SwarmItemSchema(
                    item_id=str(raw.get("id") or raw.get("item_id") or f"DOC-{i:04d}"),
                    payload=dict(raw.get("payload") or raw),
                    index=i,
                )
            else:
                item = SwarmItemSchema(
                    item_id=f"DOC-{i:04d}",
                    payload={"text": str(raw)},
                    index=i,
                )
            items.append(item)
        return items

    def run(
        self,
        dataset: Union[Iterable[Any], Sequence[Any]],
        *,
        worker_fn: Optional[WorkerFn] = None,
        max_workers: Optional[int] = None,
        cfo_ceiling: Optional[int] = None,
    ) -> SwarmReportSchema:
        """Sync swarm via ThreadPoolExecutor (I/O-bound safe)."""
        t0 = time.perf_counter()
        items = self.normalize_items(dataset)
        ceiling = int(cfo_ceiling if cfo_ceiling is not None else self.cfo_ceiling)
        workers = max(1, int(max_workers or self.max_workers))
        ledger = TokenLedger(ceiling)
        process = worker_fn or default_item_processor
        results: List[SwarmItemResultSchema] = []
        skipped = 0
        swarm_id = f"SWARM-{uuid.uuid4().hex[:10].upper()}"

        def _safe(item: SwarmItemSchema) -> SwarmItemResultSchema:
            estimate = self.per_item_token_estimate
            if not ledger.try_reserve(estimate):
                return SwarmItemResultSchema(
                    index=item.index,
                    item_id=item.item_id,
                    ok=False,
                    tokens=0,
                    quality=0.0,
                    error="cfo_ceiling_exhausted",
                    worker_id=f"SKIP-{item.index}",
                )
            try:
                out = process(item)
            except Exception as exc:  # noqa: BLE001 — isolate worker faults
                ledger.release(estimate)
                return SwarmItemResultSchema(
                    index=item.index,
                    item_id=item.item_id,
                    ok=False,
                    tokens=0,
                    quality=0.0,
                    error=f"worker_exception:{type(exc).__name__}:{exc}",
                    worker_id=f"W-{item.index}",
                )
            # Normalize / charge
            actual = max(0, int(out.tokens))
            charged = ledger.charge_exact(estimate, actual)
            return out.model_copy(
                update={
                    "index": item.index,
                    "item_id": item.item_id,
                    "tokens": charged,
                    "worker_id": out.worker_id or f"W-{item.index}",
                }
            )

        if not items:
            report = self._finalize(
                swarm_id=swarm_id,
                results=[],
                skipped=0,
                ledger=ledger,
                workers=workers,
                wall_ms=0.0,
                mode="thread",
            )
            return report

        with ThreadPoolExecutor(max_workers=min(workers, len(items))) as pool:
            futs = {pool.submit(_safe, it): it for it in items}
            for fut in as_completed(futs):
                try:
                    res = fut.result()
                except Exception as exc:  # noqa: BLE001
                    it = futs[fut]
                    res = SwarmItemResultSchema(
                        index=it.index,
                        item_id=it.item_id,
                        ok=False,
                        tokens=0,
                        quality=0.0,
                        error=f"pool_exception:{type(exc).__name__}",
                        worker_id=f"W-{it.index}",
                    )
                if res.error == "cfo_ceiling_exhausted":
                    skipped += 1
                results.append(res)

        results.sort(key=lambda r: r.index)
        wall = round((time.perf_counter() - t0) * 1000.0, 2)
        return self._finalize(
            swarm_id=swarm_id,
            results=results,
            skipped=skipped,
            ledger=ledger,
            workers=workers,
            wall_ms=wall,
            mode="thread",
        )

    async def run_async(
        self,
        dataset: Union[Iterable[Any], Sequence[Any]],
        *,
        worker_fn: Optional[AsyncWorkerFn] = None,
        max_workers: Optional[int] = None,
        cfo_ceiling: Optional[int] = None,
    ) -> SwarmReportSchema:
        """Async swarm via asyncio.Semaphore + gather (event-loop native)."""
        t0 = time.perf_counter()
        items = self.normalize_items(dataset)
        ceiling = int(cfo_ceiling if cfo_ceiling is not None else self.cfo_ceiling)
        workers = max(1, int(max_workers or self.max_workers))
        ledger = TokenLedger(ceiling)
        process = worker_fn or default_async_processor
        sem = asyncio.Semaphore(workers)
        swarm_id = f"SWARM-{uuid.uuid4().hex[:10].upper()}"

        async def _safe(item: SwarmItemSchema) -> SwarmItemResultSchema:
            estimate = self.per_item_token_estimate
            if not ledger.try_reserve(estimate):
                return SwarmItemResultSchema(
                    index=item.index,
                    item_id=item.item_id,
                    ok=False,
                    tokens=0,
                    quality=0.0,
                    error="cfo_ceiling_exhausted",
                    worker_id=f"SKIP-{item.index}",
                )
            async with sem:
                try:
                    out = await process(item)
                except Exception as exc:  # noqa: BLE001
                    ledger.release(estimate)
                    return SwarmItemResultSchema(
                        index=item.index,
                        item_id=item.item_id,
                        ok=False,
                        tokens=0,
                        quality=0.0,
                        error=f"worker_exception:{type(exc).__name__}:{exc}",
                        worker_id=f"W-{item.index}",
                    )
            actual = max(0, int(out.tokens))
            charged = ledger.charge_exact(estimate, actual)
            return out.model_copy(
                update={
                    "index": item.index,
                    "item_id": item.item_id,
                    "tokens": charged,
                    "worker_id": out.worker_id or f"W-{item.index}",
                }
            )

        if not items:
            return self._finalize(
                swarm_id=swarm_id,
                results=[],
                skipped=0,
                ledger=ledger,
                workers=workers,
                wall_ms=0.0,
                mode="asyncio",
            )

        raw = await asyncio.gather(
            *[_safe(it) for it in items],
            return_exceptions=False,
        )
        results = list(raw)
        results.sort(key=lambda r: r.index)
        skipped = sum(1 for r in results if r.error == "cfo_ceiling_exhausted")
        wall = round((time.perf_counter() - t0) * 1000.0, 2)
        return self._finalize(
            swarm_id=swarm_id,
            results=results,
            skipped=skipped,
            ledger=ledger,
            workers=workers,
            wall_ms=wall,
            mode="asyncio",
        )

    def _finalize(
        self,
        *,
        swarm_id: str,
        results: List[SwarmItemResultSchema],
        skipped: int,
        ledger: TokenLedger,
        workers: int,
        wall_ms: float,
        mode: str,
    ) -> SwarmReportSchema:
        succeeded = sum(1 for r in results if r.ok)
        failed = sum(1 for r in results if not r.ok and r.error != "cfo_ceiling_exhausted")
        # skipped already counted in failed-or-skip; keep separate field
        failed = sum(
            1
            for r in results
            if (not r.ok) and r.error not in (None, "cfo_ceiling_exhausted")
        )
        tokens = ledger.spent
        under = tokens <= ledger.ceiling
        ok_qualities = [r.quality for r in results if r.ok]
        quality = (
            sum(ok_qualities) / len(ok_qualities) if ok_qualities else 0.0
        )
        # success ratio softens quality if many failures
        if results:
            ratio = succeeded / max(1, len(results))
            quality = min(1.0, quality * (0.5 + 0.5 * ratio))

        issues: List[str] = []
        if not under:
            issues.append("cfo_ceiling_breach")
        if failed:
            issues.append(f"worker_failures={failed}")
        if quality < self.min_quality_gate:
            issues.append("swarm_quality_below_gate")
        if not results:
            issues.append("empty_dataset")

        from .vectors import RhythmAudit

        audit = RhythmAudit(
            marker="swarm_gate",
            charter_id=f"swarm:{swarm_id}",
            quality=float(quality),
            threshold=self.min_quality_gate,
            passed=quality >= self.min_quality_gate and under and failed == 0,
            remediation_loops=0 if failed == 0 else 1,
            blocking_issues=tuple(issues),
        )

        report = SwarmReportSchema(
            swarm_id=swarm_id,
            total=len(results),
            succeeded=succeeded,
            failed=failed,
            skipped_budget=skipped,
            tokens=tokens,
            cfo_ceiling=ledger.ceiling,
            under_budget=under,
            quality=round(quality, 4),
            max_workers=workers,
            wall_ms=wall_ms,
            results=results,
            rhythm_audit=audit.to_dict(),
            mode=mode,
        )
        self.swarms_run += 1
        self.last_report = report
        self._history.append(
            {
                "swarm_id": swarm_id,
                "total": report.total,
                "succeeded": report.succeeded,
                "failed": report.failed,
                "tokens": report.tokens,
                "quality": report.quality,
            }
        )
        if len(self._history) > 50:
            self._history = self._history[-50:]
        if not self.quiet:
            print(
                f"[SwarmManager] {swarm_id} ok={succeeded}/{len(results)} "
                f"tok={tokens}/{ledger.ceiling} Q={quality:.3f}"
            )
        return report

    def stats(self) -> Dict[str, Any]:
        return {
            "swarms_run": self.swarms_run,
            "cfo_ceiling": self.cfo_ceiling,
            "max_workers": self.max_workers,
            "last_swarm_id": (
                self.last_report.swarm_id if self.last_report else None
            ),
            "history_tail": list(self._history[-5:]),
        }

    async def process_dataset(
        self,
        dataset: Sequence[Any],
        base_worker_role: str = "SwarmWorker",
        *,
        cfo_ceiling: Optional[int] = None,
        max_workers: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Reference-compatible async entry (Hands / Scaling blueprint).

        Wraps :meth:`run_async` and returns ``{swarm_results: [...]}`` plus
        full report fields. ``base_worker_role`` is recorded for telemetry only.
        """
        report = await self.run_async(
            dataset,
            max_workers=max_workers,
            cfo_ceiling=cfo_ceiling,
        )
        swarm_results = [
            {
                "item": r.item_id,
                "status": (
                    "SUCCESS"
                    if r.ok
                    else (
                        "SKIPPED_BUDGET"
                        if r.error == "cfo_ceiling_exhausted"
                        else "FAILED"
                    )
                ),
                "tokens": r.tokens,
                "error": r.error,
                "worker_role": base_worker_role,
            }
            for r in report.results
        ]
        return {
            "swarm_results": swarm_results,
            "total_tokens_spent": report.tokens,
            "cfo_ceiling": report.cfo_ceiling,
            "report": report.model_dump(),
        }
