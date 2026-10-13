# Recovering and backing up your BurnRate journal

BurnRate now has two protections: a recovery code reconnects you to an existing journal, and SQLite snapshots preserve copies of the server database. Neither guarantees that every unsaved or recent change survives every failure.

## Set up recovery now

1. Deploy this version and restart the Python service.
2. Open the address and browser containing the journal you want to keep.
3. Go to **Settings → Recovery & backups → Create recovery code**.
4. Save the code in a password manager or download it and keep it outside the browser.
5. Check that the same panel shows a successful server backup.

The code is displayed once. The server stores only its SHA-256 hash. The code contains 128 bits of cryptographically generated randomness, is reusable, and currently has no expiry. Anyone who obtains it can open this journal, so treat it like a password.

Creating a replacement invalidates the previous recovery code. It does not disconnect devices that are already linked. Device revocation is not implemented.

## Recover after losing cookies, or connect another device

Open your Python backend address and choose **Settings → Recover journal**. Enter the saved code. BurnRate requests a JSON export of the current browser journal before switching; check that the browser saved that download if you need it.

The backend creates a new cookie token linked to the recovered journal. The current browser's former server journal remains separate. Recovery does not merge journals.

Both devices now read and write the same journal, including when LAN and VPN use different host addresses. A conflicting write returns HTTP 409 and pauses saving rather than overwriting newer data. Export unsaved edits before reloading. Live updates between open devices are not implemented; refresh to fetch changes made elsewhere.

Codes work only on the server database that contains their hashes. A code does not contain your data and cannot recreate a deleted database. Back up the database too.

## How the backend implements recovery

Previously the cookie hash was both the session key and the journal ID. Now the `sessions` table has a `journal_id` column:

```text
Browser A cookie hash → journal_id X
Browser B cookie hash → journal_id X
Recovery code hash    → journal_id X
SQLite journal X     → saved data
```

Startup migrates existing sessions by setting `journal_id = token_hash`. Existing cookies and journal IDs continue working. New recovery sessions point to that same journal ID; journal rows are not copied or renamed.

| API | Purpose |
| --- | --- |
| `GET /api/protection` | Shows whether this journal has a code, and backup status |
| `POST /api/recovery/code` | Creates or replaces the current journal's code; requires a session and saved journal |
| `POST /api/recovery/restore` | Accepts `{ "code": "BR-…" }`, sets a new cookie and returns the recovered journal |

Origin checks also apply to recovery. Recovery attempts are limited to ten per client IP per fifteen minutes, in process memory. The limit resets on restart and is not distributed across servers. Reverse proxies can affect which client IP is seen.

Codes are sent in POST bodies, never URLs, and are not stored in frontend local storage. Use HTTPS for deployment beyond your trusted network so cookies and recovery codes are encrypted in transit.

## Automatic server backups

The Python service creates a snapshot during startup, then every six hours while it runs. It keeps the latest 120 snapshots. At an uninterrupted six-hour interval this covers about thirty days; frequent restarts create additional snapshots and shorten that time coverage.

The default directory is `backups` beside the configured database, normally `backend/backups/`. Filenames include a UTC timestamp. Snapshots include journals, revisions, session mappings and recovery hashes; they do not include `.env`, provider API keys or browser-only unsaved data.

`backend/app/backups.py` uses SQLite's backup API, including committed changes in the write-ahead log. It writes to a temporary file, runs an integrity check, closes connections, then renames the result. Older snapshots are pruned only after a successful new snapshot. Snapshot files have mode `600`; newly created backup directories have mode `700`.

Backup failures do not stop the app. They appear in Settings and PM2 logs. Therefore, periodically check the latest backup date and error status.

Optional configuration in `backend/.env`:

```env
BURNRATE_BACKUP_INTERVAL_HOURS=6
# Prefer a separately mounted disk when available:
# BURNRATE_BACKUP_DIR=/mnt/another-disk/burnrate-backups
```

Restart with `pm2 restart burnrate` after changes. Changing the interval keeps the retention count at 120. Backup scheduling assumes one backend process, as in the supplied PM2 configuration.

## Keep a copy outside the server

Default snapshots on the same disk help with accidental deletion or database corruption, but losing that disk can lose both the journal and snapshots. A different folder on the same disk does not solve this.

For the default server path, run this on your Mac to copy snapshots to a local folder:

```sh
mkdir -p "$HOME/BurnRate-backups"
chmod 700 "$HOME/BurnRate-backups"
scp -r root@192.168.1.10:/mnt/nvme/Projects/burnrate/backend/backups/. "$HOME/BurnRate-backups/"
```

This is a manual off-server copy, not an installed schedule. Repeat it regularly, or configure your existing backup service to copy the snapshot directory to another device. Keep those copies private because they include journal data and session mappings.

Continue using **Settings → Export JSON** before clearing browser data, importing another journal, or making changes you may want to undo. These exports can be imported through the app without restoring the entire server database.

## If a database restore is needed

Stop BurnRate first. Preserve the current database and any `-wal` / `-shm` files separately before replacing anything. Restore a verified snapshot to the configured `BURNRATE_DB` path, remove the old sidecars from that active path, set restrictive permissions, then restart.

Restoring a snapshot rolls back all journals and session/recovery mappings to its timestamp. Codes and cookies created after that snapshot may stop working. Changes after the snapshot are not in that copy. Never replace a live SQLite database while PM2 is running it.

The automated tests verify migration of an old database, recovery after service restart, code replacement, isolation of the previous journal, guessing limits, WAL-inclusive snapshots, retention, file permissions and visible backup failure status.
