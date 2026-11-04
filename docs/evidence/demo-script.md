# Demo video script (60–90 s)

Record on the public Studio URL, in an incognito window, light mode, ~1280 px wide.
Speak in Indonesian (or English — be consistent). Keep the cursor visible; do not cut
between steps.

| s | Screen | What to do | Narration (id) |
|---|---|---|---|
| 0–8 | Studio page | Show the Studio title + the app loading | "Ini Orvina, aplikasi ringkasan materi untuk mahasiswa, berjalan di ModelScope Studio." |
| 8–20 | Login → Register | Register a fresh account (username, password, centang syarat) | "Daftar akun baru: nama pengguna, kata sandi, dan persetujuan syarat. Tidak ada onboarding." |
| 20–30 | Dashboard | Point at the greeting, the week atom, the stat strip, "Aktivitas terakhir" | "Dashboard menampilkan data nyata: ringkasan tersimpan, dokumen, dan agenda minggu ini." |
| 30–50 | Ringkas Materi | Drag in a PDF/PPTX (or photo), pick style "Poin, rumus, dan kode", bahasa Indonesia, klik "Ringkas" | "Unggah catatan kelas — PDF, PPTX, DOCX, teks, atau foto. Pilih gaya ringkasan, lalu Orvina memprosesnya." |
| 50–60 | Running state | AtomLoader + stage label ("Memeriksa format" …) | "Progresnya terlihat: baca file, ringkas bagian, periksa format, cari tenggat." |
| 60–72 | DocumentView | The generated summary: LaTeX formula rendered, code block, "Sumber" tab | "Hasilnya Markdown dengan rumus LaTeX dan kode, plus daftar sumber file. Bisa diunduh sebagai .md." |
| 72–80 | Perpustakaan | Search box, subject chip, open the document | "Semua ringkasan tersimpan di Perpustakaan, bisa dicari dan difilter per mata kuliah." |
| 80–90 | Dashboard again / theme toggle | Toggle dark mode, back to light | "Tersedia mode gelap dan terang, bahasa Indonesia dan Inggris. Terima kasih." |

**Notes**
- If the summarize job takes longer than ~30 s, keep the running state on screen — it is
  part of the demo (polling every 2 s).
- The "7 hari ke depan" card is empty until deadlines are extracted; if a deadline appears
  from the uploaded file, point at it ("tenggat otomatis dari ringkasan").
- One frame should show the agent window with the model name `Qwen3.8-27B` visible
  (OpenCode session) — for the compliance evidence, not for the video itself.
