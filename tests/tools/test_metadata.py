from __future__ import annotations

from unittest.mock import MagicMock, patch

from youtube_tools_mcp.tools.metadata import get_youtube_video_metadata
from youtube_tools_mcp.youtube.metadata import YouTubeVideoMetadata

from ..conftest import SAMPLE_VIDEO_ID


class TestGetYoutubeVideoMetadata:
    @patch("youtube_tools_mcp.tools.metadata.fetch_video_metadata")
    @patch("youtube_tools_mcp.tools.metadata.extract_video_id", return_value=SAMPLE_VIDEO_ID)
    def test_returns_json(self, mock_extract: MagicMock, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = YouTubeVideoMetadata(
            video_id=SAMPLE_VIDEO_ID,
            video_url=f"https://www.youtube.com/watch?v={SAMPLE_VIDEO_ID}",
            title="Test Video",
            source="yt-dlp",
        )

        result = get_youtube_video_metadata(SAMPLE_VIDEO_ID)

        assert "Test Video" in result
        assert SAMPLE_VIDEO_ID in result

    @patch("youtube_tools_mcp.tools.metadata.fetch_video_metadata")
    @patch("youtube_tools_mcp.tools.metadata.extract_video_id", return_value=SAMPLE_VIDEO_ID)
    def test_passes_proxy_to_fetch(self, mock_extract: MagicMock, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = YouTubeVideoMetadata(
            video_id=SAMPLE_VIDEO_ID,
            video_url=f"https://www.youtube.com/watch?v={SAMPLE_VIDEO_ID}",
            title="Proxy Test",
            source="yt-dlp",
        )

        get_youtube_video_metadata(SAMPLE_VIDEO_ID, proxy="http://proxy:8080")
        mock_fetch.assert_called_once_with(
            SAMPLE_VIDEO_ID,
            include_channel_description=True,
            proxy="http://proxy:8080",
        )
