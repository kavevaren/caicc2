"""QA-fix tests (prompt orvina_perbaikan, 2026-11-03).

Covers the rules the prompt calls out: deadline fallback parsing (BUG-01),
deterministic ICS filter incl. the safety valve (FEAT-01), ICS direct event +
re-import upsert (BUG-03/BUG-21), import-meta, jobs active feed with percent
+ label (FEAT-02), and inline suggestion edit + accept-batch (FEAT-01).
"""
from __future__ import annotations

import datetime as dt
import time

from server.ai.summarize import _clean_deadlines, fallback_deadlines
from server.jobs.import_schedule import filter_ics
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


# ---------------------------------------------------------------- deadlines


def test_clean_deadlines_new_schema_and_drops() -> None:
    raw = [
        {
            "title": "UAS Fisika",
            "kind": "tenggat",
            "subkind": "ujian",
            "date": "2026-11-20",
            "time": "13.00",
            "evidence": "UAS 20 November",
        },
        {"title": "Kumpul kelompok", "kind": "belajar", "date": "2026-11-12", "time": None, "evidence": "kumpul 12 November"},
        {"title": "Tanpa tanggal", "kind": "tenggat", "date": "nanti", "time": None, "evidence": "?"},
        {"title": "Subkind salah", "kind": "belajar", "subkind": "ujian", "date": "2026-11-13", "time": None, "evidence": "?"},
    ]
    out, warns = _clean_deadlines(raw, dt.date(2026, 11, 3))
    assert len(out) == 3
    # 13:00 WIB -> 06:00 UTC
    assert out[0]["start_at"] == "2026-11-20T06:00:00.000Z"
    assert out[0]["kind"] == "tenggat" and out[0]["subkind"] == "ujian"
    # date-only stays date-only
    assert out[1]["start_at"] == "2026-11-12"
    # subkind only kept for kind 'tenggat'
    assert out[1]["subkind"] is None
    assert out[2]["title"] == "Subkind salah" and out[2]["subkind"] is None
    assert warns == ["deadline_dropped"]


def test_fallback_deadlines_indonesian_and_english() -> None:
    today = dt.date(2026, 11, 3)
    md_id = (
        "# Judul\n\n## Isi\nmateri\n\n## Tanggal & tenggat\n"
        "- UTS Fisika pada 5 November 2026 pukul 13.00\n"
        "- Kuis Kimia 12 November\n\n## Peta sumber\nHal. 2\n"
    )
    out = fallback_deadlines(md_id, today)
    assert len(out) == 2
    by_title = {d["title"].split()[0].lower(): d for d in out}
    assert by_title["uts"]["start_at"] == "2026-11-05T06:00:00.000Z"
    assert by_title["uts"]["kind"] == "tenggat" and by_title["uts"]["subkind"] == "ujian"
    # no year -> next occurrence from today (still 2026)
    assert by_title["kuis"]["start_at"] == "2026-11-12"
    assert by_title["kuis"]["subkind"] == "kuis"

    md_en = (
        "# Title\n\n## Content\nmaterial\n\n## Dates & deadlines\n"
        "- Midterm exam on March 15, 2027 at 09:00\n"
    )
    out_en = fallback_deadlines(md_en, today)
    assert len(out_en) == 1
    # 09:00 WIB -> 02:00 UTC
    assert out_en[0]["start_at"] == "2027-03-15T02:00:00.000Z"
    assert out_en[0]["subkind"] == "ujian"


# ---------------------------------------------------------------- ICS filter


def test_filter_ics_include_exclude_and_safety_valve() -> None:
    items = [
        {"title": "Ospek Baru", "kind": "acara", "start_at": "2026-11-05T01:00:00.000Z", "location": "Gedung A"},
        {"title": "Kuis Fisika", "kind": "tenggat", "start_at": "2026-11-10T02:00:00.000Z"},
    ]
    # no note -> unchanged
    assert filter_ics(items, None) == items
    # negation clause excludes
    kept = filter_ics(items, "abaikan kuis")
    assert [it["title"] for it in kept] == ["Ospek Baru"]
    # positive clause includes
    kept = filter_ics(items, "hanya ospek")
    assert [it["title"] for it in kept] == ["Ospek Baru"]
    # safety valve: a filter that would drop everything keeps all events
    assert filter_ics(items, "fokus ke materi") == items


# ------------------------------------------------- ICS import (BUG-03/21)


def test_ics_import_direct_event_reimport_upsert(client, monkeypatch) -> None:
    # The health probe has no token here; pin the import gate to "ok".
    monkeypatch.setattr("server.api.schedule.ms_state", lambda: {"status": "ok", "latency_ms": 1, "updated_at": 0.0})
    u = _register(client, "qa_ics")
    u2 = _register(client, "qa_ics_other")
    ics = (
        "BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nSUMMARY:Ujian Akhir\r\n"
        "UID:tes-001@orvina\r\nDTSTART:20261105T060000Z\r\nLOCATION:Lab 2\r\n"
        "END:VEVENT\r\nEND:VCALENDAR\r\n"
    )

    def do_import(ics_text: str, notes: str | None = None) -> dict:
        data = {"notes": notes} if notes is not None else {}
        r = client.post(
            "/api/schedule/import",
            headers=u["headers"],
            files=[("files", ("tes.ics", ics_text.encode("utf-8")))],
            data=data,
        )
        assert r.status_code == 202, r.text
        job_id = r.json()["job_id"]
        job = None
        for _ in range(200):
            job = client.get(f"/api/jobs/{job_id}", headers=u["headers"]).json()
            if job["status"] in ("done", "error"):
                break
            time.sleep(0.05)
        assert job["status"] == "done", job
        return job

    # BUG-21: deterministic ICS lands in the calendar without review
    job = do_import(ics, notes="hanya yang penting")
    items = client.get("/api/events", headers=u["headers"]).json()["items"]
    assert len(items) == 1
    ev = items[0]
    assert ev["title"] == "Ujian Akhir"
    assert ev["source"] == "impor" and ev["kind"] == "acara"
    assert ev["start_at"].startswith("2026-11-05T06:00:00")
    # FEAT-02: percent persisted, label = first file name
    assert job["percent"] == 100 and job["label"] == "tes.ics"

    # FEAT-01: last import notes come back from import-meta
    r = client.get("/api/schedule/import-meta", headers=u["headers"])
    assert r.status_code == 200 and r.json()["notes"] == "hanya yang penting"

    # FEAT-02: the finished job is in the active feed (last 5 minutes)
    feed = client.get("/api/jobs?active=1", headers=u["headers"]).json()["items"]
    assert any(j["id"] == job["id"] and j["percent"] == 100 for j in feed)
    # ownership: another user cannot read the job
    assert client.get(f"/api/jobs/{job['id']}", headers=u2["headers"]).status_code == 404

    # BUG-03: re-import with the same UID updates, never duplicates
    job2 = do_import(ics.replace("Ujian Akhir", "Ujian Akhir (revisi)"))
    assert job2["status"] == "done"
    items = client.get("/api/events", headers=u["headers"]).json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Ujian Akhir (revisi)"


# ------------------------------------------------- suggestion edit + batch


def test_suggestion_inline_edit_and_accept_batch(client) -> None:
    u = _register(client, "qa_batch")
    user_id = db.read_one("SELECT id FROM users WHERE username = ?", ("qa_batch",))["id"]
    db.write(
        "INSERT INTO event_suggestions (user_id, document_id, title, start_at, end_at, evidence, status, kind, subkind, source)"
        " VALUES (?, NULL, 'Kuis X', '2026-11-10', NULL, 'Hal. 1', 'pending', 'tenggat', 'kuis', 'ringkasan')",
        (user_id,),
    )
    s = client.get("/api/suggestions", headers=u["headers"]).json()["items"][0]
    # FEAT-01: inline edit before saving
    r = client.patch(
        f"/api/suggestions/{s['id']}",
        json={"title": "Kuis X (edit)", "kind": "kelas", "subkind": "ujian"},
        headers=u["headers"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["title"] == "Kuis X (edit)"
    assert body["kind"] == "kelas" and body["subkind"] is None  # subkind dropped for non-tenggat
    # removed category -> 422 (no silent fallback)
    assert client.patch(f"/api/suggestions/{s['id']}", json={"kind": "kegiatan"}, headers=u["headers"]).status_code == 422
    # batch: one valid + one missing id -> only the valid one is accepted
    r = client.post("/api/suggestions/accept-batch", json={"ids": [s["id"], 999999]}, headers=u["headers"])
    assert r.status_code == 201, r.text
    assert len(r.json()["items"]) == 1
    ev = r.json()["items"][0]
    assert ev["title"] == "Kuis X (edit)" and ev["source"] == "ringkasan"
    # accepted suggestion leaves the pending list
    assert client.get("/api/suggestions", headers=u["headers"]).json()["items"] == []
