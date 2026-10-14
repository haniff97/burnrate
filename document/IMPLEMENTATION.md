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
- DeepSeek can be enabled directly on My plan or in Settings. AI-composed meals, template plans and fallback notices are labelled separately.
- Custom dropdowns across pages/dialogs, editable/deletable journal meals, quick water logging, walking steps and Minutes/All day duration modes.
- A frozen midnight recap card appears at the top of the journal, generated only at 00:00 Malaysia time.

### Python backend

- FastAPI routes for sessions, journal snapshots, catalog, daily summary, plans, weekly reviews and photo drafts.
- SQLite journal revisions, idempotent mutation records, draft records and user-scoped caches.
- Anonymous HttpOnly cookie sessions isolate journals without a login screen. Recovery codes can link additional browser sessions to the same journal.
- Automatic SQLite snapshots on startup and every six hours, with the newest 120 retained; off-server replication remains an operator task.
- Strict validation for types, ranges, dates, record references, serving units and eating-window conflicts.
- Python recalculates catalog nutrition and never trusts client-provided plan totals.
- Missing food intake and wholly unknown protein remain unknown, not zero.
- Rolling template plans respond to recovery, logged effort, available time and partner status.
- Optional DeepSeek plans compose three meals from the five-food catalog, using seven-day food/recovery summaries, fourteen-day activity logs, goal context and two-week weight averages.
- Python checks slots, food IDs, serving bounds, whole-unit portions, intake floor and activity limits, then recalculates calories and protein. Protein remains a reference, with a visible warning if unmet.
- Plans that cannot meet configured constraints return a needs-attention state.
- Gemini adapter: structured recognition, edible portion ranges, local nutrition lookup, batched unknown-food estimates and draft confirmation.
- DeepSeek adapter: schema validation, candidate constraints, a bounded repair request, server-calculated totals and rules fallback.
- Stale AI results cannot publish over a newer journal revision.
- Weekly AI review endpoint preserves the current goal date; proposed dates remain proposals.
- Request origin checks, bounded bodies and images, no raw-photo retention and a per-session AI quota.

## Verification completed

- All 52 Python API tests passed, including mocked-provider, storage, recovery, snapshots, midnight scheduling, steps, duration modes and dynamic-plan tests.
- All 13 JavaScript planning checks passed; recovery-file checks and JavaScript syntax checks also passed during their implementation.
- Browser integration verified against the running Python service: a water update persisted, reloaded, and generated a server-validated plan.
- SQLite inspection confirmed stored journal revisions and plan records.
- Initial tests used mocked providers. See the AI configuration update below for subsequent live connection checks.

## Remaining work and deliberate MVP limits

| Area | Current status / next step |
|---|---|
| Public backend | Updated service tested locally; user previously deployed an earlier version to Orange Pi via PM2; newest changes still need deployment. Sites hosting remains static |
| AI activation | Keys and models configured; DeepSeek and Gemini synthetic live format tests passed |
| Cross-device identity | Recovery-code pairing implemented; account recovery, device revocation and automatic live sync remain pending |
| Nutrition source | Illustrative averages; replace with verified source records |
| Food learning | Presets supported; richer alias, calibration and food-catalog CRUD pending |
| Portion geometry | Units, mass ranges and volume ranges supported; calibration pending |
| Weekly review UI | Endpoint and Review now dialog implemented; static mode retains the local reflection |
| Goal proposal decisions | No accept/decline endpoint or decision history UI yet |
| Scheduling | Frozen recap runs at 00:00 Malaysia time while the server is running; it uses rules, not AI. AI plans refresh on demand; scheduled AI plans and weekly jobs remain pending |
| Data model | Validated journal snapshots + revision tables; normalized per-entity tables pending |
| Recovery policy | Conservative maintain/rest MVP; progression and health policy review pending |
| Reliability | Server queue pauses on failure/conflict; automated reconnect/offline reconciliation pending |
| Public operations | Local SQLite snapshots implemented; HTTPS, persistent storage, off-server backup scheduling, perimeter controls and distributed quotas still needed |

## Where to find it

- Backend entrypoint: `backend/app/main.py`.
- Validation: `backend/app/models.py`.
- Storage: `backend/app/storage.py`.
- Food pipeline: `backend/app/food.py`.
- Provider adapters: `backend/app/providers.py`.
- Python planning: `backend/app/planner.py`.
- Dashboard connection: `frontend/dist/server.js`.
- Custom dropdowns: `frontend/dist/dropdowns.mjs`.
- Midnight scheduling / recap calculation: `backend/app/recaps.py` and the lifespan in `main.py`.
- Snapshot helper: `backend/app/backups.py`.
- Setup and endpoint reference: `backend/README.md`.
- Design specifications: `deepseek-brain.md` and `gemini-food-pipeline.md`.

See `backend/README.md` for the launch command. Open `http://127.0.0.1:8000` when the service is running; API documentation is at `/api/docs`.

## AI configuration update — October 14, 2026

`backend/.env` now loads automatically on startup; existing process environment variables take precedence. Model IDs are configured as `gemini-3.5-flash-lite` and `deepseek-flash`. The keys were preserved and were not printed. DeepSeek uses non-thinking mode for bounded daily JSON output, and a live synthetic structured-output smoke test passed. Gemini's model-list request succeeded, but generation returned HTTP 402 indicating depleted prepaid credits. At that stage Gemini food analysis was blocked until billing was resolved; the follow-up below records its resolution. No billing change or purchase was made. Permanent provider/configuration errors no longer consume the repair retry.

## Gemini billing and compatibility follow-up — October 14, 2026

After billing was updated, basic Gemini requests succeeded. The nested API-native response schema was rejected with HTTP 400, so the adapter now requests JSON mode, puts the full output contract in the prompt, and validates all returned fields and cross-field constraints with Pydantic. Invalid outputs still receive only one repair attempt. Live synthetic tests passed for an image input and nutrition-estimate JSON. This does not establish real meal-recognition or calorie accuracy, which still requires the weighed-meal evaluation described in the specifications. Model IDs and keys were preserved.

## Dynamic AI planning update — October 14, 2026

### How to use it

Open **My plan**, enable **Use DeepSeek to compose meals and personalize activity**, then choose **Refresh plan**. This sends the calculated brief and recent logs to the configured server-side DeepSeek provider. The toggle is currently held in the page session; check it again after reloading.

A successful composed plan shows **AI-composed · validated**, alongside **AI plan · server validated**. The AI may vary catalog-food combinations and servings, and choose a shorter eligible activity. It cannot add unknown foods, override the goal or meal times, lower the configured intake floor, or exceed the familiar-load/time limit.

### What the model receives

- Seven days of food completeness, totals and recovery check-ins.
- Fourteen days of activity, including steps and all-day entries.
- Current and previous seven-day weight averages. A difference is supplied only when each window has at least three measurements.
- Latest logged weight, configured goal/date, activity eligibility, recent confirmed food names, catalog nutrition and per-meal serving bounds.

Missing logs remain incomplete information. Weight change is descriptive context, not proof of a calorie deficit or its cause. Plans support a routine without guaranteeing the goal date.

### Validation and fallback

The expanded `PlanChoice` contract accepts three composed meals and an optional activity duration. Python owns calorie/protein calculations and validates the choices. The provider gets at most one repair retry; schema feedback identifies the failing field without echoing model output. Invalid or unavailable AI output falls back to rules with a visible notice. An impossible rules plan stays in a needs-attention state. Revision checks still prevent stale AI output from being published, and cache schema version 2 separates these plans from older results.

The current five-food catalog limits variety. Dietary exclusions, a larger verified catalog, automatic progression and calorie-target adjustment are not implemented. The midnight recap remains a separate rules-based frozen snapshot; turning on AI refresh does not enable AI at midnight.

### Verification

A live synthetic DeepSeek request produced validated AI-composed meals after bounded constraint repair. Browser verification also displayed an AI-composed plan with a different menu and a walking session. This verifies connectivity and contract handling; it does not establish nutrition accuracy or guaranteed goal attainment.

See [the developer guide](DEVELOPER_GUIDE.md) for the expanded contract and implementation flow.

## Learn the architecture

See [the developer guide](DEVELOPER_GUIDE.md) for the stack, end-to-end request flows, trade-offs, concurrency, AI validation and exercises for reusing these patterns.
