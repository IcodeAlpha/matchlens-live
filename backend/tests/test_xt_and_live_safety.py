import numpy as np
import pytest

from app.analytics import xt
from app.analytics.tactical import analyze_match
from app.schemas.events import MatchConfig
from app.simulation.generator import generate_match
from build_xt_grid import build


def test_generated_matches_are_valid_and_deterministic():
    for seed in range(1, 6):
        a = generate_match(MatchConfig(seed=seed))
        b = generate_match(MatchConfig(seed=seed))
        assert a.validation['valid'], a.validation['errors'][:3]
        assert [e.model_dump() for e in a.events] == [e.model_dump() for e in b.events]


def test_xt_grid_is_read_from_disk_once(tmp_path, monkeypatch):
    path = tmp_path / 'grid.npy'
    np.save(path, np.full((16, 12), 0.01))
    monkeypatch.setattr(xt, 'GRID_PATH', path)
    xt.reload_grid()
    calls = {'n': 0}
    real_load = np.load
    monkeypatch.setattr(np, 'load', lambda *a, **k: calls.__setitem__('n', calls['n'] + 1) or real_load(*a, **k))
    for _ in range(500):
        xt.calculate_xt_gain(10, 10, 60, 50)
    assert calls['n'] == 1
    xt.reload_grid()


def test_xt_is_none_when_grid_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(xt, 'GRID_PATH', tmp_path / 'missing.npy')
    xt.reload_grid()
    assert xt.calculate_xt_gain(10, 10, 60, 50) is None
    xt.reload_grid()


def test_wrong_grid_shape_is_rejected(tmp_path, monkeypatch):
    path = tmp_path / 'bad.npy'
    np.save(path, np.zeros((4, 4)))
    monkeypatch.setattr(xt, 'GRID_PATH', path)
    xt.reload_grid()
    with pytest.raises(ValueError):
        xt.calculate_xt_gain(1, 1, 2, 2)
    xt.reload_grid()


def test_simulated_xt_grid_properties():
    grid, meta = build(matches=60, first_seed=40_000)
    assert grid.shape == (16, 12) and (grid >= 0).all()
    assert meta['real_world_data'] is False and meta['unvisited_zones'] == 0
    cols = grid.mean(axis=1)
    assert (np.diff(cols) >= -1e-3).all(), 'threat should rise toward the opposition goal'
    cx, cy = np.unravel_index(grid.argmax(), grid.shape)
    assert cx >= 13 and 3 <= cy <= 8, 'peak threat should be central and near goal'


def test_live_analysis_never_references_future_events():
    events = generate_match(MatchConfig(seed=42)).events
    by_id = {e.event_id: e for e in events}
    for as_of in (305, 900, 2000, 4000):
        r = analyze_match(events, as_of_seconds=as_of)
        ids = [i for x in r['insights'] for i in x['evidence_event_ids']]
        ids += [i for p in r['dangerous_possessions'] for i in p['evidence_event_ids']]
        ids += [i for p in r['player_impact'] for i in p['evidence_event_ids']]
        assert ids and all(by_id[i].elapsed_seconds <= as_of for i in ids)
        assert r['momentum'][-1]['end_seconds'] - r['momentum'][-1]['start_seconds'] == 300
