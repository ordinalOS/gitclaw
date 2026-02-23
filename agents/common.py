#!/usr/bin/env python3
"""Common utilities for GitClaw agents."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# ── Constants ────────────────────────────────────────────────────────────────

STATE_SCHEMA_VERSION = "1.0.0"

DEFAULT_STATE = {
    "schema_version": STATE_SCHEMA_VERSION,
    "initialized_at": None,  # Set at creation time
    "agents": {},
    "last_architect_run": None,
    "proposals": {},
    "council_reviews": {},
}

# ── Path Resolution ──────────────────────────────────────────────────────────

def get_repo_root() -> Path:
    """Get repository root via git."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(result.stdout.strip())

REPO_ROOT = get_repo_root()
STATE_FILE = REPO_ROOT / "memory" / "state.json"
MEMORY_DIR = REPO_ROOT / "memory"

# ── State File Management ────────────────────────────────────────────────────

def compute_state_checksum(state: dict) -> str:
    """Compute SHA-256 checksum of state dict for corruption detection."""
    canonical = json.dumps(state, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode()).hexdigest()

def ensure_state_file() -> None:
    """Create state.json atomically if it doesn't exist.
    
    This runs at module import time to guarantee the file exists before
    any agent tries to load it. Uses atomic write to prevent corruption.
    """
    if STATE_FILE.exists():
        return
    
    # Ensure memory directory exists
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create default state with timestamp
    state = DEFAULT_STATE.copy()
    state["initialized_at"] = datetime.now(timezone.utc).isoformat()
    
    # Compute checksum for future verification
    checksum = compute_state_checksum(state)
    state["_checksum"] = checksum
    
    # Atomic write: write to temp file, then rename
    temp_fd, temp_path = tempfile.mkstemp(
        dir=MEMORY_DIR,
        prefix=".state-",
        suffix=".json.tmp",
    )
    try:
        with os.fdopen(temp_fd, 'w') as f:
            json.dump(state, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        
        # Atomic rename
        os.replace(temp_path, STATE_FILE)
        
        # Structured logging for audit trail
        log_data = {
            "timestamp": state["initialized_at"],
            "action": "state_initialized",
            "path": str(STATE_FILE),
            "schema_version": STATE_SCHEMA_VERSION,
            "checksum": checksum[:16],  # First 16 chars for log brevity
        }
        print(f"[STATE_INIT] {json.dumps(log_data)}", file=sys.stderr)
    except Exception:
        # Clean up temp file on failure
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise

def load_state() -> dict:
    """Load state from file with corruption detection.
    
    Raises:
        RuntimeError: If state file is corrupted or invalid
    """
    with open(STATE_FILE, 'r') as f:
        state = json.load(f)
    
    # Verify schema version
    if state.get("schema_version") != STATE_SCHEMA_VERSION:
        raise RuntimeError(
            f"State schema version mismatch: "
            f"expected {STATE_SCHEMA_VERSION}, "
            f"got {state.get('schema_version')}"
        )
    
    # Verify checksum if present
    stored_checksum = state.pop("_checksum", None)
    if stored_checksum:
        actual_checksum = compute_state_checksum(state)
        if actual_checksum != stored_checksum:
            raise RuntimeError(
                f"State file corruption detected: "
                f"checksum mismatch at {STATE_FILE}"
            )
    
    return state

def save_state(state: dict) -> None:
    """Save state to file atomically with checksum."""
    state = state.copy()
    state["schema_version"] = STATE_SCHEMA_VERSION
    
    # Compute and store checksum
    checksum = compute_state_checksum(state)
    state["_checksum"] = checksum
    
    # Atomic write
    temp_fd, temp_path = tempfile.mkstemp(
        dir=MEMORY_DIR,
        prefix=".state-",
        suffix=".json.tmp",
    )
    try:
        with os.fdopen(temp_fd, 'w') as f:
            json.dump(state, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, STATE_FILE)
    except Exception:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise

# Initialize state file at import time
ensure_state_file()

# ── Logging ──────────────────────────────────────────────────────────────────

def log(component: str, message: str) -> None:
    """Log structured message to stderr."""
    timestamp = datetime.now(timezone.utc).isoformat()
    log_entry = {
        "timestamp": timestamp,
        "component": component,
        "message": message,
    }
    print(json.dumps(log_entry), file=sys.stderr)
