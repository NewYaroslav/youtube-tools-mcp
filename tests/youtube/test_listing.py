from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from youtube_tools_mcp.youtube.listing import (
    ChannelListError,
    ListingError,
    PlaylistNotFoundError,
    _clamp_max_results,
    _extract_entries_ytdlp,
    _resolve_channel_id_for_api,
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


class TestClampMaxResults:
    def test_returns_value_when_in_range(self) -> None:
        assert _clamp_max_results(25, max_allowed=50) == 25

    def test_clamps_to_max_allowed(self) -> None:
        assert _clamp_max_results(100, max_allowed=50) == 50

    def test_raises_on_zero(self) -> None:
        with pytest.raises(ListingError, match="max_results must be >= 1"):
            _clamp_max_results(0, max_allowed=50)

    def test_raises_on_negative(self) -> None:
        with pytest.raises(ListingError, match="max_results must be >= 1"):
            _clamp_max_results(-5, max_allowed=50)


class TestResolveChannelIdForApi:
    @patch("youtube_tools_mcp.youtube.listing._youtube_api_get")
    @patch.dict("os.environ", {"YOUTUBE_API_KEY": "test-key"})
    def test_returns_raw_channel_id(self, mock_get: MagicMock) -> None:
        result = _resolve_channel_id_for_api("UCxxxxxxxxxxxxxxxxxxxxxx", api_key="test-key")
        assert result == "UCxxxxxxxxxxxxxxxxxxxxxx"
        mock_get.assert_not_called()

    @patch("youtube_tools_mcp.youtube.listing._youtube_api_get")
    @patch.dict("os.environ", {"YOUTUBE_API_KEY": "test-key"})
    def test_resolves_handle_via_api(self, mock_get: MagicMock) -> None:
        mock_get.return_value = {
            "items": [{"id": "UCresolvedxxxxxxxxxxxxxx"}],
        }
        result = _resolve_channel_id_for_api("@testhandle", api_key="test-key")
        assert result == "UCresolvedxxxxxxxxxxxxxx"
        mock_get.assert_called_once()
        args, _ = mock_get.call_args
        assert args[1]["forHandle"] == "testhandle"

    @patch("youtube_tools_mcp.youtube.listing._youtube_api_get")
    @patch.dict("os.environ", {"YOUTUBE_API_KEY": "test-key"})
    def test_raises_when_handle_not_found(self, mock_get: MagicMock) -> None:
        mock_get.return_value = {"items": []}
        with pytest.raises(ChannelListError, match="Handle @testhandle not found"):
            _resolve_channel_id_for_api("@testhandle", api_key="test-key")

    def test_raises_on_invalid_input(self) -> None:
        with pytest.raises(ChannelListError, match="Cannot extract"):
            _resolve_channel_id_for_api("not-a-channel", api_key="test-key")


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
        result = list_playlist_videos("PLtest1234", max_results=2)
        assert len(result) == 2
        assert result[0]["video_id"] == "vid1"
        assert result[0]["position"] == 1
        assert result[0]["duration"] == 120.0
        assert result[1]["position"] == 2

    @patch("yt_dlp.YoutubeDL")
    def test_empty_playlist_raises(self, mock_ydl_cls: MagicMock) -> None:
        _mock_ytdl_context(mock_ydl_cls, [])
        with pytest.raises(PlaylistNotFoundError):
            list_playlist_videos("PLempty1234", max_results=10)

    def test_invalid_id_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot extract"):
            list_playlist_videos("bad")

    @patch("yt_dlp.YoutubeDL")
    def test_zero_max_results_raises(self, mock_ydl_cls: MagicMock) -> None:
        _mock_ytdl_context(mock_ydl_cls, [])
        with pytest.raises(ListingError, match="max_results must be >= 1"):
            list_playlist_videos("PLtest1234", max_results=0)


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
        with pytest.raises(ChannelListError):
            list_channel_videos("UCxxxxxxxxxxxxxxxxxxxxxx", max_results=10)

    def test_invalid_id_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot extract"):
            list_channel_videos("not-a-channel")

    @patch("yt_dlp.YoutubeDL")
    def test_zero_max_results_raises(self, mock_ydl_cls: MagicMock) -> None:
        _mock_ytdl_context(mock_ydl_cls, [])
        with pytest.raises(ListingError, match="max_results must be >= 1"):
            list_channel_videos("UCxxxxxxxxxxxxxxxxxxxxxx", max_results=0)


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
        with pytest.raises(ChannelListError, match="Failed to fetch"):
            list_channel_playlists("UCxxxxxxxxxxxxxxxxxxxxxx")

    @patch("youtube_tools_mcp.youtube.listing._youtube_api_get")
    @patch.dict("os.environ", {"YOUTUBE_API_KEY": "test-key"})
    def test_empty_items_returns_empty_list(self, mock_get: MagicMock) -> None:
        mock_get.return_value = {"items": []}
        result = list_channel_playlists("UCxxxxxxxxxxxxxxxxxxxxxx")
        assert result == []

    @patch("youtube_tools_mcp.youtube.listing._youtube_api_get")
    @patch.dict("os.environ", {"YOUTUBE_API_KEY": "test-key"})
    def test_paginates_when_max_results_greater_than_50(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = [
            {
                "items": [{"id": "PL1", "snippet": {"title": "P1"}, "contentDetails": {"itemCount": 1}}],
                "nextPageToken": "token1",
            },
            {
                "items": [{"id": "PL2", "snippet": {"title": "P2"}, "contentDetails": {"itemCount": 2}}],
                "nextPageToken": "token2",
            },
            {
                "items": [{"id": "PL3", "snippet": {"title": "P3"}, "contentDetails": {"itemCount": 3}}],
            },
        ]
        result = list_channel_playlists("UCxxxxxxxxxxxxxxxxxxxxxx", max_results=120)
        assert len(result) == 3
        assert mock_get.call_count == 3
        # second call should include pageToken
        args2, _ = mock_get.call_args_list[1]
        assert args2[1]["pageToken"] == "token1"
        # page sizes
        assert mock_get.call_args_list[0][0][1]["maxResults"] == "50"
        assert mock_get.call_args_list[1][0][1]["maxResults"] == "50"
        assert mock_get.call_args_list[2][0][1]["maxResults"] == "50"

    @patch("youtube_tools_mcp.youtube.listing._youtube_api_get")
    @patch.dict("os.environ", {"YOUTUBE_API_KEY": "test-key"})
    def test_paginates_partial_page(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = [
            {
                "items": [{"id": "PL1", "snippet": {"title": "P1"}, "contentDetails": {"itemCount": 1}}] * 50,
                "nextPageToken": "token1",
            },
            {
                "items": [{"id": "PL2", "snippet": {"title": "P2"}, "contentDetails": {"itemCount": 2}}],
            },
        ]
        result = list_channel_playlists("UCxxxxxxxxxxxxxxxxxxxxxx", max_results=51)
        assert len(result) == 51
        assert mock_get.call_count == 2
        assert mock_get.call_args_list[0][0][1]["maxResults"] == "50"
        assert mock_get.call_args_list[1][0][1]["maxResults"] == "1"

    @patch("youtube_tools_mcp.youtube.listing._youtube_api_get")
    @patch.dict("os.environ", {"YOUTUBE_API_KEY": "test-key"})
    def test_zero_max_results_raises(self, mock_get: MagicMock) -> None:
        with pytest.raises(ListingError, match="max_results must be >= 1"):
            list_channel_playlists("UCxxxxxxxxxxxxxxxxxxxxxx", max_results=0)

    @patch("youtube_tools_mcp.youtube.listing._youtube_api_get")
    @patch.dict("os.environ", {"YOUTUBE_API_KEY": "test-key"})
    def test_resolves_handle_to_channel_id(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = [
            {"items": [{"id": "UCresolvedxxxxxxxxxxxxxx"}]},
            {
                "items": [
                    {"id": "PL1", "snippet": {"title": "P1"}, "contentDetails": {"itemCount": 1}},
                ],
            },
        ]
        result = list_channel_playlists("@testhandle", max_results=1)
        assert len(result) == 1
        assert result[0]["playlist_id"] == "PL1"
