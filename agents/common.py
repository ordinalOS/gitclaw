#!/usr/bin/env python3
"""Common utilities for GitClaw agents."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# State file path
STATE_FILE = Path("memory/state.json")

# Default empty state structure
DEFAULT_STATE = {
    "agent_name": "Unknown",
    "xp": 0,
    "level": "Initiate",
    "stats": {
        "issues_triaged": 0,
        "prs_reviewed": 0,
        "researches_completed": 0,
        "quests_completed": 0,
        "lore_entries": 0,
        "dreams_interpreted": 0,
        "fortunes_dispensed": 0,
        "roasts_delivered": 0,
        "comments_posted": 0,
        "commits_made": 0,
        "solana_queries": 0,
        "solana_monitors": 0,
        "solana_builds": 0,
        "hn_scrapes": 0,
        "news_scrapes": 0,
        "crypto_analyses": 0,
        "stock_analyses": 0,
        "pages_built": 0,
        "council_reviews": 0,
    },
    "last_run": None,
    "memory": {},
}


def load_state():
    """Load agent state from memory/state.json.
    
    Returns default empty state if file doesn't exist or is corrupted.
    This ensures agents can initialize cleanly even on first run.
    """
    try:
        if not STATE_FILE.exists():
            print(f"⚠️  State file not found, initializing default state", file=sys.stderr)
            return DEFAULT_STATE.copy()
        
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
            # Ensure all required keys exist
            if "stats" not in state:
                state["stats"] = DEFAULT_STATE["stats"].copy()
            if "memory" not in state:
                state["memory"] = {}
            return state
    except json.JSONDecodeError as e:
        print(f"⚠️  Corrupted state file: {e}, using default state", file=sys.stderr)
        return DEFAULT_STATE.copy()
    except Exception as e:
        print(f"⚠️  Error loading state: {e}, using default state", file=sys.stderr)
        return DEFAULT_STATE.copy()


def save_state(state):
    """Save agent state to memory/state.json.
    
    Handles write failures gracefully by logging to stderr.
    """
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"⚠️  Error saving state: {e}", file=sys.stderr)
        # Don't raise — let the agent continue even if state save fails


def add_xp(amount, reason=""):
    """Award XP and handle level-ups."""
    state = load_state()
    state["xp"] = state.get("xp", 0) + amount

    # Level thresholds
    levels = [
        (0, "Initiate"),
        (100, "Apprentice"),
        (500, "Journeyman"),
        (1500, "Expert"),
        (3000, "Master"),
        (5000, "Grandmaster"),
        (10000, "Legend"),
    ]

    old_level = state.get("level", "Initiate")
    for threshold, level_name in reversed(levels):
        if state["xp"] >= threshold:
            state["level"] = level_name
            break

    if state["level"] != old_level:
        print(f"🎉 Level up! {old_level} → {state['level']}")

    if reason:
        print(f"✨ +{amount} XP: {reason}")

    save_state(state)
    return state


def increment_stat(stat_name, amount=1):
    """Increment a stat counter."""
    state = load_state()
    if "stats" not in state:
        state["stats"] = {}
    state["stats"][stat_name] = state["stats"].get(stat_name, 0) + amount
    save_state(state)
    return state


def get_stat(stat_name):
    """Get current value of a stat."""
    state = load_state()
    return state.get("stats", {}).get(stat_name, 0)


def store_memory(key, value):
    """Store a value in agent memory."""
    state = load_state()
    if "memory" not in state:
        state["memory"] = {}
    state["memory"][key] = value
    save_state(state)


def recall_memory(key, default=None):
    """Recall a value from agent memory."""
    state = load_state()
    return state.get("memory", {}).get(key, default)


def update_last_run():
    """Update last_run timestamp."""
    state = load_state()
    state["last_run"] = datetime.utcnow().isoformat() + "Z"
    save_state(state)


def get_personality():
    """Load personality config."""
    try:
        with open("config/personality.yml", "r") as f:
            import yaml

            return yaml.safe_load(f)
    except Exception as e:
        print(f"⚠️  Could not load personality: {e}", file=sys.stderr)
        return {"tone": "professional", "emoji": True}


def format_response(content, metadata=None):
    """Format agent response with standard structure."""
    response = {"content": content, "timestamp": datetime.utcnow().isoformat() + "Z"}

    if metadata:
        response["metadata"] = metadata

    return response


def log_error(error_message, context=None):
    """Log error to stderr with context."""
    timestamp = datetime.utcnow().isoformat() + "Z"
    print(f"❌ [{timestamp}] {error_message}", file=sys.stderr)
    if context:
        print(f"   Context: {json.dumps(context)}", file=sys.stderr)
