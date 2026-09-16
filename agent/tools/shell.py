"""Running commands, behind the guard."""

from __future__ import annotations

import os
import subprocess

from ..actuation.guard import Guard
from .registry import Registry, Tool, ToolError

SCHEMA = {
    "type": "object",
    "properties": {
        "cmd": {"type": "string", "description": "The command to run, as you would type it."},
        "timeout": {"type": "integer", "description": "Seconds before it is killed. Default 60.",
                    "default": 60},
    },
    "required": ["cmd"],
}

DESCRIPTION = (
    "Run a shell command and get its combined output. Runs in the user's "
    "working directory. Destructive commands stop and ask the user first, so "
    "expect a refusal rather than silence if you reach for one."
)


def make(registry: Registry, guard: Guard, cwd: str | None = None) -> Tool:
    workdir = cwd or os.getcwd()

    def bash(cmd: str, timeout: int = 60) -> str:
        may_run, why = guard.check_shell(cmd)
        if not may_run:
            raise ToolError(f"Not run -- {why}.")
        try:
            proc = subprocess.run(
                # -f skips .zshenv/.zshrc. Those print banners and set aliases
                # that would land in every tool result and make behaviour depend
                # on the user's dotfiles; this process already carries the PATH.
                ["/bin/zsh", "-f", "-c", cmd],
                capture_output=True, text=True,
                timeout=max(1, min(int(timeout), 600)),
                cwd=workdir,
            )
        except subprocess.TimeoutExpired:
            raise ToolError(f"Timed out after {timeout}s. Try a narrower command.")
        except OSError as exc:
            raise ToolError(f"Could not run it: {exc}")

        body = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0:
            return f"[exit {proc.returncode}]\n{body}".rstrip()
        return body.rstrip() or "[no output]"

    return registry.add(Tool(name="bash", description=DESCRIPTION,
                             parameters=SCHEMA, fn=bash))
