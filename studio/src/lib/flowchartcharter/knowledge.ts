/** Brain-1 ontology for Studio — Advanced Blueprint + Muscle-Memory VDB. */

export interface Foundation {
  id: string;
  name: string;
  description: string;
  mechanism: string;
  role: string;
  metric: string;
  rhythm: string;
}

export const FOUNDATIONS: Foundation[] = [
  {
    id: "charter",
    name: "Charter",
    description: "Pre-drawn deterministic playbook — agents follow rather than search.",
    mechanism: "Measurement operator M collapses path superposition to 100% confident action.",
    role: "Executive Board / Head Coach",
    metric: "Path accuracy · Determinism confidence 1.0",
    rhythm: "Cheat-sheet blueprint — agents move in unison",
  },
  {
    id: "flow_units",
    name: "Flow Units",
    description: "Type-safe modular work blocks with explicit I/O and exit criteria.",
    mechanism: "|FlowUnit_i⟩ selected via historical success amplitudes c_i × H_ctx affinity.",
    role: "GM / Operations",
    metric: "Token efficiency · Q_success/Q_total",
    rhythm: "Well-oiled machine — zero micro-management",
  },
  {
    id: "rhythm_markers",
    name: "Rhythm Markers",
    description: "Self-auditing checkpoints against quality thresholds + Q_s schema gates.",
    mechanism: "EvaluateRhythmMarker: Q_s = exp(−k·D); fail routes back without human.",
    role: "Position Managers · Key Players · CFO",
    metric: "Quality gate pass rate · Q_s · 1/Δt",
    rhythm: "Entanglement — alignment before commit",
  },
  {
    id: "muscle_memory",
    name: "Muscle-Memory Loop",
    description:
      "Vector DB of verified execution trajectories — not unstructured GraphRAG chunks.",
    mechanism:
      "Four quadrants: state_vector · flow_path · Q_ent · prompt_tweak. HIT → accelerated path.",
    role: "All agents · Boss Agent · QueryMuscleMemory",
    metric: "Hit rate · trajectory reuse · latency vs GraphRAG",
    rhythm: "Cheat codes from history",
  },
  {
    id: "coach_trust",
    name: "Engineer Exit / Coach Trust Hand-Off",
    description: "Earned autonomy when quality gates pass — human exits the flow.",
    mechanism: "Board GovernanceVector approve_hand_off when trust ∧ quality ≥ floor.",
    role: "Head Coach · Board",
    metric: "Trust rate · hand-off approvals",
    rhythm: "Engineer out of the loop",
  },
  {
    id: "monday_sync",
    name: "Monday Morning Sync",
    description: "Downtime RLAIF — fitness, promote/demote/fire, re-weight + commit memories.",
    mechanism: "TriggerMondayMorningSync re-ingests successful_runs into Muscle-Memory VDB.",
    role: "Boss Agent (GM)",
    metric: "F(x) vs industry benchmark · VDB growth",
    rhythm: "Idle compute → fleet optimization",
  },
];

export const MIND_MAP = [
  {
    id: "core",
    title: "Core Concept",
    items: [
      "Execution-first vs GraphRAG retrieval-first",
      "Charter owns the journey",
      "Muscle-Memory beats open-graph RAG",
      "Coach Trust Hand-Off",
    ],
  },
  {
    id: "foundations",
    title: "Foundational Structures",
    items: [
      "Charter",
      "Flow Units",
      "Rhythm Markers",
      "Muscle-Memory Vector DB",
      "Engineer Exit",
      "Monday Morning Sync",
    ],
  },
  {
    id: "hierarchy",
    title: "Corporate Hierarchy",
    items: [
      "CEO",
      "CFO (token economics)",
      "Board",
      "Boss Agent / GM",
      "Position Managers",
      "Key Players",
    ],
  },
  {
    id: "ops",
    title: "Operational Mechanisms",
    items: [
      "Blackboard JSON only",
      "BSP super-steps",
      "QueryMuscleMemory HIT/MISS",
      "Five agent skills",
      "CFO budget matrix",
    ],
  },
  {
    id: "math",
    title: "Mathematical Framework",
    items: [
      "|ψ⟩ = Σ cᵢ|FlowUnitᵢ⟩",
      "H_ctx contextual entropy",
      "Q_s = exp(−k·D)",
      "Cosine state_vector match",
      "F(x) fitness score",
    ],
  },
  {
    id: "goals",
    title: "Strategic Goals",
    items: [
      "Zero-hallucination playbooks",
      "Sub-second accelerated paths",
      "Token/latency savings",
      "Open design standard",
    ],
  },
];

export const HIERARCHY_PYRAMID = [
  { role: "Head Coach (Human Engineer)" },
  { role: "CEO · CFO · Board" },
  { role: "Boss Agent (GM)" },
  { role: "Position Managers" },
  { role: "Key Players · Validators" },
];

export const FLOW_UNIT_BLUEPRINT = [
  { element: "Input schema", fn: "Typed contract", contract: "JSON / Pydantic" },
  { element: "Action", fn: "Deterministic unit work", contract: "Side-effect bounded" },
  { element: "Exit criteria", fn: "Quality + Q_s gate", contract: "≥ floor" },
  { element: "Rhythm marker", fn: "Self-audit checkpoint", contract: "Maker-checker" },
  { element: "Handoff", fn: "Blackboard post", contract: "No NL filler" },
];

export const FITNESS_EQ =
  "F(x) = α·(Q_success/Q_total) + β·(1/Δt) − γ·norm(Tokens) + Q_s";

export const QUANTUM = {
  superposition: "|ψ⟩ = Σ cᵢ |FlowUnitᵢ⟩ · affinity(H_ctx)",
  measurement: "|ExecutedPath⟩ = M|ψ⟩  (CFO matrix pre-gate)",
  synergy: "Q_s = exp(−k · D)",
  note: "HIT on Muscle-Memory skips collapse — replay verified flow_path",
};

export const SKILL_CATALOG = [
  {
    name: "QueryMuscleMemory",
    purpose: "Trajectory cheat-codes (state · path · Q_ent · tweak)",
  },
  { name: "EvaluateRhythmMarker", purpose: "Schema self-audit · Q_s gate" },
  { name: "ExecuteQuantumCollapse", purpose: "Tensor routing decision engine" },
  { name: "TriggerMondayMorningSync", purpose: "RLAIF + VDB re-ingest" },
  { name: "AdjustCorporateRoster", purpose: "PROMOTE | DEMOTE | FIRE" },
];

export const MUSCLE_MEMORY_QUADRANTS = [
  {
    name: "State Embedding",
    field: "state_vector",
    desc: "entropy · size_kb · complexity · error_weight",
  },
  {
    name: "Contextual Action",
    field: "successful_flow_path",
    desc: "Ordered Flow Units that solved this job",
  },
  {
    name: "Synergy Fingerprint",
    field: "entanglement_score",
    desc: "Q_entanglement of the team run",
  },
  {
    name: "Cheat Code",
    field: "prompt_tweak",
    desc: "Prompt/format insight that saved the day",
  },
];
