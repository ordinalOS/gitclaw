#!/usr/bin/env python3
"""News scraper agent that fetches and analyzes news articles."""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib import request, parse, error

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from common import (
    call_llm,
    update_agent_state,
    load_state,
    append_to_memory,
    format_timestamp,
)


def fetch_news(query: str, days_back: int = 3) -> list:
    """Fetch news articles from NewsAPI."""
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        print("❌ NEWS_API_KEY not set")
        return []

    # Calculate date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days_back)
    from_date = start_date.strftime("%Y-%m-%d")
    to_date = end_date.strftime("%Y-%m-%d")

    # Build URL with date filters
    params = {
        "q": query,
        "from": from_date,
        "to": to_date,
        "sortBy": "publishedAt",
        "language": "en",
        "pageSize": 10,
        "apiKey": api_key,
    }
    url = f"https://newsapi.org/v2/everything?{parse.urlencode(params)}"

    try:
        req = request.Request(url, headers={"User-Agent": "GitClaw/1.0"})
        with request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            
            # Validate response structure
            if not isinstance(data, dict):
                print("❌ Invalid API response: expected dictionary")
                return []
            
            if data.get("status") != "ok":
                error_msg = data.get("message", "Unknown error")
                print(f"❌ API error: {error_msg}")
                return []
            
            articles = data.get("articles")
            if not isinstance(articles, list):
                print("❌ Invalid API response: articles not found or not a list")
                return []
            
            if not articles:
                print(f"ℹ️ No articles found for query: {query}")
                return []
            
            # Validate and clean articles
            valid_articles = []
            for article in articles:
                if not isinstance(article, dict):
                    continue
                
                # Ensure required fields exist
                if not all(key in article for key in ["title", "url"]):
                    continue
                
                # Add article with safe field access
                valid_articles.append({
                    "title": article.get("title", "Untitled"),
                    "description": article.get("description", ""),
                    "url": article.get("url", ""),
                    "source": article.get("source", {}).get("name", "Unknown"),
                    "publishedAt": article.get("publishedAt", ""),
                })
            
            print(f"✅ Fetched {len(valid_articles)} valid articles (from {len(articles)} total)")
            return valid_articles
            
    except error.HTTPError as e:
        print(f"❌ HTTP error fetching news: {e.code} {e.reason}")
        return []
    except error.URLError as e:
        print(f"❌ Network error fetching news: {e.reason}")
        return []
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON response from API: {e}")
        return []
    except Exception as e:
        print(f"❌ Unexpected error fetching news: {e}")
        return []


def analyze_news(articles: list) -> dict:
    """Analyze news articles using LLM."""
    if not articles:
        return {
            "summary": "No articles to analyze.",
            "key_topics": [],
            "sentiment": "neutral",
            "notable_stories": [],
        }

    # Format articles for analysis
    articles_text = "\n\n".join(
        [
            f"**{a['title']}**\n{a['description']}\nSource: {a['source']} | {a['publishedAt']}"
            for a in articles[:10]  # Limit to 10 for token efficiency
        ]
    )

    prompt = f"""Analyze these recent news articles and provide:
1. A concise summary of the main themes
2. Key topics (max 5, as array)
3. Overall sentiment (positive/negative/neutral)
4. 2-3 most notable stories with brief explanations

Articles:
{articles_text}

Respond in JSON format:
{{
  "summary": "brief overview",
  "key_topics": ["topic1", "topic2"],
  "sentiment": "positive/negative/neutral",
  "notable_stories": [
    {{"title": "...", "why": "..."}} 
  ]
}}"""

    try:
        response = call_llm(prompt, max_tokens=800, temperature=0.3)
        analysis = json.loads(response)
        return analysis
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse LLM response as JSON: {e}")
        print(f"Raw response: {response[:200]}...")
        return {
            "summary": "Analysis failed due to parsing error.",
            "key_topics": [],
            "sentiment": "neutral",
            "notable_stories": [],
        }
    except Exception as e:
        print(f"❌ Error analyzing news: {e}")
        return {
            "summary": "Analysis failed due to unexpected error.",
            "key_topics": [],
            "sentiment": "neutral",
            "notable_stories": [],
        }


def format_markdown_report(query: str, articles: list, analysis: dict) -> str:
    """Format analysis as markdown report."""
    report = f"""# News Analysis: {query}

**Generated:** {format_timestamp()}
**Articles Analyzed:** {len(articles)}

## Summary
{analysis['summary']}

## Key Topics
{', '.join(analysis['key_topics']) if analysis['key_topics'] else 'None identified'}

## Sentiment
{analysis['sentiment'].title()}

## Notable Stories
"""

    for story in analysis.get("notable_stories", []):
        report += f"\n### {story.get('title', 'Untitled')}\n"
        report += f"{story.get('why', 'No explanation provided')}\n"

    report += "\n## Recent Articles\n"
    for article in articles[:5]:
        report += f"\n- [{article['title']}]({article['url']})\n"
        report += f"  *{article['source']} | {article['publishedAt']}*\n"

    return report


def main():
    """Main news scraper workflow."""
    query = os.getenv("NEWS_QUERY", "technology AI")
    days_back = int(os.getenv("NEWS_DAYS_BACK", "3"))

    print(f"🔍 Scraping news for: {query} (last {days_back} days)")

    # Fetch news
    articles = fetch_news(query, days_back)
    if not articles:
        print("❌ No articles found")
        sys.exit(1)

    # Analyze news
    print("🧠 Analyzing articles...")
    analysis = analyze_news(articles)

    # Format report
    report = format_markdown_report(query, articles, analysis)

    # Save to memory
    timestamp = format_timestamp()
    memory_entry = {
        "timestamp": timestamp,
        "query": query,
        "articles_count": len(articles),
        "analysis": analysis,
        "report": report,
    }
    append_to_memory("news_scrapes", memory_entry)

    # Update state
    update_agent_state("news_scrapes")

    # Output report
    print("\n" + "=" * 60)
    print(report)
    print("=" * 60)

    print(f"\n✅ News analysis complete for: {query}")


if __name__ == "__main__":
    main()
