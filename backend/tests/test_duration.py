import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.models import Session
from app.recaps import build_recap
from test_api import state,TODAY

def session(**fields):
    return {'id':'walk-day','date':TODAY,'activityId':'walk','name':'Walking','duration':None,'duration_mode':'all_day','steps':4500,'effort':3,'status':'completed',**fields}

def test_all_day_saved_without_inventing_minutes(tmp_path):
    with TestClient(create_app(tmp_path/'journal.db')) as client:
        client.get('/api/session');data=state()
        data['activities']=[{'id':'walk','name':'Walking','icon':'walk','type':'cardio','metric':'duration','preference':'most','enabled':True,'partner':False,'available':True}]
        data['sessions']=[session()]
        saved=client.put('/api/state',json={'expected_revision':0,'mutation_id':'walk','state':data})
        assert saved.status_code==200
        loaded=client.get('/api/state').json()['state']
        assert loaded['sessions'][0]['duration'] is None
        assert loaded['sessions'][0]['duration_mode']=='all_day'
        recap=build_recap(loaded,TODAY,1,'midnight')
        assert recap['movement_minutes']==0
        assert recap['all_day_sessions']==1
        assert recap['steps']==4500
        plan=client.post('/api/plans',json={'expected_revision':1,'date':TODAY,'use_ai':False})
        assert plan.status_code==200
        assert plan.json()['activity']['duration']==20

def test_legacy_minutes_keep_default_mode():
    entry=session(duration=25)
    del entry['duration_mode']
    assert Session.model_validate(entry).duration_mode=='minutes'

@pytest.mark.parametrize('mode,duration',[('minutes',None),('minutes',0),('all_day',20),('hours',20)])
def test_inconsistent_duration_rejected(mode,duration):
    with pytest.raises(ValueError):Session.model_validate(session(duration_mode=mode,duration=duration))
