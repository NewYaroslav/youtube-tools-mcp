from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from youtube_tools_mcp.youtube.downloader import (
    DownloadError,
    FFmpegError,
    FFmpegInputError,
    FFmpegNotFoundError,
    FFmpegOutputError,
    StreamUrlError,
    _base_ytdlp_opts,
    download_audio,
    download_frame_source,
    download_video,
    extract_frame,
    extract_frames_batch,
    get_media_duration,
    get_stream_url,
    get_video_duration,
)


def _mock_ytdl_context(mock_ytdl_cls: MagicMock, info: dict) -> None:
    """Configure a mocked yt_dlp.YoutubeDL to return the given info dict."""
    mock_ydl = MagicMock()
    mock_ydl.extract_info.return_value = info
    mock_ytdl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ytdl_cls.return_value.__exit__ = MagicMock(return_value=False)


class TestBaseYtdlpOpts:
    def test_disables_progress_by_default(self) -> None:
        opts = _base_ytdlp_opts(skip_download=True)

        assert opts == {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "skip_download": True,
        }


class TestGetStreamUrl:
    @patch("yt_dlp.YoutubeDL")
    def test_returns_direct_url_and_duration(self, mock_ydl_cls: MagicMock) -> None:
        _mock_ytdl_context(mock_ydl_cls, {"url": "https://stream.url/video.mp4", "duration": 210.5})

        stream_url, duration = get_stream_url("dQw4w9WgXcQ")
        assert stream_url == "https://stream.url/video.mp4"
        assert duration == 210.5

    @patch("yt_dlp.YoutubeDL")
    def test_uses_cookies_from_browser_when_set(self, mock_ydl_cls: MagicMock) -> None:
        _mock_ytdl_context(mock_ydl_cls, {"url": "https://stream.url/video.mp4", "duration": 210.5})

        get_stream_url("dQw4w9WgXcQ", cookies_from_browser="chrome")

        opts = mock_ydl_cls.call_args[0][0]
        assert opts["cookiesfrombrowser"] == ["chrome"]

    @patch("yt_dlp.YoutubeDL")
    def test_uses_android_client_when_set(self, mock_ydl_cls: MagicMock) -> None:
        _mock_ytdl_context(mock_ydl_cls, {"url": "https://stream.url/video.mp4", "duration": 210.5})

        get_stream_url("dQw4w9WgXcQ", client="android")

        opts = mock_ydl_cls.call_args[0][0]
        assert "Android" in opts["user_agent"]
        assert opts["extractor_args"]["youtube"]["player_client"] == "android"

    @patch("yt_dlp.YoutubeDL")
    def test_uses_ytdlp_socket_timeout_when_set(self, mock_ydl_cls: MagicMock) -> None:
        _mock_ytdl_context(mock_ydl_cls, {"url": "https://stream.url/video.mp4", "duration": 210.5})

        get_stream_url("dQw4w9WgXcQ", ytdlp_socket_timeout=11.0)

        opts = mock_ydl_cls.call_args[0][0]
        assert opts["socket_timeout"] == 11.0

    @pytest.mark.parametrize(
        "value",
        ["nan", "inf", "-inf", float("nan"), float("inf"), float("-inf"), 0, -1],
    )
    def test_rejects_invalid_ytdlp_socket_timeout(self, value: object) -> None:
        with pytest.raises(DownloadError, match="ytdlp_socket_timeout must be a positive finite number"):
            get_stream_url("dQw4w9WgXcQ", ytdlp_socket_timeout=value)

    @pytest.mark.parametrize("value", ["abc", "nan", "inf", "-inf", "0", "-1"])
    def test_rejects_invalid_ytdlp_socket_timeout_from_environment(self, value: str) -> None:
        with (
            patch.dict("os.environ", {"YOUTUBE_TOOLS_YTDLP_SOCKET_TIMEOUT": value}, clear=True),
            pytest.raises(
                DownloadError,
                match="YOUTUBE_TOOLS_YTDLP_SOCKET_TIMEOUT must be a positive finite number",
            ),
        ):
            get_stream_url("dQw4w9WgXcQ")

    @patch("yt_dlp.YoutubeDL")
    def test_raises_stream_url_error_when_no_url(self, mock_ydl_cls: MagicMock) -> None:
        _mock_ytdl_context(mock_ydl_cls, {"url": None, "duration": 120.0})

        with pytest.raises(StreamUrlError, match="No direct stream URL"):
            get_stream_url("dQw4w9WgXcQ")

    @patch("yt_dlp.YoutubeDL")
    def test_raises_stream_url_error_when_no_info(self, mock_ydl_cls: MagicMock) -> None:
        _mock_ytdl_context(mock_ydl_cls, None)

        with pytest.raises(StreamUrlError, match="no info"):
            get_stream_url("dQw4w9WgXcQ")

    @patch("yt_dlp.YoutubeDL")
    def test_raises_stream_url_error_when_no_duration(self, mock_ydl_cls: MagicMock) -> None:
        _mock_ytdl_context(mock_ydl_cls, {"url": "https://stream.url/video.mp4", "duration": None})

        with pytest.raises(StreamUrlError, match="Could not determine duration"):
            get_stream_url("dQw4w9WgXcQ")

    def test_raises_on_invalid_client(self) -> None:
        with pytest.raises(DownloadError, match="Unknown client"):
            get_stream_url("dQw4w9WgXcQ", client="andrloid")


class TestGetVideoDuration:
    @patch("yt_dlp.YoutubeDL")
    def test_returns_duration(self, mock_ydl_cls: MagicMock) -> None:
        _mock_ytdl_context(mock_ydl_cls, {"duration": 210.5})

        result = get_video_duration("dQw4w9WgXcQ")
        assert result == 210.5

    @patch("yt_dlp.YoutubeDL")
    def test_uses_cookies_from_browser_when_set(self, mock_ydl_cls: MagicMock) -> None:
        _mock_ytdl_context(mock_ydl_cls, {"duration": 210.5})

        get_video_duration("dQw4w9WgXcQ", cookies_from_browser="firefox")

        opts = mock_ydl_cls.call_args[0][0]
        assert opts["cookiesfrombrowser"] == ["firefox"]

    @patch("yt_dlp.YoutubeDL")
    def test_uses_ios_client_when_set(self, mock_ydl_cls: MagicMock) -> None:
        _mock_ytdl_context(mock_ydl_cls, {"duration": 210.5})

        get_video_duration("dQw4w9WgXcQ", client="ios")

        opts = mock_ydl_cls.call_args[0][0]
        assert "iPhone" in opts["user_agent"]
        assert opts["extractor_args"]["youtube"]["player_client"] == "ios"

    @patch("yt_dlp.YoutubeDL")
    def test_raises_when_no_info(self, mock_ydl_cls: MagicMock) -> None:
        _mock_ytdl_context(mock_ydl_cls, None)

        with pytest.raises(StreamUrlError):
            get_video_duration("dQw4w9WgXcQ")

    @patch("yt_dlp.YoutubeDL")
    def test_raises_when_no_duration(self, mock_ydl_cls: MagicMock) -> None:
        _mock_ytdl_context(mock_ydl_cls, {"duration": None})

        with pytest.raises(StreamUrlError, match="Could not determine duration"):
            get_video_duration("dQw4w9WgXcQ")

    def test_raises_on_invalid_client(self) -> None:
        with pytest.raises(DownloadError, match="Unknown client"):
            get_video_duration("dQw4w9WgXcQ", client="andrloid")


class TestGetMediaDuration:
    @patch("youtube_tools_mcp.youtube.downloader.shutil")
    @patch("youtube_tools_mcp.youtube.downloader.subprocess")
    def test_returns_float_from_ffprobe_stdout(self, mock_subprocess: MagicMock, mock_shutil: MagicMock) -> None:
        mock_shutil.which.return_value = "/usr/bin/ffmpeg"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "210.5\n"
        mock_subprocess.run.return_value = mock_result

        result = get_media_duration("/tmp/video.mp4")
        assert result == 210.5

        cmd = mock_subprocess.run.call_args[0][0]
        assert cmd[0] == "ffprobe"
        assert cmd[-1] == "/tmp/video.mp4"

    @patch("youtube_tools_mcp.youtube.downloader.shutil")
    @patch("youtube_tools_mcp.youtube.downloader.subprocess")
    def test_raises_ffmpeg_error_on_nonzero_exit(self, mock_subprocess: MagicMock, mock_shutil: MagicMock) -> None:
        mock_shutil.which.return_value = "/usr/bin/ffmpeg"
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Invalid data"
        mock_subprocess.run.return_value = mock_result

        with pytest.raises(FFmpegError, match="ffprobe failed"):
            get_media_duration("/tmp/video.mp4")

    @patch("youtube_tools_mcp.youtube.downloader.shutil")
    @patch("youtube_tools_mcp.youtube.downloader.subprocess")
    def test_raises_ffmpeg_error_on_invalid_stdout(self, mock_subprocess: MagicMock, mock_shutil: MagicMock) -> None:
        mock_shutil.which.return_value = "/usr/bin/ffmpeg"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "not_a_number"
        mock_subprocess.run.return_value = mock_result

        with pytest.raises(FFmpegError, match="invalid duration"):
            get_media_duration("/tmp/video.mp4")

    def test_raises_ffmpeg_not_found(self) -> None:
        with (
            patch("youtube_tools_mcp.youtube.downloader.shutil.which", return_value=None),
            pytest.raises(FFmpegNotFoundError),
        ):
            get_media_duration("/tmp/video.mp4")


class TestExtractFrame:
    @patch("youtube_tools_mcp.youtube.downloader.shutil")
    @patch("youtube_tools_mcp.youtube.downloader.subprocess")
    def test_extracts_frame_successfully_no_scale(self, mock_subprocess: MagicMock, mock_shutil: MagicMock) -> None:
        mock_shutil.which.return_value = "/usr/bin/ffmpeg"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.run.return_value = mock_result
        mock_subprocess.TimeoutExpired = subprocess.TimeoutExpired

        output_path = Path("/tmp/test_frame.jpg")
        with patch.object(Path, "exists", return_value=True):
            result = extract_frame("https://stream.url/video.mp4", 10.0, output_path, ffmpeg_timeout=12.5)

        assert result == output_path
        mock_subprocess.run.assert_called_once()
        cmd = mock_subprocess.run.call_args[0][0]
        kwargs = mock_subprocess.run.call_args.kwargs
        assert kwargs["timeout"] == 12.5
        assert cmd[0] == "ffmpeg"
        assert cmd[2] == "10.000"
        assert "-vf" not in cmd

    @patch("youtube_tools_mcp.youtube.downloader.shutil")
    @patch("youtube_tools_mcp.youtube.downloader.subprocess")
    def test_extracts_frame_with_max_width(self, mock_subprocess: MagicMock, mock_shutil: MagicMock) -> None:
        mock_shutil.which.return_value = "/usr/bin/ffmpeg"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.run.return_value = mock_result
        mock_subprocess.TimeoutExpired = subprocess.TimeoutExpired

        output_path = Path("/tmp/test_frame.jpg")
        with patch.object(Path, "exists", return_value=True):
            result = extract_frame("https://stream.url/video.mp4", 10.0, output_path, max_width=800)

        assert result == output_path
        cmd = mock_subprocess.run.call_args[0][0]
        assert "-vf" in cmd
        scale_val = cmd[cmd.index("-vf") + 1]
        assert "800" in scale_val

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
    @patch("youtube_tools_mcp.youtube.downloader.subprocess")
    def test_nonzero_input_error_raises_input_error(self, mock_subprocess: MagicMock, mock_shutil: MagicMock) -> None:
        mock_shutil.which.return_value = "/usr/bin/ffmpeg"
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Error opening input file https://stream.url/video.mp4"
        mock_subprocess.run.return_value = mock_result
        mock_subprocess.TimeoutExpired = subprocess.TimeoutExpired

        with pytest.raises(FFmpegInputError, match="ffmpeg failed"):
            extract_frame("https://stream.url/video.mp4", 10.0, Path("/tmp/frame.jpg"))

    @patch("youtube_tools_mcp.youtube.downloader.shutil")
    @patch("youtube_tools_mcp.youtube.downloader.subprocess")
    def test_nonzero_output_error_raises_output_error(self, mock_subprocess: MagicMock, mock_shutil: MagicMock) -> None:
        mock_shutil.which.return_value = "/usr/bin/ffmpeg"
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Permission denied"
        mock_subprocess.run.return_value = mock_result
        mock_subprocess.TimeoutExpired = subprocess.TimeoutExpired

        with pytest.raises(FFmpegOutputError, match="ffmpeg failed"):
            extract_frame("https://stream.url/video.mp4", 10.0, Path("/tmp/frame.jpg"))

    @patch("youtube_tools_mcp.youtube.downloader.shutil")
    @patch("youtube_tools_mcp.youtube.downloader.subprocess")
    def test_failed_to_open_output_is_output_error(self, mock_subprocess: MagicMock, mock_shutil: MagicMock) -> None:
        mock_shutil.which.return_value = "/usr/bin/ffmpeg"
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Failed to open output file /nope/frame.jpg"
        mock_subprocess.run.return_value = mock_result
        mock_subprocess.TimeoutExpired = subprocess.TimeoutExpired

        with pytest.raises(FFmpegOutputError, match="ffmpeg failed"):
            extract_frame("https://stream.url/video.mp4", 10.0, Path("/tmp/frame.jpg"))

    @patch("youtube_tools_mcp.youtube.downloader.shutil")
    def test_raises_ffmpeg_error_on_timeout(self, mock_shutil: MagicMock) -> None:
        mock_shutil.which.return_value = "/usr/bin/ffmpeg"

        with patch("youtube_tools_mcp.youtube.downloader.subprocess") as mock_subprocess:
            mock_subprocess.TimeoutExpired = subprocess.TimeoutExpired
            mock_subprocess.run.side_effect = subprocess.TimeoutExpired(cmd="ffmpeg", timeout=30)

            with pytest.raises(FFmpegInputError, match="timed out after 60.0s"):
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
            pytest.raises(FFmpegOutputError, match="did not produce output"),
        ):
            extract_frame("https://stream.url/video.mp4", 10.0, Path("/tmp/frame.jpg"))

    def test_raises_ffmpeg_not_found(self) -> None:
        with (
            patch("youtube_tools_mcp.youtube.downloader.shutil.which", return_value=None),
            pytest.raises(FFmpegNotFoundError),
        ):
            extract_frame("https://stream.url/video.mp4", 10.0, Path("/tmp/frame.jpg"))

    @patch("youtube_tools_mcp.youtube.downloader.shutil")
    @patch("youtube_tools_mcp.youtube.downloader.subprocess")
    def test_passes_proxy_via_env(self, mock_subprocess: MagicMock, mock_shutil: MagicMock) -> None:
        mock_shutil.which.return_value = "/usr/bin/ffmpeg"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.run.return_value = mock_result
        mock_subprocess.TimeoutExpired = subprocess.TimeoutExpired

        output_path = Path("/tmp/test_frame.jpg")
        with patch.object(Path, "exists", return_value=True):
            extract_frame("https://stream.url/video.mp4", 10.0, output_path, proxy="http://proxy:8080")

        kwargs = mock_subprocess.run.call_args.kwargs
        assert kwargs["env"]["HTTP_PROXY"] == "http://proxy:8080"
        assert kwargs["env"]["HTTPS_PROXY"] == "http://proxy:8080"

    @patch("youtube_tools_mcp.youtube.downloader.shutil")
    @patch("youtube_tools_mcp.youtube.downloader.subprocess")
    def test_no_env_when_proxy_is_none(self, mock_subprocess: MagicMock, mock_shutil: MagicMock) -> None:
        mock_shutil.which.return_value = "/usr/bin/ffmpeg"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.run.return_value = mock_result
        mock_subprocess.TimeoutExpired = subprocess.TimeoutExpired

        output_path = Path("/tmp/test_frame.jpg")
        with patch.object(Path, "exists", return_value=True):
            extract_frame("https://stream.url/video.mp4", 10.0, output_path, proxy=None)

        kwargs = mock_subprocess.run.call_args.kwargs
        assert kwargs.get("env") is None


class TestExtractFramesBatch:
    @patch("youtube_tools_mcp.youtube.downloader.extract_frame")
    @patch("youtube_tools_mcp.youtube.downloader.shutil")
    def test_extracts_multiple_frames(self, mock_shutil: MagicMock, mock_extract: MagicMock) -> None:
        mock_shutil.which.return_value = "/usr/bin/ffmpeg"
        mock_extract.side_effect = lambda url, ts, path, max_width=None, quality=5, ffmpeg_timeout=60.0, proxy=None: (
            path
        )

        output_dir = Path("/tmp/frames")
        timestamps = [0.0, 5.0, 10.0]

        with patch.object(Path, "mkdir"):
            result = extract_frames_batch(
                "https://stream.url/video.mp4",
                timestamps,
                output_dir,
                ffmpeg_timeout=15.0,
            )

        assert len(result) == 3
        assert all(isinstance(p, Path) for p in result)
        assert mock_extract.call_args.kwargs["ffmpeg_timeout"] == 15.0

    @patch("youtube_tools_mcp.youtube.downloader.extract_frame")
    @patch("youtube_tools_mcp.youtube.downloader.shutil")
    def test_empty_timestamps(self, mock_shutil: MagicMock, mock_extract: MagicMock) -> None:
        mock_shutil.which.return_value = "/usr/bin/ffmpeg"
        output_dir = Path("/tmp/frames")

        with patch.object(Path, "mkdir"):
            result = extract_frames_batch("https://stream.url/video.mp4", [], output_dir)

        assert result == []
        mock_extract.assert_not_called()

    @patch("youtube_tools_mcp.youtube.downloader.extract_frame")
    @patch("youtube_tools_mcp.youtube.downloader.shutil")
    def test_passes_proxy_to_extract_frame(self, mock_shutil: MagicMock, mock_extract: MagicMock) -> None:
        mock_shutil.which.return_value = "/usr/bin/ffmpeg"
        mock_extract.side_effect = lambda url, ts, path, max_width=None, quality=5, ffmpeg_timeout=60.0, proxy=None: (
            path
        )

        output_dir = Path("/tmp/frames")
        timestamps = [0.0, 5.0]

        with patch.object(Path, "mkdir"):
            extract_frames_batch(
                "https://stream.url/video.mp4",
                timestamps,
                output_dir,
                proxy="http://proxy:8080",
            )

        assert mock_extract.call_count == 2
        assert mock_extract.call_args.kwargs["proxy"] == "http://proxy:8080"

    def test_raises_ffmpeg_not_found(self) -> None:
        with (
            patch("youtube_tools_mcp.youtube.downloader.shutil.which", return_value=None),
            pytest.raises(FFmpegNotFoundError),
        ):
            extract_frames_batch("https://stream.url/video.mp4", [0.0], Path("/tmp/frames"))


class TestDownloadFrameSource:
    @patch("yt_dlp.YoutubeDL")
    def test_downloads_small_local_source(self, mock_ydl_cls: MagicMock) -> None:
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {"id": "dQw4w9WgXcQ", "ext": "mp4"}
        mock_ydl.prepare_filename.return_value = "/tmp/frames/dQw4w9WgXcQ.mp4"

        output_dir = Path("/tmp/frames")
        with patch.object(Path, "exists", return_value=True), patch.object(Path, "mkdir"):
            result = download_frame_source("dQw4w9WgXcQ", output_dir)

        opts = mock_ydl_cls.call_args[0][0]
        assert opts["format"] == "18/best[height<=480][tbr<=1000][vcodec!=none]/worst[vcodec!=none]"
        assert opts["noplaylist"] is True
        assert result.name == "dQw4w9WgXcQ.mp4"

    @patch("yt_dlp.YoutubeDL")
    def test_uses_proxy_cookies_and_client(self, mock_ydl_cls: MagicMock) -> None:
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {"id": "dQw4w9WgXcQ", "ext": "mp4"}
        mock_ydl.prepare_filename.return_value = "/tmp/frames/dQw4w9WgXcQ.mp4"

        output_dir = Path("/tmp/frames")
        with patch.object(Path, "exists", return_value=True), patch.object(Path, "mkdir"):
            download_frame_source(
                "dQw4w9WgXcQ",
                output_dir,
                proxy="http://proxy:8080",
                cookies_from_browser="firefox",
                client="ios",
            )

        opts = mock_ydl_cls.call_args[0][0]
        assert opts["proxy"] == "http://proxy:8080"
        assert opts["cookiesfrombrowser"] == ["firefox"]
        assert "iPhone" in opts["user_agent"]
        assert opts["extractor_args"]["youtube"]["player_client"] == "ios"


class TestDownloadVideo:
    @patch("yt_dlp.YoutubeDL")
    @patch("youtube_tools_mcp.youtube.downloader.shutil.which")
    def test_uses_cookies_and_client(self, mock_which: MagicMock, mock_ydl_cls: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/ffmpeg"
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {"title": "Test", "ext": "mp4"}
        mock_ydl.prepare_filename.return_value = "/tmp/Test.mp4"

        output_dir = Path("/tmp/downloads")
        with patch.object(Path, "exists", return_value=True), patch.object(Path, "mkdir"):
            result = download_video(
                "dQw4w9WgXcQ",
                output_dir,
                proxy="http://proxy:8080",
                cookies_from_browser="chrome",
                client="android",
                ytdlp_socket_timeout=15.0,
            )

        opts = mock_ydl_cls.call_args[0][0]
        assert opts["proxy"] == "http://proxy:8080"
        assert opts["cookiesfrombrowser"] == ["chrome"]
        assert opts["socket_timeout"] == 15.0
        assert "Android" in opts["user_agent"]
        assert opts["extractor_args"]["youtube"]["player_client"] == "android"
        assert result.name == "Test.mp4"


class TestDownloadAudio:
    @patch("yt_dlp.YoutubeDL")
    @patch("youtube_tools_mcp.youtube.downloader.shutil.which")
    def test_uses_cookies_and_client(self, mock_which: MagicMock, mock_ydl_cls: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/ffmpeg"
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {"title": "Test", "ext": "webm"}
        mock_ydl.prepare_filename.return_value = "/tmp/Test.webm"

        output_dir = Path("/tmp/downloads")
        with patch.object(Path, "exists", return_value=True), patch.object(Path, "mkdir"):
            result = download_audio(
                "dQw4w9WgXcQ",
                output_dir,
                proxy="http://proxy:8080",
                cookies_from_browser="firefox",
                client="ios",
                ytdlp_socket_timeout=15.0,
            )

        opts = mock_ydl_cls.call_args[0][0]
        assert opts["proxy"] == "http://proxy:8080"
        assert opts["cookiesfrombrowser"] == ["firefox"]
        assert opts["socket_timeout"] == 15.0
        assert "iPhone" in opts["user_agent"]
        assert opts["extractor_args"]["youtube"]["player_client"] == "ios"
        assert result.name == "Test.mp3"
