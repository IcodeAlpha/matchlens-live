"""Realism report: aggregate statistics of simulated matches vs typical top-flight ranges.

The bands are approximate ranges written by the author from general football
knowledge. They are NOT sourced figures: adjust them, cite your own sources if
you tighten them, and never describe the simulator as "calibrated to real data".

Usage (from backend/):  python scripts/realism_report.py --matches 150 --out docs/realism_report
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.events import EventType as T, MatchConfig  # noqa: E402
from app.simulation.generator import generate_match  # noqa: E402

# (key, label, low, high)
BANDS = [
    ('shots', 'Shots per team', 9, 15),
    ('goals_team', 'Goals per team', 1.1, 1.7),
    ('goals_match', 'Goals per match (both teams)', 2.3, 3.2),
    ('conversion', 'Shot conversion %', 8, 13),
    ('on_target', 'Shots on target % of shots', 30, 40),
    ('xg_per_shot', 'Mean xG per shot', 0.08, 0.12),
    ('passes', 'Passes per team', 350, 600),
    ('pass_comp', 'Pass completion %', 78, 88),
    ('tackles', 'Tackles per team', 12, 25),
    ('interceptions', 'Interceptions per team', 8, 18),
    ('pressures', 'Pressures per team', 80, 170),
    ('corners', 'Corners per team', 3.5, 6.5),
    ('fouls', 'Fouls per team', 8, 13),
    ('yellows', 'Yellow cards per match', 2.2, 5.0),
    ('reds', 'Red cards per match', 0.04, 0.18),
]


def measure(matches: int, first_seed: int) -> tuple[dict, int]:
    rows, invalid = [], 0
    for seed in range(first_seed, first_seed + matches):
        m = generate_match(MatchConfig(seed=seed, match_id=f'r-{seed}'))
        invalid += not m.validation['valid']
        yellows = sum(e.event_type == T.YELLOW_CARD for e in m.events)
        reds = sum(e.event_type == T.RED_CARD for e in m.events)
        for team in ('home', 'away'):
            ev = [e for e in m.events if e.team_id == team]
            shots = [e for e in ev if e.event_type == T.SHOT]
            passes = [e for e in ev if e.event_type == T.PASS]
            rows.append(dict(
                shots=len(shots), goals=sum(e.shot_outcome == 'goal' for e in shots),
                on_target=sum(e.shot_outcome in ('goal', 'saved') for e in shots),
                xg=sum(e.shot_xg for e in shots), passes=len(passes),
                comp=sum(bool(e.successful) for e in passes),
                tackles=sum(e.event_type == T.TACKLE for e in ev),
                interceptions=sum(e.event_type == T.INTERCEPTION for e in ev),
                pressures=sum(e.event_type == T.PRESSURE for e in ev),
                corners=sum(e.event_type == T.CORNER for e in ev),
                fouls=sum(e.event_type == T.FOUL for e in ev), yellows=yellows / 2, reds=reds / 2))
    mean = lambda k: st.mean(r[k] for r in rows)  # noqa: E731
    s = mean('shots')
    return {
        'shots': s, 'goals_team': mean('goals'), 'goals_match': 2 * mean('goals'),
        'conversion': 100 * mean('goals') / s, 'on_target': 100 * mean('on_target') / s,
        'xg_per_shot': mean('xg') / s, 'passes': mean('passes'),
        'pass_comp': 100 * mean('comp') / mean('passes'), 'tackles': mean('tackles'),
        'interceptions': mean('interceptions'), 'pressures': mean('pressures'),
        'corners': mean('corners'), 'fouls': mean('fouls'),
        'yellows': 2 * mean('yellows'), 'reds': 2 * mean('reds'),
    }, invalid


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--matches', type=int, default=150)
    ap.add_argument('--first-seed', type=int, default=1)
    ap.add_argument('--out', default='docs/realism_report')
    ap.add_argument('--strict', action='store_true', help='exit 1 if any metric is out of band')
    a = ap.parse_args()
    values, invalid = measure(a.matches, a.first_seed)
    lines = ['# Synthetic realism report', '',
             f'{a.matches} simulated matches (seeds {a.first_seed}-{a.first_seed + a.matches - 1}); '
             f'structurally invalid matches: {invalid}.', '',
             'Bands are approximate top-flight ranges chosen by the author, not sourced figures.', '',
             '| Metric | Simulated | Band | Status |', '|---|---|---|---|']
    out, result = 0, {}
    for key, label, lo, hi in BANDS:
        v = values[key]; ok = lo <= v <= hi; out += not ok
        result[key] = {'value': round(v, 3), 'low': lo, 'high': hi, 'in_band': ok}
        lines.append(f'| {label} | {v:.2f} | {lo}-{hi} | {"ok" if ok else "OUT OF BAND"} |')
    lines += ['', f'In band: {len(BANDS) - out}/{len(BANDS)}']
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out + '.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    Path(a.out + '.json').write_text(json.dumps(
        {'matches': a.matches, 'invalid': invalid, 'metrics': result}, indent=2))
    print('\n'.join(lines))
    sys.exit(1 if (a.strict and out) else 0)