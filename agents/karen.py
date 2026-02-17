#!/usr/bin/env python3
"""
Karen — GitClaw's QA compliance officer.
Scans memory for empty values, broken JSON, missing data, and rendering issues.
Files complaints as issue comments with the energy of someone
who'd like to speak to the manager.

Modes:
    python3 karen.py audit     → full memory & state audit (stdout)
    python3 karen.py review    → PR code review mode (reads PR_DIFF env)
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from common import (
    MEMORY_DIR, REPO_ROOT, award_xp, call_llm, gh_post_comment,
    load_state, log, read_prompt, today, update_stats,
)


# ── Audit Checks ─────────────────────────────────────────────────────────────

def check_state_json() -> list:
    """Audit memory/state.json for empty, null, or suspicious values."""
    issues = []
    state_file = MEMORY_DIR / "state.json"

    if not state_file.exists():
        issues.append({
            "severity": "CRITICAL",
            "file": "memory/state.json",
            "field": "(entire file)",
            "problem": "state.json does not exist",
            "detail": "The agent has no state. This is an existential crisis.",
        })
        return issues

    try:
        state = json.loads(state_file.read_text())
    except json.JSONDecodeError as e:
        issues.append({
            "severity": "CRITICAL",
            "file": "memory/state.json",
            "field": "(parse error)",
            "problem": f"Invalid JSON: {e}",
            "detail": "state.json is corrupted. Nothing works without valid state.",
        })
        return issues

    # Check required top-level keys
    required_keys = ["agent", "xp", "level", "stats", "last_active", "streak"]
    for key in required_keys:
        if key not in state:
            issues.append({
                "severity": "CRITICAL",
                "file": "memory/state.json",
                "field": key,
                "problem": f"Missing required key: '{key}'",
                "detail": "Core state field is absent. Agents depend on this.",
            })

    # Check agent identity
    agent = state.get("agent", {})
    for field in ["name", "persona", "born", "version"]:
        val = agent.get(field)
        if not val or (isinstance(val, str) and not val.strip()):
            issues.append({
                "severity": "WARNING",
                "file": "memory/state.json",
                "field": f"agent.{field}",
                "problem": f"Empty or missing: '{field}' = {repr(val)}",
                "detail": "Agent identity field is blank. Who even ARE you?",
            })

    # Check stats for all-zeros (stale agent)
    stats = state.get("stats", {})
    if stats and all(v == 0 for v in stats.values()):
        issues.append({
            "severity": "WARNING",
            "file": "memory/state.json",
            "field": "stats.*",
            "problem": "All stats are zero",
            "detail": "Agent has done nothing. Every counter is 0. Is it even running?",
        })

    # Check for null values anywhere in state
    def find_nulls(obj, path=""):
        if obj is None:
            issues.append({
                "severity": "WARNING",
                "file": "memory/state.json",
                "field": path or "(root)",
                "problem": f"Null value at '{path}'",
                "detail": "Null values can cause crashes in agents that don't check.",
            })
        elif isinstance(obj, dict):
            for k, v in obj.items():
                find_nulls(v, f"{path}.{k}" if path else k)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                find_nulls(v, f"{path}[{i}]")

    find_nulls(state)

    # Check XP/level consistency
    xp = state.get("xp", 0)
    level = state.get("level", "")
    expected_levels = [
        (0, "Unawakened"), (50, "Novice"), (150, "Apprentice"),
        (300, "Journeyman"), (500, "Adept"), (800, "Expert"),
        (1200, "Master"), (1800, "Grandmaster"), (2500, "Legend"),
        (5000, "Mythic"), (10000, "Transcendent"),
    ]
    expected_level = "Unawakened"
    for threshold, name in expected_levels:
        if xp >= threshold:
            expected_level = name
    if level != expected_level:
        issues.append({
            "severity": "WARNING",
            "file": "memory/state.json",
            "field": "level",
            "problem": f"Level mismatch: '{level}' but XP={xp} should be '{expected_level}'",
            "detail": "XP and level are out of sync. Someone's been editing state manually.",
        })

    # Check streak
    streak = state.get("streak", {})
    current = streak.get("current", 0)
    longest = streak.get("longest", 0)
    if current > longest:
        issues.append({
            "severity": "WARNING",
            "file": "memory/state.json",
            "field": "streak",
            "problem": f"Current streak ({current}) > longest ({longest})",
            "detail": "Mathematically impossible. Longest should always >= current.",
        })

    last_date = streak.get("last_date", "")
    if last_date:
        try:
            last = datetime.strptime(last_date, "%Y-%m-%d")
            days_ago = (datetime.now(timezone.utc).replace(tzinfo=None) - last).days
            if days_ago > 7:
                issues.append({
                    "severity": "NITPICK",
                    "file": "memory/state.json",
                    "field": "streak.last_date",
                    "problem": f"Last active {days_ago} days ago ({last_date})",
                    "detail": "The agent hasn't been active in over a week. Is it alive?",
                })
        except ValueError:
            issues.append({
                "severity": "WARNING",
                "file": "memory/state.json",
                "field": "streak.last_date",
                "problem": f"Invalid date format: '{last_date}'",
                "detail": "Expected YYYY-MM-DD format.",
            })

    return issues


def check_memory_dirs() -> list:
    """Audit memory subdirectories for empty files, missing dirs, broken content."""
    issues = []

    expected_dirs = [
        "dreams", "lore", "research", "roasts", "fortunes", "quests",
        "hn", "news", "crypto", "stocks", "proposals", "council",
    ]

    for dirname in expected_dirs:
        dirpath = MEMORY_DIR / dirname
        if not dirpath.is_dir():
            issues.append({
                "severity": "WARNING",
                "file": f"memory/{dirname}/",
                "field": "(directory)",
                "problem": f"Directory missing: memory/{dirname}/",
                "detail": "Expected memory subdirectory doesn't exist.",
            })
            continue

        # Check for .gitkeep
        gitkeep = dirpath / ".gitkeep"
        if not gitkeep.exists():
            issues.append({
                "severity": "NITPICK",
                "file": f"memory/{dirname}/.gitkeep",
                "field": ".gitkeep",
                "problem": "Missing .gitkeep file",
                "detail": "Empty dirs need .gitkeep to be tracked by git.",
            })

        # Check each file in the directory
        for f in dirpath.rglob("*"):
            if not f.is_file() or f.name == ".gitkeep":
                continue

            # Empty files
            if f.stat().st_size == 0:
                issues.append({
                    "severity": "WARNING",
                    "file": str(f.relative_to(REPO_ROOT)),
                    "field": "(content)",
                    "problem": "File is completely empty (0 bytes)",
                    "detail": "An agent wrote an empty file. That's not a memory, that's amnesia.",
                })
                continue

            # Check JSON files for validity
            if f.suffix == ".json":
                try:
                    data = json.loads(f.read_text())
                    # Check for empty objects/arrays
                    if isinstance(data, dict) and not data:
                        issues.append({
                            "severity": "WARNING",
                            "file": str(f.relative_to(REPO_ROOT)),
                            "field": "(content)",
                            "problem": "JSON file contains empty object {}",
                            "detail": "Written but empty. What was the point?",
                        })
                    elif isinstance(data, list) and not data:
                        issues.append({
                            "severity": "NITPICK",
                            "file": str(f.relative_to(REPO_ROOT)),
                            "field": "(content)",
                            "problem": "JSON file contains empty array []",
                            "detail": "An empty list is barely a file.",
                        })
                except json.JSONDecodeError as e:
                    issues.append({
                        "severity": "CRITICAL",
                        "file": str(f.relative_to(REPO_ROOT)),
                        "field": "(parse error)",
                        "problem": f"Invalid JSON: {e}",
                        "detail": "Corrupted JSON file in memory. This will break things.",
                    })

            # Check markdown files for substance
            if f.suffix == ".md":
                content = f.read_text().strip()
                if len(content) < 10:
                    issues.append({
                        "severity": "WARNING",
                        "file": str(f.relative_to(REPO_ROOT)),
                        "field": "(content)",
                        "problem": f"Markdown file has only {len(content)} chars",
                        "detail": "This 'memory' is barely a post-it note.",
                    })

    return issues


def check_agent_files() -> list:
    """Quick lint check on agent Python files."""
    issues = []
    agents_dir = REPO_ROOT / "agents"

    if not agents_dir.is_dir():
        issues.append({
            "severity": "CRITICAL",
            "file": "agents/",
            "field": "(directory)",
            "problem": "agents/ directory missing",
            "detail": "The entire agent codebase is gone. This is an emergency.",
        })
        return issues

    for f in sorted(agents_dir.glob("*.py")):
        content = f.read_text()
        lines = content.split("\n")

        # Check for empty files
        if not content.strip():
            issues.append({
                "severity": "CRITICAL",
                "file": f"agents/{f.name}",
                "field": "(content)",
                "problem": "Agent file is empty",
                "detail": "An empty agent. It's just standing there. Menacingly.",
            })
            continue

        # Check for bare except clauses
        for i, line in enumerate(lines, 1):
            if re.match(r'\s*except\s*:', line):
                issues.append({
                    "severity": "WARNING",
                    "file": f"agents/{f.name}",
                    "field": f"line {i}",
                    "problem": "Bare except clause (catches everything including SystemExit)",
                    "detail": "Use 'except Exception:' at minimum. Bare except is sloppy.",
                })

        # Check for TODO/FIXME/HACK comments
        for i, line in enumerate(lines, 1):
            for tag in ["TODO", "FIXME", "HACK", "XXX"]:
                if tag in line.upper() and "#" in line:
                    issues.append({
                        "severity": "NITPICK",
                        "file": f"agents/{f.name}",
                        "field": f"line {i}",
                        "problem": f"Found {tag} comment: {line.strip()[:80]}",
                        "detail": "Someone left a note and never came back. Classic.",
                    })

        # Check for hardcoded API URLs without error handling
        if "urllib.request.urlopen" in content and "try" not in content:
            issues.append({
                "severity": "WARNING",
                "file": f"agents/{f.name}",
                "field": "(network calls)",
                "problem": "HTTP calls without try/except",
                "detail": "Network calls will crash the agent if the API is down.",
            })

    return issues


def check_workflows() -> list:
    """Check workflow files for common issues."""
    issues = []
    workflows_dir = REPO_ROOT / ".github" / "workflows"

    if not workflows_dir.is_dir():
        return issues

    for f in sorted(workflows_dir.glob("*.yml")):
        content = f.read_text()

        # Check for ${{ }} directly in run: blocks (security issue)
        in_run = False
        for i, line in enumerate(content.split("\n"), 1):
            stripped = line.strip()
            if stripped.startswith("run:"):
                in_run = True
                # Check single-line run
                if "${{" in stripped and "env:" not in stripped:
                    issues.append({
                        "severity": "CRITICAL",
                        "file": f".github/workflows/{f.name}",
                        "field": f"line {i}",
                        "problem": "GitHub expression in run: block (injection risk)",
                        "detail": "Use env: block to pass values safely. This is a security vulnerability.",
                    })
                continue
            if in_run and not stripped.startswith("-") and not stripped.startswith("if:"):
                if "${{" in stripped and "github.repository" not in stripped:
                    # Allow ${{ github.repository }} as it's safe
                    issues.append({
                        "severity": "WARNING",
                        "file": f".github/workflows/{f.name}",
                        "field": f"line {i}",
                        "problem": f"Possible GitHub expression in run block: {stripped[:60]}",
                        "detail": "Verify this is passed via env: block, not interpolated directly.",
                    })
            if stripped and not stripped.startswith("|") and not stripped.startswith("#"):
                if not line.startswith(" " * 8) and not line.startswith("\t"):
                    in_run = False

    return issues


def check_config() -> list:
    """Check config files for issues."""
    issues = []

    # Check agent.md exists
    agent_md = REPO_ROOT / "agent.md"
    if not agent_md.exists():
        issues.append({
            "severity": "CRITICAL",
            "file": "agent.md",
            "field": "(file)",
            "problem": "agent.md missing",
            "detail": "The master config file is gone. No agent features can be checked.",
        })
    else:
        content = agent_md.read_text()
        if not content.strip():
            issues.append({
                "severity": "CRITICAL",
                "file": "agent.md",
                "field": "(content)",
                "problem": "agent.md is empty",
                "detail": "Config exists but says nothing. Very zen. Very broken.",
            })

    # Check prompt templates exist for enabled agents
    prompts_dir = REPO_ROOT / "templates" / "prompts"
    if prompts_dir.is_dir():
        for f in prompts_dir.glob("*.md"):
            content = f.read_text().strip()
            if len(content) < 50:
                issues.append({
                    "severity": "WARNING",
                    "file": f"templates/prompts/{f.name}",
                    "field": "(content)",
                    "problem": f"Prompt template suspiciously short ({len(content)} chars)",
                    "detail": "A prompt this short won't produce quality output.",
                })

    return issues


def check_pages() -> list:
    """Check GitHub Pages docs/ for rendering issues."""
    issues = []
    docs_dir = REPO_ROOT / "docs"

    if not docs_dir.is_dir():
        issues.append({
            "severity": "NITPICK",
            "file": "docs/",
            "field": "(directory)",
            "problem": "docs/ directory doesn't exist yet",
            "detail": "Pages haven't been built. Run the pages-builder workflow.",
        })
        return issues

    # Check .nojekyll
    if not (docs_dir / ".nojekyll").exists():
        issues.append({
            "severity": "WARNING",
            "file": "docs/.nojekyll",
            "field": "(file)",
            "problem": ".nojekyll missing — Jekyll will process the site",
            "detail": "Without .nojekyll, GitHub Pages uses Jekyll which breaks raw HTML.",
        })

    # Check required pages exist
    required_pages = ["index.html", "memory.html", "council.html", "agents.html", "debug.html"]
    for page in required_pages:
        page_path = docs_dir / page
        if not page_path.exists():
            issues.append({
                "severity": "WARNING",
                "file": f"docs/{page}",
                "field": "(file)",
                "problem": f"Page missing: {page}",
                "detail": "Expected page not generated. Site is incomplete.",
            })
        elif page_path.stat().st_size == 0:
            issues.append({
                "severity": "CRITICAL",
                "file": f"docs/{page}",
                "field": "(content)",
                "problem": f"Page is empty: {page}",
                "detail": "A blank HTML page. The builder wrote nothing. Embarrassing.",
            })
        else:
            content = page_path.read_text()
            if "<html" not in content.lower():
                issues.append({
                    "severity": "WARNING",
                    "file": f"docs/{page}",
                    "field": "(content)",
                    "problem": f"No <html> tag found in {page}",
                    "detail": "This doesn't look like a valid HTML page.",
                })

    # Check CSS/JS assets
    for asset in ["assets/style.css", "assets/app.js"]:
        asset_path = docs_dir / asset
        if not asset_path.exists():
            issues.append({
                "severity": "WARNING",
                "file": f"docs/{asset}",
                "field": "(file)",
                "problem": f"Asset missing: {asset}",
                "detail": "The site will render without styling or interactivity.",
            })
        elif asset_path.stat().st_size == 0:
            issues.append({
                "severity": "WARNING",
                "file": f"docs/{asset}",
                "field": "(content)",
                "problem": f"Asset is empty: {asset}",
                "detail": "Zero bytes of CSS/JS. The terminal aesthetic won't work.",
            })

    # Check data files
    data_dir = docs_dir / "data"
    if data_dir.is_dir():
        for df in ["state.json", "activity.json", "council.json", "agents.json"]:
            df_path = data_dir / df
            if df_path.exists():
                try:
                    json.loads(df_path.read_text())
                except json.JSONDecodeError:
                    issues.append({
                        "severity": "CRITICAL",
                        "file": f"docs/data/{df}",
                        "field": "(content)",
                        "problem": f"Invalid JSON in data file: {df}",
                        "detail": "The JS frontend reads this. Broken JSON = broken dashboard.",
                    })

    return issues


# ── Full Audit ───────────────────────────────────────────────────────────────

def run_full_audit() -> dict:
    """Run all checks and compile results."""
    all_issues = []

    checks = [
        ("State", check_state_json),
        ("Memory", check_memory_dirs),
        ("Agents", check_agent_files),
        ("Workflows", check_workflows),
        ("Config", check_config),
        ("Pages", check_pages),
    ]

    for name, check_fn in checks:
        try:
            found = check_fn()
            all_issues.extend(found)
            log("Karen", f"  {name}: {len(found)} issue(s)")
        except Exception as e:
            log("Karen", f"  {name}: check failed — {e}")
            all_issues.append({
                "severity": "CRITICAL",
                "file": f"({name} check)",
                "field": "(check error)",
                "problem": f"Check crashed: {e}",
                "detail": "Karen's own check failed. This is meta-embarrassing.",
            })

    critical = sum(1 for i in all_issues if i["severity"] == "CRITICAL")
    warnings = sum(1 for i in all_issues if i["severity"] == "WARNING")
    nitpicks = sum(1 for i in all_issues if i["severity"] == "NITPICK")

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": len(all_issues),
        "critical": critical,
        "warnings": warnings,
        "nitpicks": nitpicks,
        "issues": all_issues,
    }


def format_audit_for_llm(audit: dict) -> str:
    """Format audit results as structured text for the LLM."""
    lines = [
        f"Audit timestamp: {audit['timestamp']}",
        f"Total issues: {audit['total']}",
        f"  Critical: {audit['critical']}",
        f"  Warnings: {audit['warnings']}",
        f"  Nitpicks: {audit['nitpicks']}",
        "",
        "Issues found:",
    ]

    for i, issue in enumerate(audit["issues"], 1):
        sev = {"CRITICAL": "🔴", "WARNING": "🟡", "NITPICK": "🟢"}.get(issue["severity"], "⚪")
        lines.append(f"\n{i}. {sev} [{issue['severity']}] {issue['file']}")
        lines.append(f"   Field: {issue['field']}")
        lines.append(f"   Problem: {issue['problem']}")
        lines.append(f"   Detail: {issue['detail']}")

    if not audit["issues"]:
        lines.append("\nNo issues found. (Karen is suspicious. Check again.)")

    return "\n".join(lines)


# ── PR Review Mode ───────────────────────────────────────────────────────────

def review_pr_diff(pr_diff: str, pr_title: str) -> str:
    """Review a PR diff for bugs and quality issues."""
    system_prompt = read_prompt("karen")

    user_message = (
        f"## PR Review Request: {pr_title}\n\n"
        f"Review this PR diff for bugs, empty values, missing error handling, "
        f"and anything that doesn't meet quality standards.\n\n"
        f"```diff\n{pr_diff[:4000]}\n```\n\n"
        f"File your complaints."
    )

    try:
        response = call_llm(system_prompt, user_message, max_tokens=1500)
    except Exception as e:
        log("Karen", f"LLM call failed: {e}")
        response = (
            "## 💅 Karen's Complaint\n\n"
            "I TRIED to review this PR but the LLM API is down. "
            "Which is ALSO something someone should fix.\n\n"
            "I'll be back. Trust me.\n\n"
            "— 💅 *Karen has filed her complaints. You're welcome.*"
        )

    return response


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "audit"
    issue_number = int(os.environ.get("ISSUE_NUMBER", "0"))

    if mode == "audit":
        log("Karen", "Starting full audit...")
        audit = run_full_audit()

        # Get LLM to write the complaint in Karen's voice
        system_prompt = read_prompt("karen")
        audit_text = format_audit_for_llm(audit)

        user_message = (
            f"## QA Audit Results\n\n"
            f"You just ran a full audit of the GitClaw repository. "
            f"Here are the raw findings:\n\n"
            f"{audit_text}\n\n"
            f"Write your official complaint report based on these findings. "
            f"Be Karen about it."
        )

        try:
            response = call_llm(system_prompt, user_message, max_tokens=2000)
        except Exception as e:
            log("Karen", f"LLM failed: {e}")
            # Format a raw report without LLM
            lines = [
                "## 💅 Karen's QA Report (Raw — LLM Unavailable)\n",
                f"**Total complaints:** {audit['total']}\n",
                f"- 🔴 Critical: {audit['critical']}",
                f"- 🟡 Warnings: {audit['warnings']}",
                f"- 🟢 Nitpicks: {audit['nitpicks']}\n",
            ]
            for issue in audit["issues"]:
                sev = {"CRITICAL": "🔴", "WARNING": "🟡", "NITPICK": "🟢"}.get(issue["severity"], "⚪")
                lines.append(f"- {sev} **{issue['file']}** — {issue['problem']}")
            lines.append("\n— 💅 *Karen has filed her complaints. You're welcome.*")
            response = "\n".join(lines)

        if issue_number > 0:
            gh_post_comment(issue_number, response)

        # Archive
        archive_dir = MEMORY_DIR / "karen"
        archive_dir.mkdir(parents=True, exist_ok=True)

        # Save the formatted report
        report_path = archive_dir / f"{today()}-audit.md"
        report_path.write_text(
            f"# Karen QA Audit — {today()}\n\n{response}\n"
        )

        # Save raw audit data
        data_path = archive_dir / f"{today()}-audit.json"
        data_path.write_text(json.dumps(audit, indent=2, default=str) + "\n")

        update_stats("karen_audits")
        award_xp(15)

        print(response)

    elif mode == "review":
        pr_diff = os.environ.get("PR_DIFF", "")
        pr_title = os.environ.get("PR_TITLE", "Unknown PR")

        if not pr_diff:
            log("Karen", "No PR diff provided")
            print("No diff to review. Karen is unimpressed.")
            sys.exit(1)

        response = review_pr_diff(pr_diff, pr_title)

        update_stats("karen_reviews")
        award_xp(10)

        print(response)

    else:
        print(f"Unknown mode: {mode}. Use 'audit' or 'review'.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
