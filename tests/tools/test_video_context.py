from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from mcp.shared.exceptions import McpError

from youtube_tools_mcp.tools.video_context import get_youtube_video_context
from youtube_tools_mcp.youtube.metadata import MetadataFetchError, YouTubeVideoMetadata
from youtube_tools_mcp.youtube.transcript import (
    InvalidVideoIdError,
    NoTranscriptFoundError,
    TranscriptsDisabledError,
    VideoUnavailableError,
)

from ..conftest import SAMPLE_URL, SAMPLE_VIDEO_ID


class TestGetYoutubeVideoContext:
    @patch("youtube_tools_mcp.tools.video_context.fetch_video_metadata")
    @patch("youtube_tools_mcp.tools.video_context.TranscriptFetcher")
    def test_returns_combined_json(
        self,
        mock_fetcher_cls: MagicMock,
        mock_fetch_metadata: MagicMock,
    ) -> None:
        mock_fetch_metadata.return_value = YouTubeVideoMetadata(
            video_id=SAMPLE_VIDEO_ID,
            video_url=f"https://www.youtube.com/watch?v={SAMPLE_VIDEO_ID}",
            title="Test Video",
            source="yt-dlp",
        )
        mock_fetcher = mock_fetcher_cls.return_value
        mock_fetcher.fetch.return_value = "[00:00] Hello world"

        result = get_youtube_video_context(SAMPLE_VIDEO_ID)

        data = json.loads(result)
        assert data["metadata"]["title"] == "Test Video"
        assert data["metadata"]["video_id"] == SAMPLE_VIDEO_ID
        assert data["transcript"] == "[00:00] Hello world"
        assert "metadata_error" not in data

    @patch("youtube_tools_mcp.tools.video_context.fetch_video_metadata")
    @patch("youtube_tools_mcp.tools.video_context.TranscriptFetcher")
    def test_accepts_url(
        self,
        mock_fetcher_cls: MagicMock,
        mock_fetch_metadata: MagicMock,
    ) -> None:
        mock_fetch_metadata.return_value = YouTubeVideoMetadata(
            video_id=SAMPLE_VIDEO_ID,
            video_url=f"https://www.youtube.com/watch?v={SAMPLE_VIDEO_ID}",
            title="URL Video",
            source="yt-dlp",
        )
        mock_fetcher = mock_fetcher_cls.return_value
        mock_fetcher.fetch.return_value = "[00:00] Hello"

        result = get_youtube_video_context(SAMPLE_URL)

        data = json.loads(result)
        assert data["metadata"]["title"] == "URL Video"
        mock_fetcher.fetch.assert_called_once_with(SAMPLE_VIDEO_ID, languages=("ru", "en"))

    @patch("youtube_tools_mcp.tools.video_context.fetch_video_metadata")
    @patch("youtube_tools_mcp.tools.video_context.TranscriptFetcher")
    def test_custom_languages(
        self,
        mock_fetcher_cls: MagicMock,
        mock_fetch_metadata: MagicMock,
    ) -> None:
        mock_fetch_metadata.return_value = YouTubeVideoMetadata(
            video_id=SAMPLE_VIDEO_ID,
            video_url=f"https://www.youtube.com/watch?v={SAMPLE_VIDEO_ID}",
            title="Lang Video",
            source="yt-dlp",
        )
        mock_fetcher = mock_fetcher_cls.return_value
        mock_fetcher.fetch.return_value = "[00:00] Bonjour"

        get_youtube_video_context(SAMPLE_VIDEO_ID, languages=["fr"])
        mock_fetcher.fetch.assert_called_once_with(SAMPLE_VIDEO_ID, languages=("fr",))

    @patch("youtube_tools_mcp.tools.video_context.fetch_video_metadata")
    @patch("youtube_tools_mcp.tools.video_context.TranscriptFetcher")
    def test_partial_result_when_metadata_fails(
        self,
        mock_fetcher_cls: MagicMock,
        mock_fetch_metadata: MagicMock,
    ) -> None:
        mock_fetch_metadata.side_effect = MetadataFetchError("yt-dlp blocked")
        mock_fetcher = mock_fetcher_cls.return_value
        mock_fetcher.fetch.return_value = "[00:00] Transcript only"

        result = get_youtube_video_context(SAMPLE_VIDEO_ID)

        data = json.loads(result)
        assert data["metadata"] is None
        assert "metadata_error" in data
        assert "yt-dlp blocked" in data["metadata_error"]
        assert data["transcript"] == "[00:00] Transcript only"

    @patch("youtube_tools_mcp.tools.video_context.fetch_video_metadata")
    @patch("youtube_tools_mcp.tools.video_context.TranscriptFetcher")
    def test_warning_included_when_fallback_occurs(
        self,
        mock_fetcher_cls: MagicMock,
        mock_fetch_metadata: MagicMock,
    ) -> None:
        metadata = YouTubeVideoMetadata(
            video_id=SAMPLE_VIDEO_ID,
            video_url=f"https://www.youtube.com/watch?v={SAMPLE_VIDEO_ID}",
            title="Fallback Video",
            source="yt-dlp",
            warnings=["youtube-data-api failed: API quota exceeded"],
        )
        mock_fetch_metadata.return_value = metadata
        mock_fetcher = mock_fetcher_cls.return_value
        mock_fetcher.fetch.return_value = "[00:00] Hello"

        result = get_youtube_video_context(SAMPLE_VIDEO_ID)

        data = json.loads(result)
        assert data["metadata"]["title"] == "Fallback Video"
        assert data["metadata_warnings"] == ["youtube-data-api failed: API quota exceeded"]

    @patch("youtube_tools_mcp.tools.video_context.fetch_video_metadata")
    @patch("youtube_tools_mcp.tools.video_context.TranscriptFetcher")
    def test_passes_timeout_options(
        self,
        mock_fetcher_cls: MagicMock,
        mock_fetch_metadata: MagicMock,
    ) -> None:
        mock_fetch_metadata.return_value = YouTubeVideoMetadata(
            video_id=SAMPLE_VIDEO_ID,
            video_url=f"https://www.youtube.com/watch?v={SAMPLE_VIDEO_ID}",
            title="Timeout Video",
            source="yt-dlp",
        )
        mock_fetcher = mock_fetcher_cls.return_value
        mock_fetcher.fetch.return_value = "[00:00] Hello"

        get_youtube_video_context(
            SAMPLE_VIDEO_ID,
            transcript_api_timeout=9.0,
            ytdlp_socket_timeout=30.0,
        )

        mock_fetch_metadata.assert_called_once_with(
            SAMPLE_VIDEO_ID,
            include_channel_description=True,
            proxy=None,
            cookies_from_browser=None,
            client="web",
            ytdlp_socket_timeout=30.0,
        )
        mock_fetcher_cls.assert_called_once_with(
            proxy_url=None,
            cookies_from_browser=None,
            client="web",
            transcript_api_timeout=9.0,
            ytdlp_socket_timeout=30.0,
        )

    def test_invalid_url_raises_mcp_error(self) -> None:
        with pytest.raises(McpError, match="Cannot extract YouTube video ID"):
            get_youtube_video_context("not_a_valid_id")

    @patch("youtube_tools_mcp.tools.video_context.fetch_video_metadata")
    @patch("youtube_tools_mcp.tools.video_context.TranscriptFetcher")
    def test_transcripts_disabled_raises_mcp_error(
        self,
        mock_fetcher_cls: MagicMock,
        mock_fetch_metadata: MagicMock,
    ) -> None:
        mock_fetch_metadata.return_value = YouTubeVideoMetadata(
            video_id=SAMPLE_VIDEO_ID,
            video_url=f"https://www.youtube.com/watch?v={SAMPLE_VIDEO_ID}",
            title="Test",
            source="yt-dlp",
        )
        mock_fetcher = mock_fetcher_cls.return_value
        mock_fetcher.fetch.side_effect = TranscriptsDisabledError("disabled")

        with pytest.raises(McpError, match="Transcripts are disabled"):
            get_youtube_video_context(SAMPLE_VIDEO_ID)

    @patch("youtube_tools_mcp.tools.video_context.fetch_video_metadata")
    @patch("youtube_tools_mcp.tools.video_context.TranscriptFetcher")
    def test_no_transcript_found_raises_mcp_error(
        self,
        mock_fetcher_cls: MagicMock,
        mock_fetch_metadata: MagicMock,
    ) -> None:
        mock_fetch_metadata.return_value = YouTubeVideoMetadata(
            video_id=SAMPLE_VIDEO_ID,
            video_url=f"https://www.youtube.com/watch?v={SAMPLE_VIDEO_ID}",
            title="Test",
            source="yt-dlp",
        )
        mock_fetcher = mock_fetcher_cls.return_value
        mock_fetcher.fetch.side_effect = NoTranscriptFoundError("not found")

        with pytest.raises(McpError, match="No transcript found"):
            get_youtube_video_context(SAMPLE_VIDEO_ID)

    @patch("youtube_tools_mcp.tools.video_context.fetch_video_metadata")
    @patch("youtube_tools_mcp.tools.video_context.TranscriptFetcher")
    def test_invalid_video_id_transcript_raises_mcp_error(
        self,
        mock_fetcher_cls: MagicMock,
        mock_fetch_metadata: MagicMock,
    ) -> None:
        mock_fetch_metadata.return_value = YouTubeVideoMetadata(
            video_id=SAMPLE_VIDEO_ID,
            video_url=f"https://www.youtube.com/watch?v={SAMPLE_VIDEO_ID}",
            title="Test",
            source="yt-dlp",
        )
        mock_fetcher = mock_fetcher_cls.return_value
        mock_fetcher.fetch.side_effect = InvalidVideoIdError("invalid")

        with pytest.raises(McpError, match="Invalid video ID"):
            get_youtube_video_context(SAMPLE_VIDEO_ID)

    @patch("youtube_tools_mcp.tools.video_context.fetch_video_metadata")
    @patch("youtube_tools_mcp.tools.video_context.TranscriptFetcher")
    def test_video_unavailable_transcript_raises_mcp_error(
        self,
        mock_fetcher_cls: MagicMock,
        mock_fetch_metadata: MagicMock,
    ) -> None:
        mock_fetch_metadata.return_value = YouTubeVideoMetadata(
            video_id=SAMPLE_VIDEO_ID,
            video_url=f"https://www.youtube.com/watch?v={SAMPLE_VIDEO_ID}",
            title="Test",
            source="yt-dlp",
        )
        mock_fetcher = mock_fetcher_cls.return_value
        mock_fetcher.fetch.side_effect = VideoUnavailableError("unavailable")

        with pytest.raises(McpError, match="Video unavailable"):
            get_youtube_video_context(SAMPLE_VIDEO_ID)
