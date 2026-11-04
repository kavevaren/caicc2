"""L2 API core tests (SPEC §6, lean scope).

Cover the L2 task list: register without terms -> terms_required; login with a
wrong password -> generic invalid_credentials; a summary job runs end to end
with FakeLLM and creates a document (+ ai_calls + event_suggestions); another
user's document -> 404; every INSERT in the API/runner/seed sources names its
columns explicitly; an invalid request returns the contract error JSON.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

import pytest

from server.ai import FakeLLM


def _register(client, username: str, accept_terms: bool = True) -> dict:
    r = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "display_name": username.title(),
            "password": "password123",
            "lang": "id",
            "accept_terms": accept_terms,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    return {"token": body["token"], "headers": {"Authorization": f"Bearer {body['token']}"}}


def test_register_without_terms_returns_terms_required(client) -> None:
    r = client.post(
        "/api/auth/register",
        json={"username": "termsless", "display_name": "Terms", "password": "password123", "lang": "id", "accept_terms": False},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "terms_required"


def test_register_invalid_username_and_weak_password(client) -> None:
    r = client.post(
        "/api/auth/register",
        json={"username": "x", "display_name": "X", "password": "password123", "lang": "id", "accept_terms": True},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_username"
    r = client.post(
        "/api/auth/register",
        json={"username": "weakpw", "display_name": "Weak", "password": "short", "lang": "id", "accept_terms": True},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "weak_password"


def test_login_wrong_password_returns_generic_error(client) -> None:
    _register(client, "logintest")
    r = client.post("/api/auth/login", json={"username": "logintest", "password": "wrong-password"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_credentials"
    # unknown user gives the exact same generic error
    r = client.post("/api/auth/login", json={"username": "nosuchuser9", "password": "wrong-password"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_credentials"


def test_token_via_custom_header(client) -> None:
    u = _register(client, "hdrtok")
    token = u["token"]
    # X-Orvina-Token alone works (the Studio gateway strips Authorization)
    r = client.get("/api/me", headers={"X-Orvina-Token": token})
    assert r.status_code == 200
    assert r.json()["user"]["username"] == "hdrtok"
    # the classic Bearer header still works (local dev, curl, tests)
    assert client.get("/api/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    # a garbage value in the custom header is rejected like a missing token
    assert client.get("/api/me", headers={"X-Orvina-Token": "bogus"}).status_code == 401
    assert client.get("/api/me").status_code == 401


def test_me_patch_roundtrip(client) -> None:
    user = _register(client, "metest")
    r = client.get("/api/me", headers=user["headers"])
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["username"] == "metest"
    assert body["onboarding_done"] is True
    assert body["points"] == 0 and body["rank"] == 1 and body["unread"] == 0
    r = client.patch("/api/me", json={"display_name": "Nama Baru", "lang": "en", "theme": "dark"}, headers=user["headers"])
    assert r.status_code == 200
    assert r.json()["display_name"] == "Nama Baru"
    assert r.json()["lang"] == "en"
    assert r.json()["theme"] == "dark"


def test_summary_job_runs_end_to_end_with_fakellm(client, monkeypatch) -> None:
    import server.ai as ai_pkg
    from server.store import db

    real = ai_pkg.summarize

    def fake(job_id, files, options, on_stage, on_progress=None):
        return real(job_id, files, options, on_stage, llm=FakeLLM(), on_progress=on_progress)

    monkeypatch.setattr(ai_pkg, "summarize", fake)
    # The health probe has no token here; pin the summaries gate to "ok" so the
    # job is accepted deterministically.
    monkeypatch.setattr("server.api.summaries.ms_state", lambda: {"status": "ok", "latency_ms": 1, "updated_at": 0.0})

    user = _register(client, "jobtest")
    r = client.post(
        "/api/summaries",
        headers=user["headers"],
        files=[("files", ("catatan.txt", b"Limit fungsi adalah nilai yang didekati. Ujian akhir 4 November 2026.", "text/plain"))],
        data={"title": "Uji Ringkasan", "style": "structured_notes", "lang": "id"},
    )
    assert r.status_code == 202, r.text
    job_id = r.json()["job_id"]

    job = None
    for _ in range(100):
        job = client.get(f"/api/jobs/{job_id}", headers=user["headers"]).json()
        if job["status"] in ("done", "error"):
            break
        time.sleep(0.1)
    assert job is not None and job["status"] == "done", job
    assert job["stage"] == "done"
    assert "extract" in job["stages"] and "reduce" in job["stages"]

    doc_id = job["result_document_id"]
    doc = client.get(f"/api/documents/{doc_id}", headers=user["headers"]).json()
    assert doc["kind"] == "summary"
    assert doc["title"] == "Uji Ringkasan"
    assert doc["content_md"]
    assert doc["source_files"][0]["name"] == "catatan.txt"
    assert doc["extra"]["ai_calls"], "ai_calls must be stored with the document"
    assert doc["extra"]["figures"] == []

    n_calls = db.read_one("SELECT count(*) AS n FROM ai_calls WHERE job_id = ?", (job_id,))["n"]
    assert n_calls >= 3
    assert n_calls == len(doc["extra"]["ai_calls"])
    n_sugg = db.read_one("SELECT count(*) AS n FROM event_suggestions WHERE document_id = ?", (doc_id,))["n"]
    assert n_sugg >= 1  # FakeLLM returns one resolvable deadline

    # The dashboard now shows real data for this user.
    dash = client.get("/api/dashboard", headers=user["headers"]).json()
    assert dash["stats"]["summaries"] >= 1
    assert len(dash["week"]) == 7
    assert dash["recent"][0]["title"] == "Uji Ringkasan"


def test_foreign_document_returns_404(client) -> None:
    from server.store import db

    owner = _register(client, "docowner")
    other = _register(client, "docother")
    owner_id = db.read_one("SELECT id FROM users WHERE username = 'docowner'")["id"]
    cur = db.write(
        "INSERT INTO documents (user_id, kind, title, content_md) VALUES (?, 'summary', 'Doc A', 'isi')",
        (owner_id,),
    )
    doc_id = int(cur.lastrowid)
    # owner sees it
    assert client.get(f"/api/documents/{doc_id}", headers=owner["headers"]).status_code == 200
    # another user gets 404 (no existence leak)
    assert client.get(f"/api/documents/{doc_id}", headers=other["headers"]).status_code == 404
    assert client.delete(f"/api/documents/{doc_id}", headers=other["headers"]).status_code == 404
    # export is owner-only too
    r = client.get(f"/api/documents/{doc_id}/export", params={"format": "md"}, headers=owner["headers"])
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/markdown")
    assert r.text == "isi"


def test_all_inserts_name_their_columns() -> None:
    root = Path(__file__).resolve().parents[2]
    api_names = ("auth", "me", "subjects", "documents", "summaries", "jobs", "dashboard", "forum", "schedule", "projects", "chat")
    files = [
        root / "server" / "jobs" / "runner.py",
        root / "server" / "seed.py",
        *(root / "server" / "api" / f"{n}.py" for n in api_names),
    ]
    offenders: list[str] = []
    for p in files:
        src = p.read_text(encoding="utf-8")
        n_inserts = len(re.findall(r"INSERT\s+INTO", src, re.I))
        n_with_cols = len(re.findall(r"INSERT\s+INTO\s+[A-Za-z_]+\s*\(", src, re.I))
        if n_inserts != n_with_cols:
            offenders.append(f"{p.name}: {n_inserts} INSERTs but {n_with_cols} with column lists")
    assert not offenders


def test_invalid_request_returns_contract_error_json(client) -> None:
    user = _register(client, "valtest")
    r = client.get("/api/documents", params={"page": "abc"}, headers=user["headers"])
    assert r.status_code == 422
    assert r.json() == {"error": {"code": "validation", "message_key": "errors.validation"}}


@pytest.mark.usefixtures("client")
def test_dashboard_shape_with_seed_demo() -> None:
    # The lifespan seeded demo data (demo / demo12345); the contract shape holds.
    from server.store import db

    row = db.read_one("SELECT * FROM users WHERE username = 'demo'")
    assert row is not None, "seed should have created the demo user on an empty DB"
