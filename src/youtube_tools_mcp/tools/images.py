from __future__ import annotations

import base64
from pathlib import Path

from mcp.shared.exceptions import McpError
from mcp.types import INTERNAL_ERROR, CallToolResult, ErrorData, ImageContent, TextContent

from youtube_tools_mcp.vision import VisionAPIError, VisionConfigError, analyze_image_path

_IMAGE_MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def _err(msg: str) -> McpError:
    return McpError(ErrorData(code=INTERNAL_ERROR, message=msg))


def _image_path_and_mime(path: str) -> tuple[Path, str]:
    image_path = Path(path).expanduser()
    if not image_path.exists():
        raise _err(f"Image file not found: {image_path}")
    if not image_path.is_file():
        raise _err(f"Path is not a file: {image_path}")

    suffix = image_path.suffix.lower()
    mime_type = _IMAGE_MIME_TYPES.get(suffix)
    if mime_type is None:
        raise _err(f"Unsupported image extension {suffix!r}. Supported: {', '.join(sorted(_IMAGE_MIME_TYPES))}")
    return image_path, mime_type


def read_image_file(
    path: str,
    vision_analysis: bool = False,
    vision_prompt: str | None = None,
    vision_model: str | None = None,
    vision_base_url: str | None = None,
    vision_api_key: str | None = None,
) -> CallToolResult:
    """Read a local image file and return it as MCP ImageContent or text analysis.

    Args:
        path: Local image path. Unicode paths are supported.
        vision_analysis: Return text analysis from a configured vision model.
        vision_prompt: Optional prompt for vision analysis.
        vision_model: Optional model override for vision analysis.
        vision_base_url: Optional vision API base URL override (e.g. https://api.openai.com/v1).
        vision_api_key: Optional vision API key override.

    Returns:
        MCP result containing inline image data or text analysis.
    """
    image_path, mime_type = _image_path_and_mime(path)
    if vision_analysis:
        try:
            text = analyze_image_path(
                image_path, mime_type, vision_prompt, vision_model, vision_base_url, vision_api_key
            )
        except (VisionConfigError, VisionAPIError) as exc:
            raise _err(str(exc)) from exc
        return CallToolResult(content=[TextContent(type="text", text=text)])

    data = base64.b64encode(image_path.read_bytes()).decode()
    return CallToolResult(content=[ImageContent(type="image", data=data, mimeType=mime_type)])


def analyze_image_file(
    path: str,
    prompt: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> CallToolResult:
    """Analyze a local image file with a vision model and return text.

    Args:
        path: Local image path.
        prompt: Optional analysis prompt.
        model: Optional vision model override.
        base_url: Optional vision API base URL override.
        api_key: Optional vision API key override.
    """
    image_path, mime_type = _image_path_and_mime(path)
    try:
        text = analyze_image_path(image_path, mime_type, prompt, model, base_url, api_key)
    except (VisionConfigError, VisionAPIError) as exc:
        raise _err(str(exc)) from exc
    return CallToolResult(content=[TextContent(type="text", text=text)])
