"""Evidence-linked tactical analysis of synthetic MatchLens events.

Coordinates are attack-normalized for each team. These are descriptive
heuristics, not calibrated scouting metrics or causal inference.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from app.schemas.events import MatchEvent, EventType

TEAMS = ("home", "away")
ACTIONS = {EventType.PASS, EventType.CARRY}


def _xt_gain(event: MatchEvent) -> float | None:
    if event.event_type not in ACTIONS or event.successful is not True:
        return None
    if None in (event.x, event.y, event.end_x, event.end_y):
        return None
    try:
        from app.analytics.xt import calculate_xt_gain
        value = calculate_xt_gain(event.x, event.y, event.end_x, event.end_y)
        return float(value) if value is not None else None
    except (FileNotFoundError, ImportError, ValueError, OSError):
        return None


def _ref(events: Iterable[MatchEvent], limit: int = 12) -> list[str]:
    return list(dict.fromkeys(e.event_id for e in events))[:limit]


def _insight(kind: str, team: str, headline: str, explanation: str,
             events: list[MatchEvent], metrics: dict, confidence: str = "descriptive") -> dict:
    return {
        "type": kind, "team_id": team, "headline": headline,
        "explanation": explanation, "metrics": metrics,
        "evidence_event_ids": _ref(events), "evidence_count": len(events),
        "confidence": confidence,
    }


def analyze_match(events: list[MatchEvent], *, window_seconds: int = 300,
                  as_of_seconds: int | None = None) -> dict:
    """Analyze a full match or an event prefix (live playback).

    as_of_seconds makes the analysis causally safe for live broadcasts: future
    events are excluded. Never infer pressing *caused* a turnover from proximity.
    """
    if window_seconds <= 0:
        raise ValueError("window_seconds must be positive")
    selected = sorted(
        (e for e in events if as_of_seconds is None or e.elapsed_seconds <= as_of_seconds),
        key=lambda e: (e.elapsed_seconds, e.event_id),
    )
    match_id = selected[0].match_id if selected else (events[0].match_id if events else None)
    if not selected:
        return {"match_id": match_id, "synthetic": True, "as_of_seconds": as_of_seconds,
                "window_seconds": window_seconds, "insights": [], "momentum": [],
                "dangerous_possessions": [], "player_impact": [], "team_metrics": {}}

    end_time = selected[-1].elapsed_seconds if as_of_seconds is None else as_of_seconds
    possessions: dict[int, list[MatchEvent]] = defaultdict(list)
    players: dict[str, dict] = {}
    team_metrics = {
        t: {"shots": 0, "xg_proxy": 0.0, "progressive_actions": 0,
            "final_third_entries": 0, "pressures": 0, "interceptions": 0,
            "tackles": 0, "successful_actions": 0, "xt_gain": 0.0,
            "xt_available": False}
        for t in TEAMS
    }
    attack_events: dict[str, list[MatchEvent]] = {t: [] for t in TEAMS}
    press_events: dict[str, list[MatchEvent]] = {t: [] for t in TEAMS}
    for e in selected:
        # Pressure is a defensive event carrying the opponent's possession ID.
        if e.event_type not in (EventType.PRESSURE, EventType.TACKLE, EventType.INTERCEPTION):
            possessions[e.possession_id].append(e)
        team = e.team_id
        if team not in TEAMS:
            continue
        m = team_metrics[team]
        if e.event_type == EventType.PRESSURE:
            m["pressures"] += 1
            press_events[team].append(e)
        elif e.event_type == EventType.INTERCEPTION:
            m["interceptions"] += 1
        elif e.event_type == EventType.TACKLE:
            m["tackles"] += 1
        elif e.event_type == EventType.SHOT:
            m["shots"] += 1
            m["xg_proxy"] += e.shot_xg or 0
            attack_events[team].append(e)
        if e.event_type in ACTIONS and e.successful is True:
            m["successful_actions"] += 1
            if e.x is not None and e.end_x is not None:
                if e.end_x - e.x >= 10:
                    m["progressive_actions"] += 1
                    attack_events[team].append(e)
                if e.x < 66.67 <= e.end_x:
                    m["final_third_entries"] += 1
                    attack_events[team].append(e)
            gain = _xt_gain(e)
            if gain is not None:
                m["xt_available"] = True
                m["xt_gain"] += gain
        if e.player_id and e.event_type in (ACTIONS | {EventType.SHOT, EventType.TACKLE, EventType.INTERCEPTION}):
            p = players.setdefault(e.player_id, {"player_id": e.player_id,
                "team_id": team, "progressive_actions": 0, "shots": 0,
                "xg_proxy": 0.0, "defensive_actions": 0, "xt_gain": 0.0,
                "xt_available": False, "evidence": []})
            qualifies = False
            if e.event_type in ACTIONS and e.successful is True:
                if e.x is not None and e.end_x is not None and e.end_x - e.x >= 10:
                    p["progressive_actions"] += 1
                    qualifies = True
                gain = _xt_gain(e)
                if gain is not None:
                    p["xt_available"] = True
                    p["xt_gain"] += gain
            elif e.event_type == EventType.SHOT:
                p["shots"] += 1
                p["xg_proxy"] += e.shot_xg or 0
                qualifies = True
            elif e.event_type in (EventType.TACKLE, EventType.INTERCEPTION):
                p["defensive_actions"] += 1
                qualifies = True
            if qualifies:
                p["evidence"].append(e)

    # A possession is attributed to the attacking side, not the defending side
    # that might have registered a pressure within it.
    dangerous = []
    for pid, group in possessions.items():
        attackers = [e for e in group if e.team_id in TEAMS and e.event_type in
                     (EventType.PASS, EventType.CARRY, EventType.SHOT, EventType.GOAL)]
        if not attackers:
            continue
        team = attackers[0].team_id
        group = [e for e in attackers if e.team_id == team]
        shots = [e for e in group if e.event_type == EventType.SHOT]
        progress = [e for e in group if e.event_type in ACTIONS and e.successful is True
                    and e.x is not None and e.end_x is not None and e.end_x - e.x >= 10]
        entries = [e for e in group if e.event_type in ACTIONS and e.successful is True
                   and e.x is not None and e.end_x is not None and e.x < 66.67 <= e.end_x]
        xg = sum(e.shot_xg or 0 for e in shots)
        if not (shots or len(progress) >= 2 or entries):
            continue
        score = round(xg + .025 * len(progress) + .04 * len(entries), 4)
        dangerous.append({"possession_id": pid, "team_id": team,
                          "start_seconds": group[0].elapsed_seconds,
                          "end_seconds": group[-1].elapsed_seconds,
                          "shots": len(shots), "xg_proxy": round(xg, 4),
                          "progressive_actions": len(progress),
                          "final_third_entries": len(entries),
                          "danger_score_proxy": score,
                          "evidence_event_ids": _ref(shots + progress + entries)})
    dangerous.sort(key=lambda p: (-p["danger_score_proxy"], p["possession_id"]))

    momentum = []
    for stop in range(window_seconds, end_time + window_seconds, window_seconds):
        stop = min(stop, end_time)
        start = max(0, stop - window_seconds)
        # Disjoint bins, including time zero in the first bin.
        bucket = [e for e in selected if start <= e.elapsed_seconds <= stop and
                  (start == 0 or e.elapsed_seconds > start)]
        row = {"start_seconds": start, "end_seconds": stop}
        for team in TEAMS:
            shots = [e for e in bucket if e.team_id == team and e.event_type == EventType.SHOT]
            progresses = [e for e in bucket if e.team_id == team and e.event_type in ACTIONS
                          and e.successful is True and e.x is not None and e.end_x is not None
                          and e.end_x - e.x >= 10]
            xg = sum(e.shot_xg or 0 for e in shots)
            # A transparent indicator, not a measured win probability.
            score = round(xg + .025 * len(progresses), 4)
            row[team] = {"shots": len(shots), "xg_proxy": round(xg, 4),
                         "progressive_actions": len(progresses),
                         "attacking_momentum_proxy": score,
                         "evidence_event_ids": _ref(shots + progresses)}
        row["leader"] = ("level" if row["home"]["attacking_momentum_proxy"] ==
                         row["away"]["attacking_momentum_proxy"] else
                         max(TEAMS, key=lambda t: row[t]["attacking_momentum_proxy"]))
        momentum.append(row)
        if stop == end_time:
            break

    insights = []
    for t in TEAMS:
        top = [p for p in dangerous if p["team_id"] == t][:3]
        if top:
            ids = {eid for p in top for eid in p["evidence_event_ids"]}
            evs = [e for e in selected if e.event_id in ids]
            insights.append(_insight("dangerous_possessions", t,
                f"{t.title()} generated {len(top)} notable attacking sequences",
                "Sequences identified from shots, progression and final-third entries; danger score is heuristic.",
                evs, {"top_possession_ids": [p["possession_id"] for p in top],
                      "combined_xg_proxy": round(sum(p["xg_proxy"] for p in top), 3)}))
        recent = [e for e in press_events[t] if e.elapsed_seconds > end_time - 900]
        if recent:
            insights.append(_insight("pressing_activity", t,
                f"{t.title()} registered {len(recent)} pressures in the last 15 minutes",
                "Pressure counts describe activity, not confirmed successful pressing or causation.",
                recent, {"pressures": len(recent), "window_seconds": 900}))
    if momentum:
        latest = momentum[-1]
        if latest["leader"] in TEAMS:
            t = latest["leader"]
            ids = set(latest[t]["evidence_event_ids"])
            evs = [e for e in selected if e.event_id in ids]
            if evs:
                insights.append(_insight("recent_momentum", t,
                    f"{t.title()} led the latest attacking-momentum window",
                    "Based on shot xG proxy and progressive-action count, not ball possession or win probability.",
                    evs, {"window_start": latest["start_seconds"],
                          "window_end": latest["end_seconds"],
                          "momentum_proxy": latest[t]["attacking_momentum_proxy"]}))

    impact = []
    for p in players.values():
        score = p["progressive_actions"] + 2 * p["shots"] + p["defensive_actions"]
        impact.append({k: v for k, v in p.items() if k != "evidence"} |
                      {"xg_proxy": round(p["xg_proxy"], 4),
                       "xt_gain": round(p["xt_gain"], 5) if p["xt_available"] else None,
                       "impact_score_proxy": score,
                       "evidence_event_ids": _ref(p["evidence"])})
    impact.sort(key=lambda p: (-p["impact_score_proxy"], p["player_id"]))
    for t in TEAMS:
        team_metrics[t]["xg_proxy"] = round(team_metrics[t]["xg_proxy"], 4)
        team_metrics[t]["xt_gain"] = (round(team_metrics[t]["xt_gain"], 5)
                                      if team_metrics[t]["xt_available"] else None)
    return {"match_id": match_id, "synthetic": True, "as_of_seconds": end_time,
            "window_seconds": window_seconds, "team_metrics": team_metrics,
            "insights": insights, "momentum": momentum,
            "dangerous_possessions": dangerous[:20], "player_impact": impact[:20],
            "methodology": {"xg": "heuristic proxy from simulator",
                            "momentum": "xg_proxy + 0.025 * progressive actions per window",
                            "progressive_action": "successful pass/carry advancing >= 10 normalized x units",
                            "pressing": "pressure event counts only",
                            "xt": "optional grid-based xT; unavailable if model cannot be loaded"}}
