# L5 (optional) · Jadwal, local mode (budget ≈ 200)

**Start only if** L4 tasks 1–3 already work on the Studio **and** more than 450 of the budget is left. Otherwise skip to L4 tasks 4–7.

**Read:** `prompts/lean/_LEAN.md`, `docs/SPEC.md` §8.5 (lines ~257–262), and in `contracts/openapi.yaml` only the `/api/events*` and `/api/suggestions*` blocks.

## Tasks
1. **API:**
   - `GET /api/events?from&to`;
   - `POST`, `PATCH` and `DELETE /api/events/{id}`, with `end_at` defaulting to start + 1 h; `end_at` at or before `start_at` returns 422 `end_before_start`; INSERTs use explicit column lists;
   - `GET /api/events/{id}.ics` (RFC 5545);
   - `GET /api/suggestions`;
   - `POST /api/suggestions/{id}/accept|dismiss`.
   - Tests: the end-time rule, the INSERT columns and accepting a suggestion.
2. **Dashboard:** fill `week` and `next_event` from events.
3. **Web:**
   - `/schedule`: a 30-day list grouped by day, an "Agenda baru" form (title, start, end, location) and a delete action;
   - a suggestions list with Accept and Dismiss;
   - an `.ics` download per event;
   - in DocumentView, enable "Tambahkan di Jadwal";
   - add Jadwal to the sidebar (lucide `CalendarDays`);
   - match the look in DESIGN §4.5 (lines ~172–176): the "Agenda baru" side sheet, suggestions in a tinted card with Terima / Abaikan, and the end-time error text. No sticky atom and no fly-in animations.
   - The Dashboard "7 hari ke depan" rows match the mockup's `ev-row` style.
4. Deploy and click through on the Studio.

## Done when
- [ ] Tests and the build pass, and a deadline from a real summary appears in Jadwal and on the Dashboard on the Studio.
