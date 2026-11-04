# L6 (optional) · Forum and "Tanya di Forum" (budget ≈ 250)

**Start only if** L5 is done on the Studio **and** more than 400 of the budget is left. Otherwise go to L4.

**Read:** `prompts/lean/_LEAN.md`, `docs/SPEC.md` §8.6 (lines ~263–280), and in `contracts/openapi.yaml` only the `/api/questions*` and `/api/answers*` blocks.

## Tasks
1. **API:**
   - `GET /api/questions?subject&q&page` (FTS5);
   - `POST /api/questions` (`subject_id`, `title` of 10–150 characters or 422 `title_length`, `body_md`);
   - `GET`, `PATCH` and `DELETE /api/questions/{id}` (owner-only edits, soft delete);
   - `POST /api/questions/{id}/answers`;
   - `PATCH` and `DELETE /api/answers/{id}` (owner-only).
   - Votes, best answer, follow, tags, similar questions, attachments and moderation stay at 501.
   - Tests: the title length, owner-only edits and FTS search.
2. **Web:**
   - `/forum`: list, subject filter, search, and an empty state with the CTA "Ajukan pertanyaan";
   - `/forum/ask`: title with a 10–150 counter, subject, and body with a Write/Preview toggle using the Markdown component;
   - `/forum/q/:id`: question, answers, an answer form and owner edit/delete;
   - add Forum to the sidebar (lucide `MessagesSquare`);
   - match the look in DESIGN §4.6 (lines ~177–183): question rows with "Belum ada jawaban" in `--warning-text`, the live title counter, write/preview tabs, the primary button "Kirim pertanyaan", and the hint box labelled "Petunjuk AI, bukan jawaban". No vote animations.
3. **Tanya di Forum:** a button in DocumentView opens `/forum/ask` with the document's subject preselected and a link to the document prefilled in the body.
4. **"Minta petunjuk AI"** (`POST /api/questions/{id}/hint` → `ai.forum_hint`, REASON, never the final answer), only if more than 150 of the budget is left.
5. Deploy and click through on the Studio with two users.

## Done when
- [ ] Tests and the build pass. On the Studio, user 1 asks from a summary and user 2 answers.
