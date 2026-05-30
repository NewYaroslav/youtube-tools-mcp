from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from youtube_tools_mcp.youtube.oauth import (
    OAuthError,
    _load_token_data,
    _save_token_data,
    get_access_token,
    refresh_access_token,
    run_device_flow,
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


class TestRunDeviceFlow:
    def test_success(self, tmp_path: Path, capsys):
        token_file = tmp_path / "oauth.json"
        device_resp = MockResponse(
            {
                "device_code": "dc",
                "user_code": "uc",
                "verification_url": "http://verify",
                "expires_in": 600,
                "interval": 1,
            }
        )
        token_resp = MockResponse(
            {
                "refresh_token": "rt",
                "access_token": "at",
                "expires_in": 3600,
            }
        )
        call_iter = iter([device_resp, token_resp])

        with (
            patch("youtube_tools_mcp.youtube.oauth._TOKEN_FILE", token_file),
            patch("urllib.request.urlopen", side_effect=lambda req, **kw: next(call_iter)),
            patch("time.sleep"),
            patch("time.time", side_effect=[0, 10, 20]),
        ):
            run_device_flow("cid", "cs")

        captured = capsys.readouterr()
        assert "http://verify" in captured.out
        assert "uc" in captured.out
        assert "successful" in captured.out

        data = json.loads(token_file.read_text(encoding="utf-8"))
        assert data is not None
        assert data["refresh_token"] == "rt"
        assert data["access_token"] == "at"

    def test_authorization_pending(self, tmp_path: Path, capsys):
        token_file = tmp_path / "oauth.json"
        device_resp = MockResponse(
            {
                "device_code": "dc",
                "user_code": "uc",
                "verification_url": "http://verify",
                "expires_in": 600,
                "interval": 1,
            }
        )
        pending_resp = MockResponse({"error": "authorization_pending"})
        token_resp = MockResponse(
            {
                "refresh_token": "rt",
                "access_token": "at",
                "expires_in": 3600,
            }
        )
        call_iter = iter([device_resp, pending_resp, token_resp])

        with (
            patch("youtube_tools_mcp.youtube.oauth._TOKEN_FILE", token_file),
            patch("urllib.request.urlopen", side_effect=lambda req, **kw: next(call_iter)),
            patch("time.sleep"),
            patch("time.time", side_effect=[0, 10, 20, 30]),
        ):
            run_device_flow("cid", "cs")

        data = json.loads(token_file.read_text(encoding="utf-8"))
        assert data is not None
        assert data["refresh_token"] == "rt"

    def test_expired_device_code(self, tmp_path: Path):
        token_file = tmp_path / "oauth.json"
        device_resp = MockResponse(
            {
                "device_code": "dc",
                "user_code": "uc",
                "verification_url": "http://verify",
                "expires_in": 1,
                "interval": 1,
            }
        )
        call_iter = iter([device_resp])

        with (
            patch("youtube_tools_mcp.youtube.oauth._TOKEN_FILE", token_file),
            patch("urllib.request.urlopen", side_effect=lambda req, **kw: next(call_iter)),
            patch("time.sleep"),
            patch("time.time", side_effect=[0, 2]),
            pytest.raises(OAuthError, match="expired"),
        ):
            run_device_flow("cid", "cs")

    def test_invalid_device_response(self):
        bad_resp = MockResponse({"incomplete": True})

        with patch("urllib.request.urlopen", return_value=bad_resp), pytest.raises(
            OAuthError, match="Invalid device code"
        ):
            run_device_flow("cid", "cs")

    def test_oauth_error(self):
        device_resp = MockResponse(
            {
                "device_code": "dc",
                "user_code": "uc",
                "verification_url": "http://verify",
                "expires_in": 600,
                "interval": 1,
            }
        )
        error_resp = MockResponse({"error": "access_denied", "error_description": "User denied"})
        call_iter = iter([device_resp, error_resp])

        with (
            patch("urllib.request.urlopen", side_effect=lambda req, **kw: next(call_iter)),
            patch("time.sleep"),
            patch("time.time", side_effect=[0, 10]),
            pytest.raises(OAuthError, match="User denied"),
        ):
            run_device_flow("cid", "cs")

    def test_missing_refresh_token(self):
        device_resp = MockResponse(
            {
                "device_code": "dc",
                "user_code": "uc",
                "verification_url": "http://verify",
                "expires_in": 600,
                "interval": 1,
            }
        )
        token_resp = MockResponse({"access_token": "at"})  # no refresh_token
        call_iter = iter([device_resp, token_resp])

        with (
            patch("urllib.request.urlopen", side_effect=lambda req, **kw: next(call_iter)),
            patch("time.sleep"),
            patch("time.time", side_effect=[0, 10]),
            pytest.raises(OAuthError, match="No refresh token"),
        ):
            run_device_flow("cid", "cs")


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
