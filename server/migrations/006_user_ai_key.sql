-- 2026-11-03: per-user ModelScope API key (Profil & Pengaturan).
-- The key is stored encrypted (server/store/secrets.py); only the last 4
-- characters are kept in clear as a hint. Applied once via schema_version.

CREATE TABLE user_ai_keys (
    user_id INTEGER PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
    token_enc TEXT NOT NULL,
    hint TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
