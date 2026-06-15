from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

import pytest
from mcp.shared.exceptions import McpError
from mcp.types import CallToolResult, ImageContent, TextContent

from youtube_tools_mcp.tools.frames import (
    extract_frames_every,
    extract_video_frame,
    extract_video_frames,
)
from youtube_tools_mcp.youtube.downloader import DownloadError

from ..conftest import SAMPLE_VIDEO_ID

_STREAM = "youtube_tools_mcp.tools.frames.get_stream_url"
_MEDIA_DURATION = "youtube_tools_mcp.tools.frames.get_media_duration"
_DOWNLOAD = "youtube_tools_mcp.tools.frames.download_frame_source"
_WHICH = "youtube_tools_mcp.youtube.downloader.shutil.which"
_RUN = "youtube_tools_mcp.youtube.downloader.subprocess.run"

_SAMPLE_STREAM_URL = "https://stream.example.com/video.mp4"


class TestExtractVideoFrame:
    @patch(_RUN)
    @patch(_WHICH, return_value="ffmpeg")
    def test_returns_text_with_file_path_by_default(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)

        with (
            patch(_STREAM, return_value=(_SAMPLE_STREAM_URL, 120.0)),
            patch.object(Path, "mkdir"),
            patch.object(Path, "exists", return_value=True),
        ):
            result = extract_video_frame(SAMPLE_VIDEO_ID, 10.0, ffmpeg_timeout=12.5)

        assert isinstance(result, CallToolResult)
        assert len(result.content) == 1
        assert isinstance(result.content[0], TextContent)
        assert "Extracted 1 frame(s)" in result.content[0].text
        assert "frame_10.jpg" in result.content[0].text

    @patch(_RUN)
    @patch(_WHICH, return_value="ffmpeg")
    def test_returns_inline_image_when_return_images_true(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)

        with (
            patch(_STREAM, return_value=(_SAMPLE_STREAM_URL, 120.0)),
            patch("youtube_tools_mcp.tools.frames.tempfile.mkdtemp", return_value="/tmp/yt"),
            patch.object(Path, "read_bytes", return_value=b"\xff\xd8fake_jpeg"),
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "iterdir", return_value=[]),
        ):
            result = extract_video_frame(SAMPLE_VIDEO_ID, 10.0, return_images=True)

        assert isinstance(result, CallToolResult)
        assert len(result.content) == 1
        assert isinstance(result.content[0], ImageContent)
        assert result.content[0].mimeType == "image/jpeg"

    @patch(_RUN)
    @patch(_WHICH, return_value="ffmpeg")
    def test_returns_vision_analysis_when_enabled(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)

        with (
            patch(_STREAM, return_value=(_SAMPLE_STREAM_URL, 120.0)),
            patch("youtube_tools_mcp.tools.frames.tempfile.mkdtemp", return_value="/tmp/yt"),
            patch("youtube_tools_mcp.tools.frames.analyze_image_path", return_value="A visible scene"),
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "iterdir", return_value=[]),
        ):
            result = extract_video_frame(SAMPLE_VIDEO_ID, 10.0, vision_analysis=True)

        assert isinstance(result.content[0], TextContent)
        assert "Analyzed 1 frame(s)" in result.content[0].text
        assert "A visible scene" in result.content[0].text

    def test_vision_analysis_conflicts_with_return_images(self) -> None:
        with pytest.raises(McpError, match="vision_analysis cannot be combined"):
            extract_video_frame(SAMPLE_VIDEO_ID, 10.0, return_images=True, vision_analysis=True)

    @patch(_RUN)
    @patch(_WHICH, return_value="ffmpeg")
    def test_custom_output_dir(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)

        with (
            patch(_STREAM, return_value=(_SAMPLE_STREAM_URL, 120.0)),
            patch.object(Path, "mkdir"),
            patch.object(Path, "exists", return_value=True),
        ):
            result = extract_video_frame(SAMPLE_VIDEO_ID, 10.0, output_dir="/custom/dir")

        assert isinstance(result.content[0], TextContent)
        assert "custom" in result.content[0].text and "dir" in result.content[0].text

    def test_invalid_url_raises_mcp_error(self) -> None:
        with pytest.raises(McpError, match="Cannot extract YouTube video ID"):
            extract_video_frame("not_a_valid_id", 10.0)

    def test_stream_url_error_raises_mcp_error(self) -> None:
        with (
            patch(_STREAM, side_effect=DownloadError("no stream")),
            pytest.raises(McpError, match="Failed to get stream URL"),
        ):
            extract_video_frame(SAMPLE_VIDEO_ID, 10.0, download_first=False)

    @patch(_RUN)
    @patch(_WHICH, return_value="ffmpeg")
    def test_auto_falls_back_to_local_file_when_stream_url_fails(
        self, mock_which: MagicMock, mock_run: MagicMock
    ) -> None:
        mock_run.return_value = MagicMock(returncode=0)

        with (
            patch(_STREAM, side_effect=DownloadError("no stream")),
            patch(_DOWNLOAD, return_value=Path("/tmp/yt_video_/video.mp4")) as mock_download,
            patch.object(Path, "mkdir"),
            patch.object(Path, "exists", return_value=True),
        ):
            result = extract_video_frame(SAMPLE_VIDEO_ID, 10.0)

        assert isinstance(result, CallToolResult)
        mock_download.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "yt_video_" in cmd[4]

    def test_ffmpeg_not_found_raises_mcp_error(self) -> None:
        with (
            patch(_WHICH, return_value=None),
            patch(_STREAM, return_value=(_SAMPLE_STREAM_URL, 120.0)),
            patch.object(Path, "mkdir"),
            pytest.raises(McpError, match="ffmpeg is required"),
        ):
            extract_video_frame(SAMPLE_VIDEO_ID, 10.0)

    @patch(_RUN)
    @patch(_WHICH, return_value="ffmpeg")
    def test_auto_falls_back_to_local_file_on_stream_timeout(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.side_effect = [
            subprocess.TimeoutExpired(cmd="ffmpeg", timeout=60.0),
            MagicMock(returncode=0),
        ]

        with (
            patch(_STREAM, return_value=(_SAMPLE_STREAM_URL, 120.0)),
            patch(_DOWNLOAD, return_value=Path("/tmp/yt_video_/video.mp4")) as mock_download,
            patch.object(Path, "mkdir"),
            patch.object(Path, "exists", return_value=True),
        ):
            result = extract_video_frame(SAMPLE_VIDEO_ID, 10.0)

        assert isinstance(result, CallToolResult)
        mock_download.assert_called_once()
        first_cmd = mock_run.call_args_list[0][0][0]
        second_cmd = mock_run.call_args_list[1][0][0]
        assert first_cmd[4] == _SAMPLE_STREAM_URL
        assert "yt_video_" in second_cmd[4]

    def test_invalid_ffmpeg_timeout_raises_mcp_error(self) -> None:
        with pytest.raises(McpError, match="ffmpeg_timeout must be positive"):
            extract_video_frame(SAMPLE_VIDEO_ID, 10.0, ffmpeg_timeout=0.0)

    def test_invalid_download_first_mode_raises_mcp_error(self) -> None:
        with pytest.raises(McpError, match="download_first must be"):
            extract_video_frame(SAMPLE_VIDEO_ID, 10.0, download_first="sometimes")

    @patch(_RUN)
    @patch(_WHICH, return_value="ffmpeg")
    def test_passes_proxy_to_get_stream_url(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)

        with (
            patch(_STREAM, return_value=(_SAMPLE_STREAM_URL, 120.0)) as mock_stream,
            patch.object(Path, "mkdir"),
            patch.object(Path, "exists", return_value=True),
        ):
            extract_video_frame(SAMPLE_VIDEO_ID, 10.0, proxy="http://proxy:8080", download_first=False)

        mock_stream.assert_called_once_with(
            SAMPLE_VIDEO_ID, proxy="http://proxy:8080", cookies_from_browser=None, client="web"
        )

    @patch(_RUN)
    @patch(_WHICH, return_value="ffmpeg")
    def test_passes_cookies_from_browser_to_get_stream_url(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)

        with (
            patch(_STREAM, return_value=(_SAMPLE_STREAM_URL, 120.0)) as mock_stream,
            patch.object(Path, "mkdir"),
            patch.object(Path, "exists", return_value=True),
        ):
            extract_video_frame(SAMPLE_VIDEO_ID, 10.0, cookies_from_browser="chrome", download_first=False)

        mock_stream.assert_called_once_with(SAMPLE_VIDEO_ID, proxy=None, cookies_from_browser="chrome", client="web")

    @patch(_RUN)
    @patch(_WHICH, return_value="ffmpeg")
    def test_passes_client_to_get_stream_url(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)

        with (
            patch(_STREAM, return_value=(_SAMPLE_STREAM_URL, 120.0)) as mock_stream,
            patch.object(Path, "mkdir"),
            patch.object(Path, "exists", return_value=True),
        ):
            extract_video_frame(SAMPLE_VIDEO_ID, 10.0, client="android", download_first=False)

        mock_stream.assert_called_once_with(SAMPLE_VIDEO_ID, proxy=None, cookies_from_browser=None, client="android")

    @patch(_RUN)
    @patch(_WHICH, return_value="ffmpeg")
    def test_download_first_uses_local_file(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)

        with (
            patch(_DOWNLOAD, return_value=Path("/tmp/yt_video_/video.mp4")) as mock_download,
            patch.object(Path, "mkdir"),
            patch.object(Path, "exists", return_value=True),
        ):
            result = extract_video_frame(SAMPLE_VIDEO_ID, 10.0, download_first=True)

        assert isinstance(result, CallToolResult)
        mock_download.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "yt_video_" in cmd[4]
        assert "video.mp4" in cmd[4]

    @patch(_RUN)
    @patch(_WHICH, return_value="ffmpeg")
    def test_download_first_passes_proxy(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)

        with (
            patch(_DOWNLOAD, return_value=Path("/tmp/yt_video_/video.mp4")) as mock_download,
            patch.object(Path, "mkdir"),
            patch.object(Path, "exists", return_value=True),
        ):
            extract_video_frame(SAMPLE_VIDEO_ID, 10.0, proxy="http://proxy:8080", download_first=True)

        mock_download.assert_called_once_with(
            SAMPLE_VIDEO_ID, ANY, proxy="http://proxy:8080", cookies_from_browser=None, client="web"
        )


class TestExtractVideoFrames:
    @patch(_RUN)
    @patch(_WHICH, return_value="ffmpeg")
    def test_returns_text_with_file_paths_by_default(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)

        with (
            patch(_STREAM, return_value=(_SAMPLE_STREAM_URL, 120.0)),
            patch.object(Path, "mkdir"),
            patch.object(Path, "exists", return_value=True),
        ):
            result = extract_video_frames(SAMPLE_VIDEO_ID, [0.0, 5.0, 10.0], ffmpeg_timeout=12.5)

        assert isinstance(result, CallToolResult)
        assert len(result.content) == 1
        assert isinstance(result.content[0], TextContent)
        assert "Extracted 3 frame(s)" in result.content[0].text
        assert "frame_0000.jpg" in result.content[0].text
        assert "frame_0001.jpg" in result.content[0].text
        assert "frame_0002.jpg" in result.content[0].text

    @patch(_RUN)
    @patch(_WHICH, return_value="ffmpeg")
    def test_returns_inline_images_when_return_images_true(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)

        with (
            patch(_STREAM, return_value=(_SAMPLE_STREAM_URL, 120.0)),
            patch("youtube_tools_mcp.tools.frames.tempfile.mkdtemp", return_value="/tmp/yt"),
            patch.object(Path, "read_bytes", return_value=b"\xff\xd8jpeg"),
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "iterdir", return_value=[]),
        ):
            result = extract_video_frames(SAMPLE_VIDEO_ID, [0.0, 5.0], return_images=True)

        assert isinstance(result, CallToolResult)
        assert len(result.content) == 2
        assert all(isinstance(c, ImageContent) for c in result.content)

    @patch(_RUN)
    @patch(_WHICH, return_value="ffmpeg")
    def test_returns_vision_analysis_when_enabled(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)

        with (
            patch(_STREAM, return_value=(_SAMPLE_STREAM_URL, 120.0)),
            patch("youtube_tools_mcp.tools.frames.tempfile.mkdtemp", return_value="/tmp/yt"),
            patch("youtube_tools_mcp.tools.frames.analyze_image_path", side_effect=["First frame", "Second frame"]),
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "iterdir", return_value=[]),
        ):
            result = extract_video_frames(SAMPLE_VIDEO_ID, [0.0, 5.0], vision_analysis=True)

        assert isinstance(result.content[0], TextContent)
        assert "Analyzed 2 frame(s)" in result.content[0].text
        assert "First frame" in result.content[0].text
        assert "Second frame" in result.content[0].text

    @patch(_RUN)
    @patch(_WHICH, return_value="ffmpeg")
    def test_custom_output_dir(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)

        with (
            patch(_STREAM, return_value=(_SAMPLE_STREAM_URL, 120.0)),
            patch.object(Path, "mkdir"),
            patch.object(Path, "exists", return_value=True),
        ):
            result = extract_video_frames(SAMPLE_VIDEO_ID, [0.0], output_dir="/custom/dir")

        assert isinstance(result.content[0], TextContent)
        assert "custom" in result.content[0].text and "dir" in result.content[0].text

    def test_too_many_timestamps_raises_mcp_error(self) -> None:
        timestamps = list(range(31))
        with pytest.raises(McpError, match="Too many timestamps"):
            extract_video_frames(SAMPLE_VIDEO_ID, timestamps)

    def test_invalid_url_raises_mcp_error(self) -> None:
        with pytest.raises(McpError, match="Cannot extract YouTube video ID"):
            extract_video_frames("not_a_valid_id", [0.0])

    def test_stream_url_error_raises_mcp_error(self) -> None:
        with (
            patch(_STREAM, side_effect=DownloadError("no stream")),
            pytest.raises(McpError, match="Failed to get stream URL"),
        ):
            extract_video_frames(SAMPLE_VIDEO_ID, [0.0], download_first=False)

    @patch(_RUN)
    @patch(_WHICH, return_value="ffmpeg")
    def test_auto_falls_back_to_local_file_for_batch_on_stream_timeout(
        self, mock_which: MagicMock, mock_run: MagicMock
    ) -> None:
        mock_run.side_effect = [
            subprocess.TimeoutExpired(cmd="ffmpeg", timeout=60.0),
            MagicMock(returncode=0),
            MagicMock(returncode=0),
        ]

        with (
            patch(_STREAM, return_value=(_SAMPLE_STREAM_URL, 120.0)),
            patch(_DOWNLOAD, return_value=Path("/tmp/yt_video_/video.mp4")) as mock_download,
            patch.object(Path, "mkdir"),
            patch.object(Path, "exists", return_value=True),
        ):
            result = extract_video_frames(SAMPLE_VIDEO_ID, [0.0, 5.0])

        assert isinstance(result, CallToolResult)
        mock_download.assert_called_once()
        assert mock_run.call_args_list[0][0][0][4] == _SAMPLE_STREAM_URL
        assert all("yt_video_" in call[0][0][4] for call in mock_run.call_args_list[1:])

    @patch(_RUN)
    @patch(_WHICH, return_value="ffmpeg")
    def test_passes_proxy_to_get_stream_url(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)

        with (
            patch(_STREAM, return_value=(_SAMPLE_STREAM_URL, 120.0)) as mock_stream,
            patch.object(Path, "mkdir"),
            patch.object(Path, "exists", return_value=True),
        ):
            extract_video_frames(SAMPLE_VIDEO_ID, [0.0, 5.0], proxy="http://proxy:8080", download_first=False)

        mock_stream.assert_called_once_with(
            SAMPLE_VIDEO_ID, proxy="http://proxy:8080", cookies_from_browser=None, client="web"
        )

    @patch(_RUN)
    @patch(_WHICH, return_value="ffmpeg")
    def test_passes_cookies_from_browser_to_get_stream_url(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)

        with (
            patch(_STREAM, return_value=(_SAMPLE_STREAM_URL, 120.0)) as mock_stream,
            patch.object(Path, "mkdir"),
            patch.object(Path, "exists", return_value=True),
        ):
            extract_video_frames(SAMPLE_VIDEO_ID, [0.0, 5.0], cookies_from_browser="firefox", download_first=False)

        mock_stream.assert_called_once_with(SAMPLE_VIDEO_ID, proxy=None, cookies_from_browser="firefox", client="web")

    @patch(_RUN)
    @patch(_WHICH, return_value="ffmpeg")
    def test_passes_client_to_get_stream_url(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)

        with (
            patch(_STREAM, return_value=(_SAMPLE_STREAM_URL, 120.0)) as mock_stream,
            patch.object(Path, "mkdir"),
            patch.object(Path, "exists", return_value=True),
        ):
            extract_video_frames(SAMPLE_VIDEO_ID, [0.0, 5.0], client="ios", download_first=False)

        mock_stream.assert_called_once_with(SAMPLE_VIDEO_ID, proxy=None, cookies_from_browser=None, client="ios")

    @patch(_RUN)
    @patch(_WHICH, return_value="ffmpeg")
    def test_download_first_uses_local_file(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)

        with (
            patch(_DOWNLOAD, return_value=Path("/tmp/yt_video_/video.mp4")) as mock_download,
            patch.object(Path, "mkdir"),
            patch.object(Path, "exists", return_value=True),
        ):
            result = extract_video_frames(SAMPLE_VIDEO_ID, [0.0, 5.0], download_first=True)

        assert isinstance(result, CallToolResult)
        mock_download.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "yt_video_" in cmd[4]
        assert "video.mp4" in cmd[4]


class TestExtractFramesEvery:
    @patch(_RUN)
    @patch(_WHICH, return_value="ffmpeg")
    def test_returns_text_with_file_paths_by_default(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)

        with (
            patch(_STREAM, return_value=(_SAMPLE_STREAM_URL, 120.0)),
            patch.object(Path, "mkdir"),
            patch.object(Path, "exists", return_value=True),
        ):
            result = extract_frames_every(SAMPLE_VIDEO_ID, interval_sec=30.0, max_frames=4, ffmpeg_timeout=12.5)

        assert isinstance(result, CallToolResult)
        assert len(result.content) == 1
        assert isinstance(result.content[0], TextContent)
        assert "Extracted 4 frame(s)" in result.content[0].text

    @patch(_RUN)
    @patch(_WHICH, return_value="ffmpeg")
    def test_returns_inline_images_when_return_images_true(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)

        with (
            patch(_STREAM, return_value=(_SAMPLE_STREAM_URL, 120.0)),
            patch("youtube_tools_mcp.tools.frames.tempfile.mkdtemp", return_value="/tmp/yt"),
            patch.object(Path, "read_bytes", return_value=b"\xff\xd8jpeg"),
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "iterdir", return_value=[]),
        ):
            result = extract_frames_every(SAMPLE_VIDEO_ID, interval_sec=30.0, max_frames=3, return_images=True)

        assert isinstance(result, CallToolResult)
        assert len(result.content) == 3
        assert all(isinstance(c, ImageContent) for c in result.content)

    @patch(_RUN)
    @patch(_WHICH, return_value="ffmpeg")
    def test_returns_vision_analysis_when_enabled(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)

        with (
            patch(_STREAM, return_value=(_SAMPLE_STREAM_URL, 120.0)),
            patch("youtube_tools_mcp.tools.frames.tempfile.mkdtemp", return_value="/tmp/yt"),
            patch("youtube_tools_mcp.tools.frames.analyze_image_path", side_effect=["Frame 0", "Frame 1"]),
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "iterdir", return_value=[]),
        ):
            result = extract_frames_every(SAMPLE_VIDEO_ID, interval_sec=30.0, max_frames=2, vision_analysis=True)

        assert isinstance(result.content[0], TextContent)
        assert "Analyzed 2 frame(s)" in result.content[0].text
        assert "Frame 0" in result.content[0].text
        assert "Frame 1" in result.content[0].text

    @patch(_RUN)
    @patch(_WHICH, return_value="ffmpeg")
    def test_respects_max_frames(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)

        with (
            patch(_STREAM, return_value=(_SAMPLE_STREAM_URL, 600.0)),
            patch.object(Path, "mkdir"),
            patch.object(Path, "exists", return_value=True),
        ):
            extract_frames_every(SAMPLE_VIDEO_ID, interval_sec=30.0, max_frames=5)

        assert mock_run.call_count == 5

    def test_max_frames_exceeds_limit_raises_mcp_error(self) -> None:
        with pytest.raises(McpError, match="max_frames.*exceeds limit"):
            extract_frames_every(SAMPLE_VIDEO_ID, max_frames=31)

    def test_negative_interval_raises_mcp_error(self) -> None:
        with pytest.raises(McpError, match="interval_sec must be positive"):
            extract_frames_every(SAMPLE_VIDEO_ID, interval_sec=-1.0)

    def test_zero_interval_raises_mcp_error(self) -> None:
        with pytest.raises(McpError, match="interval_sec must be positive"):
            extract_frames_every(SAMPLE_VIDEO_ID, interval_sec=0.0)

    def test_video_shorter_than_interval_raises_mcp_error(self) -> None:
        with (
            patch(_STREAM, return_value=(_SAMPLE_STREAM_URL, 10.0)),
            pytest.raises(McpError, match="shorter than interval"),
        ):
            extract_frames_every(SAMPLE_VIDEO_ID, interval_sec=30.0)

    def test_invalid_url_raises_mcp_error(self) -> None:
        with pytest.raises(McpError, match="Cannot extract YouTube video ID"):
            extract_frames_every("not_a_valid_id")

    def test_stream_url_error_raises_mcp_error(self) -> None:
        with (
            patch(_STREAM, side_effect=DownloadError("no stream")),
            pytest.raises(McpError, match="Failed to get stream URL"),
        ):
            extract_frames_every(SAMPLE_VIDEO_ID, download_first=False)

    @patch(_RUN)
    @patch(_WHICH, return_value="ffmpeg")
    def test_auto_falls_back_to_local_file_for_interval_on_stream_timeout(
        self, mock_which: MagicMock, mock_run: MagicMock
    ) -> None:
        mock_run.side_effect = [
            subprocess.TimeoutExpired(cmd="ffmpeg", timeout=60.0),
            MagicMock(returncode=0),
            MagicMock(returncode=0),
            MagicMock(returncode=0),
            MagicMock(returncode=0),
        ]

        with (
            patch(_STREAM, return_value=(_SAMPLE_STREAM_URL, 120.0)),
            patch(_DOWNLOAD, return_value=Path("/tmp/yt_video_/video.mp4")) as mock_download,
            patch(_MEDIA_DURATION, return_value=120.0),
            patch.object(Path, "mkdir"),
            patch.object(Path, "exists", return_value=True),
        ):
            result = extract_frames_every(SAMPLE_VIDEO_ID, interval_sec=30.0, max_frames=4)

        assert isinstance(result, CallToolResult)
        mock_download.assert_called_once()
        assert mock_run.call_args_list[0][0][0][4] == _SAMPLE_STREAM_URL
        assert all("yt_video_" in call[0][0][4] for call in mock_run.call_args_list[1:])

    @patch(_RUN)
    @patch(_WHICH, return_value="ffmpeg")
    def test_passes_proxy(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)

        with (
            patch(_STREAM, return_value=(_SAMPLE_STREAM_URL, 120.0)) as mock_stream,
            patch.object(Path, "mkdir"),
            patch.object(Path, "exists", return_value=True),
        ):
            extract_frames_every(SAMPLE_VIDEO_ID, interval_sec=30.0, proxy="http://proxy:8080", download_first=False)

        mock_stream.assert_called_once_with(
            SAMPLE_VIDEO_ID, proxy="http://proxy:8080", cookies_from_browser=None, client="web"
        )

    @patch(_RUN)
    @patch(_WHICH, return_value="ffmpeg")
    def test_passes_cookies_from_browser(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)

        with (
            patch(_STREAM, return_value=(_SAMPLE_STREAM_URL, 120.0)) as mock_stream,
            patch.object(Path, "mkdir"),
            patch.object(Path, "exists", return_value=True),
        ):
            extract_frames_every(SAMPLE_VIDEO_ID, interval_sec=30.0, cookies_from_browser="edge", download_first=False)

        mock_stream.assert_called_once_with(SAMPLE_VIDEO_ID, proxy=None, cookies_from_browser="edge", client="web")

    @patch(_RUN)
    @patch(_WHICH, return_value="ffmpeg")
    def test_passes_client(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)

        with (
            patch(_STREAM, return_value=(_SAMPLE_STREAM_URL, 120.0)) as mock_stream,
            patch.object(Path, "mkdir"),
            patch.object(Path, "exists", return_value=True),
        ):
            extract_frames_every(SAMPLE_VIDEO_ID, interval_sec=30.0, client="android", download_first=False)

        mock_stream.assert_called_once_with(SAMPLE_VIDEO_ID, proxy=None, cookies_from_browser=None, client="android")

    @patch(_RUN)
    @patch(_WHICH, return_value="ffmpeg")
    def test_download_first_uses_local_file(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)

        with (
            patch(_DOWNLOAD, return_value=Path("/tmp/yt_video_/video.mp4")) as mock_download,
            patch(_MEDIA_DURATION, return_value=120.0),
            patch.object(Path, "mkdir"),
            patch.object(Path, "exists", return_value=True),
        ):
            result = extract_frames_every(SAMPLE_VIDEO_ID, interval_sec=30.0, max_frames=4, download_first=True)

        assert isinstance(result, CallToolResult)
        mock_download.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "yt_video_" in cmd[4]
        assert "video.mp4" in cmd[4]
