from __future__ import annotations

from unittest.mock import MagicMock, patch

from youtube_tools_mcp.utils.proxy import get_proxy_url


class TestGetProxyUrl:
    def test_https_proxy_uppercase(self) -> None:
        with patch.dict("os.environ", {"HTTPS_PROXY": "http://proxy:8080"}, clear=True):
            assert get_proxy_url() == "http://proxy:8080"

    def test_https_proxy_lowercase(self) -> None:
        with patch.dict("os.environ", {"https_proxy": "http://proxy:8080"}, clear=True):
            assert get_proxy_url() == "http://proxy:8080"

    def test_http_proxy_fallback(self) -> None:
        with patch.dict("os.environ", {"HTTP_PROXY": "http://proxy:8080"}, clear=True):
            assert get_proxy_url() == "http://proxy:8080"

    def test_http_proxy_lowercase_fallback(self) -> None:
        with patch.dict("os.environ", {"http_proxy": "http://proxy:8080"}, clear=True):
            assert get_proxy_url() == "http://proxy:8080"

    def test_https_takes_priority_over_http(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "HTTPS_PROXY": "https://proxy:8443",
                "HTTP_PROXY": "http://proxy:8080",
            },
            clear=True,
        ):
            assert get_proxy_url() == "https://proxy:8443"

    def test_full_priority_order(self) -> None:
        # os.environ is case-insensitive on Windows; use a mocked mapping
        # to verify the exact precedence: HTTPS > https > HTTP > http.
        env = {
            "HTTPS_PROXY": "http://upper-https:8080",
            "https_proxy": "http://lower-https:8080",
            "HTTP_PROXY": "http://upper-http:8080",
            "http_proxy": "http://lower-http:8080",
        }
        mock_environ = MagicMock()
        mock_environ.get = env.get
        with patch("youtube_tools_mcp.utils.proxy.os.environ", mock_environ):
            assert get_proxy_url() == "http://upper-https:8080"

    def test_none_when_no_proxy_set(self) -> None:
        with (
            patch.dict("os.environ", {}, clear=True),
            patch(
                "youtube_tools_mcp.utils.proxy._read_proxy_config",
                return_value=None,
            ),
        ):
            assert get_proxy_url() is None

    def test_env_takes_priority_over_config_file(self) -> None:
        with (
            patch.dict("os.environ", {"HTTPS_PROXY": "http://env-proxy:8080"}, clear=True),
            patch(
                "youtube_tools_mcp.utils.proxy._read_proxy_config",
                return_value="http://config-proxy:8080",
            ),
        ):
            assert get_proxy_url() == "http://env-proxy:8080"

    def test_fallback_to_config_file_when_no_env(self) -> None:
        with (
            patch.dict("os.environ", {}, clear=True),
            patch(
                "youtube_tools_mcp.utils.proxy._read_proxy_config",
                return_value="http://config-proxy:8080",
            ),
        ):
            assert get_proxy_url() == "http://config-proxy:8080"

    def test_none_when_config_file_returns_none(self) -> None:
        with (
            patch.dict("os.environ", {}, clear=True),
            patch(
                "youtube_tools_mcp.utils.proxy._read_proxy_config",
                return_value=None,
            ),
        ):
            assert get_proxy_url() is None
