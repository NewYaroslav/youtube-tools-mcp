from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


class OAuthError(Exception):
    """OAuth flow or token error."""


class OAuthCredentialsNotFoundError(OAuthError):
    """No stored OAuth credentials found."""


_TOKEN_DIR = Path.home() / ".config" / "youtube-tools-mcp"
_TOKEN_FILE = _TOKEN_DIR / "oauth.json"
_OAUTH_SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"
_DEVICE_CODE_URL = "https://oauth2.googleapis.com/device/code"
_TOKEN_URL = "https://oauth2.googleapis.com/token"


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


def run_device_flow(client_id: str, client_secret: str) -> None:
    """Run OAuth 2.0 device code flow and save refresh token."""
    device_resp = _post_form(
        _DEVICE_CODE_URL,
        {
            "client_id": client_id,
            "scope": _OAUTH_SCOPE,
        },
    )

    device_code = device_resp.get("device_code")
    user_code = device_resp.get("user_code")
    verification_url = device_resp.get("verification_url") or device_resp.get("verification_uri")
    expires_in = device_resp.get("expires_in", 1800)
    interval = device_resp.get("interval", 5)

    if not all([device_code, user_code, verification_url]):
        raise OAuthError("Invalid device code response")

    print(f"\nOpen this URL in your browser: {verification_url}")
    print(f"Enter this code: {user_code}\n")

    start_time = time.time()

    while time.time() - start_time < expires_in:
        time.sleep(interval)

        token_resp = _post_form(
            _TOKEN_URL,
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "device_code": str(device_code),
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
        )

        if token_resp.get("error") == "authorization_pending":
            continue
        if token_resp.get("error") == "slow_down":
            interval += 5
            continue
        if "error" in token_resp:
            raise OAuthError(
                f"OAuth error: {token_resp.get('error_description', token_resp['error'])}"
            )

        refresh_token = token_resp.get("refresh_token")
        access_token = token_resp.get("access_token")
        expires_in_token = token_resp.get("expires_in", 3600)

        if not refresh_token:
            raise OAuthError("No refresh token received")

        _save_token_data(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "access_token": access_token,
                "expires_at": time.time() + expires_in_token,
            }
        )

        print("OAuth authorization successful. Token saved.")
        return

    raise OAuthError("Device code expired before authorization")


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
        run_device_flow(client_id, client_secret)
    except OAuthError as exc:
        print(f"OAuth failed: {exc}")
        raise SystemExit(1) from exc
