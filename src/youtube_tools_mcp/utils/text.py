from __future__ import annotations

import re

_FILLER_WORDS = frozenset(
    {
        "hmm",
        "hm",
        "um",
        "uh",
        "ah",
        "ahh",
        "like,",
        "you know",
        "you know,",
        "sort of",
        "kind of",
        " basically,",
        " basically",
        " literally,",
        " literally",
    }
)

_SENTENCE_END = re.compile(r"[.!?]\s*$")
_TIMESTAMP_PREFIX = re.compile(r"^\[\d{1,2}:\d{2}(?::\d{2})?\]\s*")
_LOWER_START = re.compile(r"^[a-zа-яё]")


def remove_fillers(text: str, fillers: set[str] | None = None) -> str:
    """Remove filler words from text."""
    word_set = fillers if fillers is not None else _FILLER_WORDS
    lines = text.split("\n")
    result: list[str] = []
    for line in lines:
        cleaned = line
        for filler in sorted(word_set, key=len, reverse=True):
            cleaned = cleaned.replace(filler, "")
        cleaned = re.sub(r"  +", " ", cleaned).strip()
        if cleaned:
            result.append(cleaned)
    return "\n".join(result)


def fix_casing(text: str) -> str:
    """Capitalize the first letter of each sentence; lowercase the rest."""
    lines = text.split("\n")
    result: list[str] = []
    for line in lines:
        ts_match = _TIMESTAMP_PREFIX.match(line)
        if ts_match:
            rest = line[ts_match.end() :]
            if rest:
                rest = rest[0].upper() + rest[1:]
            result.append(line[: ts_match.end()] + rest)
            continue
        if line:
            result.append(line[0].upper() + line[1:])
        else:
            result.append(line)
    return "\n".join(result)


def merge_broken_lines(text: str) -> str:
    """Merge lines that were broken mid-sentence by auto-generated subtitles."""
    lines = text.split("\n")
    if len(lines) <= 1:
        return text

    result: list[str] = [lines[0]]
    for line in lines[1:]:
        prev = result[-1]
        ts_match = _TIMESTAMP_PREFIX.match(line)
        if ts_match:
            result.append(line)
            continue

        if prev and not _SENTENCE_END.search(prev) and _LOWER_START.match(line.lstrip()):
            sep = " " if not prev.endswith(" ") else ""
            result[-1] = prev + sep + line
        else:
            result.append(line)

    return "\n".join(result)


def remove_duplicate_lines(text: str) -> str:
    """Remove consecutive duplicate text lines, preserving timestamps."""
    lines = text.split("\n")
    result: list[str] = []
    for line in lines:
        ts_match = _TIMESTAMP_PREFIX.match(line)
        text_part = line[ts_match.end() :].strip() if ts_match else line.strip()
        if not text_part:
            result.append(line)
            continue

        prev_text = None
        if result:
            prev_ts = _TIMESTAMP_PREFIX.match(result[-1])
            prev_text = result[-1][prev_ts.end() :].strip() if prev_ts else result[-1].strip()

        if text_part != prev_text:
            result.append(line)

    return "\n".join(result)


def format_timestamp(seconds: float) -> str:
    """Convert seconds to MM:SS or HH:MM:SS string."""
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def clean_transcript_text(
    text: str,
    *,
    remove_fillers: bool = True,
    fix_casing: bool = True,
    merge_lines: bool = True,
    remove_duplicates: bool = True,
) -> str:
    """Apply all cleanup steps to transcript text."""
    result = text
    if remove_fillers:
        result = _remove_fillers(result)
    if fix_casing:
        result = _fix_casing(result)
    if merge_lines:
        result = _merge_broken_lines(result)
    if remove_duplicates:
        result = _remove_duplicate_lines(result)
    return result


_remove_fillers = remove_fillers
_fix_casing = fix_casing
_merge_broken_lines = merge_broken_lines
_remove_duplicate_lines = remove_duplicate_lines
