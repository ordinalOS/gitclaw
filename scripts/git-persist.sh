#!/usr/bin/env bash
# ============================================================================
# git-persist.sh — GitClaw's memory backbone
# Handles committing agent state/memory changes back to the repo.
# The repo IS the database. Every thought is a commit.
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/utils.sh"

REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"

# ---------------------------------------------------------------------------
# persist <file_path> <commit_message> [branch]
#
# Stages a file, commits, and pushes. Used by agents to save state.
# Uses the GitHub Actions bot identity for commits.
# ---------------------------------------------------------------------------
persist() {
  local file_path="${1:?Usage: persist <file_path> <commit_message> [branch]}"
  local commit_message="${2:?}"
  local branch="${3:-main}"

  cd "$REPO_ROOT"

  # Configure git identity (GitHub Actions bot)
  git config user.name "gitclaw[bot]"
  git config user.email "gitclaw[bot]@users.noreply.github.com"

  # Pull latest to avoid conflicts
  git pull --rebase origin "$branch" 2>/dev/null || true

  # Stage and commit
  git add "$file_path"

  if git diff --cached --quiet; then
    log_info "No changes to persist for: $file_path"
    return 0
  fi

  git commit -m "🧠 $commit_message" \
    --author="gitclaw[bot] <gitclaw[bot]@users.noreply.github.com>"

  # Push with retry (handles race conditions from parallel workflows)
  local retries=5
  # Random jitter (0-3s) to spread out parallel pushes
  sleep "$((RANDOM % 4))"
  for i in $(seq 1 $retries); do
    if git push origin "$branch" 2>/dev/null; then
      log_info "Persisted: $file_path"
      return 0
    fi
    log_warn "Push attempt $i/$retries failed, rebasing and retrying..."
    if ! git pull --rebase origin "$branch" 2>/dev/null; then
      # Rebase conflict — auto-resolve state.json by re-applying update
      git checkout --theirs memory/state.json 2>/dev/null || true
      git add memory/state.json 2>/dev/null || true
      GIT_EDITOR=true git rebase --continue 2>/dev/null || {
        git rebase --abort 2>/dev/null || true
        git pull origin "$branch" --no-edit 2>/dev/null || true
      }
    fi
    sleep "$((i * 2 + RANDOM % 3))"
  done

  log_error "Failed to persist after $retries attempts: $file_path"
  return 1
}

# ---------------------------------------------------------------------------
# persist_many <commit_message> <file1> [file2] [file3] ...
#
# Batch persist multiple files in a single commit.
# ---------------------------------------------------------------------------
persist_many() {
  local commit_message="${1:?Usage: persist_many <commit_message> <file1> [file2...]}"
  shift
  local files=("$@")

  cd "$REPO_ROOT"

  git config user.name "gitclaw[bot]"
  git config user.email "gitclaw[bot]@users.noreply.github.com"

  git pull --rebase origin main 2>/dev/null || true

  for f in "${files[@]}"; do
    git add "$f"
  done

  if git diff --cached --quiet; then
    log_info "No changes to persist"
    return 0
  fi

  git commit -m "🧠 $commit_message" \
    --author="gitclaw[bot] <gitclaw[bot]@users.noreply.github.com>"

  local retries=5
  sleep "$((RANDOM % 4))"
  for i in $(seq 1 $retries); do
    if git push origin main 2>/dev/null; then
      log_info "Persisted batch"
      return 0
    fi
    log_warn "Batch push attempt $i/$retries failed, retrying..."
    if ! git pull --rebase origin main 2>/dev/null; then
      git checkout --theirs memory/state.json 2>/dev/null || true
      git add memory/state.json 2>/dev/null || true
      GIT_EDITOR=true git rebase --continue 2>/dev/null || {
        git rebase --abort 2>/dev/null || true
        git pull origin main --no-edit 2>/dev/null || true
      }
    fi
    sleep "$((i * 2 + RANDOM % 3))"
  done
  log_error "Failed to persist batch after $retries attempts"
  return 1
}

# ---------------------------------------------------------------------------
# update_state <jq_expression>
#
# Atomically update memory/state.json using a jq expression.
# Example: update_state '.xp += 10 | .level = "Apprentice"'
# ---------------------------------------------------------------------------
update_state() {
  local jq_expr="${1:?Usage: update_state <jq_expression>}"
  local state_file="$REPO_ROOT/memory/state.json"

  # Ensure state file exists
  if [[ ! -f "$state_file" ]]; then
    echo '{}' > "$state_file"
  fi

  local updated
  updated=$(jq "$jq_expr" "$state_file")
  echo "$updated" > "${state_file}.tmp"
  mv "${state_file}.tmp" "$state_file"

  log_info "State updated: $jq_expr"
}

# ---------------------------------------------------------------------------
# append_memory <category> <filename> <content>
#
# Appends content to a memory file (e.g., lore, dreams, research).
# Creates the file if it doesn't exist.
# ---------------------------------------------------------------------------
append_memory() {
  local category="${1:?Usage: append_memory <category> <filename> <content>}"
  local filename="${2:?}"
  local content="${3:?}"

  local target_dir="$REPO_ROOT/memory/$category"
  mkdir -p "$target_dir"

  local target_file="$target_dir/$filename"
  local timestamp
  timestamp="$(date -u +"%Y-%m-%d %H:%M:%S UTC")"

  {
    echo ""
    echo "---"
    echo "**[$timestamp]**"
    echo ""
    echo "$content"
  } >> "$target_file"

  log_info "Appended to memory/$category/$filename"
}

# Ensure git identity is always configured when this script is sourced
# Prevents "Committer identity unknown" errors in any workflow
if [[ -z "$(git config user.name 2>/dev/null)" ]]; then
  git config user.name "gitclaw[bot]" 2>/dev/null || true
  git config user.email "gitclaw[bot]@users.noreply.github.com" 2>/dev/null || true
fi

# Allow sourcing or direct execution
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  "${1:?Usage: git-persist.sh <persist|persist_many|update_state|append_memory> [args...]}" "${@:2}"
fi
