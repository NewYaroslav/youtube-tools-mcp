from __future__ import annotations

import json

from mcp.shared.exceptions import McpError
from mcp.types import INTERNAL_ERROR, ErrorData

from youtube_tools_mcp.youtube.listing import (
    ChannelListError,
    ListingError,
    PlaylistNotFoundError,
    list_channel_playlists,
    list_channel_videos,
    list_playlist_videos,
)


def _err(msg: str) -> McpError:
    return McpError(ErrorData(code=INTERNAL_ERROR, message=msg))


def list_playlist_videos_tool(
    playlist_id_or_url: str,
    max_results: int = 50,
    proxy: str | None = None,
    cookies_from_browser: str | None = None,
    client: str = "web",
) -> str:
    try:
        videos = list_playlist_videos(
            playlist_id_or_url,
            max_results=max_results,
            proxy=proxy,
            cookies_from_browser=cookies_from_browser,
            client=client,
        )
        return json.dumps(videos, ensure_ascii=False, indent=2)
    except (PlaylistNotFoundError, ListingError, ValueError) as exc:
        raise _err(str(exc)) from exc


def list_channel_videos_tool(
    channel_id_or_url: str,
    max_results: int = 50,
    proxy: str | None = None,
    cookies_from_browser: str | None = None,
    client: str = "web",
) -> str:
    try:
        videos = list_channel_videos(
            channel_id_or_url,
            max_results=max_results,
            proxy=proxy,
            cookies_from_browser=cookies_from_browser,
            client=client,
        )
        return json.dumps(videos, ensure_ascii=False, indent=2)
    except (ChannelListError, ListingError, ValueError) as exc:
        raise _err(str(exc)) from exc


def list_channel_playlists_tool(
    channel_id_or_url: str,
    max_results: int = 50,
    proxy: str | None = None,
) -> str:
    try:
        playlists = list_channel_playlists(
            channel_id_or_url,
            max_results=max_results,
            proxy=proxy,
        )
        return json.dumps(playlists, ensure_ascii=False, indent=2)
    except (ChannelListError, ListingError, ValueError) as exc:
        raise _err(str(exc)) from exc
