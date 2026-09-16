"""One JSON surface for the macOS app.

The app draws the onboarding; it does not decide what is on the menu. Every
model, preset and detected gateway comes from here, so the app and the CLI
can never disagree about what Workroom supports.

    python -m agent.bridge survey
    python -m agent.bridge save --brain qwen35-9b --preset alongside
"""

from __future__ import annotations

import argparse
import json
import sys

from . import config as cfg
from . import memcap
from .discovery import gateways, hardware, local_models


def survey() -> dict:
    hw = hardware()

    models = []
    for m in cfg.CATALOGUE:
        row = m.as_dict()
        row["runnable"] = hw.can_run(m.needs_ram_gb)
        row["reason"] = (
            "" if row["runnable"]
            else f"Needs {m.needs_ram_gb} GB; this Mac has {hw.total_ram_gb} GB."
        )
        models.append(row)

    presets = []
    for p in cfg.MEMORY_PRESETS:
        c = memcap.plan(p.key, hw)
        presets.append({
            "key": p.key, "title": p.title, "desc": p.desc,
            "tps": p.tps, "ctx": p.ctx, **c.as_dict(),
        })

    return {
        "hardware": hw.as_dict(),
        "catalogue": models,
        "presets": presets,
        "local_models": [m.as_dict() for m in local_models()],
        "gateways": [g.as_dict() for g in gateways()],
        "state": cfg.load_state(),
        "defaults": {"brain": cfg.DEFAULT_BRAIN, "preset": cfg.DEFAULT_PRESET},
        "current_sysctl_mb": memcap.current_sysctl_mb(),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="agent.bridge")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("survey", help="Everything the onboarding app needs.")
    s = sub.add_parser("save", help="Record the choices the user made.")
    s.add_argument("--brain", required=True)
    s.add_argument("--preset", required=True)
    s.add_argument("--vision", default="")
    s.add_argument("--gateway", default="")
    args = ap.parse_args(argv)

    if args.cmd == "survey":
        json.dump(survey(), sys.stdout, indent=2)
        print()
        return 0

    if args.brain not in cfg.BY_KEY:
        print(json.dumps({"ok": False, "error": f"unknown model {args.brain!r}"}))
        return 2
    if args.preset not in cfg.PRESET_BY_KEY:
        print(json.dumps({"ok": False, "error": f"unknown preset {args.preset!r}"}))
        return 2

    state = {
        "brain": args.brain,
        "compressor": cfg.DEFAULT_COMPRESSOR,
        "memory_preset": args.preset,
        "ctx": cfg.PRESET_BY_KEY[args.preset].ctx,
    }
    if args.vision:
        state["vision"] = args.vision
    if args.gateway:
        state["gateway"] = args.gateway
    cfg.save_state(state)
    print(json.dumps({"ok": True, "state": state, "path": str(cfg.STATE_FILE)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
