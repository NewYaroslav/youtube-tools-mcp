from __future__ import annotations

from unittest.mock import MagicMock

import pytest

SAMPLE_VIDEO_ID = "dQw4w9WgXcQ"
SAMPLE_URL = f"https://www.youtube.com/watch?v={SAMPLE_VIDEO_ID}"


SAMPLE_TRANSCRIPT_RAW = [
    {"start": 0.0, "text": "We're no strangers to love", "duration": 3.5},
    {"start": 3.5, "text": "You know the rules and so do I", "duration": 3.2},
    {"start": 6.7, "text": "A full commitment's what I'm thinking of", "duration": 4.0},
    {"start": 10.7, "text": "You wouldn't get this from any other guy", "duration": 3.8},
]


@pytest.fixture()
def mock_youtube_transcript_api() -> MagicMock:
    """Fixture that mocks YouTubeTranscriptApi and returns a configured MagicMock."""
    mock_api = MagicMock()
    snippets = []
    for entry in SAMPLE_TRANSCRIPT_RAW:
        snippet = MagicMock()
        snippet.start = entry["start"]
        snippet.text = entry["text"]
        snippet.duration = entry["duration"]
        snippets.append(snippet)
    mock_api.fetch.return_value = snippets
    return mock_api
