/** Studio runtime — Tensor Routing + 5 agent skills (mirrors core v0.5). */

export type AgentStatus = "Active" | "Promoted" | "Demoted" | "Fired";

export interface ExecutionMetrics {
  tokenCost: number;
  executionTime: number;
  qualityScore: number;
  synergyScore: number;
}

export interface Agent {
  id: string;
  name: string;
  role: string;
  status: AgentStatus;
  history: ExecutionMetrics[];
  muscleMemory: Record<string, number>;
  corporateRank: number;
  load: number;
  capability: Record<string, number>;
  talentEligible: boolean;
  layer: "ops" | "exec" | "audit";
}

export type VectorType =
  | "StrategyVector"
  | "BudgetVector"
  | "GovernanceVector"
  | "OpsVector"
  | "RhythmAudit";

export interface ExecVector {
  type: VectorType;
  from?: string;
  charter_id?: string;
  marker?: string;
  quality?: number;
  threshold?: number;
  passed?: boolean;
  trust_signal?: boolean;
  approve_hand_off?: boolean;
  token_spend?: number;
  token_budget?: number;
  halt_if_over?: boolean;
  notes?: string;
  roster_outcomes?: Record<string, string>;
  [key: string]: unknown;
}

export interface PathAmp {
  path: string;
  c: number;
  p: number;
  weight: number;
}

export interface QuantumCollapse {
  agent: string;
  chosenPath: string;
  confidence: number;
  preEntropy: number;
  amplitudes: PathAmp[];
  marker: string;
  quality?: number;
  contextEntropy: number;
  cfoForced: boolean;
}

export interface CharterRun {
  workload: string;
  quality: number;
  trust: boolean;
  remediationLoops: number;
  pathByAgent: Record<string, string>;
  metrics: ExecutionMetrics[];
  auditPassed: boolean;
  governanceApproved: boolean;
  vectors: ExecVector[];
  collapses: QuantumCollapse[];
  entanglement: number;
  meanPreEntropy: number;
  contextEntropy: number;
  qsMean: number;
}

export interface SystemSnapshot {
  roster: Agent[];
  executives: { ceo: string; cfo: string; board: string; gm: string };
  runs: CharterRun[];
  syncOutcomes: Record<string, string>;
  playbook: string[];
  vectors: ExecVector[];
  trustRate: number;
  step: number;
  tokenSpend: number;
  tokenBudget: number;
  lastCollapses: QuantumCollapse[];
  skillsUsed: string[];
}

const PATHS = ["path_A", "path_B", "path_lite"] as const;
const PATH_AFFINITY: Record<string, number> = {
  path_A: 0.15,
  path_B: 0.95,
  path_lite: 0.4,
};
const PATH_COSTS: Record<string, number> = {
  path_A: 220,
  path_B: 380,
  path_lite: 90,
};
const COST_NORM = 300;
const QUALITY_FLOOR = 0.9;
const LR = 0.12;
const DECAY = 0.02;
const K_SYNERGY = 3.0;

export const AGENT_SKILLS = [
  "QueryMuscleMemory",
  "EvaluateRhythmMarker",
  "ExecuteQuantumCollapse",
  "TriggerMondayMorningSync",
  "AdjustCorporateRoster",
] as const;

function uid() {
  return Math.random().toString(36).slice(2, 10);
}

function rand(min: number, max: number) {
  return min + Math.random() * (max - min);
}

function shannonEntropy(probs: number[]): number {
  let ent = 0;
  for (const p of probs) {
    if (p > 1e-15) ent -= p * Math.log2(p);
  }
  return ent;
}

function entropyAffinity(path: string, hCtx: number): number {
  const affinity = PATH_AFFINITY[path] ?? 0.5;
  const match = 1 - Math.abs(affinity - hCtx);
  return 0.4 + 1.6 * match;
}

export function contextEntropyForWorkload(name: string): number {
  const lower = name.toLowerCase();
  let base = 0.25;
  if (/security|audit|messy|legacy|migration/.test(lower)) base = 0.72;
  else if (/api|integration|realtime|telemetry/.test(lower)) base = 0.45;
  return Math.min(1, Math.max(0, base + rand(-0.06, 0.06)));
}

export function buildSuperposition(
  muscle: Record<string, number>,
  hCtx: number,
  remainingBudget: number,
  margin = 500,
): {
  amplitudes: PathAmp[];
  entropy: number;
  dominant: string;
  cfoForced: boolean;
  blocked: string[];
} {
  const raw: Record<string, number> = {};
  for (const p of PATHS) {
    raw[p] = Math.max(1e-9, (muscle[p] ?? 1) * entropyAffinity(p, hCtx));
  }
  const blocked: string[] = [];
  const affordable = Math.max(0, remainingBudget - margin);
  for (const p of PATHS) {
    const cost = PATH_COSTS[p] ?? 200;
    if (cost > affordable && remainingBudget < cost) {
      raw[p] = 0;
      blocked.push(p);
    }
  }
  let cfoForced = false;
  let total = Object.values(raw).reduce((s, w) => s + w, 0);
  if (total <= 1e-12) {
    for (const p of PATHS) raw[p] = p === "path_lite" ? 1 : 0;
    total = 1;
    cfoForced = true;
  }
  const amplitudes: PathAmp[] = PATHS.filter((p) => raw[p] > 1e-12).map((p) => ({
    path: p,
    c: Math.sqrt(raw[p]),
    p: raw[p] / total,
    weight: raw[p],
  }));
  const entropy = shannonEntropy(amplitudes.map((a) => a.p));
  const dominant = amplitudes.reduce((b, a) => (a.p > b.p ? a : b)).path;
  return { amplitudes, entropy, dominant, cfoForced, blocked };
}

export function reinforce(
  muscle: Record<string, number>,
  path: string,
  quality: number,
): Record<string, number> {
  const updated: Record<string, number> = { ...muscle };
  for (const p of PATHS) updated[p] = Math.max(0.05, updated[p] ?? 1);
  if (quality >= QUALITY_FLOOR) {
    updated[path] = Math.min(8, updated[path] * (1 + LR * quality));
    for (const p of PATHS) {
      if (p !== path) updated[p] = Math.max(0.05, updated[p] * (1 - DECAY));
    }
  } else {
    const penalty = LR * (QUALITY_FLOOR - quality + 0.1);
    updated[path] = Math.max(0.05, updated[path] * (1 - penalty));
    for (const p of PATHS) {
      if (p !== path) updated[p] = Math.min(8, updated[p] * (1 + DECAY * 2));
    }
  }
  return updated;
}

/** Q_s = exp(−k · D) */
export function synergyQs(d: number, k = K_SYNERGY): number {
  return Math.exp(-k * Math.min(1, Math.max(0, d)));
}

export function createRoster(): Agent[] {
  return [
    {
      id: uid(),
      name: "Worker-1",
      role: "Key Player — Data Extraction",
      status: "Active",
      history: [],
      muscleMemory: { path_A: 1.4, path_B: 0.9, path_lite: 0.8 },
      corporateRank: 1,
      load: 0,
      capability: { extraction: 1, general: 0.5 },
      talentEligible: true,
      layer: "ops",
    },
    {
      id: uid(),
      name: "Worker-2",
      role: "Key Player — Validation",
      status: "Active",
      history: [],
      muscleMemory: { path_A: 1.0, path_B: 1.2, path_lite: 0.9 },
      corporateRank: 1,
      load: 0,
      capability: { validation: 1, general: 0.5 },
      talentEligible: true,
      layer: "ops",
    },
    {
      id: uid(),
      name: "Worker-3",
      role: "Position Manager — Synthesizer",
      status: "Active",
      history: [],
      muscleMemory: { path_A: 1.5, path_B: 0.7, path_lite: 1.0 },
      corporateRank: 2,
      load: 0,
      capability: { synthesis: 1, general: 0.6 },
      talentEligible: true,
      layer: "ops",
    },
    {
      id: uid(),
      name: "Validator-1",
      role: "Rhythm Marker Validator",
      status: "Active",
      history: [],
      muscleMemory: { path_A: 1, path_B: 1, path_lite: 1 },
      corporateRank: 4,
      load: 0,
      capability: { audit: 1, general: 0.4 },
      talentEligible: false,
      layer: "audit",
    },
  ];
}

export function fitness(history: ExecutionMetrics[]): number {
  if (!history.length) return 0;
  const n = history.length;
  const q = history.reduce((s, m) => s + m.qualityScore, 0) / n;
  const t = history.reduce((s, m) => s + m.executionTime, 0) / n;
  const c = history.reduce((s, m) => s + m.tokenCost, 0) / n;
  const sy = history.reduce((s, m) => s + m.synergyScore, 0) / n;
  const rhythm = t > 0 ? 1 / t : 0;
  return 0.4 * q + 0.3 * rhythm - 0.15 * (c / COST_NORM) + 0.2 * sy;
}

function executeUnit(agent: Agent, path: string, qualityBias = 0): ExecutionMetrics {
  let cost: number;
  if (path === "path_lite") cost = Math.floor(rand(60, 120));
  else if (path === "path_B") cost = Math.floor(rand(280, 450));
  else cost = Math.floor(rand(140, 280));
  const m: ExecutionMetrics = {
    tokenCost: cost,
    executionTime: rand(0.4, 1.8),
    qualityScore: Math.min(1, Math.max(0, rand(0.78, 0.98) + qualityBias)),
    synergyScore: rand(0.85, 1),
  };
  agent.history.push(m);
  agent.load = Math.min(1, agent.load + 0.08);
  return m;
}

function rhythmAudit(
  charterId: string,
  quality: number,
  threshold: number,
  loops: number,
): ExecVector {
  const passed = quality >= threshold && loops <= 3;
  return {
    type: "RhythmAudit",
    marker: "gate",
    charter_id: charterId,
    quality: Number(quality.toFixed(4)),
    threshold,
    passed,
    remediation_loops: loops,
    blocking_issues: passed ? [] : [`quality ${quality.toFixed(3)} < ${threshold}`],
  };
}

function collapseForAgent(
  agent: Agent,
  marker: string,
  hCtx: number,
  remaining: number,
  qualityBias = 0,
): { collapse: QuantumCollapse; metrics: ExecutionMetrics } {
  const pre = buildSuperposition(agent.muscleMemory, hCtx, remaining);
  const chosen = pre.dominant;
  let bias = qualityBias;
  if (chosen === "path_B" && hCtx >= 0.55) bias += 0.06;
  else if (chosen === "path_A" && hCtx < 0.4) bias += 0.04;
  else if (chosen === "path_lite") bias -= 0.03;
  const metrics = executeUnit(agent, chosen, bias);
  agent.muscleMemory = reinforce(agent.muscleMemory, chosen, metrics.qualityScore);
  const collapse: QuantumCollapse = {
    agent: agent.name,
    chosenPath: chosen,
    confidence: 1,
    preEntropy: Number(pre.entropy.toFixed(4)),
    amplitudes: pre.amplitudes.map((a) => ({
      path: a.path,
      c: Number(a.c.toFixed(4)),
      p: Number(a.p.toFixed(4)),
      weight: Number(a.weight.toFixed(4)),
    })),
    marker,
    quality: Number(metrics.qualityScore.toFixed(4)),
    contextEntropy: Number(hCtx.toFixed(4)),
    cfoForced: pre.cfoForced,
  };
  return { collapse, metrics };
}

export function runCharter(
  roster: Agent[],
  workload: string,
  prevVectors: ExecVector[],
  tokenSpend: number,
  tokenBudget: number,
): { run: CharterRun; vectors: ExecVector[]; tokenSpend: number; skillsUsed: string[] } {
  const vectors: ExecVector[] = [...prevVectors];
  const hCtx = contextEntropyForWorkload(workload);
  const skillsUsed = [
    "QueryMuscleMemory",
    "ExecuteQuantumCollapse",
    "EvaluateRhythmMarker",
  ];

  vectors.push({
    type: "StrategyVector",
    from: "CEO",
    charter_id: workload,
    priority: 0.7,
    budget_cap_tokens: tokenBudget,
    quality_floor: 0.9,
  });

  const metrics: ExecutionMetrics[] = [];
  const pathByAgent: Record<string, string> = {};
  const collapses: QuantumCollapse[] = [];
  const qualities: number[] = [];
  let spendAcc = 0;

  for (const a of roster) {
    if (a.status === "Fired" || a.layer !== "ops") continue;
    const remaining = tokenBudget - tokenSpend - spendAcc;
    const { collapse, metrics: m } = collapseForAgent(a, "superstep", hCtx, remaining);
    pathByAgent[a.name] = collapse.chosenPath;
    collapses.push(collapse);
    metrics.push(m);
    qualities.push(m.qualityScore);
    spendAcc += m.tokenCost;
  }

  let quality = metrics.length
    ? metrics.reduce((s, m) => s + m.qualityScore, 0) / metrics.length
    : 0;
  let loops = 0;
  let audit = rhythmAudit(workload, quality, 0.9, loops);
  vectors.push(audit);

  while (!audit.passed && loops < 3) {
    loops += 1;
    const batch: ExecutionMetrics[] = [];
    for (const a of roster) {
      if (a.status === "Fired" || a.layer !== "ops") continue;
      const remaining = tokenBudget - tokenSpend - spendAcc;
      const { collapse, metrics: m } = collapseForAgent(
        a,
        `remediate#${loops}`,
        hCtx,
        remaining,
        0.12,
      );
      collapses.push(collapse);
      batch.push(m);
      qualities.push(m.qualityScore);
      spendAcc += m.tokenCost;
    }
    metrics.push(...batch);
    quality = batch.reduce((s, m) => s + m.qualityScore, 0) / Math.max(batch.length, 1);
    audit = rhythmAudit(workload, quality, 0.9, loops);
    vectors.push(audit);
  }

  const nextSpend = tokenSpend + spendAcc;
  vectors.push({
    type: "BudgetVector",
    from: "CFO",
    charter_id: workload,
    token_spend: nextSpend,
    token_budget: tokenBudget,
    cost_penalty_gamma: 0.001,
    halt_if_over: nextSpend > tokenBudget,
  });

  const trust = Boolean(audit.passed) && quality >= 0.9;
  vectors.push({
    type: "GovernanceVector",
    from: "Board",
    charter_id: workload,
    trust_signal: trust,
    approve_hand_off: trust,
    notes: trust ? "hand-off approved" : "hand-off withheld",
  });

  const qsMean = synergyQs(0);
  const meanPreEntropy =
    collapses.length > 0
      ? collapses.reduce((s, c) => s + c.preEntropy, 0) / collapses.length
      : 0;
  const entanglement =
    qualities.length >= 2
      ? qualities.slice(0, -1).reduce((s, q, i) => {
          const dProxy = 1 - Math.sqrt(q * qualities[i + 1]);
          return s + synergyQs(dProxy);
        }, 0) /
        (qualities.length - 1)
      : qualities[0] ?? 0;

  return {
    run: {
      workload,
      quality,
      trust,
      remediationLoops: loops,
      pathByAgent,
      metrics,
      auditPassed: Boolean(audit.passed),
      governanceApproved: trust,
      vectors: vectors.slice(-6),
      collapses,
      entanglement: Number(entanglement.toFixed(4)),
      meanPreEntropy: Number(meanPreEntropy.toFixed(4)),
      contextEntropy: Number(hCtx.toFixed(4)),
      qsMean: Number(qsMean.toFixed(4)),
    },
    vectors,
    tokenSpend: nextSpend,
    skillsUsed,
  };
}

export function mondayMorningSync(
  roster: Agent[],
  prevVectors: ExecVector[],
  tokenSpend: number,
  tokenBudget: number,
  lastTrust: boolean,
  lastQuality: number,
): {
  outcomes: Record<string, string>;
  playbook: string[];
  vectors: ExecVector[];
} {
  const benchmark = 0.65;
  const outcomes: Record<string, string> = {};
  const playbook: string[] = [];
  const fitnessSnap: Record<string, number> = {};

  for (const a of roster) {
    if (!a.talentEligible || !a.history.length) continue;
    const f = fitness(a.history);
    fitnessSnap[a.name] = Number(f.toFixed(4));
    if (f >= benchmark * 1.15) {
      a.status = "Promoted";
      a.corporateRank = Math.min(10, a.corporateRank + 1);
      outcomes[a.name] = "PROMOTED";
      playbook.push(`Promote ${a.name}: F=${f.toFixed(3)}`);
    } else if (f < benchmark * 0.55) {
      a.status = "Fired";
      outcomes[a.name] = "FIRED";
      playbook.push(`Fire ${a.name}: F=${f.toFixed(3)}`);
    } else {
      a.status = "Active";
      outcomes[a.name] = "RETAINED";
      playbook.push(
        `Retain ${a.name}: F=${f.toFixed(3)} · A=${(a.muscleMemory.path_A ?? 1).toFixed(2)} B=${(a.muscleMemory.path_B ?? 1).toFixed(2)} lite=${(a.muscleMemory.path_lite ?? 1).toFixed(2)}`,
      );
    }
  }

  const vectors = [...prevVectors];
  vectors.push({
    type: "OpsVector",
    from: "GM",
    charter_id: "downtime-sync",
    roster_outcomes: { ...outcomes },
    fitness_snapshot: fitnessSnap,
    playbook_updates: playbook.slice(0, 8),
  });
  vectors.push({
    type: "StrategyVector",
    from: "CEO",
    charter_id: "downtime-sync",
    priority: 0.6,
    budget_cap_tokens: tokenBudget,
    quality_floor: 0.9,
  });
  vectors.push({
    type: "BudgetVector",
    from: "CFO",
    charter_id: "downtime-sync",
    token_spend: tokenSpend,
    token_budget: tokenBudget,
    halt_if_over: tokenSpend > tokenBudget,
  });
  vectors.push({
    type: "GovernanceVector",
    from: "Board",
    charter_id: "downtime-sync",
    trust_signal: lastTrust,
    approve_hand_off: lastTrust && lastQuality >= 0.9,
    notes: lastTrust ? "fleet stable" : "review remediation",
  });

  return { outcomes, playbook, vectors };
}

export function initialSnapshot(): SystemSnapshot {
  return {
    roster: createRoster(),
    executives: {
      ceo: "CEO-Prime",
      cfo: "CFO-Ledger",
      board: "Board-Spectre",
      gm: "Alpha-GM",
    },
    runs: [],
    syncOutcomes: {},
    playbook: [],
    vectors: [],
    trustRate: 0,
    step: 0,
    tokenSpend: 0,
    tokenBudget: 50_000,
    lastCollapses: [],
    skillsUsed: [],
  };
}

export const PHASES = [
  { id: "ST-01", name: "Charter Init", marker: "start" },
  { id: "ST-02", name: "Voluntary Bind", marker: "bind" },
  { id: "ST-03", name: "Super-Step", marker: "superstep" },
  { id: "ST-04", name: "Rhythm Audit", marker: "gate" },
  { id: "ST-05", name: "Muscle Memory", marker: "loop" },
  { id: "ST-06", name: "Coach Trust", marker: "handoff" },
  { id: "ST-07", name: "Monday Sync", marker: "sync" },
] as const;

export const WORKLOADS = [
  "Enterprise Data Migration",
  "API Integration Synthesis",
  "Security Audit Routing",
  "Realtime Telemetry Charter",
] as const;
