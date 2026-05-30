from __future__ import annotations

import contextlib
import json
import os
import secrets
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any


class OAuthError(Exception):
    """OAuth flow or token error."""


class OAuthCredentialsNotFoundError(OAuthError):
    """No stored OAuth credentials found."""


_TOKEN_DIR = Path.home() / ".config" / "youtube-tools-mcp"
_TOKEN_FILE = _TOKEN_DIR / "oauth.json"
_OAUTH_SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"
_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_DEFAULT_PORT = 8085


def _ensure_token_dir() -> None:
    _TOKEN_DIR.mkdir(parents=True, exist_ok=True)


def _load_token_data() -> dict[str, Any] | None:
    if not _TOKEN_FILE.exists():
        return None
    try:
        with open(_TOKEN_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None


def _save_token_data(data: dict[str, Any]) -> None:
    _ensure_token_dir()
    with open(_TOKEN_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    if os.name != "nt":
        os.chmod(_TOKEN_FILE, 0o600)


def _find_port(start: int = _DEFAULT_PORT) -> int:
    """Find an available port starting from *start*."""
    for port in range(start, start + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise OAuthError(
        f"Could not find a free port in range {start}-{start + 99}. "
        "Make sure no other process is blocking the range and try again."
    )


def _post_form(url: str, params: dict[str, str]) -> dict[str, Any]:
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as response:  # noqa: S310
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise OAuthError(f"HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise OAuthError(f"Request failed: {exc.reason}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OAuthError("Invalid JSON response") from exc


def _exchange_code_for_token(
    code: str, redirect_uri: str, client_id: str, client_secret: str
) -> dict[str, Any]:
    return _post_form(
        _TOKEN_URL,
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
    )


class _CallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, _format: str, *_args: Any) -> None:  # noqa: ANN401
        pass

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)

        result = {
            "code": query.get("code", [None])[0],
            "state": query.get("state", [None])[0],
            "error": query.get("error_description", [None])[0]
            or query.get("error", [None])[0],
        }
        self.server._oauth_result = result

        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()

        if result["code"]:
            body = (
                "<h1>Authorization successful</h1>"
                "<p>You can close this window and return to the terminal.</p>"
            )
        else:
            err = result["error"] or "Unknown error"
            body = f"<h1>Authorization failed</h1><p>{err}</p>"
        self.wfile.write(body.encode("utf-8"))


def _wait_for_callback(port: int, timeout: float = 300.0) -> dict[str, str | None]:
    """Start a temporary HTTP server and wait for the OAuth callback."""
    server = HTTPServer(("127.0.0.1", port), _CallbackHandler)
    server._oauth_result = {"code": None, "state": None, "error": None}
    deadline = time.time() + timeout
    while time.time() < deadline:
        server.timeout = max(1.0, deadline - time.time())
        server.handle_request()
        if server._oauth_result.get("code") or server._oauth_result.get("error"):
            break
    return server._oauth_result  # type: ignore[return-value]


def run_authorization_flow(client_id: str, client_secret: str) -> None:
    """Run OAuth 2.0 authorization code flow with localhost callback."""
    port = _find_port()
    redirect_uri = f"http://127.0.0.1:{port}"
    state = secrets.token_urlsafe(16)

    auth_params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": _OAUTH_SCOPE,
        "response_type": "code",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    auth_url = f"{_AUTH_URL}?{urllib.parse.urlencode(auth_params)}"

    print(f"\nOpen this URL in your browser:\n{auth_url}\n")

    with contextlib.suppress(Exception):
        webbrowser.open(auth_url)

    print(f"Waiting for authorization callback on {redirect_uri} ...")
    result = _wait_for_callback(port)

    code = result.get("code")
    received_state = result.get("state")
    error_desc = result.get("error")

    if code is None:
        raise OAuthError(f"Authorization failed: {error_desc or 'no code received'}")

    if received_state != state:
        raise OAuthError("Invalid state parameter — possible CSRF attack")

    token_resp = _exchange_code_for_token(code, redirect_uri, client_id, client_secret)

    refresh_token = token_resp.get("refresh_token")
    access_token = token_resp.get("access_token")
    expires_in = token_resp.get("expires_in", 3600)

    if not refresh_token:
        raise OAuthError("No refresh token received")

    _save_token_data(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "access_token": access_token,
            "expires_at": time.time() + expires_in,
        }
    )

    print("OAuth authorization successful. Token saved.")


def refresh_access_token(refresh_token: str, client_id: str, client_secret: str) -> tuple[str, int]:
    """Refresh access token using refresh token."""
    resp = _post_form(
        _TOKEN_URL,
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )

    access_token = resp.get("access_token")
    expires_in = resp.get("expires_in", 3600)

    if not access_token:
        raise OAuthError("No access token in refresh response")

    return str(access_token), int(expires_in)


def get_access_token() -> str | None:
    """Return a valid access token, refreshing if needed."""
    data = _load_token_data()
    if not data:
        return None

    client_id = data.get("client_id")
    client_secret = data.get("client_secret")
    refresh_token = data.get("refresh_token")

    if not all([client_id, client_secret, refresh_token]):
        return None

    expires_at = data.get("expires_at", 0)

    # If token expires within the next 5 minutes, refresh
    if time.time() < expires_at - 300 and data.get("access_token"):
        return str(data["access_token"])

    try:
        access_token, expires_in = refresh_access_token(
            str(refresh_token), str(client_id), str(client_secret)
        )
    except OAuthError:
        return None

    data["access_token"] = access_token
    data["expires_at"] = time.time() + expires_in
    _save_token_data(data)

    return access_token


def main() -> None:
    """CLI entry point for OAuth authorization."""
    client_id = os.environ.get("YOUTUBE_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("YOUTUBE_OAUTH_CLIENT_SECRET")

    if not client_id:
        print("Error: Set YOUTUBE_OAUTH_CLIENT_ID environment variable")
        raise SystemExit(1)
    if not client_secret:
        print("Error: Set YOUTUBE_OAUTH_CLIENT_SECRET environment variable")
        raise SystemExit(1)

    try:
        run_authorization_flow(client_id, client_secret)
    except OAuthError as exc:
        print(f"OAuth failed: {exc}")
        raise SystemExit(1) from exc
