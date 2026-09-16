"""The agent loop: generate, dispatch tools, inject results, resume."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import config as cfg
from .brain import Brain, Reply
from .compressor import Compressor
from .toolcall import format_result
from .tools import memory as memtool
from .tools.registry import Registry

#: How many times the model may call tools before we insist on an answer.
#: A capable model finishes ordinary tasks in two or three; the cap exists to
#: stop a confused one from grinding all night on the same failing command.
MAX_STEPS = 12

SYSTEM = """\
You are Workroom, a computer-use agent running entirely on this Mac. No part of \
this conversation leaves the machine.

Work like a careful colleague at a terminal:
- Look before you act. Read a file before editing it; check a path exists \
before writing to it.
- Prefer the narrow tool. `read_file` and `edit_file` over `bash cat` and \
`bash sed`; `grep` over `bash grep`.
- One step at a time. Call a tool, read the real result, then decide. Never \
write what you imagine a result will be.
- When a tool fails, read the error and change your approach. Do not retry \
the identical command.
- Destructive commands stop and ask the user. If one is refused, that is an \
answer: find another way or say why you cannot.
- Say what you found in plain words. No preamble, no restating the question.

Tools are called as:
<tool_call><function=NAME><parameter=KEY>VALUE</parameter></function></tool_call>
Stop after the closing tag and wait for the result."""


@dataclass
class Step:
    """One tool call and what came back, for the UI to render."""
    name: str
    args: dict
    result: str
    ok: bool


@dataclass
class Outcome:
    text: str
    steps: list[Step] = field(default_factory=list)
    stopped_early: bool = False


class Agent:
    def __init__(self, brain: Brain, registry: Registry,
                 compressor: Compressor | None = None,
                 project_file: Path | None = None,
                 ctx: int = 16384):
        self.brain = brain
        self.registry = registry
        self.compressor = compressor
        self.ctx = ctx
        self.messages: list[dict] = [{"role": "system", "content": self._system(project_file)}]

    # -- prompt -----------------------------------------------------------
    def _system(self, project_file: Path | None) -> str:
        parts = [SYSTEM]
        pf = project_file or Path.cwd() / "AGENT.md"
        if pf.exists():
            try:
                body = pf.read_text().strip()
                if body:
                    parts.append(f"\n# This project\n{body}")
            except OSError:
                pass
        notes = memtool.recent()
        if notes:
            parts.append(f"\n# From earlier sessions\n{notes}")
        return "\n".join(parts)

    # -- the loop ---------------------------------------------------------
    def send(
        self,
        user_text: str,
        on_text: Callable[[str], None] | None = None,
        on_step: Callable[[Step], None] | None = None,
        images: list[str] | None = None,
    ) -> Outcome:
        self.messages.append({"role": "user", "content": user_text})
        steps: list[Step] = []
        tools = self.registry.schemas()
        pending_images = images

        for _ in range(MAX_STEPS):
            self._compress_if_full(tools)
            reply: Reply = self.brain.complete(
                self.messages, tools=tools, images=pending_images, on_text=on_text
            )
            pending_images = None
            self.messages.append({"role": "assistant", "content": reply.raw})

            if not reply.wants_tools:
                return Outcome(text=reply.text or reply.raw.strip(), steps=steps)

            for call in reply.calls:
                content, ok = self.registry.dispatch(call)
                if ok and self.compressor and len(content) > cfg.TOOL_OUTPUT_CAP_CHARS:
                    content = self.compressor.shrink_tool_output(
                        content, cfg.TOOL_OUTPUT_CAP_CHARS
                    )
                step = Step(name=call.name, args=call.args, result=content, ok=ok)
                steps.append(step)
                if on_step:
                    on_step(step)
                self.messages.append(
                    {"role": "user", "content": format_result(call.name, content, ok)}
                )

        return Outcome(
            text="I stopped after "
                 f"{MAX_STEPS} tool calls without reaching an answer. Here is where "
                 "I got to -- tell me how you want to narrow it.",
            steps=steps,
            stopped_early=True,
        )

    # -- context ----------------------------------------------------------
    def _compress_if_full(self, tools: list[dict]) -> None:
        if not self.compressor or not self.compressor.available:
            return
        used = self.brain.count_tokens(self.messages, tools)
        if used < self.ctx * cfg.COMPRESS_TRIGGER:
            return

        # Keep the system prompt and the most recent exchanges verbatim; the
        # older half becomes a digest.
        head, tail = self.messages[0], self.messages[1:]
        if len(tail) < 6:
            return
        cut = len(tail) // 2
        older, recent = tail[:cut], tail[cut:]
        transcript = "\n\n".join(f"{m['role']}: {m['content']}" for m in older)

        digest = self.compressor.digest(transcript)
        if digest is None:
            return
        self.messages = [head, {"role": "user", "content": digest.as_message()}, *recent]
        self.brain.reset_cache()

    def context_fraction(self, tools: list[dict] | None = None) -> float:
        try:
            return self.brain.count_tokens(self.messages, tools or self.registry.schemas()) / self.ctx
        except Exception:
            return 0.0
