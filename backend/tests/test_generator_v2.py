from collections import Counter

import pytest

from app.schemas.events import EventType as T, MatchConfig
from app.simulation.generator import generate_match
from realism_report import BANDS, measure

SEEDS = range(7000, 7040)


def _match(seed):
    return generate_match(MatchConfig(seed=seed, match_id=f't-{seed}'))


def test_sent_off_players_never_act_again():
    reds = 0
    for seed in SEEDS:
        m = _match(seed)
        assert m.validation['valid'], m.validation['errors'][:3]
        gone = set()
        for e in m.events:
            if e.event_type == T.RED_CARD:
                gone.add((e.team_id, e.player_id)); reds += 1
            elif e.player_id and (e.team_id, e.player_id) in gone:
                pytest.fail(f'{e.player_id} acted after a red card at {e.event_id}')
    assert reds > 0, 'expected at least one red card across the sample'


def test_every_card_directly_follows_a_foul_by_the_same_player():
    for seed in SEEDS:
        ev = _match(seed).events
        for i, e in enumerate(ev):
            if e.event_type in (T.YELLOW_CARD, T.RED_CARD):
                prior = [x for x in ev[max(0, i - 2):i] if x.event_type in (T.FOUL, T.YELLOW_CARD)]
                assert prior and prior[0].player_id == e.player_id and prior[0].team_id == e.team_id


def test_a_foul_is_followed_by_a_free_kick_for_the_other_team():
    for seed in SEEDS:
        ev = _match(seed).events
        for i, e in enumerate(ev):
            if e.event_type == T.FOUL:
                fk = next(x for x in ev[i + 1:i + 5] if x.event_type == T.FREE_KICK)
                assert fk.team_id != e.team_id


def test_corners_start_at_the_flag_and_are_delivered_by_the_same_team():
    n = 0
    for seed in SEEDS:
        ev = _match(seed).events
        for i, e in enumerate(ev):
            if e.event_type == T.CORNER:
                n += 1
                assert e.x >= 99 and (e.y <= 2.01 or e.y >= 97.99)
                d = ev[i + 1]
                assert d.event_type == T.PASS and d.restart == 'corner' and d.team_id == e.team_id
    assert n > 50


def test_same_seed_same_match_v2():
    a, b = _match(7001), _match(7001)
    assert [e.model_dump() for e in a.events] == [e.model_dump() for e in b.events]


def test_realism_stays_inside_the_documented_bands():
    values, invalid = measure(matches=100, first_seed=8000)
    assert invalid == 0
    outside = {k: round(values[k], 2) for k, _l, lo, hi in BANDS if not lo <= values[k] <= hi}
    assert not outside, f'metrics out of band: {outside}'


def test_roles_behave_like_roles():
    shots, defending = Counter(), Counter()
    for seed in range(100, 140):
        for e in _match(seed).events:
            n = int(e.player_id.split('-')[1]) if e.player_id else None
            if e.event_type == T.SHOT:
                shots[n] += 1
            elif e.event_type in (T.TACKLE, T.INTERCEPTION):
                defending[n] += 1
    assert shots[9] > 5 * max(shots[4], shots[5]), 'strikers should shoot far more than centre-backs'
    assert min(defending[4], defending[5], defending[6]) > 2 * defending[9], \
        'centre-backs and the DM should win the ball far more than the striker'
