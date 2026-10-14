import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from test_api import state, TODAY


@pytest.mark.parametrize('steps',[None,0,3500,200000])
def test_walking_steps_round_trip(tmp_path,steps):
    app=create_app(tmp_path/'journal.db')
    with TestClient(app) as client:
        client.get('/api/session')
        data=state()
        data['activities'].append({'id':'walk','name':'Walking','icon':'walk','type':'cardio','metric':'duration','preference':'mid','enabled':True,'partner':False,'available':True})
        session={'id':'walk-1','date':TODAY,'activityId':'walk','name':'Walking','duration':20,'effort':3,'status':'completed'}
        if steps is not None:session['steps']=steps
        data['sessions'].append(session)
        saved=client.put('/api/state',json={'expected_revision':0,'mutation_id':'walk','state':data})
        assert saved.status_code==200
        assert client.get('/api/state').json()['state']['sessions'][0]['steps']==steps
        # An optional step count does not change activity-metric validation or planning.
        assert client.post('/api/plans',json={'expected_revision':1,'date':TODAY,'use_ai':False}).status_code==200


@pytest.mark.parametrize('steps',[-1,1.5,200001,'3500'])
def test_invalid_steps_rejected(tmp_path,steps):
    with TestClient(create_app(tmp_path/'journal.db')) as client:
        client.get('/api/session')
        data=state()
        data['sessions'].append({'id':'jog-1','date':TODAY,'activityId':'jog','name':'Jogging','distance':2,'duration':20,'effort':3,'status':'completed','steps':steps})
        response=client.put('/api/state',json={'expected_revision':0,'mutation_id':'invalid','state':data})
        assert response.status_code==422
        assert client.get('/api/state').json()['state'] is None
