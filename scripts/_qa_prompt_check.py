import sys

sys.path.insert(0, ".")
from server.ai import prompts as p

s = p.deadlines_prompt("id", "2026-11-03", "hanya kelas B")
assert "kelas B" in s and "{language}" not in s, s
s2 = p.reduce_prompt("terstruktur", "id")
assert "Judul" in s2 and "mhchem" in s2 and "{language}" not in s2 and "{note}" not in s2, s2
s3 = p.schedule_import_prompt("en", "2026-11-03")
assert "tenggat" in s3 and "{language}" not in s3, s3
print("prompts OK")
