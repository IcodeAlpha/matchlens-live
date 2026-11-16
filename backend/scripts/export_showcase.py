"""Pre-compute showcase matches as static JSON, so the demo needs no server.

Scans seeds for matches with a story (comeback, late winner, red card, result
against the run of play, goal fest, stalemate), then writes for each pick:
events, fictional rosters, narrated key moments (en/es/sw, fan/analyst), and
analysis snapshots every N seconds. Every narrated claim and every snapshot is
re-verified against the raw event log before anything is written: if a single
check fails, the export aborts.

Everything is synthetic and deterministic: same arguments -> byte-identical files.

Usage (from backend/):
    python scripts/build_xt_grid.py --matches 300          # once
    python scripts/export_showcase.py --out ../frontend/public/data
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.analytics import xt  # noqa: E402
from app.analytics.tactical import analyze_match  # noqa: E402
from app.narration.narrator import narrate_all  # noqa: E402
from app.narration.verifier import verify_moment, verify_snapshot  # noqa: E402
from app.schemas.events import EventType as T, MatchConfig  # noqa: E402
from app.simulation.generator import generate_match  # noqa: E402
from app.simulation.rosters import build_rosters  # noqa: E402

LATE = 4800          # 80:00
PRIORITY = ['comeback', 'late_winner', 'red_card', 'xg_upset', 'goal_fest', 'stalemate', 'rout']


def _mm(seconds: int) -> str:
    return f"{seconds // 60}'"


def facts(events) -> dict:
    """Story facts derived only from the event log."""
    h = a = 0
    timeline = [(0, 0, 0, None)]
    for e in events:
        if e.event_type == T.GOAL:
            h, a = e.score_home, e.score_away
            timeline.append((e.elapsed_seconds, h, a, e.team_id))
    final = (events[-1].score_home, events[-1].score_away)
    winner = 'home' if final[0] > final[1] else 'away' if final[1] > final[0] else None
    xg = {'home': 0.0, 'away': 0.0}
    shots = {'home': 0, 'away': 0}
    for e in events:
        if e.event_type == T.SHOT:
            xg[e.team_id] += e.shot_xg
            shots[e.team_id] += 1
    out = {'final': final, 'winner': winner, 'xg': xg, 'shots': shots,
           'total_goals': sum(final), 'margin': abs(final[0] - final[1]),
           'reds': [e for e in events if e.event_type == T.RED_CARD]}
    deficit, late_goal = 0, None
    if winner:
        loser = 'away' if winner == 'home' else 'home'
        for _, th, ta, _team in timeline:
            w, l = (th, ta) if winner == 'home' else (ta, th)
            deficit = max(deficit, l - w)
        scored = [t for t in timeline[1:] if t[3] == winner]
        if scored:
            t, th, ta, _ = scored[-1]
            w, l = (th, ta) if winner == 'home' else (ta, th)
            if t >= LATE and w - 1 <= l:            # the winner was not ahead before it
                late_goal = t
        out['upset_gap'] = xg[loser] - xg[winner]
    out['deficit'], out['late_goal'] = deficit, late_goal
    return out


def tags_and_scores(f: dict) -> dict[str, float]:
    s: dict[str, float] = {}
    if f['winner'] and f['deficit'] >= 1:
        s['comeback'] = f['deficit'] * 10 + f['total_goals']
    if f['late_goal']:
        s['late_winner'] = f['total_goals'] + (f['late_goal'] - LATE) / 600
    if f['reds'] and f['total_goals'] >= 2:
        s['red_card'] = len(f['reds']) * 5 + f['total_goals']
    if f['winner'] and f.get('upset_gap', 0) >= .8:
        s['xg_upset'] = f['upset_gap'] * 10
    if f['total_goals'] >= 5:
        s['goal_fest'] = f['total_goals'] * 10 + sum(f['shots'].values())
    if f['final'] == (0, 0) and sum(f['shots'].values()) >= 20:
        s['stalemate'] = sum(f['shots'].values())
    if f['winner'] and f['margin'] >= 3:
        s['rout'] = f['margin'] * 10 + f['total_goals']
    return s


def label(tag: str, f: dict, teams: dict) -> str:
    w = teams[f['winner']]['name'] if f['winner'] else None
    score = f"{f['final'][0]}-{f['final'][1]}"
    if tag == 'comeback':
        return f"{w} come from {f['deficit']} goal{'s' if f['deficit'] > 1 else ''} down to win {score}"
    if tag == 'late_winner':
        return f"{w} snatch it late: decisive goal on {_mm(f['late_goal'])} ({score})"
    if tag == 'red_card':
        r = f['reds'][0]
        return f"{teams[r.team_id]['name']} reduced to ten men on {_mm(r.elapsed_seconds)} ({score})"
    if tag == 'xg_upset':
        loser = 'away' if f['winner'] == 'home' else 'home'
        return (f"{w} win {score} against the run of play "
                f"({f['xg'][f['winner']]:.1f} xG vs {f['xg'][loser]:.1f})")
    if tag == 'goal_fest':
        return f"Goal fest: {score}"
    if tag == 'stalemate':
        return f"Goalless with {sum(f['shots'].values())} shots"
    return f"{w} run riot, {score}"


def key_moments(events, teams: dict) -> list[dict]:
    out = []
    for i, e in enumerate(events):
        xg = e.shot_xg
        if e.event_type == T.GOAL:
            kind = 'goal'
            xg = events[i - 1].shot_xg if i and events[i - 1].event_type == T.SHOT else None
        elif e.event_type == T.RED_CARD:
            kind = 'red_card'
        elif e.event_type == T.SHOT and e.shot_outcome != 'goal' and (e.shot_xg or 0) >= .25:
            kind = 'big_chance'
        else:
            continue
        m = {'event_id': e.event_id, 'elapsed_seconds': e.elapsed_seconds, 'kind': kind,
             'team_id': e.team_id, 'player_id': e.player_id, 'xg': xg,
             'outcome': e.shot_outcome if kind == 'big_chance' else None,
             'score_home': e.score_home, 'score_away': e.score_away,
             'evidence_event_ids': [e.event_id]}
        m['texts'] = narrate_all(m, teams)
        m['text'] = m['texts']['fan']['en']
        out.append(m)
    return out


def dump(path: Path, obj) -> int:
    data = json.dumps(obj, separators=(',', ':'), ensure_ascii=True)
    path.write_text(data, encoding='utf-8')
    return len(data.encode('utf-8'))


def export(out: Path, scan: int = 400, count: int = 6, step: int = 60,
           first_seed: int = 1) -> list[dict]:
    if xt.xt_metadata() is None:
        raise SystemExit('xT grid missing: run  python scripts/build_xt_grid.py  first, so the '
                         'exported analysis is reproducible.')
    best: dict[str, tuple[float, int]] = {}
    pool: dict[int, dict] = {}
    for seed in range(first_seed, first_seed + scan):
        res = generate_match(MatchConfig(seed=seed, match_id=f'scan-{seed}'))
        f = facts(res.events)
        sc = tags_and_scores(f)
        pool[seed] = sc
        for tag, v in sc.items():
            if tag not in best or v > best[tag][0]:
                best[tag] = (v, seed)
    picks: list[tuple[str, int]] = []
    for tag in PRIORITY:
        if tag in best and best[tag][1] not in [s for _, s in picks] and len(picks) < count:
            picks.append((tag, best[tag][1]))

    (out / 'matches').mkdir(parents=True, exist_ok=True)
    index = []
    for tag, seed in picks:
        match_id = f'{tag.replace("_", "-")}-{seed}'
        res = generate_match(MatchConfig(seed=seed, match_id=match_id))
        teams = build_rosters(seed)
        f = facts(res.events)
        snaps = [{'as_of_seconds': t,
                  'analysis': analyze_match(res.events, as_of_seconds=t)}
                 for t in list(range(step, 5400, step)) + [5400]]
        moments = key_moments(res.events, teams)
        fails: list[str] = []
        for mo in moments:
            bad = verify_moment(res.events, mo, teams, mo['texts'])
            mo['verified'] = not bad
            fails += bad
        for sn in snaps:
            fails += verify_snapshot(res.events, sn['analysis'])
        if fails:
            raise SystemExit(f'verification failed for {match_id}:\n' + '\n'.join(fails[:20]))
        verification = {'moments': len(moments), 'moments_verified': len(moments),
                        'snapshots': len(snaps), 'snapshots_verified': len(snaps),
                        'languages': ['en', 'es', 'sw'], 'styles': ['fan', 'analyst'],
                        'method': 'recomputed independently from the raw event log'}
        doc = {'match_id': match_id, 'seed': seed, 'synthetic': True, 'generator': 'v2',
               'label': label(tag, f, teams), 'tags': sorted(pool[seed]) or [tag],
               'primary_tag': tag, 'teams': teams, 'summary': res.summary,
               'key_moments': moments, 'verification': verification,
               'events': [e.model_dump(mode='json') for e in res.events],
               'snapshots': snaps, 'snapshot_step_seconds': step}
        size = dump(out / 'matches' / f'{match_id}.json', doc)
        index.append({'match_id': match_id, 'seed': seed, 'label': doc['label'],
                      'tags': doc['tags'], 'primary_tag': tag, 'final_score':
                      {'home': f['final'][0], 'away': f['final'][1]},
                      'home': {k: teams['home'][k] for k in ('name', 'short', 'color')},
                      'away': {k: teams['away'][k] for k in ('name', 'short', 'color')},
                      'file': f'matches/{match_id}.json', 'bytes': size})
    dump(out / 'index.json', {'synthetic': True, 'generator': 'v2',
                              'xt_grid': xt.xt_metadata(), 'matches': index})
    return index


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(Path(__file__).resolve().parents[2] / 'frontend' / 'public' / 'data'))
    ap.add_argument('--scan', type=int, default=400)
    ap.add_argument('--count', type=int, default=6)
    ap.add_argument('--snapshot-step', type=int, default=60)
    ap.add_argument('--first-seed', type=int, default=1)
    a = ap.parse_args()
    for m in export(Path(a.out), a.scan, a.count, a.snapshot_step, a.first_seed):
        print(f"{m['match_id']:<26} {m['final_score']['home']}-{m['final_score']['away']}  "
              f"{m['bytes']/1024:7.0f} KB  {m['label']}")