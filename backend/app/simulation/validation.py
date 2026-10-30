from collections import Counter
from app.schemas.events import EventType


def validate_match(events):
    errors = []
    if not events:
        return {'valid': False, 'errors': ['No events']}
    if events[0].event_type != EventType.KICK_OFF:
        errors.append('Match must begin with kick-off')
    if events[-1].event_type != EventType.FULL_TIME:
        errors.append('Match must end with full-time')
    if sum(e.event_type == EventType.HALF_TIME for e in events) != 1:
        errors.append('Expected one half-time event')
    if len({e.event_id for e in events}) != len(events):
        errors.append('Duplicate event IDs')
    if any(a.elapsed_seconds > b.elapsed_seconds for a, b in zip(events, events[1:])):
        errors.append('Events out of chronological order')
    if any(a.possession_id > b.possession_id for a, b in zip(events, events[1:])):
        errors.append('Possession IDs decreased')
    if any(e.synthetic is not True for e in events):
        errors.append('Non-synthetic event detected')
    if any(e.period == 1 and e.elapsed_seconds > 2700 or e.period == 2 and e.elapsed_seconds < 2700 for e in events):
        errors.append('Period and clock disagree')
    goals = Counter(e.team_id for e in events if e.event_type == EventType.GOAL)
    last = events[-1]
    if goals['home'] != last.score_home or goals['away'] != last.score_away:
        errors.append('Final score does not equal recorded goals')
    home = away = 0
    for e in events:
        if e.event_type == EventType.GOAL:
            if e.team_id == 'home': home += 1
            elif e.team_id == 'away': away += 1
        if (e.score_home, e.score_away) != (home, away):
            errors.append(f'Score mismatch at {e.event_id}')
            break
    for i, e in enumerate(events):
        if e.event_type == EventType.SHOT:
            if e.shot_outcome == 'goal' and (i+1 >= len(events) or events[i+1].event_type != EventType.GOAL):
                errors.append(f'Goal shot without goal event: {e.event_id}')
            if e.shot_outcome == 'saved' and (i+1 >= len(events) or events[i+1].event_type != EventType.SAVE):
                errors.append(f'Saved shot without save event: {e.event_id}')
        if e.event_type == EventType.GOAL and (i == 0 or events[i-1].event_type != EventType.SHOT):
            errors.append(f'Goal without preceding shot: {e.event_id}')
    return {'valid': not errors, 'errors': errors}


def summarize_match(events):
    counts = Counter(e.event_type.value for e in events)
    def team_stats(team):
        own = [e for e in events if e.team_id == team]
        passes = [e for e in own if e.event_type == EventType.PASS]
        shots = [e for e in own if e.event_type == EventType.SHOT]
        return {
            'goals': sum(e.event_type == EventType.GOAL for e in own),
            'passes': len(passes),
            'pass_completion_pct': round(100*sum(e.successful is True for e in passes)/len(passes), 1) if passes else 0,
            'shots': len(shots),
            'shots_on_target': sum(e.shot_outcome in ('goal','saved') for e in shots),
            'xg_proxy': round(sum(e.shot_xg or 0 for e in shots), 3),
            'interceptions': sum(e.event_type == EventType.INTERCEPTION for e in own),
            'tackles': sum(e.event_type == EventType.TACKLE for e in own),
            'recoveries': sum(e.event_type == EventType.RECOVERY for e in own),
            'pressures': sum(e.event_type == EventType.PRESSURE for e in own),
        }
    return {'duration_seconds': 5400, 'total_events': len(events), 'total_possessions': len({e.possession_id for e in events}) - 1,
            'event_counts': dict(counts), 'home': team_stats('home'), 'away': team_stats('away'),
            'coordinate_system': '0-100, possession-team attack normalized',
            'xg_note': 'Heuristic proxy, not calibrated xG',
            'possession_note': 'No time-weighted possession share computed'}
