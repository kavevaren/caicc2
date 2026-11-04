# Tugas: Perbaiki bug aplikasi Orvina (hasil uji coba QA)

## Konteks
Orvina adalah aplikasi belajar (repo/Studio ModelScope: `Jonathan_5960/orviva`) dengan menu: Dashboard, Ringkas Materi, Perpustakaan (+ Proyek), Jadwal, Tanya (chat AI berbasis ringkasan), dan Forum. UI dwibahasa (ID/EN) dengan mode terang/gelap. Di bawah ini adalah daftar bug dari sesi uji coba manual pada 3 November 2026 (zona waktu Asia/Jakarta, UTC+7).

## Aturan kerja
1. Baca dulu struktur kode dan temukan file yang relevan sebelum mengubah apa pun. Jangan menebak nama file.
2. Kerjakan berurutan: bug P1 (termasuk BUG-21) → FEAT-02 (progress bar, karena dipakai fitur lain) → FEAT-01 → bug P2 → UI-REDESIGN (sekaligus menyelesaikan bug tampilan P3; bug P3 yang tidak tercakup redesign tetap diperbaiki) → FEAT-03 (Google Calendar). Satu bug = satu perubahan kecil yang fokus; jangan refactor besar kecuali yang dibutuhkan FEAT-02 (model job), BUG-21 (store jadwal bersama), dan UI-REDESIGN (token & komponen dasar).
3. Jangan merusak fitur yang sudah berjalan: upload & ringkas, ganti nama, simpan ke proyek, buat proyek, pencarian/filter perpustakaan, chat Tanya, posting & jawab di Forum, tambah jadwal manual, impor .ics, toggle ID/EN, toggle tema.
4. Semua teks baru yang tampil ke pengguna wajib lewat sistem i18n dan punya terjemahan ID **dan** EN.
5. Tambahkan/ubah tes otomatis untuk logika (parsing JSON, dedupe .ics, filter tanggal, pluralisasi) bila proyek punya kerangka tes.
6. Di akhir, laporkan untuk setiap bug: penyebab, file yang diubah, cara verifikasi. Tandai bug yang tidak bisa direproduksi atau butuh keputusan pemilik.

---

## P1 — Data salah / fitur inti gagal

### BUG-01 · Ekstraksi tenggat dari ringkasan gagal (JSON)
- **Gejala:** Setelah meringkas file berisi tenggat ("Tugas: laporan praktikum dikumpulkan 10 November 2026", "UTS Biologi 17 November 2026 pukul 09.00"), muncul teks mentah di bawah ringkasan: `deadlines: could not parse the model JSON after 1 repair retry`. Akibatnya tidak ada saran jadwal, tanggal 10 & 17 Nov kosong di kalender, kartu "Tugas" tetap kosong. Padahal bagian "Dates & deadlines" di ringkasan berhasil menuliskan kedua tanggal itu.
- **Perbaikan yang diharapkan:**
  - Gunakan mode JSON / `response_format` / structured output jika API model mendukung; turunkan temperature untuk panggilan ini.
  - Sebelum `JSON.parse`/`json.loads`: buang pembungkus ```` ```json ````, ambil hanya blok `{...}`/`[...]` pertama, toleransi trailing comma.
  - Tetapkan skema tegas, mis. `[{ "title": str, "type": "tugas|ujian|acara|kegiatan", "date": "YYYY-MM-DD", "time": "HH:MM"|null }]`, dan validasi.
  - Fallback: jika tetap gagal, parse tanggal dari bagian "Tanggal & tenggat" ringkasan yang sudah ada (format Indonesia & Inggris).
  - Jangan pernah menampilkan pesan teknis ke pengguna; tampilkan pesan ramah ber-i18n (mis. "Tenggat tidak bisa dibaca otomatis.") dan log detailnya di server.
- **Selesai bila:** materi contoh di atas menghasilkan 2 saran di "Saran dari ringkasan" (Tugas 10 Nov, Ujian 17 Nov 09.00) dan tidak ada teks error mentah.

### BUG-02 · Jenis jadwal "Tugas" tidak tersimpan/terbaca
- **Repro:** Jadwal → Tambah jadwal → Judul "Kuis Biologi", Jenis **Tugas**, Lokasi "Ruang 101" → Simpan.
- **Aktual:** Muncul di "Kegiatan hari ini" dan "Acara mendatang"; kartu "Tugas" tetap "Belum ada tugas." Chip "Tugas" tetap terpilih setelah form direset.
- **Diharapkan:** Item tersimpan dengan `type = tugas` dan tampil di kartu "Tugas". Periksa pengiriman nilai jenis dari form, penyimpanan di backend, dan filter per kartu. Setelah simpan, reset chip Jenis ke default.

### BUG-03 · Impor .ics menghasilkan agenda ganda
- **Repro:** Jadwal → Impor dari file → upload `.ics` berisi satu VEVENT (`UID:tes-001@orvina`, "Praktikum Kimia", 5 Nov 2026 03:00Z, Lab 2).
- **Aktual:** "Praktikum Kimia" tersimpan 2× (2 titik di kalender, "2 agenda", dobel di semua daftar).
- **Diharapkan:** Satu event per `UID` (+ `RECURRENCE-ID` bila ada). Impor ulang file yang sama tidak menambah duplikat (upsert). Pastikan juga handler upload tidak terpanggil dua kali (mis. event `drop` + `change`, atau React StrictMode/efek ganda).

### BUG-04 · Label sumber agenda salah
- Agenda dari impor `.ics` diberi badge **"Dari ringkasan"**. Simpan field `source` yang benar (`manual` | `ringkasan` | `impor`) dan tampilkan label sesuai (mis. "Impor file" / "Imported").

### BUG-05 · "Kegiatan hari ini" menampilkan tanggal yang dipilih, bukan hari ini
- Hari ini Selasa 3 Nov; saat Kamis 5 dipilih di kalender, kartu "Kegiatan hari ini" berisi agenda Kamis 5 dan "Kuis Biologi" (hari ini) hilang.
- **Diharapkan:** Pilih salah satu dan konsisten: (a) kartu selalu berisi hari ini, atau (b) judul kartu berubah dinamis, mis. "Kegiatan Kamis, 5 Nov" bila tanggal lain dipilih. Default yang disarankan: (b).

### BUG-06 · Acara yang sudah lewat masih di "Acara mendatang"
- "Kuis Biologi" 3 Nov 08.00 masih muncul di "Acara mendatang" saat jam sudah lewat (malam hari). Filter dengan `start >= sekarang` memakai zona waktu pengguna, urutkan menaik.

### BUG-07 · Dashboard: ringkasan minggu ini saling bertentangan
- **Aktual (ID):** judul "1 agenda, 1 hari ini" tetapi subjudul "Tidak ada agenda minggu ini."
- **Aktual (EN):** "1 agenda items, 1 today" + "Nothing on the agenda this week."
- **Diharapkan:** Subjudul memakai sumber data yang sama dengan judul; teks kosong hanya muncul jika jumlah = 0. Gunakan pluralisasi i18n (EN: "1 agenda item" / "2 agenda items").

---

## P2 — Pesan, umpan balik, dan i18n

### BUG-08 · Kunci i18n mentah di Impor jadwal
- Area "Impor dari file" pernah menampilkan "Membaca file…" + `schedule.stage.queued` dan terlihat macet. Tambahkan terjemahan untuk semua kunci `schedule.stage.*` (ID & EN), pastikan status antrean berpindah ke selesai/gagal, dan beri timeout + pesan gagal bila proses tidak selesai.

### BUG-09 · Judul bagian ringkasan berbahasa Inggris
- Dengan "Bahasa output: Bahasa Indonesia", heading masih "TL;DR", "Content", "Key formulas", "Glossary", "Dates & deadlines", "Source map". Heading harus mengikuti bahasa output (mis. "Ringkasan singkat", "Isi", "Rumus kunci", "Glosarium", "Tanggal & tenggat", "Peta sumber"). Jika parser BUG-01 bergantung pada nama heading, sesuaikan agar mendukung kedua bahasa.

### BUG-10 · Rumus kimia tanpa subskrip / berpotensi dobel
- Rumus tampil sebagai `6CO2+6H2O+cahaya→C6H12O6+6O2` (angka tidak menjadi subskrip); saat disalin teksnya muncul dua kali.
- Gunakan KaTeX + ekstensi mhchem (`\ce{6CO2 + 6H2O -> C6H12O6 + 6O2}`) atau minta model menulis `\text{CO}_2`. Pastikan CSS KaTeX dimuat sehingga hanya satu versi yang terlihat (output MathML disembunyikan secara visual).

### BUG-11 · Source map mengarang nama bagian
- Source map menyebut bagian "Tenggat dan Jadwal" yang tidak ada di file sumber. Instruksikan model hanya memakai heading/halaman yang benar-benar ada di sumber; bila sumber tanpa heading, rujuk nama file atau nomor baris/halaman.

### BUG-12 · Kualitas glosarium
- Definisi melingkar, mis. "Klorofil: komponen yang dikandung kloroplas, disebut dalam materi fotosintesis." Perbarui prompt: definisi harus menjelaskan fungsi/arti singkat, bukan mengulang konteks kemunculan. (Perubahan prompt saja.)

### BUG-13 · Validasi form jadwal terlalu umum
- Simpan jadwal dengan judul kosong → "Permintaan tidak valid. Periksa kembali isianmu." Validasi di sisi klien dan tunjukkan kolom spesifik (mis. "Judul wajib diisi") di bawah input terkait. Pertahankan validasi server.

### BUG-14 · Forum: kirim pertanyaan tanpa mata kuliah tidak memberi umpan balik
- Judul + isi terisi, mata kuliah kosong → klik "Kirim pertanyaan" tidak terjadi apa-apa. Tampilkan pesan "Pilih mata kuliah" di bawah dropdown (atau jadikan mata kuliah opsional).

### BUG-15 · Tanya: pesan pengguna tidak langsung tampil
- Setelah Enter, gelembung pertanyaan pengguna tidak muncul dan teks tetap di kotak input selama "Orvina berpikir…"; baru muncul setelah jawaban datang.
- **Diharapkan:** Optimistic update — gelembung pengguna langsung tampil, input langsung dikosongkan, auto-scroll ke bawah; jika request gagal, tandai pesan gagal + tombol coba lagi dan kembalikan teks.

---

## P3 — Tampilan

### BUG-16 · Judul percakapan panjang meluber di sidebar Tanya
- Muncul scrollbar horizontal. Gunakan `overflow:hidden; text-overflow:ellipsis; white-space:nowrap` (+ `min-width:0` pada flex child) dan tooltip judul penuh.

### BUG-17 · Tombol menu (☰) di header tidak berfungsi di desktop
- Klik tidak mengubah sidebar. Implementasikan collapse/expand sidebar di desktop (simpan status di localStorage dalam try/catch), atau sembunyikan tombol pada breakpoint desktop.

### BUG-18 · Label orbit tertimpa penanda
- Di orbit Jadwal/Dashboard, label hari ("Kam 5", "Sel 3") tertutup lingkaran penanda bernomor. Geser label ke luar lingkaran (offset radial) atau beri latar/halo pada teks.

### BUG-19 · Kartu proyek & form proyek
- Kartu proyek "mtk" menampilkan kotak hitam kosong (thumbnail/preview kosong) — sembunyikan bila tidak ada isi.
- Saat klik "Proyek baru", input "Nama proyek" menempel/menimpa teks "Kumpulkan beberapa ringkasan dalam satu folder" — tambahkan jarak.
- Halaman detail proyek tidak punya tautan "Kembali" dan tidak ada item sidebar yang aktif — tambahkan breadcrumb/kembali ke Perpustakaan dan tandai "Perpustakaan" aktif.

### BUG-20 · Konsistensi nama
- Aplikasi menampilkan "Orvina", sedangkan nama Studio/repo "orviva". **Jangan ubah otomatis** — laporkan semua lokasi nama dan minta konfirmasi pemilik.

---

## P1 tambahan — Kalender tidak ter-update

### BUG-21 · Kalender tidak memperbarui diri setelah upload/impor
- **Gejala:** Setelah file jadwal (atau file materi yang berisi tenggat) selesai diproses, kalender, orbit minggu, kartu Kegiatan/Acara/Tugas, dan Dashboard tidak langsung menampilkan agenda baru; pengguna harus pindah halaman atau refresh.
- **Perbaikan yang diharapkan:**
  - Saat job impor/ekstraksi berstatus `done`, invalidasi & refetch semua data jadwal (kalender bulan, orbit minggu, ketiga kartu, "Saran dari ringkasan", statistik Dashboard). Gunakan satu sumber data/store bersama, bukan state lokal per komponen.
  - Pindahkan tampilan kalender ke bulan/minggu agenda pertama yang baru diimpor dan sorot sebentar item barunya.
  - Saran dari ringkasan yang diterima pengguna juga langsung muncul di kalender tanpa refresh.
  - Pastikan tidak ada cache usang (mis. respons GET dicache browser/proxy ModelScope — set `Cache-Control: no-store` untuk endpoint jadwal).
- **Selesai bila:** impor `jadwal_tes.ics` → dalam ≤2 detik setelah selesai, tanggal 5 Nov punya 1 titik dan agenda tampil di semua kartu tanpa refresh.

---

## Fitur baru

### FEAT-01 · Kolom "Catatan untuk AI" pada Impor jadwal
Tujuan: pengguna bisa memberi tahu AI bagian mana dari file yang harus diambil ke kalender.
- **UI:** Di bagian "Impor dari file" (Jadwal) dan opsi Ringkas Materi, tambahkan textarea **"Catatan untuk AI (opsional)"**, maks. 500 karakter + penghitung, placeholder contoh: *"Ambil hanya jadwal kelas B; abaikan hari libur; semua ujian masuk jenis Ujian; tugas di halaman 2 saja."*
- **Backend:** Kirim catatan bersama file ke job ekstraksi; sisipkan ke prompt ekstraksi sebagai instruksi pengguna yang **membatasi/menyaring** hasil (bukan menggantikan aturan sistem). Lindungi dari prompt injection: catatan hanya boleh memengaruhi pemilihan & kategorisasi item, tidak boleh mengubah format output JSON.
- **Langkah tinjau sebelum simpan:** Setelah ekstraksi, tampilkan daftar pratinjau (judul, jenis, tanggal, jam, lokasi, sumber halaman/baris) dengan checkbox per item, bisa diedit inline, tombol "Tambahkan ke kalender" dan "Batal". Item baru masuk kalender hanya setelah dikonfirmasi.
- Simpan catatan bersama riwayat impor agar bisa dipakai ulang ("Impor ulang dengan catatan yang sama").
- Format `.ics` tetap diparse secara deterministik (tanpa AI); catatan hanya dipakai untuk menyaring event `.ics` bila diisi. PDF/DOCX/XLSX/gambar memakai AI + catatan.
- **Selesai bila:** file berisi beberapa kelas + catatan "hanya kelas B" → pratinjau hanya memuat jadwal kelas B.

### FEAT-02 · Floating progress bar global (bertahan saat refresh)
Saat ini progress bar hilang di semua fitur, dan setelah refresh tidak ada indikator sama sekali.
- **Model job di server:** setiap proses panjang (Ringkas Materi, Impor jadwal, ekstraksi tenggat, sinkron Google Calendar, unggahan file) dibuat sebagai job dengan `job_id`, `type`, `status` (`queued|uploading|processing|done|failed|cancelled`), `stage` (kunci i18n), `progress` 0–100, `message`, `result_link`, `created_at`, `user_id`. Simpan di DB/penyimpanan persisten, bukan memori proses.
- **Klien:** komponen **floating di bagian bawah layar** (tengah-bawah atau kanan-bawah, di atas footer "Compliance Notice" ModelScope, tidak menutupi tombol utama), tampil di semua halaman. Isi per job: ikon jenis, nama file, tahap (teks terjemahan, bukan kunci mentah), persentase + bar, tombol Batal (bila didukung), dan setelah selesai tombol "Lihat hasil". Bisa diciutkan menjadi pil kecil "2 proses berjalan". Beberapa job ditumpuk.
- **Persisten saat refresh:** saat aplikasi dimuat, ambil `GET /jobs?status=active` (+ yang selesai < 5 menit) dan lanjutkan pemantauan via SSE/WebSocket atau polling 1–2 detik. Jangan bergantung hanya pada state React/localStorage.
- **Progres nyata:** unggahan memakai progres byte (XHR/`fetch` dengan stream); pemrosesan memakai tahap berbobot (mis. baca file 20%, ekstraksi 60%, simpan 20%). Jika tidak bisa dihitung, tampilkan bar indeterminate — jangan diam.
- **Gagal/timeout:** tampilkan pesan ramah + "Coba lagi"; job yang tidak bergerak > N menit ditandai gagal (ini juga menyelesaikan BUG-08).
- Saat job selesai, picu refresh data terkait (lihat BUG-21) dan notifikasi singkat (toast).
- Aksesibilitas: `role="progressbar"`, `aria-valuenow`, `aria-live="polite"` untuk perubahan status.

### FEAT-03 · Sinkronisasi ke Google Calendar (OAuth 2.0)
- **Alur OAuth:** Authorization Code + PKCE, dijalankan di **server** (client secret tidak boleh ada di frontend). Scope minimal: `https://www.googleapis.com/auth/calendar.events` (+ `calendar.readonly` hanya jika perlu daftar kalender untuk dipilih). `access_type=offline`, `prompt=consent` untuk mendapat refresh token.
- **Penting untuk ModelScope:** aplikasi berjalan di dalam iframe (`*.ms.fun` di dalam modelscope.ai). Google menolak halaman login di dalam iframe, jadi buka OAuth di **popup/tab baru** (`window.open`), lalu callback mengirim hasil ke jendela aplikasi via `postMessage` (validasi `origin`) dan menutup popup. Redirect URI: `https://jonathan-5960-orviva.ms.fun/api/google/callback` (sesuaikan dengan route sebenarnya) dan daftarkan persis di Google Cloud Console.
- **Rahasia:** baca `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `TOKEN_ENCRYPTION_KEY` dari environment/secrets ModelScope. Jangan commit ke repo. Simpan refresh token **terenkripsi** per pengguna. Gunakan parameter `state` acak untuk mencegah CSRF.
- **UI:** di halaman Jadwal (atau Pengaturan): tombol "Hubungkan Google Calendar", status terhubung (email akun), pemilih kalender tujuan (default: primary), toggle "Sinkron otomatis", tombol "Sinkronkan sekarang", dan "Putuskan" (revoke token + hapus dari DB).
- **Sinkron (Orvina → Google, satu arah dulu):** buat/ubah/hapus event Google saat agenda Orvina dibuat/diubah/dihapus. Simpan pemetaan `orvina_event_id ↔ google_event_id` agar tidak dobel; gunakan juga `extendedProperties.private.orvinaId`. Zona waktu `Asia/Jakarta`; event tanpa jam → all-day. Jenis (Tugas/Ujian/Acara/Kegiatan) → `colorId` berbeda + prefix opsional. Event dari impor `.ics` tetap membawa UID asli di `iCalUID` bila memungkinkan.
- **Opsional/sesudahnya:** impor event dari Google ke Orvina (dua arah) — buat di balik feature flag, jangan aktif default.
- **Error handling:** token kedaluwarsa → refresh otomatis; token dicabut (`invalid_grant`) → status "Terputus, hubungkan ulang"; rate limit 403/429 → retry dengan backoff. Setiap sinkron besar berjalan sebagai job di FEAT-02.
- **Catatan untuk pemilik (laporkan, jangan kerjakan sendiri):** pemilik perlu membuat OAuth Client di Google Cloud Console, mengaktifkan Google Calendar API, mengisi OAuth consent screen, dan menambahkan akun penguji selama aplikasi berstatus "Testing". Agent cukup menulis panduan langkahnya di README.
- **Selesai bila:** hubungkan akun → tambah agenda "Kuis Biologi" → muncul di Google Calendar pada jam yang sama; ubah jam di Orvina → ikut berubah; hapus → terhapus; impor ulang tidak membuat duplikat di Google.

---

## UI-REDESIGN · Ubah tampilan sesuai desain baru "Orvina Redesign"

Referensi visual: file `Orvina Redesign.html` (berisi 5 halaman × mode terang/malam) dan screenshot di folder `redesign_referensi/` (`dash.png`, `ringkas.png`, `perpus.png`, `forum.png`, `jadwal.png`, `dash_dark.png`, `jadwal_dark.png`). Data di desain (nama "Jonathan", "Proyek BYON", dll.) hanya contoh — **jangan di-hardcode**, ambil dari data nyata.

**Aturan umum redesign**
- **Tanpa animasi:** jangan tambahkan transisi, animasi masuk, efek hover yang bergerak, shimmer, atau parallax. Perubahan state (hover/aktif/terpilih) cukup ganti warna/border secara instan. Orbit di Dashboard statis.
- Ubah tampilan saja kecuali disebut lain; jangan mengubah logika yang sudah diperbaiki di BUG/FEAT di atas.
- Semua warna lewat CSS variables (token di bawah) dengan nilai terang dan malam; toggle tema mengganti set token, bukan menimpa per komponen.
- Semua teks lewat i18n (ID & EN).

### 1. Design token

**Tipografi:** font **Poppins** (400, 500, 600, 700) — muat dari Google Fonts atau self-host; fallback `system-ui, sans-serif`.

| Peran | Ukuran / tebal |
|---|---|
| Judul halaman (H1) | 30px / 700, warna teks utama |
| Subjudul halaman | 14px / 400, warna teks sekunder |
| Judul kartu | 18px / 600 (judul besar kartu proyek 22px / 700) |
| Angka hero Dashboard | 76px / 700 |
| Angka/jam besar | 34–40px / 700 ("13.00") |
| Teks isi | 14px / 400–500 |
| Teks kecil / meta | 12–13px / 400 |
| Label chip | 11–11.5px / 600 |

Format waktu & rentang memakai titik dan kata "sampai": `13.00`, `13.00 sampai 14.40`, `2 sampai 8 November` (EN: `1:00 PM`, `to`).

**Warna — mode terang**

| Token | Nilai | Dipakai untuk |
|---|---|---|
| `--bg-page` | `#EDEDF1` | latar area konten |
| `--bg-sidebar` | `#F6F7F9` | latar sidebar, dipisah garis kanan `--border` |
| `--bg-card` | `#FFFFFF` (boleh gradien sangat halus ke `#F8F8FA`) | kartu |
| `--bg-tile` | `#F2F3F6` | sel kalender, tile hari, opsi |
| `--bg-tile-2` | `#ECEDF1` | chip netral, hover |
| `--text` | `#111216` | teks utama, tombol hitam |
| `--text-2` | `#62656E` | teks sekunder |
| `--text-3` | `#55585F` | meta |
| `--accent` | `#1F4FF5` | tombol utama, link, item aktif, Tenggat |
| `--accent-soft` | `#E9EEFF` | latar chip Kelas, kotak info, menu aktif |
| `--accent-mid` | `#7C97FF` | titik "Belajar" di orbit |
| `--sun` | `#F5B82E` (halo `#FBEFD0`) | matahari orbit |
| `--border` | `#E8E9EE` | garis tipis, input |

**Warna — mode malam**

| Token | Nilai |
|---|---|
| `--bg-page` | `#08090B` |
| `--bg-sidebar` | `#0E0F12` |
| `--bg-card` | `#141519` |
| `--bg-tile` | `#1B1C21` |
| `--bg-tile-2` | `#24252B` |
| `--text` | `#F3F4F7` |
| `--text-2` | `#9A9DA8` |
| `--text-3` | `#B3B6C0` |
| `--accent` | `#1F4FF5` (teks link `#5B7CFF`, teks di latar aksen-lembut `#A9BBFF`) |
| `--accent-soft` | `#16224F` |
| `--border` | `#232429` |

**Bentuk & bayangan**
- Radius: kartu besar `26px`; tile/sel kalender/opsi `14px`; input & tombol `12px`; chip `9px`; tombol pil/segmented `30px`; avatar & tombol ikon bulat `50%`.
- Bayangan kartu: terang `0 24px 44px -32px rgba(16,18,36,.28)`; malam `0 24px 44px -30px rgba(0,0,0,.85)`. Elemen terpilih: `inset 0 0 0 1.5px var(--accent)` atau border `2px solid var(--accent)`.
- Spasi: padding konten halaman `44px` kiri/kanan, `32px` atas; jarak antar kartu `24px`; padding kartu `28–32px`.

**Komponen dasar**
- **Tombol utama:** latar `--accent`, teks putih 14/600, tinggi 44px, radius 12px, ikon "+" di kiri untuk aksi tambah.
- **Tombol hitam (sekunder kuat):** latar `--text`, teks putih (malam: latar `--bg-tile-2`, teks `--text`) — dipakai untuk "Pilih berkas".
- **Tombol outline:** latar kartu, border `--border`, teks `--text`.
- **Tombol ikon bulat:** 44px, latar kartu, bayangan kartu (toggle tema, prev/next kalender, tombol × tutup saran).
- **Segmented control:** wadah `--bg-tile` radius 12–14px, segmen aktif latar kartu putih + teks aksen (terang) / latar `--bg-tile-2` (malam). Dipakai untuk Bulan/Minggu, tingkat detail, tab Forum.
- **Pemilih bahasa ID/EN:** segmented kecil di kanan atas; segmen aktif **latar hitam `--text`, teks putih** (gunakan ini konsisten di semua halaman — di file desain Dashboard memakai biru, samakan ke hitam).
- **Chip filter:** pil radius 30px, border `--border`, teks 13/500; aktif = latar `--text`, teks putih.
- **Chip kategori agenda:** Kelas = latar `--accent-soft`, teks `--accent`; Belajar = latar `--bg-tile-2`, teks `--text-3`; Tenggat = latar `--accent`, teks putih. Tag mata kuliah di Forum mengikuti pola yang sama; tag "Terjawab" = latar `--text`, teks putih.
- **Input/select/textarea:** tinggi 46px, latar kartu, border `--border`, radius 12px, placeholder `--text-2`; fokus = border `--accent` (tanpa glow beranimasi).

### 2. Kerangka aplikasi (semua halaman)
- **Sidebar kiri lebar 272px**, penuh tinggi, latar `--bg-sidebar`, garis kanan `--border`.
  - Atas: logo ikon orbit biru + teks "Orvina" 22/700.
  - Menu: Dashboard, Ringkas Materi, Perpustakaan, Jadwal, Forum. Item: ikon garis 18px + teks 14/500, tinggi 46px, radius 14px. **Aktif:** latar kartu putih + bayangan kartu, ikon & teks `--accent` 600 (malam: latar `--accent-soft`, teks `#A9BBFF`). Samakan gaya aktif ini di semua halaman.
  - Bawah (dipisah garis): avatar bulat 36px latar `--accent-soft` berisi inisial, nama 14/600, username 12px `--text-2`, tombol teks "Keluar" di kanan.
  - **Menu "Tanya" tidak ada di desain.** Jangan hapus fiturnya: pindahkan akses Tanya AI ke tombol "Tanya Orvina" di halaman detail ringkasan & detail proyek, dan sebagai tab "Chat" di Forum bila cocok. Laporkan keputusan penempatan ke pemilik.
- **Header halaman:** kiri H1 + subjudul; kanan berurutan: tombol aksi utama halaman (jika ada), pemilih ID/EN, tombol bulat toggle tema (ikon bulan di mode terang, matahari di mode malam).
- **Tombol ☰ dihapus di desktop** (menyelesaikan BUG-17); hanya muncul di layar < 768px untuk membuka sidebar sebagai drawer.
- **Responsif:** desain dibuat untuk lebar 1440px. ≥1280px: tata letak dua kolom seperti desain (kolom kanan ±320px). 768–1279px: kolom kanan turun ke bawah kolom utama. <768px: sidebar jadi drawer, kartu satu kolom, grid kalender tetap 7 kolom dengan chip disembunyikan menjadi titik.
- Floating progress bar (FEAT-02) mengikuti token ini: kartu `--bg-card`, radius 18px, bayangan kartu, bar `--accent` di atas track `--bg-tile`, posisi bawah-tengah area konten (tidak menutupi sidebar).

### 3. Dashboard (`dash.png`, `dash_dark.png`)
Grid: kolom kiri lebar (±740px) + kolom kanan (±320px).
- **Header:** "Halo, {nama}" + tanggal lengkap ("Selasa, 3 November 2026").
- **Kartu hero minggu ini** (kiri atas): 
  - Kiri: label "Minggu ini, 2 sampai 8 November" 14px `--text-2`; angka total agenda 76/700 + kata "agenda" 22/600 `--accent`; tiga kolom kecil "Kelas / Belajar / Tenggat" (label 12px, angka 22/700); garis pemisah; jam agenda berikutnya 40/700 ("13.00"); label "Kelas berikutnya, hari ini" 12/600 `--accent`; nama agenda 14/600. Bila tidak ada agenda, tampilkan "0 agenda" dan teks "Minggu ini masih kosong" (jangan saling bertentangan — BUG-07).
  - Kanan: **orbit statis** — elips utama + elips miring tipis, matahari kuning di tengah dengan halo, 7 titik hari berlabel (Sen…Min). Hari ini = cincin ganda biru + label tebal. Titik diberi warna sesuai kategori agenda hari itu: Kelas = lingkaran kosong bergaris biru, Belajar = titik `--accent-mid`, Tenggat = titik `--accent`. Legenda di bawah orbit. Label tidak boleh tertimpa titik (BUG-18).
- **Kartu "7 hari ke depan"** (kiri bawah): link kanan "Buka jadwal lengkap". Tujuh tile sejajar (radius 14px, latar `--bg-tile`): nama hari 12px, tanggal 22/700, chip kategori agenda utama hari itu (judul singkat). Hari ini = latar kartu + border 2px `--accent`. Tile bisa diklik → membuka Jadwal pada tanggal itu. Caption di bawah 13px `--text-2` menjelaskan sumber tenggat.
- **Kartu "Perpustakaan"** (kanan atas): link "Lihat semua". Daftar 4 proyek terbaru: ikon folder dalam kotak 40px radius 10px (warna bergiliran: aksen solid, aksen lembut, abu, hitam), nama 14/600, meta "2 ringkasan, diperbarui 11 jam lalu" 12px, chevron ›.
- **Kartu "Forum"** (kanan bawah): link "Buka chat" (atau "Buka forum"). Daftar 4 percakapan/diskusi terbaru: avatar inisial bulat 40px, nama 14/600, waktu kanan 12px, pratinjau pesan satu baris dengan ellipsis, badge jumlah belum dibaca (bulat 20px, latar `--accent`, teks putih).
- Statistik lama ("1 ringkasan tersimpan / dokumen / agenda") dan tombol besar "Ringkas materi baru / Buka perpustakaan" diganti oleh kartu-kartu di atas.

### 4. Ringkas Materi (`ringkas.png`)
Kiri lebar + kanan "Pengaturan" ±340px.
- **Kartu "Berkas":** dropzone border putus-putus `--border`, radius 18px, latar `--bg-tile`; di tengah kotak ikon unggah 72px (latar kartu, bayangan), judul "Tarik berkas ke sini" 16/600, keterangan format, tombol hitam "Pilih berkas". Di bawahnya daftar berkas: baris kartu radius 14px berisi badge jenis berkas 40px (PDF = aksen lembut, DOCX/lain = abu), nama 14/600, status "2,4 MB, siap diringkas" atau **bar progres unggah inline** dengan persen biru di kanan, tombol × hapus.
- **Kartu "Bentuk ringkasan":** subjudul "Pratinjau kecil menunjukkan bentuk hasil yang akan kamu dapat." Grid 2×2 opsi: tile `--bg-tile` radius 18px, kiri thumbnail kertas mini 70×86px (garis-garis yang menggambarkan bentuk hasil; garis aksen biru menandai heading/rumus), kanan judul 15/600 + deskripsi 13px. Terpilih = latar kartu + border 2px `--accent`.
- **Kartu "Pengaturan":** Judul (input), **Simpan ke proyek** (select), Bahasa hasil (select), **Tingkat detail** (segmented Ringkas / Standar / Mendalam), kotak info latar `--accent-soft` radius 14px berisi checkbox **"Masukkan tenggat ke Jadwal"** + penjelasan (terhubung ke BUG-01), **Catatan untuk AI / Instruksi tambahan** (textarea, FEAT-01), tombol utama lebar penuh "Buat ringkasan".
  - Field "Mata kuliah" lama: pertahankan datanya, tapi tampilkan sebagai pilihan proyek/mata kuliah dalam satu select "Simpan ke proyek" **atau** tetap sebagai select terpisah di bawah Judul — laporkan pilihanmu. Jangan hilangkan filter mata kuliah di Perpustakaan/Forum.
- **Kartu "Ringkasan terakhir"** (kanan bawah): link "Perpustakaan"; daftar judul 14/600 + waktu relatif kanan, dipisah garis.

### 5. Perpustakaan (`perpus.png`)
- Header kanan: tombol utama "+ Proyek baru".
- Baris pencarian (input lebar, ikon kaca pembesar) + chip filter mata kuliah/bahasa (Semua aktif hitam).
- **Bagian "Proyek":** grid 3 kolom kartu berbentuk **map/folder**: tab kecil di kiri atas (warna bergiliran aksen, aksen-mid, abu, hitam) menyatu dengan garis atas kartu; di dalam, maksimal 2 "kertas" bertumpuk berisi judul ringkasan (kotak putih radius 8px, bayangan tipis, teks 12px); jika kosong, kotak putus-putus bertulis "Kosong". Di bawahnya nama proyek 22/700 dan meta "2 ringkasan, diperbarui 11 jam lalu". Kartu terakhir "Proyek baru" = border putus-putus, ikon + dalam lingkaran putih. Hilangkan kotak hitam kosong lama (BUG-19).
- **Kartu "Diperbarui terakhir":** tabel dengan kolom Judul (ikon dokumen dalam kotak aksen-lembut + judul 14/600), Proyek, Bentuk, Diperbarui, menu ⋮ (Ganti nama, Pindah proyek, Unduh .md, Hapus). Baris dipisah garis `--border`, tinggi ±62px.

### 6. Forum (`forum.png`)
- Tab segmented di bawah header: **Komunitas** (aktif = latar aksen, teks putih), Chat, Unggah soal, Unggah jawaban, FAQ.
- Baris pencarian + tombol utama "Ajukan pertanyaan".
- **Daftar diskusi:** kartu radius 18px; kiri kolom angka jumlah jawaban 26/700 + label "jawaban" 12px; kanan chip (mata kuliah, "Terjawab"), judul 16/600, meta "Dimas, 2 jam lalu" 13px `--text-2`.
- **Kartu kanan "Komunitasmu":** daftar grup (avatar inisial, nama 14/600, "5 pesan baru" 12px), tombol outline lebar "Cari komunitas lain".
- **Batas cakupan:** tab Chat, Unggah soal, Unggah jawaban, FAQ, dan Komunitas/grup **belum punya backend**. Buat kerangka UI-nya saja dengan empty state ("Segera hadir") dan laporkan; jangan membangun sistem chat/komunitas tanpa persetujuan pemilik. Tab Komunitas menampilkan daftar pertanyaan forum yang sudah ada.

### 7. Jadwal (`jadwal.png`, `jadwal_dark.png`)
Kiri lebar (±690px) + kanan ±370px.
- Header kanan: tombol utama **"+ Agenda baru"** → membuka **modal** berisi form tambah jadwal (Judul, Jenis, Tanggal, Jam mulai–selesai, Lokasi, Ulangi) dengan validasi per kolom (BUG-13). Form lama yang selalu tampil di bawah halaman dihapus.
- **Kartu unggah** (kiri atas): border putus-putus, kotak ikon kalender-unggah 64px, judul "Unggah silabus, KRS, atau pengumuman" 16/600, deskripsi 13px, tombol hitam "Pilih berkas". Tambahkan di kartu ini textarea kecil **"Catatan untuk AI"** (FEAT-01) yang muncul setelah berkas dipilih, beserta tombol "Proses".
- **Kartu "Saran dari ringkasan"** (kanan atas): latar gradien lembut `--accent-soft` → kartu, border tipis aksen (malam: latar `#101A40`, border `--accent`). Tiap saran: judul 14/600, "Jum, 13 November, dari BYON SCRIPT" 12px, tombol utama kecil "Tambahkan", tombol bulat × "Abaikan". Juga dipakai untuk pratinjau hasil impor (FEAT-01).
- **Kartu kalender:** 
  - Baris atas: dua tombol bulat ‹ ›, judul bulan 26/700, tombol outline "Hari ini", segmented "Bulan / Minggu".
  - Header hari Sen…Min 12px `--text-2`.
  - Grid 7 kolom, **ketujuh kolom harus muat penuh di kartu** (di file desain kolom Minggu terpotong — itu kesalahan desain, jangan ditiru). Sel: tile `--bg-tile` radius 14px, tinggi ±106px, nomor tanggal 13/600 kiri atas, maksimal 1–2 chip agenda (teks dipotong ellipsis) + "+N" bila lebih. Hari di luar bulan: tanpa tile, angka `--text-2`.
  - **Hari ini:** sel latar kartu + border 2px `--accent`, nomor dalam lingkaran biru terisi 28px teks putih.
  - Klik sel → filter "Semua agenda" ke tanggal itu; tampilan Minggu = 7 kolom dengan slot jam.
- **Kartu "Semua agenda"** (kanan): chip filter Semua / Kelas / Belajar / Tenggat. Daftar dikelompokkan per tanggal mulai **hari ini** (agenda yang sudah lewat tidak tampil — BUG-06): heading "Sel, 3 November" 12/600 + pil "Hari ini" (latar aksen, teks putih). Tiap baris: jam 16/700 di kiri (lebar tetap 56px), judul 15/600, chip kategori berisi rentang ("Kelas, 13.00 sampai 14.40" / "Tenggat, 09.00"), lalu link sumber biru 12px ("Dari ringkasan biologi" / "Dari impor KRS.pdf" — BUG-04). Klik baris → detail agenda (edit, hapus, unduh .ics, status sinkron Google). Baris dipisah garis.
- Kartu lama "Kegiatan hari ini / Acara mendatang / Tugas" dan orbit di halaman Jadwal **diganti** oleh kartu "Semua agenda" + filter (orbit tetap di Dashboard). Logika BUG-02/05/06 tetap berlaku pada daftar & filter baru.
- **Kategori agenda:** desain memakai **Kelas, Belajar, Tenggat**, sedangkan aplikasi sekarang memakai Kegiatan, Acara, Tugas, Ujian. Usulan pemetaan: `kelas` (baru, bisa berulang mingguan), `belajar` ← Kegiatan, `tenggat` dengan subjenis `tugas | kuis | ujian` ← Tugas/Ujian, dan Acara → `belajar` atau tetap kategori tersendiri. Buat migrasi data lama, gunakan pemetaan yang sama di ekstraksi AI dan Google Calendar (FEAT-03). **Konfirmasi pemetaan Acara ke pemilik sebelum migrasi.**

### 8. Mode malam (`dash_dark.png`, `jadwal_dark.png`)
- Struktur identik, hanya token yang berganti (tabel di bagian 1).
- Tombol hitam berubah jadi latar `--bg-tile-2` dengan teks terang; chip Kelas berubah jadi latar `--accent-soft` (#16224F) dengan teks `#A9BBFF`; avatar kontras tinggi (putih dengan teks hitam) tetap boleh untuk variasi.
- Pastikan kontras teks ≥ 4.5:1 untuk teks isi di kedua mode.

### Selesai bila
- Kelima halaman di 1440px, mode terang dan malam, cocok dengan screenshot referensi (tata letak, warna, radius, tipografi) tanpa animasi.
- Kalender menampilkan 7 kolom penuh; label orbit tidak tertimpa.
- Tidak ada fitur lama yang hilang (Tanya AI, mata kuliah, ganti nama, unduh .md, hapus, impor .ics, progress bar, sinkron Google).
- Tampilan tetap rapi di 1024px dan 390px (lebar ponsel) tanpa scroll horizontal.

---

## Data uji untuk verifikasi
- `data_uji/materi_fotosintesis.txt` — materi fotosintesis dengan 2 tenggat (10 Nov 2026 tugas, 17 Nov 2026 09.00 ujian).
- `data_uji/jadwal_tes.ics` — 1 VEVENT "Praktikum Kimia", `UID:tes-001@orvina`, 2026-11-05 03:00–04:00 UTC (10.00–11.00 WIB), lokasi Lab 2.

## Checklist akhir
- [ ] Ringkas `materi_fotosintesis.txt` → heading berbahasa Indonesia, rumus bersubskrip, tanpa error mentah, 2 saran tenggat muncul.
- [ ] Impor `jadwal_tes.ics` dua kali → tetap 1 agenda, label "Impor file", jam 10.00–11.00.
- [ ] Tambah jadwal jenis Tugas → muncul di kartu "Tugas".
- [ ] Pilih tanggal lain → kartu kegiatan konsisten dengan judulnya; acara lewat tidak ada di "Acara mendatang".
- [ ] Dashboard ID & EN → teks jumlah agenda konsisten dan pluralisasi benar.
- [ ] Tanya → pesan pengguna langsung tampil, judul panjang terpotong rapi.
- [ ] Forum/Jadwal → pesan validasi spesifik per kolom.
- [ ] Setelah impor/ringkas selesai, kalender & Dashboard ter-update tanpa refresh (BUG-21).
- [ ] Catatan "hanya kelas B" menyaring hasil ekstraksi; pratinjau muncul sebelum disimpan (FEAT-01).
- [ ] Floating progress bar muncul di bawah untuk Ringkas, Impor, dan Sinkron; tetap tampil dan melanjutkan progres setelah halaman di-refresh (FEAT-02).
- [ ] Google Calendar: hubungkan via popup, buat/ubah/hapus agenda tersinkron tanpa duplikat, putuskan berfungsi, tidak ada secret di frontend/repo (FEAT-03).
- [ ] UI-REDESIGN: kelima halaman (terang & malam) sesuai referensi, tanpa animasi, kalender 7 kolom penuh, responsif di 1024px & 390px; menu Tanya tetap dapat diakses; pemetaan kategori Kelas/Belajar/Tenggat sudah dikonfirmasi.
- [ ] Semua teks baru ada di ID & EN; tidak ada kunci i18n mentah.
- [ ] Fitur yang sudah berjalan (lihat Aturan kerja no. 3) tetap berjalan.
