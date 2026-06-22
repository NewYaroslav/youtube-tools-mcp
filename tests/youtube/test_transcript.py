from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from requests import Session
from requests.exceptions import Timeout
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
    _parse_json3_events,
    _TimeoutSession,
    fetch_transcript_via_ytdlp,
)

from ..conftest import SAMPLE_VIDEO_ID


@pytest.fixture(autouse=True)
def _clear_transcript_timeout_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("YOUTUBE_TOOLS_TRANSCRIPT_API_REQUEST_TIMEOUT", raising=False)


def _mock_ytdlp_context(mock_ytdl_cls: MagicMock, info: dict) -> MagicMock:
    mock_ydl = MagicMock()
    mock_ydl.extract_info.return_value = info
    mock_ytdl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ytdl_cls.return_value.__exit__ = MagicMock(return_value=False)
    return mock_ydl


class TestTimeoutSession:
    def test_injects_default_timeout(self) -> None:
        session = _TimeoutSession(15.0)

        with patch.object(Session, "request") as request:
            session.request("GET", "https://example.com")

        request.assert_called_once_with(
            "GET",
            "https://example.com",
            timeout=15.0,
        )

    def test_preserves_explicit_timeout(self) -> None:
        session = _TimeoutSession(15.0)

        with patch.object(Session, "request") as request:
            session.request("GET", "https://example.com", timeout=2.0)

        request.assert_called_once_with(
            "GET",
            "https://example.com",
            timeout=2.0,
        )


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
        with (
            patch(
                "youtube_tools_mcp.youtube.transcript.TranscriptFetcher._fetch_via_ytdlp",
                side_effect=TranscriptFetchError("ytdlp failed"),
            ),
            patch("youtube_tools_mcp.youtube.captions.get_access_token", return_value=None),
            pytest.raises(TranscriptFetchError),
        ):
            fetcher.fetch(SAMPLE_VIDEO_ID)

    @patch("youtube_tools_mcp.youtube.transcript.YouTubeTranscriptApi")
    def test_fetch_unexpected_exception(self, mock_api_cls: MagicMock) -> None:
        mock_api = mock_api_cls.return_value
        mock_api.fetch.side_effect = RuntimeError("unexpected")

        fetcher = TranscriptFetcher()
        with (
            patch(
                "youtube_tools_mcp.youtube.transcript.TranscriptFetcher._fetch_via_ytdlp",
                side_effect=TranscriptFetchError("ytdlp failed"),
            ),
            patch("youtube_tools_mcp.youtube.captions.get_access_token", return_value=None),
            pytest.raises(TranscriptFetchError, match="Unexpected error"),
        ):
            fetcher.fetch(SAMPLE_VIDEO_ID)

    @patch("youtube_tools_mcp.youtube.transcript.YouTubeTranscriptApi")
    def test_fetch_could_not_retrieve_falls_back_to_ytdlp_without_cookies(
        self,
        mock_api_cls: MagicMock,
    ) -> None:
        mock_api = mock_api_cls.return_value
        mock_api.fetch.side_effect = CouldNotRetrieveTranscript("blocked")

        fetcher = TranscriptFetcher()
        with patch(
            "youtube_tools_mcp.youtube.transcript.TranscriptFetcher._fetch_via_ytdlp",
            return_value="[00:01] ytdlp line",
        ) as mock_ytdlp:
            result = fetcher.fetch(SAMPLE_VIDEO_ID)

        assert result == "[00:01] ytdlp line"
        mock_ytdlp.assert_called_once()

    @patch("youtube_tools_mcp.youtube.transcript.YouTubeTranscriptApi")
    def test_fetch_could_not_retrieve_falls_back_to_captions_api_when_ytdlp_fails(
        self,
        mock_api_cls: MagicMock,
    ) -> None:
        mock_api = mock_api_cls.return_value
        mock_api.fetch.side_effect = CouldNotRetrieveTranscript("blocked")

        fetcher = TranscriptFetcher()
        with (
            patch(
                "youtube_tools_mcp.youtube.transcript.TranscriptFetcher._fetch_via_ytdlp",
                side_effect=TranscriptFetchError("ytdlp failed"),
            ),
            patch(
                "youtube_tools_mcp.youtube.transcript.TranscriptFetcher._fetch_via_captions_api",
                return_value="[00:01] fallback line",
            ),
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
        with (
            patch(
                "youtube_tools_mcp.youtube.transcript.TranscriptFetcher._fetch_via_ytdlp",
                side_effect=TranscriptFetchError("ytdlp failed"),
            ),
            patch(
                "youtube_tools_mcp.youtube.transcript.TranscriptFetcher._fetch_via_captions_api",
                side_effect=TranscriptFetchError("fallback failed"),
            ),
            pytest.raises(TranscriptFetchError, match="blocked"),
        ):
            fetcher.fetch(SAMPLE_VIDEO_ID)

    @patch("youtube_tools_mcp.youtube.transcript.YouTubeTranscriptApi")
    def test_fetch_unexpected_exception_falls_back_to_captions_api(
        self,
        mock_api_cls: MagicMock,
    ) -> None:
        mock_api = mock_api_cls.return_value
        mock_api.fetch.side_effect = RuntimeError("unexpected")

        fetcher = TranscriptFetcher()
        with (
            patch(
                "youtube_tools_mcp.youtube.transcript.TranscriptFetcher._fetch_via_ytdlp",
                side_effect=TranscriptFetchError("ytdlp failed"),
            ),
            patch(
                "youtube_tools_mcp.youtube.transcript.TranscriptFetcher._fetch_via_captions_api",
                return_value="[00:02] fallback",
            ),
        ):
            result = fetcher.fetch(SAMPLE_VIDEO_ID)

        assert result == "[00:02] fallback"

    @patch("youtube_tools_mcp.youtube.transcript.YouTubeTranscriptApi")
    def test_fetch_youtube_transcript_api_timeout_falls_back_to_ytdlp(
        self,
        mock_api_cls: MagicMock,
    ) -> None:
        mock_api = mock_api_cls.return_value
        mock_api.fetch.side_effect = Timeout("read timed out")

        fetcher = TranscriptFetcher()
        with patch(
            "youtube_tools_mcp.youtube.transcript.TranscriptFetcher._fetch_via_ytdlp",
            return_value="[00:03] ytdlp fallback",
        ) as mock_ytdlp:
            result = fetcher.fetch(SAMPLE_VIDEO_ID)

        assert result == "[00:03] ytdlp fallback"
        mock_ytdlp.assert_called_once()

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

    @patch("youtube_tools_mcp.youtube.transcript.YouTubeTranscriptApi")
    def test_fetch_uses_ytdlp_first_when_cookies_set(
        self,
        mock_api_cls: MagicMock,
    ) -> None:
        mock_api = mock_api_cls.return_value
        mock_api.fetch.side_effect = CouldNotRetrieveTranscript("blocked")

        fetcher = TranscriptFetcher(cookies_from_browser="firefox")
        with patch(
            "youtube_tools_mcp.youtube.transcript.TranscriptFetcher._fetch_via_ytdlp",
            return_value="[00:01] ytdlp line",
        ) as mock_ytdlp:
            result = fetcher.fetch(SAMPLE_VIDEO_ID)

        assert result == "[00:01] ytdlp line"
        mock_ytdlp.assert_called_once()
        mock_api.fetch.assert_not_called()

    @patch("youtube_tools_mcp.youtube.transcript.YouTubeTranscriptApi")
    def test_fetch_ytdlp_fallback_fails_then_tries_captions_api(
        self,
        mock_api_cls: MagicMock,
    ) -> None:
        mock_api = mock_api_cls.return_value
        mock_api.fetch.side_effect = CouldNotRetrieveTranscript("blocked")

        fetcher = TranscriptFetcher(cookies_from_browser="firefox")
        with (
            patch(
                "youtube_tools_mcp.youtube.transcript.TranscriptFetcher._fetch_via_ytdlp",
                side_effect=TranscriptFetchError("ytdlp failed"),
            ) as mock_ytdlp,
            patch(
                "youtube_tools_mcp.youtube.transcript.TranscriptFetcher._fetch_via_captions_api",
                return_value="[00:02] captions line",
            ) as mock_captions,
        ):
            result = fetcher.fetch(SAMPLE_VIDEO_ID)

        assert result == "[00:02] captions line"
        mock_ytdlp.assert_called_once()
        mock_captions.assert_called_once()


class TestParseJson3Events:
    def test_parse_simple(self):
        events = [
            {"tStartMs": 1000, "dDurationMs": 2500, "segs": [{"utf8": "Hello "}, {"utf8": "world"}]},
            {"tStartMs": 4000, "dDurationMs": 2000, "segs": [{"utf8": "Second"}]},
            {"tStartMs": 7000, "segs": [{"utf8": "\n"}]},
        ]
        result = _parse_json3_events(events)
        assert len(result) == 2
        assert result[0]["text"] == "Hello world"
        assert result[0]["start"] == 1.0
        assert result[0]["duration"] == 2.5
        assert result[1]["text"] == "Second"
        assert result[1]["start"] == 4.0

    def test_empty_events(self):
        assert _parse_json3_events([]) == []

    def test_skips_no_segs(self):
        events = [
            {"tStartMs": 1000, "dDurationMs": 1000},
            {"tStartMs": 2000, "dDurationMs": 1000, "segs": [{"utf8": "only"}]},
        ]
        result = _parse_json3_events(events)
        assert len(result) == 1
        assert result[0]["text"] == "only"


class TestFetchTranscriptViaYtdlp:
    @patch("yt_dlp.YoutubeDL")
    def test_downloads_selected_json3_with_ytdlp_downloader(self, mock_ytdl_cls: MagicMock) -> None:
        mock_ydl = _mock_ytdlp_context(
            mock_ytdl_cls,
            {
                "automatic_captions": {
                    "en": [
                        {"ext": "vtt", "url": "https://subs.example/en.vtt"},
                        {"ext": "json3", "url": "https://subs.example/en.json3"},
                    ]
                },
                "http_headers": {"User-Agent": "yt-dlp"},
            },
        )

        def write_subtitle(filename: str, sub_info: dict, subtitle: bool = False) -> None:
            assert subtitle is True
            assert sub_info["url"] == "https://subs.example/en.json3"
            assert sub_info["http_headers"] == {"User-Agent": "yt-dlp"}
            Path(filename).write_text(
                json.dumps(
                    {
                        "events": [
                            {
                                "tStartMs": 1000,
                                "dDurationMs": 2500,
                                "segs": [{"utf8": "Hello "}, {"utf8": "world"}],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

        mock_ydl.dl.side_effect = write_subtitle

        result = fetch_transcript_via_ytdlp(
            SAMPLE_VIDEO_ID,
            languages=("en",),
            proxy="http://proxy:8080",
            cookies_from_browser="firefox",
            client="android",
        )

        assert result == "[00:01] Hello world"
        opts = mock_ytdl_cls.call_args[0][0]
        assert opts["proxy"] == "http://proxy:8080"
        assert opts["cookiesfrombrowser"] == ["firefox"]
        assert "Android" in opts["user_agent"]
        mock_ydl.dl.assert_called_once()

    @patch("yt_dlp.YoutubeDL")
    def test_falls_back_to_first_available_track_and_parses_vtt(self, mock_ytdl_cls: MagicMock) -> None:
        mock_ydl = _mock_ytdlp_context(
            mock_ytdl_cls,
            {
                "automatic_captions": {
                    "ru": [{"ext": "vtt", "url": "https://subs.example/ru.vtt"}],
                },
            },
        )

        def write_subtitle(filename: str, sub_info: dict, subtitle: bool = False) -> None:
            assert subtitle is True
            assert sub_info["url"] == "https://subs.example/ru.vtt"
            Path(filename).write_text(
                "WEBVTT\n\n"
                "00:00:02.000 --> 00:00:04.500\n"
                "<c>Hello</c> &amp; welcome\n\n"
                "00:00:05.000 --> 00:00:06.000\n"
                "Second line\n",
                encoding="utf-8",
            )

        mock_ydl.dl.side_effect = write_subtitle

        result = fetch_transcript_via_ytdlp(SAMPLE_VIDEO_ID, languages=("en",))

        assert result == "[00:02] Hello & welcome\n[00:05] Second line"

    @patch("yt_dlp.YoutubeDL")
    def test_prefers_human_subtitles_over_automatic_captions(self, mock_ytdl_cls: MagicMock) -> None:
        mock_ydl = _mock_ytdlp_context(
            mock_ytdl_cls,
            {
                "subtitles": {
                    "en": [{"ext": "json3", "url": "https://subs.example/human.json3"}],
                },
                "automatic_captions": {
                    "en": [{"ext": "json3", "url": "https://subs.example/auto.json3"}],
                },
            },
        )

        def write_subtitle(filename: str, sub_info: dict, subtitle: bool = False) -> None:
            assert subtitle is True
            assert sub_info["url"] == "https://subs.example/human.json3"
            Path(filename).write_text(
                json.dumps(
                    {
                        "events": [
                            {
                                "tStartMs": 3000,
                                "dDurationMs": 1000,
                                "segs": [{"utf8": "Human subtitle"}],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

        mock_ydl.dl.side_effect = write_subtitle

        result = fetch_transcript_via_ytdlp(SAMPLE_VIDEO_ID, languages=("en",))

        assert result == "[00:03] Human subtitle"

    @patch("yt_dlp.YoutubeDL")
    def test_skips_requested_language_with_unsupported_format(self, mock_ytdl_cls: MagicMock) -> None:
        mock_ydl = _mock_ytdlp_context(
            mock_ytdl_cls,
            {
                "subtitles": {
                    "ru": [{"ext": "srv3", "url": "https://subs.example/ru.srv3"}],
                    "en": [{"ext": "json3", "url": "https://subs.example/en.json3"}],
                },
            },
        )

        def write_subtitle(filename: str, sub_info: dict, subtitle: bool = False) -> None:
            assert subtitle is True
            assert sub_info["url"] == "https://subs.example/en.json3"
            Path(filename).write_text(
                json.dumps(
                    {
                        "events": [
                            {
                                "tStartMs": 4000,
                                "dDurationMs": 1000,
                                "segs": [{"utf8": "English fallback"}],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

        mock_ydl.dl.side_effect = write_subtitle

        result = fetch_transcript_via_ytdlp(SAMPLE_VIDEO_ID, languages=("ru", "en"))

        assert result == "[00:04] English fallback"

    @patch("yt_dlp.YoutubeDL")
    def test_falls_back_to_auto_when_human_format_is_unsupported(self, mock_ytdl_cls: MagicMock) -> None:
        mock_ydl = _mock_ytdlp_context(
            mock_ytdl_cls,
            {
                "subtitles": {
                    "en": [{"ext": "srv3", "url": "https://subs.example/human.srv3"}],
                },
                "automatic_captions": {
                    "en": [{"ext": "json3", "url": "https://subs.example/auto.json3"}],
                },
            },
        )

        def write_subtitle(filename: str, sub_info: dict, subtitle: bool = False) -> None:
            assert subtitle is True
            assert sub_info["url"] == "https://subs.example/auto.json3"
            Path(filename).write_text(
                json.dumps(
                    {
                        "events": [
                            {
                                "tStartMs": 5000,
                                "dDurationMs": 1000,
                                "segs": [{"utf8": "Automatic fallback"}],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

        mock_ydl.dl.side_effect = write_subtitle

        result = fetch_transcript_via_ytdlp(SAMPLE_VIDEO_ID, languages=("en",))

        assert result == "[00:05] Automatic fallback"

    @patch("yt_dlp.YoutubeDL")
    def test_prefers_requested_auto_language_over_unrequested_human_language(self, mock_ytdl_cls: MagicMock) -> None:
        mock_ydl = _mock_ytdlp_context(
            mock_ytdl_cls,
            {
                "subtitles": {
                    "en": [{"ext": "json3", "url": "https://subs.example/human-en.json3"}],
                },
                "automatic_captions": {
                    "ru": [{"ext": "json3", "url": "https://subs.example/auto-ru.json3"}],
                },
            },
        )

        def write_subtitle(filename: str, sub_info: dict, subtitle: bool = False) -> None:
            assert subtitle is True
            assert sub_info["url"] == "https://subs.example/auto-ru.json3"
            Path(filename).write_text(
                json.dumps(
                    {
                        "events": [
                            {
                                "tStartMs": 6000,
                                "dDurationMs": 1000,
                                "segs": [{"utf8": "Requested auto"}],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

        mock_ydl.dl.side_effect = write_subtitle

        result = fetch_transcript_via_ytdlp(SAMPLE_VIDEO_ID, languages=("ru",))

        assert result == "[00:06] Requested auto"

    @patch("yt_dlp.YoutubeDL")
    def test_download_error_is_wrapped(self, mock_ytdl_cls: MagicMock) -> None:
        mock_ydl = _mock_ytdlp_context(
            mock_ytdl_cls,
            {
                "automatic_captions": {
                    "en": [{"ext": "json3", "url": "https://subs.example/en.json3"}],
                },
            },
        )
        mock_ydl.dl.side_effect = RuntimeError("HTTP 429")

        with pytest.raises(TranscriptFetchError, match="HTTP 429"):
            fetch_transcript_via_ytdlp(SAMPLE_VIDEO_ID, languages=("en",))

    @patch("yt_dlp.YoutubeDL")
    def test_sets_ytdlp_socket_timeout(self, mock_ytdl_cls: MagicMock) -> None:
        _mock_ytdlp_context(
            mock_ytdl_cls,
            {
                "automatic_captions": {
                    "en": [
                        {
                            "ext": "json3",
                            "data": json.dumps(
                                {
                                    "events": [
                                        {
                                            "tStartMs": 1000,
                                            "dDurationMs": 1000,
                                            "segs": [{"utf8": "Timeout"}],
                                        }
                                    ]
                                }
                            ),
                        }
                    ],
                },
            },
        )

        result = fetch_transcript_via_ytdlp(
            SAMPLE_VIDEO_ID,
            languages=("en",),
            ytdlp_socket_timeout=17.5,
        )

        assert result == "[00:01] Timeout"
        opts = mock_ytdl_cls.call_args[0][0]
        assert opts["socket_timeout"] == 17.5


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
        assert call_kwargs["http_client"].timeout == 5.0

    @patch("youtube_tools_mcp.youtube.transcript.YouTubeTranscriptApi")
    def test_init_without_proxy_no_proxy_config(self, mock_api_cls: MagicMock) -> None:
        with patch.dict("os.environ", {}, clear=True):
            TranscriptFetcher()

        call_kwargs = mock_api_cls.call_args[1]
        assert "proxy_config" not in call_kwargs
        assert call_kwargs["http_client"].timeout == 5.0

    @patch("youtube_tools_mcp.youtube.transcript.YouTubeTranscriptApi")
    def test_init_uses_transcript_api_request_timeout_from_environment(self, mock_api_cls: MagicMock) -> None:
        with patch.dict("os.environ", {"YOUTUBE_TOOLS_TRANSCRIPT_API_REQUEST_TIMEOUT": "3.5"}, clear=True):
            TranscriptFetcher()

        call_kwargs = mock_api_cls.call_args[1]
        assert call_kwargs["http_client"].timeout == 3.5

    @patch("youtube_tools_mcp.youtube.transcript.YouTubeTranscriptApi")
    def test_init_uses_explicit_transcript_api_timeout(self, mock_api_cls: MagicMock) -> None:
        TranscriptFetcher(transcript_api_timeout=8.5)

        call_kwargs = mock_api_cls.call_args[1]
        assert call_kwargs["http_client"].timeout == 8.5

    @patch("youtube_tools_mcp.youtube.transcript.YouTubeTranscriptApi")
    @pytest.mark.parametrize(
        "value",
        ["nan", "inf", "-inf", float("nan"), float("inf"), float("-inf"), 0, -1],
    )
    def test_init_rejects_invalid_explicit_transcript_api_timeout(
        self,
        _mock_api_cls: MagicMock,
        value: object,
    ) -> None:
        with pytest.raises(TranscriptFetchError, match="transcript_api_timeout must be a positive finite number"):
            TranscriptFetcher(transcript_api_timeout=value)

    @patch("youtube_tools_mcp.youtube.transcript.YouTubeTranscriptApi")
    @pytest.mark.parametrize("value", ["abc", "nan", "inf", "-inf", "0", "-1"])
    def test_init_rejects_invalid_transcript_api_timeout_from_environment(
        self,
        _mock_api_cls: MagicMock,
        value: str,
    ) -> None:
        with (
            patch.dict("os.environ", {"YOUTUBE_TOOLS_TRANSCRIPT_API_REQUEST_TIMEOUT": value}, clear=True),
            pytest.raises(
                TranscriptFetchError,
                match="YOUTUBE_TOOLS_TRANSCRIPT_API_REQUEST_TIMEOUT must be a positive finite number",
            ),
        ):
            TranscriptFetcher()
