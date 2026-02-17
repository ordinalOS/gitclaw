"""
GitClaw Agent Commons
Shared utilities, LLM client, and state management for all agents.
The Python equivalent of scripts/utils.sh + scripts/llm.sh.
"""

import json
import os
import subprocess
import sys
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(subprocess.check_output(
    ["git", "rev-parse", "--show-toplevel"], text=True
).strip())

STATE_FILE = REPO_ROOT / "memory" / "state.json"
CONFIG_DIR = REPO_ROOT / "config"
PROMPTS_DIR = REPO_ROOT / "templates" / "prompts"
MEMORY_DIR = REPO_ROOT / "memory"


# ── LLM Client ──────────────────────────────────────────────────────────────

def call_llm(
    system_prompt: str,
    user_message: str,
    provider: str | None = None,
    model: str | None = None,
    max_tokens: int = 2048,
) -> str:
    """Call an LLM API and return the response text."""
    import urllib.request

    provider = provider or os.environ.get("GITCLAW_PROVIDER", "anthropic")
    model = model or os.environ.get("GITCLAW_MODEL", "claude-haiku-4-5-20251001")

    if provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")

        payload = json.dumps({
            "model": model,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_message}],
        }).encode()

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
                return data["content"][0]["text"]
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            log("LLM", f"Anthropic API error: {exc}")
            raise RuntimeError(f"LLM API call failed: {exc}") from exc

    elif provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")

        payload = json.dumps({
            "model": model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        }).encode()

        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
                return data["choices"][0]["message"]["content"]
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            log("LLM", f"OpenAI API error: {exc}")
            raise RuntimeError(f"LLM API call failed: {exc}") from exc

    raise ValueError(f"Unknown provider: {provider}")


# ── State Management ─────────────────────────────────────────────────────────

def load_state() -> dict:
    """Load agent state from memory/state.json."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: dict) -> None:
    """Save agent state to memory/state.json."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")


def update_stats(key: str, increment: int = 1) -> dict:
    """Increment a stat counter and return updated state."""
    state = load_state()
    stats = state.setdefault("stats", {})
    stats[key] = stats.get(key, 0) + increment
    save_state(state)
    return state


def award_xp(amount: int) -> dict:
    """Award XP and update level."""
    state = load_state()
    state["xp"] = state.get("xp", 0) + amount
    state["level"] = get_level(state["xp"])
    state["last_active"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    save_state(state)
    return state


# ── XP & Leveling ────────────────────────────────────────────────────────────

XP_LEVELS = [
    (0, "Unawakened"),
    (50, "Novice"),
    (150, "Apprentice"),
    (300, "Journeyman"),
    (500, "Adept"),
    (800, "Expert"),
    (1200, "Master"),
    (1800, "Grandmaster"),
    (2500, "Legend"),
    (5000, "Mythic"),
    (10000, "Transcendent"),
]


def get_level(xp: int) -> str:
    """Get level name for a given XP amount."""
    level = "Unawakened"
    for threshold, name in XP_LEVELS:
        if xp >= threshold:
            level = name
    return level


def xp_bar(xp: int) -> str:
    """Generate a visual XP progress bar."""
    current_threshold = 0
    next_threshold = 50

    for threshold, _ in XP_LEVELS:
        if threshold <= xp:
            current_threshold = threshold
        else:
            next_threshold = threshold
            break

    if next_threshold == current_threshold:
        return "██████████ MAX"

    progress = xp - current_threshold
    total = next_threshold - current_threshold
    filled = int((progress / total) * 10)

    bar = "█" * filled + "░" * (10 - filled)
    return f"{bar} {xp} XP"


# ── Memory Helpers ───────────────────────────────────────────────────────────

def append_memory(category: str, filename: str, content: str) -> Path:
    """Append content to a memory file with timestamp."""
    target_dir = MEMORY_DIR / category
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / filename

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    entry = f"\n---\n**[{timestamp}]**\n\n{content}\n"

    with open(target_file, "a") as f:
        f.write(entry)

    return target_file


def read_prompt(name: str) -> str:
    """Read a system prompt template."""
    prompt_file = PROMPTS_DIR / f"{name}.md"
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt not found: {prompt_file}")
    return prompt_file.read_text()


# ── GitHub API Helpers ───────────────────────────────────────────────────────

def gh_post_comment(issue_number: int, body: str) -> None:
    """Post a comment on an issue/PR via gh CLI."""
    subprocess.run(
        ["gh", "api",
         f"repos/{os.environ['GITHUB_REPOSITORY']}/issues/{issue_number}/comments",
         "-f", f"body={body}"],
        check=True, capture_output=True,
    )


def gh_add_labels(issue_number: int, labels: list[str]) -> None:
    """Add labels to an issue."""
    subprocess.run(
        ["gh", "issue", "edit", str(issue_number),
         "--add-label", ",".join(labels)],
        check=True, capture_output=True,
    )


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def log(agent: str, message: str) -> None:
    print(f"[🤖 {agent}] {message}", file=sys.stderr)
