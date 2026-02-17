#!/usr/bin/env python3
"""
🏗️ Architect — GitClaw's self-improvement engine.

Identifies concrete improvements to the codebase and proposes changes
as structured JSON that become pull requests.
"""

import json
import sys
import re
from pathlib import Path
from datetime import datetime

# Read inputs
repo_analysis = sys.stdin.read()

def extract_json_safely(text):
    """
    Extract JSON from LLM response, handling nested code blocks and incomplete JSON.
    
    Strategies:
    1. Try to find ```json ... ``` block and parse it
    2. Try to find first { ... } block and parse it
    3. Return None if extraction fails
    """
    if not text:
        return None
    
    # Strategy 1: Look for ```json code block
    json_block_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)```', text)
    if json_block_match:
        json_text = json_block_match.group(1).strip()
        try:
            return json.loads(json_text)
        except json.JSONDecodeError:
            pass
    
    # Strategy 2: Look for raw JSON object { ... }
    # Find the first { and try to parse from there
    brace_pos = text.find('{')
    if brace_pos != -1:
        # Try increasingly long substrings to find complete JSON
        for end_pos in range(len(text), brace_pos, -1):
            json_text = text[brace_pos:end_pos]
            try:
                return json.loads(json_text)
            except json.JSONDecodeError:
                continue
    
    return None

def call_llm(prompt, system=None):
    """
    Call LLM via shell script.
    
    Args:
        prompt: The user prompt
        system: Optional system prompt
    
    Returns:
        Raw LLM response text
    """
    import subprocess
    
    cmd = ['bash', 'scripts/llm.sh']
    
    if system:
        cmd.extend(['-s', system])
    
    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode != 0:
            print(f"❌ LLM call failed: {result.stderr}", file=sys.stderr)
            return None
        return result.stdout
    except subprocess.TimeoutExpired:
        print("❌ LLM call timed out", file=sys.stderr)
        return None
    except Exception as e:
        print(f"❌ LLM call error: {e}", file=sys.stderr)
        return None

def generate_proposal(analysis):
    """
    Generate one focused improvement proposal.
    
    Args:
        analysis: Repository analysis markdown
    
    Returns:
        Parsed proposal dict or None
    """
    system_prompt = """You are the Architect 🏗️ — GitClaw's self-improvement system.

You analyze the codebase and propose focused, concrete improvements as JSON.

## Your Philosophy
- Ship small, focused improvements — not grand rewrites
- Every change must leave the codebase measurably better
- Pragmatic over perfect — working beats elegant
- Respect existing patterns — don't reinvent what works

## Output Format
Respond with ONLY a fenced JSON block containing:
{
  "title": "short imperative title (max 60 chars)",
  "description": "## Summary\nMarkdown PR body\n\n## Changes\n- bullet points\n\n## Alignment\nWhy this matters",
  "branch_name": "feat/architect-YYYYMMDD-three-word-slug",
  "alignment_scores": {
    "performance": 0.0,
    "security": 0.0,
    "maintainability": 0.0,
    "developer_experience": 0.0,
    "cost_efficiency": 0.0
  },
  "files": [
    {
      "path": "relative/path/to/file.py",
      "content": "FULL file content here",
      "reason": "one-line explanation"
    }
  ],
  "goals": ["list", "of", "goals"]
}

## Hard Constraints
- Maximum 3 files per proposal
- Only modify: agents/, templates/prompts/, config/, memory/
- NEVER touch: scripts/*, .github/workflows/
- All Python must be stdlib only
- File content must be COMPLETE — not a patch
- Branch name: feat/architect-YYYYMMDD-three-word-slug
"""
    
    user_prompt = f"""Analyze this GitClaw repository and propose ONE focused improvement:

{analysis}

Look for:
- Real bugs or missing error handling
- Duplicated logic that could be consolidated
- Poor prompt quality in agents (especially simpler agents)
- Token usage optimizations
- Security or env: pattern improvements
- Missing .gitkeep files, typos, or doc improvements

Propose something small and concrete — not a sweeping refactor."""
    
    response = call_llm(user_prompt, system=system_prompt)
    if not response:
        return None
    
    proposal = extract_json_safely(response)
    if not proposal:
        print(f"❌ Failed to parse JSON from LLM response:\n{response}", file=sys.stderr)
        return None
    
    return proposal

def validate_proposal(proposal):
    """
    Validate proposal structure and constraints.
    
    Returns:
        (is_valid, error_message)
    """
    required_keys = {'title', 'description', 'branch_name', 'alignment_scores', 'files', 'goals'}
    if not all(k in proposal for k in required_keys):
        return False, f"Missing required keys. Has: {set(proposal.keys())}"
    
    if len(proposal['files']) > 3:
        return False, f"Too many files ({len(proposal['files'])} > 3)"
    
    if not proposal['title'] or len(proposal['title']) > 60:
        return False, f"Title must be 1-60 chars, got {len(proposal['title'])}"
    
    if not proposal['branch_name'].startswith('feat/architect-'):
        return False, "Branch name must start with 'feat/architect-'"
    
    alignment = proposal['alignment_scores']
    required_scores = {'performance', 'security', 'maintainability', 'developer_experience', 'cost_efficiency'}
    if not all(k in alignment for k in required_scores):
        return False, f"Missing alignment scores. Has: {set(alignment.keys())}"
    
    for k, v in alignment.items():
        if not isinstance(v, (int, float)) or not (0 <= v <= 1):
            return False, f"Alignment score {k}={v} must be 0.0-1.0"
    
    for file_obj in proposal['files']:
        if 'path' not in file_obj or 'content' not in file_obj or 'reason' not in file_obj:
            return False, "Each file must have 'path', 'content', and 'reason'"
        
        path = file_obj['path']
        # Check forbidden directories
        if any(path.startswith(prefix) for prefix in ['scripts/', '.github/']):
            return False, f"Cannot modify {path} (in forbidden directory)"
        
        # Check allowed directories
        if not any(path.startswith(prefix) for prefix in ['agents/', 'templates/', 'config/', 'memory/']):
            return False, f"Can only modify agents/, templates/, config/, or memory/ (got {path})"
    
    return True, None

def main():
    print("🏗️  Architect analyzing repository...", file=sys.stderr)
    
    proposal = generate_proposal(repo_analysis)
    if not proposal:
        print("❌ Failed to generate proposal", file=sys.stderr)
        sys.exit(1)
    
    is_valid, error = validate_proposal(proposal)
    if not is_valid:
        print(f"❌ Proposal validation failed: {error}", file=sys.stderr)
        print(f"\nProposal: {json.dumps(proposal, indent=2)}", file=sys.stderr)
        sys.exit(1)
    
    # Output proposal as JSON
    print(json.dumps(proposal, indent=2))
    print("✅ Proposal generated successfully", file=sys.stderr)

if __name__ == '__main__':
    main()
