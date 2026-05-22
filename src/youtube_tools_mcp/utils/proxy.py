from __future__ import annotations

import json
import os
from pathlib import Path


def _read_proxy_config() -> str | None:
    """Read first proxy URL from .claude/proxy-config.json if present."""
    config_path = Path(".claude/proxy-config.json")
    if not config_path.exists():
        return None
    try:
        with config_path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        proxies = data.get("proxies", [])
        if proxies:
            return str(proxies[0]["url"])
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    return None


def get_proxy_url() -> str | None:
    """Return proxy URL from environment variables or project config.

    Checks HTTPS_PROXY, https_proxy, HTTP_PROXY, http_proxy in order.
    Falls back to the first proxy in .claude/proxy-config.json when present.
    Returns None if no proxy is configured.
    """
    return (
        os.environ.get("HTTPS_PROXY")
        or os.environ.get("https_proxy")
        or os.environ.get("HTTP_PROXY")
        or os.environ.get("http_proxy")
        or _read_proxy_config()
        or None
    )
