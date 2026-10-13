import hashlib
import json
import sqlite3
from pathlib import Path

class Conflict(Exception): pass

class Store:
    def __init__(self,path):
        self.path=str(path);Path(path).parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS journal(user_id TEXT PRIMARY KEY,revision INTEGER NOT NULL,json TEXT NOT NULL,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS journal_revision(user_id TEXT,revision INTEGER,json TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(user_id,revision));
            CREATE TABLE IF NOT EXISTS mutation(user_id TEXT,id TEXT,revision INTEGER,PRIMARY KEY(user_id,id));
            CREATE TABLE IF NOT EXISTS plan_revision(user_id TEXT,input_hash TEXT,json TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(user_id,input_hash));
            CREATE TABLE IF NOT EXISTS draft(user_id TEXT,id TEXT,json TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(user_id,id));
            CREATE TABLE IF NOT EXISTS cache(user_id TEXT,kind TEXT,key TEXT,json TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(user_id,kind,key));
            CREATE TABLE IF NOT EXISTS recovery(user_id TEXT PRIMARY KEY,code_hash TEXT UNIQUE NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            ''')
            # Preserve existing token-hash journal IDs while allowing new devices
            # to have independent cookie tokens pointing to the same journal.
            if 'journal_id' not in {r['name'] for r in db.execute('PRAGMA table_info(sessions)')}:
                db.execute('ALTER TABLE sessions ADD COLUMN journal_id TEXT')
            db.execute('UPDATE sessions SET journal_id=token_hash WHERE journal_id IS NULL')
    def connect(self):
        db=sqlite3.connect(self.path,timeout=10);db.row_factory=sqlite3.Row;db.execute('PRAGMA foreign_keys=ON');return db
    def session(self,token):
        key=hashlib.sha256(token.encode()).hexdigest()
        with self.connect() as db:db.execute('INSERT OR IGNORE INTO sessions(token_hash,journal_id) VALUES(?,?)',(key,key))
        return key
    def get(self,user):
        with self.connect() as db:r=db.execute('SELECT revision,json FROM journal WHERE user_id=?',(user,)).fetchone()
        return dict(revision=r['revision'],state=json.loads(r['json'])) if r else dict(revision=0,state=None)
    def save(self,user,expected,mutation_id,data):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            replay=db.execute('SELECT revision FROM mutation WHERE user_id=? AND id=?',(user,mutation_id)).fetchone()
            row=db.execute('SELECT revision,json FROM journal WHERE user_id=?',(user,)).fetchone()
            current=row['revision'] if row else 0
            if replay:return dict(revision=current,state=json.loads(row['json']))
            if current!=expected:raise Conflict()
            rev=current+1;encoded=json.dumps(data,allow_nan=False)
            db.execute('INSERT INTO journal(user_id,revision,json) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET revision=excluded.revision,json=excluded.json,updated_at=CURRENT_TIMESTAMP',(user,rev,encoded))
            db.execute('INSERT INTO journal_revision(user_id,revision,json) VALUES(?,?,?)',(user,rev,encoded))
            db.execute('INSERT INTO mutation VALUES(?,?,?)',(user,mutation_id,rev))
        return dict(revision=rev,state=data)
    def cached(self,user,kind,key):
        with self.connect() as db:r=db.execute('SELECT json FROM cache WHERE user_id=? AND kind=? AND key=?',(user,kind,key)).fetchone()
        return json.loads(r['json']) if r else None
    def cache(self,user,kind,key,value):
        with self.connect() as db:db.execute('INSERT OR REPLACE INTO cache(user_id,kind,key,json) VALUES(?,?,?,?)',(user,kind,key,json.dumps(value,allow_nan=False)))
    def draft(self,user,id,value):
        with self.connect() as db:db.execute('INSERT OR REPLACE INTO draft(user_id,id,json) VALUES(?,?,?)',(user,id,json.dumps(value,allow_nan=False)))
    def save_plan(self,user,key,value):
        with self.connect() as db:db.execute('INSERT OR REPLACE INTO plan_revision(user_id,input_hash,json) VALUES(?,?,?)',(user,key,json.dumps(value,allow_nan=False)))
    def get_plan(self,user,key):
        with self.connect() as db:r=db.execute('SELECT json FROM plan_revision WHERE user_id=? AND input_hash=?',(user,key)).fetchone()
        return json.loads(r['json']) if r else None
    def known_session(self,token):
        key=hashlib.sha256(token.encode()).hexdigest()
        with self.connect() as db:r=db.execute('SELECT journal_id FROM sessions WHERE token_hash=?',(key,)).fetchone()
        return r['journal_id'] if r else None
    def has_recovery(self,user):
        with self.connect() as db:return db.execute('SELECT 1 FROM recovery WHERE user_id=?',(user,)).fetchone() is not None
    def set_recovery(self,user,code):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM journal WHERE user_id=?',(user,)).fetchone():raise KeyError(user)
            db.execute('INSERT INTO recovery(user_id,code_hash) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET code_hash=excluded.code_hash,created_at=CURRENT_TIMESTAMP',(user,hashlib.sha256(code.encode()).hexdigest()))
    def recover_session(self,code,token):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            r=db.execute('SELECT user_id FROM recovery WHERE code_hash=?',(hashlib.sha256(code.encode()).hexdigest(),)).fetchone()
            if not r:return None
            db.execute('INSERT INTO sessions(token_hash,journal_id) VALUES(?,?)',(hashlib.sha256(token.encode()).hexdigest(),r['user_id']))
            return r['user_id']
    def get_draft(self,user,id):
        with self.connect() as db:r=db.execute('SELECT json FROM draft WHERE user_id=? AND id=?',(user,id)).fetchone()
        return json.loads(r['json']) if r else None
    def commit_plan(self,user,expected,key,value):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT revision FROM journal WHERE user_id=?',(user,)).fetchone()
            if not row or row['revision']!=expected:raise Conflict()
            db.execute('INSERT OR REPLACE INTO plan_revision(user_id,input_hash,json) VALUES(?,?,?)',(user,key,json.dumps(value,allow_nan=False)))
    def confirm_draft(self,user,draft_id,expected,mutation_id,meal):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT revision,json FROM journal WHERE user_id=?',(user,)).fetchone()
            if not row:raise Conflict()
            draft=db.execute('SELECT json FROM draft WHERE user_id=? AND id=?',(user,draft_id)).fetchone()
            if not draft:raise KeyError(draft_id)
            d=json.loads(draft['json'])
            data=json.loads(row['json'])
            replay=db.execute('SELECT revision FROM mutation WHERE user_id=? AND id=?',(user,mutation_id)).fetchone()
            if replay:return dict(revision=row['revision'],state=data)
            if d.get('status')=='confirmed':raise ValueError('Draft already confirmed')
            if row['revision']!=expected:raise Conflict()
            data['meals'].append(meal);data['revision']+=1;data['plan']=None
            revision=row['revision']+1;encoded=json.dumps(data,allow_nan=False)
            db.execute('UPDATE journal SET revision=?,json=?,updated_at=CURRENT_TIMESTAMP WHERE user_id=?',(revision,encoded,user))
            db.execute('INSERT INTO journal_revision(user_id,revision,json) VALUES(?,?,?)',(user,revision,encoded))
            db.execute('INSERT INTO mutation VALUES(?,?,?)',(user,mutation_id,revision))
            d['status']='confirmed';d['meal_id']=meal['id']
            db.execute('UPDATE draft SET json=? WHERE user_id=? AND id=?',(json.dumps(d),user,draft_id))
            return dict(revision=revision,state=data)
