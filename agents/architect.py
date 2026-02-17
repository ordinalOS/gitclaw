#!/usr/bin/env python3
"""
Architect Agent — GitClaw's autonomous improvement engine.

Analyzes the codebase for concrete improvements and proposes focused changes.
"""

import json
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.common import call_llm, get_github_context, log_event

# Allowed directories for file modifications
ALLOWED_DIRS = {"agents", "templates/prompts", "config", "memory"}


def validate_proposal(proposal_json: str) -> dict | None:
    """
    Parse and validate a proposal JSON structure.
    
    Args:
        proposal_json: Raw JSON string from LLM output
        
    Returns:
        Validated proposal dict, or None if invalid
    """
    try:
        proposal = json.loads(proposal_json)
    except json.JSONDecodeError as e:
        log_event(
            "architect",
            "error",
            f"Failed to parse proposal JSON: {e}",
            {"error": str(e), "raw_length": len(proposal_json)}
        )
        return None
    
    # Validate required top-level fields
    required_fields = ["title", "description", "branch_name", "files", "alignment_scores"]
    for field in required_fields:
        if field not in proposal:
            log_event(
                "architect",
                "error",
                f"Missing required field: {field}",
                {"proposal_keys": list(proposal.keys())}
            )
            return None
    
    # Validate field types
    if not isinstance(proposal.get("title"), str) or len(proposal["title"]) > 60:
        log_event("architect", "error", "Invalid title: must be string ≤60 chars")
        return None
    
    if not isinstance(proposal.get("description"), str):
        log_event("architect", "error", "Invalid description: must be string")
        return None
    
    if not isinstance(proposal.get("branch_name"), str):
        log_event("architect", "error", "Invalid branch_name: must be string")
        return None
    
    if not isinstance(proposal.get("files"), list):
        log_event("architect", "error", "Invalid files: must be list")
        return None
    
    if len(proposal["files"]) > 3:
        log_event("architect", "error", "Too many files: max 3 allowed")
        return None
    
    if not isinstance(proposal.get("alignment_scores"), dict):
        log_event("architect", "error", "Invalid alignment_scores: must be dict")
        return None
    
    # Validate required alignment score keys
    required_scores = ["performance", "security", "maintainability", "developer_experience", "cost_efficiency"]
    for score_key in required_scores:
        if score_key not in proposal["alignment_scores"]:
            log_event(
                "architect",
                "error",
                f"Missing alignment score: {score_key}"
            )
            return None
        
        score = proposal["alignment_scores"][score_key]
        if not isinstance(score, (int, float)) or not (0.0 <= score <= 1.0):
            log_event(
                "architect",
                "error",
                f"Invalid alignment score {score_key}: must be 0.0-1.0"
            )
            return None
    
    # Validate files structure and paths
    for i, file_obj in enumerate(proposal["files"]):
        if not isinstance(file_obj, dict):
            log_event("architect", "error", f"File {i}: must be dict")
            return None
        
        if "path" not in file_obj or "content" not in file_obj:
            log_event("architect", "error", f"File {i}: missing 'path' or 'content'")
            return None
        
        if not isinstance(file_obj["path"], str) or not isinstance(file_obj["content"], str):
            log_event("architect", "error", f"File {i}: path and content must be strings")
            return None
        
        # Validate file path is in allowed directory
        file_path = file_obj["path"]
        path_parts = file_path.split("/")
        
        if not path_parts or path_parts[0] not in ALLOWED_DIRS:
            log_event(
                "architect",
                "error",
                f"File {i}: path not in allowed directories",
                {"path": file_path, "allowed": list(ALLOWED_DIRS)}
            )
            return None
        
        # Prevent directory traversal
        if ".." in path_parts:
            log_event(
                "architect",
                "error",
                f"File {i}: path contains directory traversal",
                {"path": file_path}
            )
            return None
    
    return proposal


def create_proposal_branch(proposal: dict) -> bool:
    """
    Create a git branch and commit the proposed changes.
    
    Args:
        proposal: Validated proposal dict
        
    Returns:
        True if successful, False otherwise
    """
    branch_name = proposal["branch_name"]
    
    try:
        # Create and checkout branch
        subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=os.getcwd(),
            check=True,
            capture_output=True
        )
        
        # Write files
        repo_root = Path(os.getcwd())
        for file_obj in proposal["files"]:
            file_path = repo_root / file_obj["path"]
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, "w") as f:
                f.write(file_obj["content"])
            
            subprocess.run(
                ["git", "add", file_obj["path"]],
                cwd=os.getcwd(),
                check=True,
                capture_output=True
            )
        
        # Commit with description
        commit_msg = f"🏗️ {proposal['title']}\n\n{proposal['description']}"
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=os.getcwd(),
            check=True,
            capture_output=True,
            env={**os.environ, "GIT_AUTHOR_NAME": "Architect", "GIT_AUTHOR_EMAIL": "architect@gitclaw.dev", "GIT_COMMITTER_NAME": "Architect", "GIT_COMMITTER_EMAIL": "architect@gitclaw.dev"}
        )
        
        log_event(
            "architect",
            "success",
            f"Created proposal branch: {branch_name}",
            {"files_modified": len(proposal["files"])}
        )
        return True
        
    except subprocess.CalledProcessError as e:
        log_event(
            "architect",
            "error",
            f"Failed to create proposal branch: {e}",
            {"branch": branch_name, "stderr": e.stderr.decode() if e.stderr else ""}
        )
        return False


def analyze_codebase() -> str:
    """
    Analyze the codebase and request improvement proposals from LLM.
    
    Returns:
        LLM response with proposal JSON
    """
    # Gather codebase statistics
    repo_root = Path(os.getcwd())
    agent_files = sorted(repo_root.glob("agents/*.py"))
    workflow_files = sorted(repo_root.glob(".github/workflows/*.yml"))
    config_files = sorted(repo_root.glob("config/*.yml"))
    
    agent_lines = sum(
        len(f.read_text().splitlines())
        for f in agent_files
    )
    
    workflow_lines = sum(
        len(f.read_text().splitlines())
        for f in workflow_files
    )
    
    # Build analysis prompt
    analysis_prompt = f"""
You are the Architect — GitClaw's autonomous improvement engine.

Repository State:
- {len(agent_files)} agent files ({agent_lines} lines)
- {len(workflow_files)} workflow files ({workflow_lines} lines)
- {len(config_files)} config files

Your task: Analyze the codebase and propose ONE focused, concrete improvement.

Constraints:
- Max 3 files per proposal
- Only modify: agents/, templates/prompts/, config/, memory/
- NEVER touch: scripts/, .github/workflows/
- Python stdlib only — no pip imports
- Branch name: feat/architect-YYYYMMDD-three-word-slug
- All file content must be COMPLETE (not diffs)

Respond with ONLY a valid JSON object matching this structure:
{{
  "title": "short imperative title (max 60 chars)",
  "description": "## Summary\nMarkdown content...",
  "branch_name": "feat/architect-...",
  "alignment_scores": {{
    "performance": 0.0,
    "security": 0.0,
    "maintainability": 0.0,
    "developer_experience": 0.0,
    "cost_efficiency": 0.0
  }},
  "files": [
    {{
      "path": "agents/example.py",
      "content": "full file content...",
      "reason": "why changed"
    }}
  ],
  "goals": ["goal1", "goal2"]
}}

Focus on: bug fixes, error handling, prompt improvements, security, performance.
"""
    
    response = call_llm(
        system="You are the Architect — GitClaw's autonomous improvement engine.",
        user_message=analysis_prompt,
        temperature=0.7
    )
    
    return response


def main():
    """
    Main entry point: analyze codebase and propose improvements.
    """
    log_event("architect", "start", "Analyzing codebase for improvements")
    
    # Get codebase analysis and proposal from LLM
    proposal_response = analyze_codebase()
    
    # Extract JSON from response (handle markdown code blocks)
    proposal_json = proposal_response
    if "```json" in proposal_response:
        proposal_json = proposal_response.split("```json")[1].split("```")[0].strip()
    elif "```" in proposal_response:
        proposal_json = proposal_response.split("```")[1].split("```")[0].strip()
    
    # Validate proposal
    proposal = validate_proposal(proposal_json)
    if not proposal:
        log_event(
            "architect",
            "error",
            "Proposal validation failed",
            {"response_length": len(proposal_response)}
        )
        return
    
    log_event(
        "architect",
        "info",
        f"Valid proposal: {proposal['title']}",
        {"branch": proposal["branch_name"], "files": len(proposal["files"])}
    )
    
    # Create proposal branch
    if create_proposal_branch(proposal):
        log_event(
            "architect",
            "complete",
            "Proposal created successfully",
            {
                "title": proposal["title"],
                "branch": proposal["branch_name"],
                "alignment": proposal["alignment_scores"]
            }
        )
    else:
        log_event(
            "architect",
            "error",
            "Failed to create proposal branch"
        )


if __name__ == "__main__":
    main()
