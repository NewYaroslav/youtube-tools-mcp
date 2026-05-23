from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from youtube_tools_mcp.youtube.listing import (
    ChannelNotFoundError,
    ListingError,
    PlaylistNotFoundError,
    _extract_entries_ytdlp,
    list_channel_playlists,
    list_channel_videos,
    list_playlist_videos,
)


def _mock_ytdl_context(mock_ydl_cls: MagicMock, entries: list[dict] | None) -> None:
    mock_ydl = MagicMock()
    if entries is None:
        mock_ydl.extract_info.return_value = None
    else:
        mock_ydl.extract_info.return_value = {"entries": entries}
    mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)


class TestExtractEntriesYtdlp:
    @patch("yt_dlp.YoutubeDL")
    def test_returns_entries(self, mock_ydl_cls: MagicMock) -> None:
        _mock_ytdl_context(mock_ydl_cls, [{"id": "abc123", "title": "Video 1"}])
        result = _extract_entries_ytdlp("https://youtube.com/playlist?list=PLtest", 10)
        assert len(result) == 1
        assert result[0]["id"] == "abc123"

    @patch("yt_dlp.YoutubeDL")
    def test_empty_entries_returns_empty_list(self, mock_ydl_cls: MagicMock) -> None:
        _mock_ytdl_context(mock_ydl_cls, [])
        result = _extract_entries_ytdlp("https://youtube.com/playlist?list=PLtest", 10)
        assert result == []

    @patch("yt_dlp.YoutubeDL")
    def test_none_info_raises(self, mock_ydl_cls: MagicMock) -> None:
        _mock_ytdl_context(mock_ydl_cls, None)
        with pytest.raises(ListingError, match="returned no info"):
            _extract_entries_ytdlp("https://youtube.com/playlist?list=PLtest", 10)

    @patch("yt_dlp.YoutubeDL")
    def test_applies_proxy(self, mock_ydl_cls: MagicMock) -> None:
        _mock_ytdl_context(mock_ydl_cls, [{"id": "v1"}])
        _extract_entries_ytdlp("url", 5, proxy="http://proxy:8080")
        opts = mock_ydl_cls.call_args[0][0]
        assert opts["proxy"] == "http://proxy:8080"

    @patch("yt_dlp.YoutubeDL")
    def test_applies_cookies_from_browser(self, mock_ydl_cls: MagicMock) -> None:
        _mock_ytdl_context(mock_ydl_cls, [{"id": "v1"}])
        _extract_entries_ytdlp("url", 5, cookies_from_browser="chrome")
        opts = mock_ydl_cls.call_args[0][0]
        assert opts["cookiesfrombrowser"] == ["chrome"]

    @patch("yt_dlp.YoutubeDL")
    def test_applies_client(self, mock_ydl_cls: MagicMock) -> None:
        _mock_ytdl_context(mock_ydl_cls, [{"id": "v1"}])
        _extract_entries_ytdlp("url", 5, client="android")
        opts = mock_ydl_cls.call_args[0][0]
        assert "Android" in opts["user_agent"]


class TestListPlaylistVideos:
    @patch("yt_dlp.YoutubeDL")
    def test_list_playlist(self, mock_ydl_cls: MagicMock) -> None:
        _mock_ytdl_context(
            mock_ydl_cls,
            [
                {"id": "vid1", "title": "Video 1", "duration": 120.0},
                {"id": "vid2", "title": "Video 2", "duration": 60.0},
            ],
        )
        result = list_playlist_videos("PLtest123", max_results=2)
        assert len(result) == 2
        assert result[0]["video_id"] == "vid1"
        assert result[0]["position"] == 1
        assert result[0]["duration"] == 120.0
        assert result[1]["position"] == 2

    @patch("yt_dlp.YoutubeDL")
    def test_empty_playlist_raises(self, mock_ydl_cls: MagicMock) -> None:
        _mock_ytdl_context(mock_ydl_cls, [])
        with pytest.raises(PlaylistNotFoundError):
            list_playlist_videos("PLempty", max_results=10)

    def test_invalid_id_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot extract"):
            list_playlist_videos("not-a-playlist")


class TestListChannelVideos:
    @patch("yt_dlp.YoutubeDL")
    def test_list_channel_by_id(self, mock_ydl_cls: MagicMock) -> None:
        _mock_ytdl_context(mock_ydl_cls, [{"id": "vid1", "title": "Upload 1"}])
        result = list_channel_videos("UCxxxxxxxxxxxxxxxxxxxxxx", max_results=1)
        assert len(result) == 1
        assert result[0]["video_id"] == "vid1"

    @patch("yt_dlp.YoutubeDL")
    def test_list_channel_by_handle(self, mock_ydl_cls: MagicMock) -> None:
        _mock_ytdl_context(mock_ydl_cls, [{"id": "vid1", "title": "Upload 1"}])
        result = list_channel_videos("@testhandle", max_results=1)
        assert len(result) == 1

    @patch("yt_dlp.YoutubeDL")
    def test_empty_channel_raises(self, mock_ydl_cls: MagicMock) -> None:
        _mock_ytdl_context(mock_ydl_cls, [])
        with pytest.raises(ChannelNotFoundError):
            list_channel_videos("UCxxxxxxxxxxxxxxxxxxxxxx", max_results=10)

    def test_invalid_id_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot extract"):
            list_channel_videos("not-a-channel")


class TestListChannelPlaylists:
    @patch("youtube_tools_mcp.youtube.listing._youtube_api_get")
    @patch.dict("os.environ", {"YOUTUBE_API_KEY": "test-key"})
    def test_list_channel_playlists(self, mock_get: MagicMock) -> None:
        mock_get.return_value = {
            "items": [
                {
                    "id": "PL1",
                    "snippet": {"title": "Playlist 1", "description": "Desc 1"},
                    "contentDetails": {"itemCount": 5},
                },
                {
                    "id": "PL2",
                    "snippet": {"title": "Playlist 2", "description": "Desc 2"},
                    "contentDetails": {"itemCount": 10},
                },
            ],
        }
        result = list_channel_playlists(
            "UCxxxxxxxxxxxxxxxxxxxxxx",
            max_results=10,
        )
        assert len(result) == 2
        assert result[0]["playlist_id"] == "PL1"
        assert result[0]["title"] == "Playlist 1"
        assert result[0]["video_count"] == 5
        assert result[1]["playlist_id"] == "PL2"
        assert result[1]["video_count"] == 10

    @patch.dict("os.environ", {}, clear=True)
    def test_no_api_key_raises(self) -> None:
        with pytest.raises(ListingError, match="YOUTUBE_API_KEY"):
            list_channel_playlists("UCxxxxxxxxxxxxxxxxxxxxxx")

    @patch("youtube_tools_mcp.youtube.listing._youtube_api_get")
    @patch.dict("os.environ", {"YOUTUBE_API_KEY": "test-key"})
    def test_api_failure_raises(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = Exception("quota exceeded")
        with pytest.raises(ChannelNotFoundError, match="Failed to fetch"):
            list_channel_playlists("UCxxxxxxxxxxxxxxxxxxxxxx")

    @patch("youtube_tools_mcp.youtube.listing._youtube_api_get")
    @patch.dict("os.environ", {"YOUTUBE_API_KEY": "test-key"})
    def test_empty_items_returns_empty_list(self, mock_get: MagicMock) -> None:
        mock_get.return_value = {"items": []}
        result = list_channel_playlists("UCxxxxxxxxxxxxxxxxxxxxxx")
        assert result == []
