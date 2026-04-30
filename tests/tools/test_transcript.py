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
