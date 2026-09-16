"""Parsing tool calls out of a token stream.

Qwen3.5 emits its native XML-ish form::

    <tool_call><function=bash><parameter=cmd>ls -la</parameter></function></tool_call>

A 4-bit quant gets this wrong often enough that a strict parser would stall
the agent, so we also accept the JSON form models fall back to under
pressure. Everything is normalised to a :class:`ToolCall`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

OPEN = "<tool_call>"
CLOSE = "</tool_call>"

_BLOCK = re.compile(r"<tool_call>(.*?)</tool_call>", re.DOTALL)
_FUNC = re.compile(r"<function\s*=\s*([A-Za-z0-9_.-]+)\s*>(.*?)</function>", re.DOTALL)
_PARAM = re.compile(r"<parameter\s*=\s*([A-Za-z0-9_.-]+)\s*>(.*?)</parameter>", re.DOTALL)
# Some quants drop the closing </function> but keep the parameters.
_FUNC_LOOSE = re.compile(r"<function\s*=\s*([A-Za-z0-9_.-]+)\s*>(.*)", re.DOTALL)


class ToolCallError(ValueError):
    """Raised when a block looks like a tool call but cannot be read."""


@dataclass
class ToolCall:
    name: str
    args: dict[str, object] = field(default_factory=dict)
    raw: str = ""

    def __repr__(self) -> str:  # keeps REPL traces short
        inner = ", ".join(f"{k}={v!r}" for k, v in self.args.items())
        return f"{self.name}({inner})"


def _unwrap(text: str) -> str:
    """Drop the newlines the chat template puts around a parameter value.

    Qwen writes each value on its own line::

        <parameter=path>
        pyproject.toml
        </parameter>

    so exactly one leading and one trailing newline are formatting, not
    content. Observed on the 4-bit quant: without this, every path argument
    arrives as "\npyproject.toml\n" and every file tool fails. Only one
    newline is removed at each end, so a value that genuinely starts with a
    blank line keeps the rest.
    """
    if text.startswith("\r\n"):
        text = text[2:]
    elif text.startswith("\n"):
        text = text[1:]
    if text.endswith("\r\n"):
        text = text[:-2]
    elif text.endswith("\n"):
        text = text[:-1]
    return text


def _coerce(text: str) -> object:
    """Parameters arrive as text. Recover the obvious scalars."""
    text = _unwrap(text)
    s = text.strip()
    low = s.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("null", "none"):
        return None
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"-?\d*\.\d+", s):
        return float(s)
    if s[:1] in "[{" and s[-1:] in "]}":
        try:
            return json.loads(s)
        except ValueError:
            return text
    return text


def _from_xml(body: str) -> ToolCall | None:
    m = _FUNC.search(body) or _FUNC_LOOSE.search(body)
    if not m:
        return None
    name, inner = m.group(1), m.group(2)
    args = {k: _coerce(v) for k, v in _PARAM.findall(inner)}
    return ToolCall(name=name, args=args, raw=body)


def _from_json(body: str) -> ToolCall | None:
    s = body.strip()
    if not s.startswith("{"):
        start = s.find("{")
        if start == -1:
            return None
        s = s[start:]
    try:
        obj = json.loads(s)
    except ValueError:
        return None
    if not isinstance(obj, dict):
        return None

    # {"name": ..., "arguments": {...}} and the OpenAI {"function": {...}} shape
    if "function" in obj and isinstance(obj["function"], dict):
        obj = obj["function"]
    name = obj.get("name") or obj.get("tool") or obj.get("tool_name")
    if not name:
        return None
    args = obj.get("arguments", obj.get("args", obj.get("parameters", {})))
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            args = {"input": args}
    if not isinstance(args, dict):
        args = {"input": args}
    return ToolCall(name=str(name), args=args, raw=body)


def parse_block(body: str) -> ToolCall:
    """Read one tool-call body. Raises :class:`ToolCallError` on nonsense."""
    call = _from_xml(body) or _from_json(body)
    if call is None:
        raise ToolCallError(f"could not read a tool call from: {body[:200]!r}")
    return call


def parse_all(text: str) -> list[ToolCall]:
    """Every well-formed call in a completed message. Unreadable blocks are
    skipped -- the loop retries once with the parse error fed back."""
    out: list[ToolCall] = []
    for body in _BLOCK.findall(text):
        try:
            out.append(parse_block(body))
        except ToolCallError:
            continue
    if out:
        return out

    # A stream stopped on </tool_call> has an opening tag with no closer.
    if OPEN in text:
        try:
            return [parse_block(text.split(OPEN, 1)[1])]
        except ToolCallError:
            return []
    # Some turns emit a bare JSON object with no wrapper at all.
    bare = _from_json(text)
    return [bare] if bare else []


def strip_calls(text: str) -> str:
    """The prose the model wrote around its tool calls."""
    return _BLOCK.sub("", text).split(OPEN)[0].strip()


def format_result(name: str, content: str, ok: bool = True) -> str:
    """What gets injected back into the transcript."""
    status = "" if ok else ' status="error"'
    return f'<tool_result name="{name}"{status}>\n{content}\n</tool_result>'
