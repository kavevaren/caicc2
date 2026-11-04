# L4 · Ship: deploy, compliance, README, evidence (budget ≈ 200)

**Read:** `prompts/lean/_LEAN.md`, "Current phase" and "Manual checks" in `docs/PROGRESS.md`, and `docs/SPEC.md` §2 and §13 (lines ~24–39 and ~436–458).

Code freeze is **Wed 4 Nov 12:00**. After that, only deploy, README and evidence work.

## Tasks
1. **Clean up:**
   - routes and buttons for cut features are hidden;
   - no MSW in the production bundle;
   - no leftover test output;
   - `.dockerignore` excludes `.env`, `arsip/`, `prompts/`, `docs/`, `scripts/`, `web/node_modules/` and data.
2. **Run all checks:** `pytest`, `ruff`, `tsc`, `npm run build` and `python scripts/compliance.py` (print the `MANUAL` count). Paste the outputs into the report.
3. **Final Studio deploy** (the developer clicks, you guide):
   - free CPU, secrets set, visibility **Public**;
   - `/api/health` is green;
   - seed loaded;
   - restart once and confirm the app comes back.
   - In an incognito window, inside the Studio page, run register → summarize → library → document → dashboard.
4. **Design pass:** go through every built page once against `docs/design/DESIGN.md` §4 and the mockup. Confirm the look matches (colours, fonts, spacing, cards, exactly one primary button, chips, empty states) and fix small mismatches before the freeze.
5. **Screenshots** in `docs/evidence/screenshots/`, plus one of the mockup next to the real Dashboard: login, dashboard, Ringkas Materi while running, DocumentView with LaTeX, and Perpustakaan, each in light at 1280 px. Add dashboard and DocumentView at 400 px. Make sure the agent window with the model name is visible in at least one screenshot.
6. **README:** a one-paragraph pitch, screenshots, the architecture diagram, setup, environment variables and Studio secrets, the model-role table, a **Competition compliance** table (each SPEC §2 rule mapped to where the code enforces it), libraries and licenses, Apache-2.0, and **known limits**. State the scope cut honestly: no audio, no figures, and data may reset when the Studio restarts.
7. **Evidence pack** in `docs/evidence/`:
   - the "Prompt log" in `PROGRESS.md` complete;
   - `prompts.pdf` (or `.md`) containing `_LEAN.md`, `L1-ai-core.md` and one bug-fix iteration;
   - the smoke-test table;
   - a 60–90 second demo video script.
8. **Submission checklist** for the developer:
   - the work title is identical to the Studio title;
   - the Studio link;
   - the project zip (no `.env`, no data, no `arsip/`, no `node_modules/`);
   - the prompts PDF;
   - the screenshots folder.

## Done when
- [ ] A fresh user completes the full loop on the public Studio URL.
- [ ] All checks pass and the checklist is ticked.
