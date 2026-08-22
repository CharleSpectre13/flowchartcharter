# FlowChartCharter

**Accountable house for multi-agent work.**  
Map (YAML Charter) + Car (harness) + House (durable notebook) + optional Grok mouth.

No paid keys required for the core path.  
Apache-2.0 · open design · offline-first.

> **For people:** Accountable house — YAML Charter + harness (Halt, Earned Rhythm) + durable notebook. Optional Grok. No key required. Apache-2.0.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/core-v3.4.1-informational.svg)](packages/core)
[![CI](https://img.shields.io/badge/CI-Continuous%20Audit%20Loop-purple.svg)](.github/workflows/audit.yml)

```bash
pip install "git+https://github.com/CharleSpectre13/flowchartcharter.git"
# optional live mouth
export XAI_API_KEY=...
```

```python
from flowchartcharter import FlowChartCharterSystem, LiveModel, first_day

system = FlowChartCharterSystem()
# optional: house = first_day()          # durable notebook starter
# optional: brain = LiveModel.from_env() # live only when key is present
```

---

## What it is (current reality)

FlowChartCharter is an execution-and-quality-first multi-agent framework built around four durable pieces:

| Piece | Role | Status today |
|-------|------|--------------|
| **Map** | Versioned YAML Charterfile that owns the workflow | Implemented (playbook compiler + schemas) |
| **Car** | Harness with Halt law, receipts, sandbox, Earned Rhythm | Implemented and probe-tested |
| **House** | Durable notebook (`house.jsonl` / first-day starter) | Implemented |
| **Mouth** | Optional LiveModel (Grok / Ollama) | Optional; offline path works without it |

GraphRAG and other graph tools remain **callable sub-flows only**. The Charter owns the path. Agents do not search their way out of a job under time pressure.

Core safety contracts that are live:

- **Halt law** — process chokepoint; side-effects can be refused
- **Earned Rhythm** — quality comes from evidence only; `force_quality` and self-grade are banned
- **Maker ≠ Audit Manager** — independent rhythm markers and system-audit probes
- **Stop conditions** — max iterations, consecutive-failure halt, pilot required before auto-mode

See `constitution/constitution.md`, `loop-engineering/Contract/stop-conditions.md`, and the latest Cross-Reference Report under `07_CROSS_REFERENCE_REPORTS/`.

---

## Install

**Recommended (source tracks the honest design):**

```bash
git clone https://github.com/CharleSpectre13/flowchartcharter.git
cd flowchartcharter
pip install -e ".[dev]"
export PYTHONPATH=packages/core
```

Or install directly from git:

```bash
pip install "git+https://github.com/CharleSpectre13/flowchartcharter.git"
```

Optional vector SDK (Qdrant client):

```bash
pip install "flowchart-charter-engine[vector]"
```

Live LLM is opt-in. The system never requires a key to start.

---

## Architecture (as designed and present)

1. **YAML Charterfile** → compiled into live Pydantic models and flow units  
2. **Boss / roster hierarchy** with fitness, risk index, and Monday Morning Sync  
3. **Muscle-Memory** — successful trajectories stored and retrieved (in-memory default; Qdrant optional)  
4. **Harness** — Halt, receipts, sandbox, earned quality gates  
5. **Durable house** — notebook that survives process death  
6. **Studio** (optional) — TypeScript sources in `studio/`; glanceable UI, not a required path

### Design intent vs GraphRAG

GraphRAG answered *what is related*. Production multi-agent work is bottlenecked by execution under budget, schema, and accountability. FlowChartCharter optimizes the fastest reliable path to execute. Graph tools stay callable sub-flows when pure discovery is needed. The Charter owns the workflow.

### Fitness (as implemented)

```
F(x) = α · (Q_success / Q_total)
     + β · exp(−Δt / expected_t)       # bounded speed
     − γ · max(0, tokens − expected)/N # bloat only
     + Q_entanglement
```

### Lifecycle markers

```
ST-01 Init → ST-02 Bind → ST-03 Super-step
  → ST-04 Rhythm Audit → ST-05 Remediate
  → ST-06 Coach Trust Hand-Off
  → ST-07 Monday Morning Sync
```

---

## CLI & API surfaces

| Command / path | Purpose |
|----------------|---------|
| `fcc run playbook.yaml` | Compile + execute Charterfile |
| `fcc --local …` | Offline / in-memory path |
| `fcc-audit` | Live harness probes |
| `POST /workload/submit` | JSON job → Boss Agent |
| `POST /system/load-playbook` | Upload Charterfile YAML |
| `POST /system/execute-compiled` | Run active playbook |
| `GET /metrics` | Prometheus metrics |

```bash
export PYTHONPATH=packages/core
python -m flowchartcharter
# → http://0.0.0.0:8090/docs
```

Docker path (API + optional Qdrant):

```bash
docker compose up --build
```

---

## Current status (honest)

- Design & core contracts: **GREEN** (constitution, Halt, Earned Rhythm, probes)
- Monorepo honesty: **GREEN** (studio source complete; satellites are pure redirects)
- First-day stranger experience & independent regression suite: still hardening
- Production durability under kill/restart + claim-reality CI gate: **target**, not claim

Run the live audit yourself:

```bash
PYTHONPATH=packages/core python3 loop-engineering/Ops/run-team-audit-loop.py
PYTHONPATH=packages/core python3 examples/test_v26_earned_rhythm.py
```

---

## Monorepo

**Canonical repo:** https://github.com/CharleSpectre13/flowchartcharter

| Former satellite | Now lives at |
|---|---|
| `flowchartcharter-loop` | `loop-engineering/`, audit scripts, CXRs |
| `flowchartcharter-studio` | `studio/` |

Satellites are read-only redirects. All new work lands here.

---

## Projected production-ready target (A-range)

These items are the explicit goals for “finished and production ready.” They are **not** claimed as complete today:

- Independent maker-checker CI with frozen golden fixtures
- Durable `house.jsonl` checkpointing proven under process kill + restart
- Claim-reality gate in CI (README statements vs measured probe results)
- One-command offline first-day demo that produces clear receipts
- Studio remains optional; primary path stays map + car + house
- Explicit maturity badges and no self-grade path anywhere in production loops
- Regression suite that covers Halt round-trip, rhythm independence, and citation honesty under load

When the above are green under continuous-team-audit-loop, the system moves from “solid open design + working harness” to production-ready.

---

## Package layout

```text
packages/core/flowchartcharter/   # installable core
  system.py / harness.py / kill_law.py / rhythm_gate.py
  playbook_compiler.py / muscle_memory.py / house.py
  system_audit.py / live_model.py / durable_notebook.py
constitution/                     # immutable principles
loop-engineering/                 # contracts, stop-conditions, ops, verifiers
spec/                             # executable SPECs
studio/                           # optional TypeScript dashboard sources
library/ + examples/              # Charterfiles and tests
07_CROSS_REFERENCE_REPORTS/       # audit artifacts
```

---

## License

Apache-2.0.  
Open design. Build the charter. Keep the fear real. Exit the loop when the evidence earns it.

**FlowChartCharter** — map, car, house, optional mouth.
