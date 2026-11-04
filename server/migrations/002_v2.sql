-- L7 v2 (2026-11-02). Applied once per database via schema_version; the
-- runner never re-applies a file, so ALTERs here are safe to add.

-- Event kind for the "Tambah jadwal" form (default keeps old rows valid).
ALTER TABLE events ADD COLUMN kind TEXT NOT NULL DEFAULT 'kegiatan'
    CHECK (kind IN ('kegiatan', 'acara', 'tugas', 'ujian'));

-- Suggestions from the schedule import carry their kind to accept (L7 task 2).
ALTER TABLE event_suggestions ADD COLUMN kind TEXT NOT NULL DEFAULT 'kegiatan'
    CHECK (kind IN ('kegiatan', 'acara', 'tugas', 'ujian'));

-- jobs.kind must accept 'schedule_import' (L7 task 2). SQLite has no
-- DROP CONSTRAINT, so the table is rebuilt in place.
BEGIN;
CREATE TABLE jobs_new (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('summary', 'transcript', 'schedule_import')),
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'done', 'error')),
    stage TEXT NOT NULL DEFAULT 'queued',
    stages_json TEXT,
    result_document_id INTEGER REFERENCES documents (id) ON DELETE SET NULL,
    error_code TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
INSERT INTO jobs_new (id, user_id, kind, status, stage, stages_json, result_document_id, error_code, created_at, updated_at)
    SELECT id, user_id, kind, status, stage, stages_json, result_document_id, error_code, created_at, updated_at
    FROM jobs;
DROP TABLE jobs;
ALTER TABLE jobs_new RENAME TO jobs;
COMMIT;
CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs (user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs (status);

-- To-dos for the Jadwal "Tugas" card (L7 task 1).
CREATE TABLE IF NOT EXISTS todos (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0,
    due_date TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_todos_user ON todos (user_id, done);
