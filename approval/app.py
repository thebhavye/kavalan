"""Approval web service (FastAPI).

A family member opens these pages on their phone:
  GET  /            simple HTML list of pending held actions
  GET  /pending     JSON list of pending held actions
  GET  /approve/{id}  approval page for one held action
  POST /decision     {id, approved} — records approve/reject (JSON or form)

Recording approval here does NOT execute anything — the agent resumes via
resume_held(), which re-submits through ArmorIQ.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from approval import store

app = FastAPI(title="Kavalan family approvals")

TEMPLATE_DIR = Path(__file__).parent / "templates"


def _render(template: str, **kwargs: Any) -> str:
    html = (TEMPLATE_DIR / template).read_text(encoding="utf-8")
    for key, value in kwargs.items():
        html = html.replace("{{ " + key + " }}", str(value))
    return html


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    pending = store.list_pending()
    if not pending:
        items = "<p>No actions waiting for approval.</p>"
    else:
        items = "<ul>" + "".join(
            f"<li><a href=\"/approve/{h['id']}\">#{h['id']} — {h['tool']}</a>"
            f" — {h['reason']}</li>"
            for h in pending
        ) + "</ul>"
    return _render("approve.html", title="Pending approvals",
                   body=items, held_id="", tool="", args="", reason="")


@app.get("/pending", response_class=JSONResponse)
def pending() -> dict:
    return {"pending": store.list_pending()}


@app.get("/approve/{held_id}", response_class=HTMLResponse)
def approve_page(held_id: int) -> str:
    held = store.get_held(held_id)
    if held is None:
        raise HTTPException(status_code=404, detail="unknown held action")
    import json as _json
    body = (
        f"<h1>Approve #{held['id']}?</h1>"
        f"<p><b>Tool:</b> {held['tool']}</p>"
        f"<p><b>Args:</b> <code>{_json.dumps(held['args'])}</code></p>"
        f"<p><b>Why held:</b> {held['reason']}</p>"
        f"<p><b>Status:</b> {held['status']}</p>"
        f"<button onclick=\"decide(true)\">Approve</button> "
        f"<button onclick=\"decide(false)\">Reject</button>"
        f"<p id=\"out\"></p>"
    )
    return _render("approve.html", title=f"Approve #{held_id}", body=body,
                   held_id=held_id, tool=held["tool"],
                   args=_json.dumps(held["args"]), reason=held["reason"])


@app.post("/decision")
async def decision(request: Request) -> dict:
    """Accept JSON {id, approved} or form fields (from the HTML page)."""
    held_id = -1
    is_approved = False
    if "application/json" in request.headers.get("content-type", ""):
        payload = await request.json()
        held_id = int(payload.get("id", -1))
        is_approved = bool(payload.get("approved", False))
    else:
        form = await request.form()
        held_id = int(form.get("id", -1))
        is_approved = str(form.get("approved", "")).lower() in (
            "1", "true", "yes", "on")
    if held_id < 0:
        raise HTTPException(status_code=400, detail="missing id")
    row = store.set_decision(held_id, is_approved)
    if row is None:
        raise HTTPException(status_code=404, detail="unknown held action")
    return {"id": row["id"], "status": row["status"]}
