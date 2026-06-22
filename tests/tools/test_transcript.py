from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from mcp.shared.exceptions import McpError

from youtube_tools_mcp.tools.transcript import get_youtube_transcript
from youtube_tools_mcp.youtube.transcript import (
    InvalidVideoIdError,
    NoTranscriptFoundError,
    TranscriptsDisabledError,
    VideoUnavailableError,
)

from ..conftest import SAMPLE_URL, SAMPLE_VIDEO_ID


@pytest.fixture(autouse=True)
def _clear_cookies_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("YOUTUBE_TOOLS_COOKIES_FROM_BROWSER", raising=False)


class TestGetYoutubeTranscript:
    @patch("youtube_tools_mcp.tools.transcript.TranscriptFetcher")
    def test_returns_transcript_text(self, mock_fetcher_cls: MagicMock) -> None:
        mock_fetcher = mock_fetcher_cls.return_value
        mock_fetcher.fetch.return_value = "[00:00] Hello world"

        result = get_youtube_transcript(SAMPLE_VIDEO_ID)
        assert result == "[00:00] Hello world"

    @patch("youtube_tools_mcp.tools.transcript.TranscriptFetcher")
    def test_accepts_url(self, mock_fetcher_cls: MagicMock) -> None:
        mock_fetcher = mock_fetcher_cls.return_value
        mock_fetcher.fetch.return_value = "[00:00] Hello"

        result = get_youtube_transcript(SAMPLE_URL)
        assert "Hello" in result
        mock_fetcher.fetch.assert_called_once_with(SAMPLE_VIDEO_ID, languages=("ru", "en"))

    @patch("youtube_tools_mcp.tools.transcript.TranscriptFetcher")
    def test_custom_languages(self, mock_fetcher_cls: MagicMock) -> None:
        mock_fetcher = mock_fetcher_cls.return_value
        mock_fetcher.fetch.return_value = "[00:00] Bonjour"

        get_youtube_transcript(SAMPLE_VIDEO_ID, languages=["fr"])
        mock_fetcher.fetch.assert_called_once_with(SAMPLE_VIDEO_ID, languages=("fr",))

    def test_invalid_url_raises_mcp_error(self) -> None:
        with pytest.raises(McpError, match="Cannot extract YouTube video ID"):
            get_youtube_transcript("not_a_valid_id")

    @patch("youtube_tools_mcp.tools.transcript.TranscriptFetcher")
    def test_transcripts_disabled_raises_mcp_error(self, mock_fetcher_cls: MagicMock) -> None:
        mock_fetcher = mock_fetcher_cls.return_value
        mock_fetcher.fetch.side_effect = TranscriptsDisabledError("disabled")

        with pytest.raises(McpError, match="Transcripts are disabled"):
            get_youtube_transcript(SAMPLE_VIDEO_ID)

    @patch("youtube_tools_mcp.tools.transcript.TranscriptFetcher")
    def test_no_transcript_found_raises_mcp_error(self, mock_fetcher_cls: MagicMock) -> None:
        mock_fetcher = mock_fetcher_cls.return_value
        mock_fetcher.fetch.side_effect = NoTranscriptFoundError("not found")

        with pytest.raises(McpError, match="No transcript found"):
            get_youtube_transcript(SAMPLE_VIDEO_ID)

    @patch("youtube_tools_mcp.tools.transcript.TranscriptFetcher")
    def test_invalid_video_id_raises_mcp_error(self, mock_fetcher_cls: MagicMock) -> None:
        mock_fetcher = mock_fetcher_cls.return_value
        mock_fetcher.fetch.side_effect = InvalidVideoIdError("invalid")

        with pytest.raises(McpError, match="Invalid video ID"):
            get_youtube_transcript(SAMPLE_VIDEO_ID)

    @patch("youtube_tools_mcp.tools.transcript.TranscriptFetcher")
    def test_video_unavailable_raises_mcp_error(self, mock_fetcher_cls: MagicMock) -> None:
        mock_fetcher = mock_fetcher_cls.return_value
        mock_fetcher.fetch.side_effect = VideoUnavailableError("unavailable")

        with pytest.raises(McpError, match="Video unavailable"):
            get_youtube_transcript(SAMPLE_VIDEO_ID)

    @patch("youtube_tools_mcp.tools.transcript.TranscriptFetcher")
    def test_default_languages(self, mock_fetcher_cls: MagicMock) -> None:
        mock_fetcher = mock_fetcher_cls.return_value
        mock_fetcher.fetch.return_value = "[00:00] Test"

        get_youtube_transcript(SAMPLE_VIDEO_ID)
        mock_fetcher.fetch.assert_called_once_with(SAMPLE_VIDEO_ID, languages=("ru", "en"))

    @patch("youtube_tools_mcp.tools.transcript.TranscriptFetcher")
    def test_passes_proxy_to_fetcher(self, mock_fetcher_cls: MagicMock) -> None:
        mock_fetcher = mock_fetcher_cls.return_value
        mock_fetcher.fetch.return_value = "[00:00] Test"

        get_youtube_transcript(SAMPLE_VIDEO_ID, proxy="http://proxy:8080")
        mock_fetcher_cls.assert_called_once_with(
            proxy_url="http://proxy:8080",
            cookies_from_browser=None,
            client="web",
            transcript_api_timeout=None,
            ytdlp_socket_timeout=None,
        )
        mock_fetcher.fetch.assert_called_once_with(SAMPLE_VIDEO_ID, languages=("ru", "en"))

    @patch("youtube_tools_mcp.tools.transcript.TranscriptFetcher")
    def test_passes_cookies_and_client(self, mock_fetcher_cls: MagicMock) -> None:
        mock_fetcher = mock_fetcher_cls.return_value
        mock_fetcher.fetch.return_value = "[00:00] Test"

        get_youtube_transcript(
            SAMPLE_VIDEO_ID,
            proxy="http://proxy:8080",
            cookies_from_browser="firefox",
            client="android",
        )
        mock_fetcher_cls.assert_called_once_with(
            proxy_url="http://proxy:8080",
            cookies_from_browser="firefox",
            client="android",
            transcript_api_timeout=None,
            ytdlp_socket_timeout=None,
        )

    @patch("youtube_tools_mcp.tools.transcript.TranscriptFetcher")
    def test_uses_cookies_from_environment(self, mock_fetcher_cls: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_fetcher = mock_fetcher_cls.return_value
        mock_fetcher.fetch.return_value = "[00:00] Test"
        monkeypatch.setenv("YOUTUBE_TOOLS_COOKIES_FROM_BROWSER", " firefox ")

        get_youtube_transcript(SAMPLE_VIDEO_ID)

        mock_fetcher_cls.assert_called_once_with(
            proxy_url=None,
            cookies_from_browser="firefox",
            client="web",
            transcript_api_timeout=None,
            ytdlp_socket_timeout=None,
        )

    @patch("youtube_tools_mcp.tools.transcript.TranscriptFetcher")
    def test_explicit_cookies_override_environment(
        self,
        mock_fetcher_cls: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_fetcher = mock_fetcher_cls.return_value
        mock_fetcher.fetch.return_value = "[00:00] Test"
        monkeypatch.setenv("YOUTUBE_TOOLS_COOKIES_FROM_BROWSER", "firefox")

        get_youtube_transcript(SAMPLE_VIDEO_ID, cookies_from_browser="chrome")

        mock_fetcher_cls.assert_called_once_with(
            proxy_url=None,
            cookies_from_browser="chrome",
            client="web",
            transcript_api_timeout=None,
            ytdlp_socket_timeout=None,
        )

    @patch("youtube_tools_mcp.tools.transcript.TranscriptFetcher")
    def test_empty_explicit_cookies_disable_environment(
        self,
        mock_fetcher_cls: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_fetcher = mock_fetcher_cls.return_value
        mock_fetcher.fetch.return_value = "[00:00] Test"
        monkeypatch.setenv("YOUTUBE_TOOLS_COOKIES_FROM_BROWSER", "firefox")

        get_youtube_transcript(SAMPLE_VIDEO_ID, cookies_from_browser=" ")

        mock_fetcher_cls.assert_called_once_with(
            proxy_url=None,
            cookies_from_browser=None,
            client="web",
            transcript_api_timeout=None,
            ytdlp_socket_timeout=None,
        )

    @patch("youtube_tools_mcp.tools.transcript.TranscriptFetcher")
    def test_blank_environment_cookies_are_ignored(
        self,
        mock_fetcher_cls: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_fetcher = mock_fetcher_cls.return_value
        mock_fetcher.fetch.return_value = "[00:00] Test"
        monkeypatch.setenv("YOUTUBE_TOOLS_COOKIES_FROM_BROWSER", " ")

        get_youtube_transcript(SAMPLE_VIDEO_ID)

        mock_fetcher_cls.assert_called_once_with(
            proxy_url=None,
            cookies_from_browser=None,
            client="web",
            transcript_api_timeout=None,
            ytdlp_socket_timeout=None,
        )

    @patch("youtube_tools_mcp.tools.transcript.TranscriptFetcher")
    def test_passes_timeout_options_to_fetcher(self, mock_fetcher_cls: MagicMock) -> None:
        mock_fetcher = mock_fetcher_cls.return_value
        mock_fetcher.fetch.return_value = "[00:00] Test"

        get_youtube_transcript(
            SAMPLE_VIDEO_ID,
            transcript_api_timeout=12.5,
            ytdlp_socket_timeout=30.0,
        )

        mock_fetcher_cls.assert_called_once_with(
            proxy_url=None,
            cookies_from_browser=None,
            client="web",
            transcript_api_timeout=12.5,
            ytdlp_socket_timeout=30.0,
        )
