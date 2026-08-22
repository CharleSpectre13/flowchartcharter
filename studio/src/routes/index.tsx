import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Eraser,
  Play,
  RefreshCw,
  Sparkles,
  Users,
  Wallet,
  Zap,
} from "lucide-react";
import {
  PRESET_JOBS,
  clearLogs,
  createDashboard,
  executeWorkload,
  fitnessScore,
  mondayMorningSync,
  type DashboardState,
  type LogKind,
  type RosterAgent,
} from "@/lib/flowchartcharter/dashboard";

export const Route = createFileRoute("/")({
  component: MasterDashboard,
});

function MasterDashboard() {
  const [state, setState] = useState<DashboardState>(() => createDashboard());
  const [busy, setBusy] = useState(false);
  const logEnd = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [state.logs.length]);

  async function onGo() {
    if (busy) return;
    setBusy(true);
    await sleep(180);
    setState((s) => executeWorkload(s));
    setBusy(false);
  }

  async function onSync() {
    if (busy) return;
    setBusy(true);
    await sleep(220);
    setState((s) => mondayMorningSync(s));
    setBusy(false);
  }

  function onReset() {
    setState(createDashboard());
  }

  const activeAgents = state.roster.filter((a) => a.status !== "FIRED").length;

  return (
    <div className="flex min-h-full flex-col bg-bg text-fg">
      <header className="sticky top-0 z-20 border-b border-border bg-surface/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div className="flex items-center gap-3">
            <span className="pulse-dot inline-block h-3 w-3 rounded-full bg-ok" />
            <div>
              <h1 className="text-base font-bold tracking-tight sm:text-lg">
                FlowChartCharter
                <span className="ml-2 rounded border border-primary/40 bg-primary/10 px-2 py-0.5 font-mono text-[10px] font-medium uppercase tracking-widest text-primary">
                  Enterprise Engine v1
                </span>
              </h1>
              <p className="text-xs text-muted">
                Run a charter — agents follow the map
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-xs text-muted">
            <span>
              Head Coach: <strong className="text-fg">Active</strong>
            </span>
            <span>
              Rhythm:{" "}
              <strong className="text-ok">
                {state.rhythm === "idle"
                  ? "In Total Sync"
                  : state.rhythm === "running"
                    ? "Executing…"
                    : "Syncing…"}
              </strong>
            </span>
            <span className="font-mono text-primary">
              Runs {state.runs} · Memory hits {state.hits}
            </span>
          </div>
        </div>
      </header>

      <main className="mx-auto grid w-full max-w-6xl flex-1 gap-4 p-4 lg:grid-cols-3">
        <section className="space-y-4 lg:col-span-1">
          <div className="rounded-xl border border-border bg-surface p-4 shadow-lg">
            <div className="mb-1 flex items-center justify-between gap-2">
              <h2 className="flex items-center gap-2 text-base font-semibold">
                <Users className="h-4 w-4 text-primary" />
                Corporate Roster
              </h2>
              <span className="rounded bg-surface-2 px-2 py-0.5 font-mono text-[10px] text-primary">
                {activeAgents} active
              </span>
            </div>
            <p className="mb-3 text-xs text-muted">
              Promoted = high fitness. Fired = below benchmark after Monday Sync.
            </p>
            <ul className="space-y-2">
              {state.roster.map((a) => (
                <PlayerCard key={a.id} agent={a} />
              ))}
            </ul>
            <button
              type="button"
              disabled={busy}
              onClick={onSync}
              className="mt-4 flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-primary-fg shadow-md transition hover:opacity-90 disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${busy ? "animate-spin" : ""}`} />
              Monday Morning Sync
            </button>
          </div>

          <div className="rounded-xl border border-border bg-surface p-4 shadow-lg">
            <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide">
              <Wallet className="h-4 w-4 text-ok" />
              CFO Token Guardrail
            </h3>
            <div className="mb-2 flex items-center justify-between text-sm">
              <span className="text-muted">Cost ceiling</span>
              <span className="font-mono font-bold text-ok">
                {state.cfoBudget.toLocaleString()} tokens
              </span>
            </div>
            <input
              type="range"
              min={200}
              max={5000}
              step={100}
              value={state.cfoBudget}
              onChange={(e) =>
                setState((s) => ({
                  ...s,
                  cfoBudget: Number(e.target.value),
                }))
              }
              className="w-full"
              aria-label="CFO token budget"
            />
            <p className="mt-2 text-[11px] text-muted">
              Paths over this budget are blocked before collapse.
            </p>
          </div>

          <HowToUse />
        </section>

        <section className="space-y-4 lg:col-span-2">
          <div className="rounded-xl border border-border bg-surface p-4 shadow-lg sm:p-5">
            <h2 className="mb-1 flex items-center gap-2 text-base font-semibold">
              <Zap className="h-4 w-4 text-ok" />
              Workload Charter
            </h2>
            <p className="mb-4 text-xs text-muted">
              Describe the job, set entropy and match threshold, then run.
            </p>

            <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted">
              Job description
            </label>
            <input
              type="text"
              value={state.workload}
              onChange={(e) =>
                setState((s) => ({ ...s, workload: e.target.value }))
              }
              className="mb-3 w-full rounded-xl border border-border bg-bg px-4 py-3 text-sm text-fg outline-none ring-primary focus:ring-2"
              placeholder="Describe the workload…"
            />

            <div className="mb-3 flex flex-wrap gap-2">
              {PRESET_JOBS.map((job) => (
                <button
                  key={job}
                  type="button"
                  onClick={() => setState((s) => ({ ...s, workload: job }))}
                  className={`rounded-full border px-3 py-1.5 text-left text-[11px] transition ${
                    state.workload === job
                      ? "border-ok/50 bg-ok/15 text-ok"
                      : "border-border bg-surface-2 text-muted hover:text-fg"
                  }`}
                >
                  {job.length > 36 ? `${job.slice(0, 34)}…` : job}
                </button>
              ))}
            </div>

            <div className="mb-4 grid gap-3 sm:grid-cols-2">
              <Knob
                label="Context entropy"
                hint="0 = clean data · 1 = messy / high uncertainty"
                value={state.entropy}
                min={0}
                max={1}
                step={0.1}
                onChange={(v) => setState((s) => ({ ...s, entropy: v }))}
              />
              <Knob
                label="Memory match threshold"
                hint="Higher requires a closer Muscle-Memory match"
                value={state.threshold}
                min={0.5}
                max={1}
                step={0.05}
                onChange={(v) => setState((s) => ({ ...s, threshold: v }))}
              />
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={busy || !state.workload.trim()}
                onClick={onGo}
                className="flex min-h-14 min-w-[10rem] flex-1 items-center justify-center gap-2 rounded-xl bg-ok px-6 py-3 text-base font-bold text-accent-fg shadow-lg transition hover:opacity-90 disabled:opacity-50 sm:flex-none"
              >
                <Play className="h-5 w-5 fill-current" />
                Run charter
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={onReset}
                className="flex min-h-14 items-center justify-center gap-2 rounded-xl border border-border bg-surface-2 px-4 py-3 text-sm text-muted hover:text-fg disabled:opacity-50"
              >
                <Eraser className="h-4 w-4" />
                Reset
              </button>
            </div>

            {state.lastPath && (
              <div
                className={`mt-4 rounded-xl border px-4 py-3 ${
                  state.lastHit
                    ? "border-ok/40 bg-ok/10"
                    : "border-primary/40 bg-primary/10"
                }`}
              >
                <div className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide">
                  <Sparkles className="h-3.5 w-3.5" />
                  {state.lastHit
                    ? "Muscle-Memory HIT — verified path"
                    : "Quantum path (collapsed)"}
                </div>
                <div className="font-mono text-sm text-fg">
                  {state.lastPath.join(" → ")}
                </div>
              </div>
            )}
          </div>

          <div className="flex h-80 flex-col rounded-xl border border-border bg-surface p-4 shadow-lg">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted">
                <span className="h-2 w-2 rounded-full bg-primary" />
                System Blackboard / Telemetry
              </h3>
              <button
                type="button"
                onClick={() => setState((s) => clearLogs(s))}
                className="text-xs text-muted hover:text-fg"
              >
                Clear
              </button>
            </div>
            <div className="flex-1 space-y-1.5 overflow-y-auto rounded-lg border border-border bg-bg p-3 font-mono text-xs">
              {state.logs.map((line) => (
                <div key={line.id} className={logColor(line.kind)}>
                  <span className="text-muted">[{line.t}] </span>
                  {line.text}
                </div>
              ))}
              <div ref={logEnd} />
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-border py-3 text-center text-[11px] text-muted">
        FlowChartCharter · Muscle-Memory · Quantum Router · CFO Guardrail
      </footer>
    </div>
  );
}

function PlayerCard({ agent }: { agent: RosterAgent }) {
  const score = fitnessScore(agent);
  const badge =
    agent.status === "PROMOTED"
      ? "border-ok/40 bg-ok/10 text-ok"
      : agent.status === "FIRED"
        ? "border-danger/40 bg-danger/10 text-danger"
        : "border-border bg-surface-2 text-muted";

  return (
    <li className="flex items-center justify-between gap-2 rounded-xl border border-border bg-bg px-3 py-2.5">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-bold">{agent.id}</span>
          <span className="truncate text-xs text-muted">{agent.role}</span>
          <span
            className={`rounded border px-1.5 py-0.5 font-mono text-[10px] ${badge}`}
          >
            {agent.status}
          </span>
        </div>
        <div className="mt-0.5 text-[11px] text-muted">
          Success {agent.success}/{agent.total} · Tokens {agent.tokens} · Errors{" "}
          {agent.errors}
        </div>
      </div>
      <div className="shrink-0 text-right font-mono text-xs text-primary">
        {score.toFixed(2)}
      </div>
    </li>
  );
}

function Knob({
  label,
  hint,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  hint: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="rounded-xl border border-border bg-bg p-3">
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-muted">{label}</span>
        <span className="font-mono text-sm font-bold text-primary">
          {value.toFixed(2)}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full"
        aria-label={label}
      />
      <p className="mt-1 text-[10px] text-muted">{hint}</p>
    </div>
  );
}

function HowToUse() {
  return (
    <div className="rounded-xl border border-border bg-surface p-4 text-xs text-muted">
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-fg">
        <ArrowRight className="h-4 w-4 text-ok" />
        Quick start
      </div>
      <ol className="list-decimal space-y-1.5 pl-4">
        <li>Choose a workload preset or type your own.</li>
        <li>
          Press <strong className="text-ok">Run charter</strong>.
        </li>
        <li>
          <strong className="text-ok">HIT</strong> reuses Muscle-Memory ·{" "}
          <strong className="text-primary">MISS</strong> collapses a new path.
        </li>
        <li>
          Use <strong className="text-primary">Monday Morning Sync</strong> to
          promote or decommission agents.
        </li>
      </ol>
    </div>
  );
}

function logColor(kind: LogKind): string {
  if (kind === "success") return "text-ok";
  if (kind === "warning") return "text-warn";
  if (kind === "error") return "text-danger";
  return "text-fg/90";
}

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}
