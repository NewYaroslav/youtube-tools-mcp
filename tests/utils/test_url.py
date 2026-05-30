from __future__ import annotations

import pytest

from youtube_tools_mcp.utils.url import extract_video_id, normalize_url


class TestExtractVideoId:
    def test_bare_video_id(self) -> None:
        assert extract_video_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_bare_video_id_with_whitespace(self) -> None:
        assert extract_video_id("  dQw4w9WgXcQ  ") == "dQw4w9WgXcQ"

    def test_watch_url(self) -> None:
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_watch_url_without_www(self) -> None:
        url = "https://youtube.com/watch?v=dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_watch_url_with_extra_params(self) -> None:
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_short_url(self) -> None:
        url = "https://youtu.be/dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_embed_url(self) -> None:
        url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_shorts_url(self) -> None:
        url = "https://www.youtube.com/shorts/R-TlOApnm-s"
        assert extract_video_id(url) == "R-TlOApnm-s"

    def test_shorts_url_with_extra_params(self) -> None:
        url = "https://m.youtube.com/shorts/R-TlOApnm-s?si=test"
        assert extract_video_id(url) == "R-TlOApnm-s"

    def test_invalid_input_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Cannot extract YouTube video ID"):
            extract_video_id("not_a_valid_id")

    def test_empty_string_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            extract_video_id("")

    def test_random_url_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            extract_video_id("https://example.com/page")

    def test_video_id_with_dash_and_underscore(self) -> None:
        vid = "abc123_-XYZ"
        assert extract_video_id(vid) == vid


class TestNormalizeUrl:
    def test_creates_watch_url(self) -> None:
        assert normalize_url("dQw4w9WgXcQ") == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    def test_roundtrip_with_extract_video_id(self) -> None:
        vid = "dQw4w9WgXcQ"
        url = normalize_url(vid)
        assert extract_video_id(url) == vid
