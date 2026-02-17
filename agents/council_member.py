#!/usr/bin/env python3
"""
Council Member — one of the 7 reviewers on GitClaw's Council of 7.
Each member has a unique persona (Zuckerberg, Mr. Wonderful, Musk,
Toly, Satoshi, CIA, Cobain) that shapes their code review style.

Persona is selected via COUNCIL_PERSONA env var.
"""

import os
import sys
from datetime import datetime, timezone

from common import (
    MEMORY_DIR, award_xp, call_llm, log, read_prompt,
    save_state, load_state, today, update_stats,
)

PERSONAS = {
    "zuckerberg": {"name": "Mark Zuckerberg", "emoji": "👓"},
    "wonderful":  {"name": "Mr. Wonderful",   "emoji": "💰"},
    "musk":       {"name": "Elon Musk",        "emoji": "🚀"},
    "toly":       {"name": "Toly",             "emoji": "⚡"},
    "satoshi":    {"name": "Satoshi Nakamoto",  "emoji": "₿"},
    "cia":        {"name": "The CIA",          "emoji": "🕵️"},
    "cobain":     {"name": "Kurt Cobain",      "emoji": "🎸"},
}

FALLBACK_VOTES = {
    "zuckerberg": "Ship it. Move fast. VOTE: APPROVE",
    "wonderful":  "The numbers don't lie, but I can't see them right now. VOTE: REVISE",
    "musk":       "Delete everything and start over. Actually, VOTE: REVISE",
    "toly":       "Need more data on throughput. VOTE: REVISE",
    "satoshi":    "Insufficient information to verify. VOTE: REVISE",
    "cia":        "[REDACTED] — Unable to complete assessment. VOTE: REVISE",
    "cobain":     "Whatever. Come back when it means something. VOTE: REVISE",
}


def main():
    persona = os.environ.get("COUNCIL_PERSONA", "").lower().strip()
    pr_number = os.environ.get("PR_NUMBER", "0")
    pr_title = os.environ.get("PR_TITLE", "Untitled PR")
    pr_body = os.environ.get("PR_BODY", "")
    pr_diff = os.environ.get("PR_DIFF", "")

    if persona not in PERSONAS:
        log("Council", f"Unknown persona: '{persona}'. Valid: {list(PERSONAS.keys())}")
        sys.exit(1)

    info = PERSONAS[persona]
    log("Council", f"Summoning {info['emoji']} {info['name']} for PR #{pr_number}")

    # Load the persona-specific system prompt
    try:
        system_prompt = read_prompt(f"council-{persona}")
    except FileNotFoundError:
        log("Council", f"Prompt file not found: council-{persona}.md")
        sys.exit(1)

    # Truncate diff to avoid token blowout
    diff_truncated = pr_diff[:3000]
    if len(pr_diff) > 3000:
        diff_truncated += f"\n\n... [{len(pr_diff) - 3000} more characters truncated]"

    user_message = (
        f"## Pull Request #{pr_number}: {pr_title}\n\n"
        f"### Description\n{pr_body or '(No description provided)'}\n\n"
        f"### Diff\n```diff\n{diff_truncated}\n```\n\n"
        f"Review this PR as {info['name']}. "
        f"Deliver your council review now.\n\n"
        f"You MUST end your review with exactly one of these on its own line:\n"
        f"VOTE: APPROVE\n"
        f"VOTE: REJECT\n"
        f"VOTE: REVISE"
    )

    try:
        response = call_llm(system_prompt, user_message, max_tokens=1200)
    except Exception as e:
        log("Council", f"LLM failed for {persona}: {e}")
        response = (
            f"## {info['emoji']} {info['name']} — Council Review\n\n"
            f"*Council member encountered a temporal disturbance (API error).*\n\n"
            f"{FALLBACK_VOTES.get(persona, 'VOTE: REVISE')}"
        )

    # Ensure there's a vote line in the response
    has_vote = any(
        line.strip().startswith("VOTE:")
        for line in response.split("\n")
    )
    if not has_vote:
        response += "\n\nVOTE: REVISE"

    update_stats("council_reviews")
    award_xp(10)

    print(response)


if __name__ == "__main__":
    main()
