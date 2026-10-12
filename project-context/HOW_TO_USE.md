# How to use this pack with Claude (free plan)

Contents:
| File | Size | Use |
|---|---|---|
| `PROJECT_CONTEXT.md` | ~8k tokens | **Always start with this.** The whole project explained: purpose, stack, every app, models, crawlers, API map, frontend pages, run commands, conventions, known issues. |
| `FILE_INDEX.md` | ~11k tokens | Every source file with line count and its classes/functions. Add it when you want Claude to tell you *which* file to change. |
| `key_files/` | ~60k tokens total | Real copies of the most-used files (all `models.py`, all `urls.py`, `settings.py`, `movers.py`, `App.tsx`, `api/client.ts`, `api/market.ts`, …) with their original paths. Upload only the ones relevant to your question. |

## Suggested first message

> I'm working on my project "StockScope". The attached PROJECT_CONTEXT.md explains it.
> Read it, then help me with: <your task>.
> If you need the exact code of a file, tell me the path and I'll paste it.

Attach `PROJECT_CONTEXT.md` (and `FILE_INDEX.md` if the task is about finding/changing code).
Uploading the `.md` files directly works better than uploading the zip.

## Tips for the free plan
- Free chats have a limited message/context budget: attach only what the task needs.
- Paste single files from the real repo when Claude asks for them; the paths in these docs
  are relative to the repo root `Stock-Market-Application-crawling-2/`.
- Start a new chat for an unrelated task and re-attach `PROJECT_CONTEXT.md`.
- This snapshot is from 2026-10-12. If the code changes a lot, regenerate it.
