from __future__ import annotations

from pathlib import Path

import pytest
from mcp.shared.exceptions import McpError
from mcp.types import CallToolResult, ImageContent

from youtube_tools_mcp.tools.images import read_image_file


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
