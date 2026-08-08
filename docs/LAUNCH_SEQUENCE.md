# Phase 6 — Public Launch Sequence

## Lock main → Go live

Branch policy: treat `main` as release-ready after CI Continuous Audit Loop is green.

## 1. Show HN (Hacker News)

**Title:**  
Show HN: FlowChartCharter – A zero-hallucination, fear-driven agent orchestrator (GraphRAG alternative)

**Body (draft):**

```text
I built FlowChartCharter after watching multi-agent stacks burn tokens on
GraphRAG-style retrieval loops that still needed a human babysitter.

Instead of optimizing relatedness, FCC optimizes the fastest reliable path
to execute:

• YAML Charterfiles (declarative enterprise workflows)
• Teleological Performance Constraints (termination_risk_index / fear metric)
• Muscle-Memory vectors (reuse proven Flow Paths, not chunks)
• Boss Agent corporate hierarchy + Monday Morning Sync
• 5-day Analytics film room → dossier-driven talent prune

pip install flowchart-charter-engine
fcc --local run library/secops_vulnerability_audit.yaml
fcc monitor   # Rich terminal dashboard

GitHub: https://github.com/CharleSpectre13/flowchartcharter
```

## 2. Product Hunt

Assets to attach:

| Asset | Source |
|-------|--------|
| Sandbox UI | `/ui/` Live Sandbox screenshots |
| Prometheus | Grafana panels on `fcc_node_fear_index`, `fcc_token_spend_total` |
| Terminal CLI | `fcc monitor` + `fcc run` TTY captures |
| CharterHub | library playbook cards |

Tagline: **Execution-first agents. Fear real. Memory earned.**

## 3. Architecture Thread (TPC deep-dive)

Topics:

1. Why GraphRAG token bloat is structural (not a prompt bug)
2. Fitness math: bounded `exp(-Δt/expected)` + delta-token bloat only
3. Lean re-hiring paradox + Phantom Node elastic requisition
4. Coach Trust Hand-Off — when the engineer exits the live loop
5. CharterHub as the DockerHub of agent workflows

## Commands checklist before launch

```bash
pip install -e ".[dev]"
export PYTHONPATH=packages/core
fcc version
fcc --local run library/unstructured_data_etl.yaml
fcc --local monitor --once
fcc --local sync
python scripts/audit_loop.py
```
