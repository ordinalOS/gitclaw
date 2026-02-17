#!/usr/bin/env python3
"""
Architect Agent — GitClaw's autonomous improvement engine.
Analyzes the repo, proposes code changes via LLM, and creates PRs.

Usage:
    python3 architect.py analyze    → JSON repo analysis to stdout
    python3 architect.py generate   → JSON proposal to stdout (reads ANALYSIS_JSON env)
    python3 architect.py apply      → creates branch + PR (reads PROPOSAL_JSON env)
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from common import (
    MEMORY_DIR, REPO_ROOT, award_xp, call_llm, log,
    load_state, read_prompt, today, update_stats,
)

# Files and directories the Architect must never modify
PROTECTED_PATHS = {
    "scripts/git-persist.sh",
    "scripts/llm.sh",
    "scripts/utils.sh",
    "scripts/github-api.sh",
    ".github/workflows/architect.yml",
    ".github/workflows/council-review.yml",
    ".github/workflows/council-member.yml",
    ".github/workflows/proposal-lint.yml",
}

PROTECTED_PREFIXES = [
    ".git/",
]

MAX_FILES_PER_PROPOSAL = 3


# ── Analyze ──────────────────────────────────────────────────────────────────

def analyze_repo() -> dict:
    """Scan the repository and build a context summary for the LLM."""
    analysis = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "state": {},
        "file_tree": [],
        "recent_commits": [],
        "open_issues": [],
        "open_prs": [],
        "agent_files": [],
        "workflow_files": [],
    }

    # Load state
    try:
        analysis["state"] = load_state()
    except Exception:
        analysis["state"] = {}

    # File tree (top 2 levels)
    try:
        result = subprocess.run(
            ["find", ".", "-maxdepth", "2", "-type", "f",
             "-not", "-path", "./.git/*"],
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=10,
        )
        analysis["file_tree"] = result.stdout.strip().split("\n")[:100]
    except Exception:
        pass

    # Recent commits
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-15"],
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=10,
        )
        analysis["recent_commits"] = result.stdout.strip().split("\n")
    except Exception:
        pass

    # Open issues
    try:
        result = subprocess.run(
            ["gh", "issue", "list", "--state", "open", "--limit", "10",
             "--json", "number,title,labels"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            analysis["open_issues"] = json.loads(result.stdout)
    except Exception:
        pass

    # Open PRs
    try:
        result = subprocess.run(
            ["gh", "pr", "list", "--state", "open", "--limit", "5",
             "--json", "number,title,headRefName"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            analysis["open_prs"] = json.loads(result.stdout)
    except Exception:
        pass

    # Agent files summary
    agents_dir = REPO_ROOT / "agents"
    if agents_dir.is_dir():
        for f in sorted(agents_dir.glob("*.py")):
            try:
                lines = f.read_text().split("\n")
                # Extract docstring (first triple-quoted block)
                doc = ""
                for line in lines[:10]:
                    if line.strip().startswith('"""') or line.strip().startswith("'''"):
                        doc = line.strip().strip('"').strip("'")
                        break
                analysis["agent_files"].append({
                    "name": f.name,
                    "lines": len(lines),
                    "doc": doc,
                })
            except Exception:
                pass

    # Workflow files summary
    workflows_dir = REPO_ROOT / ".github" / "workflows"
    if workflows_dir.is_dir():
        for f in sorted(workflows_dir.glob("*.yml")):
            try:
                content = f.read_text()
                name_match = re.search(r'^name:\s*["\']?(.+?)["\']?\s*$', content, re.MULTILINE)
                analysis["workflow_files"].append({
                    "file": f.name,
                    "name": name_match.group(1) if name_match else f.stem,
                    "lines": len(content.split("\n")),
                })
            except Exception:
                pass

    return analysis


# ── Generate ─────────────────────────────────────────────────────────────────

def generate_proposal(analysis: dict, context_hint: str = "") -> dict:
    """Use LLM to generate a structured improvement proposal."""
    system_prompt = read_prompt("architect")

    # Build a focused context message
    state = analysis.get("state", {})
    xp = state.get("xp", 0)
    level = state.get("level", "Unknown")
    stats = state.get("stats", {})

    # Read a few agent files to give the LLM real code context
    code_samples = []
    agents_dir = REPO_ROOT / "agents"
    for agent_info in analysis.get("agent_files", [])[:5]:
        try:
            content = (agents_dir / agent_info["name"]).read_text()
            if len(content) < 3000:
                code_samples.append(f"### {agent_info['name']}\n```python\n{content}\n```")
        except Exception:
            pass

    user_message = (
        f"## Repository Analysis — {today()}\n\n"
        f"**Agent State:** {xp} XP, Level: {level}\n"
        f"**Stats:** {json.dumps(stats, indent=2)}\n\n"
        f"**Recent commits:**\n"
        + "\n".join(f"- {c}" for c in analysis.get("recent_commits", [])[:10])
        + "\n\n"
        f"**Open issues:** {len(analysis.get('open_issues', []))}\n"
        f"**Open PRs:** {len(analysis.get('open_prs', []))}\n\n"
        f"**File tree:**\n"
        + "\n".join(analysis.get("file_tree", [])[:50])
        + "\n\n"
        f"**Agent files:**\n"
        + "\n".join(
            f"- {a['name']} ({a['lines']} lines): {a['doc']}"
            for a in analysis.get("agent_files", [])
        )
        + "\n\n"
        f"**Workflow files:**\n"
        + "\n".join(
            f"- {w['file']} ({w['lines']} lines): {w['name']}"
            for w in analysis.get("workflow_files", [])
        )
        + "\n\n"
    )

    if code_samples:
        user_message += "## Sample Code (for context)\n\n" + "\n\n".join(code_samples[:3]) + "\n\n"

    if context_hint:
        user_message += f"## Human Hint\n{context_hint}\n\n"

    user_message += (
        "Based on this analysis, propose ONE focused improvement.\n"
        "Output ONLY the JSON block as specified in your instructions."
    )

    response = call_llm(system_prompt, user_message, max_tokens=4000)

    # Extract JSON from the response
    proposal = parse_proposal_json(response)
    proposal["proposed_at"] = datetime.now(timezone.utc).isoformat()
    proposal["version"] = state.get("agent", {}).get("version", "1.0.0")

    return proposal


def parse_proposal_json(response: str) -> dict:
    """Extract JSON block from LLM response."""
    # Try fenced code block first
    json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', response, re.DOTALL)
    if json_match:
        return json.loads(json_match.group(1))

    # Try raw JSON
    brace_start = response.find("{")
    brace_end = response.rfind("}")
    if brace_start >= 0 and brace_end > brace_start:
        return json.loads(response[brace_start:brace_end + 1])

    raise ValueError("No valid JSON found in LLM response")


# ── Apply ────────────────────────────────────────────────────────────────────

def apply_proposal(proposal: dict) -> tuple:
    """Create a branch, write files, commit, and open a PR."""
    title = proposal.get("title", "Architect improvement")
    description = proposal.get("description", "Automated improvement by GitClaw Architect.")
    branch = proposal.get("branch_name", "")
    files = proposal.get("files", [])
    alignment = proposal.get("alignment_scores", {})
    goals = proposal.get("goals", [])

    if not branch:
        slug = re.sub(r'[^a-z0-9]+', '-', title.lower())[:30].strip('-')
        branch = f"feat/architect-{today().replace('-', '')}-{slug}"

    if not files:
        raise ValueError("Proposal has no files to write")

    if len(files) > MAX_FILES_PER_PROPOSAL:
        raise ValueError(f"Proposal exceeds {MAX_FILES_PER_PROPOSAL} file limit")

    # Safety check: refuse to modify protected files
    for f in files:
        path = f.get("path", "")
        if path in PROTECTED_PATHS:
            raise ValueError(f"Refusing to modify protected file: {path}")
        if any(path.startswith(prefix) for prefix in PROTECTED_PREFIXES):
            raise ValueError(f"Refusing to modify protected path: {path}")

    # Configure git identity
    subprocess.run(
        ["git", "config", "user.name", "gitclaw[bot]"],
        check=True, cwd=str(REPO_ROOT),
    )
    subprocess.run(
        ["git", "config", "user.email", "gitclaw[bot]@users.noreply.github.com"],
        check=True, cwd=str(REPO_ROOT),
    )

    # Create and switch to new branch
    subprocess.run(
        ["git", "checkout", "-b", branch],
        check=True, cwd=str(REPO_ROOT),
    )

    # Write each file
    for f in files:
        file_path = REPO_ROOT / f["path"]
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(f["content"])
        subprocess.run(
            ["git", "add", f["path"]],
            check=True, cwd=str(REPO_ROOT),
        )
        log("Architect", f"Wrote: {f['path']} ({f.get('reason', 'no reason given')})")

    # Commit
    commit_msg = f"🏗️ Architect: {title}"
    subprocess.run(
        ["git", "commit", "-m", commit_msg,
         "--author", "gitclaw[bot] <gitclaw[bot]@users.noreply.github.com>"],
        check=True, cwd=str(REPO_ROOT),
    )

    # Push branch
    subprocess.run(
        ["git", "push", "origin", branch],
        check=True, cwd=str(REPO_ROOT),
    )

    # Build PR body
    alignment_table = "\n".join(
        f"| {axis} | {'█' * int(score * 10)}{'░' * (10 - int(score * 10))} {score:.1f} |"
        for axis, score in alignment.items()
    )

    pr_body = (
        f"{description}\n\n"
        f"## Goal Alignment\n\n"
        f"| Axis | Score |\n|------|-------|\n{alignment_table}\n\n"
        f"## Goals Addressed\n"
        + "\n".join(f"- {g}" for g in goals)
        + "\n\n"
        f"## Files Changed\n"
        + "\n".join(f"- `{f['path']}` — {f.get('reason', 'modified')}" for f in files)
        + "\n\n---\n"
        f"*🏗️ Proposed by GitClaw Architect — automated improvement engine*\n"
        f"*This PR will be reviewed by the Council of 7.*"
    )

    # Create PR
    result = subprocess.run(
        ["gh", "pr", "create",
         "--title", title,
         "--body", pr_body,
         "--head", branch,
         "--base", "main"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )

    if result.returncode != 0:
        log("Architect", f"PR creation failed: {result.stderr}")
        raise RuntimeError(f"gh pr create failed: {result.stderr}")

    pr_url = result.stdout.strip()
    pr_number = re.search(r'/(\d+)$', pr_url)
    pr_num = pr_number.group(1) if pr_number else "0"

    log("Architect", f"Created PR #{pr_num}: {pr_url}")

    # Switch back to main
    subprocess.run(
        ["git", "checkout", "main"],
        check=True, cwd=str(REPO_ROOT),
    )

    return pr_num, branch


# ── Archive ──────────────────────────────────────────────────────────────────

def archive_proposal(proposal: dict, pr_number: str, branch: str):
    """Save proposal record to memory/proposals/."""
    proposals_dir = MEMORY_DIR / "proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)

    record = {
        **proposal,
        "pr_number": pr_number,
        "branch": branch,
        "status": "proposed",
    }

    # Remove full file contents from archive (too large)
    if "files" in record:
        record["files"] = [
            {"path": f["path"], "reason": f.get("reason", "")}
            for f in record["files"]
        ]

    slug = re.sub(r'[^a-z0-9]+', '-', proposal.get("title", "proposal").lower())[:40].strip('-')
    archive_path = proposals_dir / f"{today()}-{slug}.json"
    archive_path.write_text(json.dumps(record, indent=2) + "\n")

    log("Architect", f"Archived proposal: {archive_path.name}")
    return archive_path


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: architect.py [analyze|generate|apply]", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "analyze":
        analysis = analyze_repo()
        print(json.dumps(analysis, indent=2, default=str))

    elif command == "generate":
        analysis_json = os.environ.get("ANALYSIS_JSON", "{}")
        context_hint = os.environ.get("PROPOSAL_CONTEXT", "")
        try:
            analysis = json.loads(analysis_json)
        except json.JSONDecodeError:
            log("Architect", "Invalid ANALYSIS_JSON, running fresh analysis")
            analysis = analyze_repo()

        proposal = generate_proposal(analysis, context_hint)
        print(json.dumps(proposal, indent=2))

    elif command == "apply":
        proposal_json = os.environ.get("PROPOSAL_JSON", "")
        if not proposal_json:
            log("Architect", "PROPOSAL_JSON not set")
            sys.exit(1)

        proposal = json.loads(proposal_json)
        pr_number, branch = apply_proposal(proposal)
        archive_proposal(proposal, pr_number, branch)

        update_stats("proposals_made")
        award_xp(50)

        # Output for workflow capture
        print(json.dumps({"pr_number": pr_number, "branch": branch}))

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
