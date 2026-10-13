"""Illustrative averages; replace with verified nutrition-source records before launch."""
CATALOG = [
    dict(id='rice',name='Cooked rice',unit='g',basis=100,kcal=130,protein=2.7,emoji='🍚'),
    dict(id='chicken',name='Chicken breast · cooked',unit='g',basis=100,kcal=165,protein=31,emoji='🍗'),
    dict(id='egg',name='Boiled egg · medium',unit='unit',basis=1,kcal=75,protein=6.5,emoji='🥚'),
    dict(id='greens',name='Leafy greens · cooked',unit='g',basis=100,kcal=25,protein=2,emoji='🥬'),
    dict(id='apple',name='Apple · medium',unit='unit',basis=1,kcal=95,protein=.5,emoji='🍎'),
]
FOODS = {f['id']:f for f in CATALOG}

def normalize_state(journal):
    data=journal.model_dump(mode='json')
    data['plan']=None
    for meal in [*data['meals'],*data['savedPresets']]:
        for item in meal['items']:
            if item['food'] is not None:
                c=FOODS.get(item['food'])
                if not c or item['unit'] != c['unit']: raise ValueError('Unknown food or incompatible serving unit')
                k=c['kcal']*item['amount']/c['basis']
                item.update(name=c['name'],kcal=k,protein=round(c['protein']*item['amount']/c['basis'],1),low=round(k*.9,2),high=round(k*1.1,2),nutrition_source='catalog_average')
            elif item['nutrition_source']=='catalog_average':
                item['nutrition_source']='user'
    return data

def summary(data,date):
    rows=[m for m in data['meals'] if m['date']==date]
    items=[i for m in rows for i in m['items']]
    missing=[slot for slot in data['settings']['mealTimes'] if not any(m['slot']==slot for m in rows)]
    return dict(date=date,kcal_used=sum(i['kcal'] for i in items) if items else None,
        kcal_low=sum(i['low'] for i in items) if items else None,kcal_high=sum(i['high'] for i in items) if items else None,
        protein_used_g=sum(i['protein'] for i in items if i['protein'] is not None) if any(i['protein'] is not None for i in items) else None,
        food_quality=dict(estimated_items=len(items),missing_meal_slots=len(missing),unknown_protein_items=sum(i['protein'] is None for i in items)),
        complete=not missing,missing_slots=missing)
