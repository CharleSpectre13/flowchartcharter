# Async API Routing Audit — Boss Super-Step Rhythm

## Goal
Maximum rhythm, zero idle latency when workers call production LLMs.

## Structure
1. **CFO pre-collapse gate** (serial, cheap) — budget matrix before any fan-out
2. **Path collapse** per agent (serial or batched) — quantum router
3. **Fan-out** `run_workers_parallel(tasks)` — ThreadPoolExecutor over `LLMExecutionClient.execute`
4. **Barrier** — collect all `WorkerTaskResult` before Rhythm Marker audit
5. **Ledger commit** — schema failures already carry `entanglement_errors_delta`

## Why threads not asyncio for v1.3
- Existing Boss loop is synchronous Python
- LLM HTTP is I/O bound; threads release GIL during socket wait
- Same client instance is stateless per call (config only)
- No nested event-loop issues with FastAPI when called from sync path

## FastAPI path
`POST /workload/submit` remains async def but calls `execute_charter` in threadpool if needed later; current charter is sub-ms simulated / mock. Live LLM: wrap `run_workers_parallel` inside `asyncio.to_thread` at the system boundary.

## Latency budget
| Stage | Bound |
|-------|-------|
| CFO gate | O(paths) |
| Fan-out wall | max(worker_llm_latency) not sum |
| Schema gate | O(1) Pydantic |
| Muscle-Memory query | O(k) ANN / local hybrid |
