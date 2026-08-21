# FlowChartCharter Studio

Interactive glanceable UI for the FlowChartCharter engine (now part of the monorepo).

**Canonical home:** this directory inside https://github.com/CharleSpectre13/flowchartcharter

The former standalone repo `flowchartcharter-studio` is a read-only redirect.

## What lives here

- `src/lib/flowchartcharter/dashboard.ts` — Master Dashboard engine (roster, Muscle-Memory HIT/MISS, Monday Sync)
- `src/lib/flowchartcharter/engine.ts` — Tensor routing, Quantum collapse, Rhythm markers, agent skills
- `src/lib/flowchartcharter/knowledge.ts` — Brain-1 ontology / foundations
- `src/routes/index.tsx` — UI surface
- `src/styles.css` — theme tokens

## Run / develop

Studio is designed to live beside the Python engine. Wire it into your TanStack Start / Vite workspace or use the App Builder.

```bash
# Engine (required for live data)
pip install "git+https://github.com/CharleSpectre13/flowchartcharter.git"
export XAI_API_KEY=...   # optional — LiveModel uses grok-4.5 when set
```

```bash
# Typecheck only from this folder (full Vite config lives in your app workspace)
npm run typecheck
```

Apache-2.0 · Spectre Industries open design
