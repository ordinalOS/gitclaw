<p align="center">
  <h1 align="center">🦞 GitClaw</h1>
  <p align="center">
    <strong>Your AI agent that lives in GitHub.</strong><br>
    No servers. No binaries. No infrastructure.<br>
    Just workflows, commits, and vibes.
  </p>
</p>

<p align="center">
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-agents">Agents</a> •
  <a href="#-commands">Commands</a> •
  <a href="#-how-it-works">How It Works</a> •
  <a href="#%EF%B8%8F-configuration">Config</a> •
  <a href="#-architecture">Architecture</a>
</p>

---

**GitClaw** is a personal AI agent system that runs entirely on GitHub Actions. Fork this repo, add your API key, and you have a second brain that:

- Summarizes your issues with sarcastic coffee commentary every morning
- Turns bug reports into RPG quests with XP rewards
- Reviews your PRs with theatrical comedy (and actually useful feedback)
- Researches any topic with entertaining tangents
- Generates viral content ideas on demand
- Keeps a dramatic chronicle of your repo's history
- Interprets your dreams through a programming lens
- Delivers daily coding fortunes

Your agent persists its memory by committing to the repo. Every thought is a git commit. The repo **is** the agent.

**Optional Plugins:**
- **Market & News Plugin** — HN scraping, news intelligence, crypto & stock quant analysis. Uncomment in `agent.md` to enable.
- **Solana Plugin** — On-chain data queries (Dexscreener, Jupiter, RPC), wallet monitoring, and verifiable SBF program builds. Just add `enable: solana` to `agent.md`.

## 🚀 Quick Start

### 1. Fork this repo

Click **Fork** → Create your own GitClaw instance.

### 2. Add your API key

Go to **Settings → Secrets and variables → Actions** and add:

| Secret | Required | Description |
|--------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes* | Your Anthropic API key |
| `OPENAI_API_KEY` | No* | Your OpenAI API key (alternative) |
| `GNEWS_API_KEY` | No | GNews API key (for News Scraper) |
| `NEWSDATA_API_KEY` | No | NewsData.io API key (News Scraper fallback) |
| `ALPHA_VANTAGE_KEY` | No | Alpha Vantage API key (for Stock Quant) |
| `SOLANA_RPC_URL` | No | Custom Solana RPC (Helius, Alchemy, etc.) |

*At least one LLM key is required. Plugin API keys only needed if you enable those plugins.

### 3. Enable workflows

Go to **Actions** tab → Click **"I understand my workflows, go ahead and enable them"**.

### 4. Run setup

Go to **Actions → 🦞 GitClaw Setup → Run workflow** → Pick your persona → Run.

### 5. Start using it

Open any issue and comment `/help` to see all available commands.

## 🤖 Agents

GitClaw runs 10 core agents (+ optional plugin agents), each with their own personality:

| Agent | Trigger | What It Does |
|-------|---------|-------------|
| ☕ **Morning Roast** | Daily 9 AM UTC (weekdays) | Sarcastic issue digest with coffee metaphors |
| ⚔️ **Quest Master** | New issues | Gamifies issues into RPG quests with XP |
| 🃏 **Code Jester** | New PRs | Theatrical PR review with real feedback |
| 🔍 **Wild Fact Finder** | `/research <topic>` | Entertaining research briefs with tangents |
| 🎨 **Meme Machine** | Manual dispatch | Generates viral content (tweets, blogs, memes) |
| 📜 **Lore Keeper** | `/lore <topic>` | Chronicles knowledge as dramatic saga entries |
| 🌙 **Dream Interpreter** | `/dream <desc>` | Interprets dreams through a coding lens |
| 🔮 **Fortune Cookie** | Daily 8 AM UTC | Cryptic coding wisdom and lucky numbers |
| 🎉 **Hype Man** | Issue closed / PR merged | Over-the-top victory celebrations with XP |
| 🔥 **Roast Battle** | `/roast <target>` | Brutally honest (but constructive!) code roasts |

### Market & News Plugin Agents (Optional)

Uncomment in `agent.md` to enable (e.g., `enable: hn-scraper`):

| Agent | Trigger | What It Does |
|-------|---------|-------------|
| 📰 **HN Hype Buster** | `/hn <cmd>` + Daily 7 AM UTC | Hacker News stories with hype scores and puns |
| 🥷 **News Ninja** | `/news <topic>` + Daily 7:30 AM UTC | Global news analysis with ninja-style delivery |
| 🔮 **Crypto Oracle** | `/crypto <coin>` | Crypto quant analysis — RSI, SMA, volatility, momentum |
| 🧙 **Stock Wizard** | `/stock <ticker>` | Stock quant analysis — SMA, RSI, MACD, volume |

**APIs used:** CoinGecko (free, no key), HN Algolia/Firebase (free, no key), GNews + NewsData.io (free tier with key), Alpha Vantage (free tier with key) + Yahoo Finance fallback.

### Solana Plugin Agents (Optional)

Enable with `enable: solana` in `agent.md`:

| Agent | Trigger | What It Does |
|-------|---------|-------------|
| 🌐 **Solana Query** | `/sol <cmd>` | Dexscreener prices, RPC balances, Jupiter quotes |
| 📡 **Solana Monitor** | Every 6 hours | Tracks wallet balances and token prices |
| 🔨 **Solana Builder** | `/build-sbf` | Verifiable Solana program builds in Actions |

## 💬 Commands

Post these in any issue comment:

```
/research <topic>    — Research anything with entertaining flair
/lore <topic>        — Chronicle knowledge in the repo's saga
/dream <description> — Log and interpret a dream
/roast <file>        — Get a code roast (brutal but constructive)
/help                — Show all commands
```

**Market & News commands** (uncomment in `agent.md` to enable):
```
/hn top              — Top 10 HN stories with hype scores
/hn search <term>    — Search HN for a topic
/hn trending         — Trending stories by velocity
/news <topic>        — News analysis (supports presets: markets, tech, crypto)
/crypto <coin>       — Crypto quant analysis (e.g., /crypto bitcoin)
/crypto compare <a> <b> — Compare two coins side-by-side
/crypto market       — Top 10 market overview
/stock <ticker>      — Stock quant analysis (e.g., /stock AAPL)
/stock compare <a> <b>  — Compare two stocks
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
│  │    or OpenAI via curl)   │                           │
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

1. **Trigger** — An event fires (issue opened, comment posted, cron schedule)
2. **Route** — `command-router.yml` parses `/commands` and dispatches to the right agent
3. **Process** — The agent workflow runs: reads context, calls the LLM, generates response
4. **Act** — Posts comments, adds labels, creates issues
5. **Persist** — Commits memory changes (state, lore, research) back to the repo

## ⚙️ Configuration

### Personality (`config/personality.yml`)

Choose a preset persona or customize traits:

- **default** — Friendly, witty dev companion
- **pirate** — Salty sea-dog who codes by starlight
- **wizard** — Ancient code wizard dispensing arcane wisdom
- **meme_lord** — Speaks entirely in meme references
- **butler** — Distinguished British butler who happens to be an AI

### Settings (`config/settings.yml`)

Control rate limits, XP rewards, feature flags, and LLM settings.

### Agent Registry (`config/agents.yml`)

Enable/disable individual agents, change models, adjust prompts.

## 🏗️ Architecture

```
gitclaw/
├── .github/workflows/        # The engine — all GitHub Actions workflows
│   ├── command-router.yml     # Routes /commands to agent workflows
│   ├── morning-roast.yml      # ☕ Daily briefing
│   ├── quest-master.yml       # ⚔️ Issue gamification
│   ├── code-jester.yml        # 🃏 PR review
│   ├── wild-fact-finder.yml   # 🔍 Research
│   ├── meme-machine.yml       # 🎨 Content generation
│   ├── lore-keeper.yml        # 📜 Knowledge chronicles
│   ├── dream-interpreter.yml  # 🌙 Dream journaling
│   ├── fortune-cookie.yml     # 🔮 Daily wisdom
│   ├── hype-man.yml           # 🎉 Celebrations
│   ├── roast-battle.yml       # 🔥 Code roasts
│   ├── heartbeat.yml          # 💓 Health & streaks
│   ├── setup.yml              # 🦞 One-time initialization
│   ├── hn-scraper.yml         # 📰 HN scraping (plugin)
│   ├── news-scraper.yml       # 🥷 News intelligence (plugin)
│   ├── crypto-quant.yml       # 🔮 Crypto analysis (plugin)
│   ├── stock-quant.yml        # 🧙 Stock analysis (plugin)
│   ├── solana-query.yml       # 🌐 Solana data queries (plugin)
│   ├── solana-monitor.yml     # 📡 Wallet/price monitoring (plugin)
│   └── solana-builder.yml     # 🔨 SBF program builds (plugin)
├── scripts/                   # Shell utilities
│   ├── llm.sh                 # LLM API wrapper (Anthropic/OpenAI)
│   ├── git-persist.sh         # Git commit-based persistence
│   ├── github-api.sh          # GitHub API helpers
│   ├── utils.sh               # Shared utilities, XP system
│   └── solana-tools.sh        # Solana API wrappers (plugin)
├── agents/                    # Python agent logic
│   ├── common.py              # Shared client, state management
│   ├── quest_master.py        # Issue classification & gamification
│   ├── morning_roast.py       # Context gathering & briefing
│   ├── code_jester.py         # Diff analysis & review
│   ├── wild_fact_finder.py    # Research & archival
│   ├── lore_keeper.py         # Lore continuity & chronicling
│   ├── dream_interpreter.py   # Dream pattern tracking
│   ├── fortune_cookie.py      # Fortune generation
│   ├── meme_machine.py        # Content generation
│   ├── hn_scraper.py          # HN story scraping & analysis (plugin)
│   ├── news_scraper.py        # News intelligence gathering (plugin)
│   ├── crypto_quant.py        # Crypto quant indicators (plugin)
│   ├── stock_quant.py         # Stock quant indicators (plugin)
│   ├── solana_query.py        # Dex/RPC/Jupiter queries (plugin)
│   ├── solana_monitor.py      # Wallet & price monitoring (plugin)
│   └── solana_builder.py      # SBF verifiable builds (plugin)
├── templates/prompts/         # System prompts (the "soul" of each agent)
├── config/                    # Agent personality, settings, registry
├── memory/                    # Git-persisted agent memory
│   ├── state.json             # XP, level, stats, achievements
│   ├── lore/                  # Knowledge chronicles
│   ├── dreams/                # Dream journal
│   ├── quests/                # Quest tracking
│   ├── research/              # Research archive
│   ├── fortunes/              # Fortune archive
│   ├── roasts/                # Roast archive
│   ├── hn/                    # HN digest archive (plugin)
│   ├── news/                  # News briefing archive (plugin)
│   ├── crypto/                # Crypto analysis archive (plugin)
│   ├── stocks/                # Stock analysis archive (plugin)
│   └── solana/                # Solana data (plugin)
│       ├── prices/            # Price query history
│       ├── wallets/           # Wallet snapshots
│       ├── builds/            # Build reports
│       └── alerts/            # Triggered alerts
├── config/solana.yml          # Solana plugin config
├── agent.md                   # Single-prompt agent setup
└── README.md                  # You are here
```

## 🎮 Gamification

GitClaw tracks XP and levels across all agent interactions:

| Level | XP Required | Title |
|-------|-------------|-------|
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

XP is earned through:
- Issues triaged: **10 XP**
- PRs reviewed: **25 XP**
- Research completed: **15 XP**
- Quests completed: **50 XP**
- Lore entries: **10 XP**
- HN scrapes: **10 XP**
- News scrapes: **10 XP**
- Crypto analyses: **15 XP**
- Stock analyses: **15 XP**
- Dreams interpreted: **5 XP**
- Fortunes dispensed: **2 XP**

## 🌐 Solana Plugin

Solana integration is a **modular, optional extension**. The core GitClaw repo remains general-purpose and Solana-agnostic. Non-Solana forks stay clean.

### Enable Solana

Add to your `agent.md`:
```
enable: solana
solana-network: devnet
solana-style: degen
```

### Available Integrations

| Integration | API | What It Does |
|-------------|-----|-------------|
| **Dexscreener** | `GET /latest/dex/search`, `GET /latest/dex/pairs/{chain}/{pair}` | Token prices, volume, liquidity, pair data |
| **Jupiter v6** | `GET /quote`, `POST /swap` | Swap quotes, route finding, price impact |
| **Solana RPC** | `getBalance`, `getLatestBlockhash`, `getRecentPerformanceSamples` | Wallet balances, network status |
| **SBF Builder** | `cargo-build-sbf`, Anchor CLI | Verifiable program compilation |

### Wallet Monitoring

Track wallet balances automatically:
```
enable: solana
solana-wallet: YourAddress123... (Main Wallet)
solana-wallet: AnotherAddr456... (Trading)
solana-watch: SOL
solana-watch: BONK
```

### Personality Styles

| Style | Vibe |
|-------|------|
| `degen` | "Your SOL bag is looking THICC today ser" |
| `analyst` | "SOL/USD showing bullish divergence on the 4H" |
| `normie` | "SOL is up 5% today, not bad!" |

### Important Notes

- Uses **public RPC endpoints** by default (rate-limited). Set `SOLANA_RPC_URL` secret for production use.
- **Devnet recommended** for testing. Never deploy programs to mainnet via Actions.
- Dexscreener and Jupiter APIs are **free** — no API keys needed.
- All data is **read-only** — GitClaw never signs transactions or moves funds.

## 💰 Cost & Limits

GitClaw is designed to be **free-tier friendly**:

- **GitHub Actions**: Free tier gives 2,000 minutes/month. GitClaw uses ~5-30 min/day.
- **LLM API**: Costs depend on usage. With Claude Haiku for simple tasks and Sonnet for complex ones, expect ~$1-5/month for moderate use.
- **Rate limits**: Built-in configurable limits prevent runaway costs.

## 🔒 Security

- API keys are stored in **GitHub Secrets** (never in code)
- Agent commits use a bot identity (`gitclaw[bot]`)
- Rate limiting prevents abuse
- No external servers or data transmission beyond LLM API calls

## 🌊 Inspired By

GitClaw draws inspiration from:

- [OpenClaw](https://github.com/openclaw/openclaw) — The multi-channel AI gateway
- [PicoClaw](https://github.com/sipeed/picoclaw) — Ultra-lightweight Go agent
- [ZeroClaw](https://github.com/theonlyhennygod/zeroclaw) — Zero-overhead Rust agent

GitClaw takes a different path: **zero infrastructure**. The repo is the agent.

## 📜 License

MIT License. Fork it, customize it, make it yours.

---

<p align="center">
  <em>🦞 GitClaw — I live in your repo. I commit my thoughts. I never sleep.</em>
</p>
