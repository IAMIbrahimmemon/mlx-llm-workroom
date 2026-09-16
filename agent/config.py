"""Static configuration and the model catalogue.

The catalogue is the single source of truth shared by the CLI and the macOS
onboarding app. Anything the user is asked to choose during onboarding is
described here, not in the UI layer.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path

# ---------------------------------------------------------------- locations

WORKROOM_HOME = Path(os.environ.get("WORKROOM_HOME", Path.home() / ".workroom"))
MEMORY_DIR = WORKROOM_HOME / "memory"
STATE_FILE = WORKROOM_HOME / "state.json"
LOG_DIR = WORKROOM_HOME / "logs"

# ------------------------------------------------------------------- models


@dataclass(frozen=True)
class ModelSpec:
    key: str
    repo: str
    label: str
    gb: float          # on-disk download size, measured from the HF API
    vision: bool
    role: str          # "brain" | "compressor"
    blurb: str
    needs_ram_gb: int  # unified memory the machine must have, total
    tps: str           # rough decode speed on a base M3
    recommended: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


#: Verified against the Hugging Face API on 2026-09-15. ``gb`` is the real
#: summed blob size of the repo, which runs a little above the weight count.
#:
#: ``tps`` is MEASURED for the 9B (16.3 tok/s at 1k ctx on a base M3 --
#: ``scripts/bench_tps.py``). The others are estimates scaled by active
#: parameters, since decode here is bound by memory bandwidth; re-run the
#: bench and correct them once those weights are on a machine.
CATALOGUE: tuple[ModelSpec, ...] = (
    ModelSpec(
        key="qwen35-9b",
        repo="mlx-community/Qwen3.5-9B-MLX-4bit",
        label="Qwen3.5-9B",
        gb=5.98,
        vision=True,
        role="brain",
        blurb="Reads your screen, writes code and calls tools. "
              "Leaves room for Chrome and Xcode alongside it.",
        needs_ram_gb=16,
        tps="~16 tok/s",
        recommended=True,
    ),
    ModelSpec(
        key="qwen35-4b",
        repo="mlx-community/Qwen3.5-4B-MLX-4bit",
        label="Qwen3.5-4B",
        gb=2.90,
        vision=True,
        role="brain",
        blurb="Twice the speed, noticeably clumsier with tools. "
              "Worth it on a Mac that is always busy.",
        needs_ram_gb=8,
        tps="~30 tok/s",
    ),
    ModelSpec(
        key="qwen35-27b",
        repo="mlx-community/Qwen3.5-27B-4bit",
        label="Qwen3.5-27B",
        gb=17.0,
        vision=True,
        role="brain",
        blurb="Sharper, but it would not leave enough memory for the "
              "rest of your Mac.",
        needs_ram_gb=48,
        tps="~6 tok/s",
    ),
    ModelSpec(
        key="qwen35-2b",
        repo="mlx-community/Qwen3.5-2B-MLX-4bit",
        label="Qwen3.5-2B",
        gb=1.50,
        vision=False,
        role="compressor",
        blurb="Summarises long sessions so the brain keeps its context free.",
        needs_ram_gb=8,
        tps="~60 tok/s",
    ),
)

BY_KEY: dict[str, ModelSpec] = {m.key: m for m in CATALOGUE}

#: What a first-time user gets if they press Continue without reading.
DEFAULT_BRAIN = "qwen35-9b"
DEFAULT_COMPRESSOR = "qwen35-2b"


def brains() -> list[ModelSpec]:
    return [m for m in CATALOGUE if m.role == "brain"]


def recommended_brain() -> ModelSpec:
    return BY_KEY[DEFAULT_BRAIN]


# ------------------------------------------------------- unified memory cap

@dataclass(frozen=True)
class MemoryPreset:
    key: str
    title: str
    desc: str
    #: Fraction of total unified memory MLX may wire down.
    share: float
    ctx: int
    tps: str

    def limit_mb(self, total_gb: int) -> int:
        """Wired-memory ceiling in MB, rounded to a whole gibibyte."""
        return int(total_gb * self.share) * 1024

    def limit_gb(self, total_gb: int) -> int:
        return int(total_gb * self.share)


#: Two answers to "how much of this Mac gets to think?". The shares are
#: deliberately fractions rather than absolutes so the same presets work on a
#: 16 GB Air and a 128 GB Studio.
MEMORY_PRESETS: tuple[MemoryPreset, ...] = (
    # Measured 2026-09-15: decode sits at ~16 tok/s regardless of the ceiling,
    # because it is bound by memory *bandwidth*, not capacity. A bigger
    # ceiling therefore buys context and stability under pressure -- not
    # speed. Saying otherwise on the onboarding screen would be a lie.
    MemoryPreset(
        key="alongside",
        title="Alongside your work",
        desc="You carry on using this Mac. Chrome, Xcode and Slack stay "
             "quick, and Workroom gives ground when they need memory.",
        share=0.50,
        ctx=16384,
        tps="~16 tok/s",
    ),
    MemoryPreset(
        key="dedicated",
        title="All yours",
        desc="For a Mac you walk away from. Same speed, twice the context, "
             "and it never gets evicted when something else wants memory.",
        share=0.75,
        ctx=32768,
        tps="~16 tok/s",
    ),
)

PRESET_BY_KEY: dict[str, MemoryPreset] = {p.key: p for p in MEMORY_PRESETS}
DEFAULT_PRESET = "alongside"

# --------------------------------------------------------------- behaviour

IMG_MAX_EDGE = 1280
TOOL_OUTPUT_CAP_CHARS = 4000
AX_FUZZY_THRESHOLD = 0.85
VISION_CONFIDENCE_MIN = 0.50
COMPRESS_TRIGGER = 0.60          # fraction of context before summarising
MEMORY_FILES_AT_BOOT = 3

DENY_BUNDLES = (
    "com.apple.systempreferences",
    "com.apple.keychainaccess",
    "com.1password.1password",
    "com.agilebits.onepassword7",
)
DENY_URL_PATTERNS = (
    r".*\bbank\b.*",
    r".*\.paypal\.com",
    r"accounts\.google\.com/.*(password|signin).*",
)

# ------------------------------------------------------------------- state


def load_state() -> dict:
    """Read the choices made during onboarding. Empty dict on first run."""
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    WORKROOM_HOME.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True))
    tmp.replace(STATE_FILE)


def is_onboarded() -> bool:
    return bool(load_state().get("brain"))
