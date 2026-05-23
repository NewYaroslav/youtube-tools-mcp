from __future__ import annotations

import os
from typing import Any

from youtube_tools_mcp.utils.proxy import get_proxy_url
from youtube_tools_mcp.utils.url import (
    extract_channel_id,
    extract_playlist_id,
    normalize_url,
    resolve_channel_handle,
)
from youtube_tools_mcp.youtube.downloader import _apply_client_options
from youtube_tools_mcp.youtube.metadata import _youtube_api_get


class ListingError(Exception):
    """Base exception for listing operations."""


class PlaylistNotFoundError(ListingError):
    """Playlist not found or empty."""


class ChannelNotFoundError(ListingError):
    """Channel not found or has no videos."""


def _extract_entries_ytdlp(
    url: str,
    max_results: int,
    proxy: str | None = None,
    cookies_from_browser: str | None = None,
    client: str = "web",
) -> list[dict[str, Any]]:
    import yt_dlp

    ydl_opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "playlistend": max_results,
        "skip_download": True,
    }
    resolved = get_proxy_url(proxy)
    if resolved:
        ydl_opts["proxy"] = resolved
    if cookies_from_browser:
        ydl_opts["cookiesfrombrowser"] = [cookies_from_browser]
    _apply_client_options(ydl_opts, client)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        raise ListingError(f"yt-dlp failed to extract entries from {url}: {exc}") from exc

    if not isinstance(info, dict):
        raise ListingError(f"yt-dlp returned no info for {url}")

    entries = info.get("entries")
    if not isinstance(entries, list):
        return []

    return entries


def _entry_to_video_dict(entry: dict[str, Any], position: int) -> dict[str, Any]:
    vid = entry.get("id")
    return {
        "video_id": vid,
        "title": entry.get("title"),
        "url": normalize_url(vid) if vid else None,
        "duration": entry.get("duration"),
        "position": position,
    }


def list_playlist_videos(
    playlist_id_or_url: str,
    max_results: int = 50,
    proxy: str | None = None,
    cookies_from_browser: str | None = None,
    client: str = "web",
) -> list[dict[str, Any]]:
    """List videos in a YouTube playlist using yt-dlp.

    Args:
        playlist_id_or_url: Playlist URL or raw playlist ID.
        max_results: Maximum number of videos to return.
        proxy: Optional proxy URL override.
        cookies_from_browser: Browser to extract cookies from for YouTube auth.
        client: yt-dlp client profile to spoof.
    """
    playlist_id = extract_playlist_id(playlist_id_or_url)
    url = f"https://www.youtube.com/playlist?list={playlist_id}"
    entries = _extract_entries_ytdlp(url, max_results, proxy, cookies_from_browser, client)

    if not entries:
        raise PlaylistNotFoundError(f"Playlist {playlist_id} not found or is empty")

    return [_entry_to_video_dict(e, i + 1) for i, e in enumerate(entries)]


def list_channel_videos(
    channel_id_or_url: str,
    max_results: int = 50,
    proxy: str | None = None,
    cookies_from_browser: str | None = None,
    client: str = "web",
) -> list[dict[str, Any]]:
    """List upload videos from a YouTube channel using yt-dlp.

    Args:
        channel_id_or_url: Channel URL, handle (@name), or raw channel ID (UC...).
        max_results: Maximum number of videos to return.
        proxy: Optional proxy URL override.
        cookies_from_browser: Browser to extract cookies from for YouTube auth.
        client: yt-dlp client profile to spoof.
    """
    handle = resolve_channel_handle(channel_id_or_url)
    if handle:
        url = f"https://www.youtube.com/@{handle}/videos"
    else:
        channel_id = extract_channel_id(channel_id_or_url)
        url = f"https://www.youtube.com/channel/{channel_id}/videos"

    entries = _extract_entries_ytdlp(url, max_results, proxy, cookies_from_browser, client)

    if not entries:
        raise ChannelNotFoundError(f"Channel {channel_id_or_url} not found or has no videos")

    return [_entry_to_video_dict(e, i + 1) for i, e in enumerate(entries)]


def list_channel_playlists(
    channel_id_or_url: str,
    max_results: int = 50,
    proxy: str | None = None,
) -> list[dict[str, Any]]:
    """List playlists owned by a YouTube channel using the YouTube Data API.

    Requires YOUTUBE_API_KEY environment variable.

    Args:
        channel_id_or_url: Channel URL or raw channel ID (UC...).
        max_results: Maximum number of playlists to return.
        proxy: Optional proxy URL override.
    """
    try:
        channel_id = extract_channel_id(channel_id_or_url)
    except ValueError:
        raise ChannelNotFoundError(
            f"Cannot extract channel ID from: {channel_id_or_url!r}"
        ) from None

    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        raise ListingError("list_channel_playlists requires YOUTUBE_API_KEY. Set it as an environment variable.")

    try:
        data = _youtube_api_get(
            "playlists",
            {
                "part": "snippet,contentDetails",
                "channelId": channel_id,
                "maxResults": str(max_results),
                "key": api_key,
            },
            proxy=proxy,
        )
    except Exception as exc:
        raise ChannelNotFoundError(f"Failed to fetch playlists for channel {channel_id}: {exc}") from exc

    items = data.get("items")
    if not isinstance(items, list):
        return []

    result: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        snippet = item.get("snippet")
        content_details = item.get("contentDetails")
        if not isinstance(snippet, dict):
            continue
        result.append(
            {
                "playlist_id": item.get("id"),
                "title": snippet.get("title"),
                "description": snippet.get("description"),
                "video_count": (content_details.get("itemCount") if isinstance(content_details, dict) else None),
            }
        )

    return result
