"""What the agent carries between sessions.

Plain markdown in ``~/.workroom/memory``, one file per day. Readable and
deletable by the user without a tool, which is the point: an agent that
remembers things about you should keep those notes where you can see them.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

from ..config import MEMORY_DIR, MEMORY_FILES_AT_BOOT
from .registry import Registry, Tool, ToolError


def _today_file(root: Path) -> Path:
    return root / f"{_dt.date.today().isoformat()}.md"


def recent(root: Path | None = None, n: int = MEMORY_FILES_AT_BOOT) -> str:
    """The last few days of notes, newest last, for the system prompt."""
    root = root or MEMORY_DIR
    if not root.exists():
        return ""
    files = sorted(root.glob("*.md"))[-n:]
    chunks = []
    for f in files:
        try:
            body = f.read_text().strip()
        except OSError:
            continue
        if not body:
            continue
        # The file already opens with its own date heading.
        if body.startswith("#"):
            body = body.split("\n", 1)[1].strip() if "\n" in body else ""
        if body:
            chunks.append(f"## {f.stem}\n{body}")
    return "\n\n".join(chunks)


def append(note: str, root: Path | None = None, heading: str | None = None) -> Path:
    root = root or MEMORY_DIR
    root.mkdir(parents=True, exist_ok=True)
    f = _today_file(root)
    stamp = _dt.datetime.now().strftime("%H:%M")
    prefix = f"### {heading}\n" if heading else ""
    with f.open("a") as fh:
        if not f.stat().st_size:
            fh.write(f"# {f.stem}\n\n")
        fh.write(f"{prefix}- {stamp} {note.strip()}\n")
    return f


def register(registry: Registry, root: Path | None = None) -> None:
    root = root or MEMORY_DIR

    def remember(note: str) -> str:
        if not note.strip():
            raise ToolError("Nothing to remember -- pass the note as `note`.")
        f = append(note, root)
        return f"Noted in {f.name}."

    registry.add(Tool(
        name="remember",
        description=(
            "Write a durable note you will still want in a future session: a "
            "preference the user stated, a decision and its reason, a fact "
            "about this machine or project that was expensive to work out. "
            "Not for step-by-step progress within a task."
        ),
        parameters={
            "type": "object",
            "properties": {"note": {"type": "string", "description": "One fact, in a sentence."}},
            "required": ["note"],
        },
        fn=remember,
    ))
