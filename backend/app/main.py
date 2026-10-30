from functools import lru_cache
from fastapi import FastAPI, Query
from app.schemas.events import MatchConfig
from app.simulation.generator import generate_match

app = FastAPI(title='MatchLens Live API', version='0.4.0')

@lru_cache(maxsize=32)
def cached_match(match_id: str, seed: int):
    return generate_match(MatchConfig(match_id=match_id, seed=seed))

@app.get('/health')
def health():
    return {'status':'healthy','service':'matchlens-live'}

@app.get('/api/matches/{match_id}/events')
def events(match_id: str, seed: int = 42, count: int = Query(default=100, ge=1, le=5000), offset: int = Query(default=0, ge=0)):
    match = cached_match(match_id, seed)
    return {'match_id': match_id, 'total': len(match.events), 'events': match.events[offset:offset+count]}

@app.get('/api/matches/{match_id}/summary')
def summary(match_id: str, seed: int = 42):
    m = cached_match(match_id, seed)
    return {'match_id':match_id,'summary':m.summary,'validation':m.validation}

@app.get('/api/matches/{match_id}/intelligence')
def intelligence(match_id: str, seed: int = 42, count: int = Query(default=100, ge=1, le=5000), offset: int = Query(default=0, ge=0)):
    from app.analytics.xt import calculate_xt_gain
    m = cached_match(match_id, seed)
    enriched = []
    for e in m.events[offset:offset+count]:
        item = e.model_dump(mode='json')
        item['xt_gain'] = (calculate_xt_gain(e.x,e.y,e.end_x,e.end_y)
                           if e.event_type.value in ('pass','carry') and e.successful and e.end_x is not None else None)
        enriched.append(item)
    return {'match_id':match_id,'total_events':len(m.events),'events':enriched,'synthetic':True}

@app.get('/api/matches/{match_id}/tactical-insights')
def tactical_insights(match_id: str, seed: int = 42,
                      window_seconds: int = Query(default=300, ge=60, le=1800),
                      as_of_seconds: int | None = Query(default=None, ge=0, le=5400)):
    from app.analytics.tactical import analyze_match
    match = cached_match(match_id, seed)
    return analyze_match(match.events, window_seconds=window_seconds,
                         as_of_seconds=as_of_seconds)
