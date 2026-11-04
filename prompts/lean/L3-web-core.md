# L3 · Web core: shell, auth, Ringkas Materi, Perpustakaan, DocumentView, Dashboard (budget ≈ 430)

**Read:**
- `prompts/lean/_LEAN.md` (§3 UI rule);
- `web/src/styles/tokens.css`, `web/src/main.tsx`, `web/src/App.tsx` and `web/src/components/atom/AtomLoader.tsx`;
- in `docs/SPEC.md`, only §8.1–§8.3 and §8.8 (lines ~225–248 and ~286–294).
- For types, search `web/src/lib/api-types.ts` for the schema names you need (`User`, `Me`, `Job`, `Document`, `DocumentList`, `Dashboard`, `Subject`). Do not read the whole file.
- **Design target:**
  - `docs/design/dashboard-mockup.html` (read its `<style>` block and the markup of the sidebar, header, hero, stat strip, quick actions and cards; skip its scripts);
  - `docs/design/DESIGN.md` §1.2 (lines ~36–41), §2 (lines ~59–74), §4 intro + 4.1–4.3 + 4.8 (lines ~137–163 and ~186–189), §5 (lines ~195–200) and §7 (lines ~208–212).
  - Rebuild that look in React following `_LEAN.md` §3: same colours, fonts, spacing, radius, card style and layout, but with no heavy motion.

**Work only in:** `web/`.

## Tasks
1. **Foundation:**
   - `lib/api.ts`: relative `api/...` URLs; the Bearer token stored in `localStorage` with try/catch and an in-memory fallback; error JSON mapped to `errors.<code>`; a 401 logs the user out; `watchJob(id)` polls `GET api/jobs/{id}` every 2 s until `done` or `error`.
   - `lib/i18n.ts`: `t(key, params)` reading `locales/id.json` and `locales/en.json`, with the language from the user or `localStorage`. Add a small Vitest test, or a Node script run in `make lint`, that fails if the two files have different keys.
   - `lib/useFetch.ts`: a hook returning `{data, error, loading, reload}`.
   - `components/ui/`: Button, Input, Select, Card, EmptyState, ErrorBox (with "Coba lagi"), Tabs and Markdown (react-markdown with remark-math, remark-gfm and rehype-katex; code in plain `<pre><code>`).
2. **Shell** (DESIGN §2, as in the mockup):
   - routes `/login`, `/register`, `/`, `/summarize`, `/library` and `/library/:id`; use `HashRouter` so the app works at any Studio path;
   - a 248 px sidebar with the lockup from `assets/brand/`, lucide nav icons for the built pages only, the active item tinted, and the user block (avatar, name, "Keluar");
   - a header on every page with title, subtitle, the `ID`/`EN` switch and the sun/moon theme toggle (stored);
   - at 860 px and below, a drawer with a scrim (Esc closes it) and a menu button;
   - the health banner from DESIGN §2 when `modelscope` is not `ok`;
   - an error boundary showing a translated message;
   - tab title `<Page> · Orvina`, and favicon D.
3. **Login and Register** (DESIGN §4.1): a centred 420 px card with the lockup, the tagline "Belajar bersama, paham lebih dalam", Masuk / Daftar tabs and the language switch in the corner. Errors appear under each field, including `terms_required` and the generic login error. No onboarding.
4. **Ringkas Materi** (`/summarize`, DESIGN §4.3):
   - the Upload card and the Opsi card side by side, stacked under 1100 px;
   - a dashed drop zone that turns `--primary` on drag-over, listing the allowed types and the `MAX_UPLOAD_MB` limit, with file chips showing a type icon, size and remove;
   - style as segmented cards, plus title, subject (select or add), language and detail;
   - one primary button, "Ringkas";
   - while running, `AtomLoader` with the translated stage name, then open DocumentView;
   - on error, the translated message and "Coba lagi".
5. **Perpustakaan** (`/library`, DESIGN §4.8): search, subject filter chips, and rows with a type icon, subject chip, date and a menu. Paged, with an empty state linking to `/summarize`.
6. **DocumentView** (`/library/:id`):
   - the rendered summary with LaTeX and code;
   - tabs Ringkasan · Sumber;
   - rename, delete (with a confirm dialog) and download `.md`;
   - if the summary returned deadlines, list them with the note "Tambahkan di Jadwal (segera)" and the button disabled until L5.
7. **Dashboard** (`/`, DESIGN §4.2; match the mockup's layout):
   - the header with a greeting and the date in Indonesian format;
   - the hero "Minggu ini": the text on the left (event count and the next event in a tinted box, or an empty-state line), and the week atom on the right as a **static** SVG with 7 day electrons and today highlighted;
   - the stat strip: one card with cells for summaries, documents and "Agenda minggu ini". No points ring.
   - quick actions: "Ringkas materi baru" (the only primary button) and "Buka perpustakaan" (secondary);
   - columns 3:2: "7 hari ke depan" on the left (an empty state until L5), and "Aktivitas terakhir" (recent documents) on the right.
   - No Top 5, reminders, points or "Rekam kelas" blocks; the grid closes up without gaps.
8. **Production build:** MSW loads in dev only (already done). The `npm run build` bundle must be at most 250 KB gzip for the initial JS; load KaTeX CSS only on pages that render Markdown.

## Done when
- [ ] `tsc`, the locale key-parity check and `npm run build` pass, and `compliance` passes.
- [ ] One click-through against the real local server: register, summarize a small PDF, check the library, open DocumentView, rename it, download `.md`, then return to the dashboard. Check it at 400 px and in dark mode. Note any bug in the report and fix it.
- [ ] **Design check:** open `docs/design/dashboard-mockup.html` and the app's Dashboard side by side at 1280 px and 400 px, in light and dark. The colours, fonts, spacing, card style, sidebar and header match. List any remaining differences in the report: they should only be the cut blocks and the removed animations.
