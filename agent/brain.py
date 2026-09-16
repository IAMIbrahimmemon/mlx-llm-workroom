"""The one model that does everything.

Qwen3.5-9B handles text, tool calling and screen vision in a single set of
weights, so there is one loader, one KV cache and one process. An image is
not a hand-off to a sub-agent -- it is just another item in this model's own
context.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence

from .toolcall import CLOSE, ToolCall, parse_all, strip_calls

DEFAULT_MAX_TOKENS = 2048


@dataclass
class Stats:
    prompt_tokens: int = 0
    generation_tokens: int = 0
    cached_tokens: int = 0
    tps: float = 0.0
    seconds: float = 0.0
    peak_gb: float = 0.0

    def line(self) -> str:
        cached = f", {self.cached_tokens} cached" if self.cached_tokens else ""
        return (f"{self.generation_tokens} tok in {self.seconds:.1f}s "
                f"({self.tps:.1f} tok/s, {self.prompt_tokens} prompt{cached})")


@dataclass
class Reply:
    text: str                                   # prose, tool calls removed
    raw: str                                    # everything the model emitted
    calls: list[ToolCall] = field(default_factory=list)
    stats: Stats = field(default_factory=Stats)

    @property
    def wants_tools(self) -> bool:
        return bool(self.calls)


class Brain:
    """Wraps mlx-vlm. Loads lazily so the REPL can draw before weights land."""

    def __init__(self, repo: str, ctx: int = 16384, think: bool = False,
                 max_tokens: int = DEFAULT_MAX_TOKENS, temperature: float = 0.6):
        self.repo = repo
        self.ctx = ctx
        self.think = think
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._model = None
        self._processor = None
        self._config = None
        self._cache = None

    # -- loading ----------------------------------------------------------
    @property
    def loaded(self) -> bool:
        return self._model is not None

    def load(self) -> None:
        if self.loaded:
            return
        from mlx_vlm import PromptCacheState, load
        from mlx_vlm.utils import load_config

        self._model, self._processor = load(self.repo, lazy=False)
        self._config = load_config(self.repo)
        # Reused across turns: the system prompt and the settled part of the
        # transcript are a stable prefix, so only new tokens get prefilled.
        self._cache = PromptCacheState()

    def reset_cache(self) -> None:
        """After compression rewrites history the old prefix no longer holds."""
        if self.loaded:
            from mlx_vlm import PromptCacheState
            self._cache = PromptCacheState()

    # -- generation -------------------------------------------------------
    def complete(
        self,
        messages: Sequence[dict],
        tools: Sequence[dict] | None = None,
        images: Sequence[str] | None = None,
        on_text: Callable[[str], None] | None = None,
        think: bool | None = None,
    ) -> Reply:
        """One assistant turn. Streams to ``on_text`` if given.

        Stops as soon as a complete ``</tool_call>`` has been emitted: anything
        the model writes after that is speculation about a result it has not
        seen yet, and generating it wastes the user's tokens and time.
        """
        self.load()
        from mlx_vlm import apply_chat_template, stream_generate

        imgs = list(images or [])
        prompt = apply_chat_template(
            self._processor,
            self._config,
            list(messages),
            num_images=len(imgs),
            tools=list(tools) if tools else None,
        )

        started = time.perf_counter()
        pieces: list[str] = []
        last = None
        kwargs = {
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "prompt_cache_state": self._cache,
            "enable_thinking": self.think if think is None else think,
        }
        if imgs:
            kwargs["image"] = imgs

        for chunk in stream_generate(self._model, self._processor, prompt, **kwargs):
            piece = chunk.text or ""
            if piece:
                pieces.append(piece)
                if on_text:
                    on_text(piece)
            last = chunk
            if CLOSE in "".join(pieces[-8:]) or CLOSE in "".join(pieces):
                break

        raw = "".join(pieces)
        stats = Stats(seconds=time.perf_counter() - started)
        if last is not None:
            stats.prompt_tokens = getattr(last, "prompt_tokens", 0) or 0
            stats.generation_tokens = getattr(last, "generation_tokens", 0) or 0
            stats.cached_tokens = getattr(last, "cached_tokens", 0) or 0
            stats.tps = getattr(last, "generation_tps", 0.0) or 0.0
            stats.peak_gb = round((getattr(last, "peak_memory", 0) or 0), 2)
        if not stats.tps and stats.seconds > 0:
            stats.tps = stats.generation_tokens / stats.seconds

        return Reply(text=strip_calls(raw), raw=raw, calls=parse_all(raw), stats=stats)

    # -- counting ---------------------------------------------------------
    def count_tokens(self, messages: Sequence[dict], tools: Sequence[dict] | None = None) -> int:
        """Roughly how full the context is. Used to decide when to compress."""
        self.load()
        from mlx_vlm import apply_chat_template
        text = apply_chat_template(
            self._processor, self._config, list(messages),
            tools=list(tools) if tools else None,
        )
        tok = getattr(self._processor, "tokenizer", self._processor)
        try:
            return len(tok.encode(text))
        except Exception:
            return len(text) // 4        # a serviceable fallback for English

    @property
    def context_used(self) -> float:
        return 0.0
