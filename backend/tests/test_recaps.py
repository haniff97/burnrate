from datetime import datetime,timedelta,timezone
import time
from fastapi.testclient import TestClient
from app.main import create_app
from app.storage import Store
from app.recaps import seconds_until_midnight,build_recap,ZONE
from test_api import state,TODAY


def test_midnight_uses_malaysia_timezone():
    assert seconds_until_midnight(datetime(2026,10,14,15,59,59,tzinfo=timezone.utc))==1
    assert seconds_until_midnight(datetime(2026,12,31,23,59,tzinfo=ZONE))==60
    assert seconds_until_midnight(datetime(2026,10,15,0,0,tzinfo=ZONE))==86400


def test_recap_frozen_once_with_correct_dates(tmp_path):
    store=Store(tmp_path/'journal.db');uid=store.session('a'*64);data=state()
    data['days'][TODAY]={'water':1.5,'sleep':5,'energy':2,'soreness':'none'}
    data['activities'].append({'id':'walk','name':'Walking','icon':'walk','type':'cardio','metric':'duration','preference':'mid','enabled':True,'partner':False,'available':True})
    data['sessions'].append({'id':'walk-1','date':TODAY,'name':'Walking','activityId':'walk','duration':20,'effort':3,'status':'completed','steps':2500})
    store.save(uid,0,'one',data)
    assert store.freeze_recaps(TODAY,'2026-10-15T00:00:00+08:00')==1
    first=store.latest_recap(uid)
    assert first['steps']==2500
    assert first['movement_minutes']==20
    assert first['food']['kcal_used'] is None
    assert first['next_plan']['rest'] is True
    assert first['next_plan']['date']==(datetime.fromisoformat(TODAY)+timedelta(days=1)).date().isoformat()
    data['days'][TODAY]['water']=3
    store.save(uid,1,'two',data)
    assert store.freeze_recaps(TODAY,'later',True)==0
    assert store.latest_recap(uid)==first
    assert Store(tmp_path/'journal.db').latest_recap(uid)==first
    outsider=store.session('b'*64)
    assert store.latest_recap(outsider) is None


def test_delayed_recap_excludes_future_logs():
    data=state();future=(datetime.fromisoformat(TODAY)+timedelta(days=1)).date().isoformat()
    data['weights']=[{'date':future,'kg':70}]
    data['sessions']=[{'date':future,'duration':20,'steps':2000,'effort':10,'activityId':'jog','name':'Jogging','status':'completed'}]
    result=build_recap(data,TODAY,1,'later',True)
    assert result['delayed']
    assert result['goal']['latest_kg'] is None
    assert result['movement_minutes']==0
    assert result['steps'] is None
    assert result['next_plan']['activity'] is not None


def test_endpoint_reads_only_without_generating_at_startup(tmp_path):
    path=tmp_path/'journal.db';store=Store(path);uid=store.session('a'*64)
    store.save(uid,0,'one',state())
    with TestClient(create_app(path)) as client:
        assert client.get('/api/daily-recap').status_code==401
        client.cookies.set('burnrate_session','a'*64)
        assert client.get('/api/daily-recap').json()['recap'] is None
        store.freeze_recaps(TODAY,'midnight')
        first=client.get('/api/daily-recap').json()['recap']
        assert first['day']==TODAY
        assert client.get('/api/daily-recap').json()['recap']==first
        other=TestClient(create_app(path));other.get('/api/session')
        assert other.get('/api/daily-recap').json()['recap'] is None


def test_lifespan_scheduler_persists_recap_at_boundary(tmp_path,monkeypatch):
    path=tmp_path/'journal.db';store=Store(path);uid=store.session('a'*64)
    store.save(uid,0,'one',state())
    boundary=datetime.fromisoformat(TODAY).replace(tzinfo=ZONE)+timedelta(days=1)
    monkeypatch.setattr('app.main.now_local',lambda:boundary)
    delays=iter([0.01,86400])
    monkeypatch.setattr('app.main.seconds_until_midnight',lambda now:next(delays,86400))
    with TestClient(create_app(path)):
        deadline=time.monotonic()+2
        while store.latest_recap(uid) is None and time.monotonic()<deadline:time.sleep(0.01)
        recap=store.latest_recap(uid)
        assert recap is not None
        assert recap['day']==TODAY
        assert recap['generated_at']==boundary.isoformat()
        assert recap['delayed'] is False
