"""Host-header checks for the MCP HTTP transport (tunnel reachability)."""
from starlette.testclient import TestClient

from mcp_servers.common.transport import public_hosts, tunnel_transport_security

INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                   "clientInfo": {"name": "test", "version": "0"}}}
HEADERS = {"Content-Type": "application/json",
           "Accept": "application/json, text/event-stream"}


def _status_for_host(host: str) -> int:
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("t", transport_security=tunnel_transport_security())
    with TestClient(server.streamable_http_app()) as client:
        return client.post("/mcp", json=INIT,
                           headers={**HEADERS, "Host": host}).status_code


def test_public_hosts_accepts_urls_and_bare_hosts(monkeypatch):
    monkeypatch.setenv("MCP_PUBLIC_HOSTS",
                       " https://a.trycloudflare.com/mcp , b.trycloudflare.com,")
    assert public_hosts() == ["a.trycloudflare.com", "b.trycloudflare.com"]


def test_configured_tunnel_host_is_accepted(monkeypatch):
    monkeypatch.setenv("MCP_PUBLIC_HOSTS", "a.trycloudflare.com")
    assert _status_for_host("a.trycloudflare.com") == 200
    assert _status_for_host("127.0.0.1:8001") == 200


def test_unknown_host_still_rejected(monkeypatch):
    monkeypatch.setenv("MCP_PUBLIC_HOSTS", "a.trycloudflare.com")
    assert _status_for_host("evil.example.com") == 421
