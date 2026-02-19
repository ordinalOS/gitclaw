#!/usr/bin/env python3
"""Common utilities for GitClaw agents."""

import hashlib
import json
import os
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(subprocess.check_output(
    ["git", "rev-parse", "--show-toplevel"], text=True
).strip())

STATE_FILE = REPO_ROOT / "memory" / "state.json"
STATE_CHECKSUM_FILE = REPO_ROOT / "memory" / "state.json.sha256"
STATE_BACKUP_DIR = REPO_ROOT / "memory" / ".state-backups"
STATE_RECOVERY_LOG = REPO_ROOT / "memory" / "state-recovery.log"
CONFIG_DIR = REPO_ROOT / "config"
PROMPTS_DIR = REPO_ROOT / "templates" / "prompts"
MEMORY_DIR = REPO_ROOT / "memory"

# Ensure backup directory exists
STATE_BACKUP_DIR.mkdir(parents=True, exist_ok=True)


# ── State Integrity ──────────────────────────────────────────────────────────

def _compute_checksum(data: bytes) -> str:
    """Compute SHA-256 checksum of data."""
    return hashlib.sha256(data).hexdigest()


def _verify_state_integrity() -> bool:
    """Verify state.json matches its checksum. Returns False if corrupted or missing."""
    if not STATE_FILE.exists():
        return False
    if not STATE_CHECKSUM_FILE.exists():
        return False
    
    try:
        state_bytes = STATE_FILE.read_bytes()
        expected_checksum = STATE_CHECKSUM_FILE.read_text().strip()
        actual_checksum = _compute_checksum(state_bytes)
        return actual_checksum == expected_checksum
    except (OSError, IOError):
        return False


def _create_state_backup() -> None:
    """Create timestamped backup of current state file."""
    if not STATE_FILE.exists():
        return
    
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_path = STATE_BACKUP_DIR / f"state-{timestamp}.json"
    backup_checksum_path = STATE_BACKUP_DIR / f"state-{timestamp}.json.sha256"
    
    try:
        # Copy state and checksum
        STATE_FILE.replace(backup_path)
        if STATE_CHECKSUM_FILE.exists():
            STATE_CHECKSUM_FILE.replace(backup_checksum_path)
        
        # Keep only last 3 backups
        backups = sorted(STATE_BACKUP_DIR.glob("state-*.json"))
        for old_backup in backups[:-3]:
            old_backup.unlink(missing_ok=True)
            old_backup.with_suffix(".json.sha256").unlink(missing_ok=True)
    except (OSError, IOError) as exc:
        _log_recovery_event("backup_failed", {"error": str(exc)})


def _log_recovery_event(event_type: str, details: dict) -> None:
    """Log state recovery event to structured log file."""
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event_type,
        "details": details,
    }
    try:
        with STATE_RECOVERY_LOG.open("a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except (OSError, IOError):
        # If we can't log recovery events, print to stderr as fallback
        print(json.dumps(log_entry), file=sys.stderr)


# ── State Management ─────────────────────────────────────────────────────────

def load_state() -> dict:
    """Load agent state with integrity verification.
    
    Returns state dict on success.
    Raises RuntimeError if state is corrupted and recovery is not allowed.
    
    Recovery mode requires GITCLAW_ALLOW_STATE_RECOVERY=1 environment variable.
    When enabled, corrupted state falls back to empty default and logs event.
    """
    # Check integrity first
    if STATE_FILE.exists() and _verify_state_integrity():
        try:
            state = json.loads(STATE_FILE.read_text())
            return state
        except (json.JSONDecodeError, OSError, IOError) as exc:
            # Checksum passed but JSON invalid — filesystem corruption
            _log_recovery_event("corruption_detected", {
                "error": str(exc),
                "checksum_valid": True,
            })
            # Fall through to recovery logic below
    
    # State missing or corrupted — check if recovery is allowed
    allow_recovery = os.environ.get("GITCLAW_ALLOW_STATE_RECOVERY", "0") == "1"
    
    if not allow_recovery:
        # Fail loudly by default — operator must acknowledge state issues
        error_msg = (
            "State file missing or corrupted. Set GITCLAW_ALLOW_STATE_RECOVERY=1 "
            "to allow automatic recovery with empty state."
        )
        _log_recovery_event("recovery_blocked", {"reason": "env_var_not_set"})
        raise RuntimeError(error_msg)
    
    # Recovery allowed — attempt to restore from backup
    backups = sorted(STATE_BACKUP_DIR.glob("state-*.json"), reverse=True)
    for backup in backups[:3]:  # Try last 3 backups
        checksum_file = backup.with_suffix(".json.sha256")
        if not checksum_file.exists():
            continue
        
        try:
            backup_bytes = backup.read_bytes()
            expected_checksum = checksum_file.read_text().strip()
            if _compute_checksum(backup_bytes) == expected_checksum:
                # Valid backup found — restore it
                state = json.loads(backup_bytes)
                _log_recovery_event("backup_restored", {"backup": backup.name})
                save_state(state)  # Write restored state atomically
                return state
        except (json.JSONDecodeError, OSError, IOError):
            continue
    
    # No valid backups — initialize empty state with recovery counter
    _log_recovery_event("empty_state_initialized", {"reason": "no_valid_backups"})
    default_state = {
        "_recovery_count": 1,
        "_last_recovery": datetime.now(timezone.utc).isoformat(),
    }
    save_state(default_state)
    return default_state


def save_state(state: dict) -> None:
    """Save agent state with atomic write and checksum.
    
    Uses write-to-temp-then-rename pattern to prevent corruption.
    Creates backup of previous state before overwriting.
    """
    # Create backup of current state if it exists
    if STATE_FILE.exists():
        _create_state_backup()
    
    # Atomic write: write to temp file, then rename
    temp_file = STATE_FILE.with_suffix(".tmp")
    temp_checksum = STATE_CHECKSUM_FILE.with_suffix(".tmp")
    
    try:
        state_bytes = json.dumps(state, indent=2).encode("utf-8")
        checksum = _compute_checksum(state_bytes)
        
        # Write both files
        temp_file.write_bytes(state_bytes)
        temp_checksum.write_text(checksum)
        
        # Atomic rename (POSIX guarantees atomicity)
        temp_file.replace(STATE_FILE)
        temp_checksum.replace(STATE_CHECKSUM_FILE)
    except (OSError, IOError) as exc:
        # Clean up temp files on failure
        temp_file.unlink(missing_ok=True)
        temp_checksum.unlink(missing_ok=True)
        raise RuntimeError(f"Failed to save state: {exc}") from exc


# ── Logging ──────────────────────────────────────────────────────────────────

def log(component: str, message: str) -> None:
    """Log a message with timestamp and component prefix."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{component}] {message}", file=sys.stderr)
