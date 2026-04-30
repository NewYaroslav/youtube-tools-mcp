from __future__ import annotations

from youtube_tools_mcp.utils.text import (
    clean_transcript_text,
    fix_casing,
    format_timestamp,
    merge_broken_lines,
    remove_duplicate_lines,
    remove_fillers,
)


class TestRemoveFillers:
    def test_removes_um_and_uh(self) -> None:
        text = "um this is uh a test"
        assert remove_fillers(text) == "this is a test"

    def test_removes_like_comma(self) -> None:
        text = "it's like, really good"
        result = remove_fillers(text)
        assert "like," not in result
        assert "really good" in result

    def test_removes_you_know(self) -> None:
        text = "you know this is important"
        result = remove_fillers(text)
        assert "you know" not in result
        assert "this is important" in result

    def test_preserves_normal_text(self) -> None:
        text = "This is a normal sentence."
        assert remove_fillers(text) == text

    def test_custom_filler_set(self) -> None:
        text = "like totally this is like totally rad"
        result = remove_fillers(text, fillers={"like totally"})
        assert "like totally" not in result
        assert "this is" in result

    def test_empty_string(self) -> None:
        assert remove_fillers("") == ""

    def test_filler_only_line_removed(self) -> None:
        text = "um\nreal text"
        assert remove_fillers(text) == "real text"

    def test_removes_basically(self) -> None:
        text = "it's basically the same"
        result = remove_fillers(text)
        assert "basically" not in result

    def test_removes_sort_of(self) -> None:
        text = "it's sort of like that"
        result = remove_fillers(text)
        assert "sort of" not in result


class TestFixCasing:
    def test_capitalizes_lowercase_start(self) -> None:
        assert fix_casing("hello world") == "Hello world"

    def test_preserves_already_capitalized(self) -> None:
        assert fix_casing("Hello world") == "Hello world"

    def test_handles_timestamp_prefix(self) -> None:
        result = fix_casing("[03:15] this is a test")
        assert result == "[03:15] This is a test"

    def test_handles_empty_line(self) -> None:
        assert fix_casing("") == ""

    def test_multiline(self) -> None:
        text = "first line\nsecond line"
        result = fix_casing(text)
        assert result == "First line\nSecond line"


class TestMergeBrokenLines:
    def test_merges_continuation_line(self) -> None:
        text = "This is the start of\na sentence that continues"
        result = merge_broken_lines(text)
        assert "start of a sentence" in result
        assert result.count("\n") == 0

    def test_does_not_merge_after_sentence_end(self) -> None:
        text = "First sentence.\nSecond sentence."
        result = merge_broken_lines(text)
        assert result == text

    def test_does_not_merge_timestamp_line(self) -> None:
        text = "Some text.\n[01:00] continuation"
        result = merge_broken_lines(text)
        assert "\n" in result

    def test_single_line_unchanged(self) -> None:
        text = "Just one line"
        assert merge_broken_lines(text) == text

    def test_empty_string(self) -> None:
        assert merge_broken_lines("") == ""

    def test_merges_multiple_continuations(self) -> None:
        text = "This is\na sentence\nthat keeps going"
        result = merge_broken_lines(text)
        assert "This is a sentence that keeps going" in result


class TestRemoveDuplicateLines:
    def test_removes_consecutive_duplicates(self) -> None:
        text = "hello\nhello\nworld"
        assert remove_duplicate_lines(text) == "hello\nworld"

    def test_preserves_non_consecutive_duplicates(self) -> None:
        text = "hello\nworld\nhello"
        assert remove_duplicate_lines(text) == text

    def test_handles_timestamps(self) -> None:
        text = "[00:00] hello\n[00:05] hello"
        result = remove_duplicate_lines(text)
        assert result.count("hello") == 1

    def test_no_duplicates(self) -> None:
        text = "line one\nline two\nline three"
        assert remove_duplicate_lines(text) == text

    def test_empty_string(self) -> None:
        assert remove_duplicate_lines("") == ""


class TestFormatTimestamp:
    def test_zero(self) -> None:
        assert format_timestamp(0.0) == "00:00"

    def test_seconds_only(self) -> None:
        assert format_timestamp(45.0) == "00:45"

    def test_minutes_and_seconds(self) -> None:
        assert format_timestamp(195.0) == "03:15"

    def test_over_one_hour(self) -> None:
        assert format_timestamp(3661.0) == "1:01:01"

    def test_exact_hour(self) -> None:
        assert format_timestamp(3600.0) == "1:00:00"

    def test_fractional_seconds_truncated(self) -> None:
        assert format_timestamp(45.9) == "00:45"


class TestCleanTranscriptText:
    def test_applies_all_cleanups(self) -> None:
        raw = "um this is uh a test\nthis is a test\nit continues\non the next line"
        result = clean_transcript_text(raw)
        assert "um" not in result
        assert "uh" not in result

    def test_disable_fillers(self) -> None:
        raw = "um hello"
        result = clean_transcript_text(raw, remove_fillers=False)
        # fix_casing still runs and capitalizes to "Um"
        assert "Um" in result

    def test_disable_casing(self) -> None:
        raw = "hello world"
        result = clean_transcript_text(raw, fix_casing=False)
        assert result.startswith("h")

    def test_disable_merge(self) -> None:
        raw = "this is\na continuation"
        result = clean_transcript_text(raw, merge_lines=False)
        assert "\n" in result

    def test_disable_duplicates(self) -> None:
        raw = "Hello.\nHello."
        result = clean_transcript_text(raw, remove_duplicates=False)
        assert result.count("Hello") == 2

    def test_empty_text(self) -> None:
        assert clean_transcript_text("") == ""
