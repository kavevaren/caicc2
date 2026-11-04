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
