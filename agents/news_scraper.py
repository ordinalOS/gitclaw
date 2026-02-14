#!/usr/bin/env python3
"""
News Ninja — Stealthy news intelligence agent.
Fetches headlines from free news APIs, analyzes via LLM, delivers with ninja flair.
Triggered by /news command or daily schedule.
"""

import json
import os
import urllib.request
import urllib.parse
from datetime import datetime, timezone

from common import (
    MEMORY_DIR, award_xp, call_llm, gh_post_comment,
    log, read_prompt, today, update_stats,
)

# ── News API Endpoints ──────────────────────────────────────────────────────

GNEWS_API = "https://gnews.io/api/v4/search"
NEWSDATA_API = "https://newsdata.io/api/1/news"
HN_ALGOLIA_API = "https://hn.algolia.com/api/v1/search"

# ── Topic Presets ────────────────────────────────────────────────────────────

TOPIC_PRESETS = {
    "markets": "stock market finance economy earnings",
    "tech": "technology software AI startup programming",
    "crypto": "cryptocurrency bitcoin ethereum solana blockchain",
}


# ── API Fetchers ─────────────────────────────────────────────────────────────

def fetch_json(url: str, timeout: int = 15) -> dict:
    """Generic JSON fetch with error handling."""
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "GitClaw-NewsNinja/1.0")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def fetch_gnews(query: str) -> list[dict]:
    """Fetch headlines from GNews API (primary source)."""
    api_key = os.environ.get("GNEWS_API_KEY", "")
    if not api_key:
        return []

    encoded_q = urllib.parse.quote(query)
    url = f"{GNEWS_API}?q={encoded_q}&lang=en&max=10&apikey={api_key}"
    data = fetch_json(url)

    if "error" in data or "articles" not in data:
        log("News Ninja", f"GNews fetch failed: {data.get('error', 'no articles')}")
        return []

    headlines = []
    for article in data.get("articles", []):
        headlines.append({
            "title": article.get("title", ""),
            "description": article.get("description", ""),
            "source": article.get("source", {}).get("name", "Unknown"),
            "url": article.get("url", ""),
            "published": article.get("publishedAt", ""),
        })

    return headlines


def fetch_newsdata(query: str) -> list[dict]:
    """Fetch headlines from NewsData.io (fallback)."""
    api_key = os.environ.get("NEWSDATA_API_KEY", "")
    if not api_key:
        return []

    encoded_q = urllib.parse.quote(query)
    url = f"{NEWSDATA_API}?apikey={api_key}&q={encoded_q}&language=en"
    data = fetch_json(url)

    if "error" in data or "results" not in data:
        log("News Ninja", f"NewsData fetch failed: {data.get('error', 'no results')}")
        return []

    headlines = []
    for article in data.get("results", []) or []:
        headlines.append({
            "title": article.get("title", ""),
            "description": article.get("description", ""),
            "source": article.get("source_id", "Unknown"),
            "url": article.get("link", ""),
            "published": article.get("pubDate", ""),
        })

    return headlines


def fetch_hackernews(query: str) -> list[dict]:
    """Fetch from Hacker News Algolia API (ultra-fallback, no key needed)."""
    encoded_q = urllib.parse.quote(query)
    url = f"{HN_ALGOLIA_API}?query={encoded_q}&tags=story&hitsPerPage=10"
    data = fetch_json(url)

    if "error" in data or "hits" not in data:
        log("News Ninja", f"HN Algolia fetch failed: {data.get('error', 'no hits')}")
        return []

    headlines = []
    for hit in data.get("hits", []):
        headlines.append({
            "title": hit.get("title", ""),
            "description": f"{hit.get('points', 0)} points, {hit.get('num_comments', 0)} comments",
            "source": "Hacker News",
            "url": hit.get("url", f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"),
            "published": hit.get("created_at", ""),
        })

    return headlines


# ── Core Logic ───────────────────────────────────────────────────────────────

def fetch_news(query: str) -> list[dict]:
    """Try each news source in priority order until one succeeds."""
    # Primary: GNews
    headlines = fetch_gnews(query)
    if headlines:
        log("News Ninja", f"Fetched {len(headlines)} headlines from GNews")
        return headlines

    # Fallback: NewsData.io
    headlines = fetch_newsdata(query)
    if headlines:
        log("News Ninja", f"Fetched {len(headlines)} headlines from NewsData.io")
        return headlines

    # Ultra-fallback: Hacker News Algolia
    headlines = fetch_hackernews(query)
    if headlines:
        log("News Ninja", f"Fetched {len(headlines)} headlines from Hacker News")
        return headlines

    log("News Ninja", "All news sources failed")
    return []


def format_headlines(headlines: list[dict]) -> str:
    """Format raw headline data into a readable string for the LLM."""
    if not headlines:
        return "No headlines available."

    lines = []
    for i, h in enumerate(headlines, 1):
        lines.append(
            f"{i}. [{h['source']}] {h['title']}\n"
            f"   {h['description']}\n"
            f"   Published: {h['published']}"
        )

    return "\n\n".join(lines)


def build_fallback_response(topic: str) -> str:
    """Emergency fallback when all APIs and LLM fail."""
    return (
        f"## News Ninja -- Recon Report: {topic}\n\n"
        f"The ninja's network of informants is temporarily offline. "
        f"All recon channels returned silence.\n\n"
        f"**Possible causes:**\n"
        f"- News API keys not configured (GNEWS_API_KEY / NEWSDATA_API_KEY)\n"
        f"- API rate limits reached\n"
        f"- Network disruption in the shadows\n\n"
        f"**TL;DR:** Even a ninja needs working comms. "
        f"Check your API keys and try again.\n\n"
        f"-- *The News Ninja retreats to sharpen its blades. Stay alert.*"
    )


def main():
    raw_args = os.environ.get("QUERY_ARGS", "").strip()
    issue_number = int(os.environ.get("ISSUE_NUMBER", "0"))

    # Resolve topic from presets or use raw query
    topic = TOPIC_PRESETS.get(raw_args.lower(), raw_args) if raw_args else "technology AI programming"
    display_topic = raw_args if raw_args else "tech (default)"

    log("News Ninja", f"Scouting news for: {display_topic}")

    # Fetch headlines
    headlines = fetch_news(topic)
    formatted = format_headlines(headlines)

    if not headlines:
        response = build_fallback_response(display_topic)
    else:
        # Pass through LLM for ninja-style analysis
        system_prompt = read_prompt("news-scraper")
        user_message = (
            f"Topic: {display_topic}\n"
            f"Date: {today()}\n\n"
            f"Raw headlines:\n{formatted}\n\n"
            f"Analyze these headlines and produce your News Ninja report. "
            f"Keep numbers and facts accurate — embellish the narrative, not the data."
        )

        try:
            response = call_llm(system_prompt, user_message, max_tokens=1500)
        except Exception as e:
            log("News Ninja", f"LLM analysis failed: {e}")
            # Deliver raw headlines with minimal formatting
            response = (
                f"## News Ninja -- Raw Intel Drop: {display_topic}\n\n"
                f"*The ninja's analytical mind is resting (LLM error), "
                f"but the raw intelligence is yours:*\n\n"
                f"{formatted}\n\n"
                f"-- *The News Ninja delivers unprocessed scrolls. Interpret wisely.*"
            )

    # Post to issue if provided
    if issue_number > 0:
        gh_post_comment(issue_number, response)

    # Archive to memory/news/
    archive_dir = MEMORY_DIR / "news"
    archive_dir.mkdir(parents=True, exist_ok=True)

    slug = display_topic.lower().replace(" ", "-")[:50]
    slug = "".join(c for c in slug if c.isalnum() or c == "-")
    archive_file = archive_dir / f"{today()}-{slug}.md"

    with open(archive_file, "a") as f:
        ts = datetime.now(timezone.utc).strftime("%H:%M UTC")
        f.write(
            f"\n---\n### {ts} -- {display_topic}\n\n"
            f"{response}\n"
        )

    update_stats("news_scrapes")
    award_xp(10)

    print(response)


if __name__ == "__main__":
    main()
