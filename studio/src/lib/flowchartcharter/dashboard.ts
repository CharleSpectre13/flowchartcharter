/**
 * Master Dashboard engine — Gemini reference + FlowChartCharter core.
 * Simple control surface for charter execution, Muscle-Memory, and Monday Sync.
 */

export type AgentStatus = "ACTIVE" | "PROMOTED" | "FIRED";
export type LogKind = "info" | "success" | "warning" | "error";
export type Rhythm = "idle" | "running" | "sync";

export interface RosterAgent {
  id: string;
  role: string;
  success: number;
  total: number;
  tokens: number;
  errors: number;
  status: AgentStatus;
}

export interface MemoryRecord {
  id: string;
  jobType: string;
  flowPath: string[];
  entanglement: number;
  tweak: string;
}

export interface LogLine {
  id: string;
  t: string;
  kind: LogKind;
  text: string;
}

export interface DashboardState {
  roster: RosterAgent[];
  memory: MemoryRecord[];
  cfoBudget: number;
  workload: string;
  entropy: number;
  threshold: number;
  logs: LogLine[];
  lastPath: string[] | null;
  lastHit: boolean | null;
  runs: number;
  hits: number;
  rhythm: Rhythm;
}

let logSeq = 0;

function stamp(): string {
  logSeq += 1;
  return `#${logSeq}`;
}

function uid(): string {
  logSeq += 1;
  return `L${logSeq}`;
}

export function fitnessScore(a: RosterAgent): number {
  const q = a.success / Math.max(1, a.total);
  const ent = Math.exp(-0.5 * a.errors);
  return q * 0.7 + ent * 0.3;
}

export function createDashboard(): DashboardState {
  logSeq = 0;
  return {
    roster: [
      {
        id: "A1",
        role: "Data Cleanser",
        success: 48,
        total: 50,
        tokens: 240,
        errors: 0,
        status: "ACTIVE",
      },
      {
        id: "A2",
        role: "Code Generator",
        success: 41,
        total: 50,
        tokens: 1200,
        errors: 4,
        status: "ACTIVE",
      },
      {
        id: "A3",
        role: "QA Validator",
        success: 49,
        total: 50,
        tokens: 400,
        errors: 0,
        status: "PROMOTED",
      },
    ],
    memory: [
      {
        id: "MEM-101",
        jobType: "Refactor legacy authentication module with modern tokens",
        flowPath: ["U1_Ingest", "U2_Sanitize", "U5_SecureTokenReplace"],
        entanglement: 0.98,
        tweak: "Enforce strict Bearer header schema validation.",
      },
      {
        id: "MEM-9921",
        jobType: "Legacy Code Refactor",
        flowPath: ["U1_Ingest", "U4_TypeSanitize", "U8_DeterministicRefactor"],
        entanglement: 0.98,
        tweak: "Ensure strict camelCase enforcement during token parsing.",
      },
    ],
    cfoBudget: 1500,
    workload: "Refactor legacy authentication module with modern tokens",
    entropy: 0.2,
    threshold: 0.8,
    logs: [
      {
        id: "boot",
        t: "#0",
        kind: "info",
        text: "FlowChartCharter ready. Enter a workload and run the charter.",
      },
    ],
    lastPath: null,
    lastHit: null,
    runs: 0,
    hits: 0,
    rhythm: "idle",
  };
}

function pushLog(
  state: DashboardState,
  text: string,
  kind: LogKind = "info",
): DashboardState {
  const line: LogLine = { id: uid(), t: stamp(), kind, text };
  return {
    ...state,
    logs: [...state.logs, line].slice(-80),
  };
}

function queryMemory(
  memory: MemoryRecord[],
  workload: string,
  threshold: number,
): MemoryRecord | null {
  const lower = workload.toLowerCase();
  let best: MemoryRecord | null = null;
  let bestScore = -1;
  for (const m of memory) {
    if (m.entanglement < threshold) continue;
    const job = m.jobType.toLowerCase();
    const words = lower.split(/\s+/).filter((w) => w.length > 3);
    const hits = words.filter((w) => job.includes(w)).length;
    const score = hits / Math.max(1, words.length) + m.entanglement * 0.1;
    if (hits > 0 && score > bestScore) {
      bestScore = score;
      best = m;
    }
  }
  return best;
}

export function executeWorkload(state: DashboardState): DashboardState {
  let s: DashboardState = {
    ...state,
    rhythm: "running",
    logs: [...state.logs],
  };
  const unitCost = s.entropy > 0.6 ? 800 : 500;

  s = pushLog(s, "--- NEW WORKLOAD CHARTER ---", "info");
  s = pushLog(
    s,
    `Job: "${s.workload}" | Entropy: ${s.entropy.toFixed(1)} | CFO: ${s.cfoBudget}`,
    "info",
  );
  s = pushLog(s, "[Muscle-Memory] Querying past execution trajectories…", "info");

  const matched = queryMemory(s.memory, s.workload, s.threshold);

  if (matched) {
    s = pushLog(
      s,
      `HIT — matched ${matched.id}; reusing verified path`,
      "success",
    );
    s = pushLog(s, `Path: ${matched.flowPath.join(" → ")}`, "success");
    s = pushLog(s, `Prompt tweak: "${matched.tweak}"`, "success");
    s = pushLog(s, "Execution complete — deterministic replay, low cost.", "success");
    const roster = s.roster.map((a) =>
      a.status === "FIRED"
        ? a
        : {
            ...a,
            success: a.success + 1,
            total: a.total + 1,
            tokens: a.tokens + Math.floor(unitCost / 3),
          },
    );
    return {
      ...s,
      roster,
      lastPath: matched.flowPath,
      lastHit: true,
      runs: s.runs + 1,
      hits: s.hits + 1,
      rhythm: "idle",
    };
  }

  s = pushLog(
    s,
    `MISS — no trajectory above threshold ${s.threshold}. Quantum Router…`,
    "warning",
  );

  if (unitCost > s.cfoBudget) {
    s = pushLog(
      s,
      `CFO INTERRUPT: estimated cost ~${unitCost} exceeds budget ${s.cfoBudget}. Raise ceiling or simplify.`,
      "error",
    );
    return {
      ...s,
      lastPath: null,
      lastHit: false,
      runs: s.runs + 1,
      rhythm: "idle",
    };
  }

  s = pushLog(s, "Wave function collapse at Rhythm Marker…", "info");
  let path: string[];
  if (s.entropy >= 0.7) {
    path = ["U1_Ingest", "U3_DataCleanse", "U9_DeterministicExecute"];
    s = pushLog(s, "High entropy → data-cleansing path selected", "info");
  } else {
    path = ["U1_Ingest", "U4_SchemaEnforce", "U9_DeterministicExecute"];
    s = pushLog(s, "Low entropy → standard path selected", "info");
  }
  s = pushLog(s, `Collapsed → ${path.join(" → ")}`, "success");

  const newMem: MemoryRecord = {
    id: `MEM-${100 + s.runs + s.memory.length}`,
    jobType: s.workload,
    flowPath: path,
    entanglement: 0.96,
    tweak: "Auto-committed during live execution for future Muscle-Memory hits.",
  };
  s = pushLog(s, `Trajectory ${newMem.id} committed to Muscle-Memory DB`, "info");

  const roster = s.roster.map((a) => {
    if (a.status === "FIRED") return a;
    const extraErr = a.id === "A2" ? 1 : 0;
    return {
      ...a,
      success: a.success + (extraErr ? 0 : 1),
      total: a.total + 1,
      tokens: a.tokens + Math.floor(unitCost / 3) + (a.id === "A2" ? 200 : 0),
      errors: a.errors + extraErr,
    };
  });

  return {
    ...s,
    roster,
    memory: [...s.memory, newMem],
    lastPath: path,
    lastHit: false,
    runs: s.runs + 1,
    rhythm: "idle",
  };
}

export function mondayMorningSync(state: DashboardState): DashboardState {
  let s: DashboardState = {
    ...state,
    rhythm: "sync",
    logs: [...state.logs],
  };
  s = pushLog(s, "======== MONDAY MORNING SYNC ========", "info");
  s = pushLog(s, "Boss Agent reviewing telemetry…", "info");

  const roster: RosterAgent[] = s.roster.map((agent) => {
    if (agent.status === "FIRED") return agent;
    const score = fitnessScore(agent);
    s = pushLog(
      s,
      `${agent.id} ${agent.role} fitness = ${score.toFixed(3)}`,
      "info",
    );
    if (score < 0.7) {
      s = pushLog(s, `FIRE ${agent.id} — below industry benchmark`, "error");
      return { ...agent, status: "FIRED" };
    }
    if (score > 0.9) {
      s = pushLog(s, `PROMOTE ${agent.id} — Key Player tier`, "success");
      return { ...agent, status: "PROMOTED" };
    }
    s = pushLog(s, `RETAIN ${agent.id}`, "info");
    return { ...agent, status: "ACTIVE" };
  });

  s = pushLog(s, "Monday Morning Sync complete. Bar raised.", "success");
  return { ...s, roster, rhythm: "idle" };
}

export function clearLogs(state: DashboardState): DashboardState {
  return {
    ...state,
    logs: [
      {
        id: "cleared",
        t: "#0",
        kind: "info",
        text: "Log cleared. Ready for the next charter.",
      },
    ],
  };
}

export const PRESET_JOBS = [
  "Refactor legacy authentication module with modern tokens",
  "Legacy Code Refactor",
  "Clean messy customer CSV export",
  "Build secure API gateway",
  "Migrate old database tables",
] as const;
