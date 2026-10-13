"""Consistent SQLite snapshots, including committed WAL data."""
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


def backup_database(source, directory, keep=120):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    name = 'burnrate-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.sqlite3'
    destination = directory / name
    temporary = destination.with_suffix('.tmp')
    try:
        fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        source_uri = Path(source).resolve().as_uri() + '?mode=ro'
        with closing(sqlite3.connect(source_uri, uri=True, timeout=10)) as live:
            with closing(sqlite3.connect(temporary)) as snapshot:
                live.backup(snapshot)
                if snapshot.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise RuntimeError('Backup integrity check failed')
        os.replace(temporary, destination)
        # Prune only after a verified snapshot was written successfully.
        for old in sorted(directory.glob('burnrate-*.sqlite3'), reverse=True)[keep:]:
            old.unlink()
        return {'last_success': datetime.now(timezone.utc).isoformat(), 'error': None}
    finally:
        temporary.unlink(missing_ok=True)
