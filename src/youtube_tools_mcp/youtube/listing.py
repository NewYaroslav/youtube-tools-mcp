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
from youtube_tools_mcp.youtube.downloader import _apply_client_options, _base_ytdlp_opts
from youtube_tools_mcp.youtube.metadata import _first_item, _youtube_api_get


class ListingError(Exception):
    """Base exception for listing operations."""


class PlaylistNotFoundError(ListingError):
    """Playlist not found or empty."""


class ChannelListError(ListingError):
    """Channel-related listing failed: not found, has no content, or API error."""


def _clamp_max_results(value: int, *, max_allowed: int) -> int:
    if value < 1:
        raise ListingError(f"max_results must be >= 1, got {value}")
    return min(value, max_allowed)


def _resolve_channel_id_for_api(
    channel_id_or_url: str,
    api_key: str,
    proxy: str | None = None,
) -> str:
    try:
        return extract_channel_id(channel_id_or_url)
    except ValueError:
        pass

    handle = resolve_channel_handle(channel_id_or_url)
    if handle is None:
        raise ChannelListError(f"Cannot extract channel ID or handle from: {channel_id_or_url!r}") from None

    data = _youtube_api_get(
        "channels",
        {
            "part": "id",
            "forHandle": handle,
            "key": api_key,
        },
        proxy=proxy,
    )
    item = _first_item(data)
    if item is None:
        raise ChannelListError(f"Handle @{handle} not found")
    cid = item.get("id")
    if not isinstance(cid, str):
        raise ChannelListError(f"Handle @{handle} returned no channel ID") from None
    return cid


def _extract_entries_ytdlp(
    url: str,
    max_results: int,
    proxy: str | None = None,
    cookies_from_browser: str | None = None,
    client: str = "web",
) -> list[dict[str, Any]]:
    import yt_dlp

    ydl_opts: dict[str, Any] = _base_ytdlp_opts(
        extract_flat=True,
        playlistend=max_results,
        skip_download=True,
    )
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
    max_results = _clamp_max_results(max_results, max_allowed=500)
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
    max_results = _clamp_max_results(max_results, max_allowed=500)
    handle = resolve_channel_handle(channel_id_or_url)
    if handle:
        url = f"https://www.youtube.com/@{handle}/videos"
    else:
        channel_id = extract_channel_id(channel_id_or_url)
        url = f"https://www.youtube.com/channel/{channel_id}/videos"

    entries = _extract_entries_ytdlp(url, max_results, proxy, cookies_from_browser, client)

    if not entries:
        raise ChannelListError(f"Channel {channel_id_or_url} not found or has no videos")

    return [_entry_to_video_dict(e, i + 1) for i, e in enumerate(entries)]


def list_channel_playlists(
    channel_id_or_url: str,
    max_results: int = 50,
    proxy: str | None = None,
) -> list[dict[str, Any]]:
    """List playlists owned by a YouTube channel using the YouTube Data API.

    Requires YOUTUBE_API_KEY environment variable.

    Args:
        channel_id_or_url: Channel URL, handle (@name), or raw channel ID (UC...).
        max_results: Maximum number of playlists to return (1..500). Defaults to 50.
        proxy: Optional proxy URL override.
    """
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        raise ListingError("list_channel_playlists requires YOUTUBE_API_KEY. Set it as an environment variable.")

    channel_id = _resolve_channel_id_for_api(channel_id_or_url, api_key, proxy=proxy)
    max_results = _clamp_max_results(max_results, max_allowed=500)

    all_items: list[dict[str, Any]] = []
    page_token: str | None = None
    remaining = max_results

    try:
        while remaining > 0:
            page_size = min(50, remaining)
            params: dict[str, str] = {
                "part": "snippet,contentDetails",
                "channelId": channel_id,
                "maxResults": str(page_size),
                "key": api_key,
            }
            if page_token:
                params["pageToken"] = page_token

            data = _youtube_api_get("playlists", params, proxy=proxy)
            items = data.get("items")
            if not isinstance(items, list):
                break

            all_items.extend(items)
            remaining -= len(items)

            page_token = data.get("nextPageToken")
            if not page_token or not items:
                break
    except Exception as exc:
        raise ChannelListError(f"Failed to fetch playlists for channel {channel_id}: {exc}") from exc

    result: list[dict[str, Any]] = []
    for item in all_items:
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
