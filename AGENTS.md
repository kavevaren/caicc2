# Orvina: always-on agent instructions (lean, from 1 Nov 21:00)

The rules are in `prompts/lean/_LEAN.md`. Read it once per session if it is not already in your context. It replaces `prompts/_RULES.md` and the old version of this file, which is kept in `prompts/_old/AGENTS-v5.md` as reference only.

At the start of every session:
1. Read only the "Current phase" section of `docs/PROGRESS.md`.
2. Say in one line which L-phase and task you are continuing.
3. Follow the phase file in `prompts/lean/`.

Checkpoints (short, 3–5 lines, never delete old lines, never write secrets) go into `docs/PROGRESS.md`:
- after every numbered task;
- before any command that may take more than 2 minutes;
- when a build or test fails;
- at the end of a phase;
- when the user writes "checkpoint" or "simpan";
- before you end your reply.

Every checkpoint names the exact model ID you are running on, which must be one of the four allowed models.
