#!/usr/bin/env python3
"""
Pages Builder — Generates GitClaw's Bloomberg-terminal-style GitHub Pages site.
Reads all memory files, state, and config to produce a static HTML site in docs/.
No frameworks, no pip — pure stdlib HTML generation.
"""

import html
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from common import MEMORY_DIR, REPO_ROOT, load_state, log, today, update_stats, award_xp

DOCS_DIR = REPO_ROOT / "docs"
DATA_DIR = DOCS_DIR / "data"


# ── Data Loading ─────────────────────────────────────────────────────────────

def load_memory_files(category: str) -> list:
    """Load all .md files from a memory subdirectory, sorted newest first."""
    target_dir = MEMORY_DIR / category
    if not target_dir.is_dir():
        return []

    entries = []
    for f in sorted(target_dir.glob("*.md"), reverse=True):
        if f.name == ".gitkeep":
            continue
        try:
            content = f.read_text()
            # Parse date from filename (YYYY-MM-DD-slug.md or YYYY-MM-DD.md)
            date_match = re.match(r'(\d{4}-\d{2}-\d{2})', f.stem)
            entry_date = date_match.group(1) if date_match else "unknown"
            slug = f.stem[11:] if len(f.stem) > 10 else f.stem
            entries.append({
                "file": f.name,
                "date": entry_date,
                "slug": slug,
                "title": slug.replace("-", " ").title() if slug else entry_date,
                "content": content,
                "category": category,
            })
        except Exception:
            pass

    return entries


def load_json_files(category: str) -> list:
    """Load all .json files from a memory subdirectory."""
    target_dir = MEMORY_DIR / category
    if not target_dir.is_dir():
        return []

    entries = []
    for f in sorted(target_dir.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text())
            data["_file"] = f.name
            entries.append(data)
        except Exception:
            pass

    return entries


def load_agent_config() -> list:
    """Parse config/agents.yml manually (no PyYAML dependency)."""
    config_file = REPO_ROOT / "config" / "agents.yml"
    if not config_file.exists():
        return []

    agents = []
    current = {}
    content = config_file.read_text()

    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Top-level key (agent name or 'defaults')
        if not line.startswith(" ") and stripped.endswith(":"):
            if current and current.get("_key") not in ("agents", "defaults"):
                agents.append(current)
            current = {"_key": stripped.rstrip(":")}
            continue

        # Indented key:value
        kv_match = re.match(r'\s+(\w+):\s*"?([^"]*)"?\s*$', line)
        if kv_match and current:
            key, val = kv_match.group(1), kv_match.group(2).strip()
            if val.lower() == "true":
                val = True
            elif val.lower() == "false":
                val = False
            current[key] = val

    if current and current.get("_key") not in ("agents", "defaults"):
        agents.append(current)

    return agents


def get_recent_activity(limit: int = 50) -> list:
    """Build a chronological activity feed from all memory categories."""
    categories = [
        ("dreams", "🌙", "Dream"),
        ("lore", "📜", "Lore"),
        ("research", "🔍", "Research"),
        ("roasts", "🔥", "Roast"),
        ("fortunes", "🔮", "Fortune"),
        ("hn", "📰", "HN Digest"),
        ("news", "🥷", "News"),
        ("crypto", "🔮", "Crypto"),
        ("stocks", "🧙", "Stock"),
        ("proposals", "🏗️", "Proposal"),
        ("council", "⚖️", "Council"),
    ]

    activities = []
    for cat, emoji, label in categories:
        for entry in load_memory_files(cat):
            activities.append({
                "date": entry["date"],
                "emoji": emoji,
                "label": label,
                "title": entry["title"],
                "category": cat,
                "file": entry["file"],
            })
        # Also check JSON files (proposals, council)
        for entry in load_json_files(cat):
            date_str = entry.get("proposed_at", entry.get("date", ""))[:10]
            activities.append({
                "date": date_str or "unknown",
                "emoji": emoji,
                "label": label,
                "title": entry.get("title", entry.get("_file", "record")),
                "category": cat,
                "file": entry.get("_file", ""),
            })

    activities.sort(key=lambda x: x.get("date", ""), reverse=True)
    return activities[:limit]


# ── HTML Generation ──────────────────────────────────────────────────────────

def e(text) -> str:
    """HTML-escape text safely."""
    return html.escape(str(text)) if text else ""


def nav_html(active: str) -> str:
    """Generate the navigation bar."""
    pages = [
        ("index.html", "DASHBOARD"),
        ("memory.html", "MEMORY"),
        ("council.html", "COUNCIL"),
        ("agents.html", "AGENTS"),
        ("debug.html", "DEBUG"),
        ("blog/index.html", "BLOG"),
    ]
    links = []
    for href, label in pages:
        cls = ' class="active"' if label.lower() == active.lower() else ""
        links.append(f'<a href="{href}"{cls}>[{label}]</a>')
    return "  ".join(links)


def terminal_bar(state: dict) -> str:
    """Generate the top terminal status bar."""
    xp = state.get("xp", 0)
    level = state.get("level", "Unknown")
    persona = state.get("agent", {}).get("persona", "default")
    streak = state.get("streak", {}).get("current", 0)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    filled = min(10, int((xp % 50) / 5)) if xp < 10000 else 10
    bar = "█" * filled + "░" * (10 - filled)

    return (
        f'<div class="terminal-bar">'
        f'<span>GITCLAW TERMINAL v1.0 | {e(persona.upper())} | {now}</span>'
        f'<span>XP: {bar} {xp} | LEVEL: {e(level)} | STREAK: {streak}d</span>'
        f'</div>'
    )


def page_wrapper(title: str, active: str, state: dict, body: str) -> str:
    """Wrap page body in full HTML document."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="120">
    <title>GitClaw | {e(title)}</title>
    <link rel="stylesheet" href="{"" if "/" not in active else "../"}assets/style.css">
</head>
<body>
    {terminal_bar(state)}
    <nav class="nav">{nav_html(active)}</nav>
    <main class="main">
        {body}
    </main>
    <footer class="footer">
        <span>GitClaw Agent System | 100% GitHub Actions | Zero Infrastructure</span>
        <span id="clock"></span>
    </footer>
    <script src="{"" if "/" not in active else "../"}assets/app.js"></script>
</body>
</html>"""


def md_to_html(md: str) -> str:
    """Minimal markdown to HTML conversion (no external libs)."""
    lines = md.split("\n")
    out = []
    in_code = False
    in_list = False

    for line in lines:
        # Code blocks
        if line.strip().startswith("```"):
            if in_code:
                out.append("</code></pre>")
                in_code = False
            else:
                lang = line.strip()[3:].strip()
                out.append(f'<pre><code class="lang-{e(lang)}">')
                in_code = True
            continue
        if in_code:
            out.append(e(line))
            continue

        # Headers
        if line.startswith("### "):
            out.append(f"<h3>{e(line[4:])}</h3>")
            continue
        if line.startswith("## "):
            out.append(f"<h2>{e(line[3:])}</h2>")
            continue
        if line.startswith("# "):
            out.append(f"<h1>{e(line[2:])}</h1>")
            continue

        # Horizontal rule
        if line.strip() in ("---", "***", "___"):
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append("<hr>")
            continue

        # List items
        if re.match(r'^[-*]\s', line.strip()):
            if not in_list:
                out.append("<ul>")
                in_list = True
            item = re.sub(r'^[-*]\s', '', line.strip())
            out.append(f"<li>{inline_md(item)}</li>")
            continue
        elif in_list and not line.strip():
            out.append("</ul>")
            in_list = False

        # Paragraphs
        if line.strip():
            out.append(f"<p>{inline_md(line)}</p>")
        else:
            out.append("")

    if in_list:
        out.append("</ul>")
    if in_code:
        out.append("</code></pre>")

    return "\n".join(out)


def inline_md(text: str) -> str:
    """Convert inline markdown (bold, italic, code, links)."""
    text = e(text)
    # Bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # Italic
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'_(.+?)_', r'<em>\1</em>', text)
    # Inline code
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    return text


# ── Page Generators ──────────────────────────────────────────────────────────

def generate_dashboard(state: dict, activity: list) -> str:
    """Generate the main dashboard page."""
    stats = state.get("stats", {})
    achievements = state.get("achievements", [])

    # Stats table
    stats_rows = ""
    for key, val in sorted(stats.items()):
        label = key.replace("_", " ").title()
        stats_rows += f"<tr><td>{e(label)}</td><td class='num'>{val}</td></tr>\n"

    # Activity feed
    activity_rows = ""
    for act in activity[:15]:
        activity_rows += (
            f"<tr>"
            f"<td class='dim'>{e(act['date'])}</td>"
            f"<td>{act['emoji']}</td>"
            f"<td>{e(act['label'])}</td>"
            f"<td>{e(act['title'][:60])}</td>"
            f"</tr>\n"
        )

    # Achievements
    ach_html = ""
    if achievements:
        ach_html = " ".join(f'<span class="badge">{e(a)}</span>' for a in achievements)
    else:
        ach_html = '<span class="dim">No achievements yet</span>'

    body = f"""
    <div class="grid-3">
        <div class="panel">
            <h2 class="panel-title">AGENT STATS</h2>
            <table class="data-table">
                <thead><tr><th>Metric</th><th>Value</th></tr></thead>
                <tbody>{stats_rows}</tbody>
            </table>
        </div>
        <div class="panel">
            <h2 class="panel-title">ACTIVITY FEED</h2>
            <table class="data-table feed">
                <thead><tr><th>Date</th><th></th><th>Agent</th><th>Action</th></tr></thead>
                <tbody>{activity_rows}</tbody>
            </table>
        </div>
        <div class="panel">
            <h2 class="panel-title">ACHIEVEMENTS</h2>
            <div class="achievements">{ach_html}</div>
            <h2 class="panel-title" style="margin-top:1rem">AGENT INFO</h2>
            <table class="data-table">
                <tr><td>Name</td><td>{e(state.get('agent', {}).get('name', 'GitClaw'))}</td></tr>
                <tr><td>Persona</td><td>{e(state.get('agent', {}).get('persona', 'default'))}</td></tr>
                <tr><td>Born</td><td>{e(state.get('agent', {}).get('born', 'unknown'))}</td></tr>
                <tr><td>Version</td><td>{e(state.get('agent', {}).get('version', '1.0.0'))}</td></tr>
                <tr><td>Last Active</td><td>{e(state.get('last_active', 'unknown'))}</td></tr>
            </table>
        </div>
    </div>"""

    return page_wrapper("Dashboard", "dashboard", state, body)


def generate_memory_browser(state: dict) -> str:
    """Generate the memory browser page with tabs."""
    categories = [
        ("dreams", "Dreams", "🌙"),
        ("lore", "Lore", "📜"),
        ("research", "Research", "🔍"),
        ("roasts", "Roasts", "🔥"),
        ("fortunes", "Fortunes", "🔮"),
        ("hn", "HN", "📰"),
        ("news", "News", "🥷"),
        ("crypto", "Crypto", "🔮"),
        ("stocks", "Stocks", "🧙"),
    ]

    tabs_html = ""
    panels_html = ""

    for i, (cat, label, emoji) in enumerate(categories):
        entries = load_memory_files(cat)
        active = " active" if i == 0 else ""

        tabs_html += f'<button class="tab-btn{active}" data-tab="{cat}">{emoji} {label} ({len(entries)})</button>\n'

        entries_html = ""
        if entries:
            for entry in entries[:20]:
                content_html = md_to_html(entry["content"][:2000])
                entries_html += f"""
                <div class="memory-entry">
                    <div class="entry-header" onclick="toggleEntry(this)">
                        <span class="dim">{e(entry['date'])}</span>
                        <span>{e(entry['title'][:80])}</span>
                        <span class="expand-icon">+</span>
                    </div>
                    <div class="entry-body" style="display:none">
                        {content_html}
                    </div>
                </div>"""
        else:
            entries_html = '<div class="empty">No entries yet</div>'

        panels_html += f'<div class="tab-panel{active}" id="tab-{cat}">{entries_html}</div>\n'

    body = f"""
    <div class="panel full-width">
        <h2 class="panel-title">MEMORY BROWSER</h2>
        <div class="tabs">{tabs_html}</div>
        <div class="tab-content">{panels_html}</div>
    </div>"""

    return page_wrapper("Memory", "memory", state, body)


def generate_council_log(state: dict) -> str:
    """Generate the council voting log page."""
    proposals = load_json_files("proposals")
    council_entries = load_memory_files("council")

    rows = ""
    if proposals:
        for prop in proposals:
            title = prop.get("title", "Untitled")
            pr_num = prop.get("pr_number", "?")
            date = prop.get("proposed_at", "")[:10]
            status = prop.get("status", "proposed")
            scores = prop.get("alignment_scores", {})
            goals = prop.get("goals", [])

            score_bar = ""
            for axis, score in scores.items():
                filled = int(float(score) * 10)
                bar = "█" * filled + "░" * (10 - filled)
                score_bar += f"<div class='score-row'><span class='dim'>{e(axis[:4])}</span> {bar} {score}</div>"

            status_cls = {"proposed": "amber", "approved": "green", "rejected": "red"}.get(status, "dim")

            rows += f"""
            <div class="council-entry">
                <div class="entry-header" onclick="toggleEntry(this)">
                    <span class="dim">PR #{e(str(pr_num))}</span>
                    <span>{e(title[:60])}</span>
                    <span class="dim">{e(date)}</span>
                    <span class="{status_cls}">{e(status.upper())}</span>
                    <span class="expand-icon">+</span>
                </div>
                <div class="entry-body" style="display:none">
                    <div class="score-grid">{score_bar}</div>
                    <div class="goals">Goals: {', '.join(e(g) for g in goals)}</div>
                </div>
            </div>"""
    else:
        rows = '<div class="empty">No proposals yet. The Architect is warming up.</div>'

    # Council reviews
    council_html = ""
    if council_entries:
        for entry in council_entries[:20]:
            council_html += f"""
            <div class="memory-entry">
                <div class="entry-header" onclick="toggleEntry(this)">
                    <span class="dim">{e(entry['date'])}</span>
                    <span>{e(entry['title'][:60])}</span>
                    <span class="expand-icon">+</span>
                </div>
                <div class="entry-body" style="display:none">
                    {md_to_html(entry['content'][:2000])}
                </div>
            </div>"""

    body = f"""
    <div class="panel full-width">
        <h2 class="panel-title">ARCHITECT PROPOSALS</h2>
        {rows}
    </div>
    <div class="panel full-width">
        <h2 class="panel-title">COUNCIL REVIEWS</h2>
        {council_html or '<div class="empty">No council reviews yet.</div>'}
    </div>"""

    return page_wrapper("Council", "council", state, body)


def generate_agents_page(state: dict) -> str:
    """Generate the agent status grid."""
    agents = load_agent_config()

    cards = ""
    for agent in agents:
        name = agent.get("name", agent.get("_key", "Unknown"))
        emoji = agent.get("emoji", "🤖")
        desc = agent.get("description", "")
        enabled = agent.get("enabled", False)
        trigger = agent.get("trigger", "")
        schedule = agent.get("schedule", "")
        command = agent.get("command", "")
        plugin = agent.get("plugin", "")

        status_cls = "green" if enabled else "dim"
        status_txt = "ACTIVE" if enabled else "DISABLED"
        plugin_badge = f'<span class="badge">{e(plugin)}</span>' if plugin else ""

        trigger_info = e(trigger)
        if schedule:
            trigger_info += f" ({e(schedule)})"
        if command:
            trigger_info += f" | {e(command)}"

        cards += f"""
        <div class="agent-card {"" if enabled else "disabled"}">
            <div class="agent-header">
                <span class="agent-emoji">{emoji}</span>
                <span class="agent-name">{e(name)}</span>
                {plugin_badge}
            </div>
            <div class="agent-desc">{e(desc)}</div>
            <div class="agent-meta">
                <span class="{status_cls}">{status_txt}</span>
                <span class="dim">{trigger_info}</span>
            </div>
        </div>"""

    body = f"""
    <div class="panel full-width">
        <h2 class="panel-title">AGENT STATUS</h2>
        <div class="agent-grid">{cards}</div>
    </div>"""

    return page_wrapper("Agents", "agents", state, body)


def generate_debug_page(state: dict) -> str:
    """Generate the debug console page."""
    state_json = json.dumps(state, indent=2, default=str)

    # Get recent commits
    commits_html = ""
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-20"],
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=10,
        )
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                commits_html += f"<div class='commit-line'>{e(line)}</div>\n"
    except Exception:
        commits_html = '<div class="dim">Could not load git log</div>'

    body = f"""
    <div class="grid-2">
        <div class="panel">
            <h2 class="panel-title">STATE.JSON</h2>
            <pre class="json-view"><code>{e(state_json)}</code></pre>
        </div>
        <div class="panel">
            <h2 class="panel-title">RECENT COMMITS</h2>
            <div class="commit-log">{commits_html}</div>
            <h2 class="panel-title" style="margin-top:1rem">MEMORY INVENTORY</h2>
            <table class="data-table">
                <thead><tr><th>Category</th><th>Files</th></tr></thead>
                <tbody>
                    {generate_memory_inventory()}
                </tbody>
            </table>
        </div>
    </div>"""

    return page_wrapper("Debug", "debug", state, body)


def generate_memory_inventory() -> str:
    """Count files in each memory subdirectory."""
    rows = ""
    if MEMORY_DIR.is_dir():
        for d in sorted(MEMORY_DIR.iterdir()):
            if d.is_dir():
                count = sum(1 for f in d.rglob("*") if f.is_file() and f.name != ".gitkeep")
                rows += f"<tr><td>{e(d.name)}</td><td class='num'>{count}</td></tr>\n"
    return rows


def generate_blog(state: dict) -> str:
    """Generate blog index from lore and research entries."""
    lore = load_memory_files("lore")
    research = load_memory_files("research")
    dreams = load_memory_files("dreams")

    posts = []
    for entry in lore:
        entry["type"] = "📜 Lore"
        posts.append(entry)
    for entry in research:
        entry["type"] = "🔍 Research"
        posts.append(entry)
    for entry in dreams:
        entry["type"] = "🌙 Dream"
        posts.append(entry)

    posts.sort(key=lambda x: x.get("date", ""), reverse=True)

    posts_html = ""
    if posts:
        for post in posts[:30]:
            content_preview = post["content"][:300].replace("\n", " ")
            posts_html += f"""
            <div class="blog-post">
                <div class="entry-header" onclick="toggleEntry(this)">
                    <span class="dim">{e(post['date'])}</span>
                    <span class="badge">{e(post['type'])}</span>
                    <span>{e(post['title'][:80])}</span>
                    <span class="expand-icon">+</span>
                </div>
                <div class="entry-body" style="display:none">
                    {md_to_html(post['content'][:3000])}
                </div>
            </div>"""
    else:
        posts_html = '<div class="empty">No posts yet. Create lore, research, or dreams to populate the blog.</div>'

    body = f"""
    <div class="panel full-width">
        <h2 class="panel-title">AGENTIC WEBRING // BLOG</h2>
        <div class="webring-nav">
            <a href="../index.html">[DASHBOARD]</a>
            <a href="../memory.html">[MEMORY]</a>
            <a href="../council.html">[COUNCIL]</a>
            <span class="dim">// all nodes connected //</span>
        </div>
        {posts_html}
    </div>"""

    return page_wrapper("Blog", "blog", state, body)


# ── Site Builder ─────────────────────────────────────────────────────────────

def build_site():
    """Build the entire static site."""
    log("Pages", "Building GitClaw Pages...")

    state = load_state()
    activity = get_recent_activity()

    # Ensure directories
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "assets").mkdir(exist_ok=True)
    (DOCS_DIR / "data").mkdir(exist_ok=True)
    (DOCS_DIR / "blog").mkdir(exist_ok=True)

    # Generate pages
    pages = {
        "index.html": generate_dashboard(state, activity),
        "memory.html": generate_memory_browser(state),
        "council.html": generate_council_log(state),
        "agents.html": generate_agents_page(state),
        "debug.html": generate_debug_page(state),
        "blog/index.html": generate_blog(state),
    }

    for path, content in pages.items():
        out_file = DOCS_DIR / path
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(content)
        log("Pages", f"  Generated: {path}")

    # Write data files for JS consumption
    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / "state.json").write_text(json.dumps(state, indent=2, default=str))
    (DATA_DIR / "activity.json").write_text(json.dumps(activity[:50], indent=2, default=str))

    proposals = load_json_files("proposals")
    (DATA_DIR / "council.json").write_text(json.dumps(proposals, indent=2, default=str))

    agents = load_agent_config()
    (DATA_DIR / "agents.json").write_text(json.dumps(agents, indent=2, default=str))

    log("Pages", f"Site built: {len(pages)} pages, 4 data files")

    update_stats("pages_built")
    award_xp(5)


if __name__ == "__main__":
    build_site()
