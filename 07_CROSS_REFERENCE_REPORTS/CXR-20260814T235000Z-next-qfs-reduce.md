# CXR — Next stage determination (no build)

**Skills:** continuous-team-audit-loop · loop-engineer · rhythm-marker-validator · flowchartcharter-engineering

## Current
OS **8.3**. Local retrieve **7.6**. FCC QFS **6.5**. GraphRAG QFS **8**.

## Weak
`qfs_search` is a flat sentence sort. `bags` counts matching units. There is no per-bag partial and no reduce. Helpfulness is not scored. Components are not bags.

## Determination
**v3.1 Structured QFS Reduce** — `fcc_component` bags (connected components, not Leiden) → map partials → helpfulness reduce. Reduce cannot invent sentences. GraphRAG still HTTP-only.

## Do not do next
Leiden-as-GraphRAG. Live LLM reduce without a key. gVisor.
