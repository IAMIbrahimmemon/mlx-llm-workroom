"""Find what is already on this Mac, so onboarding can offer it.

Nothing here downloads or mutates anything. Every probe is cheap, bounded by
a short timeout, and safe to call on a machine with none of it installed --
the onboarding screens redraw from these results on every open.
"""

from __future__ import annotations

import json
import platform
import re
import subprocess
from dataclasses import dataclass, field, asdict
from pathlib import Path

import httpx

PROBE_TIMEOUT = 1.5


# ------------------------------------------------------------------ machine


@dataclass(frozen=True)
class Hardware:
    chip: str
    total_ram_gb: int
    macos: str
    arch: str

    @property
    def apple_silicon(self) -> bool:
        return self.arch == "arm64"

    def can_run(self, needs_ram_gb: int) -> bool:
        return self.apple_silicon and self.total_ram_gb >= needs_ram_gb

    def as_dict(self) -> dict:
        return {**asdict(self), "apple_silicon": self.apple_silicon}


def _sysctl(name: str) -> str:
    try:
        return subprocess.run(
            ["sysctl", "-n", name], capture_output=True, text=True, timeout=3
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def hardware() -> Hardware:
    try:
        total = int(_sysctl("hw.memsize") or 0)
    except ValueError:
        total = 0
    return Hardware(
        chip=_sysctl("machdep.cpu.brand_string") or "unknown",
        total_ram_gb=round(total / (1024**3)) if total else 0,
        macos=platform.mac_ver()[0] or "unknown",
        arch=platform.machine(),
    )


# ------------------------------------------------------- models on this Mac


@dataclass(frozen=True)
class LocalModel:
    """A set of weights already sitting on disk."""

    name: str
    source: str        # "huggingface" | "ollama"
    gb: float
    path: str = ""
    vision: bool | None = None   # None == we could not tell

    def as_dict(self) -> dict:
        return asdict(self)


_VISION_HINTS = ("-vl", "vl-", "vision", "llava", "moondream", "qwen3.5", "qwen3_5")


def _looks_like_vision(name: str) -> bool | None:
    low = name.lower()
    if any(h in low for h in _VISION_HINTS):
        return True
    return None


def huggingface_models() -> list[LocalModel]:
    """MLX-format models already in the Hugging Face cache."""
    try:
        from huggingface_hub import scan_cache_dir
    except ImportError:
        return []
    try:
        cache = scan_cache_dir()
    except Exception:
        return []

    out: list[LocalModel] = []
    for repo in cache.repos:
        if repo.repo_type != "model":
            continue
        files = {f.file_name for rev in repo.revisions for f in rev.files}
        # An MLX text/vision model always ships a config and safetensors.
        if not any(f.endswith(".safetensors") for f in files):
            continue
        vision = None
        cfg = _read_cached_config(repo)
        if cfg is not None:
            vision = "vision_config" in cfg
        out.append(
            LocalModel(
                name=repo.repo_id,
                source="huggingface",
                gb=round(repo.size_on_disk / 1e9, 2),
                path=str(repo.repo_path),
                vision=vision if vision is not None else _looks_like_vision(repo.repo_id),
            )
        )
    return sorted(out, key=lambda m: -m.gb)


def _read_cached_config(repo) -> dict | None:
    for rev in repo.revisions:
        for f in rev.files:
            if f.file_name == "config.json":
                try:
                    return json.loads(Path(f.file_path).read_text())
                except (OSError, ValueError):
                    return None
    return None


def ollama_models(base: str = "http://127.0.0.1:11434") -> list[LocalModel]:
    """Models Ollama has pulled. Cloud-hosted entries are skipped -- they are
    not local weights and running one would defeat the point of Workroom."""
    try:
        r = httpx.get(f"{base}/api/tags", timeout=PROBE_TIMEOUT)
        r.raise_for_status()
        payload = r.json()
    except Exception:
        return []

    out: list[LocalModel] = []
    for m in payload.get("models", []):
        name = m.get("name", "")
        if m.get("remote_model") or name.endswith(":cloud"):
            continue
        fam = (m.get("details") or {}).get("families") or []
        out.append(
            LocalModel(
                name=name,
                source="ollama",
                gb=round((m.get("size") or 0) / 1e9, 2),
                vision=True if any("clip" in f or "vision" in f for f in fam)
                       else _looks_like_vision(name),
            )
        )
    return sorted(out, key=lambda m: -m.gb)


def local_models() -> list[LocalModel]:
    return huggingface_models() + ollama_models()


# ---------------------------------------------------------------- gateways


@dataclass
class Gateway:
    """An OpenAI-compatible server already listening on this machine."""

    key: str
    label: str
    base_url: str
    docs: str = ""
    reachable: bool = False
    models: list[str] = field(default_factory=list)
    detail: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


KNOWN_GATEWAYS: tuple[tuple[str, str, str, str], ...] = (
    ("ollama", "Ollama", "http://127.0.0.1:11434", "ollama serve"),
    ("lmstudio", "LM Studio", "http://127.0.0.1:1234", "Developer > Start Server"),
    ("llamacpp", "llama.cpp", "http://127.0.0.1:8080", "llama-server -m model.gguf"),
    ("vllm", "vLLM", "http://127.0.0.1:8000", "vllm serve <model>"),
)


def probe_gateway(key: str, label: str, base_url: str, docs: str = "") -> Gateway:
    gw = Gateway(key=key, label=label, base_url=base_url, docs=docs)

    # Ollama speaks its own dialect as well as the OpenAI one; /api/tags is
    # the cheaper and more informative of the two.
    paths = ["/api/tags"] if key == "ollama" else ["/v1/models"]
    for path in paths:
        try:
            r = httpx.get(f"{base_url}{path}", timeout=PROBE_TIMEOUT)
            r.raise_for_status()
            body = r.json()
        except Exception as exc:
            gw.detail = _why(exc, docs)
            continue

        gw.reachable = True
        if path == "/api/tags":
            gw.models = [m.get("name", "") for m in body.get("models", [])]
        else:
            gw.models = [m.get("id", "") for m in body.get("data", [])]
        gw.detail = (
            f"{len(gw.models)} model{'s' if len(gw.models) != 1 else ''} available"
            if gw.models else "Running, but no models loaded"
        )
        break
    return gw


def _why(exc: Exception, docs: str) -> str:
    if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
        return f"Nothing listening. Start it with: {docs}" if docs else "Nothing listening."
    if isinstance(exc, httpx.TimeoutException):
        return "Timed out."
    return "Did not answer as expected."


def gateways() -> list[Gateway]:
    return [probe_gateway(*spec) for spec in KNOWN_GATEWAYS]


# ------------------------------------------------------------------ summary


def survey() -> dict:
    """Everything the onboarding app needs, in one JSON-serialisable blob."""
    hw = hardware()
    return {
        "hardware": hw.as_dict(),
        "local_models": [m.as_dict() for m in local_models()],
        "gateways": [g.as_dict() for g in gateways()],
    }


if __name__ == "__main__":
    print(json.dumps(survey(), indent=2))
