# 🦞 GitClaw Setup Guide

Getting your AI agent alive and kicking in under 5 minutes.

## Prerequisites

- A GitHub account (free tier works!)
- An API key from [Anthropic](https://console.anthropic.com/) or [OpenAI](https://platform.openai.com/)

## Step 1: Fork the Repo

Click the **Fork** button on the GitClaw repo. This creates your own copy where your agent will live.

## Step 2: Add Secrets

Go to your forked repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.

Add at least one:

| Secret Name | Value | Required |
|-------------|-------|----------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key (starts with `sk-ant-`) | Yes* |
| `OPENAI_API_KEY` | Your OpenAI API key (starts with `sk-`) | No* |

*At least one is required. Anthropic is recommended (GitClaw's prompts are optimized for Claude).

## Step 3: Enable GitHub Actions

1. Go to the **Actions** tab in your forked repo
2. Click **"I understand my workflows, go ahead and enable them"**
3. All workflows are now active

## Step 4: Run Setup

1. Go to **Actions** → **🦞 GitClaw Setup**
2. Click **Run workflow**
3. Choose your persona:
   - **default** — Friendly and witty
   - **pirate** — Arrr, matey!
   - **wizard** — Arcane code wisdom
   - **meme_lord** — Peak internet culture
   - **butler** — Very distinguished
4. Click **Run workflow**

This creates labels, initializes state, and opens a welcome issue.

## Step 5: Test It

Open any issue in your repo and comment:

```
/help
```

GitClaw should respond with the command list. Try:

```
/research why do programmers hate meetings
```

## Configuration

### Change Persona

Edit `config/personality.yml` and change `active_persona` to any preset, or customize the `traits` directly.

### Adjust Schedule

Edit the cron expressions in the workflow files:

- `morning-roast.yml` — Default: `0 9 * * 1-5` (9 AM UTC, weekdays)
- `heartbeat.yml` — Default: `0 0 * * *` (midnight UTC, daily)

### Change LLM Model

Set environment variables in your workflow files or in `config/settings.yml`:

```yaml
llm:
  default_provider: "anthropic"
  default_model: "claude-haiku-4-5-20251001"
  fallback_model: "claude-haiku-4-5-20251001"
```

### Disable Agents

In `config/agents.yml`, set any agent to `enabled: false`.

### Rate Limits

In `config/settings.yml`, adjust:

```yaml
limits:
  max_llm_calls_per_hour: 20
  max_comments_per_issue: 5
  max_workflow_minutes_per_day: 30
```

## Troubleshooting

### Workflows aren't running

1. Check **Actions** tab → Make sure workflows are enabled
2. Check **Settings** → **Actions** → **General** → Ensure "Allow all actions" is selected
3. Check that secrets are correctly set (no trailing whitespace)

### API errors

1. Verify your API key is valid and has credits
2. Check the workflow run logs in the **Actions** tab
3. GitClaw has fallback responses when API calls fail

### Agent not responding to commands

1. Commands must start with `/` at the beginning of a comment
2. Only works in issue comments (not PR comments for some commands)
3. Check that the `command-router.yml` workflow is enabled

### Git persist errors

1. Go to **Settings** → **Actions** → **General**
2. Under "Workflow permissions", select **Read and write permissions**
3. Check "Allow GitHub Actions to create and approve pull requests"

## Cost Management

To minimize API costs:

1. Use Claude Haiku (`claude-haiku-4-5-20251001`) for simple agents (hype man, quest master)
2. Reduce schedule frequency if needed
3. Set strict rate limits in `config/settings.yml`
4. Disable unused agents in `config/agents.yml`

Free tier GitHub Actions gives you 2,000 minutes/month. GitClaw typically uses:
- Morning Roast: ~2 min/run × 5 days = 10 min/week
- Quest/Review: ~1 min/run × varies
- Commands: ~1 min/run × varies

Total: ~20-50 min/week under normal use.
