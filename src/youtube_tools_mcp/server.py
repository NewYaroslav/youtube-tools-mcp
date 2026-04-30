from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult

from youtube_tools_mcp.tools.cleanup import clean_transcript as _clean_transcript
from youtube_tools_mcp.tools.download import (
    download_audio_file as _download_audio_file,
)
from youtube_tools_mcp.tools.download import (
    download_video_file as _download_video_file,
)
from youtube_tools_mcp.tools.frames import (
    extract_frames_every as _extract_frames_every,
)
from youtube_tools_mcp.tools.frames import (
    extract_video_frame as _extract_video_frame,
)
from youtube_tools_mcp.tools.frames import (
    extract_video_frames as _extract_video_frames,
)
from youtube_tools_mcp.tools.transcript import get_youtube_transcript as _get_youtube_transcript

mcp = FastMCP(
    "youtube-tools-mcp",
    instructions=(
        "MCP server for YouTube transcript extraction, text cleanup, frame extraction, and video/audio download."
    ),
)


@mcp.tool()
def get_youtube_transcript(url_or_id: str, languages: list[str] | None = None) -> str:
    """Extract transcript/subtitles from a YouTube video.

    Provide a YouTube URL or video ID and optional language preference list.
    Returns timestamped transcript text with format [MM:SS] text per line.

    Args:
        url_or_id: YouTube video URL or 11-character video ID.
        languages: Preferred language codes in priority order. Defaults to ["ru", "en"].
    """
    return _get_youtube_transcript(url_or_id, languages)


@mcp.tool()
def clean_transcript(
    text: str,
    *,
    remove_fillers: bool = True,
    fix_casing: bool = True,
    merge_lines: bool = True,
    remove_duplicates: bool = True,
) -> str:
    """Clean and format auto-generated transcript text.

    Removes filler words, fixes capitalization, merges broken subtitle lines,
    and removes duplicate lines.

    Args:
        text: Raw transcript text (with or without timestamps).
        remove_fillers: Remove filler words (hmm, um, uh, etc.).
        fix_casing: Capitalize first letter of each sentence.
        merge_lines: Merge lines broken mid-sentence.
        remove_duplicates: Remove consecutive duplicate text lines.
    """
    return _clean_transcript(
        text,
        remove_fillers=remove_fillers,
        fix_casing=fix_casing,
        merge_lines=merge_lines,
        remove_duplicates=remove_duplicates,
    )


@mcp.tool()
def extract_video_frame(url_or_id: str, timestamp: float) -> CallToolResult:
    """Extract a single frame from a YouTube video at a specific timestamp.

    Requires ffmpeg to be installed on the system.

    Args:
        url_or_id: YouTube video URL or 11-character video ID.
        timestamp: Timestamp in seconds (e.g., 195.0 for 3:15).
    """
    return _extract_video_frame(url_or_id, timestamp)


@mcp.tool()
def extract_video_frames(url_or_id: str, timestamps: list[float]) -> CallToolResult:
    """Extract multiple frames from a YouTube video at specified timestamps.

    Requires ffmpeg to be installed on the system. Maximum 30 frames per call.

    Args:
        url_or_id: YouTube video URL or 11-character video ID.
        timestamps: List of timestamps in seconds.
    """
    return _extract_video_frames(url_or_id, timestamps)


@mcp.tool()
def extract_frames_every(
    url_or_id: str,
    interval_sec: float = 30.0,
    max_frames: int = 10,
) -> CallToolResult:
    """Extract frames from a YouTube video at regular intervals.

    Requires ffmpeg to be installed on the system. Maximum 30 frames per call.

    Args:
        url_or_id: YouTube video URL or 11-character video ID.
        interval_sec: Interval between frames in seconds. Defaults to 30.
        max_frames: Maximum number of frames to extract. Defaults to 10, max 30.
    """
    return _extract_frames_every(url_or_id, interval_sec, max_frames)


@mcp.tool()
def download_video(url_or_id: str, output_dir: str = ".", quality: str = "720p") -> str:
    """Download a YouTube video to a local file.

    Args:
        url_or_id: YouTube video URL or 11-character video ID.
        output_dir: Directory to save the video file. Defaults to current directory.
        quality: Quality preset: "best", "720p", "480p", "360p". Defaults to "720p".
    """
    return _download_video_file(url_or_id, output_dir, quality)


@mcp.tool()
def download_audio(url_or_id: str, output_dir: str = ".", audio_format: str = "mp3") -> str:
    """Download audio only from a YouTube video to a local file.

    Requires ffmpeg to be installed on the system.

    Args:
        url_or_id: YouTube video URL or 11-character video ID.
        output_dir: Directory to save the audio file. Defaults to current directory.
        audio_format: Output audio format: "mp3", "m4a", "opus", "wav". Defaults to "mp3".
    """
    return _download_audio_file(url_or_id, output_dir, audio_format)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
