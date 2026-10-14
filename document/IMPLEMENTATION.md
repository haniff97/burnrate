# BurnRate implementation status

Updated: October 14, 2026 (Asia/Kuala_Lumpur).

## What has been done

The dashboard and a Python backend MVP are implemented. The local Python app serves both the dashboard and API on one origin. The published Sites dashboard continues to use browser-local storage until the backend is deployed and routed to that origin.

### Dashboard

- Mobile-first monochrome interface based on the supplied design reference.
- Homepage fits tested 390 × 844 and 320 × 667 phone viewports, with daily information before actions.
- Gear on the far right, notification bell to its left, floating Home/Journal controls and add menu.
- Food drafts, editable portions, confirmed entries, meal presets and manual overrides.
- Weight trends, custom activities, partner availability, completed/partial sessions, water and recovery.
- Reflection card above the weight chart and repaired nourishment-card layout.
- Optional Python connection, server save queue, revision conflict detection and browser backup.
- Gemini photo-analysis controls appear only when the server has credentials.
- DeepSeek plan refresh can be enabled explicitly when configured.

### Python backend

- FastAPI routes for sessions, journal snapshots, catalog, daily summary, plans, weekly reviews and photo drafts.
- SQLite journal revisions, idempotent mutation records, draft records and user-scoped caches.
- Anonymous HttpOnly cookie sessions keep different browsers' journals isolated without a login screen.
- Strict validation for types, ranges, dates, record references, serving units and eating-window conflicts.
- Python recalculates catalog nutrition and never trusts client-provided plan totals.
- Missing food intake and wholly unknown protein remain unknown, not zero.
- Rolling template plans respond to recovery, logged effort, available time and partner status.
- Plans that cannot meet configured constraints return a needs-attention state.
- Gemini adapter: structured recognition, edible portion ranges, local nutrition lookup, batched unknown-food estimates and draft confirmation.
- DeepSeek adapter: schema validation, candidate constraints, a bounded repair request, server-calculated totals and rules fallback.
- Stale AI results cannot publish over a newer journal revision.
- Weekly AI review endpoint preserves the current goal date; proposed dates remain proposals.
- Request origin checks, bounded bodies and images, no raw-photo retention and a per-session AI quota.

## Verification completed

- Python API tests passed, including mocked-provider and storage tests.
- Existing JavaScript planning checks passed.
- Browser integration verified against the running Python service: a water update persisted, reloaded, and generated a server-validated plan.
- SQLite inspection confirmed stored journal revisions and plan records.
- Initial tests used mocked providers. See the AI configuration update below for subsequent live connection checks.

## Remaining work and deliberate MVP limits

| Area | Current status / next step |
|---|---|
| Public backend | Python service runs locally; existing Sites hosting remains static |
| AI activation | Keys and models configured; DeepSeek and Gemini synthetic live format tests passed |
| Cross-device identity | Anonymous browser cookie only; account or pairing flow needed |
| Nutrition source | Illustrative averages; replace with verified source records |
| Food learning | Presets supported; richer alias, calibration and food-catalog CRUD pending |
| Portion geometry | Units, mass ranges and volume ranges supported; calibration pending |
| Weekly review UI | Endpoint and Review now dialog implemented; static mode retains the local reflection |
| Goal proposal decisions | No accept/decline endpoint or decision history UI yet |
| Scheduling | Plans refresh on demand or after saves; nightly and weekly jobs pending |
| Data model | Validated journal snapshots + revision tables; normalized per-entity tables pending |
| Recovery policy | Conservative maintain/rest MVP; progression and health policy review pending |
| Reliability | Server queue pauses on failure/conflict; automated reconnect/offline reconciliation pending |
| Public operations | HTTPS, persistent volume, perimeter controls, backups and distributed quotas needed |

## Where to find it

- Backend entrypoint: `backend/app/main.py`.
- Validation: `backend/app/models.py`.
- Storage: `backend/app/storage.py`.
- Food pipeline: `backend/app/food.py`.
- Provider adapters: `backend/app/providers.py`.
- Python planning: `backend/app/planner.py`.
- Dashboard connection: `frontend/dist/server.js`.
- Setup and endpoint reference: `backend/README.md`.
- Design specifications: `deepseek-brain.md` and `gemini-food-pipeline.md`.

See `backend/README.md` for the launch command. Open `http://127.0.0.1:8000` when the service is running; API documentation is at `/api/docs`.

## AI configuration update — October 14, 2026

`backend/.env` now loads automatically on startup; existing process environment variables take precedence. Model IDs are configured as `gemini-3.5-flash-lite` and `deepseek-flash`. The keys were preserved and were not printed. DeepSeek uses non-thinking mode for bounded daily JSON output, and a live synthetic structured-output smoke test passed. Gemini's model-list request succeeded, but generation returned HTTP 402 indicating depleted prepaid credits. Gemini food analysis remains blocked until the project's billing is resolved. No billing change or purchase was made. Permanent provider/configuration errors no longer consume the repair retry.

## Gemini billing and compatibility follow-up — October 14, 2026

After billing was updated, basic Gemini requests succeeded. The nested API-native response schema was rejected with HTTP 400, so the adapter now requests JSON mode, puts the full output contract in the prompt, and validates all returned fields and cross-field constraints with Pydantic. Invalid outputs still receive only one repair attempt. Live synthetic tests passed for an image input and nutrition-estimate JSON. This does not establish real meal-recognition or calorie accuracy, which still requires the weighed-meal evaluation described in the specifications. Model IDs and keys were preserved.

## Learn the architecture

See [the developer guide](DEVELOPER_GUIDE.md) for the stack, end-to-end request flows, trade-offs, concurrency, AI validation and exercises for reusing these patterns.
