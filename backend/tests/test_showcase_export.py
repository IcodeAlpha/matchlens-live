import json

import numpy as np
import pytest

from app.analytics import xt
from app.analytics.tactical import analyze_match
from app.schemas.events import MatchEvent
from app.simulation.rosters import CLUBS, build_rosters
from build_xt_grid import build
from export_showcase import export

REAL_CLUBS = [
    'arsenal', 'aston villa', 'bournemouth', 'brentford', 'brighton', 'burnley', 'chelsea',
    'crystal palace', 'everton', 'fulham', 'leeds', 'leicester', 'liverpool', 'luton',
    'manchester city', 'manchester united', 'newcastle', 'nottingham forest', 'sheffield',
    'southampton', 'sunderland', 'tottenham', 'west ham', 'wolverhampton', 'wolves',
    'west bromwich', 'watford', 'norwich', 'real madrid', 'barcelona', 'bayern',
    'juventus', 'paris saint', 'atletico', 'dortmund', 'ajax', 'celtic', 'rangers fc',
]


@pytest.fixture(scope='module')
def tmp_grid(tmp_path_factory):
    d = tmp_path_factory.mktemp('grid')
    grid, meta = build(matches=25, first_seed=50_000)
    np.save(d / 'g.npy', grid)
    (d / 'g.meta.json').write_text(json.dumps(meta))
    return d


@pytest.fixture
def use_grid(tmp_grid, monkeypatch):
    monkeypatch.setattr(xt, 'GRID_PATH', tmp_grid / 'g.npy')
    monkeypatch.setattr(xt, 'META_PATH', tmp_grid / 'g.meta.json')
    xt.reload_grid()
    yield
    xt.reload_grid()


def test_club_names_are_fictional():
    for name, _short, _color in CLUBS:
        assert not any(real in name.lower() for real in REAL_CLUBS), name


def test_rosters_are_deterministic_and_unique():
    a, b = build_rosters(11), build_rosters(11)
    assert a == b and a['home']['name'] != a['away']['name']
    for side in ('home', 'away'):
        names = [p['name'] for p in a[side]['players']]
        assert len(set(names)) == 11 and len(a[side]['players']) == 11


def test_export_is_valid_deterministic_and_evidence_linked(tmp_path, use_grid):
    first = export(tmp_path / 'a', scan=60, count=3, step=600)
    export(tmp_path / 'b', scan=60, count=3, step=600)
    assert len(first) == 3
    for m in first:
        fa = (tmp_path / 'a' / m['file']).read_bytes()
        fb = (tmp_path / 'b' / m['file']).read_bytes()
        assert fa == fb, 'same arguments must give byte-identical output'
        doc = json.loads(fa)
        assert doc['synthetic'] is True
        assert doc['verification']['moments_verified'] == doc['verification']['moments']
        assert all(k['verified'] for k in doc['key_moments'])
        events = [MatchEvent(**e) for e in doc['events']]
        ids = {e.event_id for e in events}
        assert all(k['event_id'] in ids for k in doc['key_moments'])
        assert [e.elapsed_seconds for e in events] == sorted(e.elapsed_seconds for e in events)
        snap = doc['snapshots'][len(doc['snapshots']) // 2]
        assert snap['analysis'] == json.loads(json.dumps(analyze_match(events, as_of_seconds=snap['as_of_seconds'])))
        by_id = {e.event_id: e for e in events}
        for s in doc['snapshots']:
            refs = [i for x in s['analysis']['insights'] for i in x['evidence_event_ids']]
            assert all(by_id[i].elapsed_seconds <= s['as_of_seconds'] for i in refs)
    idx = json.loads((tmp_path / 'a' / 'index.json').read_text())
    assert idx['synthetic'] is True and idx['xt_grid']['real_world_data'] is False


def test_export_refuses_to_run_without_xt_grid(tmp_path, monkeypatch):
    monkeypatch.setattr(xt, 'META_PATH', tmp_path / 'missing.json')
    with pytest.raises(SystemExit):
        export(tmp_path / 'o', scan=5, count=1)
