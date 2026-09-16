"""What the agent is not allowed to do on its own.

Three levels. ``ALLOW`` runs. ``CONFIRM`` stops and asks the human, because
the action is plausible but expensive to undo. ``DENY`` never runs, whatever
the model says, because no plausible task needs it.

The rule of thumb for putting a pattern in ``DENY`` rather than ``CONFIRM``:
would a reasonable user, woken at 3am, ever say yes? If they might, it is a
confirm.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from ..config import DENY_BUNDLES, DENY_URL_PATTERNS


class Level(str, Enum):
    ALLOW = "allow"
    CONFIRM = "confirm"
    DENY = "deny"


@dataclass(frozen=True)
class Verdict:
    level: Level
    reason: str = ""

    @property
    def blocked(self) -> bool:
        return self.level is Level.DENY

    @property
    def needs_human(self) -> bool:
        return self.level is Level.CONFIRM


# Ordered: the first match wins, so denials are listed before confirmations.
_DENY: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r":\s*\(\s*\)\s*\{.*\}\s*;\s*:"), "fork bomb"),
    (re.compile(r"\bmkfs(\.|\b)"), "formats a filesystem"),
    (re.compile(r"\bdd\b[^|]*\bof=/dev/r?disk"), "writes raw blocks to a disk device"),
    (re.compile(r"\bdiskutil\s+(erase|reformat|partition)"), "erases a volume"),
    # Only a recursive delete aimed at root or the home directory itself. A
    # recursive delete of a project subdirectory is a CONFIRM, not a denial --
    # people really do mean "rm -rf build".
    (re.compile(r"\brm\s+(?:-\S*[rR]\S*\s+)(?:-\S+\s+)*"
                r"(?:/|~|\$HOME|\$\{HOME\}|/\*|~/\*)\s*$"),
     "recursive delete of a home or root path"),
    (re.compile(r"\bcsrutil\s+disable"), "disables System Integrity Protection"),
    (re.compile(r"\bspctl\s+--master-disable"), "disables Gatekeeper"),
    (re.compile(r"\b(security|defaults)\s+.*(-w\s+)?.*keychain.*dump"), "dumps the keychain"),
)

_CONFIRM: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^\s*sudo\b"), "runs as root"),
    (re.compile(r"\brm\b\s+(-[a-zA-Z]+\s+)*(-[a-zA-Z]*[rRf])"), "recursive or forced delete"),
    (re.compile(r"\bgit\s+push\b.*\s(--force\b|-f\b)"), "force-pushes, rewriting remote history"),
    (re.compile(r"\bgit\s+reset\s+--hard\b"), "discards uncommitted work"),
    (re.compile(r"\bgit\s+clean\b.*-[a-zA-Z]*f"), "deletes untracked files"),
    (re.compile(r"\b(curl|wget)\b[^|]*\|\s*(sudo\s+)?(ba|z|fi)?sh\b"), "pipes a download straight into a shell"),
    (re.compile(r"\bchmod\s+(-R\s+)?777\b"), "makes files world-writable"),
    (re.compile(r"\b(killall|pkill)\b"), "kills processes by name"),
    (re.compile(r"\b(brew|npm|pip|uv)\s+(uninstall|remove|rm)\b"), "removes installed software"),
    (re.compile(r"\bshutdown\b|\breboot\b"), "restarts the machine"),
    (re.compile(r"\bosascript\b"), "drives other apps through AppleScript"),
    (re.compile(r"(^|\s)>\s*[^\s|&;>]+"), "overwrites a file in place"),
    (re.compile(r"\bmv\b\s+[^|]*\s+/(?!tmp|var/tmp)"), "moves something to a system path"),
)

_DENY_BUNDLE_RE = tuple(
    re.compile(p.replace(".", r"\.").replace("*", ".*") + "$") for p in DENY_BUNDLES
)
_DENY_URL_RE = tuple(re.compile(p, re.IGNORECASE) for p in DENY_URL_PATTERNS)


def classify_shell(cmd: str) -> Verdict:
    """Decide what to do with a shell command before it runs."""
    text = cmd.strip()
    if not text:
        return Verdict(Level.DENY, "empty command")
    for pat, why in _DENY:
        if pat.search(text):
            return Verdict(Level.DENY, why)
    for pat, why in _CONFIRM:
        if pat.search(text):
            return Verdict(Level.CONFIRM, why)
    return Verdict(Level.ALLOW)


def classify_app(bundle_id: str) -> Verdict:
    """Apps the agent may not click around in, however it was asked."""
    bid = (bundle_id or "").strip().lower()
    for pat in _DENY_BUNDLE_RE:
        if pat.match(bid):
            return Verdict(Level.DENY, f"{bundle_id} holds credentials or system settings")
    return Verdict(Level.ALLOW)


def classify_url(url: str) -> Verdict:
    """Pages the agent may not act on, even when Chrome is frontmost."""
    for pat in _DENY_URL_RE:
        if pat.search(url or ""):
            return Verdict(Level.DENY, "a banking or sign-in page")
    return Verdict(Level.ALLOW)


class Guard:
    """Session-wide policy: dry-run, the halt flag, and the confirm callback.

    ``confirm`` is supplied by the front end (the REPL prompts; a headless
    run can pass a callable that always denies). It is never bypassed.
    """

    def __init__(self, dry_run: bool = False, confirm=None, auto_approve: bool = False):
        self.dry_run = dry_run
        self.auto_approve = auto_approve
        self._confirm = confirm
        self._halted = False

    # -- halt -------------------------------------------------------------
    def halt(self) -> None:
        self._halted = True

    def resume(self) -> None:
        self._halted = False

    @property
    def halted(self) -> bool:
        return self._halted

    # -- decisions --------------------------------------------------------
    def check_shell(self, cmd: str) -> tuple[bool, str]:
        """``(may_run, reason)``. Asks the human when the verdict is CONFIRM."""
        if self._halted:
            return False, "halted"
        v = classify_shell(cmd)
        if v.blocked:
            return False, f"refused: {v.reason}"
        if v.needs_human and not self.auto_approve:
            if self._confirm is None:
                return False, f"needs confirmation ({v.reason}) and nothing can ask"
            if not self._confirm(cmd, v.reason):
                return False, f"declined by the user ({v.reason})"
        if self.dry_run:
            return False, "dry run: not executed"
        return True, ""
