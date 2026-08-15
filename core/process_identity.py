"""Canonical live_bot process identity contract (ops only — no trading logic).

RUNTIME_OPS_ONLY | PAPER_ONLY | NO_BROKER
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parents[1]
PID_FILE = PROJECT_DIR / "bot_pid.txt"
STATUS_FILE = PROJECT_DIR / "bot_status.txt"
RECOVERY_STATE_FILE = PROJECT_DIR / "bot_recovery_state.json"
BOT_SCRIPT_NAME = "live_bot.py"

VERIFY_WINDOW_SEC = 2.0
RESTART_COOLDOWN_SEC = 60
MAX_FAILURES_WINDOW = 3
FAILURE_WINDOW_SEC = 900

_REJECT_SUBSTRINGS = (
    "cursorsandbox",
    "pgrep",
    "market_session_guard",
    "unittest",
    "tae_stage3f",
)


@dataclass
class BotProcessIdentity:
    pid: int | None
    alive: bool
    cmdline: str | None
    matches_live_bot: bool
    project_match: bool
    zombie: bool
    source: str

    @property
    def valid(self) -> bool:
        return bool(
            self.pid
            and self.alive
            and self.matches_live_bot
            and self.project_match
            and not self.zombie
        )


def _run(cmd: list[str], *, timeout: float = 5.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def pid_exists(pid: int) -> bool:
    """True when the OS still has this PID.

    PermissionError means the process exists but signaling is denied (common in
    sandboxes) — treat as alive. Fall back to ``ps`` when kill(0) is inconclusive.
    """
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        pass
    try:
        result = _run(["ps", "-p", str(pid), "-o", "pid="])
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and bool((result.stdout or "").strip())


def read_cmdline(pid: int) -> str | None:
    try:
        result = _run(["ps", "-p", str(pid), "-o", "args="])
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    text = (result.stdout or "").strip()
    return text or None


def read_state(pid: int) -> str | None:
    try:
        result = _run(["ps", "-p", str(pid), "-o", "state="])
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return (result.stdout or "").strip() or None


def is_zombie(pid: int) -> bool:
    state = read_state(pid) or ""
    return state.upper().startswith("Z")


def _executable_looks_like_python(token: str) -> bool:
    base = token.rsplit("/", 1)[-1].lower()
    return "python" in base


def read_process_cwd(pid: int) -> str | None:
    """Best-effort process cwd (macOS/Linux via lsof)."""
    try:
        result = _run(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"])
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    for line in (result.stdout or "").splitlines():
        if line.startswith("n") and len(line) > 1:
            return line[1:]
    return None


def cmdline_matches_live_bot(cmdline: str | None, *, project_dir: Path = PROJECT_DIR) -> bool:
    """True only for a Python process whose argv includes the live_bot entrypoint."""
    if not cmdline:
        return False
    lowered = cmdline.lower()
    if any(s in lowered for s in _REJECT_SUBSTRINGS):
        return False

    tokens = cmdline.split()
    if not tokens:
        return False
    if not _executable_looks_like_python(tokens[0]):
        return False

    script_token = None
    for token in tokens[1:]:
        normalized = token.replace("\\", "/")
        if normalized == BOT_SCRIPT_NAME or normalized.endswith("/" + BOT_SCRIPT_NAME):
            script_token = normalized
            break
    if script_token is None:
        return False

    project = str(project_dir.resolve()).replace("\\", "/")
    if project in script_token:
        return True
    # Relative `python live_bot.py` — ownership confirmed via cwd in project_match.
    return script_token == BOT_SCRIPT_NAME or script_token.endswith("/" + BOT_SCRIPT_NAME)


def project_match_for_cmdline(
    cmdline: str | None,
    *,
    project_dir: Path = PROJECT_DIR,
    pid: int | None = None,
) -> bool:
    """True only when the process belongs to this project directory."""
    if not cmdline_matches_live_bot(cmdline, project_dir=project_dir):
        return False
    project = str(project_dir.resolve()).replace("\\", "/")
    normalized = (cmdline or "").replace("\\", "/")
    if project in normalized:
        return True

    tokens = normalized.split()
    for token in tokens:
        if token.endswith("/" + BOT_SCRIPT_NAME) and project not in token:
            # Absolute path into a different checkout.
            return False

    # Relative entrypoint — require live process cwd == this project.
    if BOT_SCRIPT_NAME not in tokens:
        return False
    if pid is None:
        return False
    cwd = read_process_cwd(pid)
    if not cwd:
        return False
    try:
        return Path(cwd).resolve() == project_dir.resolve()
    except OSError:
        return False


def find_live_bot_pids(*, project_dir: Path = PROJECT_DIR) -> list[int]:
    """Return PIDs for live_bot processes owned by this project only."""
    lines: list[str] = []
    for cmd in (
        ["pgrep", "-fl", BOT_SCRIPT_NAME],
        ["ps", "aux"],
    ):
        try:
            result = _run(cmd)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode not in (0, 1):
            continue
        for line in (result.stdout or "").splitlines():
            if BOT_SCRIPT_NAME not in line:
                continue
            lines.append(line.strip())
        if lines and cmd[0] == "pgrep":
            break

    pids: list[int] = []
    for line in lines:
        parts = line.split(None, 1)
        pid: int | None = None
        cmd_text: str | None = None
        if parts and parts[0].isdigit():
            pid = int(parts[0])
            cmd_text = parts[1] if len(parts) > 1 else read_cmdline(pid)
        else:
            # ps aux: USER PID ... COMMAND
            tokens = line.split(None, 10)
            if len(tokens) >= 11 and tokens[1].isdigit():
                pid = int(tokens[1])
                cmd_text = tokens[10]
            elif len(tokens) >= 2 and tokens[1].isdigit():
                pid = int(tokens[1])
                cmd_text = read_cmdline(pid)
        if pid is None:
            continue
        cmd = cmd_text or read_cmdline(pid)
        if not cmdline_matches_live_bot(cmd, project_dir=project_dir):
            continue
        if not project_match_for_cmdline(cmd, project_dir=project_dir, pid=pid):
            continue
        if pid_exists(pid) and not is_zombie(pid):
            pids.append(pid)
    seen: set[int] = set()
    out: list[int] = []
    for pid in pids:
        if pid not in seen:
            seen.add(pid)
            out.append(pid)
    return out


def identity_for_pid(pid: int | None, *, source: str, project_dir: Path = PROJECT_DIR) -> BotProcessIdentity:
    if pid is None:
        return BotProcessIdentity(
            pid=None,
            alive=False,
            cmdline=None,
            matches_live_bot=False,
            project_match=False,
            zombie=False,
            source=source,
        )
    alive = pid_exists(pid)
    cmdline = read_cmdline(pid) if alive else None
    zombie = is_zombie(pid) if alive else False
    matches = cmdline_matches_live_bot(cmdline, project_dir=project_dir)
    project_match = project_match_for_cmdline(
        cmdline, project_dir=project_dir, pid=pid if alive else None
    )
    return BotProcessIdentity(
        pid=pid,
        alive=alive,
        cmdline=cmdline,
        matches_live_bot=matches,
        project_match=project_match,
        zombie=zombie,
        source=source,
    )


def read_pid_file(path: Path = PID_FILE) -> int | None:
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8").strip()
        return int(text) if text else None
    except (OSError, ValueError):
        return None


def write_pid_file(pid: int, *, path: Path = PID_FILE, status_path: Path = STATUS_FILE) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(str(pid), encoding="utf-8")
    tmp.replace(path)
    status_path.write_text("RUNNING", encoding="utf-8")


def clear_pid_file(*, path: Path = PID_FILE, status_path: Path = STATUS_FILE) -> None:
    try:
        if path.is_file():
            path.unlink()
    except OSError:
        pass
    status_path.write_text("STOPPED", encoding="utf-8")


def resolve_canonical_bot(*, project_dir: Path = PROJECT_DIR) -> tuple[BotProcessIdentity, list[int]]:
    """Return (canonical identity, duplicate pids to terminate).

    RUNNING rule:
      PID exists AND process alive AND cmdline is live_bot.py AND project-owned.

    A stale ``bot_pid.txt`` must never hide a real discovered live_bot process.
    A reused PID with the wrong command line must never be accepted.
    """
    pid_path = project_dir / "bot_pid.txt"
    file_pid = read_pid_file(pid_path)
    file_id = identity_for_pid(file_pid, source="pid_file", project_dir=project_dir)
    discovered = find_live_bot_pids(project_dir=project_dir)

    if file_id.valid:
        duplicates = [p for p in discovered if p != file_id.pid]
        return file_id, duplicates

    # Real process wins over stale/invalid pid file.
    if discovered:
        preferred = discovered[0]
        if file_pid in discovered:
            preferred = file_pid
        canonical = identity_for_pid(preferred, source="discovered", project_dir=project_dir)
        duplicates = [p for p in discovered if p != preferred]
        return canonical, duplicates

    if file_pid is not None:
        return identity_for_pid(file_pid, source="stale_pid_file", project_dir=project_dir), []

    return identity_for_pid(None, source="absent", project_dir=project_dir), []


def reconcile_bot_identity_metadata(*, project_dir: Path = PROJECT_DIR) -> dict[str, Any]:
    """Refresh bot_pid.txt / bot_status.txt from the canonical live process.

    Safe ops metadata only — never starts or stops live_bot.
    """
    identity, duplicates = resolve_canonical_bot(project_dir=project_dir)
    pid_path = project_dir / "bot_pid.txt"
    status_path = project_dir / "bot_status.txt"
    if identity.valid and identity.pid is not None:
        write_pid_file(identity.pid, path=pid_path, status_path=status_path)
        return {
            "reconciled": True,
            "status": "RUNNING",
            "pid": identity.pid,
            "source": identity.source,
            "duplicates": duplicates,
            "valid": True,
        }
    if duplicates:
        return {
            "reconciled": False,
            "status": "DUPLICATE",
            "pid": identity.pid,
            "source": identity.source,
            "duplicates": duplicates,
            "valid": False,
        }
    # Dead/stale file — clear so health does not keep a false RUNNING stamp.
    if (pid_path.is_file() or (status_path.is_file() and status_path.read_text(encoding="utf-8").strip() == "RUNNING")) and not identity.valid:
        clear_pid_file(path=pid_path, status_path=status_path)
        return {
            "reconciled": True,
            "status": "NOT_RUNNING",
            "pid": None,
            "source": identity.source,
            "duplicates": [],
            "valid": False,
            "cleared_stale": True,
        }
    return {
        "reconciled": False,
        "status": "NOT_RUNNING",
        "pid": identity.pid,
        "source": identity.source,
        "duplicates": [],
        "valid": False,
    }


def terminate_pid(pid: int, *, sig: int = signal.SIGTERM) -> bool:
    """Terminate one PID only — caller must pre-validate identity."""
    try:
        os.kill(pid, sig)
        return True
    except OSError:
        return False


def dedupe_live_bots(*, project_dir: Path = PROJECT_DIR, preserve: int | None = None) -> dict[str, Any]:
    canonical, duplicates = resolve_canonical_bot(project_dir=project_dir)
    keep = preserve if preserve is not None else canonical.pid
    terminated: list[int] = []
    skipped: list[int] = []
    for pid in list(duplicates):
        if keep is not None and pid == keep:
            continue
        ident = identity_for_pid(pid, source="dedupe", project_dir=project_dir)
        if not ident.valid:
            skipped.append(pid)
            continue
        if terminate_pid(pid):
            terminated.append(pid)
        else:
            skipped.append(pid)
    # Re-resolve after terminations
    canonical, remaining = resolve_canonical_bot(project_dir=project_dir)
    if canonical.valid and canonical.pid is not None:
        write_pid_file(
            canonical.pid,
            path=project_dir / "bot_pid.txt",
            status_path=project_dir / "bot_status.txt",
        )
    elif not canonical.valid:
        clear_pid_file(
            path=project_dir / "bot_pid.txt",
            status_path=project_dir / "bot_status.txt",
        )
    return {
        "kept": keep if keep is not None else canonical.pid,
        "terminated": terminated,
        "skipped": skipped,
        "remaining_duplicates": remaining,
        "canonical_valid": canonical.valid,
        "canonical_pid": canonical.pid,
    }


def load_recovery_state(path: Path | None = None) -> dict[str, Any]:
    path = RECOVERY_STATE_FILE if path is None else path
    if not path.is_file():
        return {"attempts": [], "successes": [], "failure_count": 0, "state": "UNKNOWN"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"attempts": [], "successes": [], "failure_count": 0, "state": "UNKNOWN"}


def save_recovery_state(data: dict[str, Any], path: Path | None = None) -> None:
    path = RECOVERY_STATE_FILE if path is None else path
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def recovery_allowed(now: float | None = None, *, path: Path | None = None) -> tuple[bool, str]:
    now = time.time() if now is None else now
    state = load_recovery_state(path)
    attempts = [float(x) for x in (state.get("attempts") or [])]
    recent = [t for t in attempts if now - t <= FAILURE_WINDOW_SEC]
    if recent and (now - max(recent)) < RESTART_COOLDOWN_SEC:
        return False, f"cooldown {RESTART_COOLDOWN_SEC}s"
    if len(recent) >= MAX_FAILURES_WINDOW:
        return False, "CRASH_LOOP"
    return True, "ok"


def record_recovery_attempt(
    *, success: bool, detail: str = "", path: Path | None = None
) -> dict[str, Any]:
    now = time.time()
    state = load_recovery_state(path)
    attempts = [float(t) for t in (state.get("attempts") or [])]
    attempts.append(now)
    attempts = [t for t in attempts if now - t <= FAILURE_WINDOW_SEC * 2][-20:]
    state["attempts"] = attempts
    state["last_attempt_at"] = datetime.now(timezone.utc).isoformat()
    state["last_attempt_detail"] = detail
    if success:
        successes = [float(t) for t in (state.get("successes") or [])]
        successes.append(now)
        state["successes"] = successes[-20:]
        state["failure_count"] = 0
        state["last_success_at"] = datetime.now(timezone.utc).isoformat()
        state["state"] = "RUNNING_HEALTHY"
    else:
        state["failure_count"] = int(state.get("failure_count") or 0) + 1
        recent = [t for t in attempts if now - t <= FAILURE_WINDOW_SEC]
        state["state"] = "CRASH_LOOP" if len(recent) >= MAX_FAILURES_WINDOW else "RESTARTING"
    save_recovery_state(state, path)
    return state


def classify_operational_state(
    *,
    markets_open: bool,
    identity: BotProcessIdentity,
    heartbeat_age_sec: float | None,
    recovery_state: dict[str, Any] | None = None,
) -> str:
    """Canonical ops-state SSOT for health / advisory / final-check / session guard.

    A living validated process is never RUNNING_STALE solely due to quiet logs.
    RUNNING_STALE is reserved for identity ambiguity (invalid/missing process) while
    markets are open — recovered via KeepAlive / kickstart, not BUY-block spam.
    """
    recovery_state = recovery_state or load_recovery_state()
    if recovery_state.get("state") == "CRASH_LOOP":
        return "CRASH_LOOP"
    if identity.valid:
        if markets_open:
            return "RUNNING_HEALTHY"
        return "RUNNING_IDLE_SESSION_POLICY"
    if markets_open:
        return "DOWN_UNEXPECTED"
    return "DOWN_MARKET_CLOSED"


def wait_verified(
    pid: int, *, window_sec: float = VERIFY_WINDOW_SEC, project_dir: Path = PROJECT_DIR
) -> BotProcessIdentity:
    deadline = time.time() + window_sec
    last = identity_for_pid(pid, source="verify", project_dir=project_dir)
    while time.time() < deadline:
        time.sleep(0.25)
        last = identity_for_pid(pid, source="verify", project_dir=project_dir)
        if last.valid:
            return last
    return last


def identity_to_dict(identity: BotProcessIdentity) -> dict[str, Any]:
    return asdict(identity)
