#!/usr/bin/env python3
"""
Crypto Oracle — Mystical-yet-data-driven crypto quant analysis agent.
Fetches market data from CoinGecko, computes indicators with pure stdlib,
and delivers prophecies backed by real numbers.
"""

import json
import math
import os
import urllib.request
from datetime import datetime, timezone

from common import (
    MEMORY_DIR, award_xp, call_llm, gh_post_comment,
    log, read_prompt, today, update_stats,
)

# ── Constants ────────────────────────────────────────────────────────────────

AGENT = "Crypto Oracle"

COINGECKO_BASE = "https://api.coingecko.com/api/v3"

WELL_KNOWN_COINS = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "sol": "solana",
    "doge": "dogecoin",
    "bonk": "bonk",
    "jup": "jupiter",
    "bnb": "binancecoin",
    "xrp": "ripple",
    "ada": "cardano",
    "avax": "avalanche-2",
    "dot": "polkadot",
    "matic": "matic-network",
    "link": "chainlink",
    "uni": "uniswap",
    "atom": "cosmos",
}


# ── API Helpers ──────────────────────────────────────────────────────────────

def fetch_json(url: str) -> dict | list:
    """Fetch JSON from a URL. Returns error dict on failure."""
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "GitClaw-CryptoOracle/1.0")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def resolve_coin_id(query: str) -> str | None:
    """Resolve a user query to a CoinGecko coin ID."""
    query_lower = query.lower().strip()

    # Check well-known map first
    if query_lower in WELL_KNOWN_COINS:
        return WELL_KNOWN_COINS[query_lower]

    # Maybe they typed the full id already
    if query_lower in WELL_KNOWN_COINS.values():
        return query_lower

    # Search CoinGecko
    encoded = urllib.request.quote(query_lower)
    data = fetch_json(f"{COINGECKO_BASE}/search?query={encoded}")
    if isinstance(data, dict) and "error" in data:
        return None

    coins = data.get("coins", [])
    if coins:
        return coins[0].get("id")

    return None


def get_price_data(coin_id: str) -> dict:
    """Fetch current price, market cap, volume, and 24h change."""
    url = (
        f"{COINGECKO_BASE}/simple/price"
        f"?ids={coin_id}"
        f"&vs_currencies=usd"
        f"&include_24hr_change=true"
        f"&include_market_cap=true"
        f"&include_24hr_vol=true"
    )
    data = fetch_json(url)
    if isinstance(data, dict) and coin_id in data:
        return data[coin_id]
    return data


def get_ohlc(coin_id: str, days: int = 30) -> list:
    """Fetch OHLC candle data (30 days)."""
    url = f"{COINGECKO_BASE}/coins/{coin_id}/ohlc?vs_currency=usd&days={days}"
    data = fetch_json(url)
    if isinstance(data, dict) and "error" in data:
        return []
    return data if isinstance(data, list) else []


def get_market_chart(coin_id: str, days: int = 30) -> dict:
    """Fetch daily market chart data (prices, volumes)."""
    url = (
        f"{COINGECKO_BASE}/coins/{coin_id}/market_chart"
        f"?vs_currency=usd&days={days}&interval=daily"
    )
    data = fetch_json(url)
    if isinstance(data, dict) and "error" in data:
        return {}
    return data


def get_top_coins(limit: int = 10) -> list:
    """Fetch top coins by market cap."""
    url = (
        f"{COINGECKO_BASE}/coins/markets"
        f"?vs_currency=usd&order=market_cap_desc"
        f"&per_page={limit}&page=1&sparkline=false"
        f"&price_change_percentage=24h,7d"
    )
    data = fetch_json(url)
    if isinstance(data, dict) and "error" in data:
        return []
    return data if isinstance(data, list) else []


# ── Quant Indicators (stdlib only) ───────────────────────────────────────────

def compute_rsi(closes: list[float], period: int = 14) -> float | None:
    """Compute RSI (Relative Strength Index) from closing prices."""
    if len(closes) < period + 1:
        return None

    gains = []
    losses = []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

    if len(gains) < period:
        return None

    # Initial averages (SMA of first `period` values)
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    # Smoothed averages (Wilder's method)
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def compute_sma(values: list[float], period: int) -> float | None:
    """Compute Simple Moving Average over the last `period` values."""
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def compute_volatility(closes: list[float]) -> float | None:
    """Compute price volatility as std dev of daily returns."""
    if len(closes) < 3:
        return None

    returns = []
    for i in range(1, len(closes)):
        if closes[i - 1] != 0:
            returns.append((closes[i] - closes[i - 1]) / closes[i - 1])

    if len(returns) < 2:
        return None

    mean_r = sum(returns) / len(returns)
    variance = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
    return math.sqrt(variance)


def compute_volume_trend(volumes: list[float]) -> str:
    """Determine volume trend by comparing recent vs older average."""
    if len(volumes) < 6:
        return "insufficient data"

    midpoint = len(volumes) // 2
    older_avg = sum(volumes[:midpoint]) / midpoint
    recent_avg = sum(volumes[midpoint:]) / (len(volumes) - midpoint)

    if older_avg == 0:
        return "no baseline"

    change = (recent_avg - older_avg) / older_avg
    if change > 0.2:
        return f"surging (+{change:.0%})"
    elif change > 0.05:
        return f"rising (+{change:.0%})"
    elif change < -0.2:
        return f"drying up ({change:.0%})"
    elif change < -0.05:
        return f"fading ({change:.0%})"
    return "steady"


def compute_momentum_score(
    rsi: float | None,
    price: float,
    sma_7: float | None,
    sma_25: float | None,
    vol_trend: str,
) -> tuple[float, str]:
    """
    Compute a simple momentum score from -100 to +100.
    Returns (score, label).
    """
    score = 0.0
    factors = 0

    # RSI contribution
    if rsi is not None:
        if rsi > 70:
            score += 30
        elif rsi > 55:
            score += 15
        elif rsi < 30:
            score -= 30
        elif rsi < 45:
            score -= 15
        factors += 1

    # Price vs SMA
    if sma_7 is not None and sma_7 > 0:
        ratio_7 = (price - sma_7) / sma_7
        score += max(min(ratio_7 * 200, 30), -30)
        factors += 1

    if sma_25 is not None and sma_25 > 0:
        ratio_25 = (price - sma_25) / sma_25
        score += max(min(ratio_25 * 150, 25), -25)
        factors += 1

    # SMA crossover
    if sma_7 is not None and sma_25 is not None:
        if sma_7 > sma_25:
            score += 10
        else:
            score -= 10
        factors += 1

    # Volume trend
    if "surging" in vol_trend or "rising" in vol_trend:
        score += 5
        factors += 1
    elif "drying" in vol_trend or "fading" in vol_trend:
        score -= 5
        factors += 1

    if factors > 0:
        score = max(min(score, 100), -100)

    if score > 30:
        label = "Strongly Bullish"
    elif score > 10:
        label = "Bullish"
    elif score > -10:
        label = "Neutral"
    elif score > -30:
        label = "Bearish"
    else:
        label = "Strongly Bearish"

    return round(score, 1), label


# ── Analysis Builders ────────────────────────────────────────────────────────

def build_analysis(coin_id: str, query: str) -> str:
    """Build a full analysis report for a single coin."""
    log(AGENT, f"Analyzing: {coin_id}")

    price_data = get_price_data(coin_id)
    chart_data = get_market_chart(coin_id)
    ohlc_data = get_ohlc(coin_id)

    if isinstance(price_data, dict) and "error" in price_data:
        return f"The crystal ball is clouded — failed to fetch price data for `{query}`: {price_data['error']}"

    # Extract core metrics
    price = price_data.get("usd", 0)
    change_24h = price_data.get("usd_24h_change", 0)
    market_cap = price_data.get("usd_market_cap", 0)
    volume_24h = price_data.get("usd_24h_vol", 0)

    # Extract closing prices and volumes from chart data
    prices_raw = chart_data.get("prices", [])
    volumes_raw = chart_data.get("total_volumes", [])
    closes = [p[1] for p in prices_raw] if prices_raw else []
    volumes = [v[1] for v in volumes_raw] if volumes_raw else []

    # Also extract closes from OHLC (column index 4 = close)
    ohlc_closes = [c[4] for c in ohlc_data] if ohlc_data else []

    # Use the better dataset for indicators
    indicator_closes = closes if len(closes) >= len(ohlc_closes) else ohlc_closes

    # Compute indicators
    rsi = compute_rsi(indicator_closes)
    sma_7 = compute_sma(indicator_closes, 7)
    sma_25 = compute_sma(indicator_closes, 25)
    volatility = compute_volatility(indicator_closes)
    vol_trend = compute_volume_trend(volumes) if volumes else "no data"
    momentum, momentum_label = compute_momentum_score(rsi, price, sma_7, sma_25, vol_trend)

    # Format numbers
    def fmt_usd(v: float) -> str:
        if v >= 1_000_000_000:
            return f"${v / 1_000_000_000:.2f}B"
        if v >= 1_000_000:
            return f"${v / 1_000_000:.2f}M"
        if v >= 1_000:
            return f"${v / 1_000:.2f}K"
        return f"${v:,.2f}"

    def fmt_price(v: float) -> str:
        if v >= 1:
            return f"${v:,.2f}"
        if v >= 0.01:
            return f"${v:.4f}"
        return f"${v:.8f}"

    # Build raw data report
    lines = [
        f"## Crypto Oracle Analysis: {coin_id.upper()}\n",
        f"**Price:** {fmt_price(price)}",
        f"**24h Change:** {change_24h:+.2f}%" if change_24h else "**24h Change:** N/A",
        f"**Market Cap:** {fmt_usd(market_cap)}" if market_cap else "**Market Cap:** N/A",
        f"**24h Volume:** {fmt_usd(volume_24h)}" if volume_24h else "**24h Volume:** N/A",
        "",
        "### Indicators",
        f"- RSI (14): {rsi:.1f}" if rsi is not None else "- RSI (14): insufficient data",
        f"- SMA 7-day: {fmt_price(sma_7)}" if sma_7 is not None else "- SMA 7-day: insufficient data",
        f"- SMA 25-day: {fmt_price(sma_25)}" if sma_25 is not None else "- SMA 25-day: insufficient data",
        f"- Volatility (daily): {volatility:.4f} ({volatility * 100:.2f}%)" if volatility is not None else "- Volatility: insufficient data",
        f"- Volume Trend: {vol_trend}",
        f"- Momentum Score: {momentum:+.1f} ({momentum_label})",
        "",
        f"Data points: {len(indicator_closes)} daily closes",
    ]

    return "\n".join(lines)


def build_comparison(coin_a_id: str, coin_b_id: str, query_a: str, query_b: str) -> str:
    """Build a side-by-side comparison of two coins."""
    log(AGENT, f"Comparing: {coin_a_id} vs {coin_b_id}")

    results = []
    for coin_id, label in [(coin_a_id, query_a), (coin_b_id, query_b)]:
        price_data = get_price_data(coin_id)
        chart_data = get_market_chart(coin_id)

        prices_raw = chart_data.get("prices", [])
        volumes_raw = chart_data.get("total_volumes", [])
        closes = [p[1] for p in prices_raw] if prices_raw else []
        volumes = [v[1] for v in volumes_raw] if volumes_raw else []

        price = price_data.get("usd", 0) if isinstance(price_data, dict) and "error" not in price_data else 0
        change = price_data.get("usd_24h_change", 0) if isinstance(price_data, dict) and "error" not in price_data else 0
        mcap = price_data.get("usd_market_cap", 0) if isinstance(price_data, dict) and "error" not in price_data else 0

        rsi = compute_rsi(closes)
        sma_7 = compute_sma(closes, 7)
        sma_25 = compute_sma(closes, 25)
        volatility = compute_volatility(closes)
        vol_trend = compute_volume_trend(volumes) if volumes else "no data"
        momentum, momentum_label = compute_momentum_score(rsi, price, sma_7, sma_25, vol_trend)

        results.append({
            "label": label.upper(),
            "coin_id": coin_id,
            "price": price,
            "change_24h": change,
            "market_cap": mcap,
            "rsi": rsi,
            "sma_7": sma_7,
            "sma_25": sma_25,
            "volatility": volatility,
            "vol_trend": vol_trend,
            "momentum": momentum,
            "momentum_label": momentum_label,
        })

    a, b = results

    def fval(v, fmt=".2f"):
        return f"{v:{fmt}}" if v is not None else "N/A"

    lines = [
        f"## Crypto Oracle: {a['label']} vs {b['label']}\n",
        "| Metric | {} | {} |".format(a["label"], b["label"]),
        "|--------|------|------|",
        f"| Price | ${fval(a['price'])} | ${fval(b['price'])} |",
        f"| 24h Change | {fval(a['change_24h'], '+.2f')}% | {fval(b['change_24h'], '+.2f')}% |",
        f"| RSI (14) | {fval(a['rsi'], '.1f')} | {fval(b['rsi'], '.1f')} |",
        f"| Volatility | {fval(a['volatility'], '.4f')} | {fval(b['volatility'], '.4f')} |",
        f"| Volume Trend | {a['vol_trend']} | {b['vol_trend']} |",
        f"| Momentum | {fval(a['momentum'], '+.1f')} ({a['momentum_label']}) | {fval(b['momentum'], '+.1f')} ({b['momentum_label']}) |",
    ]

    return "\n".join(lines)


def build_market_overview() -> str:
    """Build a top-10 market overview."""
    log(AGENT, "Market overview")

    coins = get_top_coins(10)
    if not coins:
        return "The oracle's vision is obscured — could not fetch market data."

    lines = [
        "## Crypto Oracle: Market Overview (Top 10)\n",
        "| # | Coin | Price | 24h | 7d | Market Cap |",
        "|---|------|-------|-----|-----|------------|",
    ]

    for i, coin in enumerate(coins, 1):
        symbol = coin.get("symbol", "?").upper()
        price = coin.get("current_price", 0)
        change_24h = coin.get("price_change_percentage_24h_in_currency", coin.get("price_change_percentage_24h", 0))
        change_7d = coin.get("price_change_percentage_7d_in_currency", 0)
        mcap = coin.get("market_cap", 0)

        price_str = f"${price:,.2f}" if price >= 1 else f"${price:.6f}"
        mcap_str = f"${mcap / 1e9:.1f}B" if mcap >= 1e9 else f"${mcap / 1e6:.0f}M"
        c24 = f"{change_24h:+.1f}%" if change_24h else "N/A"
        c7d = f"{change_7d:+.1f}%" if change_7d else "N/A"

        lines.append(f"| {i} | {symbol} | {price_str} | {c24} | {c7d} | {mcap_str} |")

    # Compute aggregate sentiment
    changes = [c.get("price_change_percentage_24h", 0) or 0 for c in coins]
    avg_change = sum(changes) / len(changes) if changes else 0
    green_count = sum(1 for c in changes if c > 0)

    lines.append("")
    lines.append(f"**Market Pulse:** {green_count}/10 coins green | Avg 24h: {avg_change:+.1f}%")

    return "\n".join(lines)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    raw_args = os.environ.get("QUERY_ARGS", "").strip()
    issue_number = int(os.environ.get("ISSUE_NUMBER", "0"))

    log(AGENT, f"Invoked with args: '{raw_args}'")

    # Parse command: "compare btc eth", "market", or just "btc"
    parts = raw_args.split()
    command = parts[0].lower() if parts else "market"

    try:
        if command == "compare" and len(parts) >= 3:
            # Compare two coins
            query_a, query_b = parts[1], parts[2]
            coin_a = resolve_coin_id(query_a)
            coin_b = resolve_coin_id(query_b)
            if not coin_a:
                raw_data = f"Could not find coin: `{query_a}`. Try a ticker like `btc` or `sol`."
            elif not coin_b:
                raw_data = f"Could not find coin: `{query_b}`. Try a ticker like `btc` or `sol`."
            else:
                raw_data = build_comparison(coin_a, coin_b, query_a, query_b)

        elif command == "market":
            raw_data = build_market_overview()

        else:
            # Single coin analysis (the command itself is the coin query)
            query = raw_args
            coin_id = resolve_coin_id(query)
            if not coin_id:
                raw_data = f"The oracle cannot find `{query}` in the ledger of coins. Try a ticker like `btc`, `sol`, or `eth`."
            else:
                raw_data = build_analysis(coin_id, query)

    except Exception as e:
        log(AGENT, f"Data fetch error: {e}")
        raw_data = f"The crystal ball cracked mid-reading: {e}"

    # Pass through LLM for mystical commentary
    try:
        system_prompt = read_prompt("crypto-quant")
        user_message = (
            f"Command: {command}\n"
            f"Query: {raw_args}\n"
            f"Date: {today()}\n\n"
            f"Raw data:\n{raw_data}\n\n"
            f"Transform this data into your mystical oracle format. "
            f"Keep ALL real numbers accurate — embellish the narrative, never the data. "
            f"Include your full oracle reading with all sections."
        )
        response = call_llm(system_prompt, user_message, max_tokens=2000)
    except Exception as e:
        log(AGENT, f"LLM commentary failed: {e}, using raw data")
        response = (
            f"{raw_data}\n\n"
            f"*The oracle's voice is hoarse today (LLM unavailable), "
            f"but the numbers speak for themselves.*\n\n"
            f"**Disclaimer:** NOT financial advice. For entertainment/educational purposes only.\n\n"
            f"--- 🔮 *The Oracle has spoken. The candles do not lie. NFA.*"
        )

    # Post to issue
    if issue_number > 0:
        gh_post_comment(issue_number, response)

    # Persist to memory
    archive_dir = MEMORY_DIR / "crypto"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_file = archive_dir / f"{today()}-{command}.md"
    with open(archive_file, "a") as f:
        ts = datetime.now(timezone.utc).strftime("%H:%M UTC")
        f.write(f"\n---\n### {ts} — {command} {raw_args}\n\n{raw_data}\n")

    update_stats("crypto_analyses")
    award_xp(15)

    print(response)


if __name__ == "__main__":
    main()
