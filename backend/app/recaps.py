from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from .catalog import summary
from .planner import plan

ZONE = ZoneInfo('Asia/Kuala_Lumpur')

def now_local():
    return datetime.now(ZONE)

def seconds_until_midnight(now):
    local = now.astimezone(ZONE)
    boundary = datetime.combine(local.date()+timedelta(days=1),time.min,tzinfo=ZONE)
    return (boundary-local).total_seconds()

def build_recap(data,day,revision,generated_at,delayed=False):
    # Exclude newer actual logs when a delayed recap is built after downtime.
    data={**data,'meals':[m for m in data['meals'] if m['date']<=day],
          'sessions':[s for s in data['sessions'] if s['date']<=day],
          'weights':[w for w in data['weights'] if w['date']<=day]}
    food=summary(data,day);recovery=data['days'].get(day,{})
    sessions=[s for s in data['sessions'] if s['date']==day]
    weights=sorted(data['weights'],key=lambda w:w['date'])
    latest=weights[-1] if weights else None
    settings=data['settings'];next_plan=plan(data,day)
    focus=[f"Keep water visible: your configured reference is {settings['waterTarget']:g} L.",
           f"Keep meals regular, respecting your {settings['calorieFloor']:g} kcal intake floor and {settings['proteinTarget']:g} g protein reference."]
    if food['missing_slots']:focus.insert(0,'Log all meal slots and review portions; incomplete intake cannot establish a calorie deficit.')
    if not recovery.get('sleep'):focus.append('Log sleep and energy so the next plan has recovery context.')
    focus.append(next_plan.get('reason',next_plan.get('error','Review your plan settings.')))
    return {'day':day,'generated_at':generated_at,'delayed':delayed,'revision':revision,'source':'rules',
            'food':food,'water_l':recovery.get('water'),'sleep_hours':recovery.get('sleep'),'energy':recovery.get('energy'),
            'movement_minutes':sum(s['duration'] for s in sessions),'steps':sum(s.get('steps') or 0 for s in sessions) if any(s.get('steps') is not None for s in sessions) else None,
            'activities':[{'name':s['name'],'duration':s['duration'],'status':s['status']} for s in sessions],
            'goal':{'target_kg':settings['targetWeight'],'date':settings['endDate'],'latest_kg':latest['kg'] if latest else None,'latest_weight_date':latest['date'] if latest else None},
            'next_plan':next_plan,'focus':focus}
