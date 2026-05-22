from __future__ import annotations

import os


def get_proxy_url() -> str | None:
    """Return proxy URL from environment variables.

    Checks HTTPS_PROXY, https_proxy, HTTP_PROXY, http_proxy in order.
    Returns None if no proxy is configured.
    """
    return (
        os.environ.get("HTTPS_PROXY")
        or os.environ.get("https_proxy")
        or os.environ.get("HTTP_PROXY")
        or os.environ.get("http_proxy")
        or None
    )
