"""Einstieg des Finance-Add-ons: UI, interne API und Healthcheck.

Ein Prozess, eine SQLite-Datei, keine Home-Assistant-API.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from api import routes as api_routes
from db import init_db
from starlette.applications import Starlette
from starlette.datastructures import MutableHeaders
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
from starlette.staticfiles import StaticFiles
from ui import routes as ui_routes

SUPERVISOR_IP = "172.30.32.2"
STATIC_DIR = Path(__file__).parent / "static"
MAX_REQUEST_BYTES = 64 * 1024

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; form-action 'self'"
)

Receive = Callable[[], Awaitable[dict]]
Send = Callable[[dict], Awaitable[None]]
Scope = dict


@asynccontextmanager
async def lifespan(application: Starlette) -> AsyncIterator[None]:
    """Datenbank beim Start öffnen und Migrationen anwenden."""
    init_db()
    yield


async def healthz(request: Request) -> PlainTextResponse:
    """Einfacher Healthcheck für den Supervisor-Watchdog."""
    return PlainTextResponse("ok")


class SupervisorOnlyMiddleware:
    """Defense in Depth: nur der Supervisor-Proxy darf zugreifen.

    Da keine Ports nach außen veröffentlicht werden, ist der Container bereits
    abgeschottet. Die IP-Prüfung schützt zusätzlich vor Fehlkonfigurationen.
    Für lokale Entwicklung kann sie mit FINANCE_RESTRICT_INGRESS=0 ausgeschaltet
    werden.
    """

    def __init__(self, app: Callable) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        enabled = os.environ.get("FINANCE_RESTRICT_INGRESS", "1") == "1"
        if scope["type"] == "http" and enabled:
            client = scope.get("client")
            if client is None or client[0] != SUPERVISOR_IP:
                response: Response = PlainTextResponse("Forbidden", status_code=403)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


class RequestLimitMiddleware:
    """Sehr große Requests früh abweisen (Formulare und JSON)."""

    def __init__(self, app: Callable) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            for key, value in scope.get("headers", []):
                if key == b"content-length":
                    try:
                        length = int(value)
                    except ValueError:
                        length = MAX_REQUEST_BYTES + 1
                    if length > MAX_REQUEST_BYTES:
                        response: Response = PlainTextResponse("Payload Too Large", status_code=413)
                        await response(scope, receive, send)
                        return
                    break
        await self.app(scope, receive, send)


class SecurityHeadersMiddleware:
    """Minimale Security-Headers ohne Auswirkung auf die HA-Ingress-Einbettung."""

    def __init__(self, app: Callable) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["Referrer-Policy"] = "no-referrer"
                headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
            await send(message)

        await self.app(scope, receive, send_with_headers)


app = Starlette(
    routes=[
        Route("/healthz", healthz, name="healthz"),
        *ui_routes,
        *api_routes,
    ],
    middleware=[
        Middleware(SupervisorOnlyMiddleware),
        Middleware(RequestLimitMiddleware),
        Middleware(SecurityHeadersMiddleware),
    ],
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
