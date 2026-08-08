# FlowChartCharter

### The execution-first multi-agent paradigm — after GraphRAG

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![PyPI](https://img.shields.io/badge/pip-flowchart--charter--engine-green.svg)](https://pypi.org/project/flowchart-charter-engine/)
[![Version](https://img.shields.io/badge/core-v1.4.0-informational.svg)](packages/core)
[![CI](https://img.shields.io/badge/CI-Continuous%20Audit%20Loop-purple.svg)](.github/workflows/audit.yml)

> **Two lines to instantiate a Boss Agent. One YAML file to charter an enterprise.**

```bash
pip install flowchart-charter-engine
```

```python
from flowchartcharter import FlowChartCharterSystem

system = FlowChartCharterSystem()
result = system.execute_charter("Legacy Code Refactor")
print(result["quality"], result["trust"], result["playbook_mode"])
```

---

## Manifesto: Why GraphRAG Is Not Enough

GraphRAG answered a real question: *what is related, and how do I retrieve it?*

In production multi-agent shops, that question is no longer the bottleneck. The bottleneck is:

| GraphRAG failure mode | What it costs |
|-----------------------|---------------|
| **Hallucinated retrieval paths** | Silent wrong answers with confident prose |
| **Token bloat** | Re-reason every job from chunks; bill compounds |
| **Loop exhaustion** | Humans stay in the loop to babysit every hop |
| **No accountability** | Agents don't fear failure; drift is free |
| **No muscle memory** | Yesterday's perfect trajectory dies after the chat |

**FlowChartCharter flips the objective.**

We do not optimize *relatedness*. We optimize **the fastest reliable path to execute**, under budget, under schema, under fear of termination — until the engineer can **leave the live loop** (Coach Trust Hand-Off).

Graph tools remain **callable sub-flows** when pure discovery is required.  
The **Charter owns the workflow.**

---

## Architectural Pillars

### 1. The Deterministic FlowChart (YAML Charterfile)

The Head Coach writes one file. The compiler hydrates the entire enterprise.

```yaml
playbook_name: "Legacy Auth Refactor"
version: "1.0.0"
global_cfo_ceiling: 3500
roster_requisition:
  - role: "Data_Sanitizer"
    capabilities: ["json_parsing", "regex"]
  - role: "Code_Architect"
    capabilities: ["python_ast", "security_refactor"]
flow_units:
  - id: "U1_Ingest_Clean"
    assigned_role: "Data_Sanitizer"
    expected_tokens: 500
    schema:
      clean_code: "string"
      variables_found: "list[string]"
```

Schemas become **live Pydantic models at runtime**. Live-Wire LLM output is forced through them. Failures are not warnings — they are **entanglement errors**.

### 2. Teleological Performance Constraints (TPC / Fear Metric)

Every node carries a `termination_risk_index`.

- High risk → temperature collapses toward zero, schema locks, creativity caps  
- Schema divergence increments the immutable telemetry ledger  
- Monday Morning Sync **fires bloat, not hard work**

Fitness is teleological: success rate + bounded speed − token *bloat* + synergy.  
Agents that wander die. Agents that execute cleanly promote.

### 3. The Boss Agent Corporate Hierarchy

```
Executive Board (CEO strategy · CFO budget gate)
        ↓
General Manager / Boss Agent  (Monday Sync · dossier execution)
        ↓
Position Managers / Key Players / Coaches
        ↓
Elastic Phantoms (capability gaps filled at runtime)
```

JSON blackboard. Volunteer bind. Quantum-inspired path collapse under CFO ceilings.  
The engineer is the Head Coach — not a permanent copilot.

### 4. Muscle-Memory Vectors

Successful trajectories are committed — not text chunks.

- State-vector encode → cosine / ANN retrieve  
- HIT: reuse Flow Path + prompt tweak (cheat code)  
- MISS: fall back to standard Charter pathing  
- Production backends: **in-memory · Qdrant · Pinecone**

GraphRAG retrieves *documents*. Muscle-Memory retrieves **proven execution**.

### 5. The 5-Day Analytics Film Room

The Analytics Chief does not guess on Monday morning.

1. Ingest daily cycle telemetry  
2. Close five days of moving-average film  
3. Emit a **Roster Recommendation Dossier**  
4. Boss Agent executes promote / demote / fire / lean re-hire  

Board-driven talent management. Not vibes.

---

## Install

### pip (public package)

```bash
pip install flowchart-charter-engine
```

Optional vector SDKs:

```bash
pip install "flowchart-charter-engine[vector]"
```

### From source

```bash
git clone https://github.com/CharleSpectre13/flowchartcharter.git
cd flowchartcharter
pip install -e ".[dev]"
export PYTHONPATH=packages/core
```

---

## 60-second tour

```python
from flowchartcharter import FlowChartCharterSystem

system = FlowChartCharterSystem(seed=42)

# Living Playbook + Muscle-Memory + Live-Wire (mock offline)
out = system.execute_charter(
    "Legacy Code Refactor",
    context_entropy=0.35,
)
assert out["trust"] or out["quality"] > 0.8

# Head Coach: load a Charterfile
system.load_playbook("examples/charterfiles/legacy_auth_refactor.yaml")
run = system.execute_compiled("Refactor legacy auth module")
print(run["flow_path"], run["units_ok"], run["quality"])
```

### API Nervous System

```bash
export PYTHONPATH=packages/core
python -m flowchartcharter
# → http://0.0.0.0:8090/docs
```

| Method | Path | Role |
|--------|------|------|
| `POST` | `/workload/submit` | JSON job → Boss Agent |
| `GET` | `/roster/status` | Fitness + termination risk |
| `POST` | `/system/load-playbook` | Upload Charterfile YAML |
| `POST` | `/system/execute-compiled` | Run active playbook |
| `POST` | `/system/trigger-monday-sync` | Force talent prune |
| `POST` | `/system/advance-analytics` | Film-room +1 day |

---

## Enterprise Docker

One command boots **API + Qdrant Muscle-Memory**:

```bash
docker compose up --build
```

```text
engine   → http://localhost:8090
qdrant   → http://localhost:6333
docs     → http://localhost:8090/docs
```

Live LLM (optional):

```bash
export FCC_LLM_PROVIDER=xai   # openai | gemini | mock
export FCC_LLM_API_KEY=...
docker compose up --build
```

---

## Fitness (patched)

```
F(x) = α · (Q_success / Q_total)
     + β · exp(−Δt / expected_t)       # bounded speed
     − γ · max(0, tokens − expected)/N # bloat only
     + Q_entanglement
```

---

## Lifecycle

```
ST-01 Init → ST-02 Bind → ST-03 Super-step (Live-Wire)
  → ST-04 Rhythm Audit → ST-05 Remediate
  → ST-06 Coach Trust Hand-Off
  → ST-07 Monday Morning Sync (dossier-driven)
```

---

## Continuous Audit Loop

Every push to `main` runs Pepe standards:

- pycodestyle · pyflakes · black --check  
- compileall · example suite · `scripts/audit_loop.py`  
- wheel/sdist build artifact  

Locally:

```bash
python scripts/audit_loop.py
```

---

## Package layout

```text
packages/core/flowchartcharter/   # installable core
  api_server.py                   # FastAPI Nervous System
  playbook_compiler.py            # YAML Charterfile → dynamic Pydantic
  production.py                   # LLMExecutionClient + vector backends
  muscle_memory.py / living_playbook.py
  analytics.py / survival.py / quantum.py
examples/charterfiles/            # Head Coach DSL samples
docker-compose.yml                # API + Qdrant
.github/workflows/audit.yml       # CI
```

---

## License

Apache-2.0. Open design. Build the charter. Fire the bloat. Exit the loop.

**FlowChartCharter** — *execution first. fear real. memory earned.*
