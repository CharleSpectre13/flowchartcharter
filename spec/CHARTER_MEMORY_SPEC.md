# SPEC — Incremental Charter Memory (v2.7.0)

**Authority:** Spec-Anchored  
**Skills:** graph-engineering · graphify · graphrag-pipeline (sub-flow) · loop-engineer · rhythm-marker-validator · advanced-coding

## Outcomes

1. A TextUnit can be ingested; entity count rises; `full_rebuild` stays false.
2. A fact only in the new unit is retrievable via `fcc_kg_delta` or `fcc_lazy`.
3. `claimed_graphrag` stays false unless GraphRAG HTTP succeeded.
4. Reindex loop: extract ≠ verify. Same role → refuse.
5. Prior suites remain green.

## Scope

**In:** `charter_memory.py`, KG delta + lazy, RetrievalPort flags, reindex loop, tests.  
**Out:** Leiden-as-GraphRAG, vendor SDKs, live LLM extract, gVisor.

## Prior decisions

Charter owns the path. GraphRAG is a tool. Halt Law and Earned Rhythm stay.

## Verify

`python3 examples/test_v27_charter_memory.py`
