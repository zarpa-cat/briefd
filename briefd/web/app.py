"""FastAPI application for Briefd."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from briefd.storage import BriefingStore

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"
DB_PATH = Path(os.environ.get("BRIEFD_DB", "briefd.db"))

app = FastAPI(title="Briefd", description="Daily AI technical digest")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def get_store() -> BriefingStore:
    return BriefingStore(DB_PATH)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Landing page."""
    return templates.TemplateResponse(request, "index.html", {"request": request})


@app.get("/briefings", response_class=HTMLResponse)
async def briefing_list(request: Request, user_id: str = "local") -> HTMLResponse:
    """Briefing inbox — list of generated briefings for a user."""
    store = get_store()
    briefings = store.list_for_user(user_id)
    return templates.TemplateResponse(
        request,
        "briefings/list.html",
        {"request": request, "briefings": briefings, "user_id": user_id},
    )


@app.get("/briefings/{date}", response_class=HTMLResponse)
async def briefing_detail(request: Request, date: str, user_id: str = "local") -> HTMLResponse:
    """Read a single briefing."""
    store = get_store()
    briefing = store.get(user_id=user_id, date=date)
    if briefing is None:
        return HTMLResponse("<h1>Briefing not found</h1>", status_code=404)
    return templates.TemplateResponse(
        request,
        "briefings/detail.html",
        {"request": request, "briefing": briefing},
    )


@app.get("/account", response_class=HTMLResponse)
async def account(request: Request, user_id: str = "local") -> HTMLResponse:
    """Account page — subscription status and credit balance."""
    from briefd.billing import BillingClient

    rc_key = os.environ.get("RC_API_KEY", "")
    rc_project = os.environ.get("RC_PROJECT_ID", "")

    customer_status = None
    billing_error = None

    if rc_key and rc_project:
        try:
            client = BillingClient(api_key=rc_key, project_id=rc_project)
            customer_status = await client.get_customer_status(user_id)
        except Exception as e:
            billing_error = str(e)

    return templates.TemplateResponse(
        request,
        "account.html",
        {
            "request": request,
            "user_id": user_id,
            "customer_status": customer_status,
            "billing_error": billing_error,
        },
    )


@app.post("/webhook/revenuecat")
async def revenuecat_webhook(request: Request) -> dict:
    """Receive RevenueCat webhook events."""
    from briefd.webhook import handle_webhook, parse_webhook

    payload = await request.json()
    event = parse_webhook(payload)
    actions = await handle_webhook(event)
    return {"received": True, "event_type": event.event_type.value, "actions": actions}


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "service": "briefd"}
