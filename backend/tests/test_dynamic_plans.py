from copy import deepcopy
from datetime import date,timedelta
import json
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.planner import plan,daily_brief
from app.providers import PlanChoice
from app.providers import Providers
import asyncio
import httpx
from test_api import state,TODAY

def choice():
    return {'activity_id':'jog','activity_minutes':15,'reason':'A shorter familiar session fits your recovery and available time.',
        'meals':[
            {'slot':'Lunch','name':'Rice, greens and eggs','items':[{'food_id':'rice','amount':300},{'food_id':'egg','amount':3},{'food_id':'greens','amount':100}]},
            {'slot':'Snack','name':'Apple and boiled eggs','items':[{'food_id':'apple','amount':2},{'food_id':'egg','amount':2}]},
            {'slot':'Dinner','name':'Chicken with rice and greens','items':[{'food_id':'chicken','amount':200},{'food_id':'rice','amount':200},{'food_id':'greens','amount':150}]},
        ]}

def test_composed_meals_recalculated_and_shorter_activity():
    result=plan(state(),TODAY,PlanChoice.model_validate(choice()).model_dump())
    assert result['meal_source']=='ai_composed'
    assert result['meals'][0]['name']=='Rice, greens and eggs'
    assert result['meals'][0]['kcal']==640
    assert result['kcal']>=1500
    assert result['protein']==sum(m['protein'] for m in result['meals'])
    assert result['activity']['duration']==15

@pytest.mark.parametrize('kind',['unknown','oversized','fractional_unit','missing_slot','duplicate_food','low_intake','harder_activity','ineligible_activity'])
def test_invalid_dynamic_plan_rejected(kind):
    c=choice()
    if kind=='unknown':c['meals'][0]['items'][0]['food_id']='invented'
    if kind=='oversized':c['meals'][0]['items'][0]['amount']=1000
    if kind=='fractional_unit':c['meals'][0]['items'][1]['amount']=1.5
    if kind=='missing_slot':c['meals'][1]['slot']='Lunch'
    if kind=='duplicate_food':c['meals'][0]['items'].append(c['meals'][0]['items'][0])
    if kind=='low_intake':
        for meal in c['meals']:meal['items']=[{'food_id':'apple','amount':1}]
    if kind=='harder_activity':c['activity_minutes']=45
    if kind=='ineligible_activity':c['activity_id']='badminton'
    with pytest.raises(ValueError):plan(state(),TODAY,c)

def test_weight_trend_missing_data_and_future_exclusion():
    data=state();brief=daily_brief(data,TODAY)
    assert brief['weight_trend']['change_kg'] is None
    assert not brief['weight_trend']['sufficient_coverage']
    today=date.fromisoformat(TODAY)
    data['weights']=[{'date':(today-timedelta(days=i)).isoformat(),'kg':75 if i<7 else 76} for i in range(14)]
    data['weights'].append({'date':(today+timedelta(days=1)).isoformat(),'kg':50})
    brief=daily_brief(data,TODAY)
    assert brief['weight_trend']['change_kg']==-1
    assert brief['goal_context']['latest_weight_kg']==75
    assert len(brief['recent_days'])==7
    assert len(brief['catalog'])==5

def test_api_provides_context_and_caches_validated_dynamic_plan(tmp_path):
    class Fake:
        capabilities={'deepseek':True,'gemini':False}
        calls=0
        async def generate(self,provider,prompt,schema,**kwargs):
            self.calls+=1
            assert 'weight_trend' in prompt and 'recent_activity' in prompt
            result=PlanChoice.model_validate(choice());kwargs['validate'](result);return result
    fake=Fake()
    with TestClient(create_app(tmp_path/'journal.db',fake)) as client:
        client.get('/api/session')
        client.put('/api/state',json={'expected_revision':0,'mutation_id':'initial','state':state()})
        request={'expected_revision':1,'date':TODAY,'use_ai':True}
        first=client.post('/api/plans',json=request)
        assert first.status_code==200
        assert first.json()['meal_source']=='ai_composed'
        assert client.post('/api/plans',json=request).json()==first.json()
        assert fake.calls==1

def test_repair_feedback_identifies_field_without_echoing_output(monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY','test-key')
    monkeypatch.setenv('DEEPSEEK_MODEL','test-model')
    calls=[]
    def transport(request):
        calls.append(json.loads(request.content))
        result=choice()
        if len(calls)==1:result['reason']='PRIVATE_TEST_TEXT'+'x'*700
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(result)}}]})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            return await Providers(client).generate('deepseek','Create a plan.',PlanChoice)
    result=asyncio.run(run())
    assert result.meals
    repair=calls[1]['messages'][1]['content']
    assert 'string_too_long' in repair and 'reason' in repair
    assert 'PRIVATE_TEST_TEXT' not in repair
    assert len(calls)==2
