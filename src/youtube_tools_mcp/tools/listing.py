from __future__ import annotations

import json

from youtube_tools_mcp.youtube.listing import (
    ChannelNotFoundError,
    ListingError,
    PlaylistNotFoundError,
    list_channel_playlists,
    list_channel_videos,
    list_playlist_videos,
)


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
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


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
    except (ChannelNotFoundError, ListingError, ValueError) as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


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
    except (ChannelNotFoundError, ListingError, ValueError) as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)
