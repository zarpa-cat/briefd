# CLAUDE.md — Briefd codebase guide

This file gives Claude Code context for working in this repo.

## What this is

Briefd is an agent-operated SaaS: a daily AI technical digest app where the entire
operation (content ingestion, summarisation, billing, churn handling) is run by an
AI agent. It's simultaneously a product and a reference implementation.

## Stack

- **Python 3.12** — strict typing throughout, no `Any` if avoidable
- **`uv`** for dependency management (`uv sync`, `uv add`, `uv run`)
- **`ruff`** for lint + format — always `uv run ruff`, never bare `ruff`
- **`pytest`** + `pytest-asyncio` for tests
- **`httpx`** + `respx` for HTTP and mocking
- **`fastapi`** + `jinja2` + htmx for the web layer
- **RevenueCat v2 API** for billing (`briefd/billing.py`)

## Conventions

### Always TDD
Write the test first, watch it fail, then implement. Every new function needs tests.

### Format before commit
```bash
uv run ruff check --fix .
uv run ruff format .
uv run ruff format --check .   # must be clean
uv run pytest                  # must pass
```

**Critical:** Always `uv run ruff format`, not bare `ruff format`. Versions diverge
between environments and CI uses the locked version.

### Async throughout
All I/O is async (`httpx.AsyncClient`). Tests use `pytest-asyncio` in auto mode.
Mock HTTP with `respx`.

### No secrets in code
API keys via environment variables only (`os.environ.get`). Never hardcoded.

## Module layout

| Module | Purpose |
|---|---|
| `briefd/models.py` | Core dataclasses: `Story`, `Briefing`, `UserConfig` |
| `briefd/fetcher.py` | Async content fetchers: `fetch_hn_top`, `fetch_github_trending`, `fetch_rss` |
| `briefd/pipeline.py` | `filter_stories`, `generate_briefing`, `generate_briefing_gated` |
| `briefd/billing.py` | `BillingClient` — RC customer, entitlement, credit operations |
| `briefd/webhook.py` | `parse_webhook`, `handle_webhook` — RC lifecycle events |
| `briefd/storage.py` | `BriefingStore` — SQLite persistence |
| `briefd/cli.py` | Click CLI: `briefd run --topics python,rust` |
| `briefd/web/app.py` | FastAPI routes: `/`, `/briefings`, `/briefings/{date}`, `/health` |

## RevenueCat integration

- API base: `https://api.revenuecat.com/v2`
- Auth: `Authorization: Bearer <v2_secret_key>`
- Project uses virtual currency `CRED` (1 credit = 1 briefing)
- Entitlement key: `premium`
- Billing gate: `generate_briefing_gated()` checks `CustomerStatus` before any LLM call

## Key decisions

- **htmx over React**: server-rendered, simpler for an agent-operated app
- **SQLite first**: good enough for MVP, easy to migrate to Postgres later
- **Credits model**: subscription grants monthly allocation, consumables for top-up
- **Graceful degradation**: RSS 404s return `[]`, billing 404s return balance=0

## Running tests

```bash
uv run pytest                    # all tests
uv run pytest tests/test_billing.py -v   # specific file
uv run pytest -k "test_filter"   # by name pattern
```

Current test count: 66 (all passing).
