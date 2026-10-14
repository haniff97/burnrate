import math
from datetime import date, timedelta
from .catalog import FOODS, CATALOG, summary

# Product serving bounds, not individualized medical nutrition targets.
PORTION_BOUNDS={'rice':(50,600),'chicken':(30,400),'greens':(30,600),'egg':(1,4),'apple':(1,3)}

def composed_meals(data,choice):
    meals=choice['meals']
    if len(meals)!=3 or {m['slot'] for m in meals}!={'Lunch','Snack','Dinner'}:raise ValueError('Provide exactly one meal for every slot')
    result=[]
    for slot in ['Lunch','Snack','Dinner']:
        meal=next(m for m in meals if m['slot']==slot)
        if len({i['food_id'] for i in meal['items']})!=len(meal['items']):raise ValueError('Duplicate food in meal')
        kcal=protein=0;details=[];items=[]
        for item in meal['items']:
            food=FOODS.get(item['food_id']);amount=item['amount']
            if not food:raise ValueError('Meal must use known catalog foods')
            low,high=PORTION_BOUNDS[food['id']]
            if not low<=amount<=high:raise ValueError('Serving outside catalog portion bounds')
            if food['unit']=='unit' and amount!=int(amount):raise ValueError('Unit foods require whole units')
            kcal+=food['kcal']*amount/food['basis'];protein+=food['protein']*amount/food['basis']
            details.append(f"{amount:g} {food['unit']} {food['name'].lower()}")
            items.append({'food_id':food['id'],'amount':amount,'unit':food['unit']})
        result.append({'slot':slot,'time':data['settings']['mealTimes'][slot],'name':meal['name'],'detail':' · '.join(details),'kcal':math.floor(kcal+.5),'protein':math.floor(protein+.5),'items':items})
    if sum(m['kcal'] for m in result)<data['settings']['calorieFloor']:raise ValueError('Composed meals do not meet the intake floor')
    return result

TEMPLATES=[
    dict(id='lunch',slot='Lunch',name='Chicken & rice bowl',items=[('rice',250),('chicken',150),('greens',150),('egg',1)],detail='250 g cooked rice · 150 g cooked chicken · 150 g greens · 1 egg'),
    dict(id='snack',slot='Snack',name='Eggs & apple',items=[('egg',2),('apple',1)],detail='2 medium eggs · 1 medium apple'),
    dict(id='dinner',slot='Dinner',name='Chicken, rice & greens',items=[('rice',250),('chicken',150),('greens',150)],detail='250 g cooked rice · 150 g cooked chicken · 150 g greens'),
]
def nutrition(template):
    return tuple(sum(FOODS[f][key]*n/FOODS[f]['basis'] for f,n in template['items']) for key in ['kcal','protein'])

def options(data,day):
    s=data['settings'];d=data['days'].get(day,{})
    info=summary(data,day)
    recovery=(d.get('energy') is not None and d['energy']<=2) or (d.get('sleep') is not None and d['sleep']<6) or d.get('soreness')=='pain' or any(x['date']==day and x['effort']>=7 for x in data['sessions']) or (info['complete'] and info['kcal_used'] is not None and info['kcal_used']<s['calorieFloor'])
    eligible=[]
    if not recovery and s['availableMinutes']>0:
        for a in sorted(data['activities'],key=lambda a:{'most':0,'mid':1,'least':2}[a['preference']]):
            if not a['enabled'] or not a['available']:continue
            if d.get('soreness')=='legs' and a['type']!='strength':continue
            if d.get('soreness')=='upper body' and a['type']=='strength':continue
            recent=sorted([x for x in data['sessions'] if x['activityId']==a['id'] and x['date']<=day and x.get('duration')],key=lambda x:x['date'])
            prev=recent[-1] if recent else None
            duration=min(s['availableMinutes'],prev['duration'] if prev else 20)
            distance=round(prev['distance']*min(1,duration/prev['duration']),1) if prev and prev.get('distance') and a['metric']=='distance' else None
            eligible.append(dict(id=a['id'],name=a['name'],icon=a['icon'],duration=duration,detail=f"{duration:g} min · "+(f'{distance:g} km · ' if distance else '')+('repeat a familiar session' if prev else 'comfortable, self-selected pace')+(' · partner confirmed' if a['partner'] else '')))
    return eligible,recovery,info

def plan(data,day,choice=None):
    s=data['settings'];activity_options,recovery,info=options(data,day)
    result=dict(date=(date.fromisoformat(day)+timedelta(days=1)).isoformat(),source='rules',valid=True,rest=False,kcal=0,meals=[],activity=None)
    minimum=max(1,math.ceil(s['calorieFloor']/sum(nutrition(t)[0] for t in TEMPLATES)*20)/20)
    dynamic=choice is not None and choice.get('meals') is not None
    if minimum>2 and not dynamic:return dict(result,valid=False,error='Available meal templates cannot meet the configured intake floor within their portion bounds.')
    multiplier=choice.get('portion_multiplier',1) if choice else minimum
    if not dynamic and (multiplier<minimum or multiplier>2):raise ValueError('Portion multiplier outside eligible bounds')
    for t in ([] if dynamic else TEMPLATES):
        k,p=nutrition(t)
        result['meals'].append(dict(slot=t['slot'],time=s['mealTimes'][t['slot']],name=t['name'],detail=(f'{multiplier:.2f} × usual serving · ' if multiplier!=1 else '')+t['detail'],kcal=math.floor(k*multiplier+.5),protein=math.floor(p*multiplier+.5)))
    if dynamic:result['meals']=composed_meals(data,choice)
    result['kcal']=sum(m['kcal'] for m in result['meals'])
    if result['kcal']<s['calorieFloor']:raise ValueError('Intake floor not reached')
    if choice:
        requested=choice['activity_id'];result['activity']=next((a for a in activity_options if a['id']==requested),None)
        if requested is not None and result['activity'] is None:raise ValueError('Activity not eligible')
        minutes=choice.get('activity_minutes')
        if minutes is not None:
            if result['activity'] is None or minutes>result['activity']['duration']:raise ValueError('Activity duration exceeds familiar load or availability')
            activity={**result['activity'],'duration':minutes}
            # The old distance belongs to the old duration; do not invent a new distance.
            activity['detail']=f'{minutes:g} min · comfortable, self-selected pace'
            result['activity']=activity
    elif activity_options:result['activity']=activity_options[0]
    result['rest']=result['activity'] is None
    result['reason']=('Your recovery calls for a lighter day. Keep meals regular and leave training out of tomorrow’s plan.' if recovery else 'No activities are available with your current settings. Tomorrow leaves room for rest.' if not activity_options else 'Some meal slots are unlogged. Keep a familiar session; missing logs do not trigger a harder plan.' if not info['complete'] else 'Your available time and preferences guide a familiar session without increasing the load.')
    if choice:result.update(source='ai',reason=choice['reason'],meal_source='ai_composed' if dynamic else 'templates')
    result['protein']=sum(m['protein'] for m in result['meals'])
    result['protein_reference_met']=result['protein']>=s['proteinTarget']
    return result

def daily_brief(data,day):
    s=data['settings']
    eligible,recovery,info=options(data,day)
    observed=[w for w in data['weights'] if (date.fromisoformat(day)-timedelta(days=6)).isoformat()<=w['date']<=day]
    start=(date.fromisoformat(day)-timedelta(days=13)).isoformat()
    prior=[w for w in data['weights'] if start<=w['date']<(date.fromisoformat(day)-timedelta(days=6)).isoformat()]
    last=sorted([w for w in data['weights'] if w['date']<=day],key=lambda w:w['date'])
    current_avg=sum(w['kg'] for w in observed)/len(observed) if observed else None
    prior_avg=sum(w['kg'] for w in prior)/len(prior) if prior else None
    movement=[x for x in data['sessions'] if start<=x['date']<=day]
    return dict(date=day,food=info,recovery=data['days'].get(day,{}),recovery_required=recovery,
        weight=dict(count=len(observed),avg_kg=sum(w['kg'] for w in observed)/len(observed) if observed else None),
        goal=data['settings'],goal_context={'latest_weight_kg':last[-1]['kg'] if last else None,'days_until_goal':(date.fromisoformat(s['endDate'])-date.fromisoformat(day)).days},
        weight_trend={'current_week_count':len(observed),'previous_week_count':len(prior),'current_week_avg_kg':current_avg,'previous_week_avg_kg':prior_avg,'change_kg':round(current_avg-prior_avg,3) if len(observed)>=3 and len(prior)>=3 else None,'sufficient_coverage':len(observed)>=3 and len(prior)>=3},
        recent_days=[{'date':(date.fromisoformat(day)-timedelta(days=i)).isoformat(),'food':summary(data,(date.fromisoformat(day)-timedelta(days=i)).isoformat()),'recovery':data['days'].get((date.fromisoformat(day)-timedelta(days=i)).isoformat(),{})} for i in range(7)],
        recent_activity=movement,confirmed_meal_examples=[{'slot':m['slot'],'foods':[i['name'] for i in m['items']]} for m in data['meals'] if start<=m['date']<=day][-12:],
        catalog=[{**f,'amount_min':PORTION_BOUNDS[f['id']][0],'amount_max':PORTION_BOUNDS[f['id']][1]} for f in CATALOG],
        portion_multiplier_bounds=[max(1,math.ceil(s['calorieFloor']/sum(nutrition(t)[0] for t in TEMPLATES)*20)/20),2],meal_templates=[dict(id=t['id'],slot=t['slot'],kcal=nutrition(t)[0],protein=nutrition(t)[1]) for t in TEMPLATES],activity_options=eligible)
