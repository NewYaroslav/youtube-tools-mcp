from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from youtube_tools_mcp.youtube.oauth import (
    OAuthError,
    _find_free_port,
    _load_token_data,
    _save_token_data,
    get_access_token,
    refresh_access_token,
    run_authorization_flow,
)


class MockResponse:
    """Mock urllib response."""

    def __init__(self, body: dict | str, status: int = 200):
        if isinstance(body, dict):
            self._body = json.dumps(body).encode("utf-8")
        else:
            self._body = body.encode("utf-8")
        self.status = status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class TestLoadSaveTokenData:
    def test_load_missing_returns_none(self):
        with patch.object(Path, "exists", return_value=False):
            result = _load_token_data()
        assert result is None

    def test_round_trip(self, tmp_path: Path):
        token_file = tmp_path / "oauth.json"
        with patch("youtube_tools_mcp.youtube.oauth._TOKEN_FILE", token_file):
            data = {"refresh_token": "rt", "client_id": "cid", "client_secret": "cs"}
            _save_token_data(data)
            loaded = _load_token_data()
        assert loaded == data


class TestFindFreePort:
    def test_returns_port(self):
        port = _find_free_port(50000)
        assert isinstance(port, int)
        assert port >= 50000


class TestGetAccessToken:
    def test_returns_valid_token_without_refresh(self):
        future = time.time() + 3600
        data = {
            "client_id": "cid",
            "client_secret": "cs",
            "refresh_token": "rt",
            "access_token": "at",
            "expires_at": future,
        }
        with patch("youtube_tools_mcp.youtube.oauth._load_token_data", return_value=data):
            result = get_access_token()
        assert result == "at"

    def test_refreshes_expired_token(self):
        past = time.time() - 3600
        data = {
            "client_id": "cid",
            "client_secret": "cs",
            "refresh_token": "rt",
            "access_token": "old_at",
            "expires_at": past,
        }
        saved: dict = {}
        mock_resp = MockResponse({"access_token": "new_at", "expires_in": 3600})

        def mock_save(d):
            saved.update(d)

        with (
            patch("youtube_tools_mcp.youtube.oauth._load_token_data", return_value=data),
            patch("youtube_tools_mcp.youtube.oauth._save_token_data", side_effect=mock_save),
            patch("urllib.request.urlopen", return_value=mock_resp),
        ):
            result = get_access_token()

        assert result == "new_at"
        assert saved["access_token"] == "new_at"
        assert saved["expires_at"] > time.time()

    def test_returns_none_when_no_data(self):
        with patch("youtube_tools_mcp.youtube.oauth._load_token_data", return_value=None):
            result = get_access_token()
        assert result is None

    def test_returns_none_when_refresh_fails(self):
        past = time.time() - 3600
        data = {
            "client_id": "cid",
            "client_secret": "cs",
            "refresh_token": "rt",
            "access_token": "old_at",
            "expires_at": past,
        }
        from urllib.error import HTTPError

        with patch("youtube_tools_mcp.youtube.oauth._load_token_data", return_value=data), patch(
            "urllib.request.urlopen",
            side_effect=HTTPError("url", 400, "Bad Request", {}, None),
        ):
            result = get_access_token()
        assert result is None


class TestRefreshAccessToken:
    def test_returns_new_token(self):
        mock_resp = MockResponse({"access_token": "fresh", "expires_in": 7200})
        with patch("urllib.request.urlopen", return_value=mock_resp):
            token, expires = refresh_access_token("rt", "cid", "cs")
        assert token == "fresh"
        assert expires == 7200

    def test_raises_on_error(self):
        from urllib.error import HTTPError

        with patch(
            "urllib.request.urlopen",
            side_effect=HTTPError("url", 400, "Bad Request", {}, None),
        ), pytest.raises(OAuthError):
            refresh_access_token("rt", "cid", "cs")


class TestRunAuthorizationFlow:
    def test_success(self, tmp_path: Path, capsys):
        token_file = tmp_path / "oauth.json"
        token_resp = MockResponse(
            {
                "refresh_token": "rt",
                "access_token": "at",
                "expires_in": 3600,
            }
        )

        def _handle_request(req, **kw):
            return token_resp

        with (
            patch("youtube_tools_mcp.youtube.oauth._TOKEN_FILE", token_file),
            patch("youtube_tools_mcp.youtube.oauth._find_free_port", return_value=65000),
            patch(
                "youtube_tools_mcp.youtube.oauth._wait_for_callback",
                return_value={"code": "authcode", "state": "test_state", "error": None},
            ),
            patch("secrets.token_urlsafe", return_value="test_state"),
            patch("urllib.request.urlopen", side_effect=_handle_request),
        ):
            run_authorization_flow("cid", "cs")

        captured = capsys.readouterr()
        assert "accounts.google.com" in captured.out
        assert "Waiting for authorization" in captured.out

        data = json.loads(token_file.read_text(encoding="utf-8"))
        assert data is not None
        assert data["refresh_token"] == "rt"
        assert data["access_token"] == "at"

    def test_no_code_received(self, tmp_path: Path):
        token_file = tmp_path / "oauth.json"

        with (
            patch("youtube_tools_mcp.youtube.oauth._TOKEN_FILE", token_file),
            patch("youtube_tools_mcp.youtube.oauth._find_free_port", return_value=65001),
            patch(
                "youtube_tools_mcp.youtube.oauth._wait_for_callback",
                return_value={"code": None, "state": None, "error": "access_denied"},
            ),
            patch("secrets.token_urlsafe", return_value="test_state"),
            pytest.raises(OAuthError, match="access_denied"),
        ):
            run_authorization_flow("cid", "cs")

    def test_state_mismatch(self, tmp_path: Path):
        token_file = tmp_path / "oauth.json"

        with (
            patch("youtube_tools_mcp.youtube.oauth._TOKEN_FILE", token_file),
            patch("youtube_tools_mcp.youtube.oauth._find_free_port", return_value=65002),
            patch(
                "youtube_tools_mcp.youtube.oauth._wait_for_callback",
                return_value={"code": "validcode", "state": "wrong_state", "error": None},
            ),
            patch("secrets.token_urlsafe", return_value="expected_state"),
            pytest.raises(OAuthError, match="Invalid state"),
        ):
            run_authorization_flow("cid", "cs")


class TestMain:
    def test_missing_client_id_exits(self, capsys):
        with patch.dict("os.environ", {}, clear=True), pytest.raises(SystemExit):
            from youtube_tools_mcp.youtube.oauth import main

            main()
        captured = capsys.readouterr()
        assert "YOUTUBE_OAUTH_CLIENT_ID" in captured.out

    def test_missing_client_secret_exits(self, capsys):
        with patch.dict("os.environ", {"YOUTUBE_OAUTH_CLIENT_ID": "id"}, clear=True), pytest.raises(SystemExit):
            from youtube_tools_mcp.youtube.oauth import main

            main()
        captured = capsys.readouterr()
        assert "YOUTUBE_OAUTH_CLIENT_SECRET" in captured.out
