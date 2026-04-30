from __future__ import annotations

from youtube_tools_mcp.tools.cleanup import clean_transcript


class TestCleanTranscript:
    def test_default_cleanup(self) -> None:
        raw = "um this is uh a test\nthis is a test\nit continues\non the next line"
        result = clean_transcript(raw)
        assert "um" not in result
        assert "uh" not in result

    def test_disable_all_cleanups(self) -> None:
        raw = "um hello\nhello"
        result = clean_transcript(
            raw,
            remove_fillers=False,
            fix_casing=False,
            merge_lines=False,
            remove_duplicates=False,
        )
        assert "um" in result
        assert result.count("hello") == 2

    def test_remove_fillers_only(self) -> None:
        raw = "um hello world"
        result = clean_transcript(
            raw,
            remove_fillers=True,
            fix_casing=False,
            merge_lines=False,
            remove_duplicates=False,
        )
        assert "um" not in result
        assert "hello world" in result

    def test_fix_casing_only(self) -> None:
        raw = "hello world"
        result = clean_transcript(
            raw,
            remove_fillers=False,
            fix_casing=True,
            merge_lines=False,
            remove_duplicates=False,
        )
        assert result.startswith("Hello")

    def test_merge_lines_only(self) -> None:
        raw = "this is\na continuation"
        result = clean_transcript(
            raw,
            remove_fillers=False,
            fix_casing=False,
            merge_lines=True,
            remove_duplicates=False,
        )
        assert "a continuation" in result

    def test_remove_duplicates_only(self) -> None:
        raw = "hello\nhello"
        result = clean_transcript(
            raw,
            remove_fillers=False,
            fix_casing=False,
            merge_lines=False,
            remove_duplicates=True,
        )
        assert result.count("hello") == 1

    def test_empty_text(self) -> None:
        assert clean_transcript("") == ""
