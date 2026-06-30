from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from youtube_tools_mcp import server


class TestServerListingTools:
    @patch("youtube_tools_mcp.tools.listing.list_playlist_videos")
    def test_list_playlist_videos_returns_json_string(self, mock_list: MagicMock) -> None:
        mock_list.return_value = [{"video_id": "v1", "title": "Video"}]

        result = server.list_playlist_videos("PLtest1234", max_results=1)

        assert isinstance(result, str)
        assert json.loads(result) == [{"video_id": "v1", "title": "Video"}]

    @patch("youtube_tools_mcp.tools.listing.list_channel_videos")
    def test_list_channel_videos_returns_json_string(self, mock_list: MagicMock) -> None:
        mock_list.return_value = [{"video_id": "v1", "title": "Video"}]

        result = server.list_channel_videos("@handle", max_results=1)

        assert isinstance(result, str)
        assert json.loads(result) == [{"video_id": "v1", "title": "Video"}]

    @patch("youtube_tools_mcp.tools.listing.list_channel_playlists")
    def test_list_channel_playlists_returns_json_string(self, mock_list: MagicMock) -> None:
        mock_list.return_value = [{"playlist_id": "PL1", "title": "Playlist"}]

        result = server.list_channel_playlists("UCtest1234", max_results=1)

        assert isinstance(result, str)
        assert json.loads(result) == [{"playlist_id": "PL1", "title": "Playlist"}]
