import hashlib
import json
import os
import secrets
import time
from collections import defaultdict,deque
from datetime import date,timedelta
from pathlib import Path
from urllib.parse import urlsplit
from dotenv import load_dotenv
from fastapi import FastAPI,Depends,HTTPException,Request,Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from .models import StateWrite,PlanRequest,PhotoRequest,ConfirmDraft,ReviewRequest,Meal,Journal,local_today
from .catalog import CATALOG,normalize_state,summary
from .planner import plan,daily_brief
from .providers import Providers,PlanChoice,Review,ProviderUnavailable
from .food import analyze
from .storage import Store,Conflict

COOKIE='burnrate_session'
ROOT=Path(__file__).resolve().parents[2]
load_dotenv(ROOT/'backend'/'.env',override=False)

def create_app(db_path=None,providers=None):
    app=FastAPI(title='BurnRate API',version='1.0.0',docs_url='/api/docs',openapi_url='/api/openapi.json')
    store=Store(db_path or os.getenv('BURNRATE_DB',str(ROOT/'backend'/'burnrate.db')))
    providers=providers or Providers()
    app.state.store=store;app.state.providers=providers
    usage=defaultdict(deque)

    @app.middleware('http')
    async def protect(request,call_next):
        if request.url.path.startswith('/api/'):
            origin=request.headers.get('origin')
            allowed=os.getenv('BURNRATE_ORIGIN')
            actual=f'{request.url.scheme}://{request.url.netloc}'
            if origin and origin!=(allowed or actual):return JSONResponse({'detail':'Cross-origin request rejected'},403)
            if request.headers.get('sec-fetch-site')=='cross-site':return JSONResponse({'detail':'Cross-site request rejected'},403)
            length=request.headers.get('content-length')
            if length and (not length.isdigit() or int(length)>13_000_000):return JSONResponse({'detail':'Request too large'},413)
            # Bound chunked bodies too, rather than relying on Content-Length.
            if request.method in ('POST','PUT','PATCH'):
                collected=bytearray()
                async for chunk in request.stream():
                    collected.extend(chunk)
                    if len(collected)>13_000_000:return JSONResponse({'detail':'Request too large'},413)
                request._body=bytes(collected)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        if request.url.path.startswith('/api/'):response.headers['Cache-Control']='no-store'
        return response

    def user(request:Request):
        token=request.cookies.get(COOKIE,'')
        key=store.known_session(token) if len(token)==64 else None
        if not key:raise HTTPException(401,'Initialize a browser session with GET /api/session')
        return key
    def snapshot(uid,revision=None):
        result=store.get(uid)
        if result['state'] is None:raise HTTPException(404,'No server journal yet')
        if revision is not None and result['revision']!=revision:raise HTTPException(409,'Journal changed; reload before retrying')
        return result
    def limit(uid):
        now=time.monotonic();q=usage[uid]
        while q and q[0]<now-3600:q.popleft()
        if len(q)>=20:raise HTTPException(429,'AI request limit reached; manual logging remains available')
        q.append(now)
    @app.exception_handler(Conflict)
    async def conflict(request,exc):return JSONResponse({'detail':'Journal changed; reload before retrying'},409)
    @app.get('/config.js')
    def config():return Response('window.BURNRATE_API = true;',media_type='application/javascript',headers={'Cache-Control':'no-store'})
    @app.get('/api/health')
    def health():return {'service':'burnrate-python','version':1,'timezone':'Asia/Kuala_Lumpur'}
    @app.get('/api/session')
    def session(request:Request,response:Response):
        token=request.cookies.get(COOKIE,'')
        uid=store.known_session(token) if len(token)==64 else None
        if not uid:
            token=secrets.token_hex(32);uid=store.session(token)
            response.set_cookie(COOKIE,token,httponly=True,secure=os.getenv('BURNRATE_SECURE_COOKIE','false').lower()=='true',samesite='strict',max_age=60*60*24*365,path='/')
        return {**store.get(uid),'capabilities':providers.capabilities}
    @app.get('/api/state')
    def get_state(uid=Depends(user)):return store.get(uid)
    @app.put('/api/state')
    def put_state(body:StateWrite,uid=Depends(user)):
        try:data=normalize_state(body.state)
        except ValueError as exc:raise HTTPException(422,str(exc))
        return store.save(uid,body.expected_revision,body.mutation_id,data)
    @app.get('/api/catalog')
    def catalog():return {'version':1,'source':'illustrative_averages','foods':CATALOG}
    @app.get('/api/summary')
    def get_summary(date:date,uid=Depends(user)):return summary(snapshot(uid)['state'],date.isoformat())
    @app.post('/api/plans')
    async def generate_plan(body:PlanRequest,uid=Depends(user)):
        if body.date>local_today():raise HTTPException(422,'Brief date cannot be future dated')
        snap=snapshot(uid,body.expected_revision);data=snap['state'];day=body.date.isoformat()
        key=hashlib.sha256(json.dumps({'state':data,'date':day,'server_revision':snap['revision'],'schema':1,'ai':body.use_ai,'model':os.getenv('DEEPSEEK_MODEL')},sort_keys=True).encode()).hexdigest()
        cached=store.get_plan(uid,key)
        if cached:return cached
        result=plan(data,day)
        if body.use_ai and result['valid']:
            try:
                limit(uid)
                brief=daily_brief(data,day)
                def validate(choice):plan(data,day,choice.model_dump())
                choice=await providers.generate('deepseek','Choose one eligible activity ID or null and a portion multiplier within the allowed bounds (1 to 2), reaching the configured intake floor. Never change the goal or limits. Explain briefly; do not invent nutrition totals. JSON brief: '+json.dumps(brief),PlanChoice,validate=validate)
                result=plan(data,day,choice.model_dump())
            except ProviderUnavailable:
                result['fallback_reason']='AI unavailable; validated template plan used'
        result.update(revision=data['revision'],server_revision=snap['revision'],input_hash=key)
        store.commit_plan(uid,body.expected_revision,key,result)
        return result
    @app.post('/api/food/analyze')
    async def photo(body:PhotoRequest,uid=Depends(user)):
        if not providers.capabilities['gemini']:raise HTTPException(503,'Gemini is not configured; use manual entry')
        limit(uid)
        try:return await analyze(store,providers,uid,body)
        except ValueError as exc:raise HTTPException(422,str(exc))
        except ProviderUnavailable as exc:raise HTTPException(503,str(exc)+'; manual entry is still available')
    @app.get('/api/food/drafts/{draft_id}')
    def draft(draft_id:str,uid=Depends(user)):
        value=store.get_draft(uid,draft_id)
        if not value:raise HTTPException(404,'Draft not found')
        return value
    @app.post('/api/food/drafts/{draft_id}/confirm')
    def confirm(draft_id:str,body:ConfirmDraft,uid=Depends(user)):
        if body.date>local_today():raise HTTPException(422,'Meal cannot be future dated')
        snap=snapshot(uid)
        try:
            meal=Meal(id='photo-'+draft_id,date=body.date,slot=body.slot,items=body.items)
            candidate={**snap['state'],'meals':[*[m for m in snap['state']['meals'] if m['id']!=meal.id],meal.model_dump(mode='json')]}
            validated=normalize_state(Journal.model_validate(candidate))
            normalized=validated['meals'][-1]
            # Duplicate confirmed drafts are replayed in Store; do not append twice.
            return store.confirm_draft(uid,draft_id,body.expected_revision,body.mutation_id,normalized)
        except KeyError:raise HTTPException(404,'Draft not found')
        except ValueError:raise HTTPException(422,'Invalid meal or draft already confirmed')
    @app.post('/api/reviews')
    async def weekly(body:ReviewRequest,uid=Depends(user)):
        snap=snapshot(uid,body.expected_revision);data=snap['state'];end=body.date
        if end>local_today():raise HTTPException(422,'Review date cannot be future dated')
        summaries=[daily_brief(data,(end-timedelta(days=i)).isoformat()) for i in reversed(range(7))]
        weight_count=sum(x['weight']['count']>0 for x in summaries)
        sessions=sum((end-timedelta(days=6)).isoformat()<=s['date']<=end.isoformat() for s in data['sessions'])
        result={'source':'rules','findings':[f'{sessions} activity sessions in the review period.'],'suggestions':['Keep portions and recovery visible. Missing logs do not prove a cause of weight changes.'],'proposed_end_date':None,'reason':'Review your observed patterns; your goal date remains unchanged.'}
        if body.use_ai:
            try:
                limit(uid)
                review=await providers.generate('deepseek','Review these calculated daily summaries. Explain hypotheses, not medical conclusions. Do not cut intake or change limits. A proposed_end_date is a proposal only, or null. Return JSON. '+json.dumps(summaries),Review)
                if review.proposed_end_date:
                    proposed=date.fromisoformat(review.proposed_end_date)
                    if proposed<=local_today():raise ValueError('Proposal must be future dated')
                result={**review.model_dump(),'source':'ai'}
            except (ProviderUnavailable,ValueError):result['fallback_reason']='AI unavailable; local summary used'
        snapshot(uid,body.expected_revision)
        store.cache(uid,'review',f'{body.expected_revision}:{end}:{body.use_ai}',result)
        return result
    app.mount('/',StaticFiles(directory=ROOT/'dashboard'/'dist',html=True),name='dashboard')
    return app

app=create_app()
