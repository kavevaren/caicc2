"""BUG-08 watchdog tests: 'queued' jobs are never stalled (they are only
waiting for a worker thread); a 'running' job with no update for
STALL_SECONDS is failed as 'stalled'."""
from __future__ import annotations

from server.jobs import runner
from server.store import db


def _job(job_id: str, status: str, age_seconds: int) -> None:
    uid = db.read_one("SELECT id FROM users ORDER BY id LIMIT 1")
    db.write(
        "INSERT INTO jobs (id, user_id, kind, status, stage, stages_json, created_at, updated_at)"
        " VALUES (?, ?, 'summary', ?, 'queued', '[]',"
        " strftime('%Y-%m-%dT%H:%M:%fZ', 'now', ?),"
        " strftime('%Y-%m-%dT%H:%M:%fZ', 'now', ?))",
        (job_id, uid["id"], status, f"-{age_seconds} seconds", f"-{age_seconds} seconds"),
    )


def test_watchdog_ignores_queued_jobs(client) -> None:
    _job("wd-queued", "queued", runner.STALL_SECONDS + 60)
    runner._watchdog_tick()
    row = db.read_one("SELECT status, error_code FROM jobs WHERE id = ?", ("wd-queued",))
    assert row["status"] == "queued"
    assert row["error_code"] is None


def test_watchdog_fails_stalled_running_job(client) -> None:
    _job("wd-running", "running", runner.STALL_SECONDS + 60)
    runner._watchdog_tick()
    row = db.read_one("SELECT status, error_code FROM jobs WHERE id = ?", ("wd-running",))
    assert row["status"] == "error"
    assert row["error_code"] == "stalled"
