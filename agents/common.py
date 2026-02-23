#!/usr/bin/env python3
"""Common utilities for GitClaw agents."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path


def load_state():
    """Load agent state from memory/state.json.
    
    Returns empty state structure if file is missing or malformed.
    """
    state_file = Path("memory/state.json")
    
    default_state = {
        "xp": 0,
        "level": "Newbie",
        "stats": {},
        "achievements": [],
        "last_action": None
    }
    
    try:
        if not state_file.exists():
            print(f"⚠️  State file not found, initializing empty state", file=sys.stderr)
            return default_state
            
        with open(state_file) as f:
            state = json.load(f)
            # Ensure required keys exist
            for key in default_state:
                if key not in state:
                    state[key] = default_state[key]
            return state
    except json.JSONDecodeError as e:
        print(f"⚠️  Malformed state file: {e}, using empty state", file=sys.stderr)
        return default_state
    except Exception as e:
        print(f"⚠️  Error loading state: {e}, using empty state", file=sys.stderr)
        return default_state


def save_state(state):
    """Save agent state to memory/state.json."""
    state_file = Path("memory/state.json")
    state_file.parent.mkdir(exist_ok=True)
    
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)


def add_xp(amount, reason):
    """Award XP and check for level-ups."""
    state = load_state()
    state["xp"] = state.get("xp", 0) + amount
    
    # Level thresholds
    levels = [
        (0, "Newbie"),
        (100, "Beginner"),
        (300, "Intermediate"),
        (600, "Advanced"),
        (1000, "Expert"),
        (1500, "Master"),
        (2500, "Legend")
    ]
    
    old_level = state.get("level", "Newbie")
    for threshold, level in reversed(levels):
        if state["xp"] >= threshold:
            state["level"] = level
            break
    
    state["last_action"] = {
        "timestamp": datetime.utcnow().isoformat(),
        "xp_gained": amount,
        "reason": reason
    }
    
    save_state(state)
    
    if state["level"] != old_level:
        print(f"🎉 Level up! {old_level} → {state['level']}")
    print(f"✨ +{amount} XP: {reason} (Total: {state['xp']} XP)")


def increment_stat(stat_name, amount=1):
    """Increment a stat counter."""
    state = load_state()
    if "stats" not in state:
        state["stats"] = {}
    state["stats"][stat_name] = state["stats"].get(stat_name, 0) + amount
    save_state(state)


def unlock_achievement(achievement_id, name, description):
    """Unlock an achievement."""
    state = load_state()
    if "achievements" not in state:
        state["achievements"] = []
    
    # Check if already unlocked
    if any(a["id"] == achievement_id for a in state["achievements"]):
        return
    
    achievement = {
        "id": achievement_id,
        "name": name,
        "description": description,
        "unlocked_at": datetime.utcnow().isoformat()
    }
    
    state["achievements"].append(achievement)
    save_state(state)
    print(f"🏆 Achievement unlocked: {name}")
    print(f"   {description}")


def get_stat(stat_name):
    """Get current value of a stat."""
    state = load_state()
    return state.get("stats", {}).get(stat_name, 0)


def format_timestamp(iso_string):
    """Format ISO timestamp for display."""
    try:
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except:
        return iso_string


def load_config(config_path):
    """Load YAML config file (requires PyYAML in environment)."""
    import yaml
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_repo_root():
    """Get repository root directory."""
    return Path(os.environ.get("GITHUB_WORKSPACE", "."))


def get_memory_dir():
    """Get memory directory path."""
    return get_repo_root() / "memory"


def ensure_memory_dir():
    """Ensure memory directory exists."""
    memory_dir = get_memory_dir()
    memory_dir.mkdir(exist_ok=True)
    return memory_dir


def read_file(path):
    """Read file contents safely."""
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        return None


def write_file(path, content):
    """Write file contents safely."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def append_file(path, content):
    """Append to file safely."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(content)


def list_files(directory, pattern="*"):
    """List files in directory matching pattern."""
    return list(Path(directory).glob(pattern))


def get_github_token():
    """Get GitHub token from environment."""
    return os.environ.get("GITHUB_TOKEN")


def get_repo_name():
    """Get repository name from environment."""
    return os.environ.get("GITHUB_REPOSITORY")


def is_ci():
    """Check if running in CI environment."""
    return os.environ.get("CI") == "true"
