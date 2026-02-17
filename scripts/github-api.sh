#!/usr/bin/env bash
# ============================================================================
# github-api.sh — GitClaw's hands and mouth
# Wraps GitHub REST API calls for posting comments, creating labels,
# managing issues/PRs, and other repo interactions.
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/utils.sh"

# These are auto-set in GitHub Actions
GITHUB_TOKEN="${GITHUB_TOKEN:-}"
GITHUB_REPOSITORY="${GITHUB_REPOSITORY:-}"
GITHUB_API="https://api.github.com"

# ---------------------------------------------------------------------------
# post_comment <issue_number> <body>
# ---------------------------------------------------------------------------
post_comment() {
  local issue_number="${1:?Usage: post_comment <issue_number> <body>}"
  local body="${2:?}"

  curl -sS --fail-with-body \
    -X POST \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github.v3+json" \
    "$GITHUB_API/repos/$GITHUB_REPOSITORY/issues/$issue_number/comments" \
    -d "$(jq -n --arg body "$body" '{body: $body}')" > /dev/null

  log_info "Posted comment on issue #$issue_number"
}

# ---------------------------------------------------------------------------
# post_review_comment <pr_number> <body>
# ---------------------------------------------------------------------------
post_review_comment() {
  local pr_number="${1:?Usage: post_review_comment <pr_number> <body>}"
  local body="${2:?}"

  curl -sS --fail-with-body \
    -X POST \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github.v3+json" \
    "$GITHUB_API/repos/$GITHUB_REPOSITORY/pulls/$pr_number/reviews" \
    -d "$(jq -n --arg body "$body" '{body: $body, event: "COMMENT"}')" > /dev/null

  log_info "Posted review on PR #$pr_number"
}

# ---------------------------------------------------------------------------
# add_labels <issue_number> <label1> [label2] ...
# ---------------------------------------------------------------------------
add_labels() {
  local issue_number="${1:?Usage: add_labels <issue_number> <label1> [label2...]}"
  shift
  local labels=("$@")

  local labels_json
  labels_json=$(printf '%s\n' "${labels[@]}" | jq -R . | jq -s .)

  curl -sS --fail-with-body \
    -X POST \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github.v3+json" \
    "$GITHUB_API/repos/$GITHUB_REPOSITORY/issues/$issue_number/labels" \
    -d "$(jq -n --argjson labels "$labels_json" '{labels: $labels}')" > /dev/null

  log_info "Added labels to issue #$issue_number: ${labels[*]}"
}

# ---------------------------------------------------------------------------
# remove_label <issue_number> <label>
# ---------------------------------------------------------------------------
remove_label() {
  local issue_number="${1:?}" label="${2:?}"

  curl -sS --fail-with-body \
    -X DELETE \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github.v3+json" \
    "$GITHUB_API/repos/$GITHUB_REPOSITORY/issues/$issue_number/labels/$label" > /dev/null 2>&1 || true

  log_info "Removed label '$label' from issue #$issue_number"
}

# ---------------------------------------------------------------------------
# create_issue <title> <body> [labels_csv]
# ---------------------------------------------------------------------------
create_issue() {
  local title="${1:?Usage: create_issue <title> <body> [labels_csv]}"
  local body="${2:?}"
  local labels_csv="${3:-}"

  local labels_json="[]"
  if [[ -n "$labels_csv" ]]; then
    labels_json=$(echo "$labels_csv" | tr ',' '\n' | jq -R . | jq -s .)
  fi

  local response
  response=$(curl -sS --fail-with-body \
    -X POST \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github.v3+json" \
    "$GITHUB_API/repos/$GITHUB_REPOSITORY/issues" \
    -d "$(jq -n \
      --arg title "$title" \
      --arg body "$body" \
      --argjson labels "$labels_json" \
      '{title: $title, body: $body, labels: $labels}')")

  echo "$response" | jq -r '.number'
}

# ---------------------------------------------------------------------------
# get_issue <issue_number>
# ---------------------------------------------------------------------------
get_issue() {
  local issue_number="${1:?Usage: get_issue <issue_number>}"

  curl -sS --fail-with-body \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github.v3+json" \
    "$GITHUB_API/repos/$GITHUB_REPOSITORY/issues/$issue_number"
}

# ---------------------------------------------------------------------------
# get_open_issues [label_filter] [limit]
# ---------------------------------------------------------------------------
get_open_issues() {
  local label="${1:-}"
  local limit="${2:-30}"

  local url="$GITHUB_API/repos/$GITHUB_REPOSITORY/issues?state=open&per_page=$limit"
  if [[ -n "$label" ]]; then
    url="${url}&labels=$label"
  fi

  curl -sS --fail-with-body \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github.v3+json" \
    "$url"
}

# ---------------------------------------------------------------------------
# get_pr_diff <pr_number>
# ---------------------------------------------------------------------------
get_pr_diff() {
  local pr_number="${1:?Usage: get_pr_diff <pr_number>}"

  curl -sS --fail-with-body \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github.v3.diff" \
    "$GITHUB_API/repos/$GITHUB_REPOSITORY/pulls/$pr_number"
}

# ---------------------------------------------------------------------------
# get_pr_files <pr_number>
# ---------------------------------------------------------------------------
get_pr_files() {
  local pr_number="${1:?Usage: get_pr_files <pr_number>}"

  curl -sS --fail-with-body \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github.v3+json" \
    "$GITHUB_API/repos/$GITHUB_REPOSITORY/pulls/$pr_number/files"
}

# ---------------------------------------------------------------------------
# add_reaction <comment_id> <reaction>
# Reactions: +1, -1, laugh, confused, heart, hooray, rocket, eyes
# ---------------------------------------------------------------------------
add_reaction() {
  local comment_id="${1:?}" reaction="${2:?}"

  curl -sS --fail-with-body \
    -X POST \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github.v3+json" \
    "$GITHUB_API/repos/$GITHUB_REPOSITORY/issues/comments/$comment_id/reactions" \
    -d "$(jq -n --arg r "$reaction" '{content: $r}')" > /dev/null 2>&1 || true
}

# ---------------------------------------------------------------------------
# ensure_labels — creates GitClaw's label set if they don't exist
# ---------------------------------------------------------------------------
ensure_labels() {
  local labels=(
    "quest:new|🟢|New quest awaits"
    "quest:active|🔵|Quest in progress"
    "quest:complete|🟡|Quest completed"
    "quest:legendary|🟣|Legendary difficulty"
    "gitclaw:roast|☕|Morning roast target"
    "gitclaw:research|🔍|Research request"
    "gitclaw:lore|📜|Lore entry"
    "gitclaw:roast-request|🔥|Code roast request"
    "xp:10|⭐|10 XP reward"
    "xp:25|⭐|25 XP reward"
    "xp:50|⭐|50 XP reward"
    "xp:100|💎|100 XP reward"
  )

  local colors=("2ea44f" "0969da" "e3b341" "8957e5" "6f4e37" "1f6feb" "d4a373" "7b2d8b" "bf5700")

  local i=0
  for label_def in "${labels[@]}"; do
    IFS='|' read -r name emoji description <<< "$label_def"
    local color="${colors[$((i % ${#colors[@]}))]}"

    curl -sS \
      -X POST \
      -H "Authorization: token $GITHUB_TOKEN" \
      -H "Accept: application/vnd.github.v3+json" \
      "$GITHUB_API/repos/$GITHUB_REPOSITORY/labels" \
      -d "$(jq -n \
        --arg name "$name" \
        --arg desc "$emoji $description" \
        --arg color "$color" \
        '{name: $name, description: $desc, color: $color}')" > /dev/null 2>&1 || true

    i=$((i + 1))
  done

  log_info "GitClaw labels ensured"
}

# Allow sourcing or direct execution
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  "${1:?Usage: github-api.sh <function_name> [args...]}" "${@:2}"
fi
