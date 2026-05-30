from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from youtube_tools_mcp.youtube.captions import (
    CaptionDownloadError,
    CaptionListError,
    _parse_srt,
    download_caption_track,
    fetch_transcript_via_data_api,
    list_caption_tracks,
)
from youtube_tools_mcp.youtube.transcript import TranscriptFetchError


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


_SRT_SAMPLE = """1
00:00:01,000 --> 00:00:04,000
Hello world

2
00:00:04,000 --> 00:00:07,500
Second line
with break

3
00:01:02,500 --> 00:01:05,000
Third cue
"""


class TestParseSrt:
    def test_parses_sample(self):
        result = _parse_srt(_SRT_SAMPLE)
        assert len(result) == 3
        assert result[0]["text"] == "Hello world"
        assert result[0]["start"] == 1.0
        assert result[0]["duration"] == 3.0
        assert result[1]["text"] == "Second line with break"
        assert result[1]["start"] == 4.0
        assert abs(result[1]["duration"] - 3.5) < 0.01
        assert result[2]["text"] == "Third cue"
        assert result[2]["start"] == 62.5
        assert abs(result[2]["duration"] - 2.5) < 0.01

    def test_empty(self):
        assert _parse_srt("") == []

    def test_single_entry(self):
        raw = """1
00:00:10,000 --> 00:00:15,000
Only one
"""
        result = _parse_srt(raw)
        assert len(result) == 1
        assert result[0]["text"] == "Only one"
        assert result[0]["start"] == 10.0
        assert result[0]["duration"] == 5.0


class TestListCaptionTracks:
    def test_returns_tracks(self):
        mock_resp = MockResponse(
            {
                "items": [
                    {
                        "id": "cid1",
                        "snippet": {
                            "language": "ru",
                            "name": "Russian",
                            "trackKind": "asr",
                        },
                    },
                    {
                        "id": "cid2",
                        "snippet": {
                            "language": "en",
                            "name": "English",
                            "trackKind": "standard",
                        },
                    },
                ],
            }
        )

        with patch("urllib.request.urlopen", return_value=mock_resp):
            tracks = list_caption_tracks("vid123", api_key="test_key")

        assert len(tracks) == 2
        assert tracks[0]["id"] == "cid1"
        assert tracks[0]["language"] == "ru"
        assert tracks[0]["is_auto_generated"] is True
        assert tracks[1]["language"] == "en"
        assert tracks[1]["is_auto_generated"] is False

    def test_empty_items(self):
        mock_resp = MockResponse({"items": []})
        with patch("urllib.request.urlopen", return_value=mock_resp):
            tracks = list_caption_tracks("vid123", api_key="test_key")
        assert tracks == []

    def test_http_error(self):
        from urllib.error import HTTPError

        with (
            patch(
                "urllib.request.urlopen",
                side_effect=HTTPError("url", 403, "Forbidden", {}, None),
            ),
            pytest.raises(CaptionListError, match="403"),
        ):
            list_caption_tracks("vid123", api_key="test_key")


class TestDownloadCaptionTrack:
    def test_returns_text(self):
        mock_resp = MockResponse(_SRT_SAMPLE)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = download_caption_track("cid1", "access_token_123")
        assert "Hello world" in result

    def test_http_error(self):
        from urllib.error import HTTPError

        with (
            patch(
                "urllib.request.urlopen",
                side_effect=HTTPError("url", 403, "Forbidden", {}, None),
            ),
            pytest.raises(CaptionDownloadError, match="403"),
        ):
            download_caption_track("cid1", "access_token_123")


class TestFetchTranscriptViaDataApi:
    def test_no_oauth_token(self):
        with (
            patch("youtube_tools_mcp.youtube.captions.get_access_token", return_value=None),
            pytest.raises(TranscriptFetchError, match="OAuth token not available"),
        ):
            fetch_transcript_via_data_api("vid123", ("ru",))

    def test_no_tracks(self):
        with (
            patch("youtube_tools_mcp.youtube.captions.get_access_token", return_value="at"),
            patch("youtube_tools_mcp.youtube.captions.list_caption_tracks", return_value=[]),
            pytest.raises(TranscriptFetchError, match="No caption tracks"),
        ):
            fetch_transcript_via_data_api("vid123", ("ru",))

    def test_caption_list_error_is_wrapped_as_transcript_fetch_error(self):
        with (
            patch("youtube_tools_mcp.youtube.captions.get_access_token", return_value="at"),
            patch(
                "youtube_tools_mcp.youtube.captions.list_caption_tracks",
                side_effect=CaptionListError("HTTP 403"),
            ),
            pytest.raises(TranscriptFetchError, match="HTTP 403"),
        ):
            fetch_transcript_via_data_api("vid123", ("ru",))

    def test_caption_download_error_is_wrapped_as_transcript_fetch_error(self):
        tracks = [
            {"id": "cid1", "language": "ru", "name": "Russian", "is_auto_generated": True},
        ]
        with (
            patch("youtube_tools_mcp.youtube.captions.get_access_token", return_value="at"),
            patch("youtube_tools_mcp.youtube.captions.list_caption_tracks", return_value=tracks),
            patch(
                "youtube_tools_mcp.youtube.captions.download_caption_track",
                side_effect=CaptionDownloadError("HTTP 403"),
            ),
            pytest.raises(TranscriptFetchError, match="HTTP 403"),
        ):
            fetch_transcript_via_data_api("vid123", ("ru",))

    def test_success_exact_match(self):
        tracks = [
            {"id": "cid1", "language": "ru", "name": "Russian", "is_auto_generated": True},
            {"id": "cid2", "language": "en", "name": "English", "is_auto_generated": False},
        ]
        with (
            patch("youtube_tools_mcp.youtube.captions.get_access_token", return_value="at"),
            patch("youtube_tools_mcp.youtube.captions.list_caption_tracks", return_value=tracks),
            patch(
                "youtube_tools_mcp.youtube.captions.download_caption_track",
                return_value=_SRT_SAMPLE,
            ),
        ):
            result = fetch_transcript_via_data_api("vid123", ("en",))

        assert "[00:01] Hello world" in result
        assert "Second line with break" in result

    def test_fallback_first_available(self):
        tracks = [
            {"id": "cid1", "language": "de", "name": "German", "is_auto_generated": False},
        ]
        with (
            patch("youtube_tools_mcp.youtube.captions.get_access_token", return_value="at"),
            patch("youtube_tools_mcp.youtube.captions.list_caption_tracks", return_value=tracks),
            patch(
                "youtube_tools_mcp.youtube.captions.download_caption_track",
                return_value=_SRT_SAMPLE,
            ),
        ):
            result = fetch_transcript_via_data_api("vid123", ("ru",))

        assert "Hello world" in result

    def test_empty_caption_id(self):
        tracks = [{"id": None, "language": "ru", "name": "Russian", "is_auto_generated": True}]
        with (
            patch("youtube_tools_mcp.youtube.captions.get_access_token", return_value="at"),
            patch("youtube_tools_mcp.youtube.captions.list_caption_tracks", return_value=tracks),
            pytest.raises(TranscriptFetchError, match="no ID"),
        ):
            fetch_transcript_via_data_api("vid123", ("ru",))

    def test_empty_srt(self):
        tracks = [
            {"id": "cid1", "language": "ru", "name": "Russian", "is_auto_generated": True},
        ]
        with (
            patch("youtube_tools_mcp.youtube.captions.get_access_token", return_value="at"),
            patch("youtube_tools_mcp.youtube.captions.list_caption_tracks", return_value=tracks),
            patch(
                "youtube_tools_mcp.youtube.captions.download_caption_track",
                return_value="invalid",
            ),
            pytest.raises(TranscriptFetchError, match="empty"),
        ):
            fetch_transcript_via_data_api("vid123", ("ru",))
