from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from youtube_transcript_api._errors import (
    CouldNotRetrieveTranscript,
    InvalidVideoId,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnplayable,
)
from youtube_transcript_api.proxies import GenericProxyConfig

from youtube_tools_mcp.youtube.transcript import (
    InvalidVideoIdError,
    NoTranscriptFoundError,
    TranscriptFetcher,
    TranscriptFetchError,
    TranscriptsDisabledError,
    VideoUnavailableError,
)

from ..conftest import SAMPLE_VIDEO_ID


class TestTranscriptFetcher:
    @patch("youtube_tools_mcp.youtube.transcript.YouTubeTranscriptApi")
    def test_fetch_returns_formatted_transcript(self, mock_api_cls: MagicMock) -> None:
        mock_api = mock_api_cls.return_value
        snippet = MagicMock()
        snippet.start = 0.0
        snippet.text = "Hello world"
        snippet.duration = 5.0
        mock_api.fetch.return_value = [snippet]

        fetcher = TranscriptFetcher()
        result = fetcher.fetch(SAMPLE_VIDEO_ID)

        assert "[00:00]" in result
        assert "Hello world" in result
        mock_api.fetch.assert_called_once_with(SAMPLE_VIDEO_ID, languages=["en"])

    @patch("youtube_tools_mcp.youtube.transcript.YouTubeTranscriptApi")
    def test_fetch_with_custom_languages(self, mock_api_cls: MagicMock) -> None:
        mock_api = mock_api_cls.return_value
        mock_api.fetch.return_value = []

        fetcher = TranscriptFetcher()
        fetcher.fetch(SAMPLE_VIDEO_ID, languages=("ru", "uk"))

        mock_api.fetch.assert_called_once_with(SAMPLE_VIDEO_ID, languages=["ru", "uk"])

    @patch("youtube_tools_mcp.youtube.transcript.YouTubeTranscriptApi")
    def test_fetch_multiline_transcript(self, mock_api_cls: MagicMock) -> None:
        mock_api = mock_api_cls.return_value
        s1 = MagicMock(start=0.0, text="First", duration=3.0)
        s2 = MagicMock(start=3.0, text="Second", duration=3.0)
        mock_api.fetch.return_value = [s1, s2]

        fetcher = TranscriptFetcher()
        result = fetcher.fetch(SAMPLE_VIDEO_ID)

        lines = result.split("\n")
        assert len(lines) == 2
        assert "[00:00]" in lines[0]
        assert "[00:03]" in lines[1]

    @patch("youtube_tools_mcp.youtube.transcript.YouTubeTranscriptApi")
    def test_fetch_newlines_in_text_replaced(self, mock_api_cls: MagicMock) -> None:
        mock_api = mock_api_cls.return_value
        snippet = MagicMock(start=0.0, text="line1\nline2", duration=5.0)
        mock_api.fetch.return_value = [snippet]

        fetcher = TranscriptFetcher()
        result = fetcher.fetch(SAMPLE_VIDEO_ID)

        assert "line1 line2" in result
        assert "\n" not in result.split("] ", 1)[1]

    @patch("youtube_tools_mcp.youtube.transcript.YouTubeTranscriptApi")
    def test_fetch_transcripts_disabled(self, mock_api_cls: MagicMock) -> None:
        mock_api = mock_api_cls.return_value
        mock_api.fetch.side_effect = TranscriptsDisabled("disabled")

        fetcher = TranscriptFetcher()
        with pytest.raises(TranscriptsDisabledError, match="disabled"):
            fetcher.fetch(SAMPLE_VIDEO_ID)

    @patch("youtube_tools_mcp.youtube.transcript.YouTubeTranscriptApi")
    def test_fetch_no_transcript_found(self, mock_api_cls: MagicMock) -> None:
        mock_api = mock_api_cls.return_value
        mock_api.fetch.side_effect = NoTranscriptFound(SAMPLE_VIDEO_ID, ["en"], [])

        fetcher = TranscriptFetcher()
        with pytest.raises(NoTranscriptFoundError):
            fetcher.fetch(SAMPLE_VIDEO_ID)

    @patch("youtube_tools_mcp.youtube.transcript.YouTubeTranscriptApi")
    def test_fetch_invalid_video_id(self, mock_api_cls: MagicMock) -> None:
        mock_api = mock_api_cls.return_value
        mock_api.fetch.side_effect = InvalidVideoId("bad_id")

        fetcher = TranscriptFetcher()
        with pytest.raises(InvalidVideoIdError):
            fetcher.fetch("bad_id")

    @patch("youtube_tools_mcp.youtube.transcript.YouTubeTranscriptApi")
    def test_fetch_video_unplayable(self, mock_api_cls: MagicMock) -> None:
        mock_api = mock_api_cls.return_value
        mock_api.fetch.side_effect = VideoUnplayable(SAMPLE_VIDEO_ID, "unplayable", [])

        fetcher = TranscriptFetcher()
        with pytest.raises(VideoUnavailableError):
            fetcher.fetch(SAMPLE_VIDEO_ID)

    @patch("youtube_tools_mcp.youtube.transcript.YouTubeTranscriptApi")
    def test_fetch_could_not_retrieve(self, mock_api_cls: MagicMock) -> None:
        mock_api = mock_api_cls.return_value
        mock_api.fetch.side_effect = CouldNotRetrieveTranscript("retrieve error")

        fetcher = TranscriptFetcher()
        with pytest.raises(TranscriptFetchError):
            fetcher.fetch(SAMPLE_VIDEO_ID)

    @patch("youtube_tools_mcp.youtube.transcript.YouTubeTranscriptApi")
    def test_fetch_unexpected_exception(self, mock_api_cls: MagicMock) -> None:
        mock_api = mock_api_cls.return_value
        mock_api.fetch.side_effect = RuntimeError("unexpected")

        fetcher = TranscriptFetcher()
        with pytest.raises(TranscriptFetchError, match="Unexpected error"):
            fetcher.fetch(SAMPLE_VIDEO_ID)

    @patch("youtube_tools_mcp.youtube.transcript.YouTubeTranscriptApi")
    def test_fetch_could_not_retrieve_falls_back_to_captions_api(
        self,
        mock_api_cls: MagicMock,
    ) -> None:
        mock_api = mock_api_cls.return_value
        mock_api.fetch.side_effect = CouldNotRetrieveTranscript("blocked")

        fetcher = TranscriptFetcher()
        with patch(
            "youtube_tools_mcp.youtube.transcript.TranscriptFetcher._fetch_via_captions_api",
            return_value="[00:01] fallback line",
        ):
            result = fetcher.fetch(SAMPLE_VIDEO_ID)

        assert result == "[00:01] fallback line"

    @patch("youtube_tools_mcp.youtube.transcript.YouTubeTranscriptApi")
    def test_fetch_could_not_retrieve_fallback_also_fails_raises_original(
        self,
        mock_api_cls: MagicMock,
    ) -> None:
        mock_api = mock_api_cls.return_value
        mock_api.fetch.side_effect = CouldNotRetrieveTranscript("blocked")

        fetcher = TranscriptFetcher()
        with patch(
            "youtube_tools_mcp.youtube.transcript.TranscriptFetcher._fetch_via_captions_api",
            side_effect=TranscriptFetchError("fallback failed"),
        ), pytest.raises(TranscriptFetchError, match="blocked"):
            fetcher.fetch(SAMPLE_VIDEO_ID)

    @patch("youtube_tools_mcp.youtube.transcript.YouTubeTranscriptApi")
    def test_fetch_unexpected_exception_falls_back_to_captions_api(
        self,
        mock_api_cls: MagicMock,
    ) -> None:
        mock_api = mock_api_cls.return_value
        mock_api.fetch.side_effect = RuntimeError("unexpected")

        fetcher = TranscriptFetcher()
        with patch(
            "youtube_tools_mcp.youtube.transcript.TranscriptFetcher._fetch_via_captions_api",
            return_value="[00:02] fallback",
        ):
            result = fetcher.fetch(SAMPLE_VIDEO_ID)

        assert result == "[00:02] fallback"

    @patch("youtube_tools_mcp.youtube.transcript.YouTubeTranscriptApi")
    def test_fetch_no_fallback_for_transcripts_disabled(
        self,
        mock_api_cls: MagicMock,
    ) -> None:
        mock_api = mock_api_cls.return_value
        mock_api.fetch.side_effect = TranscriptsDisabled("disabled")

        fetcher = TranscriptFetcher()
        with patch(
            "youtube_tools_mcp.youtube.transcript.TranscriptFetcher._fetch_via_captions_api",
        ) as mock_fallback:
            with pytest.raises(TranscriptsDisabledError, match="disabled"):
                fetcher.fetch(SAMPLE_VIDEO_ID)
            mock_fallback.assert_not_called()

    @patch("youtube_tools_mcp.youtube.transcript.YouTubeTranscriptApi")
    def test_fetch_no_fallback_for_no_transcript_found(
        self,
        mock_api_cls: MagicMock,
    ) -> None:
        mock_api = mock_api_cls.return_value
        mock_api.fetch.side_effect = NoTranscriptFound(SAMPLE_VIDEO_ID, ["en"], [])

        fetcher = TranscriptFetcher()
        with patch(
            "youtube_tools_mcp.youtube.transcript.TranscriptFetcher._fetch_via_captions_api",
        ) as mock_fallback:
            with pytest.raises(NoTranscriptFoundError):
                fetcher.fetch(SAMPLE_VIDEO_ID)
            mock_fallback.assert_not_called()


class TestTranscriptFetcherProxy:
    @patch.dict("os.environ", {"HTTPS_PROXY": "http://127.0.0.1:8080"})
    @patch("youtube_tools_mcp.youtube.transcript.YouTubeTranscriptApi")
    def test_init_with_proxy_passes_proxy_config(self, mock_api_cls: MagicMock) -> None:
        TranscriptFetcher()

        call_kwargs = mock_api_cls.call_args[1]
        assert "proxy_config" in call_kwargs
        proxy_config = call_kwargs["proxy_config"]
        assert isinstance(proxy_config, GenericProxyConfig)
        assert proxy_config.to_requests_dict() == {
            "http": "http://127.0.0.1:8080",
            "https": "http://127.0.0.1:8080",
        }

    @patch("youtube_tools_mcp.youtube.transcript.YouTubeTranscriptApi")
    def test_init_without_proxy_no_proxy_config(self, mock_api_cls: MagicMock) -> None:
        with patch.dict("os.environ", {}, clear=True):
            TranscriptFetcher()

        call_kwargs = mock_api_cls.call_args[1]
        assert "proxy_config" not in call_kwargs
