from __future__ import annotations

import base64
from pathlib import Path

from mcp.shared.exceptions import McpError
from mcp.types import INTERNAL_ERROR, CallToolResult, ErrorData, ImageContent

_IMAGE_MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def _err(msg: str) -> McpError:
    return McpError(ErrorData(code=INTERNAL_ERROR, message=msg))


def read_image_file(path: str) -> CallToolResult:
    """Read a local image file and return it as MCP ImageContent.

    Args:
        path: Local image path. Unicode paths are supported.

    Returns:
        MCP result containing inline image data for vision-capable models.
    """
    image_path = Path(path).expanduser()
    if not image_path.exists():
        raise _err(f"Image file not found: {image_path}")
    if not image_path.is_file():
        raise _err(f"Path is not a file: {image_path}")

    suffix = image_path.suffix.lower()
    mime_type = _IMAGE_MIME_TYPES.get(suffix)
    if mime_type is None:
        raise _err(f"Unsupported image extension {suffix!r}. Supported: {', '.join(sorted(_IMAGE_MIME_TYPES))}")

    data = base64.b64encode(image_path.read_bytes()).decode()
    return CallToolResult(content=[ImageContent(type="image", data=data, mimeType=mime_type)])
