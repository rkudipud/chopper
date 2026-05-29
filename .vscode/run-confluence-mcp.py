from __future__ import annotations

import os
import sys
import urllib.request

import requests.utils


def _require_token() -> str:
    token = os.getenv("WIKI_PERSONAL_TOKEN") or os.getenv("CONFLUENCE_PERSONAL_TOKEN")
    if not token:
        raise RuntimeError(
            "Missing token: set WIKI_PERSONAL_TOKEN (preferred) or CONFLUENCE_PERSONAL_TOKEN"
        )
    return token


def _configure_proxy_bypass() -> None:
    # Force bypass for Intel wiki endpoints; this process runs dedicated Confluence MCP.
    bypass_hosts = "wiki.ith.intel.com,.ith.intel.com,intel.com,localhost,127.0.0.1"
    os.environ["NO_PROXY"] = bypass_hosts
    os.environ["no_proxy"] = bypass_hosts

    for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        os.environ.pop(var, None)

    urllib.request.getproxies = lambda: {}
    requests.utils.get_environ_proxies = lambda url, no_proxy=None: {}


def main() -> None:
    token = _require_token()
    _configure_proxy_bypass()

    sys.argv = [
        "mcp-atlassian",
        "--transport",
        "stdio",
        "--confluence-url",
        "https://wiki.ith.intel.com",
        "--confluence-personal-token",
        token,
        "--no-confluence-ssl-verify",
        "--toolsets",
        "all",
    ]

    from mcp_atlassian import main as mcp_main

    mcp_main()


if __name__ == "__main__":
    main()
