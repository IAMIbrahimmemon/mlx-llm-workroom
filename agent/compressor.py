"""Keeping the context from filling up.

A small text-only model does the summarising so the brain never stalls
mid-task to compress its own history. It runs off the hot path: the brain is
already answering by the time this is asked for anything.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

SUMMARY_PROMPT = """\
Summarise this agent transcript for your own future reference. Reply with \
JSON only, no prose around it, in exactly this shape:

{"goals": ["what the user actually wants"],
 "done": ["what has already been achieved, with concrete names and paths"],
 "open": ["what is still unresolved or was going wrong"],
 "facts": ["specific values worth keeping: paths, ports, versions, choices"]}

Keep every path, filename, port and error message exact. Drop pleasantries, \
retries that led nowhere, and anything already superseded.

TRANSCRIPT:
"""

TOOL_PROMPT = """\
Condense this tool output to the part an agent needs to carry forward. Keep \
exact identifiers, paths, numbers and error text. Drop repetition, banners \
and progress noise. No preamble -- reply with the condensed text only.

OUTPUT:
"""


@dataclass
class Digest:
    goals: list[str]
    done: list[str]
    open: list[str]
    facts: list[str]

    def as_message(self) -> str:
        def block(title: str, items: list[str]) -> str:
            return f"{title}:\n" + "\n".join(f"  - {i}" for i in items) if items else ""
        parts = [block("Goals", self.goals), block("Done", self.done),
                 block("Open", self.open), block("Facts", self.facts)]
        return "[earlier in this session]\n" + "\n".join(p for p in parts if p)


class Compressor:
    """Wraps the small model. Degrades to truncation if it will not load."""

    def __init__(self, repo: str, max_tokens: int = 700):
        self.repo = repo
        self.max_tokens = max_tokens
        self._model = None
        self._tokenizer = None
        self._failed = False

    @property
    def available(self) -> bool:
        return not self._failed

    def load(self) -> bool:
        if self._model is not None:
            return True
        if self._failed:
            return False
        try:
            from mlx_lm import load
            self._model, self._tokenizer = load(self.repo)
            return True
        except Exception:
            self._failed = True
            return False

    def _generate(self, prompt: str) -> str:
        if not self.load():
            return ""
        from mlx_lm import generate
        from mlx_lm.sample_utils import make_sampler
        messages = [{"role": "user", "content": prompt}]
        text = self._tokenizer.apply_chat_template(
            messages, add_generation_prompt=True, tokenize=False
        )
        try:
            return generate(
                self._model, self._tokenizer, prompt=text,
                max_tokens=self.max_tokens, sampler=make_sampler(temp=0.2), verbose=False,
            )
        except Exception:
            return ""

    # -- public -----------------------------------------------------------
    def digest(self, transcript: str) -> Digest | None:
        out = self._generate(SUMMARY_PROMPT + transcript)
        if not out:
            return None
        start, end = out.find("{"), out.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            obj = json.loads(out[start:end + 1])
        except ValueError:
            return None
        norm = lambda k: [str(x) for x in obj.get(k, []) if str(x).strip()]
        return Digest(goals=norm("goals"), done=norm("done"),
                      open=norm("open"), facts=norm("facts"))

    def shrink_tool_output(self, text: str, cap: int) -> str:
        """Only worth the latency when the output is much bigger than the cap."""
        if len(text) <= cap * 2:
            return text
        out = self._generate(TOOL_PROMPT + text[: cap * 8])
        return out.strip() or text
