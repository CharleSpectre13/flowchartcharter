"""fcc — FlowChartCharter Developer CLI (Phase 6).

Commands:
  fcc run <playbook.yaml>     Compile + execute Charterfile
  fcc monitor                 Live terminal dashboard (Rich)
  fcc trigger-sync / fcc sync Force Monday Morning Sync
  fcc audit-film              Advance / force Analytics Chief film room
  fcc status                  Health + roster snapshot
  fcc library                 List local enterprise playbooks
  fcc submit <workload>       Submit ad-hoc workload to Boss Agent

Server resolution:
  1. FCC_API_URL / --api (default http://127.0.0.1:8090)
  2. If server offline → in-memory FlowChartCharterSystem (local mode)
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
import typer
from rich import box
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

app = typer.Typer(
    name="fcc",
    help="FlowChartCharter — execution-first agent orchestration CLI",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()

DEFAULT_API = os.environ.get("FCC_API_URL", "http://127.0.0.1:8090")


# ---------------------------------------------------------------------------
# HTTP client helpers (graceful offline)
# ---------------------------------------------------------------------------


class ServerOffline(Exception):
    """FastAPI Nervous System unreachable."""


def _client(api: str, timeout: float = 30.0) -> httpx.Client:
    return httpx.Client(base_url=api.rstrip("/"), timeout=timeout)


def probe_server(api: str) -> bool:
    try:
        with _client(api, timeout=2.0) as c:
            r = c.get("/health")
            return r.status_code == 200
    except (httpx.HTTPError, OSError):
        return False


def api_get(api: str, path: str) -> Dict[str, Any]:
    try:
        with _client(api) as c:
            r = c.get(path)
            r.raise_for_status()
            return r.json()
    except (httpx.HTTPError, OSError) as exc:
        raise ServerOffline(str(exc)) from exc


def api_post(
    api: str,
    path: str,
    *,
    json_body: Optional[dict] = None,
    files: Optional[dict] = None,
) -> Dict[str, Any]:
    try:
        with _client(api, timeout=120.0) as c:
            if files:
                r = c.post(path, files=files)
            else:
                r = c.post(path, json=json_body or {})
            if r.status_code >= 400:
                detail = r.text
                try:
                    detail = r.json().get("detail", detail)
                except Exception:  # noqa: BLE001
                    pass
                raise ServerOffline(f"HTTP {r.status_code}: {detail}")
            if r.headers.get("content-type", "").startswith("application/json"):
                return r.json()
            return {"raw": r.text}
    except ServerOffline:
        raise
    except (httpx.HTTPError, OSError) as exc:
        raise ServerOffline(str(exc)) from exc


def resolve_mode(api: str, prefer_local: bool = False) -> Tuple[str, Any]:
    """Return ('remote', None) or ('local', FlowChartCharterSystem)."""
    if not prefer_local and probe_server(api):
        return "remote", None
    from flowchartcharter.system import FlowChartCharterSystem

    system = FlowChartCharterSystem(seed=int(os.environ.get("FCC_SEED", "42")))
    return "local", system


# ---------------------------------------------------------------------------
# Local execution path
# ---------------------------------------------------------------------------


def local_run_playbook(system: Any, path: Path, workload: str) -> Dict[str, Any]:
    meta = system.load_playbook(path)
    result = system.execute_compiled(workload or meta["playbook_name"])
    return {**result, **{"_meta": meta, "_mode": "local"}}


def local_submit(system: Any, workload: str, entropy: Optional[float]) -> Dict[str, Any]:
    return system.execute_charter(workload, context_entropy=entropy)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.callback()
def main(
    ctx: typer.Context,
    api: str = typer.Option(
        DEFAULT_API,
        "--api",
        envvar="FCC_API_URL",
        help="FlowChartCharter API base URL",
    ),
    local: bool = typer.Option(
        False,
        "--local",
        help="Force in-memory engine (skip remote server)",
    ),
) -> None:
    ctx.ensure_object(dict)
    ctx.obj["api"] = api
    ctx.obj["local"] = local


@app.command("run")
def cmd_run(
    ctx: typer.Context,
    playbook: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        help="Path to Charterfile YAML",
    ),
    workload: Optional[str] = typer.Option(
        None,
        "--workload",
        "-w",
        help="Workload label (defaults to playbook_name)",
    ),
) -> None:
    """Compile and execute a YAML Charterfile with a Rich progress bar."""
    api = ctx.obj["api"]
    force_local = ctx.obj["local"]
    mode, system = resolve_mode(api, prefer_local=force_local)

    console.print(
        Panel.fit(
            f"[bold cyan]fcc run[/]  {playbook.name}\n"
            f"mode=[yellow]{mode}[/]  api=[dim]{api}[/]",
            border_style="cyan",
        )
    )

    units_hint = 4
    try:
        import yaml

        raw = yaml.safe_load(playbook.read_text(encoding="utf-8")) or {}
        units_hint = max(1, len(raw.get("flow_units") or raw.get("units") or [1]))
        default_name = str(raw.get("playbook_name") or playbook.stem)
    except Exception:  # noqa: BLE001
        default_name = playbook.stem

    job = workload or default_name

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold]{task.description}"),
        BarColumn(bar_width=28),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        t_load = progress.add_task("Loading Charterfile…", total=1)
        t_units = progress.add_task("Executing Flow Units…", total=units_hint)

        try:
            if mode == "remote":
                progress.update(t_load, description="Uploading playbook to API…")
                with open(playbook, "rb") as fh:
                    meta = api_post(
                        api,
                        "/system/load-playbook",
                        files={
                            "file": (
                                playbook.name,
                                fh,
                                "application/yaml",
                            )
                        },
                    )
                progress.update(t_load, completed=1, description="Playbook loaded")
                units_hint = max(1, len(meta.get("flow_path") or []))
                progress.update(t_units, total=units_hint)
                progress.update(t_units, description="Boss Agent executing…")
                result = api_post(
                    api,
                    "/system/execute-compiled",
                    json_body={"workload": job},
                )
                progress.update(t_units, completed=units_hint)
            else:
                progress.update(t_load, description="Compiling in-memory…")
                assert system is not None
                meta = system.load_playbook(playbook)
                progress.update(t_load, completed=1)
                units_hint = max(1, len(meta.get("flow_path") or []))
                progress.update(t_units, total=units_hint)
                # simulate unit ticks for UX while running
                result = system.execute_compiled(job)
                for i in range(units_hint):
                    progress.update(t_units, completed=i + 1)
                    time.sleep(0.02)
        except ServerOffline as exc:
            console.print(
                f"[bold red]Server offline[/] at {api}\n"
                f"[dim]{exc}[/]\n"
                "Retry with [cyan]--local[/] to use the in-memory engine."
            )
            raise typer.Exit(code=2) from exc
        except Exception as exc:  # noqa: BLE001
            console.print(f"[bold red]Run failed:[/] {exc}")
            raise typer.Exit(code=1) from exc

    # Results panel
    q = float(result.get("quality") or 0.0)
    trust = bool(result.get("trust"))
    path = result.get("flow_path") or meta.get("flow_path") or []
    table = Table(title="Execution Result", box=box.ROUNDED, show_header=False)
    table.add_column("key", style="cyan")
    table.add_column("value")
    table.add_row("mode", mode)
    table.add_row("playbook", str(meta.get("playbook_name") or playbook.name))
    table.add_row("quality", f"{q:.3f}")
    table.add_row("trust", "[green]YES[/]" if trust else "[red]no[/]")
    table.add_row(
        "units",
        f"{result.get('units_ok', '?')}/{result.get('units_total', '?')}",
    )
    table.add_row("tokens", str(result.get("token_spend", "—")))
    table.add_row("flow", " → ".join(path) if path else "—")
    console.print(table)


@app.command("submit")
def cmd_submit(
    ctx: typer.Context,
    workload: str = typer.Argument(..., help="Workload description"),
    entropy: Optional[float] = typer.Option(None, "--entropy", "-e", min=0.0, max=1.0),
) -> None:
    """Submit an ad-hoc workload to the Boss Agent."""
    api = ctx.obj["api"]
    mode, system = resolve_mode(api, prefer_local=ctx.obj["local"])
    try:
        if mode == "remote":
            body: Dict[str, Any] = {"workload": workload}
            if entropy is not None:
                body["context_entropy"] = entropy
            result = api_post(api, "/workload/submit", json_body=body)
        else:
            assert system is not None
            result = local_submit(system, workload, entropy)
    except ServerOffline as exc:
        console.print(f"[red]Server offline:[/] {exc}")
        raise typer.Exit(2) from exc

    console.print(
        Panel(
            f"[bold]{workload}[/]\n"
            f"quality=[cyan]{float(result.get('quality', 0)):.3f}[/]  "
            f"trust={'[green]YES[/]' if result.get('trust') else '[red]no[/]'}  "
            f"mode=[yellow]{result.get('playbook_mode') or mode}[/]",
            title="Boss Agent",
            border_style="green",
        )
    )


@app.command("monitor")
def cmd_monitor(
    ctx: typer.Context,
    interval: float = typer.Option(1.5, "--interval", "-i", help="Refresh seconds"),
    once: bool = typer.Option(False, "--once", help="Single frame then exit"),
) -> None:
    """Live terminal dashboard — roster, fear metrics, tokens, analytics."""
    api = ctx.obj["api"]
    force_local = ctx.obj["local"]
    mode, system = resolve_mode(api, prefer_local=force_local)

    if mode == "local":
        console.print(
            "[yellow]No live server — monitor will show local engine snapshot.[/]\n"
            "Start API with [cyan]python -m flowchartcharter[/] then re-run."
        )

    def fetch_frame() -> Dict[str, Any]:
        if mode == "remote":
            try:
                roster = api_get(api, "/roster/status")
            except ServerOffline as exc:
                return {"error": str(exc), "offline": True}
            metrics_text = ""
            try:
                with _client(api, timeout=5.0) as c:
                    mr = c.get("/metrics")
                    if mr.status_code == 200:
                        metrics_text = mr.text
            except (httpx.HTTPError, OSError):
                pass
            return {"roster": roster, "metrics": metrics_text, "offline": False}
        assert system is not None
        # local snapshot
        nodes = []
        for a in system.roster:
            if a.__class__.__name__ == "BossAgent":
                continue
            snap = a.survival_snapshot()
            nodes.append(
                {
                    "name": a.name,
                    "role": a.role,
                    "fitness": float(snap.get("fitness") or 0),
                    "termination_risk_index": a.termination_risk_index,
                    "status": a.status.value,
                }
            )
        return {
            "roster": {
                "roster": nodes,
                "active_ops": sum(
                    1 for n in nodes if n["status"] in ("ACTIVE", "PROMOTED", "PHANTOM")
                ),
                "token_spend": system.token_spend,
                "token_budget": system.token_budget,
                "analytics": system.analytics.export(),
                "boss": {"name": system.boss.name, "playbook_tail": system.boss.playbook[-5:]},
            },
            "metrics": "",
            "offline": False,
        }

    def parse_prom(text: str) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for line in text.splitlines():
            if line.startswith("#") or not line.strip():
                continue
            # simple gauges without labels
            m = re.match(r"^([a-zA-Z_:][a-zA-Z0-9_:]*)\s+([0-9.eE+-]+)\s*$", line)
            if m:
                out[m.group(1)] = float(m.group(2))
        return out

    def render() -> Panel:
        frame = fetch_frame()
        if frame.get("offline"):
            return Panel(
                f"[bold red]API offline[/]\n{frame.get('error', '')}\n"
                f"Target: [dim]{api}[/]\n"
                "Tip: [cyan]fcc --local monitor --once[/] or start the server.",
                title="fcc monitor",
                border_style="red",
            )

        roster = frame["roster"]
        nodes = roster.get("roster") or []
        analytics = roster.get("analytics") or {}
        prom = parse_prom(frame.get("metrics") or "")

        table = Table(
            title="Active Roster",
            box=box.SIMPLE_HEAVY,
            expand=True,
        )
        table.add_column("Node", style="bold")
        table.add_column("Role", style="dim")
        table.add_column("Fear", justify="right")
        table.add_column("Fitness", justify="right")
        table.add_column("Status")

        for n in nodes:
            fear = float(n.get("termination_risk_index") or 0)
            fit = float(n.get("fitness") or 0)
            fear_style = "green" if fear < 0.3 else ("yellow" if fear < 0.6 else "red")
            table.add_row(
                str(n.get("name")),
                str(n.get("role", ""))[:40],
                Text(f"{fear:.3f}", style=fear_style),
                f"{fit:.3f}",
                str(n.get("status") or n.get("survival_status") or "—"),
            )

        tokens = int(roster.get("token_spend") or prom.get("fcc_token_spend_current", 0))
        budget = int(roster.get("token_budget") or prom.get("fcc_token_budget", 0))
        days = int(analytics.get("days_ready") or prom.get("fcc_analytics_days_ready", 0))
        active = int(roster.get("active_ops") or prom.get("fcc_active_nodes", len(nodes)))
        week = analytics.get("workweek_complete", days >= 5)

        stats = Table.grid(expand=True)
        stats.add_column()
        stats.add_column()
        stats.add_row(
            f"[cyan]Active ops[/]  {active}",
            f"[cyan]Token spend[/]  {tokens} / {budget}",
        )
        stats.add_row(
            f"[cyan]Analytics days[/]  {days}/5",
            f"[cyan]Workweek[/]  {'[green]READY[/]' if week else '[yellow]in progress[/]'}",
        )
        stats.add_row(
            f"[cyan]Mode[/]  {mode}",
            f"[cyan]API[/]  {api if mode == 'remote' else 'in-memory'}",
        )

        film = (
            "[green]Film room complete — run fcc audit-film or fcc sync[/]"
            if week
            else f"[dim]{5 - days} day(s) until Analytics Chief dossier[/]"
        )
        boss = roster.get("boss") or {}
        tail = boss.get("playbook_tail") or []
        boss_line = (
            f"Boss: [bold]{boss.get('name', 'GM')}[/]  "
            f"last note: [dim]{(tail[-1] if tail else '—')[:80]}[/]"
        )

        body = Group(
            stats,
            Text(""),
            table,
            Text(""),
            Text(film),
            Text(boss_line),
            Text(f"refreshed {time.strftime('%H:%M:%S')}  interval={interval}s", style="dim"),
        )
        return Panel(body, title="[bold]FlowChartCharter Monitor[/]", border_style="cyan")

    if once:
        console.print(render())
        return

    console.print("[dim]Live monitor — Ctrl+C to exit[/]")
    try:
        with Live(render(), console=console, refresh_per_second=max(0.5, 1 / interval)) as live:
            while True:
                time.sleep(interval)
                live.update(render())
    except KeyboardInterrupt:
        console.print("\n[dim]monitor stopped[/]")


@app.command("trigger-sync")
@app.command("sync")
def cmd_sync(ctx: typer.Context) -> None:
    """Force Monday Morning Sync (GM talent prune)."""
    api = ctx.obj["api"]
    mode, system = resolve_mode(api, prefer_local=ctx.obj["local"])
    try:
        if mode == "remote":
            result = api_post(api, "/system/trigger-monday-sync")
        else:
            assert system is not None
            result = system.downtime_sync()
    except ServerOffline as exc:
        console.print(f"[red]Server offline:[/] {exc}")
        raise typer.Exit(2) from exc

    outcomes = result.get("outcomes") or {}
    table = Table(title="Monday Morning Sync", box=box.ROUNDED)
    table.add_column("Agent")
    table.add_column("Outcome")
    for k, v in outcomes.items():
        style = "red" if "FIRE" in str(v).upper() or "TERMINAT" in str(v).upper() else "green"
        table.add_row(str(k), Text(str(v), style=style))
    console.print(table)
    console.print(
        f"dossier_driven={result.get('dossier_driven')}  "
        f"active_ops={result.get('active_ops_after_prune', '—')}"
    )


@app.command("audit-film")
def cmd_audit_film(
    ctx: typer.Context,
    force: bool = typer.Option(True, "--force/--no-force", help="Force EOW pad"),
) -> None:
    """Trigger Analytics Chief 5-day film room / end-of-week protocol."""
    api = ctx.obj["api"]
    mode, system = resolve_mode(api, prefer_local=ctx.obj["local"])
    try:
        if mode == "remote":
            result = api_post(api, f"/system/end-of-week?force={'true' if force else 'false'}")
        else:
            assert system is not None
            result = system.run_end_of_week_protocol(force=force)
    except ServerOffline as exc:
        console.print(f"[red]Server offline:[/] {exc}")
        raise typer.Exit(2) from exc

    console.print(
        Panel(
            f"days_ready={result.get('days_ready')}  "
            f"dossier_driven={result.get('dossier_driven')}\n"
            f"outcomes={json.dumps(result.get('outcomes') or {}, indent=0)[:400]}",
            title="Analytics Film Room",
            border_style="magenta",
        )
    )


@app.command("status")
def cmd_status(ctx: typer.Context) -> None:
    """Health check + compact roster."""
    api = ctx.obj["api"]
    if probe_server(api):
        h = api_get(api, "/health")
        r = api_get(api, "/roster/status")
        console.print(
            f"[green]● ONLINE[/]  v{h.get('version')}  "
            f"roster={h.get('roster_size')}  uptime={h.get('uptime_s')}s"
        )
        console.print(
            f"active_ops={r.get('active_ops')}  "
            f"tokens={r.get('token_spend')}/{r.get('token_budget')}"
        )
    else:
        console.print(f"[red]● OFFLINE[/]  {api}")
        console.print("Use [cyan]fcc --local …[/] for in-memory mode.")
        raise typer.Exit(2)


@app.command("library")
def cmd_library(
    ctx: typer.Context,
    path: Optional[Path] = typer.Option(None, "--path", help="Local library directory"),
) -> None:
    """List enterprise playbooks (remote /library or local library/)."""
    api = ctx.obj["api"]
    names: List[str] = []
    source = "local"
    if not ctx.obj["local"] and probe_server(api):
        try:
            data = api_get(api, "/library")
            names = list(data.get("playbooks") or [])
            source = f"remote:{api}"
        except ServerOffline:
            names = []
    if not names:
        root = path
        if root is None:
            # walk up from package to repo library
            cand = Path(__file__).resolve().parents[3] / "library"
            root = cand if cand.is_dir() else Path("library")
        if root.is_dir():
            names = sorted(p.name for p in root.glob("*.yaml"))
            source = str(root)
    table = Table(title=f"Playbook Library ({source})", box=box.SIMPLE)
    table.add_column("#", style="dim")
    table.add_column("Charterfile")
    for i, n in enumerate(names, 1):
        table.add_row(str(i), n)
    if not names:
        console.print("[yellow]No playbooks found[/]")
    else:
        console.print(table)


@app.command("first-day")
def cmd_first_day() -> None:
    """Seed the starter house, walk one job, print a stranger receipt."""
    os.environ.setdefault("FCC_HARNESS_PERSIST", "0")
    from flowchartcharter.system import FlowChartCharterSystem

    out = FlowChartCharterSystem(seed=15).first_day()
    console.print_json(data={
        "ok": out.get("ok"),
        "charter": out.get("charter"),
        "quality": out.get("quality"),
        "shelves": out.get("shelves"),
        "receipt_hash": (out.get("receipt") or {}).get("hash"),
        "claimed_graphrag": False,
    })


@app.command("remember")
def cmd_remember(
    note: str = typer.Argument(..., help="One drip of house memory"),
) -> None:
    """Save one note. No corpus required."""
    os.environ.setdefault("FCC_HARNESS_PERSIST", "0")
    from flowchartcharter.system import FlowChartCharterSystem

    sys_ = FlowChartCharterSystem(seed=15)
    sys_.first_day()
    rec = sys_.remember(note)
    console.print_json(data=rec)


@app.command("ask")
def cmd_ask(prompt: str = typer.Argument(..., help="Ask the world mouth")) -> None:
    """Call Grok or the house chef if present. Else honest none."""
    from flowchartcharter.house import ask_world

    console.print_json(data=ask_world(prompt))


@app.command("verify-receipt")
def cmd_verify(path: str = typer.Argument(..., help="JSON or JSONL receipt")) -> None:
    """Offline stranger check. No vendor."""
    from flowchartcharter.house import verify_receipt_path

    out = verify_receipt_path(path)
    console.print_json(data=out)
    raise typer.Exit(0 if out.get("ok") else 1)


@app.command("version")
def cmd_version() -> None:
    """Print package version."""
    try:
        from flowchartcharter import __version__
    except Exception:  # noqa: BLE001
        __version__ = "unknown"
    console.print(f"flowchart-charter-engine [cyan]{__version__}[/]")
    console.print("fcc CLI Phase 6 — Developer Tooling & Global Go-Live")


def run() -> None:
    """Console script entry: fcc"""
    app()


if __name__ == "__main__":
    run()
