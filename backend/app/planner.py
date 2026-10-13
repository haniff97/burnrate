import math
from datetime import date, timedelta
from .catalog import FOODS, summary

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
            recent=sorted([x for x in data['sessions'] if x['activityId']==a['id'] and x['date']<=day],key=lambda x:x['date'])
            prev=recent[-1] if recent else None
            duration=min(s['availableMinutes'],prev['duration'] if prev else 20)
            distance=round(prev['distance']*min(1,duration/prev['duration']),1) if prev and prev.get('distance') and a['metric']=='distance' else None
            eligible.append(dict(id=a['id'],name=a['name'],icon=a['icon'],duration=duration,detail=f"{duration:g} min · "+(f'{distance:g} km · ' if distance else '')+('repeat a familiar session' if prev else 'comfortable, self-selected pace')+(' · partner confirmed' if a['partner'] else '')))
    return eligible,recovery,info

def plan(data,day,choice=None):
    s=data['settings'];activity_options,recovery,info=options(data,day)
    result=dict(date=(date.fromisoformat(day)+timedelta(days=1)).isoformat(),source='rules',valid=True,rest=False,kcal=0,meals=[],activity=None)
    minimum=max(1,math.ceil(s['calorieFloor']/sum(nutrition(t)[0] for t in TEMPLATES)*20)/20)
    if minimum>2:return dict(result,valid=False,error='Available meal templates cannot meet the configured intake floor within their portion bounds.')
    multiplier=choice['portion_multiplier'] if choice else minimum
    if multiplier<minimum or multiplier>2:raise ValueError('Portion multiplier outside eligible bounds')
    for t in TEMPLATES:
        k,p=nutrition(t)
        result['meals'].append(dict(slot=t['slot'],time=s['mealTimes'][t['slot']],name=t['name'],detail=(f'{multiplier:.2f} × usual serving · ' if multiplier!=1 else '')+t['detail'],kcal=math.floor(k*multiplier+.5),protein=math.floor(p*multiplier+.5)))
    result['kcal']=sum(m['kcal'] for m in result['meals'])
    if result['kcal']<s['calorieFloor']:raise ValueError('Intake floor not reached')
    if choice:
        requested=choice['activity_id'];result['activity']=next((a for a in activity_options if a['id']==requested),None)
        if requested is not None and result['activity'] is None:raise ValueError('Activity not eligible')
    elif activity_options:result['activity']=activity_options[0]
    result['rest']=result['activity'] is None
    result['reason']=('Your recovery calls for a lighter day. Keep meals regular and leave training out of tomorrow’s plan.' if recovery else 'No activities are available with your current settings. Tomorrow leaves room for rest.' if not activity_options else 'Some meal slots are unlogged. Keep a familiar session; missing logs do not trigger a harder plan.' if not info['complete'] else 'Your available time and preferences guide a familiar session without increasing the load.')
    if choice:result.update(source='ai',reason=choice['reason'])
    return result

def daily_brief(data,day):
    eligible,recovery,info=options(data,day)
    observed=[w for w in data['weights'] if (date.fromisoformat(day)-timedelta(days=6)).isoformat()<=w['date']<=day]
    return dict(date=day,food=info,recovery=data['days'].get(day,{}),recovery_required=recovery,
        weight=dict(count=len(observed),avg_kg=sum(w['kg'] for w in observed)/len(observed) if observed else None),
        goal=data['settings'],portion_multiplier_bounds=[max(1,math.ceil(data['settings']['calorieFloor']/sum(nutrition(t)[0] for t in TEMPLATES)*20)/20),2],meal_templates=[dict(id=t['id'],slot=t['slot'],kcal=nutrition(t)[0],protein=nutrition(t)[1]) for t in TEMPLATES],activity_options=eligible)
