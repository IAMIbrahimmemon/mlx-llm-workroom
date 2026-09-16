# Contributing

Workroom is small on purpose. The fastest way to get a change merged is to
keep it small too.

## Getting set up

```sh
uv sync
uv run pytest -q          # 57 tests, well under a second
cd macapp && swift build
```

You do not need the model weights to work on most of this. The parser, the
guard rails, discovery and the memory ceiling are all tested without them.
`uv run python scripts/pull_models.py` when you do need them (~7.5 GB).

## Before you open a pull request

- `uv run pytest -q` passes.
- `cd macapp && swift build` produces no warnings. The Swift 6 concurrency
  warnings are errors waiting to happen; do not leave them in.
- If you touched an onboarding screen, re-render and look at it:
  `./build/Workroom.app/Contents/MacOS/Workroom --snapshot shots/`. It uses the
  app's own renderer, so it needs no Screen Recording permission.
- New behaviour comes with a test. The two that matter most are
  `tests/test_tool_parser.py` and `tests/test_guard.py` — between them they
  cover the two ways this project can hurt someone.

## Things that will be sent back

- **A tool that shells out without going through `Guard.check_shell`.** Every
  command the model runs is classified first. There is no shortcut.
- **Anything that sends data off the machine.** No telemetry, no remote
  inference, no error reporting. A gateway address that is not `127.0.0.1` is
  a bug.
- **A model repo id outside `agent/config.py`.** The catalogue is the single
  source of truth shared by the CLI and the app; the app must keep reading it
  through `python -m agent.bridge survey` rather than holding its own copy.
- **Rewriting `~/.workroom/memory/*.md`.** Those notes belong to the user.
  Append only.

## Measurements

Numbers in the README, `PLAN.md` and the onboarding copy are measured on real
hardware, not estimated. `agent/config.py` marks which `tps` figures are
measured and which are scaled guesses. If you have different hardware, run
`uv run python scripts/bench_tps.py` and send the table — a second data point
is genuinely useful.

## Reporting a bug

Include `uv run workroom doctor` output. It reports the chip, memory, macOS
version, what models are installed and which gateways answer, which is most of
what anyone needs to reproduce a problem.
