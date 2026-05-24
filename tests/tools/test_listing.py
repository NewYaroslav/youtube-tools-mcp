from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from mcp.shared.exceptions import McpError

from youtube_tools_mcp.tools.listing import (
    list_channel_playlists_tool,
    list_channel_videos_tool,
    list_playlist_videos_tool,
)


class TestListPlaylistVideosTool:
    @patch("youtube_tools_mcp.tools.listing.list_playlist_videos")
    def test_returns_json(self, mock_list: MagicMock) -> None:
        mock_list.return_value = [{"video_id": "v1", "title": "Vid"}]
        result = list_playlist_videos_tool("PLtest1234", max_results=1)
        assert '"video_id": "v1"' in result

    @patch("youtube_tools_mcp.tools.listing.list_playlist_videos")
    def test_invalid_url_raises_mcp_error(self, mock_list: MagicMock) -> None:
        mock_list.side_effect = ValueError("Cannot extract")
        with pytest.raises(McpError, match="Cannot extract"):
            list_playlist_videos_tool("bad")

    @patch("youtube_tools_mcp.tools.listing.list_playlist_videos")
    def test_passes_parameters(self, mock_list: MagicMock) -> None:
        mock_list.return_value = []
        list_playlist_videos_tool(
            "PLtest1234",
            max_results=5,
            proxy="http://p:8080",
            cookies_from_browser="chrome",
            client="android",
        )
        mock_list.assert_called_once_with(
            "PLtest1234",
            max_results=5,
            proxy="http://p:8080",
            cookies_from_browser="chrome",
            client="android",
        )


class TestListChannelVideosTool:
    @patch("youtube_tools_mcp.tools.listing.list_channel_videos")
    def test_returns_json(self, mock_list: MagicMock) -> None:
        mock_list.return_value = [{"video_id": "v1"}]
        result = list_channel_videos_tool("@handle", max_results=1)
        assert '"video_id": "v1"' in result

    @patch("youtube_tools_mcp.tools.listing.list_channel_videos")
    def test_passes_parameters(self, mock_list: MagicMock) -> None:
        mock_list.return_value = []
        list_channel_videos_tool(
            "@handle",
            max_results=3,
            proxy="http://p:8080",
            cookies_from_browser="firefox",
            client="ios",
        )
        mock_list.assert_called_once_with(
            "@handle",
            max_results=3,
            proxy="http://p:8080",
            cookies_from_browser="firefox",
            client="ios",
        )


class TestListChannelPlaylistsTool:
    @patch("youtube_tools_mcp.tools.listing.list_channel_playlists")
    def test_returns_json(self, mock_list: MagicMock) -> None:
        mock_list.return_value = [{"playlist_id": "PL1"}]
        result = list_channel_playlists_tool("UCid", max_results=2)
        assert '"playlist_id": "PL1"' in result

    @patch("youtube_tools_mcp.tools.listing.list_channel_playlists")
    def test_passes_proxy(self, mock_list: MagicMock) -> None:
        mock_list.return_value = []
        list_channel_playlists_tool("UCid", max_results=2, proxy="http://p:8080")
        mock_list.assert_called_once_with("UCid", max_results=2, proxy="http://p:8080")
