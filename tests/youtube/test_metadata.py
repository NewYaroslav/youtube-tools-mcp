from __future__ import annotations

from unittest.mock import MagicMock, patch
from urllib.request import ProxyHandler

import pytest

from youtube_tools_mcp.youtube.metadata import (
    MetadataFetchError,
    YouTubeVideoMetadata,
    _extract_metadata_from_ytdlp_info,
    _parse_iso8601_duration,
    fetch_video_metadata,
    fetch_video_metadata_api,
    fetch_video_metadata_ytdlp,
)

from ..conftest import SAMPLE_VIDEO_ID


class TestParseIso8601Duration:
    def test_full_duration(self) -> None:
        assert _parse_iso8601_duration("PT1H2M3S") == 3723.0

    def test_minutes_only(self) -> None:
        assert _parse_iso8601_duration("PT5M30S") == 330.0

    def test_seconds_only(self) -> None:
        assert _parse_iso8601_duration("PT45S") == 45.0

    def test_hours_no_minutes_seconds(self) -> None:
        assert _parse_iso8601_duration("PT2H") == 7200.0

    def test_none_value(self) -> None:
        assert _parse_iso8601_duration(None) is None

    def test_days_duration(self) -> None:
        assert _parse_iso8601_duration("P1DT2H3M4S") == 93784.0

    def test_empty_period_returns_none(self) -> None:
        assert _parse_iso8601_duration("P") is None

    def test_empty_time_period_returns_none(self) -> None:
        assert _parse_iso8601_duration("PT") is None

    def test_invalid_format(self) -> None:
        assert _parse_iso8601_duration("not-a-duration") is None


class TestExtractMetadataFromYtdlpInfo:
    def test_extracts_all_fields(self) -> None:
        info = {
            "title": "Test Video",
            "description": "A test description",
            "channel_id": "UCtest123",
            "channel": "Test Channel",
            "channel_url": "https://www.youtube.com/channel/UCtest123",
            "channel_description": "Test channel description",
            "duration": 123,
            "upload_date": "20260520",
        }

        result = _extract_metadata_from_ytdlp_info(SAMPLE_VIDEO_ID, info)

        assert result.video_id == SAMPLE_VIDEO_ID
        assert result.title == "Test Video"
        assert result.description == "A test description"
        assert result.channel_id == "UCtest123"
        assert result.channel_title == "Test Channel"
        assert result.channel_url == "https://www.youtube.com/channel/UCtest123"
        assert result.channel_description == "Test channel description"
        assert result.duration == 123.0
        assert result.upload_date == "2026-05-20"
        assert result.source == "yt-dlp"

    def test_duration_float(self) -> None:
        info = {"title": "Test", "duration": 123.45}
        result = _extract_metadata_from_ytdlp_info(SAMPLE_VIDEO_ID, info)
        assert result.duration == 123.45

    def test_no_channel_url_uses_channel_id(self) -> None:
        info = {"title": "Test", "channel_id": "UCtest123"}
        result = _extract_metadata_from_ytdlp_info(SAMPLE_VIDEO_ID, info)
        assert result.channel_url == "https://www.youtube.com/channel/UCtest123"

    def test_empty_strings_become_none(self) -> None:
        info = {"title": "", "description": "   "}
        result = _extract_metadata_from_ytdlp_info(SAMPLE_VIDEO_ID, info)
        assert result.title is None
        assert result.description is None

    def test_uploader_fallback(self) -> None:
        info = {"uploader": "Uploader Name"}
        result = _extract_metadata_from_ytdlp_info(SAMPLE_VIDEO_ID, info)
        assert result.channel_title == "Uploader Name"


class TestFetchVideoMetadataYtdlp:
    @patch("yt_dlp.YoutubeDL")
    def test_fetch_metadata(self, mock_ydl_cls: MagicMock) -> None:
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {
            "title": "Mock Video",
            "duration": 100,
        }

        result = fetch_video_metadata_ytdlp(SAMPLE_VIDEO_ID)

        assert result.title == "Mock Video"
        assert result.duration == 100.0
        assert result.source == "yt-dlp"

    @patch("yt_dlp.YoutubeDL")
    def test_fetch_failure_raises(self, mock_ydl_cls: MagicMock) -> None:
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.side_effect = RuntimeError("network error")

        with pytest.raises(MetadataFetchError, match="network error"):
            fetch_video_metadata_ytdlp(SAMPLE_VIDEO_ID)

    @patch("yt_dlp.YoutubeDL")
    def test_non_dict_info_raises(self, mock_ydl_cls: MagicMock) -> None:
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = None

        with pytest.raises(MetadataFetchError, match="returned no metadata"):
            fetch_video_metadata_ytdlp(SAMPLE_VIDEO_ID)

    @patch.dict("os.environ", {"HTTPS_PROXY": "http://127.0.0.1:8080"})
    @patch("yt_dlp.YoutubeDL")
    def test_uses_proxy_when_set(self, mock_ydl_cls: MagicMock) -> None:
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {"title": "Proxy Test", "duration": 60}

        fetch_video_metadata_ytdlp(SAMPLE_VIDEO_ID)

        opts = mock_ydl_cls.call_args[0][0]
        assert opts["proxy"] == "http://127.0.0.1:8080"

    @patch("yt_dlp.YoutubeDL")
    def test_no_proxy_when_not_set(self, mock_ydl_cls: MagicMock) -> None:
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {"title": "No Proxy Test", "duration": 30}

        with patch.dict("os.environ", {}, clear=True):
            fetch_video_metadata_ytdlp(SAMPLE_VIDEO_ID)

        opts = mock_ydl_cls.call_args[0][0]
        assert "proxy" not in opts


class TestYoutubeApiGet:
    @patch("youtube_tools_mcp.youtube.metadata.build_opener")
    @patch("youtube_tools_mcp.youtube.metadata.urlopen")
    @patch.dict("os.environ", {"HTTPS_PROXY": "http://127.0.0.1:8080"})
    def test_uses_proxy_when_set(self, mock_urlopen: MagicMock, mock_build_opener: MagicMock) -> None:
        mock_opener = MagicMock()
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"items": []}'
        mock_opener.open.return_value.__enter__ = MagicMock(return_value=mock_response)
        mock_opener.open.return_value.__exit__ = MagicMock(return_value=False)
        mock_build_opener.return_value = mock_opener

        from youtube_tools_mcp.youtube.metadata import _youtube_api_get

        _youtube_api_get("videos", {"id": SAMPLE_VIDEO_ID, "key": "test"})

        mock_build_opener.assert_called_once()
        handler = mock_build_opener.call_args[0][0]
        assert isinstance(handler, ProxyHandler)

    @patch("youtube_tools_mcp.youtube.metadata.urlopen")
    @patch("youtube_tools_mcp.youtube.metadata.build_opener")
    def test_no_proxy_when_not_set(self, mock_build_opener: MagicMock, mock_urlopen: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"items": []}'
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_response)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        from youtube_tools_mcp.youtube.metadata import _youtube_api_get

        with patch.dict("os.environ", {}, clear=True):
            _youtube_api_get("videos", {"id": SAMPLE_VIDEO_ID, "key": "test"})

        mock_build_opener.assert_not_called()
        mock_urlopen.assert_called_once()


class TestFetchVideoMetadataApi:
    @patch("youtube_tools_mcp.youtube.metadata._youtube_api_get")
    def test_fetch_via_api(self, mock_get: MagicMock) -> None:
        def _side_effect(path: str, _params: dict[str, str]) -> dict[str, object]:
            if path == "videos":
                return {
                    "items": [
                        {
                            "snippet": {
                                "title": "API Video",
                                "description": "API desc",
                                "channelId": "UCapi",
                                "channelTitle": "API Channel",
                                "publishedAt": "2026-05-20T10:00:00Z",
                            },
                            "contentDetails": {
                                "duration": "PT5M30S",
                            },
                        },
                    ],
                }
            if path == "channels":
                return {
                    "items": [
                        {
                            "snippet": {
                                "description": "Channel desc",
                                "customUrl": "api_channel",
                            },
                        },
                    ],
                }
            return {}

        mock_get.side_effect = _side_effect

        result = fetch_video_metadata_api(SAMPLE_VIDEO_ID, "test-key")

        assert result.title == "API Video"
        assert result.description == "API desc"
        assert result.channel_id == "UCapi"
        assert result.channel_title == "API Channel"
        assert result.duration == 330.0
        assert result.upload_date == "2026-05-20T10:00:00Z"
        assert result.source == "youtube-data-api"
        assert result.channel_description == "Channel desc"
        assert result.channel_url == "https://www.youtube.com/api_channel"

    @patch("youtube_tools_mcp.youtube.metadata._youtube_api_get")
    def test_api_no_items_raises(self, mock_get: MagicMock) -> None:
        mock_get.return_value = {"items": []}

        with pytest.raises(MetadataFetchError, match="returned no video"):
            fetch_video_metadata_api(SAMPLE_VIDEO_ID, "test-key")

    @patch("youtube_tools_mcp.youtube.metadata._youtube_api_get")
    def test_api_no_snippet_raises(self, mock_get: MagicMock) -> None:
        mock_get.return_value = {"items": [{}]}

        with pytest.raises(MetadataFetchError, match="no snippet"):
            fetch_video_metadata_api(SAMPLE_VIDEO_ID, "test-key")

    @patch("youtube_tools_mcp.youtube.metadata._youtube_api_get")
    def test_api_channel_failure_returns_video_with_warning(self, mock_get: MagicMock) -> None:
        def _side_effect(path: str, _params: dict[str, str]) -> dict[str, object]:
            if path == "videos":
                return {
                    "items": [
                        {
                            "snippet": {
                                "title": "API Video",
                                "description": "API desc",
                                "channelId": "UCapi",
                                "channelTitle": "API Channel",
                                "publishedAt": "2026-05-20T10:00:00Z",
                            },
                            "contentDetails": {
                                "duration": "PT5M30S",
                            },
                        },
                    ],
                }
            if path == "channels":
                raise MetadataFetchError("channel quota exceeded")
            return {}

        mock_get.side_effect = _side_effect

        result = fetch_video_metadata_api(SAMPLE_VIDEO_ID, "test-key")

        assert result.title == "API Video"
        assert result.source == "youtube-data-api"
        assert len(result.warnings) == 1
        assert "channel quota exceeded" in result.warnings[0]


class TestFetchVideoMetadataFallback:
    @patch.dict("os.environ", {"YOUTUBE_API_KEY": "test-key"})
    @patch("youtube_tools_mcp.youtube.metadata.fetch_video_metadata_api")
    @patch("youtube_tools_mcp.youtube.metadata.fetch_video_metadata_ytdlp")
    def test_api_success_no_fallback(
        self,
        mock_ytdlp: MagicMock,
        mock_api: MagicMock,
    ) -> None:
        mock_api.return_value = YouTubeVideoMetadata(
            video_id=SAMPLE_VIDEO_ID,
            video_url=f"https://www.youtube.com/watch?v={SAMPLE_VIDEO_ID}",
            title="API Title",
            source="youtube-data-api",
        )

        result = fetch_video_metadata(SAMPLE_VIDEO_ID)

        assert result.title == "API Title"
        assert result.source == "youtube-data-api"
        mock_ytdlp.assert_not_called()

    @patch.dict("os.environ", {"YOUTUBE_API_KEY": "test-key"})
    @patch("youtube_tools_mcp.youtube.metadata.fetch_video_metadata_api")
    @patch("youtube_tools_mcp.youtube.metadata.fetch_video_metadata_ytdlp")
    def test_api_failure_falls_back_to_ytdlp(
        self,
        mock_ytdlp: MagicMock,
        mock_api: MagicMock,
    ) -> None:
        mock_api.side_effect = MetadataFetchError("API quota exceeded")
        mock_ytdlp.return_value = YouTubeVideoMetadata(
            video_id=SAMPLE_VIDEO_ID,
            video_url=f"https://www.youtube.com/watch?v={SAMPLE_VIDEO_ID}",
            title="YTDL Title",
            source="yt-dlp",
        )

        result = fetch_video_metadata(SAMPLE_VIDEO_ID)

        assert result.title == "YTDL Title"
        assert result.source == "yt-dlp"
        assert len(result.warnings) == 1
        assert "API quota exceeded" in result.warnings[0]
        mock_api.assert_called_once()
        mock_ytdlp.assert_called_once()

    @patch("youtube_tools_mcp.youtube.metadata.fetch_video_metadata_ytdlp")
    def test_no_api_key_uses_ytdlp(self, mock_ytdlp: MagicMock) -> None:
        mock_ytdlp.return_value = YouTubeVideoMetadata(
            video_id=SAMPLE_VIDEO_ID,
            video_url=f"https://www.youtube.com/watch?v={SAMPLE_VIDEO_ID}",
            title="YTDL Title",
            source="yt-dlp",
        )

        with patch.dict("os.environ", {}, clear=True):
            result = fetch_video_metadata(SAMPLE_VIDEO_ID)

        assert result.title == "YTDL Title"
        assert result.source == "yt-dlp"
