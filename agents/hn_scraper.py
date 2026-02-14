#!/usr/bin/env python3
"""
HN Scraper — Hacker News analyst with hype scores and puns.
Triggered by /hn command or daily schedule.
"""

import json
import os
import urllib.request
from datetime import datetime, timezone

from common import (
    MEMORY_DIR, award_xp, call_llm, gh_post_comment,
    log, read_prompt, today, update_stats,
)

# ── HN API Endpoints ────────────────────────────────────────────────────────

HN_ALGOLIA_SEARCH = "https://hn.algolia.com/api/v1/search"
HN_ALGOLIA_RECENT = "https://hn.algolia.com/api/v1/search_by_date"
HN_FIREBASE_TOP = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_FIREBASE_ITEM = "https://hacker-news.firebaseio.com/v0/item/{}.json"


# ── API Helpers ──────────────────────────────────────────────────────────────

def fetch_json(url: str, timeout: int = 15) -> dict | list | None:
    """Fetch JSON from a URL with error handling."""
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "GitClaw-HN-Scraper/1.0")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        log("HN Scraper", f"Fetch failed for {url}: {e}")
        return None


def fetch_top_stories(limit: int = 15) -> list[dict]:
    """Fetch top stories from the HN Firebase API."""
    story_ids = fetch_json(HN_FIREBASE_TOP)
    if not story_ids:
        return []

    stories = []
    for story_id in story_ids[:limit]:
        item = fetch_json(HN_FIREBASE_ITEM.format(story_id))
        if item and item.get("type") == "story":
            stories.append({
                "title": item.get("title", "Untitled"),
                "url": item.get("url", ""),
                "points": item.get("score", 0),
                "author": item.get("by", "unknown"),
                "comments": item.get("descendants", 0),
                "id": item.get("id", 0),
            })
    return stories


def search_stories(term: str, limit: int = 15) -> list[dict]:
    """Search HN stories via the Algolia API."""
    encoded_term = urllib.request.quote(term)
    url = (
        f"{HN_ALGOLIA_SEARCH}?query={encoded_term}"
        f"&tags=story&numericFilters=points>10&hitsPerPage={limit}"
    )
    data = fetch_json(url)
    if not data or "hits" not in data:
        return []

    return [
        {
            "title": hit.get("title", "Untitled"),
            "url": hit.get("url", ""),
            "points": hit.get("points", 0),
            "author": hit.get("author", "unknown"),
            "comments": hit.get("num_comments", 0),
            "id": hit.get("objectID", "0"),
        }
        for hit in data["hits"]
    ]


def fetch_trending(limit: int = 15) -> list[dict]:
    """Fetch recent high-engagement stories via the Algolia API."""
    url = (
        f"{HN_ALGOLIA_RECENT}?tags=story"
        f"&numericFilters=points>10&hitsPerPage={limit}"
    )
    data = fetch_json(url)
    if not data or "hits" not in data:
        return []

    return [
        {
            "title": hit.get("title", "Untitled"),
            "url": hit.get("url", ""),
            "points": hit.get("points", 0),
            "author": hit.get("author", "unknown"),
            "comments": hit.get("num_comments", 0),
            "id": hit.get("objectID", "0"),
        }
        for hit in data["hits"]
    ]


# ── Formatting ───────────────────────────────────────────────────────────────

def format_stories(stories: list[dict], mode: str, search_term: str = "") -> str:
    """Format fetched stories into a readable summary for the LLM."""
    if not stories:
        return f"No stories found (mode: {mode}, term: {search_term})."

    header = {
        "top": "HN Front Page — Top Stories",
        "search": f"HN Search Results — \"{search_term}\"",
        "trending": "HN Trending — Recent High-Engagement Stories",
    }.get(mode, "HN Stories")

    lines = [f"## {header}", f"_Fetched: {today()}_\n"]
    for i, story in enumerate(stories, 1):
        hn_link = f"https://news.ycombinator.com/item?id={story['id']}"
        lines.append(
            f"{i}. **{story['title']}**\n"
            f"   - Points: {story['points']} | "
            f"Comments: {story['comments']} | "
            f"By: {story['author']}\n"
            f"   - HN: {hn_link}"
        )
        if story.get("url"):
            lines.append(f"   - Link: {story['url']}")
        lines.append("")

    return "\n".join(lines)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    raw_args = os.environ.get("QUERY_ARGS", "").strip()
    issue_number = int(os.environ.get("ISSUE_NUMBER", "0"))

    # Parse command: "search rust" -> mode="search", search_term="rust"
    parts = raw_args.split(None, 1)
    command = parts[0].lower() if parts else "top"
    search_term = parts[1] if len(parts) > 1 else ""

    # Normalize empty or "top" to top-stories mode
    if command in ("top", ""):
        mode = "top"
    elif command == "search" and search_term:
        mode = "search"
    elif command == "trending":
        mode = "trending"
    else:
        # Treat unknown single-word input as a search term
        mode = "search"
        search_term = raw_args

    log("HN Scraper", f"Mode: {mode}, term: '{search_term}'")

    # Fetch stories
    if mode == "top":
        stories = fetch_top_stories()
    elif mode == "search":
        stories = search_stories(search_term)
    else:
        stories = fetch_trending()

    raw_summary = format_stories(stories, mode, search_term)

    # Pass through LLM for entertaining commentary
    try:
        system_prompt = read_prompt("hn-scraper")
        user_message = (
            f"Query mode: {mode}\n"
            f"Search term: {search_term}\n"
            f"Date: {today()}\n\n"
            f"Here are the stories:\n\n{raw_summary}\n\n"
            f"Analyze these stories and produce your HN Hype Buster report. "
            f"Keep the actual story titles and point counts accurate — "
            f"embellish the commentary, not the data."
        )
        response = call_llm(system_prompt, user_message, max_tokens=1500)
    except Exception as e:
        log("HN Scraper", f"LLM call failed: {e}")
        response = (
            f"## 📰 HN Hype Buster — {today()}\n\n"
            f"My snark engine is temporarily offline (API error), "
            f"but here's the raw feed:\n\n"
            f"{raw_summary}\n\n"
            f"**TL;DR:** The front page exists. I'll have opinions later.\n\n"
            f"— 📰 *The HN Hype Buster | Running on fumes*"
        )

    # Post to issue if provided
    if issue_number > 0:
        gh_post_comment(issue_number, response)

    # Archive to memory/hn/
    archive_dir = MEMORY_DIR / "hn"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_file = archive_dir / f"{today()}-{mode}.md"
    with open(archive_file, "a") as f:
        ts = datetime.now(timezone.utc).strftime("%H:%M UTC")
        f.write(f"\n---\n### {ts} — {mode} {search_term}\n\n{response}\n")

    update_stats("hn_scrapes")
    award_xp(10)

    print(response)


if __name__ == "__main__":
    main()
