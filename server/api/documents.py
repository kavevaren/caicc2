"""Documents router (SPEC §6): the Perpustakaan — list/search, get, patch,
delete, export. Everything is owner-only: a foreign document is a 404."""
from __future__ import annotations

import json
import re

from fastapi import APIRouter, Depends, Query, Response

from server.api.deps import get_current_user
from server.api.errors import APIError
from server.store import db

router = APIRouter(tags=["Summaries (F1)"])

PAGE_SIZE = 20


def _get_owned(doc_id: int, user: dict) -> dict:
    row = db.read_one(
        "SELECT d.*, s.name AS subject_name,"
        " (SELECT p.id FROM project_documents pd JOIN projects p ON p.id = pd.project_id"
        "  WHERE pd.document_id = d.id ORDER BY p.created_at, p.id LIMIT 1) AS project_id"
        " FROM documents d LEFT JOIN subjects s ON s.id = d.subject_id"
        " WHERE d.id = ? AND d.user_id = ?",
        (doc_id, user["id"]),
    )
    if row is None:
        raise APIError("not_found", 404)
    return dict(row)


def _doc(row: dict) -> dict:
    return {
        "id": row["id"],
        "kind": row["kind"],
        "title": row["title"],
        "subject_id": row["subject_id"],
        "subject": row.get("subject_name"),
        "project": row.get("project_name"),
        "project_id": row.get("project_id"),
        "source_files": json.loads(row["source_files_json"] or "[]"),
        "content_md": row["content_md"],
        "extra": json.loads(row["extra_json"] or "{}"),
        "created_at": row["created_at"],
        "updated_at": None,
    }


@router.get("/api/documents")
def list_documents(
    user: dict = Depends(get_current_user),
    kind: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=100),
    subject: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
) -> dict:
    where = ["d.user_id = ?"]
    params: list = [user["id"]]
    if q:
        where.append("(d.title LIKE ? OR d.content_md LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    if subject is not None:
        where.append("d.subject_id = ?")
        params.append(subject)
    if kind in ("summary", "transcript"):
        where.append("d.kind = ?")
        params.append(kind)
    where_sql = " AND ".join(where)
    total = db.read_one(f"SELECT count(*) AS n FROM documents d WHERE {where_sql}", tuple(params))["n"]
    rows = db.read(
        "SELECT d.*, s.name AS subject_name,"
        " (SELECT p.title FROM project_documents pd JOIN projects p ON p.id = pd.project_id"
        "  WHERE pd.document_id = d.id ORDER BY p.created_at, p.id LIMIT 1) AS project_name"
        " FROM documents d LEFT JOIN subjects s ON s.id = d.subject_id"
        f" WHERE {where_sql} ORDER BY d.created_at DESC, d.id DESC LIMIT ? OFFSET ?",
        (*params, PAGE_SIZE, (page - 1) * PAGE_SIZE),
    )
    return {"items": [_doc(dict(r)) for r in rows], "total": int(total), "page": page, "pages": (int(total) + PAGE_SIZE - 1) // PAGE_SIZE}


@router.get("/api/documents/{doc_id}")
def get_document(doc_id: int, user: dict = Depends(get_current_user)) -> dict:
    return _doc(_get_owned(doc_id, user))


@router.patch("/api/documents/{doc_id}")
def patch_document(doc_id: int, body: dict, user: dict = Depends(get_current_user)) -> dict:
    _get_owned(doc_id, user)  # ownership (404 if not)
    sets: list[str] = []
    params: list = []
    if "title" in body:
        title = str(body["title"])
        if not 1 <= len(title) <= 150:
            raise APIError("validation", 422)
        sets.append("title = ?")
        params.append(title)
    if "subject_id" in body:
        sid = body["subject_id"]
        valid = sid is None or (
            isinstance(sid, int) and db.read_one("SELECT id FROM subjects WHERE id = ?", (sid,)) is not None
        )
        if not valid:
            raise APIError("validation", 422)
        sets.append("subject_id = ?")
        params.append(sid)
    if not sets:
        raise APIError("validation", 422)
    params.append(doc_id)
    db.write(f"UPDATE documents SET {', '.join(sets)} WHERE id = ?", tuple(params))
    return _doc(_get_owned(doc_id, user))


@router.delete("/api/documents/{doc_id}", status_code=204)
def delete_document(doc_id: int, user: dict = Depends(get_current_user)) -> Response:
    _get_owned(doc_id, user)  # ownership (404 if not)
    db.write("DELETE FROM documents WHERE id = ? AND user_id = ?", (doc_id, user["id"]))
    return Response(status_code=204)


def _slug(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "ringkasan"


@router.get("/api/documents/{doc_id}/export")
def export_document(doc_id: int, user: dict = Depends(get_current_user), format: str = Query(default="md")) -> Response:
    # Lean: only the .md text export (the contract's zip/html variants are a scope cut).
    if format != "md":
        raise APIError("not_implemented", 501)
    doc = _get_owned(doc_id, user)
    return Response(
        content=doc["content_md"],
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{_slug(doc["title"])}.md"'},
    )
