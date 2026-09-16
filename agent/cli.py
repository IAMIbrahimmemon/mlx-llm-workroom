"""The terminal front end: onboarding, the REPL, and a doctor command."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from . import config as cfg
from . import memcap
from .actuation.guard import Guard
from .brain import Brain
from .compressor import Compressor
from .discovery import gateways, hardware, local_models
from .loop import Agent, Step
from .tools import files as filetools
from .tools import memory as memtool
from .tools import shell as shelltools
from .tools.registry import Registry

console = Console()
ACCENT = "dark_orange3"


# --------------------------------------------------------------- onboarding

def _choose(prompt: str, options: list[tuple[str, str]], default: int = 0) -> int:
    for i, (title, detail) in enumerate(options):
        mark = "*" if i == default else " "
        console.print(f"  {mark} [bold]{i + 1}[/bold]  {title}")
        if detail:
            console.print(f"       [dim]{detail}[/dim]")
    console.print()
    while True:
        raw = console.input(f"[{ACCENT}]{prompt}[/] [dim][{default + 1}][/dim] ").strip()
        if not raw:
            return default
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw) - 1
        console.print("[dim]Pick one of the numbers.[/dim]")


def onboard(force: bool = False) -> dict:
    state = cfg.load_state()
    if state.get("brain") and not force:
        return state

    hw = hardware()
    console.print()
    console.print(Text("AI should be simple.", style=f"bold {ACCENT}"))
    console.print("One capable model, running on your own Mac. Nothing leaves this machine.\n")

    if not hw.apple_silicon:
        console.print("[red]Workroom needs Apple silicon. MLX will not run on this machine.[/red]")
        raise SystemExit(1)
    console.print(f"[dim]{hw.chip} · {hw.total_ram_gb} GB unified memory · macOS {hw.macos}[/dim]\n")

    # -- brain ------------------------------------------------------------
    console.print(Rule("Choose a brain", style="dim"))
    runnable = [m for m in cfg.brains() if hw.can_run(m.needs_ram_gb)]
    blocked = [m for m in cfg.brains() if not hw.can_run(m.needs_ram_gb)]
    opts = [
        (f"{m.label}  [dim]{m.gb:.2f} GB · {m.tps}[/dim]"
         + ("  [bold]recommended[/bold]" if m.recommended else ""), m.blurb)
        for m in runnable
    ]
    for m in blocked:
        console.print(f"  [dim]-- {m.label} needs {m.needs_ram_gb} GB, this Mac has "
                      f"{hw.total_ram_gb}[/dim]")
    default_i = next((i for i, m in enumerate(runnable) if m.recommended), 0)
    brain = runnable[_choose("Which model?", opts, default_i)]

    # -- already here -----------------------------------------------------
    have = local_models()
    live = [g for g in gateways() if g.reachable]
    if have or live:
        console.print()
        console.print(Rule("Already on this Mac", style="dim"))
        for m in have[:6]:
            console.print(f"  [dim]{m.source:<12}[/dim] {m.name}  [dim]{m.gb:.1f} GB[/dim]")
        for g in live:
            console.print(f"  [dim]gateway     [/dim] {g.label} on {g.base_url}  "
                          f"[dim]{g.detail}[/dim]")
        console.print("[dim]Workroom will use these where it can. `workroom doctor` shows them "
                      "again later.[/dim]")

    # -- memory -----------------------------------------------------------
    console.print()
    console.print(Rule("How much of this Mac gets to think?", style="dim"))
    preset_opts = []
    for p in cfg.MEMORY_PRESETS:
        c = memcap.plan(p.key, hw)
        sudo = "asks for an admin password" if c.needs_sysctl else "no password needed"
        preset_opts.append(
            (f"{p.title}  [dim]{c.limit_gb} GB ceiling · {p.tps} · {sudo}[/dim]", p.desc)
        )
    preset = cfg.MEMORY_PRESETS[_choose("Which one?", preset_opts, 0)]
    ceiling = memcap.plan(preset.key, hw)

    state = {
        "brain": brain.key,
        "compressor": cfg.DEFAULT_COMPRESSOR,
        "memory_preset": preset.key,
        "ctx": preset.ctx,
    }
    cfg.save_state(state)

    # -- fetch ------------------------------------------------------------
    console.print()
    console.print(Rule("Getting things ready", style="dim"))
    console.print(f"[dim]{brain.repo}[/dim]")
    import subprocess
    rc = subprocess.call([sys.executable, str(Path(__file__).resolve().parent.parent
                                              / "scripts" / "pull_models.py"),
                          "--only", brain.key, "--only", cfg.DEFAULT_COMPRESSOR])
    if rc != 0:
        console.print("[red]Downloads did not finish. Run `workroom pull` to try again.[/red]")

    if ceiling.needs_sysctl:
        console.print(f"\n[dim]For the {preset.title} ceiling, run this once per boot:[/dim]")
        console.print(f"  [bold]{ceiling.sysctl_command}[/bold]")

    console.print(f"\n[{ACCENT}]You're set.[/] Type a task, or `/help`.\n")
    return state


# -------------------------------------------------------------------- repl

def _confirm(cmd: str, reason: str) -> bool:
    console.print()
    console.print(Panel(Text(cmd, style="bold"), title=f"[yellow]{reason}[/yellow]",
                        border_style="yellow", expand=False))
    return console.input("[yellow]Run it?[/] [dim]y/N[/dim] ").strip().lower() in ("y", "yes")


def _render_step(step: Step) -> None:
    args = ", ".join(f"{k}={v!r}" if len(repr(v)) < 60 else f"{k}=<{len(str(v))} chars>"
                     for k, v in step.args.items())
    style = "dim" if step.ok else "red"
    console.print(f"  [{ACCENT}]›[/] [bold]{step.name}[/bold]([{style}]{args}[/])")
    first = step.result.strip().splitlines()
    if first:
        head = first[0][:120]
        more = f"  [dim](+{len(first) - 1} lines)[/dim]" if len(first) > 1 else ""
        console.print(f"    [{style}]{head}[/]{more}")


def repl(agent: Agent, brain: Brain) -> None:
    console.print(f"[dim]workroom · {brain.repo.split('/')[-1]} · {brain.ctx // 1024}k ctx · "
                  f"/help for commands[/dim]\n")
    while True:
        try:
            line = console.input(f"[{ACCENT}]›[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]bye[/dim]")
            return
        if not line:
            continue
        if line in ("/quit", "/exit", "exit", "quit"):
            console.print("[dim]bye[/dim]")
            return
        if line == "/help":
            console.print("  [dim]/mem   memory in use\n  /ctx   context used\n"
                          "  /tools what I can call\n  /quit  leave[/dim]")
            continue
        if line == "/mem":
            u = memcap.in_use()
            console.print(f"  [dim]active {u['active_gb']} GB · cache {u['cache_gb']} GB "
                          f"· peak {u['peak_gb']} GB[/dim]")
            continue
        if line == "/ctx":
            console.print(f"  [dim]{agent.context_fraction():.0%} of {agent.ctx} tokens[/dim]")
            continue
        if line == "/tools":
            console.print(f"  [dim]{', '.join(agent.registry.names())}[/dim]")
            continue

        console.print()
        try:
            out = agent.send(line, on_step=_render_step)
        except KeyboardInterrupt:
            console.print("\n[yellow]stopped[/yellow]\n")
            continue
        except Exception as exc:
            console.print(f"[red]{type(exc).__name__}: {exc}[/red]\n")
            continue
        console.print()
        console.print(out.text)
        console.print()


# ------------------------------------------------------------------ doctor

def doctor() -> int:
    hw = hardware()
    console.print()
    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_row("chip", hw.chip)
    t.add_row("memory", f"{hw.total_ram_gb} GB unified")
    t.add_row("macOS", hw.macos)
    t.add_row("MLX", "ready" if hw.apple_silicon else "[red]needs Apple silicon[/red]")
    console.print(Panel(t, title="This Mac", border_style="dim", expand=False))

    state = cfg.load_state()
    if state:
        c = memcap.plan(state.get("memory_preset", cfg.DEFAULT_PRESET), hw)
        console.print(f"\n[bold]Configured[/bold]  brain={state.get('brain')} "
                      f"ceiling={c.limit_gb} GB ctx={state.get('ctx')}")
        console.print(f"[dim]iogpu.wired_limit_mb is {memcap.current_sysctl_mb()} "
                      f"(0 means macOS is managing it; Metal offers "
                      f"{c.recommended_gb:.1f} GB here)[/dim]")
    else:
        console.print("\n[dim]Not set up yet -- run `workroom onboard`.[/dim]")

    console.print("\n[bold]Models on this Mac[/bold]")
    found = local_models()
    for m in found:
        console.print(f"  [dim]{m.source:<12}[/dim] {m.name}  [dim]{m.gb:.2f} GB[/dim]")
    if not found:
        console.print("  [dim]none found[/dim]")

    console.print("\n[bold]Gateways[/bold]")
    for g in gateways():
        dot = "[green]●[/green]" if g.reachable else "[dim]○[/dim]"
        console.print(f"  {dot} {g.label:<12} [dim]{g.base_url}[/dim]  {g.detail}")
    console.print()
    return 0


# -------------------------------------------------------------------- main

def build_agent(args) -> tuple[Agent, Brain]:
    state = cfg.load_state()
    spec = cfg.BY_KEY.get(state.get("brain", ""), cfg.recommended_brain())
    ctx = args.ctx or state.get("ctx") or 16384

    ceiling = memcap.plan(state.get("memory_preset", cfg.DEFAULT_PRESET))
    memcap.apply(ceiling)

    brain = Brain(spec.repo, ctx=ctx, think=args.think)
    guard = Guard(dry_run=args.dry_run, confirm=_confirm, auto_approve=args.yes)

    registry = Registry()
    shelltools.make(registry, guard)
    filetools.register(registry, Path.cwd())
    memtool.register(registry)

    comp_spec = cfg.BY_KEY.get(state.get("compressor", cfg.DEFAULT_COMPRESSOR))
    compressor = Compressor(comp_spec.repo) if comp_spec else None

    return Agent(brain, registry, compressor=compressor, ctx=ctx), brain


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="workroom", description="A local computer-use agent.")
    ap.add_argument("command", nargs="?", default="repl",
                    choices=["repl", "onboard", "doctor", "pull"])
    ap.add_argument("--think", action="store_true", help="Let the model reason at length.")
    ap.add_argument("--dry-run", action="store_true", help="Show actions, run none.")
    ap.add_argument("--yes", action="store_true",
                    help="Skip confirmations. Denied commands are still denied.")
    ap.add_argument("--ctx", type=int, default=0, help="Context window in tokens.")
    args = ap.parse_args(argv)

    if args.command == "doctor":
        return doctor()
    if args.command == "pull":
        from subprocess import call
        return call([sys.executable, str(Path(__file__).resolve().parent.parent
                                         / "scripts" / "pull_models.py")])
    if args.command == "onboard":
        onboard(force=True)
        return 0

    if not cfg.is_onboarded():
        onboard()

    agent, brain = build_agent(args)
    with console.status("[dim]loading the model...[/dim]"):
        brain.load()
    repl(agent, brain)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
