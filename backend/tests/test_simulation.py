from app.schemas.events import MatchConfig, EventType
from app.simulation.generator import generate_match
from app.simulation.validation import validate_match


def test_match_valid_and_deterministic():
    cfg = MatchConfig(seed=42)
    a, b = generate_match(cfg), generate_match(cfg)
    assert a.model_dump() == b.model_dump()
    assert a.validation['valid'], a.validation
    assert a.events[-1].event_type == EventType.FULL_TIME
    assert a.events[-1].elapsed_seconds == 5400
    assert len(a.events) > 300


def test_seeds_and_tactics():
    for seed in [1,2,3,4,5,42,99,123,999]:
        m = generate_match(MatchConfig(seed=seed, home_style='direct', away_style='pressing'))
        assert validate_match(m.events)['valid'], (seed, m.validation)
        assert all(e.synthetic for e in m.events)
        assert any(e.event_type == EventType.INTERCEPTION for e in m.events)


def test_goal_is_supported_by_shot():
    m = generate_match(MatchConfig(seed=5))
    for i, e in enumerate(m.events):
        if e.event_type == EventType.GOAL:
            assert m.events[i-1].event_type == EventType.SHOT
            assert m.events[i-1].shot_outcome == 'goal'
