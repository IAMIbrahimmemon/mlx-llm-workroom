"""Tool definitions and dispatch.

Schemas are plain JSON Schema, which is what the Qwen3.5 chat template wants
for its ``tools=`` argument. Keeping them here -- rather than in docstrings
parsed at import time -- means the prompt the model sees is reviewable.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Callable

from ..config import TOOL_OUTPUT_CAP_CHARS
from ..toolcall import ToolCall


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    fn: Callable[..., str]

    @property
    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolError(Exception):
    """A tool failed in a way the model should see and can act on."""


@dataclass
class Registry:
    _tools: dict[str, Tool] = field(default_factory=dict)

    def add(self, tool: Tool) -> Tool:
        self._tools[tool.name] = tool
        return tool

    def tool(self, name: str, description: str, parameters: dict):
        """Decorator form."""
        def wrap(fn: Callable[..., str]) -> Callable[..., str]:
            self.add(Tool(name=name, description=description, parameters=parameters, fn=fn))
            return fn
        return wrap

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def schemas(self) -> list[dict]:
        return [self._tools[n].schema for n in self.names()]

    def dispatch(self, call: ToolCall, cap: int = TOOL_OUTPUT_CAP_CHARS) -> tuple[str, bool]:
        """Run a call. Returns ``(content, ok)`` -- never raises.

        A failure is not an exception to the caller: the model is supposed to
        read the error and try something else, so it comes back as content.
        """
        tool = self.get(call.name)
        if tool is None:
            close = [n for n in self.names() if n.startswith(call.name[:3])]
            hint = f" Did you mean {close[0]}?" if close else ""
            return f"No tool called {call.name!r}. Available: {', '.join(self.names())}.{hint}", False

        # Reject unknown keyword arguments before calling, so a hallucinated
        # parameter produces a useful message instead of a TypeError.
        sig = inspect.signature(tool.fn)
        allowed = set(sig.parameters)
        unknown = set(call.args) - allowed
        if unknown and not any(
            p.kind is inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        ):
            return (
                f"{call.name} has no parameter(s) {', '.join(sorted(unknown))}. "
                f"It takes: {', '.join(sorted(allowed))}."
            ), False

        try:
            out = tool.fn(**call.args)
        except ToolError as exc:
            return str(exc), False
        except TypeError as exc:
            return f"{call.name}: {exc}", False
        except Exception as exc:  # a tool blowing up must not kill the session
            return f"{call.name} failed: {type(exc).__name__}: {exc}", False

        text = out if isinstance(out, str) else repr(out)
        return truncate(text, cap), True


def truncate(text: str, cap: int) -> str:
    """Trim the middle, not the tail -- the end of a traceback or a file
    listing is usually the part that matters."""
    if len(text) <= cap:
        return text
    head = cap * 2 // 3
    tail = cap - head
    dropped = len(text) - head - tail
    return (
        f"{text[:head]}\n\n... [{dropped:,} characters cut from the middle; "
        f"ask for a narrower slice if you need them] ...\n\n{text[-tail:]}"
    )
