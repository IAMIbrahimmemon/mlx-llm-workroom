#!/usr/bin/env python
"""Download model weights from Hugging Face, reporting real progress.

``huggingface_hub`` draws its own progress bars but gives no callback, so a
GUI cannot follow along. This walks the destination directory on a timer
instead and emits one JSON object per line -- which is what the onboarding
app's progress screen reads.

    uv run python scripts/pull_models.py                 # the recommended pair
    uv run python scripts/pull_models.py --json          # machine-readable
    uv run python scripts/pull_models.py --only qwen35-9b
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.config import BY_KEY, CATALOGUE, DEFAULT_BRAIN, DEFAULT_COMPRESSOR, ModelSpec


def _dir_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for f in path.rglob("*"):
        try:
            if f.is_file() and not f.is_symlink():
                total += f.stat().st_size
        except OSError:
            continue
    return total


class Reporter:
    def __init__(self, as_json: bool):
        self.as_json = as_json
        self._last_line = ""

    def emit(self, **row) -> None:
        if self.as_json:
            print(json.dumps(row), flush=True)
            return
        if row["status"] == "downloading":
            bar_w = 28
            filled = int(bar_w * row["pct"] / 100)
            bar = "█" * filled + "─" * (bar_w - filled)
            line = (f"  {row['label']:<16} {bar} {row['pct']:5.1f}%  "
                    f"{row['downloaded_gb']:.2f}/{row['total_gb']:.2f} GB")
            print("\r" + line.ljust(len(self._last_line)), end="", flush=True)
            self._last_line = line
        elif row["status"] == "done":
            print(f"\r  {row['label']:<16} done  {row['total_gb']:.2f} GB".ljust(
                len(self._last_line) + 8), flush=True)
            self._last_line = ""
        elif row["status"] == "error":
            print(f"\r  {row['label']:<16} failed: {row['detail']}", flush=True)
            self._last_line = ""


def pull(spec: ModelSpec, reporter: Reporter) -> bool:
    from huggingface_hub import snapshot_download
    from huggingface_hub.constants import HF_HUB_CACHE

    target = Path(HF_HUB_CACHE) / f"models--{spec.repo.replace('/', '--')}"
    total_bytes = spec.gb * 1e9
    stop = threading.Event()

    def watch() -> None:
        while not stop.wait(0.4):
            got = _dir_bytes(target)
            reporter.emit(
                key=spec.key, label=spec.label, status="downloading",
                pct=min(99.9, got / total_bytes * 100) if total_bytes else 0.0,
                downloaded_gb=round(got / 1e9, 2), total_gb=spec.gb,
            )

    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()
    try:
        snapshot_download(spec.repo, tqdm_class=None)
    except Exception as exc:
        stop.set(); watcher.join(timeout=1)
        reporter.emit(key=spec.key, label=spec.label, status="error",
                      detail=f"{type(exc).__name__}: {exc}", pct=0.0,
                      downloaded_gb=0.0, total_gb=spec.gb)
        return False
    stop.set(); watcher.join(timeout=1)
    reporter.emit(key=spec.key, label=spec.label, status="done", pct=100.0,
                  downloaded_gb=round(_dir_bytes(target) / 1e9, 2), total_gb=spec.gb)
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", action="append", metavar="KEY",
                    help="Model key to fetch. Repeatable. Default: the recommended pair.")
    ap.add_argument("--json", action="store_true", help="One JSON object per line.")
    ap.add_argument("--list", action="store_true", help="Show the catalogue and exit.")
    args = ap.parse_args()

    if args.list:
        for m in CATALOGUE:
            mark = " (recommended)" if m.recommended else ""
            print(f"{m.key:<14} {m.label:<14} {m.gb:>5.2f} GB  {m.role:<10}{mark}")
            print(f"{'':<14} {m.repo}")
        return 0

    keys = args.only or [DEFAULT_BRAIN, DEFAULT_COMPRESSOR]
    unknown = [k for k in keys if k not in BY_KEY]
    if unknown:
        print(f"Unknown model key(s): {', '.join(unknown)}", file=sys.stderr)
        print(f"Known: {', '.join(BY_KEY)}", file=sys.stderr)
        return 2

    specs = [BY_KEY[k] for k in keys]
    reporter = Reporter(args.json)
    if not args.json:
        total = sum(s.gb for s in specs)
        print(f"Fetching {len(specs)} model(s), {total:.2f} GB, from huggingface.co\n")

    started = time.perf_counter()
    failed = [s.label for s in specs if not pull(s, reporter)]
    if not args.json:
        elapsed = time.perf_counter() - started
        print(f"\n{'Some downloads failed: ' + ', '.join(failed) if failed else 'All set'} "
              f"({elapsed / 60:.1f} min)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
