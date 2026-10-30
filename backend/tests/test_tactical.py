from app.analytics.tactical import analyze_match
from app.schemas.events import MatchConfig
from app.simulation.generator import generate_match


def test_tactical_evidence_and_live_cutoff():
    match = generate_match(MatchConfig(seed=42))
    result = analyze_match(match.events, as_of_seconds=1200)
    visible = {e.event_id: e for e in match.events if e.elapsed_seconds <= 1200}
    assert result['synthetic'] is True
    assert result['as_of_seconds'] == 1200
    assert result['momentum']
    for insight in result['insights']:
        assert insight['evidence_event_ids']
        assert all(eid in visible for eid in insight['evidence_event_ids'])
    for possession in result['dangerous_possessions']:
        assert all(eid in visible for eid in possession['evidence_event_ids'])


def test_tactical_is_deterministic():
    events = generate_match(MatchConfig(seed=7)).events
    assert analyze_match(events) == analyze_match(events)


def test_tactical_empty_and_invalid_window():
    assert analyze_match([])['insights'] == []
    try:
        analyze_match([], window_seconds=0)
    except ValueError:
        pass
    else:
        raise AssertionError('Expected invalid window rejection')
