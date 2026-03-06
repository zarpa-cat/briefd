"""FastAPI application for Briefd."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from briefd.auth import (
    AuthStore,
    TokenStatus,
    email_to_user_id,
    generate_token,
    send_magic_link,
    verify_token,
)
from briefd.storage import BriefingStore, UserConfigStore

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"
DB_PATH = Path(os.environ.get("BRIEFD_DB", "briefd.db"))

app = FastAPI(title="Briefd", description="Daily AI technical digest")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


AUTH_DB_PATH = Path(os.environ.get("BRIEFD_AUTH_DB", "briefd-auth.db"))


def get_store() -> BriefingStore:
    return BriefingStore(DB_PATH)


def get_user_config_store() -> UserConfigStore:
    return UserConfigStore(DB_PATH)


def get_auth_store() -> AuthStore:
    return AuthStore(AUTH_DB_PATH)


def get_current_user(request: Request) -> str:
    """Extract user_id from session cookie. Returns 'local' as fallback."""
    return request.cookies.get("briefd_user", "local")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Landing page."""
    return templates.TemplateResponse(request, "landing.html", {"request": request})


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


@app.get("/auth/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    """Magic link request page."""
    return templates.TemplateResponse(request, "auth/login.html", {"request": request})


@app.post("/auth/request")
async def request_magic_link(request: Request, email: str = Form(...)) -> HTMLResponse:
    """Generate a magic link token and email it."""
    token = generate_token()
    auth_store = get_auth_store()
    auth_store.save_token(token, email=email)

    base_url = str(request.base_url).rstrip("/")
    await send_magic_link(email=email, token=token, base_url=base_url)

    return templates.TemplateResponse(
        request,
        "auth/check_email.html",
        {"request": request, "email": email},
    )


@app.get("/auth/verify", response_class=HTMLResponse)
async def verify_magic_link(request: Request, token: str) -> Response:
    """Verify a magic link token and set session cookie."""
    auth_store = get_auth_store()
    status, email = verify_token(auth_store, token)

    if status == TokenStatus.VALID:
        user_id = email_to_user_id(email)
        response = RedirectResponse(url="/briefings", status_code=303)
        response.set_cookie("briefd_user", user_id, httponly=True, max_age=60 * 60 * 24 * 30)
        return response

    error = (
        "This link has already been used."
        if status == TokenStatus.ALREADY_USED
        else "Invalid or expired link."
    )
    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {"request": request, "error": error},
        status_code=400,
    )


@app.post("/auth/logout")
async def logout() -> Response:
    """Clear session cookie."""
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("briefd_user")
    return response


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request) -> HTMLResponse:
    """User preferences — topics and delivery time."""
    user_id = get_current_user(request)
    cfg_store = get_user_config_store()
    cfg = cfg_store.get(user_id)
    return templates.TemplateResponse(
        request,
        "settings.html",
        {"request": request, "user_id": user_id, "cfg": cfg},
    )


@app.post("/settings", response_class=HTMLResponse)
async def save_settings(
    request: Request,
    topics: str = Form(...),
    delivery_hour: int = Form(7),
) -> Response:
    """Save user topic and delivery preferences."""
    from briefd.models import UserConfig

    user_id = get_current_user(request)
    topic_list = [t.strip().lower() for t in topics.split(",") if t.strip()]
    cfg = UserConfig(
        user_id=user_id,
        topics=topic_list,
        delivery_hour_utc=max(0, min(23, delivery_hour)),
    )
    get_user_config_store().save(cfg)
    return RedirectResponse(url="/settings?saved=1", status_code=303)


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "service": "briefd"}
