# BurnRate

A mobile-first dashboard for tracking food, movement, weight, and recovery. BurnRate builds a rolling daily plan from your logs and preferences instead of following a fixed three-month schedule.

## Features

- Log meals manually, reuse saved meals, or analyze food photos with Gemini.
- Track weight, water, sleep, energy, and activities such as jogging, pull-ups, and badminton.
- Add custom activities and manage preferences and partner availability.
- Generate daily plans with Python rules or optional DeepSeek assistance.
- Review progress and weekly summaries.

Built with HTML, CSS, JavaScript, Python, FastAPI, and SQLite. The local backend saves journals using anonymous browser sessions, with no login screen.

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
pm2 start ecosystem.config.js
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

Without AI keys, manual food logging and template planning still work. Food estimates are approximate and remain editable before confirmation.

## Notes

The app opens with labeled sample data. Use **Settings → Start fresh** to begin your own journal. The hosted static dashboard uses browser-local storage; server storage and AI features require the Python service.

For more detail, see [backend setup](backend/README.md), [implementation status](IMPLEMENTATION.md), or the [developer guide](DEVELOPER_GUIDE.md).
