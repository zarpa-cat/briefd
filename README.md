# briefd

> Daily AI technical digest — agent-operated SaaS.

Every morning, Briefd fetches what's happening across your chosen topics (Hacker News, GitHub Trending, RSS), synthesises what matters, skips the noise, and delivers a clean briefing. One credit per briefing.

**Status:** Phase 3 — web interface in progress.

---

## What it is

A subscription-based daily digest app with a twist: the entire operation — content ingestion, summarisation, billing management, churn handling, pricing experiments — is run by an AI agent. No human operator required for routine work.

Monetisation is handled by [RevenueCat](https://revenuecat.com): subscription tiers + virtual credits (1 briefing = 1 credit). Infrastructure bootstrapped by [rc-agent-starter](https://github.com/zarpa-cat/rc-agent-starter).

---

## Architecture

```
Content sources          Pipeline              Delivery
──────────────           ────────              ────────
HN Top Stories  ──┐
GitHub Trending ──┼──► Fetch ──► Filter ──► Summarise ──► Briefing
RSS feeds       ──┘    (httpx)   (topics)    (LLM)         (Markdown → HTML)
                                                                │
                                                    Web inbox / email
```

**Stack:**
- Python 3.12, `uv`, `ruff`
- `httpx` for async HTTP
- `fastapi` + `jinja2` + htmx for the web layer
- `rich` for CLI output
- RevenueCat for billing (subscription + credits model)
- SQLite for storage (MVP), Postgres when needed

---

## Quick start

```bash
# Install
git clone https://github.com/zarpa-cat/briefd
cd briefd
uv sync

# Generate a briefing (requires ANTHROPIC_API_KEY)
export ANTHROPIC_API_KEY=sk-ant-...
uv run briefd run --topics python,rust,llm

# Run the web app
uv run uvicorn briefd.web.app:app --reload
```

---

## Development

```bash
# Run tests
uv run pytest

# Lint + format
uv run ruff check .
uv run ruff format .

# Type check
uv run --with ty ty check .
```

All tests must pass and `ruff format --check` must be clean before committing.
**Always use `uv run ruff format`, not bare `ruff format`** — versions diverge between environments.

---

## Project structure

```
briefd/
├── briefd/
│   ├── models.py       # Story, Briefing, UserConfig dataclasses
│   ├── fetcher.py      # HN, GitHub Trending, RSS fetchers
│   ├── pipeline.py     # Filter + LLM summarise + billing gate
│   ├── billing.py      # RevenueCat client (customer, entitlements, credits)
│   ├── webhook.py      # RC webhook event handler
│   ├── storage.py      # SQLite briefing store
│   ├── cli.py          # briefd run CLI
│   └── web/
│       ├── app.py      # FastAPI routes
│       └── templates/  # Jinja2 + htmx
└── tests/              # 66 tests, all passing
```

---

## Roadmap

- [x] Phase 0: Design
- [x] Phase 1: Content pipeline (HN + GitHub + RSS + filter + LLM + SQLite + CLI)
- [x] Phase 2: Billing integration (RC customer lifecycle, credit gate, webhooks)
- [ ] Phase 3: Web interface — auth, subscription page, briefing inbox (in progress)
- [ ] Phase 4: Agent operations — scheduler, churn intervention, pricing experiments
- [ ] Phase 5: Public launch

---

Built by [Zarpa](https://zarpa-cat.github.io) 🐾
