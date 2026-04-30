from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_DEFAULT_PROMPT = "Describe this image in detail. Mention visible text, objects, people, scene, and notable details."
_ENV_LOADED = False


class VisionConfigError(Exception):
    pass


class VisionAPIError(Exception):
    pass


def _load_dotenv() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True

    for env_path in [Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env"]:
        if env_path.is_file():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                key, separator, value = line.strip().partition("=")
                if key and separator and not key.startswith("#"):
                    os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def _env(name: str) -> str | None:
    _load_dotenv()
    return os.environ.get(name)


def _base_url() -> str:
    url = _env("YOUTUBE_TOOLS_VISION_BASE_URL") or _env("OPENAI_BASE_URL")
    if not url:
        anthropic_base = _env("ANTHROPIC_BASE_URL")
        if anthropic_base:
            url = anthropic_base.rstrip("/") + "/v1"
    if not url:
        raise VisionConfigError("Vision base URL is not configured")

    url = url.rstrip("/")
    if not url.endswith("/v1"):
        url += "/v1"
    return url


def _api_key() -> str:
    key = _env("YOUTUBE_TOOLS_VISION_API_KEY") or _env("OPENAI_API_KEY")
    if not key:
        raise VisionConfigError("Vision API key is not configured")
    return key


def _model(model: str | None) -> str:
    selected = (
        model
        or _env("YOUTUBE_TOOLS_VISION_MODEL")
        or _env("OPENAI_VISION_MODEL")
        or _env("ANTHROPIC_TOOL_USE_MODEL")
        or _env("ANTHROPIC_MODEL")
    )
    if not selected:
        raise VisionConfigError("Vision model is not configured")
    return selected


def _timeout() -> float:
    raw = _env("YOUTUBE_TOOLS_VISION_TIMEOUT") or "60"
    try:
        return float(raw)
    except ValueError as exc:
        raise VisionConfigError("YOUTUBE_TOOLS_VISION_TIMEOUT must be a number") from exc


def analyze_image_path(path: Path, mime_type: str, prompt: str | None = None, model: str | None = None) -> str:
    data = base64.b64encode(path.read_bytes()).decode()
    payload = {
        "model": _model(model),
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt or _DEFAULT_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{data}"}},
                ],
            }
        ],
    }
    request = urllib.request.Request(
        _base_url() + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {_api_key()}", "Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=_timeout()) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise VisionAPIError(f"Vision API returned HTTP {exc.code}: {details}") from exc
    except urllib.error.URLError as exc:
        raise VisionAPIError(f"Vision API request failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise VisionAPIError("Vision API request timed out") from exc

    return _extract_text(response_data)


def _extract_text(response_data: dict[str, Any]) -> str:
    choices = response_data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise VisionAPIError("Vision API response did not include choices")

    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise VisionAPIError("Vision API response did not include a message")

    content = message.get("content")
    if isinstance(content, str):
        text = content.strip()
        if text:
            return text
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        text = "\n".join(parts).strip()
        if text:
            return text

    raise VisionAPIError("Vision API response did not include text content")
