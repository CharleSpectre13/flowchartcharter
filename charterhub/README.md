# CharterHub

### The open library of FlowChartCharter playbooks  
*(DockerHub for agent workflows)*

CharterHub is the community ecosystem for **YAML Charterfiles** — declarative, schema-enforced enterprise agent workflows that compile into FlowChartCharter engines.

## What belongs here

Production-grade `.yaml` playbooks with:

- `playbook_name` / `version` / `global_cfo_ceiling`
- `roster_requisition` (roles + capabilities)
- `flow_units` with **strict schemas** (dynamic Pydantic at runtime)

## Quick start

```bash
pip install flowchart-charter-engine
fcc run charterhub/playbooks/your_playbook.yaml
# or
fcc run library/secops_vulnerability_audit.yaml --local
```

## Layout

```text
charterhub/
  README.md                 # this file
  CONTRIBUTING.md           # submission standard
  playbooks/
    README.md               # index
    community/              # community submissions (PRs welcome)
```

## Seed library (shipped with engine)

| Playbook | Path |
|----------|------|
| SecOps Vulnerability Audit | `library/secops_vulnerability_audit.yaml` |
| Legacy → React Migration | `library/legacy_to_react_migration.yaml` |
| Unstructured Data ETL | `library/unstructured_data_etl.yaml` |
| Legacy Auth Refactor | `library/legacy_auth_refactor.yaml` |

## Submission checklist

1. Valid YAML; compiles with `fcc run --local`
2. Every flow unit has a non-empty `schema`
3. `expected_tokens` + `expected_latency_ms` set
4. One-paragraph description in PR body
5. Apache-2.0 compatible

## Philosophy

GraphRAG shares *documents*.  
CharterHub shares **execution trajectories** — deterministic charts the Boss Agent can run under TPC fear, Muscle-Memory, and CFO ceilings.

**Fork → write a Charterfile → PR → power the industry.**
