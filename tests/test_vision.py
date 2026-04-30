from __future__ import annotations

import json
from pathlib import Path

import pytest

from youtube_tools_mcp import vision
from youtube_tools_mcp.vision import VisionAPIError, VisionConfigError, _extract_text, analyze_image_path


def _reset_dotenv_loader(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(vision, "_ENV_LOADED", False)


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_analyze_image_path_loads_local_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    image_path = tmp_path / "frame.jpg"
    image_path.write_bytes(b"fake-image")
    env_path = tmp_path / ".env"
    env_path.write_text(
        "YOUTUBE_TOOLS_VISION_BASE_URL=http://dotenv.local/v1\n"
        "YOUTUBE_TOOLS_VISION_API_KEY=dotenv-key\n"
        "YOUTUBE_TOOLS_VISION_MODEL=dotenv-model\n",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_urlopen(request: object, timeout: float) -> _FakeResponse:
        captured["request"] = request
        return _FakeResponse({"choices": [{"message": {"content": "Dotenv description"}}]})

    _reset_dotenv_loader(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("YOUTUBE_TOOLS_VISION_BASE_URL", raising=False)
    monkeypatch.delenv("YOUTUBE_TOOLS_VISION_API_KEY", raising=False)
    monkeypatch.delenv("YOUTUBE_TOOLS_VISION_MODEL", raising=False)
    monkeypatch.setattr("youtube_tools_mcp.vision.urllib.request.urlopen", fake_urlopen)

    result = analyze_image_path(image_path, "image/jpeg")

    assert result == "Dotenv description"
    request = captured["request"]
    assert request.full_url == "http://dotenv.local/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer dotenv-key"
    assert json.loads(request.data.decode("utf-8"))["model"] == "dotenv-model"


def test_analyze_image_path_posts_openai_compatible_payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    image_path = tmp_path / "кадр.jpg"
    image_path.write_bytes(b"fake-image")
    captured: dict[str, object] = {}

    def fake_urlopen(request: object, timeout: float) -> _FakeResponse:
        captured["request"] = request
        captured["timeout"] = timeout
        return _FakeResponse({"choices": [{"message": {"content": "A frame description"}}]})

    monkeypatch.setenv("YOUTUBE_TOOLS_VISION_BASE_URL", "http://127.0.0.1:8000/v1")
    monkeypatch.setenv("YOUTUBE_TOOLS_VISION_API_KEY", "test-key")
    monkeypatch.setenv("YOUTUBE_TOOLS_VISION_MODEL", "vision-model")
    monkeypatch.setenv("YOUTUBE_TOOLS_VISION_TIMEOUT", "12")
    monkeypatch.setattr("youtube_tools_mcp.vision.urllib.request.urlopen", fake_urlopen)

    result = analyze_image_path(image_path, "image/jpeg", "describe", None)

    assert result == "A frame description"
    assert captured["timeout"] == 12.0
    request = captured["request"]
    assert request.full_url == "http://127.0.0.1:8000/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer test-key"
    payload = json.loads(request.data.decode("utf-8"))
    assert payload["model"] == "vision-model"
    assert payload["max_tokens"] == 1024
    assert payload["messages"][0]["content"][0] == {"type": "text", "text": "describe"}
    image_url = payload["messages"][0]["content"][1]["image_url"]["url"]
    assert image_url.startswith("data:image/jpeg;base64,")


@pytest.mark.parametrize(
    ("raw_max_tokens", "expected_max_tokens"),
    [("256", 256), ("1", 64), ("999999", 4096)],
)
def test_analyze_image_path_bounds_max_tokens(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    raw_max_tokens: str,
    expected_max_tokens: int,
) -> None:
    image_path = tmp_path / "frame.jpg"
    image_path.write_bytes(b"fake-image")
    captured: dict[str, object] = {}

    def fake_urlopen(request: object, timeout: float) -> _FakeResponse:
        captured["request"] = request
        return _FakeResponse({"choices": [{"message": {"content": "A frame description"}}]})

    monkeypatch.setenv("YOUTUBE_TOOLS_VISION_BASE_URL", "http://127.0.0.1:8000/v1")
    monkeypatch.setenv("YOUTUBE_TOOLS_VISION_API_KEY", "test-key")
    monkeypatch.setenv("YOUTUBE_TOOLS_VISION_MODEL", "vision-model")
    monkeypatch.setenv("YOUTUBE_TOOLS_VISION_MAX_TOKENS", raw_max_tokens)
    monkeypatch.setattr("youtube_tools_mcp.vision.urllib.request.urlopen", fake_urlopen)

    analyze_image_path(image_path, "image/jpeg")

    request = captured["request"]
    payload = json.loads(request.data.decode("utf-8"))
    assert payload["max_tokens"] == expected_max_tokens


def test_analyze_image_path_rejects_invalid_max_tokens(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    image_path = tmp_path / "frame.jpg"
    image_path.write_bytes(b"fake-image")
    monkeypatch.setenv("YOUTUBE_TOOLS_VISION_BASE_URL", "http://127.0.0.1:8000/v1")
    monkeypatch.setenv("YOUTUBE_TOOLS_VISION_API_KEY", "test-key")
    monkeypatch.setenv("YOUTUBE_TOOLS_VISION_MODEL", "vision-model")
    monkeypatch.setenv("YOUTUBE_TOOLS_VISION_MAX_TOKENS", "abc")

    with pytest.raises(VisionConfigError, match="YOUTUBE_TOOLS_VISION_MAX_TOKENS must be an integer"):
        analyze_image_path(image_path, "image/jpeg")


def test_analyze_image_path_requires_explicit_vision_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    image_path = tmp_path / "frame.jpg"
    image_path.write_bytes(b"fake-image")
    monkeypatch.setenv("YOUTUBE_TOOLS_VISION_BASE_URL", "http://127.0.0.1:8000/v1")
    monkeypatch.setenv("YOUTUBE_TOOLS_VISION_MODEL", "vision-model")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "must-not-be-used")
    monkeypatch.delenv("YOUTUBE_TOOLS_VISION_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(VisionConfigError, match="Vision API key is not configured"):
        analyze_image_path(image_path, "image/jpeg")


def test_extract_text_supports_list_content() -> None:
    result = _extract_text(
        {"choices": [{"message": {"content": [{"type": "text", "text": "part 1"}, {"text": "part 2"}]}}]}
    )

    assert result == "part 1\npart 2"


def test_extract_text_rejects_missing_choices() -> None:
    with pytest.raises(VisionAPIError, match="did not include choices"):
        _extract_text({})
