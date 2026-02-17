#!/usr/bin/env python3
"""
Architect Agent — GitClaw's autonomous improvement engine.
Analyzes the repo, proposes code changes via LLM, and creates PRs.
Can also revise existing proposals based on Council of 7 feedback.

Usage:
    python3 architect.py analyze    → JSON repo analysis to stdout
    python3 architect.py generate   → JSON proposal to stdout (reads ANALYSIS_JSON env)
    python3 architect.py apply      → creates branch + PR (reads PROPOSAL_JSON env)
    python3 architect.py revise     → revises existing PR (reads REVISION_PR, REVISION_BRANCH env)
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


def repair_json_strings(text: str) -> str:
    """Fix unescaped newlines/tabs inside JSON string values.

    LLMs often output file contents with literal newlines inside JSON strings
    instead of \\n escapes, which breaks json.loads(). This walks the string
    tracking quote boundaries and escapes bare control characters.
    """
    result = []
    in_string = False
    i = 0
    while i < len(text):
        c = text[i]
        # Check for escaped character — skip the pair
        if c == '\\' and in_string and i + 1 < len(text):
            result.append(c)
            result.append(text[i + 1])
            i += 2
            continue
        # Toggle string state on unescaped quote
        if c == '"':
            in_string = not in_string
            result.append(c)
        elif in_string and c == '\n':
            result.append('\\n')
        elif in_string and c == '\r':
            result.append('\\r')
        elif in_string and c == '\t':
            result.append('\\t')
        else:
            result.append(c)
        i += 1
    return ''.join(result)


def parse_proposal_json(response: str) -> dict:
    """Extract JSON block from LLM response."""
    # Try fenced code block first
    json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', response, re.DOTALL)
    if json_match:
        raw = json_match.group(1)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return json.loads(repair_json_strings(raw))

    # Try raw JSON
    brace_start = response.find("{")
    brace_end = response.rfind("}")
    if brace_start >= 0 and brace_end > brace_start:
        raw = response[brace_start:brace_end + 1]
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return json.loads(repair_json_strings(raw))

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
        check=True, cwd=str(REPO_ROOT), stdout=sys.stderr,
    )
    subprocess.run(
        ["git", "config", "user.email", "gitclaw[bot]@users.noreply.github.com"],
        check=True, cwd=str(REPO_ROOT), stdout=sys.stderr,
    )

    # Create and switch to new branch
    subprocess.run(
        ["git", "checkout", "-b", branch],
        check=True, cwd=str(REPO_ROOT), stdout=sys.stderr, stderr=sys.stderr,
    )

    # Write each file
    for f in files:
        file_path = REPO_ROOT / f["path"]
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(f["content"])
        subprocess.run(
            ["git", "add", f["path"]],
            check=True, cwd=str(REPO_ROOT), stdout=sys.stderr,
        )
        log("Architect", f"Wrote: {f['path']} ({f.get('reason', 'no reason given')})")

    # Commit
    commit_msg = f"🏗️ Architect: {title}"
    subprocess.run(
        ["git", "commit", "-m", commit_msg,
         "--author", "gitclaw[bot] <gitclaw[bot]@users.noreply.github.com>"],
        check=True, cwd=str(REPO_ROOT), stdout=sys.stderr, stderr=sys.stderr,
    )

    # Push branch
    subprocess.run(
        ["git", "push", "origin", branch],
        check=True, cwd=str(REPO_ROOT), stdout=sys.stderr, stderr=sys.stderr,
    )

    # Build PR body
    alignment_table = "\n".join(
        f"| {axis} | {score:.1f} |"
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
        check=True, cwd=str(REPO_ROOT), stdout=sys.stderr, stderr=sys.stderr,
    )

    return pr_num, branch


# ── Revise ────────────────────────────────────────────────────────────────────

MAX_REVISIONS = 2


def fetch_council_feedback(pr_number: str) -> list[str]:
    """Fetch council review comments from a PR, focusing on REVISE/REJECT votes."""
    try:
        # Use JSON output to properly separate multi-line comments
        result = subprocess.run(
            ["gh", "api", f"repos/{os.environ.get('GITHUB_REPOSITORY', '')}/issues/{pr_number}/comments",
             "--jq", "[.[] | .body]"],
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=15,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
    except Exception as e:
        log("Architect", f"Failed to fetch PR comments: {e}")
        return []

    try:
        comments = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

    # Keep comments that contain council votes (REVISE or REJECT)
    feedback = []
    for comment in comments:
        if "VOTE: REVISE" in comment or "VOTE: REJECT" in comment:
            feedback.append(comment)
    return feedback


def fetch_pr_diff(pr_number: str) -> str:
    """Fetch the current diff of a PR."""
    try:
        result = subprocess.run(
            ["gh", "pr", "diff", pr_number],
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=15,
        )
        if result.returncode == 0:
            return result.stdout[:4000]  # Truncate to avoid token blowout
    except Exception as e:
        log("Architect", f"Failed to fetch PR diff: {e}")
    return ""


def find_proposal_record(pr_number: str) -> dict:
    """Load the archived proposal JSON for this PR from memory/proposals/."""
    proposals_dir = MEMORY_DIR / "proposals"
    if not proposals_dir.is_dir():
        return {}

    for f in sorted(proposals_dir.glob("*.json"), reverse=True):
        try:
            record = json.loads(f.read_text())
            if str(record.get("pr_number", "")) == str(pr_number):
                return record
        except (json.JSONDecodeError, Exception):
            continue
    return {}


def revise_proposal(pr_number: str, branch: str) -> tuple:
    """Fetch council feedback, generate revised files via LLM, push to existing branch."""
    log("Architect", f"Revising PR #{pr_number} on branch {branch}")

    # Gather context
    feedback = fetch_council_feedback(pr_number)
    if not feedback:
        log("Architect", "No council feedback found — nothing to revise")
        raise RuntimeError("No council feedback found for revision")

    diff = fetch_pr_diff(pr_number)
    original = find_proposal_record(pr_number)
    system_prompt = read_prompt("architect")

    # Build the revision prompt
    feedback_text = "\n\n---\n\n".join(feedback[:7])  # At most 7 council members
    original_title = original.get("title", "Unknown proposal")
    original_desc = original.get("description", "")

    user_message = (
        f"## Revision Request — PR #{pr_number}\n\n"
        f"### Original Proposal\n"
        f"**Title:** {original_title}\n"
        f"**Description:** {original_desc}\n\n"
        f"### Current Diff\n```diff\n{diff}\n```\n\n"
        f"### Council Feedback (REVISE/REJECT votes)\n{feedback_text}\n\n"
        f"---\n\n"
        f"The Council of 7 voted to REVISE this proposal. "
        f"Read their feedback carefully and generate a revised version.\n"
        f"Address the specific concerns raised by each reviewer.\n"
        f"Output ONLY the JSON block as specified in your instructions.\n"
        f"Include a \"revision_summary\" field explaining what you changed and why."
    )

    response = call_llm(system_prompt, user_message, max_tokens=4000)
    proposal = parse_proposal_json(response)

    files = proposal.get("files", [])
    if not files:
        raise ValueError("Revised proposal has no files")

    if len(files) > MAX_FILES_PER_PROPOSAL:
        raise ValueError(f"Revised proposal exceeds {MAX_FILES_PER_PROPOSAL} file limit")

    # Safety check
    for f in files:
        path = f.get("path", "")
        if path in PROTECTED_PATHS:
            raise ValueError(f"Refusing to modify protected file: {path}")
        if any(path.startswith(prefix) for prefix in PROTECTED_PREFIXES):
            raise ValueError(f"Refusing to modify protected path: {path}")

    # Configure git identity
    subprocess.run(
        ["git", "config", "user.name", "gitclaw[bot]"],
        check=True, cwd=str(REPO_ROOT), stdout=sys.stderr,
    )
    subprocess.run(
        ["git", "config", "user.email", "gitclaw[bot]@users.noreply.github.com"],
        check=True, cwd=str(REPO_ROOT), stdout=sys.stderr,
    )

    # Fetch and checkout the existing branch
    subprocess.run(
        ["git", "fetch", "origin", branch],
        check=True, cwd=str(REPO_ROOT), stdout=sys.stderr, stderr=sys.stderr,
    )
    subprocess.run(
        ["git", "checkout", branch],
        check=True, cwd=str(REPO_ROOT), stdout=sys.stderr, stderr=sys.stderr,
    )

    # Write revised files
    for f in files:
        file_path = REPO_ROOT / f["path"]
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(f["content"])
        subprocess.run(
            ["git", "add", f["path"]],
            check=True, cwd=str(REPO_ROOT), stdout=sys.stderr,
        )
        log("Architect", f"Revised: {f['path']} ({f.get('reason', 'revised')})")

    # Commit revision
    revision_summary = proposal.get("revision_summary", "Addressed council feedback")
    title = proposal.get("title", original_title)
    commit_msg = f"🏗️ Architect revision: {title}"
    subprocess.run(
        ["git", "commit", "-m", commit_msg,
         "--author", "gitclaw[bot] <gitclaw[bot]@users.noreply.github.com>",
         "--allow-empty"],
        check=True, cwd=str(REPO_ROOT), stdout=sys.stderr, stderr=sys.stderr,
    )

    # Push to existing branch (updates the PR automatically)
    subprocess.run(
        ["git", "push", "origin", branch],
        check=True, cwd=str(REPO_ROOT), stdout=sys.stderr, stderr=sys.stderr,
    )

    # Post a revision comment on the PR (also serves as revision counter)
    files_summary = "\n".join(f"- `{f['path']}` — {f.get('reason', 'revised')}" for f in files)
    comment_body = (
        f"## 🏗️ Revision — Architect Response\n\n"
        f"**Summary:** {revision_summary}\n\n"
        f"### Files Updated\n{files_summary}\n\n"
        f"The Council of 7 will re-review this revision.\n\n"
        f"— 🏗️ *The Architect*"
    )
    try:
        subprocess.run(
            ["gh", "api", f"repos/{os.environ.get('GITHUB_REPOSITORY', '')}/issues/{pr_number}/comments",
             "-f", f"body={comment_body}"],
            check=True, cwd=str(REPO_ROOT), stdout=sys.stderr, stderr=sys.stderr,
        )
    except Exception as e:
        log("Architect", f"Failed to post revision comment: {e}")

    # Switch back to main
    subprocess.run(
        ["git", "checkout", "main"],
        check=True, cwd=str(REPO_ROOT), stdout=sys.stderr, stderr=sys.stderr,
    )

    log("Architect", f"Revision pushed to {branch} for PR #{pr_number}")
    return pr_number, branch


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
        print("Usage: architect.py [analyze|generate|apply|revise]", file=sys.stderr)
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

    elif command == "revise":
        revision_pr = os.environ.get("REVISION_PR", "0")
        revision_branch = os.environ.get("REVISION_BRANCH", "")
        if not revision_pr or revision_pr == "0" or not revision_branch:
            log("Architect", "REVISION_PR and REVISION_BRANCH must be set")
            sys.exit(1)

        pr_number, branch = revise_proposal(revision_pr, revision_branch)

        update_stats("proposals_revised")
        award_xp(30)

        # Output for workflow capture
        print(json.dumps({"pr_number": pr_number, "branch": branch}))

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
