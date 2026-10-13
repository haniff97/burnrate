export const catalog=[{id:'rice',name:'Cooked rice',unit:'g',basis:100,kcal:130,protein:2.7,amount:180,emoji:'🍚'},{id:'chicken',name:'Chicken breast · cooked',unit:'g',basis:100,kcal:165,protein:31,amount:150,emoji:'🍗'},{id:'egg',name:'Boiled egg · medium',unit:'unit',basis:1,kcal:75,protein:6.5,amount:2,emoji:'🥚'},{id:'greens',name:'Leafy greens · cooked',unit:'g',basis:100,kcal:25,protein:2,amount:150,emoji:'🥬'},{id:'apple',name:'Apple · medium',unit:'unit',basis:1,kcal:95,protein:.5,amount:1,emoji:'🍎'}];
export function summarizeMeals(meals) {
  return meals.flatMap(m => m.items).reduce((t,i)=>({
    kcal:t.kcal+i.kcal, low:t.low+i.low, high:t.high+i.high,
    protein:t.protein+(i.protein??0), unknownProtein:t.unknownProtein+(i.protein===null?1:0),
    estimated:t.estimated+1
  }),{kcal:0,low:0,high:0,protein:0,estimated:0,unknownProtein:0});
}
export function weightTrend(weights,date) {
  const from=new Date(date+'T00:00:00Z').getTime()-6*86400000;
  const rows=weights.filter(w=>new Date(w.date+'T00:00:00Z').getTime()>=from&&w.date<=date);
  return {count:rows.length,avg:rows.length?rows.reduce((n,w)=>n+w.kg,0)/rows.length:null};
}
export function buildPlan(state,date) {
  const s=state.settings,d=state.days[date]||{},sessions=state.sessions.filter(x=>x.date===date);
  const tomorrow=new Date(date+'T12:00:00Z');tomorrow.setUTCDate(tomorrow.getUTCDate()+1);
  const planDate=tomorrow.toISOString().slice(0,10);
  const base={date:planDate,source:'rules',valid:true,rest:false,kcal:0,meals:[],activity:null};
  if(s.fasting&&(s.eatFrom>=s.eatUntil||Object.values(s.mealTimes).some(t=>t<s.eatFrom||t>s.eatUntil)))return {...base,valid:false,error:'Meal times conflict with your eating window. Review your preferences.'};
  // These catalog values are illustrative averages; the UI labels all planned food as estimated.
  const mealTemplate=(slot,name,detail,items)=>({slot,name,detail,...items.reduce((t,[food,amount])=>{const c=catalog.find(f=>f.id===food);return {kcal:t.kcal+c.kcal*amount/c.basis,protein:t.protein+c.protein*amount/c.basis}}, {kcal:0,protein:0})});
  const templates=[
    mealTemplate('Lunch','Chicken & rice bowl','250 g cooked rice · 150 g cooked chicken · 150 g greens · 1 egg',[['rice',250],['chicken',150],['greens',150],['egg',1]]),
    mealTemplate('Snack','Eggs & apple','2 medium eggs · 1 medium apple',[['egg',2],['apple',1]]),
    mealTemplate('Dinner','Chicken, rice & greens','250 g cooked rice · 150 g cooked chicken · 150 g greens',[['rice',250],['chicken',150],['greens',150]])
  ];
  const total=templates.reduce((n,m)=>n+m.kcal,0);
  const multiplier=Math.max(1,Math.ceil(s.calorieFloor/total*20)/20);
  if(multiplier>2)return {...base,valid:false,error:'The current meal templates cannot meet your intake floor within their portion bounds. Add broader templates in the next backend phase or review your configured floor.'};
  base.meals=templates.map(m=>({...m,time:s.mealTimes[m.slot],kcal:Math.round(m.kcal*multiplier),protein:Math.round(m.protein*multiplier),detail:multiplier===1?m.detail:`${multiplier.toFixed(2)} × usual serving · ${m.detail}`}));
  base.kcal=base.meals.reduce((n,m)=>n+m.kcal,0);
  if(base.kcal<s.calorieFloor)return {...base,valid:false,error:'The proposed meals do not meet the configured intake floor.'};
  const lowEnergy=d.energy!==null&&d.energy!==undefined&&d.energy<=2;
  const poorSleep=d.sleep!==null&&d.sleep!==undefined&&d.sleep<6;
  const hardDay=sessions.some(x=>x.effort>=7);
  const pain=d.soreness==='pain';
  const completeFood=['Lunch','Snack','Dinner'].every(slot=>state.meals.some(m=>m.date===date&&m.slot===slot));
  const intake=state.meals.filter(m=>m.date===date).flatMap(m=>m.items).reduce((n,i)=>n+i.kcal,0);
  const lowIntake=completeFood&&intake<s.calorieFloor;
  const recovery=lowEnergy||poorSleep||hardDay||pain||lowIntake;
  const options=state.activities.filter(a=>a.enabled&&a.available&&!(d.soreness==='legs'&&a.type!=='strength')&&!(d.soreness==='upper body'&&a.type==='strength'));
  options.sort((a,b)=>({most:0,mid:1,least:2}[a.preference]-{most:0,mid:1,least:2}[b.preference]));
  if(recovery||s.availableMinutes===0||!options.length){base.rest=true;base.reason=pain?'Exercise discomfort is logged. No training is scheduled; review your recovery before choosing a session.':recovery?'Your recent recovery or completed session calls for a lighter day. Keep meals regular and leave training out of tomorrow’s plan.':!options.length?'No activities are available with your current equipment, partner and recovery settings. Tomorrow leaves room for rest.':'You selected a rest day. Tomorrow keeps meals in place and leaves training open.';return base;}
  const a=options[0],previous=state.sessions.filter(x=>x.activityId===a.id&&x.date<=date).sort((a,b)=>b.date.localeCompare(a.date))[0];
  const duration=Math.min(s.availableMinutes,previous?.duration||20);
  const distance=a.metric==='distance'&&previous?.distance?Math.round(previous.distance*Math.min(1,duration/previous.duration)*10)/10:null;
  base.activity={id:a.id,name:a.name,icon:a.icon,duration,detail:`${duration} min · ${distance?`${distance} km · `:''}${previous?'repeat a familiar session':'comfortable, self-selected pace'}${a.partner?' · partner confirmed':''}`};
  base.reason=d.soreness&&d.soreness!=='none'?'The selected activity avoids the area you marked sore. Keep the session familiar; your meals stay regular.':!completeFood?'Some meal slots are still unlogged. Tomorrow keeps a familiar activity and regular meals; missing logs don’t trigger a harder plan.':'Your available time and activity preferences guide a familiar session. No automatic increase in exercise load.';
  return base;
}
