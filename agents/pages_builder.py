#!/usr/bin/env python3
"""
Pages Builder — Generates GitClaw's Apple HIG-style GitHub Pages site.
Reads all memory files, state, and config to produce a static HTML site in docs/.
No frameworks, no pip — pure stdlib HTML generation.
"""

import html
import json
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from common import MEMORY_DIR, REPO_ROOT, load_state, log, today, update_stats, award_xp

DOCS_DIR = REPO_ROOT / "docs"
DATA_DIR = DOCS_DIR / "data"

# XP level thresholds (mirrored from common.py)
XP_LEVELS = [
    (0, "Unawakened"), (50, "Novice"), (150, "Apprentice"), (300, "Journeyman"),
    (500, "Adept"), (800, "Expert"), (1200, "Master"), (1800, "Grandmaster"),
    (2500, "Legend"), (5000, "Mythic"), (10000, "Transcendent"),
]

# Map commit emojis to agent names for workflow run parsing
EMOJI_AGENTS = {
    "☕": "Morning Roast", "⚔️": "Quest Master", "🃏": "Code Jester",
    "🔍": "Fact Finder", "🎨": "Meme Machine", "📜": "Lore Keeper",
    "🌙": "Dream", "🔮": "Fortune", "🎉": "Hype Man",
    "🔥": "Roast", "📰": "HN Scraper", "🥷": "News Ninja",
    "📡": "Solana Monitor", "🌐": "Solana Query", "🔨": "Solana Builder",
    "📺": "Pages Builder", "💓": "Heartbeat", "🏗️": "Architect",
    "💅": "Karen", "📬": "Telegram", "📧": "Gmail",
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_xp_progress_pct(xp: int) -> int:
    """Calculate XP progress percentage toward the next level."""
    current_threshold = 0
    next_threshold = 50
    for threshold, _ in XP_LEVELS:
        if threshold <= xp:
            current_threshold = threshold
        else:
            next_threshold = threshold
            break
    if next_threshold == current_threshold:
        return 100
    progress = xp - current_threshold
    total = next_threshold - current_threshold
    pct = int((progress / total) * 100)
    return max(1, pct) if progress > 0 else 0


def get_repo_url() -> str:
    """Get the GitHub repository URL from env or git remote."""
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if repo:
        return f"https://github.com/{repo}"
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=5,
        )
        url = result.stdout.strip()
        if url.startswith("git@"):
            url = url.replace(":", "/").replace("git@", "https://")
        if url.endswith(".git"):
            url = url[:-4]
        return url
    except Exception:
        return "#"


def get_workflow_runs(limit: int = 15) -> list:
    """Parse recent agent commits from git log as a proxy for workflow runs."""
    try:
        # Try bot-authored commits first, fall back to all commits with 🧠 prefix
        result = subprocess.run(
            ["git", "log", "--oneline", "--format=%h %aI %s", "-80"],
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=10,
        )
        runs = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split(" ", 2)
            if len(parts) < 3:
                continue
            sha, timestamp, message = parts
            # Only process agent memory commits (🧠 prefix)
            if "\U0001f9e0" not in message:
                continue
            agent = "Agent"
            after = message.split("\U0001f9e0", 1)[1].strip()
            for emoji, name in EMOJI_AGENTS.items():
                if after.startswith(emoji):
                    agent = name
                    break
            else:
                words = after.split(None, 1)
                if words:
                    agent = words[0]
            time_str = timestamp[:16].replace("T", " ")
            runs.append({"sha": sha, "time": time_str, "agent": agent, "message": message})
        return runs[:limit]
    except Exception:
        return []


def get_workflow_file(agent: dict) -> str:
    """Derive the workflow filename from agent config key."""
    key = agent.get("_key", "")
    if key.startswith("council_"):
        return "council-review.yml"
    return key.replace("_", "-") + ".yml"


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
    in_agents_block = False
    content = config_file.read_text()

    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Top-level key
        if not line.startswith(" ") and stripped.endswith(":"):
            if current:
                agents.append(current)
                current = {}
            in_agents_block = (stripped == "agents:")
            continue

        # Agent name (2-space indent, ends with colon, no value)
        agent_match = re.match(r'^  (\w+):\s*$', line)
        if agent_match and in_agents_block:
            if current:
                agents.append(current)
            current = {"_key": agent_match.group(1)}
            continue

        # Property (4-space indent under agent, or 2-space under top-level)
        kv_match = re.match(r'\s+(\w+):\s*(.*)', line)
        if kv_match and current:
            key, raw_val = kv_match.group(1), kv_match.group(2).strip()
            # Strip inline comments (e.g. "false  # Enable via agent.md")
            if raw_val and not raw_val.startswith('"'):
                raw_val = raw_val.split("#")[0].strip()
            # Strip quotes
            if raw_val.startswith('"') and raw_val.endswith('"'):
                raw_val = raw_val[1:-1]
            # Type coercion
            if raw_val.lower() == "true":
                val = True
            elif raw_val.lower() == "false":
                val = False
            elif raw_val.lower() == "null" or raw_val == "":
                val = None
            else:
                val = raw_val
            current[key] = val

    if current:
        agents.append(current)

    return agents


def load_plugin_config() -> list:
    """Parse config/plugins.yml manually (no PyYAML dependency)."""
    config_file = REPO_ROOT / "config" / "plugins.yml"
    if not config_file.exists():
        return []

    plugins = []
    current = {}
    in_plugins_block = False
    content = config_file.read_text()

    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Top-level key
        if not line.startswith(" ") and stripped.endswith(":"):
            if current:
                plugins.append(current)
                current = {}
            in_plugins_block = (stripped == "plugins:")
            continue

        # Plugin name (2-space indent, ends with colon, no value)
        plugin_match = re.match(r'^  (\w+):\s*$', line)
        if plugin_match and in_plugins_block:
            if current:
                plugins.append(current)
            current = {"_key": plugin_match.group(1)}
            continue

        # Property (4+ space indent under plugin)
        kv_match = re.match(r'\s+(\w+):\s*(.*)', line)
        if kv_match and current:
            key, raw_val = kv_match.group(1), kv_match.group(2).strip()
            if raw_val and not raw_val.startswith('"'):
                raw_val = raw_val.split("#")[0].strip()
            if raw_val.startswith('"') and raw_val.endswith('"'):
                raw_val = raw_val[1:-1]
            # Handle list values like [agent1, agent2, agent3]
            if raw_val.startswith("[") and raw_val.endswith("]"):
                items = [s.strip().strip("'\"") for s in raw_val[1:-1].split(",")]
                current[key] = [i for i in items if i]
            elif raw_val.lower() == "true":
                current[key] = True
            elif raw_val.lower() == "false":
                current[key] = False
            elif raw_val.lower() == "null" or raw_val == "":
                current[key] = None
            else:
                current[key] = raw_val

    if current:
        plugins.append(current)

    return plugins


def get_recent_activity(limit: int = 50) -> list:
    """Build a chronological activity feed from all memory categories."""
    categories = [
        ("dreams", "Dream"),
        ("lore", "Lore"),
        ("research", "Research"),
        ("roasts", "Roast"),
        ("fortunes", "Fortune"),
        ("hn", "HN Digest"),
        ("news", "News"),
        ("crypto", "Crypto"),
        ("stocks", "Stock"),
        ("proposals", "Proposal"),
        ("council", "Council"),
    ]

    activities = []
    for cat, label in categories:
        for entry in load_memory_files(cat):
            activities.append({
                "date": entry["date"],
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


def nav_html(active: str, subdir: bool = False) -> str:
    """Generate the navigation bar."""
    pages = [
        ("index.html", "Dashboard"),
        ("memory.html", "Memory"),
        ("council.html", "Council"),
        ("agents.html", "Agents"),
        ("plugins.html", "Plugins"),
        ("debug.html", "Debug"),
        ("blog/index.html", "Blog"),
    ]
    prefix = "../" if subdir else ""
    links = []
    for href, label in pages:
        cls = ' class="active"' if label.lower() == active.lower() else ""
        links.append(f'<a href="{prefix}{href}"{cls}>{label}</a>')
    return "\n".join(links)


def header_bar(state: dict) -> str:
    """Generate the top header bar with lobster, docs link, XP bar, alive dot."""
    xp = state.get("xp", 0)
    level = state.get("level", "Unknown")
    streak = state.get("streak", {}).get("current", 0)
    last_active = state.get("last_active", "")
    xp_pct = get_xp_progress_pct(xp)
    repo_url = get_repo_url()

    # Alive indicator: green=today, amber=yesterday, grey=older
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    yesterday_str = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    if last_active == today_str:
        alive_cls = "alive-green"
    elif last_active == yesterday_str:
        alive_cls = "alive-amber"
    else:
        alive_cls = "alive-grey"

    return (
        f'<div class="header-bar">'
        f'<div class="header-left">'
        f'<span class="alive-dot {alive_cls}"></span>'
        f'<span class="header-title">\U0001f99e GitClaw</span>'
        f'<a href="{repo_url}" class="header-link" target="_blank">Docs</a>'
        f'</div>'
        f'<div class="header-meta">'
        f'<span>{e(level)}</span>'
        f'<span class="xp-bar-container">'
        f'XP {xp}'
        f'<div class="xp-bar"><div class="xp-bar-fill" style="width:{xp_pct}%"></div></div>'
        f'</span>'
        f'<span>Streak {streak}d</span>'
        f'</div>'
        f'</div>'
    )


def page_wrapper(title: str, active: str, state: dict, body: str, subdir: bool = False) -> str:
    """Wrap page body in full HTML document."""
    prefix = "../" if subdir else ""
    favicon = "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🦞</text></svg>"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="120">
    <title>GitClaw | {e(title)}</title>
    <link rel="icon" href="{favicon}">
    <link rel="stylesheet" href="{prefix}assets/style.css">
</head>
<body>
    {header_bar(state)}
    <nav class="nav">{nav_html(active, subdir)}</nav>
    <main class="main">
        {body}
    </main>
    <footer class="footer">
        <span>Powered by <a href="{get_repo_url()}" class="footer-link">GitHub Actions</a> &middot; Zero Infrastructure</span>
        <span id="clock"></span>
    </footer>
    <script src="{prefix}assets/app.js"></script>
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
    """Generate the main dashboard page with quick stats, workflow runs, and activity."""
    stats = state.get("stats", {})
    achievements = state.get("achievements", [])
    agents = load_agent_config()
    agent_info = state.get("agent", {})
    xp = state.get("xp", 0)
    level = state.get("level", "Unknown")
    streak = state.get("streak", {}).get("current", 0)
    total_agents = len(agents)
    active_agents = sum(1 for a in agents if a.get("enabled"))
    total_commits = stats.get("commits_made", 0)
    xp_pct = get_xp_progress_pct(xp)

    # ── Quick Stats Cards ──
    quick_stats = f"""
    <div class="stat-cards">
        <div class="stat-card">
            <div class="stat-value">{xp}</div>
            <div class="stat-label">{e(level)}</div>
            <div class="stat-bar"><div class="stat-bar-fill" style="width:{xp_pct}%"></div></div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{total_commits}</div>
            <div class="stat-label">Commits</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{active_agents}/{total_agents}</div>
            <div class="stat-label">Active Agents</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{streak}d</div>
            <div class="stat-label">Streak</div>
        </div>
    </div>"""

    # ── Activity Feed ──
    activity_rows = ""
    for act in activity[:15]:
        activity_rows += (
            f"<tr>"
            f"<td class='tertiary'>{e(act['date'])}</td>"
            f"<td><span class='badge'>{e(act['label'])}</span></td>"
            f"<td>{e(act['title'][:60])}</td>"
            f"</tr>\n"
        )

    # ── Workflow Runs ──
    runs = get_workflow_runs(12)
    runs_rows = ""
    if runs:
        for run in runs:
            runs_rows += (
                f"<tr>"
                f"<td>{e(run['agent'])}</td>"
                f"<td class='tertiary'>{e(run['time'])}</td>"
                f"<td><span class='status-active' style='font-size:12px'>Done</span></td>"
                f"</tr>\n"
            )
    else:
        runs_rows = '<tr><td colspan="3" class="tertiary" style="text-align:center;padding:16px">No workflow runs yet</td></tr>'

    # ── Agent Stats (non-zero only) ──
    non_zero = [(k, v) for k, v in sorted(stats.items()) if v > 0]
    stats_cells = ""
    for key, val in non_zero:
        label = key.replace("_", " ").title()
        stats_cells += f"<tr><td>{e(label)}</td><td class='num'>{val}</td></tr>\n"

    # ── Achievements ──
    ach_html = (" ".join(f'<span class="badge">{e(a)}</span>' for a in achievements)
                if achievements else '<span class="tertiary">None yet</span>')

    body = f"""
    {quick_stats}
    <div class="grid-2">
        <div class="panel">
            <h2 class="panel-title">Recent Activity</h2>
            <div class="table-scroll">
            <table class="data-table feed">
                <thead><tr><th>Date</th><th>Agent</th><th>Action</th></tr></thead>
                <tbody>{activity_rows}</tbody>
            </table>
            </div>
        </div>
        <div class="panel">
            <h2 class="panel-title">Workflow Runs</h2>
            <div class="table-scroll">
            <table class="data-table">
                <thead><tr><th>Agent</th><th>Time</th><th>Status</th></tr></thead>
                <tbody>{runs_rows}</tbody>
            </table>
            </div>
        </div>
    </div>
    <div class="grid-2" style="margin-top:20px">
        <div class="panel">
            <h2 class="panel-title">Agent Stats</h2>
            <div class="table-scroll">
            <table class="data-table">
                <thead><tr><th>Metric</th><th>Value</th></tr></thead>
                <tbody>{stats_cells}</tbody>
            </table>
            </div>
        </div>
        <div class="panel">
            <h2 class="panel-title">System</h2>
            <table class="data-table">
                <tr><td>Name</td><td>{e(agent_info.get('name', 'GitClaw'))}</td></tr>
                <tr><td>Persona</td><td>{e(agent_info.get('persona', 'default'))}</td></tr>
                <tr><td>Born</td><td>{e(agent_info.get('born', 'unknown')[:10])}</td></tr>
                <tr><td>Version</td><td>{e(agent_info.get('version', '1.0.0'))}</td></tr>
                <tr><td>Last Active</td><td>{e(state.get('last_active', 'unknown'))}</td></tr>
            </table>
            <h2 class="panel-title" style="margin-top:12px">Achievements</h2>
            <div class="achievements">{ach_html}</div>
        </div>
    </div>"""

    return page_wrapper("Dashboard", "dashboard", state, body)


def generate_memory_browser(state: dict) -> str:
    """Generate the memory browser page with tabs."""
    categories = [
        ("dreams", "Dreams"),
        ("lore", "Lore"),
        ("research", "Research"),
        ("roasts", "Roasts"),
        ("fortunes", "Fortunes"),
        ("hn", "HN"),
        ("news", "News"),
        ("crypto", "Crypto"),
        ("stocks", "Stocks"),
    ]

    tabs_html = ""
    panels_html = ""

    for i, (cat, label) in enumerate(categories):
        entries = load_memory_files(cat)
        active = " active" if i == 0 else ""

        tabs_html += f'<button class="tab-btn{active}" data-tab="{cat}">{label} ({len(entries)})</button>\n'

        entries_html = ""
        if entries:
            for entry in entries[:20]:
                content_html = md_to_html(entry["content"][:2000])
                entries_html += f"""
                <div class="memory-entry">
                    <div class="entry-header" onclick="toggleEntry(this)">
                        <span class="tertiary">{e(entry['date'])}</span>
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
        <h2 class="panel-title">Memory Browser</h2>
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
                pct = int(float(score) * 100)
                score_bar += (
                    f"<div class='score-row'>"
                    f"<span class='label'>{e(axis[:6])}</span>"
                    f"<div class='score-bar'><div class='score-bar-fill' style='width:{pct}%'></div></div>"
                    f"<span class='score-value'>{score}</span>"
                    f"</div>"
                )

            status_cls = {"proposed": "status-proposed", "approved": "status-approved", "rejected": "status-rejected"}.get(status, "tertiary")

            rows += f"""
            <div class="council-entry">
                <div class="entry-header" onclick="toggleEntry(this)">
                    <span class="tertiary">PR #{e(str(pr_num))}</span>
                    <span>{e(title[:60])}</span>
                    <span class="tertiary">{e(date)}</span>
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
                    <span class="tertiary">{e(entry['date'])}</span>
                    <span>{e(entry['title'][:60])}</span>
                    <span class="expand-icon">+</span>
                </div>
                <div class="entry-body" style="display:none">
                    {md_to_html(entry['content'][:2000])}
                </div>
            </div>"""

    body = f"""
    <div class="panel full-width">
        <h2 class="panel-title">Architect Proposals</h2>
        {rows}
    </div>
    <div class="panel full-width">
        <h2 class="panel-title">Council Reviews</h2>
        {council_html or '<div class="empty">No council reviews yet.</div>'}
    </div>"""

    return page_wrapper("Council", "council", state, body)


def humanize_cron(cron: str) -> str:
    """Convert a cron expression to a human-readable schedule."""
    if not cron:
        return ""
    parts = cron.split()
    if len(parts) < 5:
        return cron

    minute, hour, dom, month, dow = parts[:5]

    # Common patterns
    if hour.startswith("*/"):
        return f"Every {hour[2:]}h"
    if dow == "1-5":
        return f"Weekdays {hour}:{minute.zfill(2)} UTC"
    if dow == "1":
        return f"Mondays {hour}:{minute.zfill(2)} UTC"
    if dom == "*" and month == "*" and dow == "*":
        return f"Daily {hour}:{minute.zfill(2)} UTC"
    return cron


def generate_agents_page(state: dict) -> str:
    """Generate the agent status grid with category grouping and workflow links."""
    agents = load_agent_config()
    repo_url = get_repo_url()

    # Group agents by plugin/category
    groups = [
        ("Core", [a for a in agents if not a.get("plugin")]),
        ("Market & News", [a for a in agents if a.get("plugin") == "market"]),
        ("Solana", [a for a in agents if a.get("plugin") == "solana"]),
        ("Architect & Council", [a for a in agents if a.get("plugin") in ("architect", "council", "pages")]),
        ("Notifications", [a for a in agents if a.get("plugin") in ("telegram", "gmail")]),
    ]

    sections = ""
    total = len(agents)
    active = sum(1 for a in agents if a.get("enabled"))

    for group_name, group_agents in groups:
        if not group_agents:
            continue

        cards = ""
        for agent in group_agents:
            name = agent.get("name", agent.get("_key", "Unknown"))
            desc = agent.get("description", "")
            enabled = agent.get("enabled", False)
            trigger = agent.get("trigger", "")
            schedule = agent.get("schedule", "")
            command = agent.get("command", "")
            prompt_file = agent.get("prompt_file")

            # Generate initials from agent name
            initials = "".join(w[0] for w in name.split()[:2]).upper() if name else "?"

            status_cls = "status-active" if enabled else "status-disabled"
            status_txt = "Active" if enabled else "Disabled"

            # Command badge
            cmd_html = f'<span class="badge">{e(command)}</span>' if command else ""

            # Schedule label
            schedule_html = ""
            if schedule:
                human = humanize_cron(schedule)
                schedule_html = f'<span class="tertiary">{e(human)}</span>'

            # Trigger type
            trigger_html = f'<span class="tertiary">{e(trigger)}</span>' if trigger else ""

            # Workflow actions link
            trigger_link = ""
            if repo_url != "#":
                wf = get_workflow_file(agent)
                trigger_link = f'<a href="{repo_url}/actions/workflows/{wf}" class="trigger-link" target="_blank">Actions</a>'

            # Prompt file path
            prompt_html = ""
            if prompt_file:
                prompt_html = f'<div class="tertiary" style="font-size:11px;margin-top:4px">{e(prompt_file)}</div>'

            cards += f"""
            <div class="agent-card {"" if enabled else "disabled"}">
                <div class="agent-header">
                    <span class="agent-icon">{initials}</span>
                    <span class="agent-name">{e(name)}</span>
                    {cmd_html}
                    {trigger_link}
                </div>
                <div class="agent-desc">{e(desc)}</div>
                <div class="agent-meta">
                    <span class="{status_cls}">{status_txt}</span>
                    {schedule_html}
                    {trigger_html}
                </div>
                {prompt_html}
            </div>"""

        group_count = len(group_agents)
        group_active = sum(1 for a in group_agents if a.get("enabled"))
        sections += f"""
        <div class="agent-group">
            <h3 class="agent-group-title">{e(group_name)} <span class="tertiary">({group_active}/{group_count})</span></h3>
            <div class="agent-grid">{cards}</div>
        </div>"""

    body = f"""
    <div class="panel full-width">
        <h2 class="panel-title">Agent Status <span class="tertiary" style="text-transform:none;font-weight:400">{active} of {total} active</span></h2>
        {sections}
    </div>"""

    return page_wrapper("Agents", "agents", state, body)


def generate_plugins_page(state: dict) -> str:
    """Generate the plugins registry page with status cards and setup guide."""
    plugins = load_plugin_config()
    agents = load_agent_config()

    # Read agent.md to check what's enabled
    agent_md = ""
    agent_md_path = REPO_ROOT / "agent.md"
    if agent_md_path.exists():
        agent_md = agent_md_path.read_text().lower()

    # Count enabled plugins
    def plugin_enabled(plugin: dict) -> bool:
        key = plugin.get("_key", "")
        # Core is always enabled
        if key == "core":
            return True
        # Check agent.md for any agent in this plugin
        plugin_agents = plugin.get("agents", [])
        if isinstance(plugin_agents, str):
            plugin_agents = [s.strip() for s in plugin_agents.split(",")]
        for agent_key in plugin_agents:
            check_name = agent_key.replace("_", "-")
            if check_name in agent_md:
                return True
        # Also check plugin key itself
        if key in agent_md:
            return True
        return False

    enabled_count = sum(1 for p in plugins if plugin_enabled(p))
    total_count = len(plugins)

    # Build plugin cards
    cards = ""
    for plugin in plugins:
        key = plugin.get("_key", "")
        name = e(plugin.get("name", key))
        icon = plugin.get("icon", "📦")
        desc = e(plugin.get("description", ""))
        category = e(plugin.get("category", ""))
        is_enabled = plugin_enabled(plugin)
        status_cls = "on" if is_enabled else "off"
        card_cls = "enabled" if is_enabled else "disabled"
        status_label = "Enabled" if is_enabled else "Disabled"

        # Agent count
        plugin_agents = plugin.get("agents", [])
        if isinstance(plugin_agents, str):
            plugin_agents = [s.strip() for s in plugin_agents.split(",")]
        agent_count = len(plugin_agents)

        # Secrets
        secrets = plugin.get("secrets", [])
        if isinstance(secrets, str):
            secrets = [s.strip() for s in secrets.split(",")]
        optional_secrets = plugin.get("optional_secrets", [])
        if isinstance(optional_secrets, str):
            optional_secrets = [s.strip() for s in optional_secrets.split(",")]

        secrets_html = ""
        if secrets:
            tags = "".join(f'<span class="secret-tag">{e(s)}</span>' for s in secrets)
            secrets_html = f'<div class="plugin-meta"><strong>Secrets:</strong> {tags}</div>'
        if optional_secrets:
            opt_tags = "".join(f'<span class="secret-tag">{e(s)}</span>' for s in optional_secrets)
            secrets_html += f'<div class="plugin-meta"><strong>Optional:</strong> {opt_tags}</div>'

        # Setup link
        setup_url = plugin.get("setup_url", "")
        setup_html = ""
        if setup_url:
            setup_html = f'<a class="plugin-link" href="{e(setup_url)}" target="_blank">Setup Guide ↗</a>'

        cards += f"""
        <div class="plugin-card {card_cls}">
          <div class="plugin-header">
            <span class="plugin-icon">{icon}</span>
            <span class="plugin-name">{name}</span>
            <span class="plugin-status {status_cls}">{status_label}</span>
          </div>
          <div class="plugin-desc">{desc}</div>
          <div class="plugin-meta">
            {agent_count} agent{"s" if agent_count != 1 else ""} · {e(category)}
          </div>
          {secrets_html}
          {setup_html}
        </div>"""

    body = f"""
    <div class="panel">
      <h2 class="panel-title">Plugins ({enabled_count} / {total_count} enabled)</h2>
      <div class="plugin-grid">
        {cards}
      </div>
    </div>

    <div class="setup-box">
      <h3>How to Enable a Plugin</h3>
      <ol>
        <li>Add required <strong>secrets</strong> to your GitHub repo settings
            (Settings → Secrets and variables → Actions)</li>
        <li>Add <code>enable: plugin-name</code> to <code>agent.md</code></li>
        <li>Push — agents activate on the next scheduled or dispatched run</li>
      </ol>
    </div>"""

    return page_wrapper("Plugins", "plugins", state, body)


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
        commits_html = '<div class="tertiary">Could not load git log</div>'

    body = f"""
    <div class="grid-2">
        <div class="panel">
            <h2 class="panel-title">State</h2>
            <pre class="json-view"><code>{e(state_json)}</code></pre>
        </div>
        <div class="panel">
            <h2 class="panel-title">Recent Commits</h2>
            <div class="commit-log">{commits_html}</div>
            <h2 class="panel-title" style="margin-top:1rem">Memory Inventory</h2>
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
        entry["type"] = "Lore"
        posts.append(entry)
    for entry in research:
        entry["type"] = "Research"
        posts.append(entry)
    for entry in dreams:
        entry["type"] = "Dream"
        posts.append(entry)

    posts.sort(key=lambda x: x.get("date", ""), reverse=True)

    posts_html = ""
    if posts:
        for post in posts[:30]:
            content_preview = post["content"][:300].replace("\n", " ")
            posts_html += f"""
            <div class="blog-post">
                <div class="entry-header" onclick="toggleEntry(this)">
                    <span class="tertiary">{e(post['date'])}</span>
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
        <h2 class="panel-title">Blog</h2>
        <div class="webring-nav">
            <a href="../index.html">Dashboard</a>
            <a href="../memory.html">Memory</a>
            <a href="../council.html">Council</a>
        </div>
        {posts_html}
    </div>"""

    return page_wrapper("Blog", "blog", state, body, subdir=True)


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
        "plugins.html": generate_plugins_page(state),
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

    plugins = load_plugin_config()
    (DATA_DIR / "plugins.json").write_text(json.dumps(plugins, indent=2, default=str))

    log("Pages", f"Site built: {len(pages)} pages, 5 data files")

    update_stats("pages_built")
    award_xp(5)


if __name__ == "__main__":
    build_site()
