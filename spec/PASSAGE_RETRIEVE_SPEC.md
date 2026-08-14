# SPEC — Passage Retrieve + Supersede (v2.9.0)

## Outcomes

1. TextUnits are searchable (`fcc_units`). Hits cite `TU-…`.
2. Fusion includes the units lane. SIMPLE stays muscle.
3. New episode on the same goal sets prior unit `valid=false`.
4. Rhythm fails `stale_hit` if a hit cites an invalidated unit.
5. `claimed_graphrag` still requires HTTP.

## Out

Leiden-as-GraphRAG. Live LLM extract. New embed SDK (reuse EmbeddingProvider).
