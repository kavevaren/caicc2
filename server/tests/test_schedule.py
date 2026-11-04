"""L5 schedule tests (SPEC §8.5, lean scope).

Cover the L5 task list: end_at must be strictly after start_at (422
end_before_start on POST and PATCH, default end = start + 1 h), every INSERT
in the schedule router names its columns explicitly, and accepting a pending
suggestion creates an 'ai' event and clears it from the pending list.
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


def test_create_event_default_end_and_range_rule(client) -> None:
    u = _register(client, "sched1")
    # default end_at = start + 1 h
    r = client.post(
        "/api/events",
        json={"title": "UTS Fisika", "start_at": "2026-11-05T13:00:00"},
        headers=u["headers"],
    )
    assert r.status_code == 201, r.text
    ev = r.json()
    assert ev["source"] == "manual"
    assert ev["start_at"].startswith("2026-11-05T06:00:00")  # 13:00 WIB -> 06:00 UTC
    assert ev["end_at"].startswith("2026-11-05T07:00:00")  # +1 h
    # end_at == start_at -> 422 end_before_start
    r = client.post(
        "/api/events",
        json={"title": "Sama", "start_at": "2026-11-05T13:00:00", "end_at": "2026-11-05T13:00:00"},
        headers=u["headers"],
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "end_before_start"
    # end_at before start_at -> 422 end_before_start
    r = client.post(
        "/api/events",
        json={"title": "Terbalik", "start_at": "2026-11-05T13:00:00", "end_at": "2026-11-05T12:00:00"},
        headers=u["headers"],
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "end_before_start"
    # PATCH into an invalid range -> 422
    r = client.patch(f"/api/events/{ev['id']}", json={"end_at": "2026-11-05T12:00:00"}, headers=u["headers"])
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "end_before_start"
    # list default range (today..+30d) includes the event
    r = client.get("/api/events", headers=u["headers"])
    assert r.status_code == 200
    assert any(e["id"] == ev["id"] for e in r.json()["items"])
    # .ics is RFC 5545
    r = client.get(f"/api/events/{ev['id']}.ics", headers=u["headers"])
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/calendar")
    body = r.text
    assert body.startswith("BEGIN:VCALENDAR")
    assert "BEGIN:VEVENT" in body and "SUMMARY:UTS Fisika" in body and body.rstrip().endswith("END:VCALENDAR")
    # delete -> 204, then 404
    r = client.delete(f"/api/events/{ev['id']}", headers=u["headers"])
    assert r.status_code == 204
    r = client.delete(f"/api/events/{ev['id']}", headers=u["headers"])
    assert r.status_code == 404


def test_schedule_inserts_use_explicit_column_lists() -> None:
    src = (ROOT / "server" / "api" / "schedule.py").read_text(encoding="utf-8")
    n_inserts = len(re.findall(r"INSERT\s+INTO", src, re.I))
    n_with_cols = len(re.findall(r"INSERT\s+INTO\s+[A-Za-z_]+\s*\(", src, re.I))
    assert n_inserts >= 2
    assert n_inserts == n_with_cols, "every INSERT must name its columns"


def test_todos_owner_only(client) -> None:
    u = _register(client, "todo1")
    u2 = _register(client, "todo2")
    # empty list, then create
    assert client.get("/api/todos", headers=u["headers"]).json()["items"] == []
    r = client.post("/api/todos", json={"title": "Baca bab 4", "due_date": "2026-11-10"}, headers=u["headers"])
    assert r.status_code == 201, r.text
    todo = r.json()
    assert todo["done"] is False and todo["due_date"] == "2026-11-10"
    # blank title -> 422, bad due_date -> 422
    assert client.post("/api/todos", json={"title": "  "}, headers=u["headers"]).status_code == 422
    assert client.post("/api/todos", json={"title": "X", "due_date": "10/11/2026"}, headers=u["headers"]).status_code == 422
    # patch: toggle done + change title (owner)
    r = client.patch(f"/api/todos/{todo['id']}", json={"done": True, "title": "Baca bab 4 (selesai)"}, headers=u["headers"])
    assert r.status_code == 200
    assert r.json()["done"] is True and r.json()["title"] == "Baca bab 4 (selesai)"
    # list order: pending first
    client.post("/api/todos", json={"title": "Latihan 1"}, headers=u["headers"])
    items = client.get("/api/todos", headers=u["headers"]).json()["items"]
    assert [t["title"] for t in items] == ["Latihan 1", "Baca bab 4 (selesai)"]
    # another user sees an empty list and cannot touch the todo
    assert client.get("/api/todos", headers=u2["headers"]).json()["items"] == []
    assert client.patch(f"/api/todos/{todo['id']}", json={"done": False}, headers=u2["headers"]).status_code == 404
    assert client.delete(f"/api/todos/{todo['id']}", headers=u2["headers"]).status_code == 404
    # owner delete -> 204 then 404
    assert client.delete(f"/api/todos/{todo['id']}", headers=u["headers"]).status_code == 204
    assert client.delete(f"/api/todos/{todo['id']}", headers=u["headers"]).status_code == 404


def test_suggestion_accept_and_dismiss(client) -> None:
    u = _register(client, "sched2")
    user_id = db.read_one("SELECT id FROM users WHERE username = ?", ("sched2",))["id"]
    # seed two pending suggestions directly (as the runner does after a summary;
    # the deadlines stage stores date-only start_at)
    db.write(
        "INSERT INTO event_suggestions (user_id, document_id, title, start_at, end_at, evidence, status)"
        " VALUES (?, NULL, 'Tenggat UTS Fisika', '2026-11-10', NULL, 'Hal. 2: UTS 10 November', 'pending')",
        (user_id,),
    )
    db.write(
        "INSERT INTO event_suggestions (user_id, document_id, title, start_at, end_at, evidence, status)"
        " VALUES (?, NULL, 'Tenggat Tugas 3', '2026-11-12', NULL, 'Hal. 5', 'pending')",
        (user_id,),
    )
    r = client.get("/api/suggestions", headers=u["headers"])
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 2
    assert all(s["status"] == "pending" for s in items)
    target = next(s for s in items if s["title"] == "Tenggat UTS Fisika")
    # accept -> 201 event with source 'ringkasan' (BUG-04), end defaults to start + 1 h
    r = client.post(f"/api/suggestions/{target['id']}/accept", headers=u["headers"])
    assert r.status_code == 201, r.text
    ev = r.json()
    assert ev["source"] == "ringkasan"
    assert ev["title"] == "Tenggat UTS Fisika"
    assert ev["end_at"] > ev["start_at"]
    # accepted suggestion leaves the pending list
    r = client.get("/api/suggestions", headers=u["headers"])
    remaining = r.json()["items"]
    assert [s["id"] for s in remaining] == [s["id"] for s in items if s["id"] != target["id"]]
    # the event now appears in the events list
    r = client.get("/api/events", headers=u["headers"])
    assert any(e["id"] == ev["id"] for e in r.json()["items"])
    # dismiss the other one -> 204, list empty
    other = remaining[0]
    r = client.post(f"/api/suggestions/{other['id']}/dismiss", headers=u["headers"])
    assert r.status_code == 204
    r = client.get("/api/suggestions", headers=u["headers"])
    assert r.json()["items"] == []
    # dismissing again -> 404 (no longer pending)
    r = client.post(f"/api/suggestions/{other['id']}/dismiss", headers=u["headers"])
    assert r.status_code == 404
    # another user's suggestion -> 404
    u2 = _register(client, "sched3")
    r = client.post(f"/api/suggestions/{target['id']}/accept", headers=u2["headers"])
    assert r.status_code == 404


# ---------------------------------------------------------------- L7 task 2: import

def test_parse_ics_no_ai() -> None:
    from server.jobs.import_schedule import parse_ics

    ics = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "BEGIN:VEVENT\r\n"
        "SUMMARY:Ospek Baru\r\n"
        "DTSTART:20261105T080000Z\r\n"
        "DTEND:20261105T100000Z\r\n"
        "LOCATION:Gedung A\\, Lt 2\r\n"
        "END:VEVENT\r\n"
        "BEGIN:VEVENT\r\n"
        "SUMMARY:Ujian Praktikum\r\n"
        "DTSTART;VALUE=DATE:20261108\r\n"
        "END:VEVENT\r\n"
        "BEGIN:VEVENT\r\n"
        "SUMMARY:Kosong\r\n"
        "DTSTART:20261105T090000Z\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
    items = parse_ics(ics)
    assert len(items) == 3
    # UTC Z date kept as UTC
    assert items[0]["title"] == "Ospek Baru"
    assert items[0]["kind"] == "acara"
    assert items[0]["start_at"].startswith("2026-11-05T08:00:00")
    assert items[0]["end_at"].startswith("2026-11-05T10:00:00")
    assert items[0]["location"] == "Gedung A, Lt 2"
    # VALUE=DATE (all-day) -> midnight WIB
    assert items[1]["start_at"].startswith("2026-11-07T17:00:00")  # 2026-11-08 00:00 WIB -> UTC
    assert "end_at" not in items[1]
    # no DTEND -> no end key
    assert "end_at" not in items[2]
    # empty input -> no items
    assert parse_ics("BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n") == []


def test_import_job_runs_end_to_end_with_fakellm(client, monkeypatch) -> None:
    import server.ai as ai_pkg
    from server.jobs import import_schedule

    real = import_schedule.run_import

    def fake(files, on_stage=None, **kwargs):
        kwargs["llm"] = ai_pkg.FakeLLM()
        return real(files, on_stage, **kwargs)

    monkeypatch.setattr(import_schedule, "run_import", fake)
    # The health probe has no token here; pin the import gate to "ok".
    monkeypatch.setattr("server.api.schedule.ms_state", lambda: {"status": "ok", "latency_ms": 1, "updated_at": 0.0})

    u = _register(client, "import1")
    ics = (
        "BEGIN:VCALENDAR\r\n"
        "BEGIN:VEVENT\r\n"
        "SUMMARY:Ospek Baru\r\n"
        "DTSTART:20261105T080000Z\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
    # a real .docx (an allowed import ext; txt is not one of them)
    import io

    from docx import Document

    doc = Document()
    doc.add_paragraph("Kuis fisika 10 November 09:00 di Lab 2. Kumpul kelompok 12 November.")
    buf = io.BytesIO()
    doc.save(buf)
    docx_bytes = buf.getvalue()
    r = client.post(
        "/api/schedule/import",
        headers=u["headers"],
        files=[
            ("files", ("ospek.ics", ics.encode("utf-8"))),
            ("files", ("jadwal.docx", docx_bytes)),
        ],
    )
    assert r.status_code == 202, r.text
    job_id = r.json()["job_id"]

    # poll until done (the runner thread picks up the FakeLLM-patched pipeline)
    import time

    job = None
    for _ in range(200):
        job = client.get(f"/api/jobs/{job_id}", headers=u["headers"]).json()
        if job["status"] in ("done", "error"):
            break
        time.sleep(0.05)
    assert job["status"] == "done", job

    r = client.get("/api/suggestions", headers=u["headers"])
    items = r.json()["items"]
    titles = {s["title"] for s in items}
    # ICS parsed without AI + two items from the single CHECK call (FakeLLM)
    assert "Ospek Baru" in titles
    assert "Kuis Fisika" in titles and "Kumpul Kelompok" in titles
    by_title = {s["title"]: s for s in items}
    # the CHECK item kept its kind/subkind from the model (QA schema)
    assert by_title["Kuis Fisika"]["kind"] == "tenggat"
    assert by_title["Kuis Fisika"]["subkind"] == "ujian"
    # one CHECK ai_call was recorded
    calls = db.read("SELECT * FROM ai_calls WHERE job_id = ?", (job_id,))
    assert len(calls) == 1
    assert calls[0]["feature"] == "schedule_import"
    assert calls[0]["role"] == "CHECK"
    # accept the imported suggestion -> event carries kind + source
    kuis = next(s for s in items if s["title"] == "Kuis Fisika")
    r = client.post(f"/api/suggestions/{kuis['id']}/accept", headers=u["headers"])
    assert r.status_code == 201, r.text
    assert r.json()["kind"] == "tenggat"
    assert r.json()["subkind"] == "ujian"
    assert r.json()["source"] == "impor"
