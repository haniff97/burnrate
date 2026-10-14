# BurnRate

A mobile-first dashboard for tracking food, movement, weight, and recovery. BurnRate builds a rolling daily plan from your logs and preferences instead of following a fixed three-month schedule.

## Features

- Log meals manually, reuse saved meals, or analyze food photos with Gemini.
- Track weight, water, sleep, energy, and activities such as jogging, pull-ups, and badminton.
- Add custom activities and manage preferences and partner availability.
- Generate daily plans with Python rules or DeepSeek meal composition using logs, weight trends and recovery.
- Review progress, weekly summaries, and a midnight recap with next-day focus (Malaysia time).
- Recover the same journal with a saved code and keep automatic SQLite snapshots.

Built with HTML, CSS, JavaScript, Python, FastAPI, and SQLite. The local backend saves journals using anonymous browser sessions, with no login screen.

## Project folders

| Folder | Contents |
| --- | --- |
| `backend/` | Python API, SQLite storage, tests, environment configuration and PM2 configuration |
| `frontend/` | HTML, CSS, JavaScript, frontend checks and Sites hosting metadata |
| `mock/` | Saved UI screenshots and historical deployment archives |
| `document/` | Developer guide, specifications, implementation notes and recovery instructions |

The files in `frontend/dist/` are maintained source files; no frontend build step is required.

## Run locally

Requires Python 3.12 or newer. From the project root:

```sh
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The backend creates its SQLite database automatically.

On Windows, use `backend\.venv\Scripts\python.exe` instead of `backend/.venv/bin/python`.

## Run on a Linux server with PM2

After creating the virtual environment, installing dependencies, and configuring `backend/.env`, run from the project root:

```sh
pm2 start backend/ecosystem.config.js
pm2 save
pm2 logs burnrate --lines 30
```

The app listens on port **4007**. The configuration runs one Python process and restarts it if it exits. API keys stay in `backend/.env`. After changing configuration or updating the app, run `pm2 restart burnrate`.

If PM2 is not already configured to start on boot, run `pm2 startup`, follow the command it prints, then run `pm2 save` again.

## Optional AI setup

Copy `backend/.env.example` to `backend/.env` if it does not already exist, then fill in:

```env
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-3.5-flash-lite
DEEPSEEK_API_KEY=your_deepseek_key
DEEPSEEK_MODEL=deepseek-flash
```

The backend loads `.env` automatically. Restart it after changing configuration. Keep API keys private; `.env` is excluded from Git.

For an AI plan, open **My plan**, enable **Use DeepSeek to compose meals and personalize activity**, then choose **Refresh plan**. AI composes catalog meals using your logs and trend context; Python validates portions, totals and activity limits. The midnight recap remains rules-based.

Without AI keys, manual food logging and template planning still work. Food estimates are approximate and remain editable before confirmation.

## Notes

The app opens with labeled sample data. Use **Settings → Start fresh** to begin your own journal. The hosted static dashboard uses browser-local storage; server storage and AI features require the Python service.

For more detail, see [backend setup](backend/README.md), [implementation status](document/IMPLEMENTATION.md), or the [developer guide](document/DEVELOPER_GUIDE.md).

New to cookies? Read [how BurnRate remembers your journal](document/browser-sessions/README.md), including phone restarts, LAN/VPN addresses, and backups.

To protect your data, follow [recovery and backups](document/data-protection/README.md). Create a recovery code in Settings and keep an off-server copy of your backups.
