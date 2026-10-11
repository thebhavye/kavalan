.PHONY: setup run-mcp run-mcp-pharmacy run-approval run-agent test seed demo tunnel tunnel-pharmacy

setup:
	if command -v uv >/dev/null 2>&1; then uv sync; else python -m venv .venv && . .venv/bin/activate && pip install -e .; fi

run-mcp:
	uv run python -m mcp_servers.payments.server

run-mcp-pharmacy:
	uv run python -m mcp_servers.pharmacy.server

run-approval:
	uv run uvicorn approval.app:app --host 127.0.0.1 --port 8000

run-agent:
	uv run python -m agent.main

test:
	uv run pytest -q

seed:
	uv run python scripts/seed.py

demo:
	uv run python scripts/demo_scenarios.py

# Expose the local payments MCP (streamable-http on :8001, /mcp) to the
# public internet so the ArmorIQ proxy can reach it. Prints a
# https://<random>.trycloudflare.com URL — register THAT (+ /mcp) as the MCP
# URL in the ArmorIQ dashboard. Requires `cloudflared` installed.
# (Alternative: ngrok http 8001 — needs an ngrok authtoken.)
# Then add the printed hostname to MCP_PUBLIC_HOSTS in .env and restart the
# MCP server, or it rejects tunneled requests with HTTP 421.
tunnel:
	cloudflared tunnel --url http://127.0.0.1:8001

# Same for the pharmacy MCP (streamable-http on :8002, /mcp).
tunnel-pharmacy:
	cloudflared tunnel --url http://127.0.0.1:8002
