"""The unified-memory ceiling.

On Apple silicon the model's weights, your browser's tabs and the window
server all draw on the same pool. Workroom therefore asks, once, how much of that
pool it is allowed to wire down, and holds itself to the answer.

Two layers, and they are not the same thing:

* **Per-process** (``mlx.core``) -- always applied, never needs a password.
  This is the ceiling Workroom holds *itself* to.
* **System-wide** (``iogpu.wired_limit_mb``) -- only needed when a preset
  asks for more than macOS will hand a single process by default. Requires
  an admin password, and resets on reboot.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

import mlx.core as mx

from .config import MemoryPreset, PRESET_BY_KEY, DEFAULT_PRESET
from .discovery import Hardware, hardware

SYSCTL_KEY = "iogpu.wired_limit_mb"


@dataclass(frozen=True)
class Ceiling:
    preset: str
    limit_gb: int
    limit_mb: int
    total_gb: int
    #: What macOS will give one process before the sysctl has to be raised.
    recommended_gb: float
    needs_sysctl: bool
    ctx: int

    @property
    def sysctl_command(self) -> str:
        return f"sudo sysctl -w {SYSCTL_KEY}={self.limit_mb}"

    def as_dict(self) -> dict:
        return {
            "preset": self.preset,
            "limit_gb": self.limit_gb,
            "limit_mb": self.limit_mb,
            "total_gb": self.total_gb,
            "recommended_gb": round(self.recommended_gb, 1),
            "needs_sysctl": self.needs_sysctl,
            "ctx": self.ctx,
            "sysctl_command": self.sysctl_command,
        }


def recommended_working_set_gb() -> float:
    """What Metal will hand a single process without raising the sysctl."""
    try:
        info = mx.device_info()
        return info["max_recommended_working_set_size"] / (1024**3)
    except Exception:
        # Metal's default is about two thirds of installed memory.
        return hardware().total_ram_gb * 0.66


def plan(preset_key: str = DEFAULT_PRESET, hw: Hardware | None = None) -> Ceiling:
    """Work out the ceiling for a preset without applying anything."""
    hw = hw or hardware()
    preset: MemoryPreset = PRESET_BY_KEY.get(preset_key) or PRESET_BY_KEY[DEFAULT_PRESET]
    rec = recommended_working_set_gb()
    limit_gb = preset.limit_gb(hw.total_ram_gb)
    return Ceiling(
        preset=preset.key,
        limit_gb=limit_gb,
        limit_mb=preset.limit_mb(hw.total_ram_gb),
        total_gb=hw.total_ram_gb,
        recommended_gb=rec,
        needs_sysctl=limit_gb > rec,
        ctx=preset.ctx,
    )


def current_sysctl_mb() -> int:
    """0 means macOS is managing it, which is the out-of-the-box state."""
    try:
        out = subprocess.run(
            ["sysctl", "-n", SYSCTL_KEY], capture_output=True, text=True, timeout=3
        )
        return int(out.stdout.strip() or 0)
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0


def apply(ceiling: Ceiling) -> None:
    """Hold *this process* to the ceiling. Never prompts for a password.

    ``set_memory_limit`` is the hard stop: MLX raises rather than letting the
    machine swap. The cache limit is kept well under it so freed blocks are
    returned to the system instead of being hoarded between turns.
    """
    limit_bytes = ceiling.limit_gb * 1024**3
    mx.set_memory_limit(limit_bytes)
    mx.set_cache_limit(limit_bytes // 4)
    try:
        mx.set_wired_limit(limit_bytes)
    except Exception:
        # Asking to wire more than the system sysctl allows is refused. The
        # per-process memory limit above still holds, so this is survivable:
        # the model runs, and pages may be evicted under pressure.
        pass


def raise_system_limit(ceiling: Ceiling, dry_run: bool = False) -> tuple[bool, str]:
    """Raise the system-wide wired limit. Prompts for an admin password.

    Returns ``(changed, message)``. Only called when ``needs_sysctl`` is set
    and the user has agreed to it -- never silently.
    """
    if not ceiling.needs_sysctl:
        return False, "System limit is already high enough."
    if current_sysctl_mb() >= ceiling.limit_mb:
        return False, f"{SYSCTL_KEY} is already {current_sysctl_mb()} MB."
    if dry_run:
        return False, ceiling.sysctl_command
    if not shutil.which("sysctl"):
        return False, "sysctl not found."

    try:
        proc = subprocess.run(
            ["sudo", "-n", "sysctl", "-w", f"{SYSCTL_KEY}={ceiling.limit_mb}"],
            capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"Could not run sysctl: {exc}"

    if proc.returncode == 0:
        return True, f"{SYSCTL_KEY} = {ceiling.limit_mb} MB (resets on reboot)."
    return False, (
        "Needs an admin password. Run this yourself, then start Workroom again:\n"
        f"    {ceiling.sysctl_command}"
    )


def in_use() -> dict:
    """Live memory figures, for the REPL footer."""
    return {
        "active_gb": round(mx.get_active_memory() / 1024**3, 2),
        "cache_gb": round(mx.get_cache_memory() / 1024**3, 2),
        "peak_gb": round(mx.get_peak_memory() / 1024**3, 2),
    }


if __name__ == "__main__":
    import json
    for key in ("alongside", "dedicated"):
        c = plan(key)
        print(json.dumps(c.as_dict(), indent=2))
    print("current sysctl:", current_sysctl_mb(), "MB (0 = macOS managed)")
