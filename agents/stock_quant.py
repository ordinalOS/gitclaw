#!/usr/bin/env python3
"""
Stock Quant Agent — Wall Street Wizard.
Fetches stock data, computes quant indicators with pure stdlib, and
delivers wizard-themed financial analysis. Supports single-ticker analysis,
side-by-side comparisons, and major-index market overviews.
"""

import json
import math
import os
import sys
import urllib.request
from datetime import datetime, timezone

from common import (
    MEMORY_DIR, award_xp, call_llm, gh_post_comment,
    log, read_prompt, today, update_stats,
)

# ── Constants ────────────────────────────────────────────────────────────────

AGENT = "Stock Quant"
ALPHA_VANTAGE_BASE = "https://www.alphavantage.co/query"
YAHOO_CHART_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"
MARKET_INDICES = ["SPY", "QQQ", "DIA"]


# ── HTTP Helper ──────────────────────────────────────────────────────────────

def fetch_json(url: str) -> dict:
    """Fetch JSON from a URL with a reasonable timeout."""
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "GitClaw-StockQuant/1.0")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


# ── Data Providers ───────────────────────────────────────────────────────────

def av_daily(symbol: str, api_key: str) -> dict:
    """Fetch daily time series from Alpha Vantage."""
    url = (f"{ALPHA_VANTAGE_BASE}?function=TIME_SERIES_DAILY"
           f"&symbol={symbol}&apikey={api_key}")
    return fetch_json(url)


def av_quote(symbol: str, api_key: str) -> dict:
    """Fetch global quote from Alpha Vantage."""
    url = (f"{ALPHA_VANTAGE_BASE}?function=GLOBAL_QUOTE"
           f"&symbol={symbol}&apikey={api_key}")
    return fetch_json(url)


def av_search(term: str, api_key: str) -> dict:
    """Search symbols via Alpha Vantage."""
    encoded = urllib.request.quote(term)
    url = (f"{ALPHA_VANTAGE_BASE}?function=SYMBOL_SEARCH"
           f"&keywords={encoded}&apikey={api_key}")
    return fetch_json(url)


def yahoo_chart(symbol: str) -> dict:
    """Fetch 1-month daily chart from Yahoo Finance (no key required)."""
    url = f"{YAHOO_CHART_BASE}/{symbol}?range=1mo&interval=1d"
    return fetch_json(url)


# ── Data Extraction ──────────────────────────────────────────────────────────

def extract_closes_av(daily_data: dict) -> list[float]:
    """Extract closing prices from Alpha Vantage daily series (newest first)."""
    ts = daily_data.get("Time Series (Daily)", {})
    if not ts:
        return []
    closes = []
    for date_str in sorted(ts.keys(), reverse=True):
        try:
            closes.append(float(ts[date_str]["4. close"]))
        except (KeyError, ValueError):
            continue
    return closes


def extract_volumes_av(daily_data: dict) -> list[float]:
    """Extract volumes from Alpha Vantage daily series (newest first)."""
    ts = daily_data.get("Time Series (Daily)", {})
    if not ts:
        return []
    volumes = []
    for date_str in sorted(ts.keys(), reverse=True):
        try:
            volumes.append(float(ts[date_str]["5. volume"]))
        except (KeyError, ValueError):
            continue
    return volumes


def extract_closes_yahoo(chart_data: dict) -> list[float]:
    """Extract closing prices from Yahoo chart response (oldest first, reversed)."""
    try:
        result = chart_data["chart"]["result"][0]
        closes = result["indicators"]["quote"][0]["close"]
        # Filter None values and reverse to newest-first
        return [c for c in reversed(closes) if c is not None]
    except (KeyError, IndexError, TypeError):
        return []


def extract_volumes_yahoo(chart_data: dict) -> list[float]:
    """Extract volumes from Yahoo chart response (oldest first, reversed)."""
    try:
        result = chart_data["chart"]["result"][0]
        volumes = result["indicators"]["quote"][0]["volume"]
        return [v for v in reversed(volumes) if v is not None]
    except (KeyError, IndexError, TypeError):
        return []


def extract_quote_av(quote_data: dict) -> dict:
    """Extract key fields from Alpha Vantage global quote."""
    gq = quote_data.get("Global Quote", {})
    if not gq:
        return {}
    return {
        "symbol": gq.get("01. symbol", ""),
        "price": _safe_float(gq.get("05. price")),
        "change": _safe_float(gq.get("09. change")),
        "change_pct": gq.get("10. change percent", ""),
        "volume": _safe_float(gq.get("06. volume")),
        "prev_close": _safe_float(gq.get("08. previous close")),
    }


def _safe_float(val) -> float:
    """Convert value to float safely, returning 0.0 on failure."""
    try:
        return float(str(val).rstrip("%"))
    except (ValueError, TypeError):
        return 0.0


# ── Quant Indicators (pure stdlib) ───────────────────────────────────────────

def sma(prices: list[float], period: int) -> float | None:
    """Simple Moving Average over the most recent `period` prices."""
    if len(prices) < period:
        return None
    return sum(prices[:period]) / period


def ema(prices: list[float], period: int) -> float | None:
    """Exponential Moving Average — prices should be newest-first."""
    if len(prices) < period:
        return None
    # Reverse to oldest-first for iterative calculation
    ordered = list(reversed(prices[:max(period * 2, len(prices))]))
    k = 2.0 / (period + 1)
    ema_val = sum(ordered[:period]) / period  # seed with SMA
    for p in ordered[period:]:
        ema_val = p * k + ema_val * (1 - k)
    return ema_val


def rsi(prices: list[float], period: int = 14) -> float | None:
    """Relative Strength Index (Wilder's smoothing). Prices newest-first."""
    if len(prices) < period + 1:
        return None
    # Compute daily changes oldest-first
    ordered = list(reversed(prices[:period + 1]))
    gains = []
    losses = []
    for i in range(1, len(ordered)):
        delta = ordered[i] - ordered[i - 1]
        gains.append(delta if delta > 0 else 0.0)
        losses.append(-delta if delta < 0 else 0.0)

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def macd_signal(prices: list[float]) -> dict:
    """Simplified MACD: 12-day EMA minus 26-day EMA."""
    ema12 = ema(prices, 12)
    ema26 = ema(prices, 26)
    if ema12 is None or ema26 is None:
        return {"macd": None, "signal": "insufficient data"}
    macd_val = ema12 - ema26
    direction = "bullish" if macd_val > 0 else "bearish"
    return {"macd": round(macd_val, 4), "signal": direction}


def volatility(prices: list[float], period: int = 20) -> float | None:
    """Annualized daily return volatility (std dev of log returns)."""
    if len(prices) < period + 1:
        return None
    ordered = list(reversed(prices[:period + 1]))
    returns = []
    for i in range(1, len(ordered)):
        if ordered[i - 1] > 0 and ordered[i] > 0:
            returns.append(math.log(ordered[i] / ordered[i - 1]))
    if len(returns) < 2:
        return None
    mean_r = sum(returns) / len(returns)
    variance = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
    daily_vol = math.sqrt(variance)
    return round(daily_vol * math.sqrt(252) * 100, 2)  # annualized %


def volume_analysis(volumes: list[float]) -> dict:
    """Compare recent volume to 20-day average."""
    if not volumes:
        return {"recent": 0, "avg_20d": 0, "ratio": 0}
    recent = volumes[0]
    window = volumes[:20]
    avg = sum(window) / len(window) if window else 0
    ratio = round(recent / avg, 2) if avg > 0 else 0
    return {"recent": recent, "avg_20d": round(avg, 0), "ratio": ratio}


# ── Ticker Analysis ──────────────────────────────────────────────────────────

def fetch_ticker_data(symbol: str) -> dict:
    """Fetch price data for a symbol, trying Alpha Vantage then Yahoo fallback."""
    symbol = symbol.upper().strip()
    api_key = os.environ.get("ALPHA_VANTAGE_KEY", "")

    closes = []
    volumes = []
    quote_info = {}
    source = "none"

    # Try Alpha Vantage first
    if api_key:
        log(AGENT, f"Fetching {symbol} via Alpha Vantage")
        daily = av_daily(symbol, api_key)
        quote_raw = av_quote(symbol, api_key)

        closes = extract_closes_av(daily)
        volumes = extract_volumes_av(daily)
        quote_info = extract_quote_av(quote_raw)

        if closes:
            source = "Alpha Vantage"

    # Fallback to Yahoo Finance
    if not closes:
        log(AGENT, f"Fetching {symbol} via Yahoo Finance (fallback)")
        chart = yahoo_chart(symbol)

        if "error" not in chart:
            closes = extract_closes_yahoo(chart)
            volumes = extract_volumes_yahoo(chart)
            # Build quote_info from chart data
            if closes:
                quote_info = {
                    "symbol": symbol,
                    "price": closes[0],
                    "change": round(closes[0] - closes[1], 2) if len(closes) > 1 else 0,
                    "change_pct": (
                        f"{((closes[0] - closes[1]) / closes[1] * 100):.2f}%"
                        if len(closes) > 1 and closes[1] != 0 else "N/A"
                    ),
                    "volume": volumes[0] if volumes else 0,
                    "prev_close": closes[1] if len(closes) > 1 else 0,
                }
                source = "Yahoo Finance"

    return {
        "symbol": symbol,
        "source": source,
        "quote": quote_info,
        "closes": closes,
        "volumes": volumes,
    }


def compute_indicators(data: dict) -> dict:
    """Run all quant indicators on fetched ticker data."""
    closes = data.get("closes", [])
    volumes = data.get("volumes", [])

    return {
        "sma_10": round(sma(closes, 10), 2) if sma(closes, 10) is not None else None,
        "sma_50": round(sma(closes, 50), 2) if sma(closes, 50) is not None else None,
        "rsi_14": round(rsi(closes, 14), 2) if rsi(closes, 14) is not None else None,
        "macd": macd_signal(closes),
        "volatility_pct": volatility(closes),
        "volume": volume_analysis(volumes),
        "sma_crossover": _sma_crossover_label(closes),
    }


def _sma_crossover_label(closes: list[float]) -> str:
    """Determine SMA crossover state."""
    sma10 = sma(closes, 10)
    sma50 = sma(closes, 50)
    if sma10 is None or sma50 is None:
        return "insufficient data"
    if sma10 > sma50:
        return "bullish (10 > 50)"
    return "bearish (10 < 50)"


def build_analysis_text(data: dict, indicators: dict) -> str:
    """Build raw analysis text for a single ticker."""
    q = data.get("quote", {})
    symbol = data.get("symbol", "???")
    source = data.get("source", "unknown")

    lines = [
        f"## Ticker: {symbol}",
        f"Data source: {source}",
        "",
        "### Quote",
        f"- Price: ${q.get('price', 'N/A')}",
        f"- Change: {q.get('change', 'N/A')} ({q.get('change_pct', 'N/A')})",
        f"- Volume: {q.get('volume', 'N/A'):,.0f}" if isinstance(q.get('volume'), (int, float)) else f"- Volume: {q.get('volume', 'N/A')}",
        f"- Prev Close: ${q.get('prev_close', 'N/A')}",
        "",
        "### Indicators",
        f"- SMA(10): {indicators.get('sma_10', 'N/A')}",
        f"- SMA(50): {indicators.get('sma_50', 'N/A')}",
        f"- SMA Crossover: {indicators.get('sma_crossover', 'N/A')}",
        f"- RSI(14): {indicators.get('rsi_14', 'N/A')}",
        f"- MACD: {indicators.get('macd', {}).get('macd', 'N/A')} ({indicators.get('macd', {}).get('signal', 'N/A')})",
        f"- Volatility (ann.): {indicators.get('volatility_pct', 'N/A')}%",
        f"- Volume vs 20d avg: {indicators.get('volume', {}).get('ratio', 'N/A')}x",
    ]
    return "\n".join(lines)


# ── Command Handlers ─────────────────────────────────────────────────────────

def handle_analyze(ticker: str) -> str:
    """Full analysis of a single ticker."""
    log(AGENT, f"Analyzing: {ticker}")
    data = fetch_ticker_data(ticker)

    if data["source"] == "none":
        return (f"## {ticker}\n\n"
                f"Could not fetch data for **{ticker}**. "
                f"The runes are unclear — verify the symbol and try again.")

    indicators = compute_indicators(data)
    return build_analysis_text(data, indicators)


def handle_compare(ticker1: str, ticker2: str) -> str:
    """Side-by-side comparison of two tickers."""
    log(AGENT, f"Comparing: {ticker1} vs {ticker2}")

    data1 = fetch_ticker_data(ticker1)
    data2 = fetch_ticker_data(ticker2)

    parts = []
    for data in [data1, data2]:
        if data["source"] == "none":
            parts.append(f"## {data['symbol']}\n\nNo data available.")
        else:
            indicators = compute_indicators(data)
            parts.append(build_analysis_text(data, indicators))

    return "\n\n---\n\n".join(parts)


def handle_market() -> str:
    """Overview of major market indices."""
    log(AGENT, "Market overview: SPY, QQQ, DIA")
    parts = []
    for idx in MARKET_INDICES:
        data = fetch_ticker_data(idx)
        if data["source"] == "none":
            parts.append(f"**{idx}:** data unavailable")
        else:
            indicators = compute_indicators(data)
            parts.append(build_analysis_text(data, indicators))
    return "\n\n---\n\n".join(parts)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    raw_args = os.environ.get("QUERY_ARGS", "").strip()
    issue_number = int(os.environ.get("ISSUE_NUMBER", "0"))

    # Parse command
    parts = raw_args.split()
    command = "analyze"
    tickers = []

    if not parts:
        command = "market"
    elif parts[0].lower() == "compare" and len(parts) >= 3:
        command = "compare"
        tickers = [parts[1].upper(), parts[2].upper()]
    elif parts[0].lower() == "market":
        command = "market"
    else:
        command = "analyze"
        tickers = [parts[0].upper()]

    # Fetch and compute
    if command == "compare":
        raw_data = handle_compare(tickers[0], tickers[1])
    elif command == "market":
        raw_data = handle_market()
    else:
        raw_data = handle_analyze(tickers[0])

    # Pass through LLM for wizard-themed commentary
    try:
        system_prompt = read_prompt("stock-quant")
        ticker_label = ", ".join(tickers) if tickers else "Market Overview"
        user_message = (
            f"Command: {command}\n"
            f"Ticker(s): {ticker_label}\n"
            f"Date: {today()}\n\n"
            f"Raw data and indicators:\n{raw_data}\n\n"
            f"Transform this into a Wall Street Wizard analysis using the six-section format. "
            f"Keep all numbers accurate — embellish the narrative, not the data."
        )
        response = call_llm(system_prompt, user_message, max_tokens=2000)
    except Exception as e:
        log(AGENT, f"LLM commentary failed: {e}, using raw data")
        response = (
            f"{raw_data}\n\n"
            f"*This enchantment is for entertainment and educational purposes only. "
            f"Not financial advice. The Wizard assumes no liability for trades made "
            f"under the influence of magic.*\n\n"
            f"— *The Wall Street Wizard has spoken.*"
        )

    # Post to issue
    if issue_number > 0:
        gh_post_comment(issue_number, response)

    # Archive to memory
    archive_dir = MEMORY_DIR / "stocks"
    archive_dir.mkdir(parents=True, exist_ok=True)
    ticker_slug = "-".join(tickers).lower() if tickers else "market"
    archive_file = archive_dir / f"{today()}-{command}-{ticker_slug}.md"
    with open(archive_file, "a") as f:
        ts = datetime.now(timezone.utc).strftime("%H:%M UTC")
        f.write(f"\n---\n### {ts} — {command} {' '.join(tickers)}\n\n{raw_data}\n")

    update_stats("stock_analyses")
    award_xp(15)

    print(response)


if __name__ == "__main__":
    main()
