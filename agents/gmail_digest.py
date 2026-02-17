#!/usr/bin/env python3
"""
Gmail Digest — Sends a daily HTML email digest of GitClaw activity.
Uses smtplib + email.mime (stdlib only, no pip).

Connects to Gmail SMTP with an App Password — not a regular password.
Setup: https://support.google.com/accounts/answer/185833
"""

import json
import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from common import (
    MEMORY_DIR, REPO_ROOT, load_state, log, today, update_stats, award_xp,
)

# ── Email Sending ─────────────────────────────────────────────────────────────

def send_email(subject: str, html_body: str) -> bool:
    """Send an HTML email via Gmail SMTP. Returns True on success."""
    from_addr = os.environ.get("GMAIL_ADDRESS", "")
    password = os.environ.get("GMAIL_APP_PASSWORD", "")
    to_addr = os.environ.get("GMAIL_TO_ADDRESS", from_addr)

    if not from_addr or not password:
        log("Gmail", "GMAIL_ADDRESS or GMAIL_APP_PASSWORD not set")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"GitClaw <{from_addr}>"
    msg["To"] = to_addr

    # Plain text fallback
    plain_text = f"GitClaw Daily Digest — {today()}\nView the full report on your GitClaw dashboard."
    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(from_addr, password)
            server.sendmail(from_addr, [to_addr], msg.as_string())
            log("Gmail", f"Email sent to {to_addr}")
            return True
    except Exception as exc:
        log("Gmail", f"SMTP error: {exc}")
        return False


# ── Digest Builder ────────────────────────────────────────────────────────────

MEMORY_CATEGORIES = [
    ("dreams", "Dreams", "🌙"),
    ("lore", "Lore", "📜"),
    ("research", "Research", "🔍"),
    ("roasts", "Roasts", "🔥"),
    ("fortunes", "Fortunes", "🔮"),
    ("hn", "HN Digest", "📰"),
    ("news", "News", "🥷"),
    ("crypto", "Crypto", "💰"),
    ("stocks", "Stocks", "📈"),
    ("proposals", "Proposals", "🏗️"),
    ("council", "Council", "⚖️"),
]


def get_todays_files(category: str) -> list:
    """Find files in a memory category created today."""
    cat_dir = MEMORY_DIR / category
    if not cat_dir.is_dir():
        return []

    today_str = today()
    files = []
    for f in sorted(cat_dir.iterdir()):
        if f.name.startswith(today_str) or f.name.startswith(today_str.replace("-", "")):
            # Read first 200 chars for preview
            try:
                content = f.read_text()[:200].strip()
            except Exception:
                content = ""
            files.append({"name": f.name, "preview": content})
    return files


def build_digest_html() -> str:
    """Build an HTML email body from today's memory state."""
    state = load_state()
    xp = state.get("xp", 0)
    level = state.get("level", "Unknown")
    streak = state.get("streak", {}).get("current", 0)
    stats = state.get("stats", {})
    today_str = today()

    repo = os.environ.get("GITHUB_REPOSITORY", "")
    owner = repo.split("/")[0] if "/" in repo else ""
    repo_name = repo.split("/")[-1] if "/" in repo else ""
    dashboard_url = f"https://{owner}.github.io/{repo_name}/" if repo else "#"

    # Activity rows
    activity_rows = ""
    total_items = 0
    for cat_key, cat_label, cat_emoji in MEMORY_CATEGORIES:
        files = get_todays_files(cat_key)
        if files:
            total_items += len(files)
            previews = "".join(
                f'<div style="font-size:12px;color:#666;padding:2px 0;">'
                f'  {f["name"]}'
                f'</div>'
                for f in files[:3]
            )
            activity_rows += f"""
            <tr>
              <td style="padding:8px 12px;border-bottom:1px solid #eee;">
                {cat_emoji} <strong>{cat_label}</strong>
              </td>
              <td style="padding:8px 12px;border-bottom:1px solid #eee;">
                {len(files)} item{"s" if len(files) != 1 else ""}
              </td>
              <td style="padding:8px 12px;border-bottom:1px solid #eee;">
                {previews}
              </td>
            </tr>"""

    # Stats rows (non-zero only)
    stats_html = ""
    notable = {k: v for k, v in stats.items() if v and v > 0}
    if notable:
        stat_items = "".join(
            f'<span style="display:inline-block;margin:4px 8px;padding:4px 10px;'
            f'background:#f0f0f0;border-radius:12px;font-size:12px;">'
            f'{k.replace("_", " ").title()}: {v}</span>'
            for k, v in list(notable.items())[:10]
        )
        stats_html = f"""
        <div style="padding:12px 0;">
          <strong>Agent Stats</strong><br>
          {stat_items}
        </div>"""

    return f"""
    <div style="max-width:600px;margin:0 auto;font-family:-apple-system,BlinkMacSystemFont,
      'Segoe UI',Roboto,sans-serif;color:#333;">

      <!-- Header -->
      <div style="background:#1a1a1a;color:#fff;padding:20px;border-radius:8px 8px 0 0;">
        <h1 style="margin:0;font-size:22px;">🦞 GitClaw Daily Digest</h1>
        <p style="margin:4px 0 0;color:#aaa;font-size:14px;">{today_str}</p>
      </div>

      <!-- Stats Row -->
      <div style="display:flex;background:#f8f8f8;padding:12px;gap:16px;
        border-bottom:1px solid #e0e0e0;">
        <div style="flex:1;text-align:center;">
          <div style="font-size:20px;font-weight:700;">{xp}</div>
          <div style="font-size:11px;color:#888;">XP</div>
        </div>
        <div style="flex:1;text-align:center;">
          <div style="font-size:20px;font-weight:700;">{level}</div>
          <div style="font-size:11px;color:#888;">Level</div>
        </div>
        <div style="flex:1;text-align:center;">
          <div style="font-size:20px;font-weight:700;">{streak}d</div>
          <div style="font-size:11px;color:#888;">Streak</div>
        </div>
        <div style="flex:1;text-align:center;">
          <div style="font-size:20px;font-weight:700;">{total_items}</div>
          <div style="font-size:11px;color:#888;">Today</div>
        </div>
      </div>

      <!-- Activity -->
      <div style="padding:16px;">
        <h2 style="font-size:16px;margin:0 0 12px;">Today's Activity</h2>
        {"<table style='width:100%;border-collapse:collapse;'>" + activity_rows + "</table>"
         if activity_rows
         else "<p style='color:#999;'>No activity recorded today.</p>"}
      </div>

      <!-- Stats -->
      {stats_html}

      <!-- Footer -->
      <div style="background:#f8f8f8;padding:16px;border-radius:0 0 8px 8px;
        text-align:center;font-size:12px;color:#888;border-top:1px solid #e0e0e0;">
        <a href="{dashboard_url}" style="color:#007aff;text-decoration:none;">
          View Dashboard
        </a>
        &nbsp;·&nbsp;
        Powered by GitHub Actions
      </div>
    </div>"""


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log("Gmail", "Building daily digest")

    html_body = build_digest_html()
    subject = f"🦞 GitClaw Digest — {today()}"

    success = send_email(subject, html_body)

    if success:
        update_stats("gmail_digests_sent")
        award_xp(5)
    else:
        log("Gmail", "Digest email failed to send")


if __name__ == "__main__":
    main()
