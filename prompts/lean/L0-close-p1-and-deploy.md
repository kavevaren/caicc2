# L0 · Close P1 and put a first build on the Studio (budget ≈ 60)

**Read:** `prompts/lean/_LEAN.md`, then only "Current phase" and "Not done / blocked" in `docs/PROGRESS.md`.

## Tasks
1. **Fix the three P1 leftovers.**
   - Unmount `server/api/probe_p0.py` from `server/main.py` and delete the file.
   - In `web/src/mocks/handlers.ts`, make `/api/health` return `whisper: "disabled"`.
   - Validate `contracts/openapi.yaml` with a short Python check (PyYAML: `openapi` key, every path has operations, every `$ref` resolves). Record the real path and operation count.
2. **Prepare the first deploy.**
   - Set `ms_deploy.json` `resource_configuration` to a placeholder `"FREE_CPU_NAME_FROM_STUDIO_UI"`.
   - Under "Manual checks for the developer", list the 4 steps:
     1. create the Studio;
     2. pick the free CPU option and paste its exact name;
     3. add the `MODELSCOPE_TOKEN` and `APP_SECRET_KEY` secrets;
     4. upload and build.
   - Confirm `npm run build` passes and that `Dockerfile` copies `web/dist`.
3. **Write a short P1 report and switch the plan.** Write the P1 report (at most 15 lines) and the P1 prompt-log line. Under "Assumptions", add: "From 1 Nov 21:00 the project follows `prompts/lean/` (L0–L6). The P2–P6 prompts are reference only."

## Done when
- [ ] `pytest`, `ruff`, `tsc`, `npm run build` and `compliance` all pass.
- [ ] `PROGRESS.md` says the next step is L1 and lists the manual deploy steps.
