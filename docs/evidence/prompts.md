# Orvina — prompts (evidence)

This pack contains the lean rulebook the agent worked under, the L1 phase prompt, and one
bug-fix iteration, as required by `prompts/lean/L4-ship.md` task 7. All phases were driven by
the prompt files in `prompts/lean/` (L0–L4); the full prompt log is in `docs/PROGRESS.md`.

---

## 1. `prompts/lean/_LEAN.md` (the always-on rulebook, verbatim)

# Orvina lean rules (replace `prompts/_RULES.md` and the old `AGENTS.md` from 1 Nov 21:00)

You are finishing **Orvina** for CAICC 2026 Track 2. The deadline is **Wed 4 Nov, 16:00–23:59 WIB**, and the token budget is tight. The goal is now a **small app that works on the Studio**, not the full SPEC. Wherever an older file (`_RULES.md`, `P0`–`P6`, SPEC, DESIGN) asks for more, this file wins.

## 1. Disqualification rules (never break)
- **Models:** only `zai-org/GLM-5.2`, `deepseek-ai/DeepSeek-V4-Pro-0813`, `stepfun-ai/Step-3.5-Flash` and `Qwen/Qwen3.8-27B`, via `https://api-inference.modelscope.ai/v1`. Roles: VISION = Qwen, FAST = Qwen (Step returns "no provider supported"), REASON = DeepSeek, CHECK = GLM.
- **Where the AI code lives:** only `server/ai/llm.py` calls a model. `openai` is imported only inside `server/ai/`. The browser never calls an LLM.
- **No other AI:** no other AI service and no Web Speech API. No whisper: `ENABLE_TRANSCRIPTION=false`.
- **No training and no GPU.** The Studio runs on the free CPU tier only.
- **Secrets:** environment variables only. Never in code, logs, tests, the bundle or docs.
- **Code authorship:** you write all code. Never write the `MANUAL` marker.
- **Before each phase ends:** `python scripts/compliance.py` must pass.

## 2. Scope (build only this)
**Must, in this order:**
1. Auth: register with username, password and accept terms, plus login and logout. No onboarding wizard; set `onboarding_done=1` on register.
2. F1 Ringkas Materi for PDF, DOCX, PPTX, TXT/MD and images. The output is a Markdown summary with LaTeX and code, and the job is checked by polling.
3. Perpustakaan (list and search of documents) and DocumentView (rendered summary, rename, delete, export as `.md`).
4. A simple Dashboard on real data: greeting, stats, recent documents, and "7 hari ke depan" (empty until L5).
5. Locales `id` and `en`.
6. Deployed on the public Studio, with the evidence.

**Optional, only if the budget gate allows it:** L5 Jadwal (local events, deadlines from summaries, `.ics`), then L6 Forum with "Tanya di Forum".

**Cut (leave as 501 or hide from the UI):**
- F2 and anything audio or video;
- figures and charts;
- Google;
- SSE;
- points, leaderboard, votes, best answer, follow, tags, similar questions, moderation and notifications;
- `zh`;
- onboarding;
- Lighthouse, load tests, schemathesis, Playwright and recordings.

## 3. UI rule: look like the design, move like a simple app
**The app must visually match the design in `docs/design/`.** `docs/design/dashboard-mockup.html` is the visual target, and `docs/design/DESIGN.md` gives the rules. Match the **static look**:
- the colours from `tokens.css` only (never invent new ones), light and dark;
- type: Outfit for headings and numbers, Inter for body, with the DESIGN §1.2 scale (page title 28, card title 18, body 15, meta 13, chip 12);
- spacing (4/8/12/16/24/32) and radius (card 16, control 10, chip 999);
- controls at least 44 px tall, with the focus outline from §1.2;
- the shell from DESIGN §2: a 248 px sidebar with the logo lockup, lucide icons, the active item tinted, and the user block at the bottom; a header with title, subtitle, language switch and theme toggle; a drawer at 860 px and below;
- the page layouts from DESIGN §4 for the pages we build. Every page has the header, content in cards, **exactly one primary button**, chips for subject and source, and muted relative times;
- the copy rules from DESIGN §7: sentence case, no emoji, Indonesian date formats, and buttons that say what they do.

**What we do not copy from the design: heavy motion.**
- Allowed:
  - `AtomLoader` while a job runs;
  - the week atom drawn as a **static** SVG (no rotation, zoom or scroll spin);
  - CSS transitions of at most 150 ms on hover, focus, button press and drawer open;
  - a plain skeleton (no shimmer) while loading.
- Not allowed: page transitions, count-ups, scroll-entrance staggers, the orbit and zoom system, animated tab underlines, fly-in effects, layout animations and new `framer-motion` code.
- Honor `prefers-reduced-motion`.

When the design and this file disagree, keep the design's **look** and this file's **motion** limits. Hide blocks for cut features, such as the points ring, Top 5, "Rekam kelas" and the bell count, without leaving holes in the layout: let the remaining cards fill the grid.

- **Layout:** it must be usable at 400 px wide. Every string comes from `web/src/locales/{id,en}.json`.
- **States:** every page has a loading, empty and error state. Errors show the translated message and a "Coba lagi" button.
- **Checking the design:** at the end of every phase that changes UI, compare the page against the mockup in the browser side by side, at the same width, in light and dark. Fix any visible mismatch in colour, spacing, font size or layout before the report.

## 4. Pre-approved dependencies (add these without asking; ask for anything else)
- **Python:** `bcrypt`, `pypdf`, `python-pptx`, `python-docx`, `Pillow`. `pytest`, `httpx` and `ruff` are dev-only.
- **Web:** `react-router-dom`, `react-markdown`, `remark-math`, `remark-gfm`, `rehype-katex`, `katex`, `lucide-react` (import single icons only), `@fontsource/outfit` (500, 600, 700) and `@fontsource/inter` (400, 500, 600). The icons and fonts are needed to match the design.
- **Do not add:** TanStack Query, i18next or highlight. Write small helpers instead: `useFetch`, a `t()` that reads the JSON, and plain `<pre><code>` blocks.

## 5. Token-saving work rules (mandatory)
- **Read narrowly:**
  - read only the files and SPEC lines the phase prompt lists;
  - never read `contracts/openapi.yaml` (68 KB), `web/src/lib/api-types.ts` (83 KB), `docs/SPEC.md` or `docs/DESIGN.md` in full;
  - search for the path or heading you need and read that range only;
  - never open `arsip/`, `prompts/_old/`, `*.zip`, `node_modules/`, `.venv/` or `dist/`;
  - do not re-read a file you already read in this session unless it changed.
- **Write narrowly:** make small, targeted edits. Never print whole files back to the chat, and never restate code you just wrote.
- **Test once per task:**
  - after each task, run only the relevant check (one pytest file, or `tsc`);
  - run the full set (`pytest`, `ruff`, `tsc`, `npm run build`, `compliance`) once, at the end of the phase;
  - write 1–3 tests per feature, aimed at the rules: auth errors, the job lifecycle, ownership checks and the INSERT column lists.
- **Check the browser once:** one click-through per phase at the end, not after every task. Take screenshots only in L4.
- **When stuck:** if the same error survives 2 fix attempts, write it under "Not done / blocked" with the exact message, and ask one precise question.
- **One session per phase.** Start a new session for each L-phase; `docs/PROGRESS.md` carries the state.
- **Replies stay short:** what changed, test result, next step. No essays.

## 6. Progress (the only record; no git)
- `docs/PROGRESS.md` is the only memory.
- **After each numbered task**, replace "Current phase" with phase, task, status and the exact next step. Add one line to "Done" or to "Not done / blocked", and one line to "Checkpoint log": `<date time> · <model ID> · L<n> task <n> · <change> · tests: <result> · next: <step>`.
- **At the end of a phase**, add one "Prompt log" line: date, phase, model ID, prompt file, summary, fixes, test output, screenshot paths. Then add a **report of at most 15 lines**: files changed, tests and build, acceptance done / not done, risks, next step. Then stop and wait for "lanjut".
- Never delete old lines. Never write secrets.
- Each checkpoint names the exact model you are running on. If you are not on one of the four allowed models, stop and say so before writing code.

## 7. Studio rules
- **Server:** one process, one uvicorn worker, `0.0.0.0:7860`.
- **Web app inside the iframe:** relative URLs only, and the Bearer token in `localStorage` (with try/catch and an in-memory fallback).
- **Data:** `DATA_DIR` falls back to `/tmp/orvina`. An empty DB is migrated and seeded automatically.
- **Daily rule:** every evening, the Studio must run a version we could submit. Hide unfinished features instead of shipping them broken.

---

## 2. `prompts/lean/L1-ai-core.md` (verbatim)

# L1 · AI core: LLM client and document summary (budget ≈ 250)

**Read:**
- `prompts/lean/_LEAN.md`;
- `server/ai/__init__.py` and `server/ai/probe.py`;
- in `docs/SPEC.md`, only §7 (lines ~203–219), §9.1 (the "LLM client" part, lines ~305–320) and §10.1 (lines ~337–350).

**Work only in:** `server/ai/` and `server/tests/ai/`. Never touch the DB or `server/api/`.

## Tasks
1. **`server/ai/llm.py`:** `chat(role, messages, *, json_schema=None, images=None, feature, calls)`.
   - The roles map to models as listed in `_LEAN.md` §1. Reject any other model.
   - Timeout 120 s. Up to 2 retries on 429, 5xx and timeouts. A 401 raises `ModelScopeAuthError` with no retry.
   - Images go to VISION only, resized to at most 1600 px and sent as base64.
   - For JSON: parse with pydantic, and allow one repair retry.
   - Append `{feature, role, model, latency_ms, retries, ok}` to `calls`.
   - Move the model IDs out of `probe.py` so they live only in `llm.py`; `probe.py` imports them from there.
2. **`server/ai/extract.py`:**
   - **PDF** (pypdf): text per page, labelled "Hal. N". Pages with fewer than 80 characters are skipped, with a note in `warnings` (no OCR in lean).
   - **PPTX:** slide text and notes, labelled "Slide N".
   - **DOCX:** paragraphs and tables.
   - **TXT/MD:** as is.
   - **PNG/JPG:** one VISION call: "all text, formulas as LaTeX, code as code".
   - Cap the total text at 120,000 characters.
3. **`server/ai/summarize.py`:** `summarize(job_id, files, options, on_stage)`. The stages are `extract`, `chunk`, `map`, `reduce`, `check`, `deadlines`.
   - **chunk:** about 6,000 characters each, on label boundaries.
   - **map:** FAST, notes for each chunk.
   - **reduce:** REASON, in the chosen style (`ringkas`, `terstruktur`, `poin_rumus_kode` or `latihan`) and language (`id` or `en`), with the SPEC §10.1 sections.
   - **check:** Python checks for balanced `$`/`$$` and closed code fences. If either fails, CHECK repairs the format once; if it still fails, set `warning=true`.
   - **deadlines:** CHECK returns JSON `[{title, start_at, end_at|null, evidence}]`, dropping any date it cannot resolve.
   - **Return:** `{content_md, sources, deadlines, warnings, ai_calls}`, with `figures: []`.
   - Prompts live in `server/ai/prompts.py` (English, `PROMPT_VERSION`, each ending with "Respond only in {language}."). Every prompt says "never invent content".
4. **`server/tests/ai/`** (using `FakeLLM`): run the stage order with `on_stage` calls, check that the format repair runs once, that a 401 raises `ModelScopeAuthError`, that a non-allowed model is rejected, and that DOCX and TXT extraction work. Make small fixture files at test time; do not commit binaries.
5. **`scripts/smoke_test.py`** against the real API (skipped when there is no token):
   - one tiny call per role, with latency;
   - one real `summarize` on a small generated PDF, printing the seconds spent in each stage.

## Done when
- [ ] `pytest server/tests/ai` and `ruff` pass, and `compliance` passes.
- [ ] The smoke-test table (role, model, ok, ms) and the per-stage seconds of the real summary are pasted into the report.
- [ ] A search shows no model ID outside `server/ai/llm.py` and `server/config.py`.

---

## 3. One bug-fix iteration (L2, 2026-11-01 23:10, model Qwen/Qwen3.8-27B)

**Symptom.** First run of the new L2 test suite: 25/27 passed. One test created a summary
job and then polled `GET /api/jobs/{id}`; the job came back with status `error` and
`error_code = server_restart` — even though the server had not restarted.

**Root cause.** `runner.start()` (called from the FastAPI lifespan at startup) first ran a
"stale job cleanup": every job in `queued`/`running` state was marked `error /
server_restart`, because after a real restart their worker threads are gone. But the
summaries router calls `runner.start()` **lazily on every job submit** (idempotent guard),
so the cleanup ran on every submit — and clobbered the job that had just been queued
milliseconds earlier.

**Fix.** The stale cleanup belongs to *process start*, not to *pool start*. It was moved to
run only when the thread pool is actually created (first call in this process), guarded by
an `atexit`-style flag; subsequent `runner.start()` calls are a no-op. The 202 response is
still sent before the job is queued, so the client never sees the race.

**Verification.** `pytest server/tests` → 27 passed (the job-lifecycle test now sees the job
go `queued → running → done` with the seeded `FakeLLM`-free real pipeline stubs); the same
cleanup still runs on a genuine restart (covered by the existing "queued AND running jobs
fail as server_restart at startup" behaviour, kept in the runner).
