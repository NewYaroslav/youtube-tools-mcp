from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from mcp.shared.exceptions import McpError

from youtube_tools_mcp.tools.download import download_audio_file, download_video_file
from youtube_tools_mcp.youtube.downloader import FFmpegNotFoundError, VideoDownloadError


class TestDownloadVideoFile:
    def test_returns_path_on_success(self, tmp_path: Path) -> None:
        fake_path = tmp_path / "test_video.mp4"
        fake_path.write_text("fake")

        with (
            patch("youtube_tools_mcp.tools.download.extract_video_id", return_value="dQw4w9WgXcQ"),
            patch("youtube_tools_mcp.tools.download.download_video", return_value=fake_path),
        ):
            result = download_video_file("dQw4w9WgXcQ", str(tmp_path), "720p")
            assert result == str(fake_path)

    def test_invalid_url_raises_mcp_error(self) -> None:
        with (
            patch("youtube_tools_mcp.tools.download.extract_video_id", side_effect=ValueError("bad id")),
            pytest.raises(McpError),
        ):
            download_video_file("not_a_valid_id")

    def test_unknown_quality_raises_mcp_error(self) -> None:
        with (
            patch("youtube_tools_mcp.tools.download.extract_video_id", return_value="dQw4w9WgXcQ"),
            patch(
                "youtube_tools_mcp.tools.download.download_video",
                side_effect=VideoDownloadError("bad quality"),
            ),
            pytest.raises(McpError),
        ):
            download_video_file("dQw4w9WgXcQ", ".", "8k")

    def test_ffmpeg_not_found_raises_mcp_error(self) -> None:
        with (
            patch("youtube_tools_mcp.tools.download.extract_video_id", return_value="dQw4w9WgXcQ"),
            patch(
                "youtube_tools_mcp.tools.download.download_video",
                side_effect=FFmpegNotFoundError("no ffmpeg"),
            ),
            pytest.raises(McpError),
        ):
            download_video_file("dQw4w9WgXcQ")

    def test_passes_proxy_to_download_video(self, tmp_path: Path) -> None:
        fake_path = tmp_path / "test_video.mp4"
        fake_path.write_text("fake")

        with (
            patch("youtube_tools_mcp.tools.download.extract_video_id", return_value="dQw4w9WgXcQ"),
            patch("youtube_tools_mcp.tools.download.download_video", return_value=fake_path) as mock_dl,
        ):
            download_video_file("dQw4w9WgXcQ", str(tmp_path), "720p", proxy="http://proxy:8080")
            mock_dl.assert_called_once_with(
                "dQw4w9WgXcQ",
                tmp_path.resolve(),
                "720p",
                proxy="http://proxy:8080",
                cookies_from_browser=None,
                client="web",
            )

    def test_passes_client_to_download_video(self, tmp_path: Path) -> None:
        fake_path = tmp_path / "test_video.mp4"
        fake_path.write_text("fake")

        with (
            patch("youtube_tools_mcp.tools.download.extract_video_id", return_value="dQw4w9WgXcQ"),
            patch("youtube_tools_mcp.tools.download.download_video", return_value=fake_path) as mock_dl,
        ):
            download_video_file("dQw4w9WgXcQ", str(tmp_path), "720p", client="android")
            mock_dl.assert_called_once_with(
                "dQw4w9WgXcQ", tmp_path.resolve(), "720p", proxy=None, cookies_from_browser=None, client="android"
            )

    def test_passes_cookies_from_browser_to_download_video(self, tmp_path: Path) -> None:
        fake_path = tmp_path / "test_video.mp4"
        fake_path.write_text("fake")

        with (
            patch("youtube_tools_mcp.tools.download.extract_video_id", return_value="dQw4w9WgXcQ"),
            patch("youtube_tools_mcp.tools.download.download_video", return_value=fake_path) as mock_dl,
        ):
            download_video_file("dQw4w9WgXcQ", str(tmp_path), "720p", cookies_from_browser="chrome")
            mock_dl.assert_called_once_with(
                "dQw4w9WgXcQ",
                tmp_path.resolve(),
                "720p",
                proxy=None,
                cookies_from_browser="chrome",
                client="web",
            )


class TestDownloadAudioFile:
    def test_returns_path_on_success(self, tmp_path: Path) -> None:
        fake_path = tmp_path / "test_audio.mp3"
        fake_path.write_text("fake")

        with (
            patch("youtube_tools_mcp.tools.download.extract_video_id", return_value="dQw4w9WgXcQ"),
            patch("youtube_tools_mcp.tools.download.download_audio", return_value=fake_path),
        ):
            result = download_audio_file("dQw4w9WgXcQ", str(tmp_path), "mp3")
            assert result == str(fake_path)

    def test_invalid_url_raises_mcp_error(self) -> None:
        with (
            patch("youtube_tools_mcp.tools.download.extract_video_id", side_effect=ValueError("bad id")),
            pytest.raises(McpError),
        ):
            download_audio_file("not_a_valid_id")

    def test_unknown_format_raises_mcp_error(self) -> None:
        with (
            patch("youtube_tools_mcp.tools.download.extract_video_id", return_value="dQw4w9WgXcQ"),
            patch(
                "youtube_tools_mcp.tools.download.download_audio",
                side_effect=VideoDownloadError("bad format"),
            ),
            pytest.raises(McpError),
        ):
            download_audio_file("dQw4w9WgXcQ", ".", "flac")

    def test_ffmpeg_not_found_raises_mcp_error(self) -> None:
        with (
            patch("youtube_tools_mcp.tools.download.extract_video_id", return_value="dQw4w9WgXcQ"),
            patch(
                "youtube_tools_mcp.tools.download.download_audio",
                side_effect=FFmpegNotFoundError("no ffmpeg"),
            ),
            pytest.raises(McpError),
        ):
            download_audio_file("dQw4w9WgXcQ")

    def test_default_format_is_mp3(self, tmp_path: Path) -> None:
        fake_path = tmp_path / "test_audio.mp3"
        fake_path.write_text("fake")

        with (
            patch("youtube_tools_mcp.tools.download.extract_video_id", return_value="dQw4w9WgXcQ"),
            patch("youtube_tools_mcp.tools.download.download_audio", return_value=fake_path) as mock_dl,
        ):
            download_audio_file("dQw4w9WgXcQ", str(tmp_path))
            mock_dl.assert_called_once_with(
                "dQw4w9WgXcQ", tmp_path.resolve(), "mp3", proxy=None, cookies_from_browser=None, client="web"
            )

    def test_passes_proxy_to_download_audio(self, tmp_path: Path) -> None:
        fake_path = tmp_path / "test_audio.mp3"
        fake_path.write_text("fake")

        with (
            patch("youtube_tools_mcp.tools.download.extract_video_id", return_value="dQw4w9WgXcQ"),
            patch("youtube_tools_mcp.tools.download.download_audio", return_value=fake_path) as mock_dl,
        ):
            download_audio_file("dQw4w9WgXcQ", str(tmp_path), "mp3", proxy="http://proxy:8080")
            mock_dl.assert_called_once_with(
                "dQw4w9WgXcQ",
                tmp_path.resolve(),
                "mp3",
                proxy="http://proxy:8080",
                cookies_from_browser=None,
                client="web",
            )

    def test_passes_client_to_download_audio(self, tmp_path: Path) -> None:
        fake_path = tmp_path / "test_audio.mp3"
        fake_path.write_text("fake")

        with (
            patch("youtube_tools_mcp.tools.download.extract_video_id", return_value="dQw4w9WgXcQ"),
            patch("youtube_tools_mcp.tools.download.download_audio", return_value=fake_path) as mock_dl,
        ):
            download_audio_file("dQw4w9WgXcQ", str(tmp_path), "mp3", client="ios")
            mock_dl.assert_called_once_with(
                "dQw4w9WgXcQ", tmp_path.resolve(), "mp3", proxy=None, cookies_from_browser=None, client="ios"
            )

    def test_passes_cookies_from_browser_to_download_audio(self, tmp_path: Path) -> None:
        fake_path = tmp_path / "test_audio.mp3"
        fake_path.write_text("fake")

        with (
            patch("youtube_tools_mcp.tools.download.extract_video_id", return_value="dQw4w9WgXcQ"),
            patch("youtube_tools_mcp.tools.download.download_audio", return_value=fake_path) as mock_dl,
        ):
            download_audio_file("dQw4w9WgXcQ", str(tmp_path), "mp3", cookies_from_browser="firefox")
            mock_dl.assert_called_once_with(
                "dQw4w9WgXcQ",
                tmp_path.resolve(),
                "mp3",
                proxy=None,
                cookies_from_browser="firefox",
                client="web",
            )
