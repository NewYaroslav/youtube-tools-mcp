from __future__ import annotations

from youtube_tools_mcp.utils.text import clean_transcript_text


def clean_transcript(
    text: str,
    *,
    remove_fillers: bool = True,
    fix_casing: bool = True,
    merge_lines: bool = True,
    remove_duplicates: bool = True,
) -> str:
    """Clean and format auto-generated transcript text.

    Args:
        text: Raw transcript text (with or without timestamps).
        remove_fillers: Remove filler words (hmm, um, uh, etc.).
        fix_casing: Capitalize first letter of each sentence.
        merge_lines: Merge lines broken mid-sentence.
        remove_duplicates: Remove consecutive duplicate text lines.

    Returns:
        Cleaned transcript text.
    """
    return clean_transcript_text(
        text,
        remove_fillers=remove_fillers,
        fix_casing=fix_casing,
        merge_lines=merge_lines,
        remove_duplicates=remove_duplicates,
    )
