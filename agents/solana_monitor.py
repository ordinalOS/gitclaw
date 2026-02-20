#!/usr/bin/env python3
import json
import os
import sys
import subprocess
from datetime import datetime
import time

def log(emoji, message):
    timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    print(f"{timestamp} {emoji} {message}", flush=True)

def load_state():
    try:
        with open('memory/state.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"agents": {}}

def save_state(state):
    os.makedirs('memory', exist_ok=True)
    with open('memory/state.json', 'w') as f:
        json.dump(state, f, indent=2)

def get_agent_state(state):
    if 'solana_monitor' not in state['agents']:
        state['agents']['solana_monitor'] = {
            'solana_monitors': 0,
            'failed_sweeps': 0,
            'last_sweep': None,
            'tracked_addresses': []
        }
    return state['agents']['solana_monitor']

def rpc_call_with_retry(method, params, max_retries=3):
    """Make RPC call with exponential backoff retry logic."""
    rpc_url = os.environ.get('SOLANA_RPC_URL', 'https://api.mainnet-beta.solana.com')
    
    for attempt in range(max_retries):
        try:
            payload = json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "method": method,
                "params": params
            })
            
            result = subprocess.run(
                ['curl', '-s', '-X', 'POST', rpc_url,
                 '-H', 'Content-Type: application/json',
                 '-d', payload],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                raise Exception(f"curl failed with code {result.returncode}")
            
            response = json.loads(result.stdout)
            
            # Validate response structure
            if not isinstance(response, dict):
                raise ValueError("RPC response is not a JSON object")
            
            if 'error' in response:
                error_msg = response['error'].get('message', 'Unknown error')
                raise Exception(f"RPC error: {error_msg}")
            
            if 'result' not in response:
                raise ValueError("RPC response missing 'result' field")
            
            return response['result']
            
        except subprocess.TimeoutExpired:
            log('⏱️', f"RPC timeout on attempt {attempt + 1}/{max_retries}")
        except json.JSONDecodeError as e:
            log('🔴', f"Invalid JSON response on attempt {attempt + 1}/{max_retries}: {e}")
        except Exception as e:
            log('🔴', f"RPC call failed on attempt {attempt + 1}/{max_retries}: {e}")
        
        # Exponential backoff: 2s, 4s, 8s
        if attempt < max_retries - 1:
            delay = 2 ** (attempt + 1)
            log('🔄', f"Retrying in {delay}s...")
            time.sleep(delay)
    
    # All retries exhausted
    return None

def get_account_balance(address):
    """Get SOL balance for an address with retry logic."""
    result = rpc_call_with_retry('getBalance', [address])
    if result is None:
        return None
    
    try:
        if isinstance(result, dict) and 'value' in result:
            return result['value'] / 1e9  # lamports to SOL
        return None
    except (KeyError, TypeError) as e:
        log('🔴', f"Failed to parse balance response: {e}")
        return None

def get_token_accounts(address):
    """Get SPL token accounts for an address with retry logic."""
    result = rpc_call_with_retry(
        'getTokenAccountsByOwner',
        [
            address,
            {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
            {"encoding": "jsonParsed"}
        ]
    )
    
    if result is None:
        return []
    
    try:
        if isinstance(result, dict) and 'value' in result:
            return result['value']
        return []
    except (KeyError, TypeError) as e:
        log('🔴', f"Failed to parse token accounts response: {e}")
        return []

def get_recent_transactions(address):
    """Get recent transaction signatures with retry logic."""
    result = rpc_call_with_retry(
        'getSignaturesForAddress',
        [address, {"limit": 10}]
    )
    
    if result is None:
        return []
    
    try:
        if isinstance(result, list):
            return result
        return []
    except TypeError as e:
        log('🔴', f"Failed to parse transactions response: {e}")
        return []

def monitor_address(address, agent_state):
    """Monitor a single Solana address."""
    log('🔍', f"Monitoring address: {address[:8]}...{address[-8:]}")
    
    # Get SOL balance
    balance = get_account_balance(address)
    if balance is not None:
        log('💰', f"SOL Balance: {balance:.4f} SOL")
    else:
        log('⚠️', f"Could not fetch SOL balance for {address[:8]}...")
    
    # Get token accounts
    token_accounts = get_token_accounts(address)
    if token_accounts:
        log('🪙', f"Found {len(token_accounts)} token accounts")
        for account in token_accounts[:5]:  # Limit output
            try:
                parsed = account.get('account', {}).get('data', {}).get('parsed', {})
                info = parsed.get('info', {})
                mint = info.get('mint', 'unknown')
                token_balance = info.get('tokenAmount', {}).get('uiAmount', 0)
                log('  📊', f"Token: {mint[:8]}... Balance: {token_balance}")
            except (KeyError, AttributeError):
                continue
    
    # Get recent transactions
    transactions = get_recent_transactions(address)
    if transactions:
        log('📜', f"Found {len(transactions)} recent transactions")
        for tx in transactions[:3]:  # Limit output
            try:
                sig = tx.get('signature', 'unknown')
                slot = tx.get('slot', 'unknown')
                log('  🔗', f"TX: {sig[:8]}... Slot: {slot}")
            except (KeyError, AttributeError):
                continue

def main():
    log('📡', 'Starting Solana monitoring sweep')
    
    state = load_state()
    agent_state = get_agent_state(state)
    
    # Get addresses to monitor from config or state
    addresses = agent_state.get('tracked_addresses', [])
    
    # If no addresses configured, monitor a default address
    if not addresses:
        # Solana Foundation address as example
        addresses = ['CerTgCHHWBjJY2py9mfy2Hq7W5K8yZU7MFTrfMpK6J6u']
        log('ℹ️', 'No addresses configured, using default monitoring target')
    
    sweep_success = True
    for address in addresses:
        try:
            monitor_address(address, agent_state)
        except Exception as e:
            log('🔴', f"Error monitoring {address[:8]}...: {e}")
            sweep_success = False
    
    # Update state
    agent_state['solana_monitors'] += 1
    agent_state['last_sweep'] = datetime.utcnow().isoformat() + 'Z'
    
    if not sweep_success:
        agent_state['failed_sweeps'] = agent_state.get('failed_sweeps', 0) + 1
        log('⚠️', f"Sweep completed with errors (total failed: {agent_state['failed_sweeps']})")
    else:
        log('✅', f"Sweep completed successfully (total sweeps: {agent_state['solana_monitors']})")
    
    save_state(state)
    
    log('📡', 'Solana monitoring sweep complete')

if __name__ == '__main__':
    main()
