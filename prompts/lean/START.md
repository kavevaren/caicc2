# How to run the lean plan (for the developer)

## Order and budget
Budget figures are in the same unit you measured (the P1 tasks 5–7 session cost about 250).

| Phase | File | Budget | Required? |
|---|---|---|---|
| L0 | `L0-close-p1-and-deploy.md` | ~60 | yes |
| L1 | `L1-ai-core.md` | ~250 | yes |
| L2 | `L2-api-core.md` | ~300 | yes |
| L3 | `L3-web-core.md` | ~430 | yes (includes the design match) |
| L4 | `L4-ship.md` | ~200 | yes |
| L5 | `L5-jadwal-optional.md` | ~200 | only if more than 450 remains after L3 |
| L6 | `L6-forum-optional.md` | ~250 | only if more than 400 remains after L5 |
| Reserve for bugs | | ~250 | keep it |

Must path total: about 1,240. With the reserve: about 1,490 of the 1,750 available.

**Gates:**
- If any phase costs more than 1.3× its budget, skip L5 and L6.
- If less than 300 remains, go straight to L4.

## Message to start each phase (new session every time)
Copy this, change `<Ln file>`, and send it as the first message:

```
Read prompts/lean/_LEAN.md and the "Current phase" section of docs/PROGRESS.md, then execute prompts/lean/<Ln file>.
Follow the token-saving rules in _LEAN.md §5 strictly: read only the listed files and line ranges, make small edits, test once per task, and run the full check once at the end.
Confirm in one line which phase and task you are starting, then begin. When the phase is done, write the report (max 15 lines) and stop.
```

To resume an interrupted phase in a new session:

```
Read prompts/lean/_LEAN.md and docs/PROGRESS.md "Current phase". Continue exactly from the written next step of the current L-phase. Do not redo finished tasks.
```

## Tips
- Do the Studio deploy as early as L0/L2. A working Studio every evening is the safety net.
- If the agent starts reading big files or repeats the same failing fix, interrupt it and send: "Stop. Follow _LEAN.md §5. Write the blocker in PROGRESS.md and ask one question."
