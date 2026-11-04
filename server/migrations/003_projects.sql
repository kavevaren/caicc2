-- L7 v2 (2026-11-03): Proyek — group summaries into a named folder.
-- Applied once per database via schema_version; the runner never re-applies.

CREATE TABLE projects (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE project_documents (
    project_id INTEGER NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
    document_id INTEGER NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    added_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (project_id, document_id)
);

CREATE INDEX idx_projects_user ON projects (user_id);
CREATE INDEX idx_project_documents_doc ON project_documents (document_id);
