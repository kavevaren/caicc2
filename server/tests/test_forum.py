"""L6 forum tests (SPEC §8.6, lean scope).

Cover the L6 task list: title must be 10-150 chars (422 title_length on POST
and PATCH), edits/deletes are owner-only (foreign = 404, soft delete), and
list search goes through FTS5 (a token in the body is found; a bogus token
is not).
"""
from __future__ import annotations

from server.store import db


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


def _subject(client, headers: dict, name: str) -> int:
    r = client.post("/api/subjects", json={"name": name}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_question_title_length_rule(client) -> None:
    u = _register(client, "forum1")
    sid = _subject(client, u["headers"], "L6 subjek satu")
    # 9 chars -> 422 title_length
    r = client.post(
        "/api/questions",
        data={"title": "pendek 9?", "body_md": "isi", "subject_id": str(sid)},
        headers=u["headers"],
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "title_length"
    # 151 chars -> 422 title_length
    r = client.post(
        "/api/questions",
        data={"title": "T" * 151, "body_md": "isi", "subject_id": str(sid)},
        headers=u["headers"],
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "title_length"
    # valid 10 chars -> 201, shape per contract
    r = client.post(
        "/api/questions",
        data={"title": "Foton apa itu?", "body_md": "Penjelasan singkat tentang foton.", "subject_id": str(sid)},
        headers=u["headers"],
    )
    assert r.status_code == 201, r.text
    q = r.json()
    assert q["title"] == "Foton apa itu?"
    assert q["status"] == "open"
    assert q["answers_count"] == 0
    assert q["subject_id"] == sid
    assert q["author"]["username"] == "forum1"
    # PATCH to a too-short title -> 422 title_length
    r = client.patch(f"/api/questions/{q['id']}", json={"title": "pendek"}, headers=u["headers"])
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "title_length"
    # unknown subject -> 422 validation
    r = client.post(
        "/api/questions",
        data={"title": "Subjek salah ya?", "body_md": "isi", "subject_id": "99999"},
        headers=u["headers"],
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation"


def test_question_owner_only_and_soft_delete(client) -> None:
    u = _register(client, "forum2")
    sid = _subject(client, u["headers"], "L6 subjek dua")
    r = client.post(
        "/api/questions",
        data={"title": "Momentum operator?", "body_md": "Basis [p, x] = ?", "subject_id": str(sid)},
        headers=u["headers"],
    )
    qid = r.json()["id"]
    other = _register(client, "forum3")
    # foreign user: PATCH / DELETE question -> 404; GET still 200
    assert client.patch(f"/api/questions/{qid}", json={"title": "Hacked title???"}, headers=other["headers"]).status_code == 404
    assert client.delete(f"/api/questions/{qid}", headers=other["headers"]).status_code == 404
    assert client.get(f"/api/questions/{qid}", headers=other["headers"]).status_code == 200
    # answer flow: other user may answer; only the author may edit/delete the answer
    r = client.post(f"/api/questions/{qid}/answers", data={"body_md": "[p, x] = -i hbar."}, headers=other["headers"])
    assert r.status_code == 201, r.text
    aid = r.json()["id"]
    # question flips to answered
    assert client.get(f"/api/questions/{qid}", headers=u["headers"]).json()["status"] == "answered"
    assert client.patch(f"/api/answers/{aid}", json={"body_md": "salah orang"}, headers=u["headers"]).status_code == 404
    assert client.delete(f"/api/answers/{aid}", headers=u["headers"]).status_code == 404
    assert client.patch(f"/api/answers/{aid}", json={"body_md": "[p, x] = -i hbar (edited)."}, headers=other["headers"]).status_code == 200
    # empty answer body -> 422
    assert client.post(f"/api/questions/{qid}/answers", data={"body_md": "   "}, headers=other["headers"]).status_code == 422
    # delete own answer -> 204, question back to open (no live answers left)
    assert client.delete(f"/api/answers/{aid}", headers=other["headers"]).status_code == 204
    assert client.get(f"/api/questions/{qid}", headers=u["headers"]).json()["status"] == "open"
    # owner deletes the question -> 204 soft; gone for everyone
    assert client.delete(f"/api/questions/{qid}", headers=u["headers"]).status_code == 204
    assert client.get(f"/api/questions/{qid}", headers=u["headers"]).status_code == 404
    assert client.get(f"/api/questions/{qid}", headers=other["headers"]).status_code == 404
    assert client.delete(f"/api/questions/{qid}", headers=u["headers"]).status_code == 404
    row = db.read_one("SELECT deleted FROM questions WHERE id = ?", (qid,))
    assert row["deleted"] == 1


def test_question_fts_search_and_filters(client) -> None:
    u = _register(client, "forum4")
    sid = _subject(client, u["headers"], "L6 subjek tiga")
    client.post(
        "/api/questions",
        data={"title": "Spektra atomik quanticosmos9", "body_md": "Garis quanticosmos9 pada hidrogen.", "subject_id": str(sid)},
        headers=u["headers"],
    )
    client.post(
        "/api/questions",
        data={"title": "Tunnel barrier quanticosmos8", "body_md": "Koefisien transmisi.", "subject_id": str(sid)},
        headers=u["headers"],
    )
    # FTS: a body token is found
    r = client.get("/api/questions", params={"q": "quanticosmos9"}, headers=u["headers"])
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["title"].startswith("Spektra atomik")
    assert r.json()["total"] == 1
    # bogus token -> none
    r = client.get("/api/questions", params={"q": "zzzznotthere"}, headers=u["headers"])
    assert r.json()["items"] == []
    # subject filter
    r = client.get("/api/questions", params={"subject": sid}, headers=u["headers"])
    assert r.json()["total"] == 2
    # unanswered sort puts the question with no answers first
    r = client.get("/api/questions", params={"sort": "unanswered"}, headers=u["headers"])
    body = r.json()
    assert all(it["answers_count"] == 0 for it in body["items"])
    assert body["page"] == 1 and body["pages"] >= 1
    # FTS query chars cannot break the MATCH (injection-safe)
    r = client.get("/api/questions", params={"q": '" OR 1=1 --'}, headers=u["headers"])
    assert r.status_code == 200
