"""L1 smoke test against the REAL ModelScope API.

Skips (exit 0) when MODELSCOPE_TOKEN is not set. Otherwise:
1. one tiny call per role, with latency;
2. one real summarize on a small generated PDF, printing seconds per stage.

Usage:  python scripts/smoke_test.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def make_pdf(path: Path) -> None:
    """Write a 2-page ASCII PDF (Helvetica) with a deadline mention."""
    pages = [
        [
            "Matematika Dasar",
            "",
            "Rumus luas lingkaran adalah A = r^2 dengan r",
            "jari-jari. Keliling lingkaran C = 2 * pi * r.",
            "",
            "Contoh: untuk r = 5, A = 25 * pi.",
            "Ujian akhir semester 4 November 2026.",
        ],
        [
            "Latihan Soal",
            "",
            "Soal 1: hitung luas lingkaran r = 3.",
            "Soal 2: hitung keliling lingkaran r = 7.",
            "",
            "Kunci jawaban dibahas di pertemuan terakhir.",
        ],
    ]
    n = len(pages)

    def esc(s: str) -> str:
        return s.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")

    content_objs: list[bytes] = []
    for lines in pages:
        body = ["BT /F1 12 Tf 72 720 Td 16 TL"]
        for line in lines:
            body.append(f"({esc(line)}) Tj T*" if line else "T*")
        body.append("ET")
        content_objs.append(("\n".join(body)).encode("latin-1"))

    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(n))
    total_objs = 3 + 2 * n
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []

    def add(num: int, body: bytes) -> None:
        nonlocal out
        offsets.append(len(out))
        out += f"{num} 0 obj\n".encode() + body + b"\nendobj\n"

    add(1, b"<< /Type /Catalog /Pages 2 0 R >>")
    add(2, f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode())
    add(3, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for i in range(n):
        page_obj = 4 + 2 * i
        content_obj = 5 + 2 * i
        page_dict = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_obj} 0 R >>"
        )
        add(page_obj, page_dict.encode())
        stream = content_objs[i]
        add(content_obj, b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")

    xref_pos = len(out)
    out += f"xref\n0 {total_objs + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {total_objs + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))


def main() -> None:
    token = os.environ.get("MODELSCOPE_TOKEN", "").strip()
    if not token:
        print("SKIP: MODELSCOPE_TOKEN not set (set it in the environment and re-run)")
        return

    from server.ai import summarize
    from server.ai.llm import ROLE_MODELS, chat

    # 1) one tiny call per role
    print(f"\n{'role':<8} {'model':<38} {'ok':<5} {'ms':>7}")
    for role in ("VISION", "FAST", "REASON", "CHECK"):
        calls: list[dict] = []
        try:
            t0 = time.monotonic()
            chat(role, [{"role": "user", "content": "ping"}], feature="smoke", calls=calls)
            print(f"{role:<8} {ROLE_MODELS[role]:<38} {'ok':<5} {calls[0]['latency_ms']:>7}")
        except Exception as exc:
            ms = int((time.monotonic() - t0) * 1000)
            print(f"{role:<8} {ROLE_MODELS[role]:<38} {'FAIL':<5} {ms:>7}  {str(exc)[:80]}")

    # 2) one real summarize on a small generated PDF
    with tempfile.TemporaryDirectory(prefix="orvina-smoke-") as td:
        pdf = Path(td) / "modul.pdf"
        make_pdf(pdf)
        stage_t: dict[str, float] = {}
        last = time.monotonic()

        def on_stage(name: str) -> None:
            nonlocal last
            now = time.monotonic()
            stage_t[name] = now - last
            last = now

        t0 = time.monotonic()
        try:
            files = [{"path": str(pdf), "name": "modul.pdf", "mime": "application/pdf"}]
            options = {"style": "terstruktur", "lang": "id"}
            result = summarize("smoke-1", files, options, on_stage)
            total_s = (time.monotonic() - t0) / 1000
            print(f"\nreal summarize: {total_s:.1f}s total")
            print(f"{'stage':<12} {'s':>7}")
            for stage in ("extract", "chunk", "map", "reduce", "check", "deadlines"):
                print(f"{stage:<12} {stage_t.get(stage, 0.0):>7.2f}")
            n_chars = len(result["content_md"])
            print(
                f"summary {n_chars} chars, warnings={len(result['warnings'])}, "
                f"deadlines={len(result['deadlines'])}, ai_calls={len(result['ai_calls'])}"
            )
            for w in result["warnings"]:
                print(f"  warning: {w}")
            for d in result["deadlines"]:
                print(f"  deadline: {d['title']} {d['start_at']}")
        except Exception as exc:
            print(f"\nreal summarize FAILED after {int((time.monotonic() - t0) * 1000) / 1000:.1f}s: {exc}")


if __name__ == "__main__":
    main()
