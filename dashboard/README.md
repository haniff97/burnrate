# BurnRate dashboard

Mobile-first, buildless dashboard derived from `../deepseek-brain.md` and `../gemini-food-pipeline.md`.

## Run locally

From this directory:

```sh
python3 -m http.server 5173 --bind 127.0.0.1 --directory dist
```

Open http://127.0.0.1:5173. No dependency installation or compilation is required.

## Working features

- Responsive overview, journal dates and mobile bottom navigation.
- Food drafts, manual/catalog entries, editable servings, user calorie overrides, confirmation, saved meal presets and deletion.
- Photo attachment during review; the image is not analyzed or persisted.
- Energy, sleep, soreness and water logs.
- Configurable activity library, preferences, availability, partner confirmation and completed/partial session logging.
- Daily template planning with intake-floor validation, eating-window checks, recovery constraints and maintain-only activity sessions.
- Weight logging, measured trends, movement summaries and goal preferences.
- Browser-local persistence with JSON export/import and explicitly labeled sample data.

## Backend connection

A FastAPI/SQLite backend MVP is now available in `../backend`. When that server serves this dashboard, `config.js` enables anonymous server sessions, validated storage, server-calculated catalog nutrition and daily plans. Gemini analysis and optional DeepSeek refresh require server credentials. The browser keeps a backup; conflicting server revisions pause saving instead of overwriting newer data.

The public Sites deployment still runs in browser-local mode: it does not host Python or have AI credentials. Run the Python service locally to use the connected features. See `../backend/README.md` for commands and API details, and `../IMPLEMENTATION.md` for completed work and remaining limits.

Food values remain illustrative averages. A complete verified catalog, cross-device identity, scheduled jobs and reviewed health/progression policies are not implemented.

## Verification

```sh
node --check dist/app.js
node check.mjs
```

The domain checks cover incomplete meal logs, low energy, poor sleep, pain, partner availability, disabled activities, familiar-session scaling, impossible intake floors, eating-window conflict, complete low-intake days, hard sessions, weight coverage and unknown protein.

Browser QA: manual draft confirmation, updated totals, recovery-aware plan, custom activity creation, distance-based session logging, progress summaries and persistence across reload. Responsive layouts checked at 390 and 1440 pixels; no runtime console errors observed.

## Interface revision

The home screen follows the supplied minimalist mobile reference: gray canvas, oversized greeting, four rounded white action tiles, live search and a floating Home/Preferences dock with a separate add-entry button. Detailed daily metrics remain under View journal. Help and updates controls show working guidance and current missing-meal information. The public site remains accessible without login.
