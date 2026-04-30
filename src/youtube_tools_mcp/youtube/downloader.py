from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class DownloadError(Exception):
    """Base exception for download operations."""


class FFmpegError(DownloadError):
    """ffmpeg subprocess failed."""


class FFmpegNotFoundError(FFmpegError):
    """ffmpeg is not installed or not on PATH."""


class StreamUrlError(DownloadError):
    """Could not obtain a direct stream URL from yt-dlp."""


class VideoDownloadError(DownloadError):
    """Video download failed."""


def _check_ffmpeg() -> None:
    """Raise FFmpegNotFoundError if ffmpeg is not available."""
    if shutil.which("ffmpeg") is not None:
        return

    msg = (
        "ffmpeg is required for this operation but was not found on PATH. "
        "Install from https://ffmpeg.org/download.html "
        "(Windows: winget install ffmpeg, choco install ffmpeg, or scoop install ffmpeg)"
    )
    raise FFmpegNotFoundError(msg)


def get_stream_url(video_id: str) -> tuple[str, float]:
    """Get a direct video stream URL and duration via yt-dlp without downloading.

    Uses itag 18 (360p progressive mp4) which ffmpeg can seek efficiently
    without downloading. DASH formats cause ffmpeg timeouts on long videos.
    Returns (stream_url, duration_seconds).
    """
    import yt_dlp

    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "format": "18",
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if info is None:
        raise StreamUrlError(f"yt-dlp returned no info for video {video_id}")

    direct_url = info.get("url")
    if not direct_url:
        raise StreamUrlError(f"No direct stream URL found for video {video_id}")

    duration = info.get("duration")
    if duration is None:
        raise StreamUrlError(f"Could not determine duration for video {video_id}")

    return direct_url, float(duration)


def get_video_duration(video_id: str) -> float:
    """Get video duration in seconds via yt-dlp without downloading."""
    import yt_dlp

    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if info is None:
        raise StreamUrlError(f"yt-dlp returned no info for video {video_id}")

    duration = info.get("duration")
    if duration is None:
        raise StreamUrlError(f"Could not determine duration for video {video_id}")

    return float(duration)


def extract_frame(stream_url: str, timestamp: float, output_path: Path) -> Path:
    """Extract a single frame from a video stream at the given timestamp.

    Uses ffmpeg with input seeking (-ss before -i) for fast random access.
    Requires a direct (progressive) stream URL, not a DASH manifest.
    """
    _check_ffmpeg()

    cmd = [
        "ffmpeg",
        "-ss",
        f"{timestamp:.3f}",
        "-i",
        stream_url,
        "-frames:v",
        "1",
        "-q:v",
        "5",
        "-y",
        str(output_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired as exc:
        raise FFmpegError(f"ffmpeg timed out after 30s at timestamp {timestamp}") from exc

    if result.returncode != 0:
        raise FFmpegError(f"ffmpeg failed (exit {result.returncode}): {result.stderr.strip()}")

    if not output_path.exists():
        raise FFmpegError(f"ffmpeg did not produce output file: {output_path}")

    return output_path


def extract_frames_batch(
    stream_url: str,
    timestamps: list[float],
    output_dir: Path,
) -> list[Path]:
    """Extract frames at multiple timestamps from a video stream.

    Returns list of paths to JPEG files in order of timestamps.
    Stops on first error to avoid long-running cascading failures.
    """
    _check_ffmpeg()
    output_dir.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    for i, ts in enumerate(timestamps):
        out_path = output_dir / f"frame_{i:04d}.jpg"
        extract_frame(stream_url, ts, out_path)
        paths.append(out_path)

    return paths


_VIDEO_QUALITY_MAP: dict[str, str] = {
    "best": "bestvideo+bestaudio/best",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
    "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]/best",
    "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]/best",
}

_AUDIO_FORMAT_MAP: dict[str, str] = {
    "mp3": "mp3",
    "m4a": "m4a",
    "opus": "opus",
    "wav": "wav",
}


def download_video(
    video_id: str,
    output_dir: Path,
    quality: str = "720p",
) -> Path:
    """Download a YouTube video using yt-dlp.

    Args:
        video_id: YouTube video ID.
        output_dir: Directory to save the video file.
        quality: Quality preset: "best", "720p", "480p", "360p".

    Returns:
        Path to the downloaded video file.
    """
    import yt_dlp

    if quality not in _VIDEO_QUALITY_MAP:
        raise VideoDownloadError(f"Unknown quality {quality!r}. Choose from: {', '.join(_VIDEO_QUALITY_MAP)}")

    format_spec = _VIDEO_QUALITY_MAP[quality]
    url = f"https://www.youtube.com/watch?v={video_id}"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_template = str(output_dir / "%(title)s.%(ext)s")

    ydl_opts = {
        "format": format_spec,
        "outtmpl": out_template,
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info is None:
                raise VideoDownloadError(f"yt-dlp returned no info for video {video_id}")
            filename = ydl.prepare_filename(info)
            # merge_output_format changes ext to mp4
            p = Path(filename)
            if p.suffix != ".mp4":
                p = p.with_suffix(".mp4")
            if not p.exists():
                p = Path(filename)
            if not p.exists():
                candidates = list(output_dir.glob("*.mp4"))
                if candidates:
                    p = max(candidates, key=lambda f: f.stat().st_mtime)
                else:
                    raise VideoDownloadError(f"Downloaded file not found in {output_dir}")
            return p
    except VideoDownloadError:
        raise
    except Exception as exc:
        raise VideoDownloadError(f"Failed to download video: {exc}") from exc


def download_audio(
    video_id: str,
    output_dir: Path,
    audio_format: str = "mp3",
) -> Path:
    """Download audio only from a YouTube video using yt-dlp + ffmpeg.

    Args:
        video_id: YouTube video ID.
        output_dir: Directory to save the audio file.
        audio_format: Output audio format: "mp3", "m4a", "opus", "wav".

    Returns:
        Path to the downloaded audio file.
    """
    _check_ffmpeg()

    import yt_dlp

    if audio_format not in _AUDIO_FORMAT_MAP:
        raise VideoDownloadError(f"Unknown audio format {audio_format!r}. Choose from: {', '.join(_AUDIO_FORMAT_MAP)}")

    url = f"https://www.youtube.com/watch?v={video_id}"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_template = str(output_dir / "%(title)s.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": out_template,
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudioPP",
                "preferredcodec": _AUDIO_FORMAT_MAP[audio_format],
            }
        ],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info is None:
                raise VideoDownloadError(f"yt-dlp returned no info for video {video_id}")
            filename = ydl.prepare_filename(info)
            p = Path(filename).with_suffix(f".{audio_format}")
            if not p.exists():
                candidates = list(output_dir.glob(f"*.{audio_format}"))
                if candidates:
                    p = max(candidates, key=lambda f: f.stat().st_mtime)
                else:
                    raise VideoDownloadError(f"Downloaded audio file not found in {output_dir}")
            return p
    except VideoDownloadError:
        raise
    except Exception as exc:
        raise VideoDownloadError(f"Failed to download audio: {exc}") from exc
