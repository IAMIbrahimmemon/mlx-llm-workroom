#!/usr/bin/env python
"""Measure real decode speed, so PLAN.md can stop guessing.

    uv run python scripts/bench_tps.py
    uv run python scripts/bench_tps.py --ctx 1000 8000 --think
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import config as cfg
from agent import memcap
from agent.brain import Brain

FILLER = (
    "The agent read the file, considered what it found, and decided which "
    "tool to call next. It preferred the narrow tool over the general one. "
)


def _prompt_of_about(tokens: int) -> str:
    """Roughly `tokens` tokens of innocuous prose, ~4 chars per token."""
    return (FILLER * (max(1, tokens * 4 // len(FILLER)) + 1))[: tokens * 4]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None, help="Catalogue key. Default: what you chose.")
    ap.add_argument("--ctx", type=int, nargs="+", default=[1000, 8000, 16000],
                    help="Prompt sizes in tokens.")
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--think", action="store_true", help="Also measure with reasoning on.")
    args = ap.parse_args()

    state = cfg.load_state()
    key = args.model or state.get("brain") or cfg.DEFAULT_BRAIN
    spec = cfg.BY_KEY[key]

    ceiling = memcap.plan(state.get("memory_preset", cfg.DEFAULT_PRESET))
    memcap.apply(ceiling)

    print(f"{spec.label}  {spec.repo}")
    print(f"ceiling {ceiling.limit_gb} GB  (macOS offers {ceiling.recommended_gb:.1f} GB)\n")

    brain = Brain(spec.repo, ctx=max(args.ctx) + 2048)
    t0 = time.perf_counter()
    brain.load()
    print(f"loaded in {time.perf_counter() - t0:.1f}s\n")

    modes = [False, True] if args.think else [False]
    print(f"{'prompt':>8}  {'mode':<9} {'tok/s':>7}  {'prefill':>8}  {'peak GB':>8}")
    print("-" * 48)
    rows = []
    for n in args.ctx:
        body = _prompt_of_about(n)
        for think in modes:
            speeds, prefills = [], []
            for _ in range(args.runs):
                msgs = [
                    {"role": "system", "content": "You are terse."},
                    {"role": "user", "content": body + "\n\nReply with one short sentence."},
                ]
                started = time.perf_counter()
                r = brain.complete(msgs, think=think)
                prefills.append(started)
                speeds.append(r.stats.tps)
                last = r
            tps = statistics.median(speeds)
            rows.append((n, "think" if think else "no_think", tps))
            print(f"{n:>8}  {'think' if think else 'no_think':<9} {tps:>7.1f}  "
                  f"{last.stats.prompt_tokens:>8}  {memcap.in_use()['peak_gb']:>8.2f}")

    print("\nPaste into PLAN.md Part C:")
    for n, mode, tps in rows:
        print(f"  {n:>6} tok ctx, {mode:<8} -> {tps:.1f} tok/s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
