"""Verifier: recompute every claim from the raw event log, independently.

It does not trust the narrator, the analyzer or the exported moment fields.
For a key moment it re-derives minute, score, players, clubs and xG from the
events and requires every narrated text to contain exactly those numbers and
names. For an analysis snapshot it recounts the team metrics from raw events.
"""
from __future__ import annotations

import re

from app.narration.templates import LANGS, STYLES, expected_numbers
from app.schemas.events import EventType as T

NUM = re.compile(r'\d+(?:\.\d+)?')
KIND_EVENT = {'goal': T.GOAL, 'red_card': T.RED_CARD, 'big_chance': T.SHOT}


def numbers(text: str) -> list[str]:
    return sorted(NUM.findall(text))


def verify_moment(events: list, moment: dict, teams: dict, texts: dict) -> list[str]:
    fails: list[str] = []
    eid = moment['event_id']
    idx = next((i for i, e in enumerate(events) if e.event_id == eid), None)
    if idx is None:
        return [f'{eid}: event not found']
    e = events[idx]
    if e.event_type != KIND_EVENT[moment['kind']]:
        fails.append(f'{eid}: kind {moment["kind"]} but event is {e.event_type.value}')
    if (e.team_id, e.player_id, e.elapsed_seconds) != (
            moment['team_id'], moment['player_id'], moment['elapsed_seconds']):
        fails.append(f'{eid}: team/player/time differ from the event')
    h = sum(1 for x in events[:idx + 1] if x.event_type == T.GOAL and x.team_id == 'home')
    a = sum(1 for x in events[:idx + 1] if x.event_type == T.GOAL and x.team_id == 'away')
    xg = None
    if moment['kind'] == 'goal':
        if (h, a) != (moment['score_home'], moment['score_away']):
            fails.append(f'{eid}: score {moment["score_home"]}-{moment["score_away"]} but recount is {h}-{a}')
        prev = events[idx - 1] if idx else None
        if not prev or prev.event_type != T.SHOT or prev.shot_outcome != 'goal':
            fails.append(f'{eid}: goal not preceded by a scoring shot')
        else:
            xg = prev.shot_xg
    elif moment['kind'] == 'big_chance':
        xg = e.shot_xg
        if e.shot_outcome == 'goal' or (xg or 0) < .25 or e.shot_outcome != moment.get('outcome'):
            fails.append(f'{eid}: not a big chance, or the outcome differs')
    if xg is not None and moment.get('xg') != xg:
        fails.append(f'{eid}: xG {moment.get("xg")} but the shot says {xg}')

    who = {p['player_id']: p['name'] for s in teams.values() for p in s['players']}.get(e.player_id)
    club = teams[e.team_id]['name'] if e.team_id in teams else None
    for style in STYLES:
        for lang in LANGS:
            text = texts[style][lang]
            want = expected_numbers(style, moment['kind'], e.elapsed_seconds // 60, h, a, xg)
            if numbers(text) != want:
                fails.append(f'{eid} [{style}/{lang}]: numbers {numbers(text)} != expected {want}')
            if who and who not in text:
                fails.append(f'{eid} [{style}/{lang}]: player name missing')
            if club and club not in text:
                fails.append(f'{eid} [{style}/{lang}]: club name missing')
    return fails


def verify_snapshot(events: list, analysis: dict) -> list[str]:
    """Independent recount of an analysis snapshot against the raw events."""
    t = analysis['as_of_seconds']
    ev = [e for e in events if e.elapsed_seconds <= t]
    by_id = {e.event_id: e for e in events}
    fails: list[str] = []
    for team in ('home', 'away'):
        m = analysis['team_metrics'][team]
        mine = [e for e in ev if e.team_id == team]
        shots = [e for e in mine if e.event_type == T.SHOT]
        prog = [e for e in mine if e.event_type in (T.PASS, T.CARRY) and e.successful
                and e.end_x - e.x >= 10]
        expect = {'shots': len(shots),
                  'progressive_actions': len(prog),
                  'pressures': sum(e.event_type == T.PRESSURE for e in mine),
                  'tackles': sum(e.event_type == T.TACKLE for e in mine),
                  'interceptions': sum(e.event_type == T.INTERCEPTION for e in mine)}
        for k, v in expect.items():
            if m[k] != v:
                fails.append(f'@{t}s {team}.{k}: analysis {m[k]} but recount {v}')
        if abs(m['xg_proxy'] - sum(e.shot_xg for e in shots)) > 1e-3:
            fails.append(f'@{t}s {team}.xg_proxy differs from recount')
    refs = [i for x in analysis['insights'] for i in x['evidence_event_ids']]
    refs += [i for x in analysis['momentum'] for tm in ('home', 'away') for i in x[tm]['evidence_event_ids']]
    refs += [i for x in analysis['dangerous_possessions'] for i in x['evidence_event_ids']]
    refs += [i for x in analysis['player_impact'] for i in x['evidence_event_ids']]
    for i in refs:
        if i not in by_id:
            fails.append(f'@{t}s evidence {i} does not exist')
        elif by_id[i].elapsed_seconds > t:
            fails.append(f'@{t}s evidence {i} is from the future')
    return fails