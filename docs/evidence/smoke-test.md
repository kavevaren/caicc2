# Smoke test (real ModelScope API)

Command: `MODELSCOPE_TOKEN=… python scripts/smoke_test.py` (from the repo root).
The script skips cleanly when no token is set. It does two things:

1. **Role probe** — one tiny chat call per role, printing `role / model / ok / ms`.
2. **Real summarize** — generates a small 2-page PDF (physics notes with a formula and a
   deadline sentence), runs the full pipeline `extract → chunk → map → reduce → check →
   deadlines`, and prints the seconds spent in each stage plus any warnings/deadlines.

## Results

**Status: pending — no `MODELSCOPE_TOKEN` in the agent sandbox.** The developer runs the
command where the token exists (Studio Secrets or local `.env`) and pastes the output here.

| role | model | ok | ms |
|---|---|---|---|
| VISION | `Qwen/Qwen3.8-27B` | — | — |
| FAST | `Qwen/Qwen3.8-27B` | — | — |
| REASON | `deepseek-ai/DeepSeek-V4-Pro-0813` | — | — |
| CHECK | `zai-org/GLM-5.2` | — | — |

| stage | s |
|---|---|
| extract | — |
| chunk | — |
| map | — |
| reduce | — |
| check | — |
| deadlines | — |

### Reference data (P0 platform probe, 2026-10-31, real token, local)

| model | result | latency |
|---|---|---|
| `Qwen/Qwen3.8-27B` | ok | 1045 ms |
| `deepseek-ai/DeepSeek-V4-Pro-0813` | ok | 999 ms |
| `zai-org/GLM-5.2` | ok | 3687 ms |
| `stepfun-ai/Step-3.5-Flash` | **400 "no provider supported"** | — |

That is why the FAST role uses `Qwen/Qwen3.8-27B` (see the model-role table in README.md).
