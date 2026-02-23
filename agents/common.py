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
    "proposals": [],
    "last_architect_run": None,
    "checksum": None,  # Calculated at write time
}

# ── State Management ─────────────────────────────────────────────────────────

def get_repo_root() -> Path:
    """Get repository root path."""
    return Path(
        subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    )


def calculate_state_checksum(state: dict) -> str:
    """Calculate SHA256 checksum of state (excluding checksum field)."""
    state_copy = {k: v for k, v in state.items() if k != "checksum"}
    content = json.dumps(state_copy, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def initialize_state_file(state_path: Path) -> dict:
    """Create state.json with known-good schema if it doesn't exist."""
    if state_path.exists():
        return None  # Already exists, do nothing

    state_path.parent.mkdir(parents=True, exist_ok=True)
    
    state = DEFAULT_STATE.copy()
    state["initialized_at"] = datetime.now(timezone.utc).isoformat()
    state["checksum"] = calculate_state_checksum(state)
    
    # Atomic write: temp file + rename
    fd, tmp_path = tempfile.mkstemp(
        dir=state_path.parent,
        prefix=".state_",
        suffix=".json.tmp",
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f, indent=2)
            f.write("\n")
        os.chmod(tmp_path, 0o600)  # Restrict permissions
        os.rename(tmp_path, state_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
    
    log("STATE", f"Initialized state file: {state_path}")
    return state


def validate_state_schema(state: dict, state_path: Path) -> None:
    """Validate state structure matches expected schema."""
    required_fields = {"schema_version", "initialized_at", "agents", "proposals"}
    missing = required_fields - set(state.keys())
    
    if missing:
        raise ValueError(
            f"State file corrupted: missing required fields {missing}. "
            f"Path: {state_path}. Delete the file to reinitialize."
        )
    
    if state.get("schema_version") != STATE_SCHEMA_VERSION:
        log(
            "STATE",
            f"Warning: schema version mismatch. Expected {STATE_SCHEMA_VERSION}, "
            f"got {state.get('schema_version')}. Path: {state_path}",
        )


def verify_state_checksum(state: dict, state_path: Path) -> bool:
    """Verify state checksum to detect corruption."""
    if "checksum" not in state:
        log("STATE", f"Warning: no checksum in state file: {state_path}")
        return False
    
    stored = state["checksum"]
    calculated = calculate_state_checksum(state)
    
    if stored != calculated:
        log(
            "STATE",
            f"ERROR: State checksum mismatch (corruption detected). "
            f"Path: {state_path}. Expected {stored}, got {calculated}.",
        )
        return False
    
    return True


def load_state() -> dict:
    """Load agent state, initializing if necessary."""
    repo_root = get_repo_root()
    state_path = repo_root / "memory" / "state.json"
    
    # Ensure state file exists with known-good schema
    initialized = initialize_state_file(state_path)
    if initialized:
        return initialized
    
    # Load existing state
    try:
        with open(state_path, "r") as f:
            state = json.load(f)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"State file contains invalid JSON: {state_path}. "
            f"Error: {e}. Delete the file to reinitialize."
        ) from e
    except OSError as e:
        raise RuntimeError(
            f"Cannot read state file: {state_path}. "
            f"Error: {e}. Check file permissions."
        ) from e
    
    # Validate schema
    validate_state_schema(state, state_path)
    
    # Verify checksum
    if not verify_state_checksum(state, state_path):
        log(
            "STATE",
            f"Proceeding with potentially corrupted state. "
            f"Recommend manual verification: {state_path}",
        )
    
    return state


def save_state(state: dict) -> None:
    """Save agent state atomically with checksum."""
    repo_root = get_repo_root()
    state_path = repo_root / "memory" / "state.json"
    
    # Update checksum
    state["checksum"] = calculate_state_checksum(state)
    
    # Atomic write
    fd, tmp_path = tempfile.mkstemp(
        dir=state_path.parent,
        prefix=".state_",
        suffix=".json.tmp",
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f, indent=2)
            f.write("\n")
        os.chmod(tmp_path, 0o600)
        os.rename(tmp_path, state_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


# ── Logging ──────────────────────────────────────────────────────────────────

def log(component: str, message: str) -> None:
    """Log a message with timestamp and component prefix."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sanitized_msg = message.replace(os.path.expanduser("~"), "~")
    print(f"[{timestamp}] [{component}] {sanitized_msg}", file=sys.stderr)
