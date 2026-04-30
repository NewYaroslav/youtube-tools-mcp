from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from youtube_tools_mcp.youtube.downloader import (
    FFmpegError,
    FFmpegNotFoundError,
    StreamUrlError,
    extract_frame,
    extract_frames_batch,
    get_stream_url,
    get_video_duration,
)


def _mock_ytdl_context(mock_ytdl_cls: MagicMock, info: dict) -> None:
    """Configure a mocked yt_dlp.YoutubeDL to return the given info dict."""
    mock_ydl = MagicMock()
    mock_ydl.extract_info.return_value = info
    mock_ytdl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ytdl_cls.return_value.__exit__ = MagicMock(return_value=False)


class TestGetStreamUrl:
    @patch("yt_dlp.YoutubeDL")
    def test_returns_direct_url_and_duration(self, mock_ytdl_cls: MagicMock) -> None:
        _mock_ytdl_context(mock_ytdl_cls, {"url": "https://stream.url/video.mp4", "duration": 210.5})

        stream_url, duration = get_stream_url("dQw4w9WgXcQ")
        assert stream_url == "https://stream.url/video.mp4"
        assert duration == 210.5

    @patch("yt_dlp.YoutubeDL")
    def test_raises_stream_url_error_when_no_url(self, mock_ytdl_cls: MagicMock) -> None:
        _mock_ytdl_context(mock_ytdl_cls, {"url": None, "duration": 120.0})

        with pytest.raises(StreamUrlError, match="No direct stream URL"):
            get_stream_url("dQw4w9WgXcQ")

    @patch("yt_dlp.YoutubeDL")
    def test_raises_stream_url_error_when_no_info(self, mock_ytdl_cls: MagicMock) -> None:
        _mock_ytdl_context(mock_ytdl_cls, None)

        with pytest.raises(StreamUrlError, match="no info"):
            get_stream_url("dQw4w9WgXcQ")

    @patch("yt_dlp.YoutubeDL")
    def test_raises_stream_url_error_when_no_duration(self, mock_ytdl_cls: MagicMock) -> None:
        _mock_ytdl_context(mock_ytdl_cls, {"url": "https://stream.url/video.mp4", "duration": None})

        with pytest.raises(StreamUrlError, match="Could not determine duration"):
            get_stream_url("dQw4w9WgXcQ")


class TestGetVideoDuration:
    @patch("yt_dlp.YoutubeDL")
    def test_returns_duration(self, mock_ytdl_cls: MagicMock) -> None:
        _mock_ytdl_context(mock_ytdl_cls, {"duration": 210.5})

        result = get_video_duration("dQw4w9WgXcQ")
        assert result == 210.5

    @patch("yt_dlp.YoutubeDL")
    def test_raises_when_no_info(self, mock_ytdl_cls: MagicMock) -> None:
        _mock_ytdl_context(mock_ytdl_cls, None)

        with pytest.raises(StreamUrlError):
            get_video_duration("dQw4w9WgXcQ")

    @patch("yt_dlp.YoutubeDL")
    def test_raises_when_no_duration(self, mock_ytdl_cls: MagicMock) -> None:
        _mock_ytdl_context(mock_ytdl_cls, {"duration": None})

        with pytest.raises(StreamUrlError, match="Could not determine duration"):
            get_video_duration("dQw4w9WgXcQ")


class TestExtractFrame:
    @patch("youtube_tools_mcp.youtube.downloader.shutil")
    @patch("youtube_tools_mcp.youtube.downloader.subprocess")
    def test_extracts_frame_successfully(self, mock_subprocess: MagicMock, mock_shutil: MagicMock) -> None:
        mock_shutil.which.return_value = "/usr/bin/ffmpeg"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.run.return_value = mock_result
        mock_subprocess.TimeoutExpired = subprocess.TimeoutExpired

        output_path = Path("/tmp/test_frame.jpg")
        with patch.object(Path, "exists", return_value=True):
            result = extract_frame("https://stream.url/video.mp4", 10.0, output_path)

        assert result == output_path
        mock_subprocess.run.assert_called_once()
        cmd = mock_subprocess.run.call_args[0][0]
        assert cmd[0] == "ffmpeg"
        assert cmd[2] == "10.000"

    @patch("youtube_tools_mcp.youtube.downloader.shutil")
    @patch("youtube_tools_mcp.youtube.downloader.subprocess")
    def test_raises_ffmpeg_error_on_nonzero_exit(self, mock_subprocess: MagicMock, mock_shutil: MagicMock) -> None:
        mock_shutil.which.return_value = "/usr/bin/ffmpeg"
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Error occurred"
        mock_subprocess.run.return_value = mock_result
        mock_subprocess.TimeoutExpired = subprocess.TimeoutExpired

        with pytest.raises(FFmpegError, match="ffmpeg failed"):
            extract_frame("https://stream.url/video.mp4", 10.0, Path("/tmp/frame.jpg"))

    @patch("youtube_tools_mcp.youtube.downloader.shutil")
    def test_raises_ffmpeg_error_on_timeout(self, mock_shutil: MagicMock) -> None:
        mock_shutil.which.return_value = "/usr/bin/ffmpeg"

        with patch("youtube_tools_mcp.youtube.downloader.subprocess") as mock_subprocess:
            mock_subprocess.TimeoutExpired = subprocess.TimeoutExpired
            mock_subprocess.run.side_effect = subprocess.TimeoutExpired(cmd="ffmpeg", timeout=30)

            with pytest.raises(FFmpegError, match="timed out"):
                extract_frame("https://stream.url/video.mp4", 10.0, Path("/tmp/frame.jpg"))

    @patch("youtube_tools_mcp.youtube.downloader.shutil")
    @patch("youtube_tools_mcp.youtube.downloader.subprocess")
    def test_raises_ffmpeg_error_when_output_missing(self, mock_subprocess: MagicMock, mock_shutil: MagicMock) -> None:
        mock_shutil.which.return_value = "/usr/bin/ffmpeg"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.run.return_value = mock_result
        mock_subprocess.TimeoutExpired = subprocess.TimeoutExpired

        with (
            patch.object(Path, "exists", return_value=False),
            pytest.raises(FFmpegError, match="did not produce output"),
        ):
            extract_frame("https://stream.url/video.mp4", 10.0, Path("/tmp/frame.jpg"))

    def test_raises_ffmpeg_not_found(self) -> None:
        with (
            patch("youtube_tools_mcp.youtube.downloader.shutil.which", return_value=None),
            pytest.raises(FFmpegNotFoundError),
        ):
            extract_frame("https://stream.url/video.mp4", 10.0, Path("/tmp/frame.jpg"))


class TestExtractFramesBatch:
    @patch("youtube_tools_mcp.youtube.downloader.extract_frame")
    @patch("youtube_tools_mcp.youtube.downloader.shutil")
    def test_extracts_multiple_frames(self, mock_shutil: MagicMock, mock_extract: MagicMock) -> None:
        mock_shutil.which.return_value = "/usr/bin/ffmpeg"
        mock_extract.side_effect = lambda url, ts, path: path

        output_dir = Path("/tmp/frames")
        timestamps = [0.0, 5.0, 10.0]

        with patch.object(Path, "mkdir"):
            result = extract_frames_batch("https://stream.url/video.mp4", timestamps, output_dir)

        assert len(result) == 3
        assert all(isinstance(p, Path) for p in result)

    @patch("youtube_tools_mcp.youtube.downloader.extract_frame")
    @patch("youtube_tools_mcp.youtube.downloader.shutil")
    def test_empty_timestamps(self, mock_shutil: MagicMock, mock_extract: MagicMock) -> None:
        mock_shutil.which.return_value = "/usr/bin/ffmpeg"
        output_dir = Path("/tmp/frames")

        with patch.object(Path, "mkdir"):
            result = extract_frames_batch("https://stream.url/video.mp4", [], output_dir)

        assert result == []
        mock_extract.assert_not_called()

    def test_raises_ffmpeg_not_found(self) -> None:
        with (
            patch("youtube_tools_mcp.youtube.downloader.shutil.which", return_value=None),
            pytest.raises(FFmpegNotFoundError),
        ):
            extract_frames_batch("https://stream.url/video.mp4", [0.0], Path("/tmp/frames"))
