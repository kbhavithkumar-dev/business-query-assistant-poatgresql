"""Small web protections shared by the page and its JSON endpoints."""

import base64
import os
import secrets

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from starlette.datastructures import Headers, MutableHeaders

LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]"}
MAX_REQUEST_BYTES = 8192


def web_settings():
    hosts = tuple(part.strip() for part in os.getenv(
        "ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]",
    ).split(",") if part.strip())
    username = os.getenv("APP_USERNAME", "business")
    password = os.getenv("APP_PASSWORD", "")
    if not hosts or any("*" in host for host in hosts):
        raise ValueError("Set ALLOWED_HOSTS to explicit host names.")
    if (password or set(hosts) - LOCAL_HOSTS) and (
        len(password) < 16 or not password.isascii()
        or not username or not username.isascii() or ":" in username
    ):
        raise ValueError("Use an ASCII password of at least 16 characters and a valid username.")
    return hosts, username, password


class WebSecurity:
    def __init__(self, app, username, password):
        self.app = app
        self.expected_credentials = base64.b64encode(f"{username}:{password}".encode()) if password else None

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["Cache-Control"] = "no-store"
                headers["X-Content-Type-Options"] = "nosniff"
                headers["Referrer-Policy"] = "no-referrer"
                headers["Content-Security-Policy"] = (
                    "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; "
                    "form-action 'self'; object-src 'none'"
                )
            await send(message)

        headers = Headers(scope=scope)
        path = scope["path"]
        protected_path = path == "/" or path.startswith("/api/")
        if self.expected_credentials and protected_path:
            # This compares the expected Basic header using constant-time comparison.
            scheme, _, supplied = headers.get("Authorization", "").partition(" ")
            valid = secrets.compare_digest(supplied.encode(), self.expected_credentials)
            if scheme.lower() != "basic" or not valid:
                await JSONResponse(
                    {"detail": "Sign in to the Business Data Query Assistant."}, 401,
                    headers={"WWW-Authenticate": 'Basic realm="Business Query Assistant"'},
                )(scope, receive, send_with_headers)
                return

        if scope["method"] == "POST" and headers.get("X-Business-Request") != "1":
            # A third-party browser page cannot send this header without CORS permission.
            await JSONResponse({"detail": "Missing app request header."}, 403)(
                scope, receive, send_with_headers,
            )
            return

        declared = headers.get("Content-Length", "0")
        if not declared.isdecimal() or len(declared) > 8 or int(declared) > MAX_REQUEST_BYTES:
            await JSONResponse({"detail": "Request is too large."}, 413)(scope, receive, send_with_headers)
            return

        received = 0

        async def bounded_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > MAX_REQUEST_BYTES:
                    raise HTTPException(413, "Request is too large.")
            return message

        await self.app(scope, bounded_receive, send_with_headers)
