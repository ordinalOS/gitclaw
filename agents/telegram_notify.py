#!/usr/bin/env python3
"""
Telegram Notify — Sends alerts and daily digests to Telegram.
Uses the Telegram Bot API via urllib (stdlib only, no pip).

Modes:
    Event alert:  TELEGRAM_EVENT env var set → format and send alert
    Daily digest: No event → scan today's memory and send summary
"""

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from common import (
    MEMORY_DIR, REPO_ROOT, load_state, log, today, update_stats, award_xp,
)

# ── Telegram API ──────────────────────────────────────────────────────────────

def send_telegram(message: str, parse_mode: str = "Markdown") -> bool:
    """Send a message via Telegram Bot API. Returns True on success."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        log("Telegram", "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": message,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            if result.get("ok"):
                log("Telegram", "Message sent successfully")
                return True
            log("Telegram", f"API returned ok=false: {result}")
            return False
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        log("Telegram", f"Failed to send message: {exc}")
        return False


# ── Event Alerts ──────────────────────────────────────────────────────────────

EVENT_TEMPLATES = {
    "council_verdict": (
        "⚖️ *Council Verdict — PR #{pr}*\n\n"
        "The Council of 7 has spoken:\n"
        "*{verdict}*"
    ),
    "architect_pr": (
        "🏗️ *New Architect Proposal*\n\n"
        "PR #{pr} created for council review."
    ),
    "architect_revision": (
        "🏗️ *Architect Revision*\n\n"
        "PR #{pr} revised based on council feedback."
    ),
    "pr_merged": (
        "✅ *PR #{pr} Merged*\n\n"
        "The change has been merged into main."
    ),
    "pr_closed": (
        "❌ *PR #{pr} Closed*\n\n"
        "The proposal was rejected by the council."
    ),
    "error": (
        "🚨 *GitClaw Error*\n\n"
        "{message}"
    ),
}


def format_event_alert(event: dict) -> str:
    """Format an event dict into a Telegram notification message."""
    event_type = event.get("type", "unknown")
    template = EVENT_TEMPLATES.get(event_type)

    if template:
        try:
            return template.format(**event)
        except KeyError:
            return f"🦞 *GitClaw Event*\n\n`{event_type}`: {json.dumps(event)}"

    return f"🦞 *GitClaw Event*\n\n`{event_type}`: {json.dumps(event)}"


# ── Daily Digest ──────────────────────────────────────────────────────────────

MEMORY_CATEGORIES = [
    ("dreams", "🌙 Dreams"),
    ("lore", "📜 Lore"),
    ("research", "🔍 Research"),
    ("roasts", "🔥 Roasts"),
    ("fortunes", "🔮 Fortunes"),
    ("hn", "📰 HN"),
    ("news", "🥷 News"),
    ("crypto", "💰 Crypto"),
    ("stocks", "📈 Stocks"),
    ("proposals", "🏗️ Proposals"),
    ("council", "⚖️ Council"),
]


def get_todays_files(category: str) -> list:
    """Find files in a memory category created today."""
    cat_dir = MEMORY_DIR / category
    if not cat_dir.is_dir():
        return []

    today_str = today()
    files = []
    for f in cat_dir.iterdir():
        if f.name.startswith(today_str) or f.name.startswith(today_str.replace("-", "")):
            files.append(f.name)
    return files


def format_daily_digest() -> str:
    """Build a daily activity digest from memory files and state."""
    state = load_state()
    xp = state.get("xp", 0)
    level = state.get("level", "Unknown")
    streak = state.get("streak", {}).get("current", 0)
    stats = state.get("stats", {})

    today_str = today()

    # Header
    lines = [
        f"🦞 *GitClaw Daily Digest*",
        f"_{today_str}_\n",
        f"*Level:* {level} | *XP:* {xp} | *Streak:* {streak}d\n",
    ]

    # Scan each memory category for today's activity
    activity_lines = []
    total_items = 0
    for cat_key, cat_label in MEMORY_CATEGORIES:
        files = get_todays_files(cat_key)
        if files:
            total_items += len(files)
            activity_lines.append(f"  {cat_label}: {len(files)}")

    if activity_lines:
        lines.append(f"*Today's Activity* ({total_items} items):")
        lines.extend(activity_lines)
    else:
        lines.append("_No activity recorded today._")

    # Stats summary (non-zero only)
    notable_stats = {k: v for k, v in stats.items() if v and v > 0}
    if notable_stats:
        lines.append("\n*Agent Stats:*")
        for key, val in list(notable_stats.items())[:8]:
            nice_key = key.replace("_", " ").title()
            lines.append(f"  {nice_key}: {val}")

    # Footer
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if repo:
        lines.append(f"\n[Dashboard](https://{repo.split('/')[0]}.github.io/{repo.split('/')[-1]}/)")

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    event_json = os.environ.get("TELEGRAM_EVENT", "")

    if event_json:
        # Event alert mode
        try:
            event = json.loads(event_json)
        except json.JSONDecodeError:
            log("Telegram", f"Invalid TELEGRAM_EVENT JSON: {event_json}")
            return

        message = format_event_alert(event)
        log("Telegram", f"Sending event alert: {event.get('type', 'unknown')}")
    else:
        # Daily digest mode
        message = format_daily_digest()
        log("Telegram", "Sending daily digest")

    success = send_telegram(message)

    if success:
        update_stats("telegram_messages_sent")
        award_xp(5)
    else:
        log("Telegram", "Message delivery failed")


if __name__ == "__main__":
    main()
