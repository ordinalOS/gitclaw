<p align="center">
  <h1 align="center">🦞 GitClaw</h1>
  <p align="center">
    <strong>Your AI agent that lives in GitHub.</strong><br>
    No servers. No binaries. No infrastructure.<br>
    Just workflows, commits, and vibes.
  </p>
</p>

<p align="center">
  <a href="#-quick-start">Quick Start</a> &middot;
  <a href="#%EF%B8%8F-setup-checklist">Setup</a> &middot;
  <a href="#-agents">Agents</a> &middot;
  <a href="#-commands">Commands</a> &middot;
  <a href="#-architect--council">Architect</a> &middot;
  <a href="#-how-it-works">How It Works</a> &middot;
  <a href="#%EF%B8%8F-configuration">Config</a>
</p>

---

**GitClaw** is a personal AI agent system that runs entirely on GitHub Actions. Fork this repo, configure your secrets and settings, and you have an autonomous second brain that:

- ☕ Summarizes your issues with sarcastic coffee commentary every morning
- ⚔️ Turns bug reports into RPG quests with XP rewards
- 🃏 Reviews your PRs with theatrical comedy (and actually useful feedback)
- 🔍 Researches any topic with entertaining tangents
- 🏗️ Autonomously proposes code improvements as PRs
- ⚖️ Reviews proposals through a Council of 7 AI personas who vote to merge or reject
- 📺 Builds a live GitHub Pages dashboard with agent stats, workflow runs, and memory browser
- 💅 Runs weekly QA audits to find bugs, empty values, and broken config

Your agent persists its memory by committing to the repo. Every thought is a git commit. The repo **is** the agent.

**29 agents** across 5 plugins — all running on GitHub Actions free tier.

---

## 🚀 Quick Start

### 1. Fork this repo

Click **Fork** → Create your own GitClaw instance.

### 2. Configure GitHub Settings

> **This is critical.** Without these settings, key agents (Architect, Council, Pages Builder) will fail.

Go to your forked repo → **Settings** → **Actions** → **General**:

| Setting | Value | Why |
|---------|-------|-----|
| **Workflow permissions** | `Read and write permissions` | Agents need to commit memory, push branches, post comments |
| **Allow GitHub Actions to create and approve pull requests** | ✅ Checked | Required for Architect to create PRs and Council to review them |

Then go to **Settings** → **Pages**:

| Setting | Value | Why |
|---------|-------|-----|
| **Source** | `Deploy from a branch` | |
| **Branch** | `main` / `docs` | Serves the GitClaw dashboard at `https://<user>.github.io/<repo>` |

### 3. Add Secrets

Go to **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:

#### Required

| Secret | Description | Get it from |
|--------|-------------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic API key — powers all LLM agents | [console.anthropic.com](https://console.anthropic.com/) |

> You need at least one LLM key. Anthropic (Claude) is primary. OpenAI is a fallback.

#### Optional — LLM

| Secret | Description | Get it from |
|--------|-------------|-------------|
| `OPENAI_API_KEY` | OpenAI API key — fallback if Anthropic is unavailable | [platform.openai.com](https://platform.openai.com/) |

#### Optional — Market & News Plugin

| Secret | Required? | Description | Get it from |
|--------|-----------|-------------|-------------|
| `GNEWS_API_KEY` | Optional | GNews API key for News Ninja agent | [gnews.io](https://gnews.io/) (free tier: 100 req/day) |
| `NEWSDATA_API_KEY` | Optional | NewsData.io key — News Ninja fallback source | [newsdata.io](https://newsdata.io/) (free tier: 200 req/day) |
| `ALPHA_VANTAGE_KEY` | Optional | Alpha Vantage key for Stock Wizard agent | [alphavantage.co](https://www.alphavantage.co/support/) (free tier: 25 req/day) |

> HN Scraper and Crypto Oracle use **free public APIs** (HN Algolia/Firebase, CoinGecko) — no keys needed.

#### Optional — Solana Plugin

| Secret | Required? | Description |
|--------|-----------|-------------|
| `SOLANA_RPC_URL` | Optional | Custom Solana RPC endpoint (Helius, Alchemy, etc.). Falls back to public RPC if not set. |

### 4. Enable Workflows

Go to **Actions** tab → Click **"I understand my workflows, go ahead and enable them"**.

### 5. Run Setup

Go to **Actions** → **🦞 GitClaw Setup** → **Run workflow** → Pick your persona → **Run**.

This initializes `memory/state.json`, creates labels, and boots the agent.

### 6. Activate Agents

Edit `agent.md` in the repo root to enable/disable plugins:

```md
## Core Features (enabled by default)
enable: morning-roast
enable: quest-master
enable: code-jester
enable: research
enable: lore-keeper
enable: dream-interpreter
enable: fortune-cookie
enable: hype-man
enable: roast-battle
enable: meme-machine

## Market & News Plugin
enable: hn-scraper
enable: news-scraper
enable: crypto-quant
# enable: stock-quant  # needs ALPHA_VANTAGE_KEY

## Architect & Council Plugin
enable: architect
enable: council
enable: pages-builder
enable: karen
```

### 7. Run Warmup (Optional)

Go to **Actions** → **🔥 Warmup** → **Run workflow** → scope: `all` → **Run**.

This triggers every agent with seed content — populating dreams, lore, research, roasts, HN, news, crypto, and kicking off the Architect/Council pipeline. Great for seeing everything work on day one.

---

## ✅️ Setup Checklist

After forking, make sure all of these are done:

- [ ] **GitHub Settings** → Actions → General → Workflow permissions → **Read and write**
- [ ] **GitHub Settings** → Actions → General → **Allow GitHub Actions to create and approve pull requests** ✅
- [ ] **GitHub Settings** → Pages → Source → **Deploy from branch** → `main` / `docs`
- [ ] **Secret added**: `ANTHROPIC_API_KEY` (required for all LLM agents)
- [ ] **Actions tab** → **Enable workflows** after fork
- [ ] **Run** the **🦞 GitClaw Setup** workflow (one-time init)
- [ ] **Edit** `agent.md` to enable desired plugins
- [ ] *(Optional)* **Run** the **🔥 Warmup** workflow to populate memory

---

## 🤖 Agents

GitClaw runs **29 agents** across 5 groups. All run autonomously via schedules and events — no manual intervention needed after setup.

### Core Agents (10) — Always Active

| Agent | Trigger | What It Does |
|-------|---------|-------------|
| ☕ **Morning Roast** | Weekdays 9 AM UTC | Sarcastic issue digest with coffee metaphors |
| ⚔️ **Quest Master** | New issues opened | Gamifies issues into RPG quests with XP |
| 🃏 **Code Jester** | New PRs opened | Theatrical PR review with real feedback |
| 🔍 **Wild Fact Finder** | `/research <topic>` | Entertaining research briefs with tangents |
| 🎨 **Meme Machine** | Manual dispatch | Generates viral content (tweets, blogs, memes) |
| 📜 **Lore Keeper** | `/lore <topic>` | Chronicles knowledge as dramatic saga entries |
| 🌙 **Dream Interpreter** | `/dream <desc>` | Interprets dreams through a coding lens |
| 🔮 **Fortune Cookie** | Daily 8 AM UTC | Cryptic coding wisdom and lucky numbers |
| 🎉 **Hype Man** | Issue closed / PR merged | Over-the-top victory celebrations with XP |
| 🔥 **Roast Battle** | `/roast <target>` | Brutally honest (but constructive!) code roasts |

### Market & News Plugin (4) — Enable in `agent.md`

| Agent | Trigger | API Keys | What It Does |
|-------|---------|----------|-------------|
| 📰 **HN Hype Buster** | `/hn <cmd>` + Daily 7 AM UTC | None (free API) | Hacker News stories with hype scores |
| 🥷 **News Ninja** | `/news <topic>` + Daily 7:30 AM UTC | `GNEWS_API_KEY` (optional) | Global news analysis with ninja-style delivery |
| 🔮 **Crypto Oracle** | `/crypto <coin>` | None (CoinGecko free) | Crypto quant analysis — RSI, SMA, volatility |
| 🧙 **Stock Wizard** | `/stock <ticker>` | `ALPHA_VANTAGE_KEY` (optional) | Stock quant analysis — SMA, RSI, MACD |

### Solana Plugin (3) — Enable in `agent.md`

| Agent | Trigger | What It Does |
|-------|---------|-------------|
| 🌐 **Solana Query** | `/sol <cmd>` | Dexscreener prices, RPC balances, Jupiter quotes |
| 📡 **Solana Monitor** | Every 6 hours | Tracks wallet balances and token prices |
| 🔨 **Solana Builder** | `/build-sbf` | Verifiable Solana program builds in Actions |

### Architect & Council Plugin (11) — Enable in `agent.md`

| Agent | Trigger | What It Does |
|-------|---------|-------------|
| 🏗️ **Architect** | Daily 6 AM UTC + `/propose` | Analyzes repo, proposes code improvements as PRs (uses Sonnet 4.5) |
| 🔍 **Proposal Lint** | Architect PRs opened | Validates Python syntax + YAML before council sees it |
| 👓 **Council: Zuckerberg** | Architect PRs | "Move fast and break things" — velocity-focused reviewer |
| 💰 **Council: Mr. Wonderful** | Architect PRs | ROI-obsessed Shark Tank dealmaker reviewer |
| 🚀 **Council: Musk** | Architect PRs | First principles, 10x ambition, contrarian reviewer |
| ⚡ **Council: Toly** | Architect PRs | Throughput-obsessed, parallel execution reviewer |
| ₿ **Council: Satoshi** | Architect PRs | Minimalist, trustless, privacy-focused reviewer |
| 🕵️ **Council: CIA** | Architect PRs | Classified briefing format, OPSEC reviewer |
| 🎸 **Council: Cobain** | Architect PRs | Anti-establishment, anti-bloat punk reviewer |
| 💅 **Karen** | Mondays 5 AM UTC + `/karen` + PRs | QA compliance officer — audits memory, finds bugs, files complaints |
| 📺 **Pages Builder** | Every 4h + on memory push | Builds the GitHub Pages dashboard from memory data |

### Infrastructure (2) — Always On

| Agent | Trigger | What It Does |
|-------|---------|-------------|
| 💓 **Heartbeat** | Daily midnight UTC | Updates state.json, maintains streaks |
| 🔥 **Warmup** | Sundays 3 AM UTC + manual | Triggers all agents to populate memory |

---

## 🏗️ Architect & Council

The **self-improving pipeline** — GitClaw's most powerful feature:

```
┌─────────────────────────────────────────────────────────────┐
│  🏗️ Architect (Daily 6 AM UTC or /propose)                 │
│  Analyzes repo → generates proposal → creates PR            │
│  Uses Claude Sonnet 4.5 for code-quality proposals          │
└────────────────────┬────────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  🔍 Proposal Lint                                           │
│  Validates Python syntax + YAML before council review       │
└────────────────────┬────────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  ⚖️ Council of 7 (auto-triggered on Architect PR)          │
│  Each persona reviews and posts: VOTE: APPROVE/REJECT/REVISE│
│                                                             │
│  👓 Zuckerberg  💰 Mr. Wonderful  🚀 Musk  ⚡ Toly         │
│  ₿ Satoshi     🕵️ CIA           🎸 Cobain                 │
└────────────────────┬────────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  📊 Vote Tally                                              │
│  4+ approves → auto-merge  │  4+ rejects → auto-close      │
└─────────────────────────────────────────────────────────────┘
```

**Requirements:**
- `ANTHROPIC_API_KEY` secret must be set
- "Allow GitHub Actions to create and approve pull requests" must be **enabled** in repo Settings → Actions → General
- `enable: architect` and `enable: council` in `agent.md`

**Safety:** The Architect cannot modify `scripts/`, its own workflow, or council workflows (protected paths).

---

## 📺 GitHub Pages Dashboard

GitClaw builds a live dashboard at `https://<user>.github.io/<repo>/`:

| Page | What It Shows |
|------|--------------|
| **Dashboard** | Quick stats (XP, commits, active agents, streak), recent activity feed, workflow runs, agent stats |
| **Memory** | Tabbed browser for dreams, lore, research, roasts, fortunes, HN, news, crypto, stocks |
| **Council** | Architect proposals with alignment scores, council reviews and votes |
| **Agents** | All 29 agents with status, schedules, commands, and workflow links |
| **Debug** | Raw state.json, git log, memory file inventory |
| **Blog** | Auto-generated from lore, research, and dream entries |

**Setup:** Settings → Pages → Source → `Deploy from a branch` → branch: `main`, folder: `/docs`

The dashboard rebuilds automatically every 4 hours, on every memory push, and via manual dispatch.

---

## 💬 Commands

Post these in any issue comment:

```
/research <topic>    — Research anything with entertaining flair
/lore <topic>        — Chronicle knowledge in the repo's saga
/dream <description> — Log and interpret a dream
/roast <file>        — Get a code roast (brutal but constructive)
/propose [hint]      — Ask the Architect to propose a code improvement
/karen               — Summon the QA manager for an audit
/help                — Show all commands
```

**Market & News commands** (enable in `agent.md`):
```
/hn top              — Top 10 HN stories with hype scores
/hn search <term>    — Search HN for a topic
/hn trending         — Trending stories by velocity
/news <topic>        — News analysis (supports: markets, tech, crypto)
/crypto <coin>       — Crypto quant analysis (e.g., /crypto bitcoin)
/crypto compare a b  — Compare two coins side-by-side
/crypto market       — Top 10 market overview
/stock <ticker>      — Stock quant analysis (e.g., /stock AAPL)
/stock compare a b   — Compare two stocks
/stock market        — Market overview (SPY, QQQ, DIA)
```

**Solana commands** (requires `enable: solana` in `agent.md`):
```
/sol price <token>           — Token price from Dexscreener
/sol balance <address>       — Wallet SOL balance via RPC
/sol quote <from> <to> <amt> — Jupiter v6 swap quote
/sol network                 — Solana network status & TPS
/build-sbf [path]            — Build Solana program (.so)
```

---

## 🧠 How It Works

```
┌─────────────────────────────────────────────────────────┐
│                     YOUR GITHUB REPO                     │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │  Issues   │  │   PRs    │  │ Schedule │  ← Triggers  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘              │
│       │              │              │                    │
│       ▼              ▼              ▼                    │
│  ┌──────────────────────────────────────┐               │
│  │       GitHub Actions Workflows       │  ← Engine     │
│  │  (command-router → agent workflows)  │               │
│  └────────────────┬─────────────────────┘               │
│                   │                                      │
│       ┌───────────┼───────────┐                         │
│       ▼           ▼           ▼                         │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐                   │
│  │ scripts/ │ │ agents/ │ │templates│  ← Logic          │
│  │ (shell)  │ │(python) │ │(prompts)│                   │
│  └────┬─────┘ └────┬────┘ └─────────┘                   │
│       │             │                                    │
│       ▼             ▼                                    │
│  ┌──────────────────────────┐                           │
│  │    LLM API (Anthropic    │  ← Brain                  │
│  │    or OpenAI)            │                           │
│  └────────────┬─────────────┘                           │
│               │                                          │
│               ▼                                          │
│  ┌──────────────────────────┐                           │
│  │  memory/ (git-persisted) │  ← Memory                 │
│  │  state.json, lore/,      │                           │
│  │  dreams/, research/...   │                           │
│  └──────────────────────────┘                           │
│               │                                          │
│               ▼                                          │
│  ┌──────────────────────────┐                           │
│  │  Git Commit (by bot)     │  ← Persistence            │
│  │  "🧠 Morning Roast"     │                           │
│  └──────────────────────────┘                           │
└─────────────────────────────────────────────────────────┘
```

**The key insight:** GitHub Actions IS the runtime. Git IS the database. Issues ARE the interface. No external infrastructure needed.

### Data Flow

1. **Trigger** — An event fires (issue opened, comment posted, cron schedule, PR created)
2. **Route** — `command-router.yml` parses `/commands` and dispatches to the right agent
3. **Process** — The agent workflow runs: reads context, calls the LLM, generates response
4. **Act** — Posts comments, adds labels, creates issues/PRs
5. **Persist** — Commits memory changes (state, lore, research) back to the repo
6. **Rebuild** — Pages Builder regenerates the dashboard from new memory data

---

## ⚙️ Configuration

### `agent.md` — Feature Flags

The single source of truth for which agents are active. Each `enable:` line activates an agent:

```md
enable: morning-roast     # ☕ Daily digest
enable: architect         # 🏗️ Autonomous code proposals
enable: council           # ⚖️ Council of 7 PR reviewers
enable: pages-builder     # 📺 GitHub Pages dashboard
enable: karen             # 💅 QA compliance officer
enable: hn-scraper        # 📰 Hacker News digest
enable: news-scraper      # 🥷 News intelligence
enable: crypto-quant      # 🔮 Crypto analysis
# enable: stock-quant     # 🧙 Needs ALPHA_VANTAGE_KEY
# enable: solana           # 🌐 Needs SOLANA_RPC_URL (optional)
# enable: solana-builder   # 🔨 Solana program builds
```

### `config/personality.yml` — Persona

Choose a preset or customize traits:

| Persona | Vibe |
|---------|------|
| `default` | Friendly, witty dev companion |
| `pirate` | Salty sea-dog who codes by starlight |
| `wizard` | Ancient code wizard dispensing arcane wisdom |
| `meme_lord` | Speaks entirely in meme references |
| `butler` | Distinguished British butler who happens to be an AI |

### `config/agents.yml` — Agent Registry

Fine-tune individual agents: change names, descriptions, schedules, enable/disable.

### `config/settings.yml` — Global Settings

Control rate limits, XP rewards, feature flags, and LLM settings.

---

## 🏗️ Architecture

```
gitclaw/
├── .github/workflows/          # The engine — 26 GitHub Actions workflows
│   ├── command-router.yml      # 🦞 Routes /commands to agent workflows
│   ├── warmup.yml              # 🔥 Triggers all agents (weekly + manual)
│   ├── setup.yml               # 🦞 One-time initialization
│   ├── heartbeat.yml           # 💓 Daily health & streaks
│   ├── morning-roast.yml       # ☕ Daily digest
│   ├── quest-master.yml        # ⚔️ Issue gamification
│   ├── code-jester.yml         # 🃏 PR review
│   ├── wild-fact-finder.yml    # 🔍 Research
│   ├── meme-machine.yml        # 🎨 Content generation
│   ├── lore-keeper.yml         # 📜 Knowledge chronicles
│   ├── dream-interpreter.yml   # 🌙 Dream journaling
│   ├── fortune-cookie.yml      # 🔮 Daily wisdom
│   ├── hype-man.yml            # 🎉 Celebrations
│   ├── roast-battle.yml        # 🔥 Code roasts
│   ├── architect.yml           # 🏗️ Autonomous code proposals
│   ├── council-review.yml      # ⚖️ Council dispatch + vote tally
│   ├── council-member.yml      # 🗳️ Individual council reviewer
│   ├── proposal-lint.yml       # 🔍 Syntax validation gate
│   ├── pages-builder.yml       # 📺 GitHub Pages generator
│   ├── karen.yml               # 💅 QA compliance
│   ├── hn-scraper.yml          # 📰 HN scraping (plugin)
│   ├── news-scraper.yml        # 🥷 News intelligence (plugin)
│   ├── crypto-quant.yml        # 🔮 Crypto analysis (plugin)
│   ├── stock-quant.yml         # 🧙 Stock analysis (plugin)
│   ├── solana-query.yml        # 🌐 Solana data queries (plugin)
│   ├── solana-monitor.yml      # 📡 Wallet/price monitoring (plugin)
│   └── solana-builder.yml      # 🔨 SBF program builds (plugin)
├── agents/                     # Python agent logic
│   ├── common.py               # Shared LLM client, state management
│   ├── architect.py            # Repo analysis → proposal → PR creation
│   ├── pages_builder.py        # Static site generator (Apple HIG design)
│   ├── quest_master.py         # Issue classification & gamification
│   ├── morning_roast.py        # Context gathering & briefing
│   ├── code_jester.py          # Diff analysis & review
│   └── ...                     # 16 Python agents total
├── scripts/                    # Shell utilities (portable, no deps)
│   ├── llm.sh                  # LLM API wrapper (Anthropic/OpenAI)
│   ├── git-persist.sh          # Git commit-based persistence
│   ├── github-api.sh           # GitHub API helpers
│   ├── utils.sh                # Shared utilities, XP system
│   └── solana-tools.sh         # Solana API wrappers (plugin)
├── templates/prompts/          # System prompts — the "soul" of each agent
├── config/                     # Agent personality, settings, registry
├── memory/                     # Git-persisted agent memory
│   ├── state.json              # XP, level, stats, achievements
│   ├── lore/                   # 📜 Knowledge chronicles
│   ├── dreams/                 # 🌙 Dream journal
│   ├── research/               # 🔍 Research archive
│   ├── fortunes/               # 🔮 Fortune archive
│   ├── roasts/                 # 🔥 Roast archive
│   ├── hn/                     # 📰 HN digest archive
│   ├── news/                   # 🥷 News briefing archive
│   ├── crypto/                 # 🔮 Crypto analysis archive
│   ├── stocks/                 # 🧙 Stock analysis archive
│   ├── proposals/              # 🏗️ Architect proposal records
│   ├── council/                # ⚖️ Council review records
│   ├── karen/                  # 💅 Karen audit reports
│   ├── content/                # 🎨 Generated content
│   └── solana/                 # 🌐 Solana data (plugin)
├── docs/                       # GitHub Pages site (auto-generated)
├── agent.md                    # Feature flags — enable/disable agents
└── README.md                   # You are here
```

---

## 🎮 Gamification

GitClaw tracks XP and levels across all agent interactions:

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

XP is earned through agent activity — issues triaged, PRs reviewed, research completed, dreams interpreted, pages built, and more.

---

## 🌐 Solana Plugin

Optional extension for on-chain data. Non-Solana forks stay clean.

### Enable

Add to `agent.md`:
```
enable: solana
solana-network: devnet
solana-style: degen
solana-wallet: YourWalletAddress (Main Wallet)
solana-watch: SOL
solana-watch: BONK
```

### Integrations

| Integration | API | What It Does |
|-------------|-----|-------------|
| **Dexscreener** | Token search, pair data | Prices, volume, liquidity |
| **Jupiter v6** | Swap quotes, routing | Route finding, price impact |
| **Solana RPC** | `getBalance`, `getLatestBlockhash` | Wallet balances, network status |
| **SBF Builder** | `cargo-build-sbf`, Anchor CLI | Verifiable program compilation |

> Uses **public RPC endpoints** by default. Set `SOLANA_RPC_URL` secret for production use. All data is **read-only** — GitClaw never signs transactions.

---

## 💰 Cost & Limits

GitClaw is designed to be **free-tier friendly**:

| Resource | Free Tier | GitClaw Usage |
|----------|-----------|---------------|
| **GitHub Actions** | 2,000 min/month | ~10-40 min/day depending on active agents |
| **Anthropic API** | Pay-per-use | ~$1-5/month (Haiku default, Sonnet for Architect) |
| **CoinGecko** | Free (no key) | Unlimited for basic queries |
| **HN APIs** | Free (no key) | Unlimited |
| **GNews** | 100 req/day free | 1-2 req/day |
| **Alpha Vantage** | 25 req/day free | On-demand only |

### LLM Models Used

| Agent | Model | Why |
|-------|-------|-----|
| Most agents | `claude-haiku-4-5` | Fast, cheap — good for comments and digests |
| 🏗️ Architect | `claude-sonnet-4-5` | Better code understanding for proposals |

Override globally with the `GITCLAW_MODEL` env var in workflow files.

---

## 🔒 Security

- API keys are stored in **GitHub Secrets** (never in code)
- Agent commits use a bot identity (`gitclaw[bot]`)
- All workflows are **hardened against shell injection** — no `${{ }}` in `run:` blocks
- The Architect has **protected paths** — cannot modify `scripts/`, its own workflow, or council workflows
- Rate limiting prevents abuse
- No external servers or data transmission beyond LLM API calls
- All Solana interactions are **read-only** — no transaction signing

---

## 🌊 Inspired By

- [OpenClaw](https://github.com/openclaw/openclaw) — The multi-channel AI gateway
- [PicoClaw](https://github.com/sipeed/picoclaw) — Ultra-lightweight Go agent
- [ZeroClaw](https://github.com/theonlyhennygod/zeroclaw) — Zero-overhead Rust agent

GitClaw takes a different path: **zero infrastructure**. The repo is the agent.

---

## 📜 License

MIT License. Fork it, customize it, make it yours.

---

<p align="center">
  <em>🦞 GitClaw — I live in your repo. I commit my thoughts. I never sleep.</em>
</p>
