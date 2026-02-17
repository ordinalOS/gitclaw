<p align="center">
  <h1 align="center">🦞 GitClaw</h1>
  <p align="center">
    <strong>AGI in GitHub.</strong><br>
    A self-improving AI agent that lives entirely in GitHub Actions.<br>
    No servers. No binaries. The repo is the agent.
  </p>
</p>

<p align="center">
  <a href="#-3-step-setup">Setup</a> &middot;
  <a href="#-agents">Agents</a> &middot;
  <a href="#-commands">Commands</a> &middot;
  <a href="#-architect--council">Architect</a> &middot;
  <a href="#-how-it-works">How It Works</a> &middot;
  <a href="#%EF%B8%8F-configuration">Config</a>
</p>

---

**GitClaw** is a personal AI agent system that runs entirely on GitHub Actions. Fork it, add one secret, and you have an autonomous agent that:

- 🏗️ **Proposes code improvements** as PRs — reviewed by a Council of 7 AI personas
- ☕ Summarizes your issues with sarcastic coffee commentary every morning
- ⚔️ Turns bug reports into RPG quests with XP rewards
- 🃏 Reviews your PRs with theatrical comedy (and roasts files on demand)
- 🔍 Researches any topic with entertaining tangents
- 📺 Builds a live GitHub Pages dashboard with agent stats and memory browser
- 💅 Runs weekly QA audits to find bugs and broken config

Every thought is a git commit. The repo **is** the agent.

**25 agents** across 5 plugins — all running on GitHub Actions free tier.

---

## 🚀 3-Step Setup

### Step 1: Fork

Click **Fork** → Create your own GitClaw instance.

### Step 2: Add API Key

Go to **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:

| Secret | Value | Get it from |
|--------|-------|-------------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key | [console.anthropic.com](https://console.anthropic.com/) |

### Step 3: Enable Actions

Go to **Actions** tab → Click **"I understand my workflows, go ahead and enable them"** → Run the **🦞 GitClaw Setup** workflow.

**That's it. GitClaw is alive.**

> **Recommended:** Also go to **Settings** → **Actions** → **General** → check **"Allow GitHub Actions to create and approve pull requests"** (required for Architect & Council).

<details>
<summary><strong>Optional: GitHub Pages</strong></summary>

Go to **Settings** → **Pages** → Source: `Deploy from a branch` → Branch: `main` / `docs`

Your dashboard will be at `https://<user>.github.io/<repo>/`
</details>

<details>
<summary><strong>Optional: Plugin API Keys</strong></summary>

| Secret | For | Free Tier |
|--------|-----|-----------|
| `OPENAI_API_KEY` | LLM fallback | Pay-per-use |
| `GNEWS_API_KEY` | News Ninja | 100 req/day |
| `ALPHA_VANTAGE_KEY` | Stock Wizard | 25 req/day |
| `SOLANA_RPC_URL` | Solana agents | Varies |

HN Scraper and Crypto Oracle use free public APIs — no keys needed.
</details>

---

## 🤖 Agents

### Core (6) — Always Active

| Agent | Trigger | What It Does |
|-------|---------|-------------|
| ☕ **Morning Roast** | Weekdays 9 AM UTC | Sarcastic issue digest with fortune of the day |
| ⚔️ **Quest Master** | New issues opened | Gamifies issues into RPG quests with XP |
| 🃏 **Code Jester** | New PRs + `/roast` | PR review with theatrical comedy + roast mode |
| 🔍 **Wild Fact Finder** | `/research <topic>` | Entertaining research briefs with tangents |
| 📜 **Lore Keeper** | `/lore <topic>` | Chronicles knowledge as dramatic saga entries |
| 🎉 **Hype Man** | Issue closed / PR merged | Over-the-top victory celebrations with XP |

### Market & News Plugin (4) — Enable in `agent.md`

| Agent | Trigger | What It Does |
|-------|---------|-------------|
| 📰 **HN Hype Buster** | `/hn` + Daily 7 AM | Hacker News stories with hype scores |
| 🥷 **News Ninja** | `/news` + Daily 7:30 AM | Global news analysis with ninja-style delivery |
| 🔮 **Crypto Oracle** | `/crypto <coin>` | Crypto quant analysis — RSI, SMA, volatility |
| 🧙 **Stock Wizard** | `/stock <ticker>` | Stock quant analysis — SMA, RSI, MACD |

### Solana Plugin (3) — Enable in `agent.md`

| Agent | Trigger | What It Does |
|-------|---------|-------------|
| 🌐 **Solana Query** | `/sol <cmd>` | Dexscreener prices, RPC balances, Jupiter quotes |
| 📡 **Solana Monitor** | Every 6 hours | Tracks wallet balances and token prices |
| 🔨 **Solana Builder** | `/build-sbf` | Verifiable Solana program builds |

### Architect & Council Plugin (10) — Enable in `agent.md`

| Agent | Trigger | What It Does |
|-------|---------|-------------|
| 🏗️ **Architect** | Daily 6 AM + `/propose` | Analyzes repo, proposes code improvements as PRs |
| 🔍 **Proposal Lint** | Architect PRs | Validates Python + YAML before council review |
| 👓 **Zuckerberg** | Architect PRs | "Move fast" — velocity-focused reviewer |
| 💰 **Mr. Wonderful** | Architect PRs | ROI-obsessed dealmaker reviewer |
| 🚀 **Musk** | Architect PRs | First principles, 10x ambition reviewer |
| ⚡ **Toly** | Architect PRs | Throughput-obsessed reviewer |
| ₿ **Satoshi** | Architect PRs | Minimalist, trustless reviewer |
| 🕵️ **CIA** | Architect PRs | OPSEC-focused classified reviewer |
| 🎸 **Cobain** | Architect PRs | Anti-bloat punk reviewer |
| 💅 **Karen** | Mondays + `/karen` + PRs | QA compliance — audits memory, finds bugs |

### Infrastructure (2)

| Agent | Trigger | What It Does |
|-------|---------|-------------|
| 📺 **Pages Builder** | Every 4h + on memory push | Builds live GitHub Pages dashboard |
| 💓 **Heartbeat** | Daily midnight | Updates state, maintains streaks |

---

## 🏗️ Architect & Council

The **self-improving pipeline** — GitClaw's most powerful feature:

```
  🏗️ Architect (Daily 6 AM or /propose)
  Analyzes repo → generates proposal → creates PR
                    ▼
  🔍 Proposal Lint — validates syntax
                    ▼
  ⚖️ Council of 7 — each posts VOTE: APPROVE/REJECT/REVISE
  👓 Zuckerberg  💰 Wonderful  🚀 Musk  ⚡ Toly
  ₿ Satoshi     🕵️ CIA        🎸 Cobain
                    ▼
  📊 Tally: 4+ approves → merge  │  4+ rejects → close
```

**Safety:** The Architect cannot modify `scripts/`, its own workflow, or council workflows.

---

## 💬 Commands

Post these in any issue comment:

```
/research <topic>    — Research anything with entertaining flair
/lore <topic>        — Chronicle knowledge in the repo's saga
/roast <file>        — Brutally honest code roast (via Code Jester)
/propose [hint]      — Ask the Architect to propose an improvement
/karen               — Summon the QA manager for an audit
/help                — Show all commands
```

**Plugin commands** (enable in `agent.md`):
```
/hn top|search|trending    — Hacker News analysis
/news <topic>              — Global news intelligence
/crypto <coin>             — Crypto quant analysis
/stock <ticker>            — Stock quant analysis
/sol price|balance|quote   — Solana on-chain data
/build-sbf [path]          — Build Solana program
```

---

## 🧠 How It Works

```
  Triggers (issues, PRs, schedule, /commands)
                    ▼
  Command Router → dispatches to agent workflows
                    ▼
  Agent (Python or Shell) → calls LLM API
                    ▼
  Response → posted as comment, PR review, or issue
                    ▼
  Memory → git-committed to memory/ directory
                    ▼
  Pages Builder → rebuilds dashboard from memory data
```

**The key insight:** GitHub Actions IS the runtime. Git IS the database. Issues ARE the interface.

---

## ⚙️ Configuration

### `agent.md` — Feature Flags

The single source of truth for which agents are active:

```md
enable: morning-roast     # ☕ Daily digest + fortune
enable: quest-master      # ⚔️ Issue gamification
enable: code-jester       # 🃏 PR review + /roast
enable: research          # 🔍 Wild Fact Finder
enable: lore-keeper       # 📜 Knowledge chronicles
enable: hype-man          # 🎉 Celebrations
enable: architect         # 🏗️ Autonomous proposals
enable: council           # ⚖️ Council of 7
enable: pages-builder     # 📺 Dashboard
enable: karen             # 💅 QA compliance
# enable: hn-scraper      # 📰 HN digest
# enable: news-scraper    # 🥷 News intelligence
# enable: crypto-quant    # 🔮 Crypto analysis
# enable: stock-quant     # 🧙 Needs ALPHA_VANTAGE_KEY
# enable: solana           # 🌐 On-chain data
```

### Key Files

| File | Purpose |
|------|---------|
| `agent.md` | Enable/disable agents |
| `config/agents.yml` | Agent registry — names, schedules, prompts |
| `config/settings.yml` | Rate limits, XP rewards, LLM settings |
| `config/plugins.yml` | Plugin metadata and secrets |
| `templates/prompts/` | System prompts — the "soul" of each agent |

---

## 🎮 Gamification

| Level | XP | Title |
|-------|-----|-------|
| 0 | 0 | Unawakened |
| 1 | 50 | Novice |
| 2 | 150 | Apprentice |
| 3 | 300 | Journeyman |
| 4 | 500 | Adept |
| 5 | 800 | Expert |
| 6 | 1,200 | Master |
| 7 | 1,800 | Grandmaster |
| 8 | 2,500 | Legend |
| 9 | 5,000 | Mythic |
| 10 | 10,000 | Transcendent |

---

## 💰 Cost

Designed for **free-tier**:

| Resource | Free Tier | Usage |
|----------|-----------|-------|
| **GitHub Actions** | 2,000 min/month | ~10-40 min/day |
| **Anthropic API** | Pay-per-use | ~$1-5/month (Haiku default) |
| **CoinGecko, HN** | Free | Unlimited |

---

## 🔒 Security

- API keys in **GitHub Secrets** only
- **Hardened** against shell injection — no `${{ }}` in `run:` blocks
- Architect has **protected paths** — cannot modify scripts or its own workflow
- All Solana interactions are **read-only**
- Bot identity for all commits (`gitclaw[bot]`)

---

## 📜 License

MIT License. Fork it, customize it, make it yours.

---

<p align="center">
  <em>🦞 GitClaw — AGI in GitHub. I live in your repo. I commit my thoughts. I never sleep.</em>
</p>
