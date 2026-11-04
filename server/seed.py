"""Idempotent demo seed (SPEC §5, §12).

On an empty database: 3 subjects, a demo user (demo / demo12345) and 2 sample
summary documents with LaTeX and code. Safe to run on every startup.
"""
from __future__ import annotations

import json
import logging

import bcrypt

from server.store import db

log = logging.getLogger("orvina.seed")

DEMO_SUBJECTS = ("Matematika", "Fisika", "Bahasa Indonesia")


def _doc1_md() -> str:
    return (
        "# Ringkasan: Limit dan Turunan\n\n"
        "## TL;DR\n- Limit menjelaskan perilaku fungsi saat mendekati suatu titik.\n"
        "- Turunan adalah laju perubahan sesaat.\n- Contoh rumus penting: turunan x^n.\n\n"
        "## Rumus kunci\n"
        "$$\\lim_{x \\to a} f(x) = L$$\n"
        "$$\\frac{d}{dx} x^n = n x^{n-1}$$\n\n"
        "## Contoh kode\n"
        "```python\n"
        "def turunan_konstan():\n"
        "    return 0\n"
        "```\n\n"
        "## Tanggal\nUjian tengah semester: 10 November 2026.\n"
    )


def _doc2_md() -> str:
    return (
        "# Ringkasan: Hukum Newton\n\n"
        "## TL;DR\n- Tiga hukum Newton menjelaskan gerak benda.\n"
        "## Rumus kunci\n"
        "$$F = m a$$\n"
        "## Contoh kode\n"
        "```python\n"
        "def gaya(m, a):\n"
        "    return m * a\n"
        "```\n"
    )


def seed_if_empty() -> None:
    row = db.read_one("SELECT count(*) AS n FROM users")
    if row and row["n"] > 0:
        return
    log.info("database is empty; seeding demo data")
    subject_ids: dict[str, int] = {}
    for name in DEMO_SUBJECTS:
        cur = db.write("INSERT INTO subjects (name) VALUES (?)", (name,))
        subject_ids[name] = int(cur.lastrowid)

    pw_hash = bcrypt.hashpw(b"demo12345", bcrypt.gensalt(12)).decode()
    cur = db.write(
        "INSERT INTO users (username, display_name, password_hash, lang, theme, onboarding_done) VALUES (?, ?, ?, 'id', 'system', 1)",
        ("demo", "Demo Orvina", pw_hash),
    )
    user_id = int(cur.lastrowid)
    db.write("INSERT INTO user_subjects (user_id, subject_id) VALUES (?, ?)", (user_id, subject_ids["Matematika"]))
    db.write("INSERT INTO user_subjects (user_id, subject_id) VALUES (?, ?)", (user_id, subject_ids["Fisika"]))

    docs = (
        ("Ringkasan: Limit dan Turunan", "Matematika", _doc1_md(), ["modul-limit.pdf"]),
        ("Ringkasan: Hukum Newton", "Fisika", _doc2_md(), ["modul-newton.pptx"]),
    )
    for title, subject, content, sources in docs:
        db.write(
            "INSERT INTO documents (user_id, kind, title, subject_id, source_files_json, content_md, extra_json)"
            " VALUES (?, 'summary', ?, ?, ?, ?, ?)",
            (
                user_id,
                title,
                subject_ids[subject],
                json.dumps([{"name": s, "size_bytes": 0} for s in sources]),
                content,
                json.dumps({"figures": [], "sources": [], "deadlines": [], "warnings": [], "ai_calls": []}),
            ),
        )
    log.info("demo seed done (user 'demo', %d subjects, 2 documents)", len(DEMO_SUBJECTS))
