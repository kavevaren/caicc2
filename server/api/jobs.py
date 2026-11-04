"""Jobs router (SPEC §6 + FEAT-02).

GET /api/jobs/{id} — owner-only polling channel.
GET /api/jobs?active=1 — FEAT-02: the list the floating tray polls on app
load (queued/running + finished in the last 5 minutes) so progress survives
a refresh. Percent is read from jobs.percent (persisted by the runner).
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query

from server.api.deps import get_current_user
from server.api.errors import APIError
from server.jobs import runner
from server.store import db

router = APIRouter(tags=["Jobs"])

_RECENT_WINDOW = "5 minutes"  # finished jobs still shown to the tray


def _job_payload(row: dict, job_id: str | None = None) -> dict:
    stages = json.loads(row["stages_json"] or "[]")
    progress = runner.get_progress(job_id or row["id"]) if row["status"] in ("queued", "running") else None
    percent = 100 if row["status"] == "done" else max(int(row["percent"]), runner._percent(row["stage"], progress))
    return {
        "id": row["id"],
        "kind": row["kind"],
        "status": row["status"],
        "stage": row["stage"],
        "stages": stages,
        "label": row["label"],
        "notes": row["notes"],
        "result_document_id": row["result_document_id"],
        "error_code": row["error_code"],
        "progress": {"done": progress[0], "total": progress[1]} if progress else None,
        "percent": percent,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


@router.get("/api/jobs")
def list_jobs(
    active: bool = Query(default=True),
    user: dict = Depends(get_current_user),
) -> dict:
    """FEAT-02 tray feed: active jobs + those finished in the last 5 minutes."""
    if not active:
        rows = db.read(
            "SELECT * FROM jobs WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT 20",
            (user["id"],),
        )
    else:
        rows = db.read(
            "SELECT * FROM jobs WHERE user_id = ? AND ("
            " status IN ('queued', 'running')"
            " OR (status IN ('done', 'error') AND updated_at >= strftime('%Y-%m-%dT%H:%M:%fZ', 'now', ?))"
            ") ORDER BY created_at DESC, id DESC LIMIT 20",
            (user["id"], f"-{_RECENT_WINDOW}"),
        )
    return {"items": [_job_payload(r) for r in rows]}


@router.get("/api/jobs/{job_id}")
def get_job(job_id: str, user: dict = Depends(get_current_user)) -> dict:
    row = db.read_one(
        "SELECT * FROM jobs WHERE id = ? AND user_id = ?",
        (job_id, user["id"]),
    )
    if row is None:
        raise APIError("not_found", 404)
    return _job_payload(row, job_id)
