.PHONY: setup run-mcp run-mcp-pharmacy run-approval run-agent test seed demo

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
