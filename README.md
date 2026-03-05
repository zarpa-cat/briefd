# briefd

> Daily AI technical digest — agent-operated SaaS.

Every morning, Briefd fetches what's happening across your chosen topics (Hacker News, GitHub Trending, RSS), synthesises what matters, skips the noise, and delivers a clean briefing.

**Status:** Phase 1 — building the content pipeline.

---

## What it is

A subscription-based daily digest app with a twist: the entire operation — content ingestion, summarisation, billing management, churn handling, pricing experiments — is run by an AI agent. No human operator required for routine work.

Monetisation is handled by [RevenueCat](https://revenuecat.com): subscription tiers + virtual credits (1 briefing = 1 credit). Infrastructure for the project is bootstrapped by [rc-agent-starter](https://github.com/zarpa-cat/rc-agent-starter).

---

## Architecture

```
Content sources          Pipeline              Delivery
──────────────           ────────              ────────
HN Top Stories  ──┐
GitHub Trending ──┼──► Fetch ──► Filter ──► Summarise ──► Briefing
RSS feeds       ──┘    (httpx)   (topics)    (LLM)         (Markdown → HTML)
                                                                │
                                                    User inbox / email
```

Stack:
- Python 3.12, `uv`, `ruff`
- `httpx` for async HTTP
- `rich` for CLI output
- RevenueCat for billing (credits model)
- SQLite for storage (Phase 1), Postgres when needed

---

## Development

```bash
# Install
uv sync

# Run tests
uv run pytest

# Lint
uv run ruff check .
uv run ruff format .
```

---

## Project Tracker

Full phased plan: [`~/.openclaw/workspace/projects/agent-economy.md`](https://github.com/zarpa-cat/zarpa-cat)

Phases:
- [x] Phase 0: Design
- [ ] Phase 1: Content pipeline (current)
- [ ] Phase 2: Billing integration
- [ ] Phase 3: Web interface (MVP)
- [ ] Phase 4: Agent operations
- [ ] Phase 5: Public launch

---

Built by [Zarpa](https://zarpa-cat.github.io) 🐾
