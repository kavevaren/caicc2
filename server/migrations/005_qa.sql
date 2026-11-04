-- QA fixes (2026-11-03, prompt orvina_perbaikan). Applied once per database.
--
-- 1. New agenda categories (owner decision): kelas / belajar / acara /
--    tenggat (subkind tugas|kuis|ujian). Old rows are mapped:
--    kegiatan -> belajar, tugas -> tenggat/tugas, ujian -> tenggat/ujian,
--    acara -> acara.
-- 2. BUG-03: events.ics_uid (+ unique partial index) for .ics import dedup.
-- 3. BUG-04: events.source values manual | ringkasan | impor (old 'ai' ->
--    'ringkasan'); event_suggestions carries its source to accept.
-- 4. BUG-21 / FEAT-02: jobs.percent / jobs.label / jobs.notes (persistent
--    progress, file name for the floating tray, FEAT-01 user notes).
-- 5. FEAT-01: event_suggestions gains location / subkind / ics_uid so the
--    review-before-save preview can edit and upsert imported items.

-- events: rebuild (kind + source CHECK changed, new columns) -------------------
BEGIN;
CREATE TABLE events_new (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    location TEXT,
    description TEXT,
    reminder_minutes INTEGER,
    source TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('manual', 'ringkasan', 'impor', 'google')),
    kind TEXT NOT NULL DEFAULT 'belajar' CHECK (kind IN ('kelas', 'belajar', 'acara', 'tenggat')),
    subkind TEXT CHECK (subkind IS NULL OR subkind IN ('tugas', 'kuis', 'ujian')),
    ics_uid TEXT,
    google_event_id TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
INSERT INTO events_new (
    id, user_id, title, start_at, end_at, location, description, reminder_minutes,
    source, kind, subkind, ics_uid, google_event_id, created_at
)
SELECT
    id, user_id, title, start_at, end_at, location, description, reminder_minutes,
    CASE source WHEN 'ai' THEN 'ringkasan' ELSE source END,
    CASE kind WHEN 'kegiatan' THEN 'belajar' WHEN 'tugas' THEN 'tenggat' WHEN 'ujian' THEN 'tenggat' ELSE kind END,
    CASE kind WHEN 'tugas' THEN 'tugas' WHEN 'ujian' THEN 'ujian' ELSE NULL END,
    NULL,
    google_event_id,
    created_at
FROM events;
DROP TABLE events;
ALTER TABLE events_new RENAME TO events;
COMMIT;
CREATE INDEX IF NOT EXISTS idx_events_user_start ON events (user_id, start_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_events_user_ics_uid ON events (user_id, ics_uid) WHERE ics_uid IS NOT NULL;

-- event_suggestions: rebuild (kind CHECK changed, new columns) ------------------
BEGIN;
CREATE TABLE event_suggestions_new (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    document_id INTEGER REFERENCES documents (id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    start_at TEXT NOT NULL,
    end_at TEXT,
    location TEXT,
    evidence TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'added', 'dismissed')),
    kind TEXT NOT NULL DEFAULT 'tenggat' CHECK (kind IN ('kelas', 'belajar', 'acara', 'tenggat')),
    subkind TEXT CHECK (subkind IS NULL OR subkind IN ('tugas', 'kuis', 'ujian')),
    source TEXT NOT NULL DEFAULT 'ringkasan' CHECK (source IN ('ringkasan', 'impor')),
    ics_uid TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
INSERT INTO event_suggestions_new (
    id, user_id, document_id, title, start_at, end_at, location, evidence, status,
    kind, subkind, source, ics_uid, created_at
)
SELECT
    id, user_id, document_id, title, start_at, end_at, NULL, evidence, status,
    CASE kind WHEN 'kegiatan' THEN 'belajar' WHEN 'tugas' THEN 'tenggat' WHEN 'ujian' THEN 'tenggat' ELSE kind END,
    CASE kind WHEN 'tugas' THEN 'tugas' WHEN 'ujian' THEN 'ujian' ELSE NULL END,
    CASE WHEN document_id IS NULL THEN 'impor' ELSE 'ringkasan' END,
    NULL,
    created_at
FROM event_suggestions;
DROP TABLE event_suggestions;
ALTER TABLE event_suggestions_new RENAME TO event_suggestions;
COMMIT;
CREATE INDEX IF NOT EXISTS idx_suggestions_user_status ON event_suggestions (user_id, status);

-- jobs: persistent progress + tray label + FEAT-01 notes -------------------------
ALTER TABLE jobs ADD COLUMN percent INTEGER NOT NULL DEFAULT 0;
ALTER TABLE jobs ADD COLUMN label TEXT;
ALTER TABLE jobs ADD COLUMN notes TEXT;
