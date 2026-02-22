#!/usr/bin/env python3
"""
Solana Monitor Agent — Scheduled wallet and token price monitoring.
Tracks balances and prices, detects changes, generates alerts.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from common import (
    MEMORY_DIR, award_xp, call_llm, gh_post_comment,
    log, read_prompt, today, update_stats,
)
from solana_query import (
    dex_search, get_balance, WELL_KNOWN_MINTS,
)

SNAPSHOTS_DIR = MEMORY_DIR / "solana" / "wallets"
ALERTS_DIR = MEMORY_DIR / "solana" / "alerts"


def load_previous_snapshot() -> dict:
    """Load the most recent monitoring snapshot."""
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    snapshot_files = sorted(SNAPSHOTS_DIR.glob("*.json"))
    if snapshot_files:
        try:
            return json.loads(snapshot_files[-1].read_text())
        except json.JSONDecodeError as e:
            log(f"⚠️  Corrupted snapshot file: {snapshot_files[-1].name}", level="warning")
            log(f"Parse error: {e}", level="debug")
            # Return empty dict but log the corruption for investigation
            return {}
        except Exception as e:
            log(f"❌ Failed to read snapshot: {e}", level="error")
            sys.exit(1)
    return {}


def save_snapshot(data: dict) -> Path:
    """Save current monitoring snapshot."""
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    path = SNAPSHOTS_DIR / f"snapshot-{ts}.json"
    try:
        path.write_text(json.dumps(data, indent=2) + "\n")
    except (OSError, IOError) as e:
        log(f"❌ Failed to write snapshot: {e}", level="error")
        sys.exit(1)
    return path


def get_watched_wallets() -> list[dict]:
    """Get wallets to monitor from environment or config."""
    wallets_json = os.environ.get("SOLANA_WALLETS", "[]")
    try:
        wallets = json.loads(wallets_json)
        if not isinstance(wallets, list):
            log("❌ SOLANA_WALLETS must be a JSON array", level="error")
            sys.exit(1)
        return wallets
    except json.JSONDecodeError as e:
        log(f"❌ Invalid SOLANA_WALLETS JSON: {e}", level="error")
        sys.exit(1)


def fetch_current_state() -> dict:
    """Fetch current balances for all watched wallets."""
    wallets = get_watched_wallets()
    current = {"timestamp": datetime.now(timezone.utc).isoformat(), "wallets": {}}

    for wallet in wallets:
        address = wallet.get("address")
        if not address:
            log("⚠️  Wallet missing 'address' field, skipping", level="warning")
            continue

        label = wallet.get("label", address[:8])
        log(f"📊 Checking {label}...")

        try:
            # Get SOL balance - this calls Solana RPC internally
            sol_balance = get_balance(address)
            
            # If get_balance returns None or negative (error indicator), fail-fast
            if sol_balance is None:
                log(f"❌ Failed to fetch SOL balance for {label}", level="error")
                sys.exit(1)

            current["wallets"][address] = {
                "label": label,
                "sol": sol_balance,
                "tokens": {},  # Token account parsing would go here
            }

        except Exception as e:
            # Any exception during balance fetch is critical - don't continue with partial data
            log(f"❌ Critical error fetching balance for {label}: {type(e).__name__}", level="error")
            sys.exit(1)

    return current


def detect_changes(previous: dict, current: dict) -> list[dict]:
    """Compare snapshots and detect significant changes."""
    changes = []

    if not previous or "wallets" not in previous:
        return changes

    for address, curr_data in current.get("wallets", {}).items():
        prev_data = previous.get("wallets", {}).get(address)
        if not prev_data:
            continue

        # Check SOL balance changes
        prev_sol = prev_data.get("sol", 0)
        curr_sol = curr_data.get("sol", 0)
        diff = curr_sol - prev_sol

        if abs(diff) > 0.01:  # More than 0.01 SOL change
            changes.append({
                "wallet": curr_data.get("label", address[:8]),
                "type": "sol_balance",
                "previous": prev_sol,
                "current": curr_sol,
                "change": diff,
            })

    return changes


def generate_alert(changes: list[dict]) -> str | None:
    """Generate alert message for detected changes."""
    if not changes:
        return None

    prompt = read_prompt("solana_monitor_alert")
    prompt_data = {
        "changes": changes,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        response = call_llm(prompt, json.dumps(prompt_data, indent=2))
        return response
    except Exception as e:
        log(f"⚠️  Failed to generate alert via LLM: {type(e).__name__}", level="warning")
        # Fallback to simple text alert
        lines = ["🚨 Solana Wallet Changes Detected:"]
        for change in changes:
            lines.append(
                f"- {change['wallet']}: {change['type']} changed by {change['change']:.4f}"
            )
        return "\n".join(lines)


def run_monitoring_sweep():
    """Execute one monitoring sweep cycle."""
    log("🔍 Starting Solana monitoring sweep...")

    previous = load_previous_snapshot()
    current = fetch_current_state()

    changes = detect_changes(previous, current)

    if changes:
        log(f"🚨 Detected {len(changes)} change(s)")
        alert = generate_alert(changes)

        if alert:
            ALERTS_DIR.mkdir(parents=True, exist_ok=True)
            alert_file = ALERTS_DIR / f"alert-{today()}.txt"
            try:
                alert_file.write_text(alert)
                log(f"📝 Alert saved to {alert_file.name}")
            except (OSError, IOError) as e:
                log(f"⚠️  Failed to save alert file: {e}", level="warning")

            # Try to post to GitHub if in CI environment
            if os.environ.get("GITHUB_ACTIONS") == "true":
                try:
                    gh_post_comment(alert)
                except Exception as e:
                    log(f"⚠️  Failed to post GitHub comment: {type(e).__name__}", level="warning")
    else:
        log("✅ No significant changes detected")

    # Save current snapshot
    snapshot_path = save_snapshot(current)
    log(f"💾 Snapshot saved: {snapshot_path.name}")

    # Award XP for successful monitoring sweep
    update_stats("solana_monitor", "sweeps_completed")
    award_xp("solana_monitor", 5)

    log("✅ Monitoring sweep complete")


if __name__ == "__main__":
    try:
        run_monitoring_sweep()
    except KeyboardInterrupt:
        log("\n⚠️  Monitoring interrupted by user", level="warning")
        sys.exit(130)
    except Exception as e:
        log(f"❌ Fatal error in monitoring sweep: {type(e).__name__}: {e}", level="error")
        sys.exit(1)
