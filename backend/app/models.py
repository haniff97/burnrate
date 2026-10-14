from datetime import date, datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo
from pydantic import BaseModel, ConfigDict, Field, model_validator

Number = Annotated[float, Field(ge=0, le=100000, allow_inf_nan=False)]
Positive = Annotated[float, Field(gt=0, le=10000, allow_inf_nan=False)]
Identifier = Annotated[str, Field(min_length=1, max_length=100)]
Clock = Annotated[str, Field(pattern=r'^(?:[01]\d|2[0-3]):[0-5]\d$')]

def local_today():
    return datetime.now(ZoneInfo('Asia/Kuala_Lumpur')).date()

class Model(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

class Settings(Model):
    name: str = Field(min_length=1, max_length=40)
    startWeight: float = Field(ge=20, le=400)
    targetWeight: float = Field(ge=20, le=400)
    endDate: date
    calorieFloor: float = Field(ge=500, le=5000)
    proteinTarget: float = Field(ge=10, le=300)
    waterTarget: float = Field(ge=.25, le=8)
    availableMinutes: Literal[0,15,30,45,60]
    mealTimes: dict[str, Clock]
    fasting: bool
    eatFrom: Clock
    eatUntil: Clock

    @model_validator(mode='after')
    def coherent(self):
        if set(self.mealTimes) != {'Lunch','Snack','Dinner'}:
            raise ValueError('Lunch, Snack and Dinner times are required')
        if self.targetWeight >= self.startWeight:
            raise ValueError('Weight-loss target must be below start weight')
        if self.fasting and (self.eatFrom >= self.eatUntil or any(not self.eatFrom <= t <= self.eatUntil for t in self.mealTimes.values())):
            raise ValueError('Meal times must fit the eating window')
        return self

class FoodItem(Model):
    id: Identifier
    food: str | None = None
    name: str = Field(min_length=1,max_length=160)
    amount: Positive
    unit: Literal['g','ml','unit','serving']
    kcal: Number
    protein: Number | None = None
    quality: Literal['weighed','label_based','saved_serving','calibrated_photo','uncalibrated_estimate','manual_estimate']
    low: Number
    high: Number
    emoji: str = Field(default='🍽️',max_length=20)
    nutrition_source: str = Field(default='catalog_average',max_length=40)
    assumptions: str | None = Field(default=None,max_length=1000)
    @model_validator(mode='after')
    def ranges(self):
        if not self.low <= self.kcal <= self.high:
            raise ValueError('Calories must lie within their range')
        return self

class Meal(Model):
    id: Identifier
    date: date
    slot: Literal['Lunch','Snack','Dinner']
    items: list[FoodItem] = Field(min_length=1,max_length=30)

class Activity(Model):
    id: Identifier
    name: str = Field(min_length=1,max_length=50)
    icon: str = Field(max_length=30)
    type: Literal['cardio','strength','sport','mobility']
    metric: Literal['duration','distance','reps']
    preference: Literal['most','mid','least']
    enabled: bool
    partner: bool
    available: bool

class Session(Model):
    id: Identifier
    date: date
    activityId: Identifier
    name: str = Field(min_length=1,max_length=50)
    duration_mode: Literal['minutes','all_day'] = 'minutes'
    duration: float | None = Field(default=None,gt=0,le=600)
    effort: int = Field(ge=1,le=10)
    distance: Positive | None = None
    steps: int | None = Field(default=None,ge=0,le=200000,strict=True)
    sets: int | None = Field(default=None,ge=1,le=100)
    reps: int | None = Field(default=None,ge=0,le=1000)
    hold: float | None = Field(default=None,gt=0,le=3600)
    status: Literal['completed','partial']
    @model_validator(mode='after')
    def duration_matches_mode(self):
        if self.duration_mode=='minutes' and self.duration is None:raise ValueError('Minutes require a duration')
        if self.duration_mode=='all_day' and self.duration is not None:raise ValueError('All-day entries do not contain timed minutes')
        return self

class Weight(Model):
    date: date
    kg: float = Field(ge=20,le=400)

class Daily(Model):
    energy: int | None = Field(default=None,ge=1,le=5)
    water: float = Field(default=0,ge=0,le=10)
    sleep: float | None = Field(default=None,ge=0,le=24)
    soreness: Literal['none','legs','upper body','pain'] = 'none'

class Preset(Model):
    id: Identifier
    name: str = Field(min_length=1,max_length=500)
    emoji: str = Field(default='🍽️',max_length=20)
    items: list[FoodItem] = Field(min_length=1,max_length=30)

class Journal(Model):
    version: Literal[1]
    demo: bool
    revision: int = Field(ge=0)
    settings: Settings
    activities: list[Activity] = Field(max_length=100)
    meals: list[Meal] = Field(max_length=10000)
    sessions: list[Session] = Field(max_length=10000)
    weights: list[Weight] = Field(max_length=10000)
    days: dict[date,Daily]
    plan: dict | None = None  # Client plan ignored; only validated server plans are published.
    savedPresets: list[Preset] = Field(max_length=1000)
    @model_validator(mode='after')
    def references(self):
        for rows in [self.activities,self.meals,self.sessions,self.savedPresets]:
            if len({r.id for r in rows}) != len(rows): raise ValueError('Duplicate record ID')
        activity={a.id:a for a in self.activities}
        for session in self.sessions:
            a=activity.get(session.activityId)
            if not a: raise ValueError('Unknown session activity')
            if a.metric=='distance' and session.distance is None: raise ValueError('Distance required')
            if a.metric=='reps' and not (session.reps or session.hold): raise ValueError('Reps or hold required')
        if len({w.date for w in self.weights}) != len(self.weights): raise ValueError('One weight per date')
        if any(r.date>local_today() for r in [*self.meals,*self.sessions,*self.weights]) or any(d>local_today() for d in self.days):
            raise ValueError('Actual logs cannot be future dated')
        for meal in self.meals:
            if len({i.id for i in meal.items})!=len(meal.items): raise ValueError('Duplicate meal item')
        return self

class StateWrite(Model):
    expected_revision: int = Field(ge=0)
    mutation_id: Identifier
    state: Journal

class PlanRequest(Model):
    expected_revision: int = Field(ge=0)
    date: date
    use_ai: bool = False

class PhotoRequest(Model):
    data_url: str = Field(max_length=12_000_000)
    draft_id: Identifier

class ConfirmDraft(Model):
    expected_revision: int = Field(ge=0)
    mutation_id: Identifier
    date: date
    slot: Literal['Lunch','Snack','Dinner']
    items: list[FoodItem] = Field(min_length=1,max_length=30)

class ReviewRequest(Model):
    expected_revision: int = Field(ge=0)
    date: date
    use_ai: bool = False

class RecoveryRequest(Model):
    code: str = Field(min_length=1,max_length=100)
