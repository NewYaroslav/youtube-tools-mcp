from __future__ import annotations

from mcp.shared.exceptions import McpError
from mcp.types import INTERNAL_ERROR, ErrorData

from youtube_tools_mcp.utils.url import extract_video_id
from youtube_tools_mcp.youtube.metadata import MetadataError, fetch_video_metadata, metadata_to_json


def _err(msg: str) -> McpError:
    return McpError(ErrorData(code=INTERNAL_ERROR, message=msg))


def get_youtube_video_metadata(
    url_or_id: str,
    include_channel_description: bool = True,
) -> str:
    """Fetch YouTube video metadata and channel information.

    Args:
        url_or_id: YouTube video URL or 11-character video ID.
        include_channel_description: Try to include channel description when available.

    Returns:
        Pretty JSON with video description, channel URL, and optional channel description.
    """
    try:
        video_id = extract_video_id(url_or_id)
    except ValueError as exc:
        raise _err(str(exc)) from exc

    try:
        metadata = fetch_video_metadata(
            video_id,
            include_channel_description=include_channel_description,
        )
    except MetadataError as exc:
        raise _err(f"Failed to fetch video metadata: {exc}") from exc

    return metadata_to_json(metadata)
