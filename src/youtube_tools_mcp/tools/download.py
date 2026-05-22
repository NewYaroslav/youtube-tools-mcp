from __future__ import annotations

from pathlib import Path

from mcp.shared.exceptions import McpError
from mcp.types import INTERNAL_ERROR, ErrorData

from youtube_tools_mcp.utils.url import extract_video_id
from youtube_tools_mcp.youtube.downloader import (
    DownloadError,
    FFmpegNotFoundError,
    VideoDownloadError,
    download_audio,
    download_video,
)


def _err(msg: str) -> McpError:
    return McpError(ErrorData(code=INTERNAL_ERROR, message=msg))


def download_video_file(
    url_or_id: str,
    output_dir: str = ".",
    quality: str = "720p",
    proxy: str | None = None,
) -> str:
    """Download a YouTube video to a local file.

    Args:
        url_or_id: YouTube video URL or 11-character video ID.
        output_dir: Directory to save the video file. Defaults to current directory.
        quality: Quality preset: "best", "720p", "480p", "360p". Defaults to "720p".
        proxy: Optional proxy URL (e.g. http://user:pass@host:port).

    Returns:
        Absolute path to the downloaded video file.
    """
    try:
        video_id = extract_video_id(url_or_id)
    except ValueError as exc:
        raise _err(str(exc)) from exc

    out = Path(output_dir).resolve()

    try:
        path = download_video(video_id, out, quality, proxy=proxy)
        return str(path)
    except FFmpegNotFoundError as exc:
        raise _err(str(exc)) from exc
    except VideoDownloadError as exc:
        raise _err(
            f"Download failed: {exc}. "
            "If YouTube returned a bot-check, captcha, sign-in, or anti-abuse message, "
            "retry the same tool call with the proxy parameter, or with a different proxy if proxy was already used."
        ) from exc
    except DownloadError as exc:
        raise _err(
            f"Download failed: {exc}. "
            "If YouTube returned a bot-check, captcha, sign-in, or anti-abuse message, "
            "retry the same tool call with the proxy parameter, or with a different proxy if proxy was already used."
        ) from exc


def download_audio_file(
    url_or_id: str,
    output_dir: str = ".",
    audio_format: str = "mp3",
    proxy: str | None = None,
) -> str:
    """Download audio only from a YouTube video to a local file.

    Requires ffmpeg to be installed on the system.

    Args:
        url_or_id: YouTube video URL or 11-character video ID.
        output_dir: Directory to save the audio file. Defaults to current directory.
        audio_format: Output audio format: "mp3", "m4a", "opus", "wav". Defaults to "mp3".
        proxy: Optional proxy URL (e.g. http://user:pass@host:port).

    Returns:
        Absolute path to the downloaded audio file.
    """
    try:
        video_id = extract_video_id(url_or_id)
    except ValueError as exc:
        raise _err(str(exc)) from exc

    out = Path(output_dir).resolve()

    try:
        path = download_audio(video_id, out, audio_format, proxy=proxy)
        return str(path)
    except FFmpegNotFoundError as exc:
        raise _err(str(exc)) from exc
    except VideoDownloadError as exc:
        raise _err(
            f"Download failed: {exc}. "
            "If YouTube returned a bot-check, captcha, sign-in, or anti-abuse message, "
            "retry the same tool call with the proxy parameter, or with a different proxy if proxy was already used."
        ) from exc
    except DownloadError as exc:
        raise _err(
            f"Download failed: {exc}. "
            "If YouTube returned a bot-check, captcha, sign-in, or anti-abuse message, "
            "retry the same tool call with the proxy parameter, or with a different proxy if proxy was already used."
        ) from exc
