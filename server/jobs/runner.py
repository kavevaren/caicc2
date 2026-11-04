"""Job runner (SPEC §8.1, lean + QA fixes).

A ThreadPoolExecutor(JOB_WORKERS) runs server.ai.summarize. on_stage updates
jobs.stage. On success: a documents row (kind='summary'), event_suggestions
from the deadlines and ai_calls rows. On AIError / ModelScopeAuthError:
status='error' with the mapped code. Every INSERT names its columns explicitly
and every write goes through store.db.write.

QA: progress percent is persisted in jobs.percent (BUG-21/FEAT-02, survives a
refresh); a watchdog fails jobs that make no progress for 3 minutes (BUG-08);
imports upsert by ics_uid instead of duplicating (BUG-03) and carry their
source into events (BUG-04).
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import server.ai as ai_pkg
from server.ai.llm import MAX_RETRIES, RETRY_BACKOFF_S, TIMEOUT_S
from server.config import settings
from server.store import db

log = logging.getLogger("orvina.jobs")

# Contract style enum -> L1 pipeline style.
STYLE_MAP = {
    "one_page": "ringkas",
    "structured_notes": "terstruktur",
    "key_points": "poin_rumus_kode",
    "qa_practice": "latihan",
    "flashcards": "kartu",
}

# AIError code -> job error_code (the UI maps these to translated messages).
ERROR_MAP = {
    "nothing_to_summarize": "nothing_to_summarize",
    "extract_failed": "extract_failed",
    "unsupported_format": "unsupported_format",
    "llm_unreachable": "ai_unavailable",
    "llm_bad_json": "ai_unavailable",
}

# L7a + FEAT-02: fixed stage weights for the progress percent (never
# decreases). Persisted to jobs.percent so the floating tray survives a
# refresh. The map stage scales 15 -> 80 by done/total.
STAGE_START = {"queued": 0, "extract": 10, "chunk": 15, "map": 15, "reduce": 80, "check": 93, "deadlines": 97}
_MAP_SPAN = 65
# BUG-08: a job with no update for STALL_SECONDS is failed. One live LLM call
# can take (MAX_RETRIES + 1) full timeouts plus the backoff sleeps
# (RETRY_BACKOFF_S * 1 + 2 + ... + MAX_RETRIES), so allow that plus 60 s slack.
_BACKOFF_TOTAL_S = RETRY_BACKOFF_S * (MAX_RETRIES * (MAX_RETRIES + 1) // 2)
STALL_SECONDS = int((MAX_RETRIES + 1) * TIMEOUT_S + _BACKOFF_TOTAL_S + 60)


def _now() -> str:
    return "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"


def _percent(stage: str, progress: tuple[int, int] | None) -> int:
    if stage in ("done", "error"):
        return 100 if stage == "done" else 0
    if stage == "map" and progress is not None and progress[1] > 0:
        done, total = progress
        return int(STAGE_START["map"] + _MAP_SPAN * (min(done, total) / total))
    return STAGE_START.get(stage, 0)


def _set_percent(job_id: str, percent: int) -> None:
    db.write("UPDATE jobs SET percent = ?, updated_at = ? WHERE id = ?", (percent, _now(), job_id))


def _bump_percent(job_id: str, stage: str, progress: tuple[int, int] | None) -> None:
    """Persist the max(current, computed) percent (never decreases).

    The updated_at watchdog heartbeat is refreshed on every call, even when
    the percent is unchanged, so a long chunk map keeps the job alive (BUG-08).
    """
    cur = db.read_one("SELECT percent FROM jobs WHERE id = ?", (job_id,))
    current = int(cur["percent"]) if cur else 0
    value = max(current, _percent(stage, progress))
    if value != current:
        _set_percent(job_id, value)
    else:
        db.write(f"UPDATE jobs SET updated_at = {_now()} WHERE id = ?", (job_id,))


_pool: ThreadPoolExecutor | None = None
_watchdog: threading.Thread | None = None
_lock = threading.Lock()

# L7a: in-memory map progress {job_id: (done, total)} (feeds the percent).
_progress: dict[str, tuple[int, int]] = {}
_progress_lock = threading.Lock()


def _set_progress(job_id: str, done: int, total: int) -> None:
    with _progress_lock:
        _progress[job_id] = (done, total)
    _bump_percent(job_id, "map", (done, total))


def get_progress(job_id: str) -> tuple[int, int] | None:
    """Current (done, total) chunk count, or None when not in the map loop."""
    with _progress_lock:
        return _progress.get(job_id)


def _watchdog_tick() -> None:
    """BUG-08: fail 'running' jobs with no update for STALL_SECONDS.

    'queued' jobs are never touched: waiting for a free worker thread is not
    a stall (status flips to 'running' when the worker actually starts).
    """
    db.write(
        "UPDATE jobs SET status = 'error', stage = 'error', error_code = 'stalled',"
        f" updated_at = {_now()}"
        " WHERE status = 'running'"
        " AND updated_at < strftime('%Y-%m-%dT%H:%M:%fZ', 'now', ?)",
        (f"-{STALL_SECONDS} seconds",),
    )


def _watchdog_loop() -> None:
    """BUG-08: fail stalled jobs (no progress update for STALL_SECONDS)."""
    while True:
        try:
            _watchdog_tick()
        except Exception:
            log.exception("watchdog tick failed")
        threading.Event().wait(60)


def start() -> None:
    """Create the pool + watchdog (idempotent).

    Jobs left over from a previous process are failed once, at pool
    creation — never on later submits, so a freshly queued job is not
    clobbered by the cleanup.
    """
    global _pool, _watchdog
    with _lock:
        if _pool is None:
            _pool = ThreadPoolExecutor(max_workers=settings.job_workers, thread_name_prefix="job")
            db.write(
                "UPDATE jobs SET status = 'error', stage = 'error', error_code = 'server_restart',"
                f" updated_at = {_now()} WHERE status IN ('queued', 'running')"
            )
            _watchdog = threading.Thread(target=_watchdog_loop, name="job-watchdog", daemon=True)
            _watchdog.start()


def submit(job_id: str, user_id: int, files: list[dict], options: dict) -> None:
    start()
    assert _pool is not None
    _pool.submit(_run, job_id, user_id, files, options)


def submit_import(job_id: str, user_id: int, files: list[dict], notes: str | None = None) -> None:
    """L7 task 2: schedule import (ICS without AI, the rest via one CHECK call)."""
    start()
    assert _pool is not None
    _pool.submit(_run_import, job_id, user_id, files, notes)


def _run_import(job_id: str, user_id: int, files: list[dict], notes: str | None = None) -> None:
    from server.jobs import import_schedule

    db.write(f"UPDATE jobs SET status = 'running', stage = 'queued', updated_at = {_now()} WHERE id = ?", (job_id,))
    try:
        suggestions, calls = import_schedule.run_import(files, on_stage=lambda s: _on_stage(job_id, s), notes=notes)
        _finish_import(job_id, user_id, suggestions, calls)
    except ai_pkg.ModelScopeAuthError:
        _fail(job_id, "modelscope_token_invalid")
    except ai_pkg.AIError as exc:
        _fail(job_id, ERROR_MAP.get(exc.code, "ai_unavailable"))
    except Exception:
        log.exception("import job %s crashed", job_id)
        _fail(job_id, "internal_error")


def _default_end(start_at: str) -> str:
    """events.end_at is NOT NULL; default to start + 1 h (SPEC §8.5)."""
    start_dt = dt.datetime.fromisoformat(start_at.replace("Z", "+00:00"))
    return (start_dt + dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _finish_import(job_id: str, user_id: int, suggestions: list[dict], calls: list[dict]) -> None:
    for s in suggestions:
        uid = s.get("ics_uid")
        if uid:
            # ICS = deterministic data: land directly in the calendar (BUG-21)
            # and upsert by (user, ics_uid) so re-imports never duplicate
            # (BUG-03). AI items below still go through the review card.
            end_at = s.get("end_at") or _default_end(s["start_at"])
            cur = db.write(
                "UPDATE events SET title = ?, start_at = ?, end_at = ?, location = ?, source = 'impor', kind = ?, subkind = ?"
                " WHERE user_id = ? AND ics_uid = ?",
                (s["title"], s["start_at"], end_at, s.get("location"), s["kind"], s.get("subkind"), user_id, uid),
            )
            if not cur.rowcount:
                db.write(
                    "INSERT INTO events (user_id, title, start_at, end_at, location, description, "
                    "reminder_minutes, source, kind, subkind, ics_uid)"
                    " VALUES (?, ?, ?, ?, ?, ?, NULL, 'impor', ?, ?, ?)",
                    (user_id, s["title"], s["start_at"], end_at, s.get("location"), s["evidence"], s["kind"], s.get("subkind"), uid),
                )
            continue
        db.write(
            "INSERT INTO event_suggestions (user_id, document_id, title, start_at, end_at, location, "
            "evidence, status, kind, subkind, source, ics_uid)"
            " VALUES (?, NULL, ?, ?, ?, ?, ?, 'pending', ?, ?, 'impor', ?)",
            (user_id, s["title"], s["start_at"], s["end_at"], s.get("location"), s["evidence"], s["kind"], s.get("subkind"), uid),
        )
    for c in calls:
        db.write(
            "INSERT INTO ai_calls (user_id, job_id, feature, role, model, latency_ms, retries, ok)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                user_id,
                job_id,
                c.get("feature", ""),
                c.get("role", ""),
                c.get("model", ""),
                int(c.get("latency_ms", 0)),
                int(c.get("retries", 0)),
                1 if c.get("ok") else 0,
            ),
        )
    db.write(
        f"UPDATE jobs SET status = 'done', stage = 'done', percent = 100, result_document_id = NULL, "
        f"error_code = NULL, updated_at = {_now()}"
        " WHERE id = ?",
        (job_id,),
    )


def _on_stage(job_id: str, name: str) -> None:
    row = db.read_one("SELECT stages_json FROM jobs WHERE id = ?", (job_id,))
    stages = json.loads(row["stages_json"] or "[]") if row else []
    if name not in stages:
        stages.append(name)
    db.write(
        f"UPDATE jobs SET stage = ?, stages_json = ?, updated_at = {_now()} WHERE id = ?",
        (name, json.dumps(stages), job_id),
    )
    progress = _progress.get(job_id)
    _bump_percent(job_id, name, progress)


def _fail(job_id: str, code: str) -> None:
    log.warning("job %s failed: %s", job_id, code)
    db.write(
        f"UPDATE jobs SET status = 'error', stage = 'error', error_code = ?, updated_at = {_now()} WHERE id = ?",
        (code, job_id),
    )


def _finish(job_id: str, user_id: int, result: dict[str, Any], options: dict) -> None:
    title = (options.get("title") or "").strip() or (files_first_name(options) or "Ringkasan")
    subject_id = options.get("subject_id")
    if subject_id is not None and db.read_one("SELECT id FROM subjects WHERE id = ?", (subject_id,)) is None:
        subject_id = None
    cur = db.write(
        "INSERT INTO documents (user_id, kind, title, subject_id, source_files_json, content_md, extra_json)"
        " VALUES (?, 'summary', ?, ?, ?, ?, ?)",
        (
            user_id,
            title,
            subject_id,
            json.dumps(options.get("source_files", []), ensure_ascii=False),
            result["content_md"],
            json.dumps(
                {
                    "figures": result.get("figures", []),
                    "sources": result.get("sources", []),
                    "deadlines": result.get("deadlines", []),
                    "warnings": result.get("warnings", []),
                    "ai_calls": result.get("ai_calls", []),
                },
                ensure_ascii=False,
            ),
        ),
    )
    doc_id = int(cur.lastrowid)
    for d in result.get("deadlines", []):
        db.write(
            "INSERT INTO event_suggestions (user_id, document_id, title, start_at, end_at, location, "
            "evidence, status, kind, subkind, source)"
            " VALUES (?, ?, ?, ?, ?, NULL, ?, 'pending', ?, ?, 'ringkasan')",
            (
                user_id,
                doc_id,
                d["title"],
                d["start_at"],
                d.get("end_at"),
                d.get("evidence", ""),
                d.get("kind", "tenggat"),
                d.get("subkind"),
            ),
        )
    for c in result.get("ai_calls", []):
        db.write(
            "INSERT INTO ai_calls (user_id, job_id, feature, role, model, latency_ms, retries, ok)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                user_id,
                job_id,
                c.get("feature", ""),
                c.get("role", ""),
                c.get("model", ""),
                int(c.get("latency_ms", 0)),
                int(c.get("retries", 0)),
                1 if c.get("ok") else 0,
            ),
        )
    db.write(
        f"UPDATE jobs SET status = 'done', stage = 'done', percent = 100, result_document_id = ?, error_code = NULL, updated_at = {_now()}"
        " WHERE id = ?",
        (doc_id, job_id),
    )


def files_first_name(options: dict) -> str | None:
    first = (options.get("source_files") or [{}])[0]
    return first.get("name")


def _run(job_id: str, user_id: int, files: list[dict], options: dict) -> None:
    db.write(f"UPDATE jobs SET status = 'running', stage = 'queued', updated_at = {_now()} WHERE id = ?", (job_id,))
    try:
        result = ai_pkg.summarize(
            job_id,
            files,
            options,
            lambda stage: _on_stage(job_id, stage),
            on_progress=lambda done, total: _set_progress(job_id, done, total),
        )
        _finish(job_id, user_id, result, options)
    except ai_pkg.ModelScopeAuthError:
        _fail(job_id, "modelscope_token_invalid")
    except ai_pkg.AIError as exc:
        _fail(job_id, ERROR_MAP.get(exc.code, "ai_unavailable"))
    except Exception:
        log.exception("job %s crashed", job_id)
        _fail(job_id, "internal_error")
    finally:
        with _progress_lock:
            _progress.pop(job_id, None)
