#!/usr/bin/env python3
"""
Solana Monitoring Agent — Tracks wallet balances and alerts on changes.

Runs on schedule via GitHub Actions.
Fetches current state from Solana RPC, compares to previous snapshot,
detects notable changes and surfaces them as alerts.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from agents.shared_utils import (
    MEMORY_DIR,
    award_xp,
    call_llm,
    gh_post_comment,
    log,
    run_shell,
    today,
    update_stats,
)
from integrations.solana_utils import WELL_KNOWN_MINTS, get_balance

SNAPSHOTS_DIR = MEMORY_DIR / "solana" / "snapshots"
ALERTS_DIR = MEMORY_DIR / "solana" / "alerts"


def load_previous_snapshot() -> dict:
    """Load the most recent monitoring snapshot, with fallback on errors."""
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    snapshot_files = sorted(SNAPSHOTS_DIR.glob("*.json"))
    if snapshot_files:
        try:
            return json.loads(snapshot_files[-1].read_text())
        except json.JSONDecodeError as e:
            log(f"⚠️  Corrupted snapshot {snapshot_files[-1].name}: {e}", level="warning")
            return {}
        except (OSError, IOError) as e:
            log(f"⚠️  Failed to read snapshot: {e}", level="warning")
            return {}
    return {}


def save_snapshot(data: dict) -> Path:
    """Save current monitoring state snapshot with atomic write."""
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    path = SNAPSHOTS_DIR / f"snapshot-{ts}.json"
    try:
        # Atomic write: write to temp, then rename
        temp_path = path.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(data, indent=2) + "\n")
        temp_path.rename(path)
    except (OSError, IOError) as e:
        log(f"⚠️  Failed to write snapshot: {e}", level="warning")
    return path


def get_watched_wallets() -> list[dict]:
    """Get wallets to monitor from environment or config."""
    wallets_json = os.environ.get("SOLANA_WALLETS", "[]")
    try:
        wallets = json.loads(wallets_json)
        if not isinstance(wallets, list):
            log("❌ SOLANA_WALLETS must be a JSON array", level="error")
            return []
        return wallets
    except json.JSONDecodeError as e:
        log(f"❌ Invalid SOLANA_WALLETS JSON: {e}", level="error")
        return []


def get_watchlist_tokens() -> list[str]:
    """Get tokens to track from environment or config."""
    tokens = os.environ.get("SOLANA_WATCHLIST", "SOL")
    return [t.strip().upper() for t in tokens.split(",") if t.strip()]


def check_wallets(wallets: list[dict]) -> list[dict]:
    """Check balances for all watched wallets, continuing on individual failures."""
    results = []
    for wallet in wallets:
        address = wallet.get("address", "")
        label = wallet.get("label", address[:8])
        if not address:
            log(f"⚠️  Wallet missing address, skipping", level="warning")
            continue
        try:
            balance = get_balance(address)
            results.append({
                "address": address,
                "label": label,
                "balance_sol": balance,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            log(f"⚠️  Failed to fetch balance for {label}: {e}, skipping", level="warning")
            continue
    return results


def detect_notable_changes(prev: dict, current: list[dict]) -> list[dict]:
    """Compare current balances to previous snapshot, find notable deltas."""
    changes = []
    prev_balances = {w["address"]: w.get("balance_sol", 0) for w in prev.get("wallets", [])}

    for wallet in current:
        address = wallet["address"]
        current_bal = wallet["balance_sol"]
        prev_bal = prev_balances.get(address, 0)

        delta = current_bal - prev_bal
        if abs(delta) > 0.01:  # Notable if > 0.01 SOL change
            changes.append({
                "wallet": wallet["label"],
                "address": address,
                "previous": prev_bal,
                "current": current_bal,
                "delta": delta,
            })

    return changes


def format_alert(changes: list[dict]) -> str:
    """Format monitoring changes into human-readable alert."""
    lines = ["## 🔍 Solana Wallet Changes Detected", ""]
    for change in changes:
        emoji = "📈" if change["delta"] > 0 else "📉"
        lines.append(
            f"{emoji} **{change['wallet']}**: "
            f"{change['previous']:.4f} → {change['current']:.4f} SOL "
            f"({change['delta']:+.4f})"
        )
    return "\n".join(lines)


def main():
    log("🔍 Solana Monitor — Starting sweep...")

    wallets = get_watched_wallets()
    if not wallets:
        log("⚠️  No wallets configured, exiting")
        return

    log(f"📊 Monitoring {len(wallets)} wallet(s)...")

    prev_snapshot = load_previous_snapshot()
    current_balances = check_wallets(wallets)

    if not current_balances:
        log("⚠️  Failed to fetch any wallet balances, skipping snapshot")
        return

    current_snapshot = {"timestamp": datetime.now(timezone.utc).isoformat(), "wallets": current_balances}

    save_snapshot(current_snapshot)

    changes = detect_notable_changes(prev_snapshot, current_balances)

    if changes:
        log(f"🚨 {len(changes)} notable change(s) detected")
        alert_msg = format_alert(changes)
        log(alert_msg)

        # Save alert to memory
        ALERTS_DIR.mkdir(parents=True, exist_ok=True)
        alert_file = ALERTS_DIR / f"alert-{today()}.md"
        alert_file.write_text(alert_msg)

        # Update stats
        update_stats({"solana_alerts": 1})
        award_xp("solana_monitor", 10)

    else:
        log("✅ No notable changes detected")

    log("✅ Solana Monitor — Sweep complete")


if __name__ == "__main__":
    main()
