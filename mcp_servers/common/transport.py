"""Shared HTTP transport settings for the sandbox MCP servers.

FastMCP binds to 127.0.0.1 and, by default, only accepts requests whose Host
header is localhost (DNS-rebinding protection). The ArmorIQ proxy reaches us
through a public tunnel, so requests arrive with
``Host: <random>.trycloudflare.com`` and are rejected with HTTP 421.

We keep the protection ON and add the tunnel hostname(s) from
``MCP_PUBLIC_HOSTS`` (comma-separated, exact hostnames — the MCP SDK does
exact matching only, no subdomain wildcards).
"""
from __future__ import annotations

import os

from dotenv import load_dotenv
from mcp.server.transport_security import TransportSecuritySettings

LOCAL_HOSTS = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
LOCAL_ORIGINS = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]


def public_hosts() -> list[str]:
    raw = os.environ.get("MCP_PUBLIC_HOSTS", "")
    hosts = []
    for item in raw.split(","):
        # Accept a pasted URL ("https://x.trycloudflare.com/mcp") or a bare host.
        host = item.strip().removeprefix("https://").removeprefix("http://")
        host = host.split("/", 1)[0]
        if host:
            hosts.append(host)
    return hosts


def tunnel_transport_security() -> TransportSecuritySettings:
    """Localhost plus the configured public tunnel hostname(s)."""
    load_dotenv()
    hosts = public_hosts()
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=LOCAL_HOSTS + hosts,
        allowed_origins=LOCAL_ORIGINS + [f"https://{h}" for h in hosts],
    )
