# BurnRate Python backend

FastAPI + SQLite API, serving the existing mobile dashboard from the same origin. No login screen is added. Each browser receives an opaque HttpOnly cookie that selects its isolated server journal.

## Start

From the project root, using Python 3.12 or newer:

```sh
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Open [the local app](http://127.0.0.1:8000). API documentation: [Swagger UI](http://127.0.0.1:8000/api/docs).

No API keys are needed for storage, manual logging, template planning or local weekly summaries. `backend/burnrate.db` is created automatically and excluded from source control. Copy it using SQLite's backup API when backing up a running service; do not copy only the main file while WAL writes are active.

## Enable AI

Provide `GEMINI_API_KEY`, `GEMINI_MODEL`, `DEEPSEEK_API_KEY` and `DEEPSEEK_MODEL` as **server environment variables**. `.env.example` lists settings. `backend/.env` is loaded automatically on startup. Environment variables already provided by your process manager take precedence. Do not put keys in dashboard JavaScript or send them through chat.

Model names are deliberately not pinned: select currently available models from the providers. Settings shows capability readiness. With Gemini configured, attaching a photo reveals an explicit **Analyze with Gemini** action. With DeepSeek configured, My plan and Settings let the user opt into AI on plan refresh. My plan → enable Use DeepSeek → Refresh plan requests composed catalog meals and a constrained activity choice; the toggle is currently held in memory for that page session. Missing keys or invalid responses preserve manual entry and the validated rules planner.

Provider requests follow [Google's structured-output documentation](https://ai.google.dev/gemini-api/docs/structured-output) and [DeepSeek's JSON-output documentation](https://api-docs.deepseek.com/guides/json_mode/). Live synthetic connection tests have now passed for DeepSeek JSON output, Gemini image-recognition output, and Gemini nutrition JSON. These check connectivity and formatting, not calorie accuracy. Gemini uses JSON response mode with the full contract in the prompt and strict Pydantic validation afterward; the selected model rejected the nested API-native schema. Validation failures still receive at most one repair attempt.

## API

| Method | Endpoint | Behavior |
|---|---|---|
| GET | `/api/health` | Service identity and timezone |
| GET | `/api/session` | Initialize anonymous cookie, return journal and capabilities |
| GET | `/api/daily-recap` | Read the latest frozen midnight recap; generation runs at 00:00 Malaysia time |
| GET | `/api/state` | Current state and authoritative server revision |
| PUT | `/api/state` | Validate and save a complete journal snapshot |
| GET | `/api/catalog` | Versioned illustrative nutrition catalog |
| GET | `/api/summary?date=YYYY-MM-DD` | Calculated confirmed totals and data quality |
| POST | `/api/plans` | Cached, validated next-day plan; optional DeepSeek |
| POST | `/api/reviews` | Weekly summaries; optional AI review and date proposal |
| POST | `/api/food/analyze` | Sanitized photo recognition and batched fallback nutrition |
| GET | `/api/food/drafts/{id}` | Read the browser's own draft |
| POST | `/api/food/drafts/{id}/confirm` | Atomically confirm a reviewed meal, exactly once |

Writes require `expected_revision` and `mutation_id`. A conflicting revision returns HTTP 409; retrying the same mutation replays the existing result. The dashboard preserves a browser backup and pauses server saving when a conflict or network failure occurs. Export local edits before reloading after a conflict. It does not silently overwrite a newer server journal.

Journal JSON uses the dashboard's existing schema, validated by `app/models.py`. Server normalization replaces catalog-based calories and protein with Python calculations; client plan output is discarded. User calorie overrides keep `food: null` and remain explicit estimates. The version-1 catalog uses approximate averages rather than a verified nutrition dataset.

Planning requests use the date of the daily brief; output is for the following day. Python supplies eligible activities, serving bounds, recent logs and weight-trend context. DeepSeek can compose three catalog meals and shorten an eligible session; Python validates all items and recalculates nutrition. The current catalog contains five illustrative foods, and template mode remains available. At most two provider attempts occur per stage. Weekly end-date changes are proposals only; there is no automatic goal modification or proposal-acceptance endpoint yet.

## Photo handling

JPEG, PNG and WebP are accepted, up to 8 MB decoded and 16 million pixels. EXIF is stripped, the image is resized, and JPEG content is sent only when the user requests analysis. Raw photos are not persisted. User-scoped analysis caches contain hashes and structured results. Unknown portions remain unresolved rather than being recorded as zero. Estimates retain provenance and ranges after confirmation.

The MVP portion methods are units, edible cooked grams, ml and unknown. Calibrated plate/bowl geometry, aliases and calibration CRUD from the specification are not implemented yet.

## Identity and hosting

Cookies provide anonymous browser sessions. A recovery code can now link a new browser session to an existing journal without a login screen. Existing journals are preserved by a session-table migration. Export/import copies data; recovery connects to the same journal. See [recovery and backups](../document/data-protection/README.md) for setup, API behavior, automatic SQLite snapshots and off-server backup instructions.

The default service binds to loopback. For a real deployment, serve the dashboard and API together behind HTTPS, set `BURNRATE_SECURE_COOKIE=true` and `BURNRATE_ORIGIN` to that exact origin, persist the SQLite volume, and provide a trusted access/perimeter policy suitable for health-related journals and paid AI usage. Current origin checks, request-size limits and a per-session, in-process AI quota are MVP protections, not a complete public-hosting abuse control system. No permissive CORS configuration is enabled.

The current public Sites URL hosts static files and cannot execute this Python service. It stays in browser-local mode. Deploying the Python service or adding a same-origin backend proxy is a separate deployment step; no cloud database or AI service has been connected to that URL.

## Tests

```sh
backend/.venv/bin/python -m pytest backend/tests -q
node frontend/check.mjs
node --check frontend/dist/app.js
```

Tests cover isolation, persistence, conflicts, duplicate writes, calculated nutrition, missing data, unknown protein, invalid units, recovery and partner constraints, fallback, cached drafts, confirmation boundaries, stale model responses and bounded repair requests. A Starlette warning about its TestClient's httpx dependency is emitted by the installed framework; it does not fail tests.

## Learn the architecture

See [the developer guide](../document/DEVELOPER_GUIDE.md) for the stack, end-to-end request flows, trade-offs, concurrency, AI validation and exercises for reusing these patterns.
