"""Reading and changing files.

Separate from ``bash`` on purpose: an edit expressed as an exact string
replacement is reviewable and fails loudly, where a ``sed -i`` reported as
success may have matched nothing.
"""

from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path

from .registry import Registry, Tool, ToolError

MAX_READ_BYTES = 400_000
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__",
             ".mypy_cache", ".pytest_cache", "dist", "build", ".next"}


def _resolve(path: str, root: Path) -> Path:
    # Models pad arguments with whitespace often enough that treating a padded
    # path as "not found" is a worse failure than quietly trimming it.
    p = Path(os.path.expanduser(str(path).strip()))
    return p if p.is_absolute() else (root / p)


def register(registry: Registry, root: Path | None = None) -> None:
    base = root or Path.cwd()

    # -- read -------------------------------------------------------------
    def read_file(path: str, offset: int = 0, limit: int = 0) -> str:
        p = _resolve(path, base)
        if not p.exists():
            raise ToolError(f"{p} does not exist.")
        if p.is_dir():
            raise ToolError(f"{p} is a directory. Use glob to list it.")
        if p.stat().st_size > MAX_READ_BYTES:
            raise ToolError(
                f"{p} is {p.stat().st_size:,} bytes. Read part of it with "
                f"offset/limit, or grep it instead."
            )
        try:
            lines = p.read_text(errors="replace").splitlines()
        except OSError as exc:
            raise ToolError(f"Could not read {p}: {exc}")

        start = max(0, int(offset))
        end = start + int(limit) if limit else len(lines)
        window = lines[start:end]
        if not window:
            return f"[{p} has {len(lines)} lines; nothing at offset {start}]"
        width = len(str(start + len(window)))
        return "\n".join(f"{start + i + 1:>{width}}  {ln}" for i, ln in enumerate(window))

    registry.add(Tool(
        name="read_file",
        description="Read a text file. Returns numbered lines. Use offset and "
                    "limit for a window into a long file.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "offset": {"type": "integer", "description": "First line, 0-based.", "default": 0},
                "limit": {"type": "integer", "description": "How many lines. 0 means all.", "default": 0},
            },
            "required": ["path"],
        },
        fn=read_file,
    ))

    # -- write ------------------------------------------------------------
    def write_file(path: str, content: str) -> str:
        p = _resolve(path, base)
        existed = p.exists()
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
        except OSError as exc:
            raise ToolError(f"Could not write {p}: {exc}")
        verb = "Overwrote" if existed else "Wrote"
        return f"{verb} {p} ({len(content.splitlines())} lines)."

    registry.add(Tool(
        name="write_file",
        description="Write a whole file, creating parent directories. This "
                    "replaces any existing content -- prefer edit_file for a "
                    "change to a file that already exists.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
        fn=write_file,
    ))

    # -- edit -------------------------------------------------------------
    def edit_file(path: str, old: str, new: str, count: int = 1) -> str:
        p = _resolve(path, base)
        if not p.exists():
            raise ToolError(f"{p} does not exist.")
        try:
            text = p.read_text()
        except OSError as exc:
            raise ToolError(f"Could not read {p}: {exc}")

        hits = text.count(old)
        if hits == 0:
            raise ToolError(
                f"That exact text is not in {p}. Read the file first and copy "
                f"the target text precisely, including indentation."
            )
        if hits > 1 and count == 1:
            raise ToolError(
                f"That text appears {hits} times in {p}. Include more "
                f"surrounding context to pick one, or pass count={hits} to "
                f"replace them all."
            )
        p.write_text(text.replace(old, new, -1 if count != 1 else 1))
        return f"Replaced {min(hits, count) if count != 1 else 1} occurrence(s) in {p}."

    registry.add(Tool(
        name="edit_file",
        description="Replace an exact string in a file. The old text must "
                    "match byte for byte and be unique unless you pass count.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old": {"type": "string", "description": "Exact text to find."},
                "new": {"type": "string", "description": "What replaces it."},
                "count": {"type": "integer", "description": "1 (default) or the number of matches to replace.", "default": 1},
            },
            "required": ["path", "old", "new"],
        },
        fn=edit_file,
    ))

    # -- glob -------------------------------------------------------------
    def glob(pattern: str, path: str = ".", limit: int = 200) -> str:
        root = _resolve(path, base)
        if not root.exists():
            raise ToolError(f"{root} does not exist.")
        out: list[str] = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
            for name in filenames:
                full = Path(dirpath) / name
                rel = full.relative_to(root)
                if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(str(rel), pattern):
                    out.append(str(rel))
                    if len(out) >= limit:
                        return "\n".join(sorted(out)) + f"\n[stopped at {limit}]"
        return "\n".join(sorted(out)) or f"Nothing matching {pattern!r} under {root}."

    registry.add(Tool(
        name="glob",
        description="Find files by name pattern, e.g. '*.py' or 'agent/**.py'. "
                    "Skips .git, node_modules and virtualenvs.",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "path": {"type": "string", "description": "Where to start. Default is the working directory.", "default": "."},
                "limit": {"type": "integer", "default": 200},
            },
            "required": ["pattern"],
        },
        fn=glob,
    ))

    # -- grep -------------------------------------------------------------
    def grep(pattern: str, path: str = ".", glob_filter: str = "*", limit: int = 100) -> str:
        root = _resolve(path, base)
        try:
            rx = re.compile(pattern)
        except re.error as exc:
            raise ToolError(f"Not a valid regular expression: {exc}")

        hits: list[str] = []
        targets = [root] if root.is_file() else []
        if not targets:
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
                targets.extend(Path(dirpath) / n for n in filenames
                               if fnmatch.fnmatch(n, glob_filter))

        for f in targets:
            try:
                if f.stat().st_size > MAX_READ_BYTES:
                    continue
                for i, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                    if rx.search(line):
                        rel = f.relative_to(root) if f != root else f.name
                        hits.append(f"{rel}:{i}: {line.strip()[:200]}")
                        if len(hits) >= limit:
                            return "\n".join(hits) + f"\n[stopped at {limit} matches]"
            except (OSError, UnicodeDecodeError):
                continue
        return "\n".join(hits) or f"No match for {pattern!r} under {root}."

    registry.add(Tool(
        name="grep",
        description="Search file contents with a regular expression. Returns "
                    "path:line: text for each match.",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "A Python regular expression."},
                "path": {"type": "string", "default": "."},
                "glob_filter": {"type": "string", "description": "Only search files matching this, e.g. '*.py'.", "default": "*"},
                "limit": {"type": "integer", "default": 100},
            },
            "required": ["pattern"],
        },
        fn=grep,
    ))
