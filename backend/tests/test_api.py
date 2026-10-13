import base64
import io
import json
import math
from copy import deepcopy
from datetime import timedelta
import httpx
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from app.main import create_app
from app.models import local_today,PhotoRequest
from app.providers import Providers,Recognition,PlanChoice,ProviderUnavailable
from app.food import analyze
from app.planner import plan

TODAY=local_today().isoformat()

def state():
    return {'version':1,'demo':False,'revision':0,'settings':{'name':'Test','startWeight':75.9,'targetWeight':66,'endDate':(local_today()+timedelta(days=90)).isoformat(),'calorieFloor':1500,'proteinTarget':120,'waterTarget':2.5,'availableMinutes':30,'mealTimes':{'Lunch':'12:30','Snack':'15:30','Dinner':'19:30'},'fasting':False,'eatFrom':'12:00','eatUntil':'20:00'},'activities':[{'id':'jog','name':'Jogging','icon':'run','type':'cardio','metric':'distance','preference':'most','enabled':True,'partner':False,'available':True},{'id':'badminton','name':'Badminton','icon':'racket','type':'sport','metric':'duration','preference':'least','enabled':True,'partner':True,'available':False}],'meals':[],'sessions':[],'weights':[],'days':{},'plan':None,'savedPresets':[]}

def item():
    return {'id':'i1','food':'rice','name':'Wrong client label','amount':100,'unit':'g','kcal':1,'protein':0,'quality':'manual_estimate','low':0,'high':2,'emoji':'🍚'}

@pytest.fixture
def app(tmp_path):return create_app(tmp_path/'test.db')
@pytest.fixture
def client(app):
    with TestClient(app) as c:
        c.get('/api/session');yield c

def save(c,s=None,expected=0,mutation='initial'):
    return c.put('/api/state',json={'expected_revision':expected,'mutation_id':mutation,'state':s or state()})

def test_storage_persistence_and_isolation(app,client):
    assert save(client).status_code==200
    token=client.cookies.get('burnrate_session')
    other=TestClient(app);other.get('/api/session');assert other.get('/api/state').json()['state'] is None
    resumed=TestClient(app);resumed.cookies.set('burnrate_session',token)
    assert resumed.get('/api/state').json()['state']['settings']['name']=='Test'

def test_session_required_and_csrf(client,app):
    assert TestClient(app).get('/api/state').status_code==401
    assert save(client).status_code==200
    assert client.put('/api/state',headers={'Origin':'https://evil.example'},json={}).status_code==403
    assert client.get('/api/session',headers={'Sec-Fetch-Site':'cross-site'}).status_code==403

def test_conflict_and_idempotency(client):
    assert save(client).json()['revision']==1
    assert save(client).json()['revision']==1
    assert save(client,mutation='other').status_code==409
    assert save(client,expected=1,mutation='next').json()['revision']==2

def test_authoritative_calculation_and_missing_data(client):
    s=state();s['meals']=[{'id':'m1','date':TODAY,'slot':'Lunch','items':[item()]}]
    result=save(client,s).json();assert result['state']['meals'][0]['items'][0]['kcal']==130
    summary=client.get('/api/summary',params={'date':TODAY}).json()
    assert summary['kcal_used']==130 and not summary['complete'] and summary['food_quality']['missing_meal_slots']==2
    tomorrow=(local_today()+timedelta(days=1)).isoformat()
    assert client.get('/api/summary',params={'date':tomorrow}).json()['kcal_used'] is None

def test_invalid_logs_and_units(client):
    s=state();s['weights']=[{'date':TODAY,'kg':75},{'date':TODAY,'kg':76}];assert save(client,s).status_code==422
    s=state();s['sessions']=[{'id':'s1','date':TODAY,'activityId':'missing','name':'Unknown','duration':10,'effort':5,'status':'completed'}];assert save(client,s).status_code==422
    s=state();i=item();i['unit']='ml';s['meals']=[{'id':'m','date':TODAY,'slot':'Lunch','items':[i]}];assert save(client,s).status_code==422
    s=state();s['days'][(local_today()+timedelta(days=1)).isoformat()]={'energy':5};assert save(client,s).status_code==422

def test_template_plan_and_cache(client):
    save(client)
    req={'expected_revision':1,'date':TODAY,'use_ai':False}
    r=client.post('/api/plans',json=req);assert r.status_code==200
    p=r.json();assert p['source']=='rules' and p['kcal']>=1500 and p['activity']['id']=='jog'
    assert client.post('/api/plans',json=req).json()['input_hash']==p['input_hash']
    assert client.post('/api/plans',json={**req,'expected_revision':0}).status_code==409

def test_recovery_and_partner_constraints():
    for d in [{'energy':1},{'sleep':5},{'soreness':'pain'}]:
        s=state();s['days'][TODAY]=d;assert plan(s,TODAY)['activity'] is None
    s=state();s['activities'][0]['enabled']=False;assert plan(s,TODAY)['activity'] is None
    s['activities'][1]['available']=True;assert plan(s,TODAY)['activity']['id']=='badminton'
    with pytest.raises(ValueError):plan(state(),TODAY,{'activity_id':'badminton','portion_multiplier':1,'reason':'x'})
    s=state();s['settings']['calorieFloor']=5000;assert not plan(s,TODAY)['valid']

def test_ai_absent_fallback_and_no_secret(client,monkeypatch):
    monkeypatch.delenv('DEEPSEEK_API_KEY',raising=False);monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    save(client);r=client.post('/api/plans',json={'expected_revision':1,'date':TODAY,'use_ai':True})
    assert r.status_code==200 and r.json()['source']=='rules' and 'fallback_reason' in r.json()
    assert client.post('/api/food/analyze',json={'data_url':'data:image/jpeg;base64,x','draft_id':'draft'}).status_code==503
    assert client.post('/api/reviews',json={'expected_revision':1,'date':TODAY}).json()['proposed_end_date'] is None

def test_draft_confirmation_atomic_and_replay(client,app):
    save(client);uid=app.state.store.known_session(client.cookies.get('burnrate_session'))
    app.state.store.draft(uid,'d1',{'id':'d1','status':'draft','items':[]})
    assert client.get('/api/summary',params={'date':TODAY}).json()['kcal_used'] is None
    req={'expected_revision':1,'mutation_id':'confirm-1','date':TODAY,'slot':'Lunch','items':[item()]}
    r=client.post('/api/food/drafts/d1/confirm',json=req);assert r.status_code==200
    assert r.json()['revision']==2 and len(r.json()['state']['meals'])==1
    assert client.post('/api/food/drafts/d1/confirm',json=req).json()['revision']==2
    assert client.post('/api/food/drafts/d1/confirm',json={**req,'expected_revision':2,'mutation_id':'different'}).status_code==422
    other=TestClient(app);other.get('/api/session');assert other.get('/api/food/drafts/d1').status_code==404

def test_invalid_photo_when_configured(client,monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','test');monkeypatch.setenv('GEMINI_MODEL','test-model')
    r=client.post('/api/food/analyze',json={'data_url':'data:image/jpeg;base64,eA==','draft_id':'d'})
    assert r.status_code==422

def test_provider_repair_budget_and_validation(monkeypatch):
    import asyncio
    monkeypatch.setenv('DEEPSEEK_API_KEY','test');monkeypatch.setenv('DEEPSEEK_MODEL','test-model')
    calls=[]
    def handle(request):
        calls.append(request)
        choice={'activity_id':'badminton' if len(calls)==1 else 'jog','portion_multiplier':1,'reason':'Maintain a familiar session.'}
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(choice)}}]})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as transport:
            provider=Providers(transport)
            return await provider.generate('deepseek','Select JSON',PlanChoice,validate=lambda c:plan(state(),TODAY,c.model_dump()))
    assert asyncio.run(run()).activity_id=='jog';assert len(calls)==2

def test_photo_draft_cache_and_confirm_boundary(tmp_path,monkeypatch):
    import asyncio
    from app.storage import Store
    store=Store(tmp_path/'photo.db');uid=store.session('test')
    monkeypatch.setenv('GEMINI_MODEL','test-model')
    class Fake:
        calls=0
        async def generate(self,*args,**kwargs):
            self.calls+=1
            return Recognition.model_validate({'items':[{'id':'egg1','name':'egg','food_id':'egg','preparation':'boiled','portion':{'method':'units','amount_low':1,'amount_high':1,'unit':'unit'},'confidence':'high','hidden_ingredients':[]}],'missing':[]})
    image=io.BytesIO();Image.new('RGB',(20,20)).save(image,'JPEG');data='data:image/jpeg;base64,'+base64.b64encode(image.getvalue()).decode()
    provider=Fake()
    async def run():
        a=await analyze(store,provider,uid,PhotoRequest(data_url=data,draft_id='d1'))
        b=await analyze(store,provider,uid,PhotoRequest(data_url=data,draft_id='d2'))
        assert a['items'][0]['kcal']==75 and a['status']=='draft' and b['status']=='draft'
    asyncio.run(run());assert provider.calls==1;assert store.get(uid)['state'] is None

def test_stale_ai_response_not_published(tmp_path):
    class Racing:
        capabilities={'gemini':False,'deepseek':True}
        async def generate(self,*args,**kwargs):
            snap=app.state.store.get(uid)
            changed=deepcopy(snap['state']);changed['revision']+=1
            app.state.store.save(uid,snap['revision'],'during-ai',changed)
            return PlanChoice(activity_id='jog',portion_multiplier=1,reason='Familiar session')
    app=create_app(tmp_path/'race.db',Racing())
    client=TestClient(app);client.get('/api/session');save(client)
    uid=app.state.store.known_session(client.cookies.get('burnrate_session'))
    assert client.post('/api/plans',json={'expected_revision':1,'date':TODAY,'use_ai':True}).status_code==409
    with app.state.store.connect() as db:assert db.execute('SELECT COUNT(*) FROM plan_revision').fetchone()[0]==0

def test_unknown_protein_not_zero(client):
    s=state();i=item();i.update(food=None,kcal=200,low=150,high=250,protein=None)
    s['meals']=[{'id':'m1','date':TODAY,'slot':'Lunch','items':[i]}]
    assert save(client,s).status_code==200
    result=client.get('/api/summary',params={'date':TODAY}).json()
    assert result['protein_used_g'] is None and result['food_quality']['unknown_protein_items']==1

def test_permanent_billing_error_not_retried(monkeypatch):
    import asyncio
    monkeypatch.setenv('GEMINI_API_KEY','test');monkeypatch.setenv('GEMINI_MODEL','test-model')
    calls=[]
    def handle(request):calls.append(request);return httpx.Response(402,json={'error':{'message':'No credits'}})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            with pytest.raises(ProviderUnavailable,match='billing'):
                await Providers(client).generate('gemini','Return empty JSON',Recognition)
    asyncio.run(run());assert len(calls)==1

def test_gemini_json_mode_still_validates_and_repairs(monkeypatch):
    import asyncio
    monkeypatch.setenv('GEMINI_API_KEY','test');monkeypatch.setenv('GEMINI_MODEL','test-model')
    calls=[]
    def handle(request):
        calls.append(request)
        value={'items':[],'missing':[]}
        if len(calls)==1:value['unexpected']='reject this field'
        return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':json.dumps(value)}]}}]})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            result=await Providers(client).generate('gemini','Return valid recognition JSON',Recognition)
            assert result.items==[]
    asyncio.run(run());assert len(calls)==2
