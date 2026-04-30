from __future__ import annotations

import base64
import tempfile
from pathlib import Path

from mcp.shared.exceptions import McpError
from mcp.types import INTERNAL_ERROR, CallToolResult, ErrorData, ImageContent

from youtube_tools_mcp.utils.url import extract_video_id
from youtube_tools_mcp.youtube.downloader import (
    DownloadError,
    FFmpegNotFoundError,
    extract_frame,
    extract_frames_batch,
    get_stream_url,
)

_MAX_FRAMES = 30


def _err(msg: str) -> McpError:
    return McpError(ErrorData(code=INTERNAL_ERROR, message=msg))


def _image_content(path: Path) -> ImageContent:
    data = base64.b64encode(path.read_bytes()).decode()
    return ImageContent(type="image", data=data, mimeType="image/jpeg")


def _cleanup_dir(path: Path) -> None:
    if path.exists():
        for f in path.iterdir():
            f.unlink(missing_ok=True)


def extract_video_frame(url_or_id: str, timestamp: float) -> CallToolResult:
    """Extract a single frame from a YouTube video at a specific timestamp.

    Gets a direct stream URL via yt-dlp, then uses ffmpeg to seek and extract.
    Uses progressive mp4 format so ffmpeg can seek without downloading.

    Args:
        url_or_id: YouTube video URL or 11-character video ID.
        timestamp: Timestamp in seconds (e.g., 195.0 for 3:15).

    Returns:
        MCP result containing a JPEG image of the frame.
    """
    try:
        video_id = extract_video_id(url_or_id)
    except ValueError as exc:
        raise _err(str(exc)) from exc

    try:
        stream_url, _ = get_stream_url(video_id)
    except DownloadError as exc:
        raise _err(f"Failed to get stream URL: {exc}") from exc

    tmp_dir = Path(tempfile.mkdtemp(prefix="yt_frame_"))
    try:
        out_path = tmp_dir / "frame.jpg"
        extract_frame(stream_url, timestamp, out_path)
        return CallToolResult(content=[_image_content(out_path)])
    except FFmpegNotFoundError as exc:
        raise _err(str(exc)) from exc
    except DownloadError as exc:
        raise _err(f"Frame extraction failed: {exc}") from exc
    finally:
        _cleanup_dir(tmp_dir)


def extract_video_frames(url_or_id: str, timestamps: list[float]) -> CallToolResult:
    """Extract multiple frames from a YouTube video at specified timestamps.

    Gets a single stream URL and extracts all frames from it.

    Args:
        url_or_id: YouTube video URL or 11-character video ID.
        timestamps: List of timestamps in seconds.

    Returns:
        MCP result containing JPEG images for each timestamp.
    """
    if len(timestamps) > _MAX_FRAMES:
        raise _err(f"Too many timestamps ({len(timestamps)}), maximum is {_MAX_FRAMES}")

    try:
        video_id = extract_video_id(url_or_id)
    except ValueError as exc:
        raise _err(str(exc)) from exc

    try:
        stream_url, _ = get_stream_url(video_id)
    except DownloadError as exc:
        raise _err(f"Failed to get stream URL: {exc}") from exc

    tmp_dir = Path(tempfile.mkdtemp(prefix="yt_frames_"))
    try:
        paths = extract_frames_batch(stream_url, timestamps, tmp_dir)
        return CallToolResult(content=[_image_content(p) for p in paths])
    except FFmpegNotFoundError as exc:
        raise _err(str(exc)) from exc
    except DownloadError as exc:
        raise _err(f"Frame extraction failed: {exc}") from exc
    finally:
        _cleanup_dir(tmp_dir)


def extract_frames_every(
    url_or_id: str,
    interval_sec: float = 30.0,
    max_frames: int = 10,
) -> CallToolResult:
    """Extract frames from a YouTube video at regular intervals.

    Gets stream URL and duration in a single yt-dlp call, then extracts frames.

    Args:
        url_or_id: YouTube video URL or 11-character video ID.
        interval_sec: Interval between frames in seconds. Defaults to 30.
        max_frames: Maximum number of frames to extract. Defaults to 10, max 30.

    Returns:
        MCP result containing JPEG images at regular intervals.
    """
    if max_frames > _MAX_FRAMES:
        raise _err(f"max_frames ({max_frames}) exceeds limit ({_MAX_FRAMES})")
    if interval_sec <= 0:
        raise _err("interval_sec must be positive")

    try:
        video_id = extract_video_id(url_or_id)
    except ValueError as exc:
        raise _err(str(exc)) from exc

    try:
        stream_url, duration = get_stream_url(video_id)
    except DownloadError as exc:
        raise _err(f"Failed to get video info: {exc}") from exc

    count = min(int(duration / interval_sec), max_frames)
    if count == 0:
        raise _err(f"Video duration ({duration:.1f}s) is shorter than interval ({interval_sec}s)")

    timestamps = [i * interval_sec for i in range(count)]

    tmp_dir = Path(tempfile.mkdtemp(prefix="yt_interval_"))
    try:
        paths = extract_frames_batch(stream_url, timestamps, tmp_dir)
        return CallToolResult(content=[_image_content(p) for p in paths])
    except FFmpegNotFoundError as exc:
        raise _err(str(exc)) from exc
    except DownloadError as exc:
        raise _err(f"Frame extraction failed: {exc}") from exc
    finally:
        _cleanup_dir(tmp_dir)
