#!/usr/bin/env python3
"""Solana Monitor — tracks wallet balances and token movements."""

import json
import sys
import os
from datetime import datetime
from pathlib import Path

try:
    from common import (
        get_state, save_state, load_yaml, log, format_price,
        run_shell, render_template
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from common import (
        get_state, save_state, load_yaml, log, format_price,
        run_shell, render_template
    )


def call_solana_api(method: str, params: list) -> dict:
    """Call Solana RPC with error handling."""
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params
    })
    
    rpc_url = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
    result = run_shell([
        "curl", "-sS", "-X", "POST", rpc_url,
        "-H", "Content-Type: application/json",
        "-d", payload
    ])
    
    if result["exit_code"] != 0:
        log(f"❌ Solana API call failed: {result['stderr']}", level="error")
        return {"error": result["stderr"]}
    
    try:
        data = json.loads(result["stdout"])
    except json.JSONDecodeError as e:
        log(f"❌ Failed to parse API response: {e}", level="error")
        log(f"Raw response: {result['stdout'][:500]}", level="debug")
        return {"error": f"JSON parse error: {e}"}
    
    if "error" in data:
        log(f"❌ API returned error: {data['error']}", level="error")
        return {"error": data["error"]}
    
    return data.get("result", {})


def get_sol_balance(address: str) -> float:
    """Get SOL balance for an address."""
    result = call_solana_api("getBalance", [address])
    if "error" in result:
        log(f"⚠️  Failed to get SOL balance for {address}: {result['error']}", level="warning")
        return 0.0
    
    try:
        lamports = result.get("value", 0)
        return lamports / 1e9
    except (TypeError, ValueError) as e:
        log(f"⚠️  Invalid balance value for {address}: {e}", level="warning")
        return 0.0


def get_token_accounts(address: str) -> list:
    """Get SPL token accounts for an address."""
    result = call_solana_api(
        "getTokenAccountsByOwner",
        [
            address,
            {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
            {"encoding": "jsonParsed"}
        ]
    )
    
    if "error" in result:
        log(f"⚠️  Failed to get token accounts for {address}: {result['error']}", level="warning")
        return []
    
    try:
        accounts = result.get("value", [])
        return accounts
    except (TypeError, ValueError) as e:
        log(f"⚠️  Invalid token accounts data for {address}: {e}", level="warning")
        return []


def parse_token_account(account: dict) -> dict:
    """Parse token account data with error handling."""
    try:
        parsed = account["account"]["data"]["parsed"]["info"]
        token_amount = parsed["tokenAmount"]
        
        return {
            "mint": parsed["mint"],
            "amount": float(token_amount["uiAmount"] or 0),
            "decimals": token_amount["decimals"]
        }
    except (KeyError, TypeError, ValueError) as e:
        log(f"⚠️  Failed to parse token account: {e}", level="warning")
        log(f"Raw account data: {account}", level="debug")
        return None


def get_token_metadata(mint: str) -> dict:
    """Get token metadata from Jupiter API."""
    result = run_shell([
        "curl", "-sS",
        f"https://tokens.jup.ag/token/{mint}"
    ])
    
    if result["exit_code"] != 0:
        log(f"⚠️  Failed to fetch metadata for {mint}: {result['stderr']}", level="warning")
        return {"symbol": mint[:8], "name": "Unknown"}
    
    try:
        data = json.loads(result["stdout"])
        return {
            "symbol": data.get("symbol", mint[:8]),
            "name": data.get("name", "Unknown")
        }
    except json.JSONDecodeError as e:
        log(f"⚠️  Failed to parse token metadata for {mint}: {e}", level="warning")
        return {"symbol": mint[:8], "name": "Unknown"}


def monitor_wallet(wallet: dict, state: dict) -> dict:
    """Monitor a single wallet."""
    address = wallet["address"]
    name = wallet["name"]
    
    log(f"📊 Monitoring {name} ({address})")
    
    # Get SOL balance
    sol_balance = get_sol_balance(address)
    
    # Get token balances
    token_accounts = get_token_accounts(address)
    tokens = []
    
    for account in token_accounts:
        parsed = parse_token_account(account)
        if parsed is None:
            continue  # Skip malformed accounts
        
        if parsed["amount"] > 0:
            metadata = get_token_metadata(parsed["mint"])
            tokens.append({
                "mint": parsed["mint"],
                "symbol": metadata["symbol"],
                "name": metadata["name"],
                "amount": parsed["amount"]
            })
    
    # Check for changes
    wallet_key = f"wallet_{address}"
    prev = state.get(wallet_key, {})
    
    changes = []
    
    # SOL balance change
    prev_sol = prev.get("sol_balance", 0)
    if abs(sol_balance - prev_sol) > 0.01:
        diff = sol_balance - prev_sol
        changes.append({
            "type": "sol_balance",
            "token": "SOL",
            "prev": prev_sol,
            "curr": sol_balance,
            "diff": diff
        })
    
    # Token changes
    prev_tokens = {t["mint"]: t["amount"] for t in prev.get("tokens", [])}
    curr_tokens = {t["mint"]: t["amount"] for t in tokens}
    
    for mint, amount in curr_tokens.items():
        prev_amount = prev_tokens.get(mint, 0)
        if abs(amount - prev_amount) > 0.01:
            token = next((t for t in tokens if t["mint"] == mint), None)
            if token:
                changes.append({
                    "type": "token_balance",
                    "token": token["symbol"],
                    "mint": mint,
                    "prev": prev_amount,
                    "curr": amount,
                    "diff": amount - prev_amount
                })
    
    # Store current state
    state[wallet_key] = {
        "sol_balance": sol_balance,
        "tokens": tokens,
        "last_check": datetime.utcnow().isoformat()
    }
    
    return {
        "name": name,
        "address": address,
        "sol_balance": sol_balance,
        "tokens": tokens,
        "changes": changes
    }


def main():
    """Monitor all configured wallets."""
    try:
        config = load_yaml("config/solana.yml")
    except Exception as e:
        log(f"❌ Failed to load config: {e}", level="error")
        sys.exit(1)
    
    if not config.get("enabled", False):
        log("⏸️  Solana monitoring disabled")
        return
    
    wallets = config.get("wallets", [])
    if not wallets:
        log("⚠️  No wallets configured")
        return
    
    # Load state
    try:
        state = get_state()
    except Exception as e:
        log(f"⚠️  Failed to load state, using empty state: {e}", level="warning")
        state = {}
    
    # Monitor each wallet
    results = []
    for wallet in wallets:
        try:
            result = monitor_wallet(wallet, state)
            results.append(result)
        except Exception as e:
            log(f"❌ Error monitoring wallet {wallet.get('name', 'unknown')}: {e}", level="error")
            continue  # Continue with next wallet instead of crashing
    
    # Save state
    try:
        save_state(state)
    except Exception as e:
        log(f"❌ Failed to save state: {e}", level="error")
    
    # Increment monitoring counter
    try:
        state["solana_monitors"] = state.get("solana_monitors", 0) + 1
        save_state(state)
    except Exception as e:
        log(f"⚠️  Failed to increment monitor counter: {e}", level="warning")
    
    # Report
    log(f"✅ Monitored {len(results)} wallets")
    
    for result in results:
        if result["changes"]:
            log(f"🔔 Changes detected for {result['name']}:")
            for change in result["changes"]:
                token = change["token"]
                diff = change["diff"]
                sign = "+" if diff > 0 else ""
                log(f"   {token}: {sign}{format_price(diff)}")


if __name__ == "__main__":
    main()
