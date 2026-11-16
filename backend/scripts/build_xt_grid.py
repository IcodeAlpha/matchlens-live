"""Learn a 16x12 expected-threat grid from SIMULATED matches (no real-world data).

Classic Markov xT: for each zone z,
    xT(z) = p_shoot(z) * xG(z) + sum_z' P(move z -> z' succeeds) * xT(z')
Failed moves lose the ball and contribute zero. Solved by value iteration.

Usage (from backend/):  python scripts/build_xt_grid.py --matches 300
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.analytics.xt import COLS, GRID_PATH, META_PATH, zone  # noqa: E402
from app.schemas.events import EventType as T, MatchConfig  # noqa: E402
from app.simulation.generator import generate_match  # noqa: E402


def build(matches: int, first_seed: int) -> tuple[np.ndarray, dict]:
    n = (COLS, 12)
    shots = np.zeros(n); xg_sum = np.zeros(n); moves = np.zeros(n)
    trans = np.zeros(n + n)
    for seed in range(first_seed, first_seed + matches):
        for e in generate_match(MatchConfig(seed=seed, match_id=f'xt-{seed}')).events:
            if e.event_type == T.SHOT:
                z = zone(e.x, e.y); shots[z] += 1; xg_sum[z] += e.shot_xg
            elif e.event_type in (T.PASS, T.CARRY):
                z = zone(e.x, e.y); moves[z] += 1
                if e.successful:
                    trans[z + zone(e.end_x, e.end_y)] += 1
    actions = shots + moves
    safe = np.maximum(actions, 1)
    p_shoot = shots / safe
    xg_zone = xg_sum / np.maximum(shots, 1)
    t = trans / np.maximum(moves, 1)[..., None, None]      # failed moves leak out (value 0)
    p_move = moves / safe
    grid = np.zeros(n)
    for _ in range(300):
        new = p_shoot * xg_zone + p_move * np.einsum('abcd,cd->ab', t, grid)
        if np.abs(new - grid).max() < 1e-9:
            grid = new; break
        grid = new
    meta = {'source': 'synthetic simulator (app.simulation.generator)',
            'real_world_data': False, 'matches': matches,
            'seeds': [first_seed, first_seed + matches - 1],
            'method': 'Markov xT, value iteration, xG(z)=mean simulator shot xG',
            'unvisited_zones': int((actions == 0).sum())}
    return grid, meta


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--matches', type=int, default=300)
    ap.add_argument('--first-seed', type=int, default=10_000)  # disjoint from demo seeds
    a = ap.parse_args()
    grid, meta = build(a.matches, a.first_seed)
    GRID_PATH.parent.mkdir(parents=True, exist_ok=True)
    np.save(GRID_PATH, grid)
    META_PATH.write_text(json.dumps(meta, indent=2))
    print(f'wrote {GRID_PATH} shape={grid.shape} min={grid.min():.4f} max={grid.max():.4f}')
    print(json.dumps(meta, indent=2))