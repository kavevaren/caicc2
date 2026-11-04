"""One-off: seed demo deadline + pending suggestion in the LOCAL dev DB (not the Studio seed)."""
import json
import sqlite3

conn = sqlite3.connect(r"C:\Users\Lenovo\AppData\Local\Temp\opencode\orvina-data\orvina.db")
conn.row_factory = sqlite3.Row
uid = conn.execute("SELECT id FROM users WHERE username='demo'").fetchone()["id"]
doc = conn.execute("SELECT id, extra_json FROM documents WHERE id=2").fetchone()
extra = json.loads(doc["extra_json"])
extra["deadlines"] = [
    {"title": "UTS Fisika", "start_at": "2026-11-10", "end_at": None, "evidence": "Hal. 2: UTS pada 10 November"}
]
conn.execute("UPDATE documents SET extra_json = ? WHERE id = ?", (json.dumps(extra, ensure_ascii=False), doc["id"]))
n = conn.execute("SELECT COUNT(*) AS c FROM event_suggestions WHERE user_id = ? AND status = 'pending'", (uid,)).fetchone()["c"]
if n == 0:
    conn.execute(
        "INSERT INTO event_suggestions (user_id, document_id, title, start_at, end_at, evidence, status)"
        " VALUES (?, 2, 'Tenggat Makalah AI Ethics', '2026-11-14', NULL, 'Hal. 5', 'pending')",
        (uid,),
    )
conn.commit()
print(
    "deadlines:", len(extra["deadlines"]),
    "| pending:", conn.execute("SELECT COUNT(*) AS c FROM event_suggestions WHERE user_id=? AND status='pending'", (uid,)).fetchone()["c"],
)
