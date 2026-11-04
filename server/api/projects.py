"""Projects router (L7 task 3): owner-only folders of summaries.

CRUD + add/remove documents + reorder + .md export. Everything is owner-only:
a foreign project or a foreign document is a 404 (the same rule as documents).
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field

from server.api.deps import get_current_user
from server.api.errors import APIError
from server.store import db

router = APIRouter(tags=["Projects (L7)"])


class CreateProjectRequest(BaseModel):
    title: str = Field(min_length=1, max_length=150)


class PatchProjectRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=150)


class AddDocumentRequest(BaseModel):
    document_id: int


class OrderRequest(BaseModel):
    document_ids: list[int] = Field(min_length=1)


def _get_owned(proj_id: int, user: dict) -> dict:
    row = db.read_one("SELECT * FROM projects WHERE id = ? AND user_id = ?", (proj_id, user["id"]))
    if row is None:
        raise APIError("not_found", 404)
    return dict(row)


def _doc_owned(doc_id: int, user: dict) -> dict:
    row = db.read_one(
        "SELECT d.*, s.name AS subject_name FROM documents d"
        " LEFT JOIN subjects s ON s.id = d.subject_id WHERE d.id = ? AND d.user_id = ?",
        (doc_id, user["id"]),
    )
    if row is None:
        raise APIError("not_found", 404)
    return dict(row)


def _subject_of(proj_id: int) -> str | None:
    """The dominant subject among the project's documents (null when none)."""
    row = db.read_one(
        "SELECT s.name AS name FROM project_documents pd"
        " JOIN documents d ON d.id = pd.document_id"
        " JOIN subjects s ON s.id = d.subject_id"
        " WHERE pd.project_id = ? GROUP BY s.name ORDER BY COUNT(*) DESC, s.name ASC LIMIT 1",
        (proj_id,),
    )
    return row["name"] if row else None


def _project(proj_id: int, user: dict) -> dict:
    p = _get_owned(proj_id, user)
    n = db.read_one("SELECT COUNT(*) AS n FROM project_documents WHERE project_id = ?", (proj_id,))["n"]
    return {
        "id": p["id"],
        "title": p["title"],
        "subject": _subject_of(proj_id),
        "doc_count": n,
        "created_at": p["created_at"],
        "updated_at": p["updated_at"],
    }


def _docs_of(proj_id: int, user: dict) -> list[dict]:
    rows = db.read(
        "SELECT d.id, d.kind, d.title, d.subject_id, s.name AS subject_name, d.content_md,"
        " pd.position, pd.added_at"
        " FROM project_documents pd JOIN documents d ON d.id = pd.document_id"
        " LEFT JOIN subjects s ON s.id = d.subject_id"
        " WHERE pd.project_id = ? AND d.user_id = ? ORDER BY pd.position, pd.added_at",
        (proj_id, user["id"]),
    )
    return [
        {
            "id": r["id"],
            "kind": r["kind"],
            "title": r["title"],
            "subject": r["subject_name"],
            "position": r["position"],
            "added_at": r["added_at"],
        }
        for r in rows
    ]


@router.get("/api/projects")
def list_projects(user: dict = Depends(get_current_user)) -> dict:
    rows = db.read(
        "SELECT p.id, p.title, p.updated_at, (SELECT COUNT(*) FROM project_documents pd"
        " WHERE pd.project_id = p.id) AS n FROM projects p"
        " WHERE p.user_id = ? ORDER BY p.updated_at DESC, p.id DESC",
        (user["id"],),
    )
    items = []
    for r in rows:
        items.append(
            {
                "id": r["id"],
                "title": r["title"],
                "subject": _subject_of(r["id"]),
                "doc_count": r["n"],
                "updated_at": r["updated_at"],
            }
        )
    return {"items": items}


@router.post("/api/projects", status_code=201)
def create_project(body: CreateProjectRequest, user: dict = Depends(get_current_user)) -> dict:
    title = body.title.strip()
    if not 1 <= len(title) <= 150:
        raise APIError("validation", 422)
    cur = db.write(
        "INSERT INTO projects (user_id, title) VALUES (?, ?)",
        (user["id"], title),
    )
    return _project(cur.lastrowid, user)


@router.get("/api/projects/{proj_id}")
def get_project(proj_id: int, user: dict = Depends(get_current_user)) -> dict:
    p = _project(proj_id, user)
    p["docs"] = _docs_of(proj_id, user)
    return p


@router.patch("/api/projects/{proj_id}")
def patch_project(proj_id: int, body: PatchProjectRequest, user: dict = Depends(get_current_user)) -> dict:
    _get_owned(proj_id, user)  # 404 if not the owner
    if body.title is None:
        raise APIError("validation", 422)
    title = body.title.strip()
    if not 1 <= len(title) <= 150:
        raise APIError("validation", 422)
    db.write(
        "UPDATE projects SET title = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ? AND user_id = ?",
        (title, proj_id, user["id"]),
    )
    return _project(proj_id, user)


@router.delete("/api/projects/{proj_id}", status_code=204)
def delete_project(proj_id: int, user: dict = Depends(get_current_user)) -> Response:
    _get_owned(proj_id, user)  # 404 if not the owner
    db.write("DELETE FROM projects WHERE id = ? AND user_id = ?", (proj_id, user["id"]))
    return Response(status_code=204)


@router.post("/api/projects/{proj_id}/documents", status_code=201)
def add_document(proj_id: int, body: AddDocumentRequest, user: dict = Depends(get_current_user)) -> dict:
    _get_owned(proj_id, user)  # 404 for a foreign project
    doc = _doc_owned(body.document_id, user)  # 404 for a foreign document
    # Idempotent: adding the same summary again keeps the old position.
    existing = db.read_one(
        "SELECT 1 AS x FROM project_documents WHERE project_id = ? AND document_id = ?",
        (proj_id, body.document_id),
    )
    if existing is None:
        pos = db.read_one("SELECT COALESCE(MAX(position), -1) + 1 AS p FROM project_documents WHERE project_id = ?", (proj_id,))["p"]
        db.write(
            "INSERT INTO project_documents (project_id, document_id, position) VALUES (?, ?, ?)",
            (proj_id, body.document_id, pos),
        )
        db.write(
            "UPDATE projects SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?",
            (proj_id,),
        )
    return _project(proj_id, user) | {"document": {"id": doc["id"], "title": doc["title"]}}


@router.delete("/api/projects/{proj_id}/documents/{doc_id}", status_code=204)
def remove_document(proj_id: int, doc_id: int, user: dict = Depends(get_current_user)) -> Response:
    _get_owned(proj_id, user)  # 404 for a foreign project
    cur = db.write(
        "DELETE FROM project_documents WHERE project_id = ? AND document_id = ?",
        (proj_id, doc_id),
    )
    if cur.rowcount == 0:
        raise APIError("not_found", 404)  # not in this project
    db.write(
        "UPDATE projects SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?",
        (proj_id,),
    )
    return Response(status_code=204)


@router.post("/api/projects/{proj_id}/order")
def reorder_documents(proj_id: int, body: OrderRequest, user: dict = Depends(get_current_user)) -> dict:
    """The given ids take the given order; the remaining documents of the
    project follow in their old position order (deterministic rewrite)."""
    _get_owned(proj_id, user)  # 404 for a foreign project
    rows = db.read(
        "SELECT document_id, position FROM project_documents WHERE project_id = ? ORDER BY position, added_at",
        (proj_id,),
    )
    mine = [r["document_id"] for r in rows]
    wanted = [i for i in body.document_ids if i in mine]
    rest = [i for i in mine if i not in wanted]
    order = wanted + rest
    for pos, doc_id in enumerate(order):
        db.write(
            "UPDATE project_documents SET position = ? WHERE project_id = ? AND document_id = ?",
            (pos, proj_id, doc_id),
        )
    db.write(
        "UPDATE projects SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?",
        (proj_id,),
    )
    return {"docs": _docs_of(proj_id, user)}


def _slug(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "proyek"


@router.get("/api/projects/{proj_id}/export")
def export_project(proj_id: int, user: dict = Depends(get_current_user), format: str = Query(default="md")) -> Response:
    # Lean: only the .md text export (the contract's zip/html variants are a scope cut).
    if format != "md":
        raise APIError("not_implemented", 501)
    p = _get_owned(proj_id, user)
    rows = db.read(
        "SELECT d.title, d.content_md FROM project_documents pd JOIN documents d ON d.id = pd.document_id"
        " WHERE pd.project_id = ? AND d.user_id = ? ORDER BY pd.position, pd.added_at",
        (proj_id, user["id"]),
    )
    parts = [f"# {p['title']}"]
    for r in rows:
        parts.append(f"## {r['title']}\n\n{r['content_md']}")
    return Response(
        content="\n\n".join(parts),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{_slug(p["title"])}.md"'},
    )
