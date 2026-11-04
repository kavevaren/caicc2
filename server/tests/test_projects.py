"""L7 task 3 tests: projects CRUD, ownership, ordering, .md export.

Cover the task rules: a foreign project or a foreign document is a 404,
reordering is a deterministic rewrite, adding is idempotent, and deleting a
project keeps its documents.
"""
from __future__ import annotations

import re
from pathlib import Path

from server.store import db

ROOT = Path(__file__).resolve().parents[2]


def _register(client, username: str) -> dict:
    r = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "display_name": username.title(),
            "password": "password123",
            "lang": "id",
            "accept_terms": True,
        },
    )
    assert r.status_code == 201, r.text
    token = r.json()["token"]
    return {"token": token, "headers": {"Authorization": f"Bearer {token}"}}


def _user_id(client, username: str) -> int:
    return db.read_one("SELECT id FROM users WHERE username = ?", (username,))["id"]


def _make_doc(client, username: str, title: str, content: str) -> int:
    uid = _user_id(client, username)
    cur = db.write(
        "INSERT INTO documents (user_id, kind, title, content_md) VALUES (?, 'summary', ?, ?)",
        (uid, title, content),
    )
    return cur.lastrowid


def test_projects_owner_only_crud(client) -> None:
    u = _register(client, "proj1")
    u2 = _register(client, "proj2")
    # create: 201, blank title -> 422
    r = client.post("/api/projects", json={"title": "Persiapan UTS"}, headers=u["headers"])
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["title"] == "Persiapan UTS" and p["doc_count"] == 0
    assert client.post("/api/projects", json={"title": "  "}, headers=u["headers"]).status_code == 422
    # list: owner sees it, the other user does not
    items = client.get("/api/projects", headers=u["headers"]).json()["items"]
    assert [i["title"] for i in items] == ["Persiapan UTS"]
    assert client.get("/api/projects", headers=u2["headers"]).json()["items"] == []
    # foreign project -> 404 on get / patch / delete
    assert client.get(f"/api/projects/{p['id']}", headers=u2["headers"]).status_code == 404
    assert client.patch(f"/api/projects/{p['id']}", json={"title": "Maling"}, headers=u2["headers"]).status_code == 404
    assert client.delete(f"/api/projects/{p['id']}", headers=u2["headers"]).status_code == 404
    # rename: 200, blank -> 422
    r = client.patch(f"/api/projects/{p['id']}", json={"title": "UTS Kalkulus"}, headers=u["headers"])
    assert r.status_code == 200 and r.json()["title"] == "UTS Kalkulus"
    assert client.patch(f"/api/projects/{p['id']}", json={"title": ""}, headers=u["headers"]).status_code == 422
    assert client.patch(f"/api/projects/{p['id']}", json={}, headers=u["headers"]).status_code == 422
    # add a document: own -> 201 idempotent, foreign -> 404 (both directions)
    doc_a = _make_doc(client, "proj1", "Limit dan kekontinuan", "# A\n\nisi a")
    doc_b = _make_doc(client, "proj2", "Hukum Newton", "# B\n\nisi b")
    r = client.post(f"/api/projects/{p['id']}/documents", json={"document_id": doc_a}, headers=u["headers"])
    assert r.status_code == 201, r.text
    assert r.json()["doc_count"] == 1 and r.json()["document"]["id"] == doc_a
    # idempotent: same doc again -> 201, still one entry
    r = client.post(f"/api/projects/{p['id']}/documents", json={"document_id": doc_a}, headers=u["headers"])
    assert r.status_code == 201 and r.json()["doc_count"] == 1
    # foreign document -> 404 (u2 tries to add u's doc, and u tries u2's doc)
    assert client.post(f"/api/projects/{p['id']}/documents", json={"document_id": doc_b}, headers=u2["headers"]).status_code == 404
    p2 = client.post("/api/projects", json={"title": "Fisika"}, headers=u2["headers"]).json()
    assert client.post(f"/api/projects/{p2['id']}/documents", json={"document_id": doc_a}, headers=u2["headers"]).status_code == 404
    # detail: docs in position order, dominant subject (none yet)
    d = client.get(f"/api/projects/{p['id']}", headers=u["headers"]).json()
    assert [x["id"] for x in d["docs"]] == [doc_a]
    # remove document: 204 then 404 (foreign project too)
    assert client.delete(f"/api/projects/{p['id']}/documents/{doc_a}", headers=u2["headers"]).status_code == 404
    assert client.delete(f"/api/projects/{p['id']}/documents/{doc_a}", headers=u["headers"]).status_code == 204
    assert client.delete(f"/api/projects/{p['id']}/documents/{doc_a}", headers=u["headers"]).status_code == 404
    # delete project: 204 then 404, and the document survives
    assert client.delete(f"/api/projects/{p['id']}", headers=u["headers"]).status_code == 204
    assert client.get(f"/api/projects/{p['id']}", headers=u["headers"]).status_code == 404
    assert db.read_one("SELECT id FROM documents WHERE id = ?", (doc_a,)) is not None
    # the foreign user's project still exists for u2
    assert client.get(f"/api/projects/{p2['id']}", headers=u2["headers"]).status_code == 200


def test_project_ordering(client) -> None:
    u = _register(client, "proj3")
    p = client.post("/api/projects", json={"title": "Urutan"}, headers=u["headers"]).json()
    d1 = _make_doc(client, "proj3", "Satu", "# 1")
    d2 = _make_doc(client, "proj3", "Dua", "# 2")
    d3 = _make_doc(client, "proj3", "Tiga", "# 3")
    for d in (d1, d2, d3):
        assert client.post(f"/api/projects/{p['id']}/documents", json={"document_id": d}, headers=u["headers"]).status_code == 201
    # full reorder: 3, 2, 1
    r = client.post(f"/api/projects/{p['id']}/order", json={"document_ids": [d3, d2, d1]}, headers=u["headers"])
    assert r.status_code == 200
    assert [x["id"] for x in r.json()["docs"]] == [d3, d2, d1]
    assert [x["position"] for x in r.json()["docs"]] == [0, 1, 2]
    # partial list: the given id moves first, the rest keeps the old order
    r = client.post(f"/api/projects/{p['id']}/order", json={"document_ids": [d1]}, headers=u["headers"])
    assert [x["id"] for x in r.json()["docs"]] == [d1, d3, d2]
    # unknown ids are ignored, not an error
    r = client.post(f"/api/projects/{p['id']}/order", json={"document_ids": [999999, d2]}, headers=u["headers"])
    assert r.status_code == 200
    assert [x["id"] for x in r.json()["docs"]] == [d2, d1, d3]
    # empty list -> 422; foreign project -> 404
    assert client.post(f"/api/projects/{p['id']}/order", json={"document_ids": []}, headers=u["headers"]).status_code == 422
    u2 = _register(client, "proj4")
    assert client.post(f"/api/projects/{p['id']}/order", json={"document_ids": [d1]}, headers=u2["headers"]).status_code == 404
    # the order is what the detail endpoint returns
    d = client.get(f"/api/projects/{p['id']}", headers=u["headers"]).json()
    assert [x["id"] for x in d["docs"]] == [d2, d1, d3]


def test_project_export_md(client) -> None:
    u = _register(client, "proj5")
    p = client.post("/api/projects", json={"title": "Ekspor Uji"}, headers=u["headers"]).json()
    d1 = _make_doc(client, "proj5", "Bab 1", "isi satu")
    d2 = _make_doc(client, "proj5", "Bab 2", "isi dua")
    for d in (d1, d2):
        client.post(f"/api/projects/{p['id']}/documents", json={"document_id": d}, headers=u["headers"])
    # export follows the position order: title + one ## per document
    r = client.get(f"/api/projects/{p['id']}/export?format=md", headers=u["headers"])
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/markdown")
    body = r.text
    assert body.startswith("# Ekspor Uji")
    assert body.index("## Bab 1") < body.index("## Bab 2")
    assert "isi satu" in body and "isi dua" in body
    # reordering changes the export order
    client.post(f"/api/projects/{p['id']}/order", json={"document_ids": [d2, d1]}, headers=u["headers"])
    body = client.get(f"/api/projects/{p['id']}/export?format=md", headers=u["headers"]).text
    assert body.index("## Bab 2") < body.index("## Bab 1")
    # other formats stay 501; a foreign project is a 404
    assert client.get(f"/api/projects/{p['id']}/export?format=zip", headers=u["headers"]).status_code == 501
    u2 = _register(client, "proj6")
    assert client.get(f"/api/projects/{p['id']}/export?format=md", headers=u2["headers"]).status_code == 404
    # deleting a document removes it from the export
    client.delete(f"/api/projects/{p['id']}/documents/{d1}", headers=u["headers"])
    body = client.get(f"/api/projects/{p['id']}/export?format=md", headers=u["headers"]).text
    assert "Bab 1" not in body and "## Bab 2" in body


def test_projects_inserts_use_explicit_column_lists() -> None:
    src = (ROOT / "server" / "api" / "projects.py").read_text(encoding="utf-8")
    n_inserts = len(re.findall(r"INSERT\s+INTO", src, re.I))
    n_with_cols = len(re.findall(r"INSERT\s+INTO\s+[A-Za-z_]+\s*\(", src, re.I))
    assert n_inserts >= 2
    assert n_inserts == n_with_cols, "every INSERT must name its columns"
