import hashlib
import sqlite3
from contextlib import closing

from fastapi.testclient import TestClient
from app.main import create_app
from app.storage import Store
from app.backups import backup_database
from test_api import state


def test_legacy_database_migration(tmp_path):
    path=tmp_path/'old.db'
    token='a'*64;key=hashlib.sha256(token.encode()).hexdigest()
    with closing(sqlite3.connect(path)) as db:
        db.execute('CREATE TABLE sessions(token_hash TEXT PRIMARY KEY,created_at TEXT DEFAULT CURRENT_TIMESTAMP)')
        db.execute('INSERT INTO sessions(token_hash) VALUES(?)',(key,));db.commit()
    store=Store(path)
    store.save(key,0,'old-save',state())
    assert store.known_session(token)==key
    Store(path) # Migration is repeatable.
    assert store.get(key)['state']['settings']['name']=='Test'


def test_recovery_links_devices_and_replaces_code(tmp_path):
    path=tmp_path/'journal.db'
    with TestClient(create_app(path)) as original, TestClient(create_app(path)) as other:
        original.get('/api/session')
        original.put('/api/state',json={'expected_revision':0,'mutation_id':'initial','state':state()})
        code=original.post('/api/recovery/code').json()['code']
        other.get('/api/session')
        outsider_state=state();outsider_state['settings']['name']='Other'
        other.put('/api/state',json={'expected_revision':0,'mutation_id':'initial','state':outsider_state})
        old_cookie=other.cookies.get('burnrate_session')
        result=other.post('/api/recovery/restore',json={'code':code.lower()})
        assert result.status_code==200
        assert result.json()['state']['settings']['name']=='Test'
        assert other.cookies.get('burnrate_session')!=old_cookie
        updated=state();updated['settings']['name']='Shared'
        assert other.put('/api/state',json={'expected_revision':1,'mutation_id':'edit','state':updated}).status_code==200
        assert original.get('/api/state').json()['state']['settings']['name']=='Shared'
        replacement=original.post('/api/recovery/code').json()['code']
        assert other.post('/api/recovery/restore',json={'code':code}).status_code==400
        assert other.get('/api/state').json()['state']['settings']['name']=='Shared'
        assert other.post('/api/recovery/restore',json={'code':replacement}).status_code==200
        with closing(sqlite3.connect(path)) as db:
            assert db.execute('SELECT code_hash FROM recovery').fetchone()[0]!=replacement
        # Changing sessions does not erase the browser's former server journal.
        assert Store(path).get(Store(path).known_session(old_cookie))['state']['settings']['name']=='Other'
    with TestClient(create_app(path)) as restarted:
        assert restarted.post('/api/recovery/restore',json={'code':replacement}).json()['state']['settings']['name']=='Shared'


def test_recovery_access_limits_and_origin(tmp_path):
    with TestClient(create_app(tmp_path/'journal.db')) as client:
        assert client.post('/api/recovery/code').status_code==401
        assert client.post('/api/recovery/restore',headers={'Origin':'https://other.example'},json={'code':'invalid'}).status_code==403
        client.get('/api/session')
        assert client.post('/api/recovery/code').status_code==409
        for _ in range(10):assert client.post('/api/recovery/restore',json={'code':'BR-'+'0'*32}).status_code==400
        assert client.post('/api/recovery/restore',json={'code':'BR-'+'0'*32}).status_code==429


def test_backup_includes_wal_and_recovery_and_retention(tmp_path):
    path=tmp_path/'journal.db';directory=tmp_path/'snapshots'
    store=Store(path);user=store.session('a'*64)
    # Hold a connection open so committed writes can still live in WAL.
    with closing(sqlite3.connect(path)) as live:
        live.execute('PRAGMA journal_mode=WAL')
        store.save(user,0,'save',state());store.set_recovery(user,'A'*32)
        for _ in range(4):backup_database(path,directory,keep=2)
    files=sorted(directory.glob('*.sqlite3'))
    assert len(files)==2
    assert not list(directory.glob('*.tmp'))
    assert files[-1].stat().st_mode & 0o777==0o600
    restored=Store(files[-1])
    assert restored.get(user)['state']['settings']['name']=='Test'
    assert restored.known_session('a'*64)==user
    assert restored.recover_session('A'*32,'b'*64)==user


def test_backup_status_and_failure_are_visible(tmp_path,monkeypatch):
    with TestClient(create_app(tmp_path/'journal.db')) as client:
        client.get('/api/session')
        status=client.get('/api/protection').json()
        assert status['backup']['last_success']
        assert status['backup']['error'] is None
        assert status['recovery_enabled'] is False
    def fail(*args):raise OSError('No writable disk')
    monkeypatch.setattr('app.main.backup_database',fail)
    with TestClient(create_app(tmp_path/'journal.db')) as client:
        client.get('/api/session')
        status=client.get('/api/protection').json()
        assert status['backup']['last_success'] is None
        assert status['backup']['error']
        assert client.get('/api/health').status_code==200
