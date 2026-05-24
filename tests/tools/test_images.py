from __future__ import annotations

from pathlib import Path

import pytest
from mcp.shared.exceptions import McpError
from mcp.types import CallToolResult, ImageContent, TextContent

from youtube_tools_mcp.tools.images import analyze_image_file, read_image_file


class TestReadImageFile:
    def test_returns_image_content_for_jpeg(self, tmp_path: Path) -> None:
        image_path = tmp_path / "frame.jpg"
        image_path.write_bytes(b"\xff\xd8fake_jpeg")

        result = read_image_file(str(image_path))

        assert isinstance(result, CallToolResult)
        assert len(result.content) == 1
        assert isinstance(result.content[0], ImageContent)
        assert result.content[0].mimeType == "image/jpeg"
        assert result.content[0].data

    def test_supports_unicode_paths(self, tmp_path: Path) -> None:
        image_dir = tmp_path / "кадры"
        image_dir.mkdir()
        image_path = image_dir / "пример-изображения.png"
        image_path.write_bytes(b"\x89PNGfake")

        result = read_image_file(str(image_path))

        assert isinstance(result.content[0], ImageContent)
        assert result.content[0].mimeType == "image/png"

    def test_missing_file_raises_mcp_error(self, tmp_path: Path) -> None:
        with pytest.raises(McpError, match="Image file not found"):
            read_image_file(str(tmp_path / "missing.jpg"))

    def test_unsupported_extension_raises_mcp_error(self, tmp_path: Path) -> None:
        text_path = tmp_path / "not-image.txt"
        text_path.write_text("hello", encoding="utf-8")

        with pytest.raises(McpError, match="Unsupported image extension"):
            read_image_file(str(text_path))

    def test_directory_raises_mcp_error(self, tmp_path: Path) -> None:
        with pytest.raises(McpError, match="Path is not a file"):
            read_image_file(str(tmp_path))

    def test_read_image_file_can_return_vision_analysis(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        image_path = tmp_path / "frame.jpg"
        image_path.write_bytes(b"\xff\xd8fake_jpeg")

        def fake_analyze(
            path: Path,
            mime_type: str,
            prompt: str | None,
            model: str | None,
            base_url: str | None,
            api_key: str | None,
        ) -> str:
            assert path == image_path
            assert mime_type == "image/jpeg"
            assert prompt == "what is here?"
            assert model == "vision-model"
            assert base_url is None
            assert api_key is None
            return "A test frame"

        monkeypatch.setattr("youtube_tools_mcp.tools.images.analyze_image_path", fake_analyze)

        result = read_image_file(
            str(image_path), vision_analysis=True, vision_prompt="what is here?", vision_model="vision-model"
        )

        assert isinstance(result.content[0], TextContent)
        assert result.content[0].text == "A test frame"

    def test_analyze_image_file_returns_text(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        image_path = tmp_path / "пример.png"
        image_path.write_bytes(b"\x89PNGfake")

        monkeypatch.setattr(
            "youtube_tools_mcp.tools.images.analyze_image_path",
            lambda path, mime_type, prompt, model, base_url=None, api_key=None: f"{mime_type}: {prompt}: {model}",
        )

        result = analyze_image_file(str(image_path), prompt="describe", model="vision-model")

        assert isinstance(result.content[0], TextContent)
        assert result.content[0].text == "image/png: describe: vision-model"
