# FlowChartCharter Engine

**Execution-first multi-agent state-chart systems** — the process-orchestration discipline after GraphRAG.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/core-v1.2.0-green.svg)](packages/core)

> **Public design name:** *flowchart-charter-engine*  
> **Repo:** [CharleSpectre13/flowchartcharter](https://github.com/CharleSpectre13/flowchartcharter)

---

## Whitepaper (short)

### Why GraphRAG is bloated for agent ops

GraphRAG optimizes **what is related** and **how do I retrieve it**. That is valuable for discovery — and expensive for *execution*:

| GraphRAG path | Cost |
|---------------|------|
| Unstructured graph walk | High token burn |
| Chunk → reason from scratch every time | High latency |
| Weak accountability on agent quality | Silent drift |

In a fast multi-agent shop floor, time and tokens compound. You need a **chartered path**, not another graph traversal.

### What FlowChartCharter does instead

FlowChartCharter optimizes **the fastest reliable path to execute**, with:

1. **Typed Flow Units** — deterministic playbook steps, not free-form RAG chains  
2. **Muscle-Memory Vector DB** — successful trajectories, not raw text chunks  
3. **Living Playbook** — personnel-agnostic trajectories + zero-shot synthesis at horizon  
4. **Teleological Performance Constraints (TPC)** — fear/accountability in the prompt; fitness that fires bloat, not hard work  
5. **Analytics Chief** — 5-day MA dossier so Monday Sync is Board-driven, not GM guesswork  
6. **Quantum-inspired routing** — path superposition collapse under CFO budget + context entropy  

Graph / GraphRAG remains a **callable sub-flow** when pure relational discovery is required. The **Charter owns the workflow**.

### Fitness (patched)

```
F(x) = α·(Q_success/Q_total)
     + β·exp(−Δt / expected_t)          # bounded speed — no 1/Δt blow-up
     − γ·max(0, tokens − expected)/N    # delta-token bloat only
     + Q_entanglement
```

---

## Phase 2 — API Nervous System

The engine is a **FastAPI microservice**. External dashboards and enterprise tools submit JSON workloads to the Boss Agent over HTTP.

### Boot

```bash
pip install -r requirements.txt
export PYTHONPATH=packages/core
python3 -m flowchartcharter
# or
sh scripts/run_api.sh
```

Listens on **`0.0.0.0:8090`** (API; Studio dashboard may use 8080) by default (`FCC_HOST` / `FCC_PORT`).

### Endpoints

| Method | Path | Role |
|--------|------|------|
| `POST` | `/workload/submit` | JSON workload → Boss Agent charter execution |
| `GET` | `/roster/status` | Roster fitness + `termination_risk_index` (TPC) |
| `POST` | `/system/trigger-monday-sync` | Force GM Monday Morning Sync |
| `POST` | `/system/advance-analytics` | Analytics Chief +1 day (EOW if ready) |
| `POST` | `/system/end-of-week` | Force 5-day dossier protocol |
| `POST` | `/system/upgrade-personnel` | Living Playbook remap (e.g. `70B` → `1T`) |
| `GET` | `/health` | Liveness |

Interactive docs: `http://<host>:8080/docs`

### Example

```bash
curl -s -X POST http://127.0.0.1:8080/workload/submit \
  -H 'Content-Type: application/json' \
  -d '{"workload":"Legacy Code Refactor","context_entropy":0.35}'
```

### Live-Wire LLM (optional)

Set env to swap simulation for real model calls (Pydantic-validated returns):

```bash
export FCC_LLM_PROVIDER=xai   # or openai | gemini | mock
export FCC_LLM_API_KEY=...
export FCC_LLM_MODEL=grok-2
```

Workers inject their TPC system prompt + `termination_risk_index` on every outbound call.

---

## Quick start (library)

```bash
python3 examples/run_demo.py
python3 examples/test_api_server.py
python3 scripts/audit_loop.py
```

## Architecture (v1.2)

| Layer | Module |
|-------|--------|
| API Nervous System | `api_server.py` |
| Live-Wire LLM | `llm_bridge.py` |
| System facade | `system.py` |
| Analytics Chief | `analytics.py` |
| Living Playbook | `living_playbook.py` |
| Muscle-Memory VDB | `muscle_memory.py` |
| TPC / Fitness | `fitness.py`, `survival.py` |
| Quantum routing | `quantum.py` |
| Elastic phantoms | `elastic.py` |

## Lifecycle

ST-01 Init → ST-02 Bind → ST-03 Super-step → ST-04 Rhythm Audit → ST-05 Remediate → ST-06 Coach Trust Hand-Off → ST-07 Monday Morning Sync (dossier-driven)

## Continuous audit loop

After every engineering cycle:

```bash
python3 scripts/audit_loop.py
```

Runs pycodestyle · pyflakes · compileall · test suite → writes CXR under `07_CROSS_REFERENCE_REPORTS/`.

## License

Apache-2.0. Open design. Pre-repo gates: continuous-team-audit-loop + loop-engineer.
