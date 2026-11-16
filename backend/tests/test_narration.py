import copy
import re

import pytest

from app.analytics.tactical import analyze_match
from app.narration.narrator import narrate
from app.narration.templates import LANGS, STYLES
from app.narration.verifier import numbers, verify_moment, verify_snapshot
from app.schemas.events import MatchConfig
from app.simulation.generator import generate_match
from app.simulation.rosters import build_rosters
from export_showcase import key_moments


@pytest.fixture(scope='module')
def match():
    seed = 230                      # a high-scoring match with cards and big chances
    events = generate_match(MatchConfig(seed=seed, match_id='n')).events
    teams = build_rosters(seed)
    return events, teams, key_moments(events, teams)


def test_every_moment_in_every_language_and_style_verifies(match):
    events, teams, moments = match
    assert len(moments) >= 5
    assert 'goal' in {m['kind'] for m in moments}
    for m in moments:
        assert verify_moment(events, m, teams, m['texts']) == []
        for s in STYLES:
            for l in LANGS:
                assert '{' not in m['texts'][s][l] and m['texts'][s][l].strip()


def test_translations_carry_exactly_the_same_numbers(match):
    _e, _t, moments = match
    for m in moments:
        for s in STYLES:
            ref = numbers(m['texts'][s]['en'])
            assert all(numbers(m['texts'][s][l]) == ref for l in LANGS)


def _first(moments, kind):
    return next(m for m in moments if m['kind'] == kind)


def test_verifier_catches_a_wrong_score(match):
    events, teams, moments = match
    m = copy.deepcopy(_first(moments, 'goal'))
    m['texts']['fan']['en'] = re.sub(r"It's \d+-\d+", "It's 9-9", m['texts']['fan']['en'])
    assert any('numbers' in f for f in verify_moment(events, m, teams, m['texts']))


def test_verifier_catches_a_wrong_minute_name_and_club(match):
    events, teams, moments = match
    m = copy.deepcopy(_first(moments, 'goal'))
    wrong_min = dict(m['texts']['analyst'], en=m['texts']['analyst']['en'].replace(
        f"{m['elapsed_seconds'] // 60}'", "99'", 1))
    assert verify_moment(events, m, teams, {**m['texts'], 'analyst': wrong_min})
    who = next(p['name'] for s in teams.values() for p in s['players'] if p['player_id'] == m['player_id'])
    wrong_name = dict(m['texts']['fan'], sw=m['texts']['fan']['sw'].replace(who, 'Someone Else'))
    assert any('player name' in f for f in verify_moment(events, m, teams, {**m['texts'], 'fan': wrong_name}))
    wrong_club = dict(m['texts']['fan'], es=m['texts']['fan']['es'].replace(teams[m['team_id']]['name'], 'Imaginary FC'))
    assert any('club name' in f for f in verify_moment(events, m, teams, {**m['texts'], 'fan': wrong_club}))


def test_verifier_catches_a_tampered_moment_record(match):
    events, teams, moments = match
    m = copy.deepcopy(_first(moments, 'goal'))
    m['score_home'] += 1
    assert verify_moment(events, m, teams, m['texts'])
    m2 = copy.deepcopy(_first(moments, 'goal')); m2['event_id'] = 'event-999999'
    assert verify_moment(events, m2, teams, m2['texts']) == ['event-999999: event not found']


def test_snapshot_verifier_accepts_real_and_rejects_tampered_analysis(match):
    events, _t, _m = match
    good = analyze_match(events, as_of_seconds=2400)
    assert verify_snapshot(events, good) == []
    bad = copy.deepcopy(good); bad['team_metrics']['home']['shots'] += 1
    assert any('home.shots' in f for f in verify_snapshot(events, bad))
    future = copy.deepcopy(good)
    late = next(e.event_id for e in events if e.elapsed_seconds > 2400)
    future['insights'][0]['evidence_event_ids'].append(late)
    assert any('future' in f for f in verify_snapshot(events, future))


def test_unknown_language_is_rejected(match):
    _e, teams, moments = match
    with pytest.raises(KeyError):
        narrate(moments[0], teams, 'xx', 'fan')
