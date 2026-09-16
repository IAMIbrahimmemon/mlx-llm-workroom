# Workroom

A local computer-use agent. One model, on this Mac, with tools.

## What this is
`agent/` is the runtime. `design/` holds the onboarding artboards. `PLAN.md`
is the design record and the milestone list; read Part B before changing the
model stack, because the single-model decision is load-bearing.

## Working here
- `uv run workroom` starts the REPL. `uv run workroom doctor` reports the machine,
  what models are on it, and which gateways answer.
- `uv run pytest -q` before any commit. The parser and guard tests are the
  ones that catch real regressions.
- Dependencies go through `uv add`, never pip.

## The macOS app
`macapp/` is a SwiftUI package. `cd macapp && ./bundle.sh` produces
`build/Workroom.app`. `Workroom --snapshot <dir>` renders every screen to PNG using the
app's own renderer -- no Screen Recording grant, works headless, and it is how
you check a layout change without clicking through the flow.

The app must never hold its own copy of the catalogue: it reads
`python -m agent.bridge survey`.

## Rules that are not negotiable
- Everything stays on the machine. No telemetry, no remote inference, no
  uploading a screenshot anywhere. A gateway is only ever `127.0.0.1`.
- `agent/actuation/guard.py` decides what runs. Adding a tool that shells out
  without going through `Guard.check_shell` is a bug, not a shortcut.
- Model repo ids live in `agent/config.py` and nowhere else.
- `~/.workroom/memory/*.md` belongs to the user. Append, never rewrite.
