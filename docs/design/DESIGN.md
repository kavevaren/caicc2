# Orvina: UI and motion spec (v5, React)

Visual source of truth, saved in the repo as `docs/design/DESIGN.md`. The static reference is `docs/design/dashboard-mockup.html` (keep it unchanged): match its layout, spacing, tokens and copy, then add the motion below. Functional content of each page: SPEC §8.

**The one idea: your week is an atom.**
- You are the nucleus, and your days are electrons on an orbit.
- Open a day and it becomes its own atom, whose electrons are that day's events.
- The same atom appears in the logo, loaders, progress indicators and login background, so brand and product feel like one thing.

---

## 1. Tokens

### 1.1 Colour (`web/src/styles/tokens.css`; contrast verified, WCAG AA; never invent new colours)

| Token | Light | Dark | Use |
|---|---|---|---|
| `--primary` | #1B6CA8 | #4DA8DA | main buttons, links, active nav, event electrons |
| `--primary-hover` | #15588A | #6BBDE8 | |
| `--on-primary` | #FFFFFF | #12121A | text on primary (white fails in dark) |
| `--primary-tint` | #E7F0F7 | #1B2E3E | chips, active nav, "you" rows |
| `--accent` | #F4A261 | #F4A261 | nucleus, today ring. **Decorative only, never text, never the only signal** |
| `--success` / `--success-tint` | #2D6A4F / #E6F2EC | #52B788 / #1A2E27 | |
| `--warning-text` / `--warning-tint` | #8A6100 / #FBF3DC | #E9C46A / #2E2A1C | |
| `--danger` / `--on-danger` / `--danger-tint` | #C0392B / #FFFFFF / #FBE9E7 | #F06A5E / #12121A / #3A2024 | |
| `--text` | #1A1A2E | #E8E8F0 | |
| `--muted` | #5A5A72 | #9898B0 | meta text, labels |
| `--bg` | #FAFAF7 | #12121A | page |
| `--surface` | #FFFFFF | #1E1E2E | cards |
| `--border` | #E2E2DC | #2E2E42 | card edges |
| `--border-strong` | #8E8EA3 | #6E6E8C | control edges, hollow electrons |
| `--orbit` | #CBD9E6 | #2F4A60 | orbit rings |

Theme lives on `<html data-theme="light|dark">`. The default follows `prefers-color-scheme`; the header toggle overrides it and is saved to the user's settings.

### 1.2 Type, space, shape
- **Fonts:** Outfit 500/600/700 (headings, numbers, logo), Inter 400/500/600 (body), self-hosted via `@fontsource` (no Google Fonts request; works in China).
- **Scale (px):** page title 28 · hero 30 · card title 18 · body 15 · meta 13 · chip 12. Tabular figures for numbers.
- **Space:** 4 · 8 · 12 · 16 · 24 · 32. **Radius:** card 16 · control 10 · small 6 · chip 999.
- **Controls:** at least 44 px tall; `:focus-visible` outline 3 px `--primary`, offset 2 px.
- **Icons:** `lucide-react`, stroke 1.8, size 20 (nav, buttons) or 16 (chips, lists). No emoji anywhere.

### 1.3 Motion tokens (`web/src/motion/tokens.ts`)

| Token | Value | Use |
|---|---|---|
| `fast` | 150 ms | hover, press, toggles |
| `base` | 240 ms | page enter, card enter, tabs |
| `slow` | 400 ms | crossfades, list reorders |
| `ease` | `cubic-bezier(.2,.8,.2,1)` | all tweens |
| `zoom` | spring `{stiffness:120, damping:20, mass:1}` (~600 ms) | atom zoom |
| `stagger` | 40 ms cards, 60 ms electrons | |
| `orbitPeriod` | 90 s per revolution | week atom idle rotation |

Animate only `transform`, `opacity` and the SVG `viewBox`. Never animate layout properties in loops.

---

## 2. App shell
- **Sidebar** (248 px, sticky):
  - logo lockup (icon A + "Orvina");
  - nav with lucide icons, in this order: Dashboard `LayoutDashboard` · Ringkas Materi `FileText` · Rekam & Transkrip `Mic` · Jadwal `CalendarDays` · Forum `MessagesSquare` · Leaderboard `Trophy` · Perpustakaan `Library` · Notifikasi `Bell` (unread badge) · Profil & Pengaturan `Settings`;
  - active item: `--primary-tint` background, icon in `--primary`;
  - user block at the bottom: avatar, name, real points, "Keluar".
- **Header** on every page:
  - left: title + subtitle;
  - right: language switch (`ID` / `EN` / `中文`), bell with count, theme toggle (sun/moon).
- **≤ 860 px:** the sidebar becomes a drawer (slides in over 200 ms, with a scrim; Esc closes it), and a menu button appears in the header.
- **Page transition:** fade + rise 8 px (`base`), no exit animation.
- **Favicon:** icon D. **Tab title:** `<Page> · Orvina`.
- **Health banner:** if `/api/health` reports `modelscope: invalid_token`, a full-width `--danger-tint` banner says "Token ModelScope tidak valid. Periksa MODELSCOPE_TOKEN." If `engine: starting`, a quiet `--primary-tint` banner says "Mesin AI sedang disiapkan…" with an AtomLoader.

---

## 3. The atom system (`web/src/components/atom/`)

All atoms are SVG React components. One hook `useOrbit()` provides the animated angle (one shared `requestAnimationFrame`), and one function `project(angle)` gives position, scale, opacity and depth, so every atom looks the same.

### 3.1 Geometry (hero, viewBox `0 0 400 200`)
- **Nucleus:** (200, 105), r 11, `--accent`. It is the user.
- **Main orbit:** ellipse rx 165, ry 62, stroke `--orbit` 2 px.
- **Second orbit:** rx 150, ry 40, rotated −18°, 1.5 px, opacity .5. It counter-rotates (period 140 s) and carries nothing.
- **Days:** day k (0 = today … 6) has base angle `a_k = 120° + k·360°/7`, at `x = 200 + 165·cos a`, `y = 105 + 62·sin a`.
- **Depth:** `d = sin a`; scale `0.8 + 0.2·(d+1)/2`; opacity `0.55 + 0.45·(d+1)/2`.
- **Draw order:** electrons with `d < 0`, then the nucleus, then electrons with `d ≥ 0`, re-sorted every frame so electrons pass behind and in front of the nucleus.

### 3.2 Electron states

| State | Look |
|---|---|
| Day with events | filled `--primary`, r 7 (r 8 if ≥ 3 events) |
| Free day | `--surface` fill, `--border-strong` 1.5 stroke, r 5 |
| Today | + `--accent` ring r 13, stroke 3 |
| Hover / focus | scale 1.25, `--primary` halo (opacity .2, r +6), tooltip card |

Labels (`Kam`, `Jum` …, from i18n) sit 22 px outward along the radius. Today's label is bold `--text`, the others `--muted`; labels fade to .6 when their electron is behind the nucleus.

### 3.3 Week atom motion
- **Idle:** rotation of `360°/orbitPeriod` per second; the nucleus breathes (scale 1 → 1.06 → 1 over 4 s).
- **Hover over the atom:** rotation eases to 0 in 300 ms and resumes on leave.
- **Scroll spin:** `extra = clamp(|scrollVelocity| / 1500, 0, 1) × 40°/s`, eased back with a spring.
- **Scroll dock:** as the hero leaves the viewport, the atom scales 1 → 0.85 and fades 1 → 0.6.
- **Entrance:** rings draw in (`pathLength` 0 → 1, 600 ms), then electrons fly out from the nucleus (stagger 60 ms).
- **Pause** all loops when the atom is off screen (`useInView`) or the tab is hidden.

### 3.4 Zoom into a day (signature interaction)
Triggered by click, tap, or Enter/Space on an electron. The state lives in the URL (`?day=2026-10-30`).
1. Rotation stops. Other electrons and labels fade out (`base`).
2. The `viewBox` springs (`zoom`) from `0 0 400 200` to a 120 × 60 box around the electron.
3. Halfway, the electron morphs (`layoutId`) into the **day atom** nucleus (r 16, `--primary`).
4. The day's events pop out onto their orbit (rx 150, ry 70), stagger 60 ms.
   - **Angle = time of day:** `−90° + 360° × minutes/1440`. Events bob ±2 px (3 s, phase offset per event); they do not orbit.
   - **Colour by source:** Google `--primary`, from a summary `--success`, manual `--border-strong` outline. A small icon inside repeats the source, so colour is never the only signal.
   - **Today:** a thin `--accent` "now" hand.
   - **Labels:** time (`13.00`, Outfit 600) + title (≤ 22 characters).
5. A side panel slides in (a bottom sheet on mobile) with the event list. Hovering a row highlights its electron and vice versa.
6. **Back:** Esc, the panel's back button, clicking the nucleus, or the browser back button. The animation reverses.

A free day shows a dashed empty orbit + "Hari ini kosong. Mau tambah agenda?" with a button.

### 3.5 Schedule page
- **Desktop:** a sticky day atom (360 × 360) on the left; the 30-day list grouped by day on the right.
- **Day sync:** an `IntersectionObserver` picks the active day. On change, the events collapse into the nucleus (150 ms), the nucleus pulses, and the new events pop out (stagger 60 ms). The animation is direction-aware: scrolling down enters from the right, scrolling up from the left.
- **Week ring** above the atom: 7 dots with the active day highlighted; clicking a dot scrolls to that day.
- **Event link:** clicking an event electron scrolls to its row and flashes it (`--primary-tint`, 600 ms).
- **Mobile:** a sticky 140 px strip (small atom + date + count) above the list.

### 3.6 Atom everywhere else
- **`AtomLoader`** (24/32/48 px): the logo's two ellipses counter-rotating (1.6 s) with a pulsing core. It replaces every spinner.
- **`StageAtom`:** pipeline stages as electrons on one orbit. Done stages are `--primary` with a check, the current one pulses `--accent`, future ones are hollow. The stage name and elapsed time sit below. It is driven by the job's SSE events.
- **Login / Register:** a 600 px atom behind the card at opacity .08, 90 s period. The card rises 12 px and fades in.
- **Empty states:** a small static atom with one hollow electron.
- **Leaderboard:** your row has a mini atom ring around the avatar.

---

## 4. Pages

Every page has:
- the header;
- content in cards;
- **exactly one primary button**;
- chips for subject and source;
- relative times in muted 13 px;
- math with KaTeX;
- skeletons while loading;
- empty states that say what to do next.

- **4.1 Login · Daftar · Onboarding.**
  - A centred card (max 420 px) with the lockup, the tagline "Belajar bersama, paham lebih dalam", Masuk / Daftar tabs, and the language switch in the corner.
  - Field-level errors, including "Setujui syarat dan ketentuan untuk mendaftar".
  - Onboarding: 3 steps in the same card with a 3-electron step indicator: language → subjects (chips + "Tambah mata kuliah") → Google (skippable). Steps slide horizontally (`base`); finishing lands on the Dashboard entrance.
- **4.2 Dashboard.** Matches the mockup:
  - header;
  - hero "Minggu ini": text left (count, next event in a tinted box with an accent pin, two secondary buttons), week atom right; zooming happens inside the hero and the left text crossfades to that day's summary;
  - stat strip: one card, 4 cells, numbers count up when visible, a points ring that draws in;
  - quick actions: one row of 3, "Ringkas materi baru" primary;
  - columns 3:2 whose cards enter on scroll (once, rise 12 px, stagger 40 ms).
- **4.3 Ringkas Materi.**
  - Upload card + Opsi card side by side (stacked under 1100 px).
  - The drop zone has a dashed border that turns `--primary` on drag-over; file chips show type icon, size and remove.
  - Style options are segmented cards. The primary button is "Ringkas".
  - While running: the StageAtom with "Membaca file", "Memilih gambar penting", "Meringkas bagian", "Menyusun ringkasan", "Memeriksa format", "Mencari tenggat".
  - Result tabs: Ringkasan · Gambar · Sumber · Ekspor (animated underline), plus a collapsible "Di balik layar".
- **4.4 Rekam & Transkrip.**
  - Title + subtitle.
  - Segmented control: Rekam · Unggah.
  - Rekam: a 72 px record button with a live level ring, a timer, and stop. Inside the Studio iframe with the mic blocked, the button is replaced by a secondary "Buka di tab baru" button and one line of explanation.
  - Unggah: one drop zone for media or a transcript file (.srt, .vtt, .txt); the file chip shows which kind was detected.
  - Result tabs: Transkrip · Terjemahan · Ringkasan · Keputusan · Action items (checklist; dated items get "Tambah ke Jadwal").
- **4.5 Jadwal.**
  - The layout from 3.5.
  - "Agenda baru" opens a side sheet (end defaults to start + 1 h; end ≤ start shows "Waktu selesai harus setelah waktu mulai"). Saving pops the new electron into the atom.
  - Suggestions sit in a tinted card with Terima / Abaikan; accepted ones fly into the atom.
  - The Google card sits on top.
- **4.6 Forum.**
  - List: search, filter chips, question rows ("Belum ada jawaban" in `--warning-text`); the empty state CTA is "Ajukan pertanyaan".
  - Ask: title with a live counter (10–150), similar questions appearing under the title, write/preview tabs; primary button "Kirim pertanyaan".
  - Detail:
    - the best answer first, with a success chip + check icon;
    - 44 px vote buttons with aria labels, whose number slides vertically;
    - "Minta petunjuk AI" shows its answer in a tinted box labelled "Petunjuk AI, bukan jawaban".
- **4.7 Leaderboard.**
  - Tabs: Minggu ini · Bulan ini · Sepanjang waktu.
  - Top 3 as a podium of large Outfit 700 numbers (no medals).
  - Rows reorder with layout animation (`slow`).
  - Your row is tinted, labelled "Kamu", and sticky at the bottom when off screen.
- **4.8 Perpustakaan · Notifikasi · Profil.**
  - Perpustakaan: rows with a type icon, subject chip, date and a menu.
  - Notifikasi: unread rows are tinted; "Tandai semua dibaca" fades the tints out.
  - Profil: cards Akun · Bahasa & Tampilan (language, theme, **"Kurangi animasi"**) · Notifikasi (translated labels) · Google Calendar · Data.

---

## 5. Micro-interactions
- **Buttons:** press scale .98 (`fast`); primary hover → `--primary-hover`.
- **Link cards:** hover lifts 2 px with a faint shadow.
- **Toasts:** bottom-right (bottom-centre on mobile), rise 12 px, auto-hide after 4 s, atom icon on success.
- **Skeletons:** shimmer at .6 opacity, turned off under reduced motion.
- **Errors:** inline, translated, with "Coba lagi"; never a stack trace.

## 6. Accessibility and performance (acceptance criteria)
- **Week atom semantics:** `role="group"` with an `aria-label` that lists the week in words. Each electron is a focusable button with a full label (e.g. "Jumat 30 Oktober, 1 agenda: Tugas Struktur Data, 23.59"). Arrows move between electrons, Enter zooms in, Esc goes back. A visually hidden list mirrors every atom.
- **Reduced motion:** `prefers-reduced-motion` **or** "Kurangi animasi" turns off idle rotation and scroll motion, makes the zoom a 150 ms crossfade, and shows count-ups as their final value.
- **Contrast:** WCAG AA in both themes, using the tokens only.
- **Performance:** 60 fps on a mid-range laptop and a 400 px phone. Lighthouse on the Dashboard: Performance ≥ 85, Accessibility ≥ 95. Pages are code-split; KaTeX and pdf.js load only where needed.

## 7. Copy rules
- Sentence case, no ALL CAPS, no emoji.
- Indonesian formats: "Jum 30", "13.00", "Jumat, 30 Oktober 2026".
- Buttons say what they do ("Ringkas materi baru", not "Submit").
- Every string comes from `web/src/locales/{id,en,zh}.json`. The language switch shows "Bahasa Indonesia", "English", "中文" in menus and `ID` / `EN` / `中文` in the header.
