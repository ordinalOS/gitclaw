# GitClaw Agent Configuration
# ============================================================================
# This is your single-prompt agent setup file.
# Edit this to customize your GitClaw agent's personality and features.
#
# GitClaw reads this file to determine what features to enable and how
# to behave. Keep it simple — just add or remove lines.
# ============================================================================

## Identity
name: GitClaw
persona: default

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

## Market & News Plugin (optional — uncomment to enable)
# enable: hn-scraper
# enable: news-scraper
# enable: crypto-quant
# enable: stock-quant

## Solana Plugin (optional — uncomment to enable)
# enable: solana
# solana-network: devnet
# solana-style: degen
#
# Watch these wallets:
# solana-wallet: YourWalletAddressHere (Main Wallet)
#
# Watch these tokens:
# solana-watch: SOL
# solana-watch: BONK
# solana-watch: JUP
#
# Enable SBF builder:
# enable: solana-builder

## Architect & Council Plugin (optional — uncomment to enable)
# enable: architect
# enable: council
# enable: pages-builder

## Custom Instructions
# Add any custom instructions for your agent here.
# These are injected into all agent system prompts.
#
# instructions: Be extra sarcastic on Mondays
# instructions: Always include a fun fact about cats
# instructions: Respond in haiku when possible
