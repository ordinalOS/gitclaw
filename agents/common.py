#!/usr/bin/env python3
"""Common utilities for GitClaw agents."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

STATE_FILE = Path("memory/state.json")


def load_state() -> Dict[str, Any]:
    """Load agent state from memory/state.json.
    
    Returns empty default state if file is missing or corrupted.
    """
    default_state = {
        "xp": 0,
        "level": "Novice",
        "stats": {},
        "last_action": None,
        "achievements": [],
        "personality_traits": {},
    }
    
    if not STATE_FILE.exists():
        print(f"⚠️  State file not found, using defaults", file=sys.stderr)
        return default_state
    
    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
            # Ensure required keys exist
            for key in default_state:
                if key not in state:
                    state[key] = default_state[key]
            return state
    except json.JSONDecodeError as e:
        print(f"⚠️  State file corrupted ({e}), using defaults", file=sys.stderr)
        return default_state
    except Exception as e:
        print(f"⚠️  Error loading state ({e}), using defaults", file=sys.stderr)
        return default_state


def save_state(state: Dict[str, Any]) -> None:
    """Save agent state to memory/state.json."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def award_xp(amount: int, reason: str) -> Dict[str, Any]:
    """Award XP and check for level up.
    
    Returns updated state with new XP and level.
    """
    state = load_state()
    old_xp = state.get("xp", 0)
    old_level = state.get("level", "Novice")
    
    state["xp"] = old_xp + amount
    state["last_action"] = {
        "timestamp": datetime.utcnow().isoformat(),
        "reason": reason,
        "xp_gained": amount,
    }
    
    # Level thresholds
    levels = [
        (0, "Novice"),
        (100, "Apprentice"),
        (300, "Journeyman"),
        (600, "Expert"),
        (1000, "Master"),
        (1500, "Grandmaster"),
        (2500, "Legend"),
    ]
    
    for threshold, level_name in reversed(levels):
        if state["xp"] >= threshold:
            state["level"] = level_name
            break
    
    # Check for level up
    if state["level"] != old_level:
        achievement = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": "level_up",
            "from_level": old_level,
            "to_level": state["level"],
            "xp": state["xp"],
        }
        if "achievements" not in state:
            state["achievements"] = []
        state["achievements"].append(achievement)
    
    save_state(state)
    return state


def increment_stat(stat_name: str, amount: int = 1) -> None:
    """Increment a stat counter."""
    state = load_state()
    if "stats" not in state:
        state["stats"] = {}
    state["stats"][stat_name] = state["stats"].get(stat_name, 0) + amount
    save_state(state)


def get_stat(stat_name: str) -> int:
    """Get current value of a stat."""
    state = load_state()
    return state.get("stats", {}).get(stat_name, 0)


def get_personality_trait(trait_name: str) -> Optional[Any]:
    """Get a personality trait value."""
    state = load_state()
    return state.get("personality_traits", {}).get(trait_name)


def set_personality_trait(trait_name: str, value: Any) -> None:
    """Set a personality trait value."""
    state = load_state()
    if "personality_traits" not in state:
        state["personality_traits"] = {}
    state["personality_traits"][trait_name] = value
    save_state(state)


def load_config(config_name: str) -> Dict[str, Any]:
    """Load a config file from config/ directory.
    
    Args:
        config_name: Name of config file (e.g., 'agents', 'settings')
        
    Returns:
        Parsed YAML config as dict, or empty dict if not found
    """
    config_path = Path(f"config/{config_name}.yml")
    if not config_path.exists():
        return {}
    
    try:
        import yaml
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        # Fallback: basic YAML parsing without PyYAML
        with open(config_path) as f:
            content = f.read()
            result = {}
            for line in content.split("\n"):
                line = line.strip()
                if line and not line.startswith("#") and ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip()
                    value = value.strip()
                    # Basic type conversion
                    if value.lower() in ("true", "yes"):
                        value = True
                    elif value.lower() in ("false", "no"):
                        value = False
                    elif value.isdigit():
                        value = int(value)
                    result[key] = value
            return result


def get_github_context() -> Dict[str, str]:
    """Extract GitHub Actions context from environment."""
    return {
        "repository": os.getenv("GITHUB_REPOSITORY", ""),
        "ref": os.getenv("GITHUB_REF", ""),
        "sha": os.getenv("GITHUB_SHA", ""),
        "actor": os.getenv("GITHUB_ACTOR", ""),
        "workflow": os.getenv("GITHUB_WORKFLOW", ""),
        "run_id": os.getenv("GITHUB_RUN_ID", ""),
        "run_number": os.getenv("GITHUB_RUN_NUMBER", ""),
    }


def format_github_issue(title: str, body: str, labels: list[str] = None) -> str:
    """Format an issue for GitHub API.
    
    Returns JSON string ready for gh issue create.
    """
    issue = {
        "title": title,
        "body": body,
    }
    if labels:
        issue["labels"] = labels
    return json.dumps(issue)


def parse_github_issue(issue_json: str) -> Dict[str, Any]:
    """Parse GitHub issue JSON."""
    return json.loads(issue_json)


def format_timestamp(dt: Optional[datetime] = None) -> str:
    """Format timestamp in ISO format."""
    if dt is None:
        dt = datetime.utcnow()
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def load_memory(memory_name: str) -> Optional[Dict[str, Any]]:
    """Load a memory file from memory/ directory.
    
    Args:
        memory_name: Name of memory file (e.g., 'dreams', 'quests')
        
    Returns:
        Parsed JSON content or None if not found
    """
    memory_path = Path(f"memory/{memory_name}.json")
    if not memory_path.exists():
        return None
    
    try:
        with open(memory_path) as f:
            return json.load(f)
    except json.JSONDecodeError:
        return None


def save_memory(memory_name: str, data: Dict[str, Any]) -> None:
    """Save data to a memory file.
    
    Args:
        memory_name: Name of memory file (e.g., 'dreams', 'quests')
        data: Data to save as JSON
    """
    memory_path = Path(f"memory/{memory_name}.json")
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    with open(memory_path, "w") as f:
        json.dump(data, f, indent=2)
