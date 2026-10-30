"""Reproducible synthetic football match generator (90 minutes, no stoppage time).

All coordinates are attack-normalized: each possessing team attacks towards x=100.
Shot xG is a heuristic proxy, not a fitted expected-goals model.
"""
from __future__ import annotations

import math
import random
from collections import Counter

from app.schemas.events import EventType, MatchConfig, MatchEvent, MatchResult


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def opponent(team: str) -> str:
    return 'away' if team == 'home' else 'home'


def shot_xg(x: float, y: float, pressured: bool = False) -> float:
    """Illustrative shot quality, based on distance and angle; not calibrated."""
    distance = math.hypot(100 - x, (y - 50) * 1.1)
    quality = 0.48 * math.exp(-distance / 14.0)
    if pressured:
        quality *= 0.75
    return round(clamp(quality, 0.008, 0.48), 4)


class MatchSimulator:
    def __init__(self, config: MatchConfig):
        self.config = config
        self.rng = random.Random(config.seed)
        self.events: list[MatchEvent] = []
        self.clock = 0.0
        self.period = 1
        self.team = 'home'
        self.x = 50.0
        self.y = 50.0
        self.player = 9
        self.possession_id = 0
        self.home_score = 0
        self.away_score = 0

    def emit(self, kind: EventType, *, team: str | None = None,
             player: int | None = None, x: float | None = None,
             y: float | None = None, end_x: float | None = None,
             end_y: float | None = None, receiver: int | None = None,
             opponent_id: str | None = None, successful: bool | None = None,
             xg: float | None = None, outcome: str | None = None,
             restart: str | None = None) -> MatchEvent:
        actual_team = self.team if team is None else team
        t = int(self.clock)
        event = MatchEvent(
            event_id=f'event-{len(self.events) + 1:06d}',
            match_id=self.config.match_id,
            minute=t // 60, second=t % 60, elapsed_seconds=t,
            period=self.period, possession_id=self.possession_id,
            team_id=actual_team,
            player_id=f'{actual_team}-{player}' if player is not None else None,
            event_type=kind,
            x=round(self.x if x is None else x, 2),
            y=round(self.y if y is None else y, 2),
            end_x=round(end_x, 2) if end_x is not None else None,
            end_y=round(end_y, 2) if end_y is not None else None,
            receiver_id=f'{actual_team}-{receiver}' if receiver is not None else None,
            opponent_id=opponent_id, successful=successful,
            shot_xg=xg, shot_outcome=outcome,
            score_home=self.home_score, score_away=self.away_score,
            restart=restart,
        )
        self.events.append(event)
        return event

    def switch(self, new_team: str, x: float, y: float,
               restart: EventType | None = None, player: int | None = None) -> None:
        self.team = new_team
        self.possession_id += 1
        self.x, self.y = clamp(x), clamp(y)
        self.player = player if player is not None else self.rng.randint(2, 11)
        if restart is not None:
            self.emit(restart, player=self.player, restart=restart.value)

    def settings(self, team: str) -> tuple[str, float]:
        if team == 'home':
            return self.config.home_style, self.config.home_strength
        return self.config.away_style, self.config.away_strength

    def advance(self, low: float, high: float, end: float) -> bool:
        self.clock = min(end, self.clock + self.rng.uniform(low, high))
        return self.clock < end

    def shot(self, pressured: bool) -> None:
        team, player = self.team, self.player
        xg = shot_xg(self.x, self.y, pressured)
        outcome = ('goal' if self.rng.random() < xg else
                   self.rng.choices(['saved', 'blocked', 'off_target'],
                                    weights=[37, 28, 35], k=1)[0])
        self.emit(EventType.SHOT, player=player, xg=xg, outcome=outcome)
        if outcome == 'goal':
            if team == 'home':
                self.home_score += 1
            else:
                self.away_score += 1
            self.emit(EventType.GOAL, player=player)
            self.switch(opponent(team), 50, 50, EventType.KICK_OFF, 9)
        elif outcome == 'saved':
            self.emit(EventType.SAVE, team=opponent(team), player=1,
                      opponent_id=f'{team}-{player}', successful=True)
            if self.rng.random() < .18:
                self.switch(team, 94, self.rng.uniform(8, 92), EventType.CORNER)
            else:
                self.switch(opponent(team), 10, self.rng.uniform(30, 70), EventType.GOAL_KICK, 1)
        elif outcome == 'blocked':
            if self.rng.random() < .45:
                self.switch(team, 94, self.rng.uniform(8, 92), EventType.CORNER)
            else:
                defender = self.rng.randint(2, 11)
                self.switch(opponent(team), 100 - self.x, 100 - self.y, player=defender)
                self.emit(EventType.RECOVERY, player=defender)
        else:
            self.switch(opponent(team), 8, self.rng.uniform(30, 70), EventType.GOAL_KICK, 1)

    def action(self) -> None:
        r = self.rng
        team = self.team
        style, strength = self.settings(team)
        other_style, other_strength = self.settings(opponent(team))
        pressure_chance = (.14 if other_style == 'pressing' else .07) + .05 * other_strength
        pressured = r.random() < pressure_chance
        if pressured:
            self.emit(EventType.PRESSURE, team=opponent(team), player=r.randint(2, 11),
                      opponent_id=f'{team}-{self.player}')

        # Not every final-third entry becomes a shot. Wide and distant attempts
        # are less likely; this decision is separate from shot conversion.
        centrality = 1 - abs(self.y - 50) / 50
        if self.x >= 75:
            shot_chance = clamp(.045 + (self.x - 75) * .003, .045, .12)
            shot_chance *= (.55 + .45 * centrality)
            if pressured:
                shot_chance *= .65
            if r.random() < shot_chance:
                self.shot(pressured)
                return

        # A direct defensive win is a tackle, not an interception (which
        # requires an attempted pass). A recovery starts the new possession.
        tackle_chance = (.045 if pressured else .008) * (0.7 + other_strength)
        if r.random() < tackle_chance:
            defender = r.randint(2, 11)
            self.emit(EventType.TACKLE, team=opponent(team), player=defender,
                      opponent_id=f'{team}-{self.player}', successful=True)
            self.switch(opponent(team), 100 - self.x, 100 - self.y, player=defender)
            self.emit(EventType.RECOVERY, player=defender)
            return

        do_pass = r.random() < (.78 if style == 'possession' else .65 if style == 'direct' else .72)
        if do_pass:
            dx = r.uniform(-14, 23 if style == 'direct' else 17)
            dy = r.uniform(-18, 18)
            nx, ny = clamp(self.x + dx), clamp(self.y + dy)
            length = math.hypot(nx - self.x, ny - self.y)
            success_probability = clamp(
                .97 - .005 * length + .045 * (strength - .5)
                - (.07 if pressured else 0), .55, .98
            )
            success = r.random() < success_probability
            receiver = r.choice([p for p in range(2, 12) if p != self.player])
            self.emit(EventType.PASS, player=self.player, end_x=nx, end_y=ny,
                      receiver=receiver, successful=success)
            if success:
                self.x, self.y, self.player = nx, ny, receiver
            else:
                # A failed pass is not always an interception: it may go out.
                if r.random() < .48:
                    defender = r.randint(2, 11)
                    self.emit(EventType.INTERCEPTION, team=opponent(team),
                              player=defender, x=nx, y=ny,
                              opponent_id=f'{team}-{self.player}', successful=True)
                    self.switch(opponent(team), 100 - nx, 100 - ny, player=defender)
                    self.emit(EventType.RECOVERY, player=defender)
                else:
                    self.switch(opponent(team), 100 - nx, 100 - ny,
                                EventType.THROW_IN)
        else:
            nx = clamp(self.x + r.uniform(-6, 12))
            ny = clamp(self.y + r.uniform(-12, 12))
            success_probability = clamp(
                .96 + .035 * (strength - .5) - (.10 if pressured else 0), .60, .97
            )
            success = r.random() < success_probability
            self.emit(EventType.CARRY, player=self.player, end_x=nx, end_y=ny,
                      successful=success)
            if success:
                self.x, self.y = nx, ny
            else:
                defender = r.randint(2, 11)
                self.emit(EventType.TACKLE, team=opponent(team), player=defender,
                          x=nx, y=ny, opponent_id=f'{team}-{self.player}',
                          successful=True)
                self.switch(opponent(team), 100 - nx, 100 - ny, player=defender)
                self.emit(EventType.RECOVERY, player=defender)

    def simulate(self) -> MatchResult:
        self.switch('home', 50, 50, EventType.KICK_OFF, 9)
        for period, start, end in ((1, 0.0, 2700.0), (2, 2700.0, 5400.0)):
            self.period = period
            self.clock = start
            if period == 2:
                self.switch('away', 50, 50, EventType.KICK_OFF, 9)
            while self.clock < end:
                if not self.advance(2.2, 5.8, end):
                    break
                self.action()
            self.clock = end
            self.emit(EventType.HALF_TIME if period == 1 else EventType.FULL_TIME,
                      team=None, player=None)
        return MatchResult(match_id=self.config.match_id, config=self.config,
                           events=self.events, summary=self.summary(),
                           validation=self.validate())

    def summary(self) -> dict:
        shots = [e for e in self.events if e.event_type == EventType.SHOT]
        def team_summary(team: str) -> dict:
            subset = [e for e in self.events if e.team_id == team]
            team_shots = [e for e in shots if e.team_id == team]
            return {
                'goals': self.home_score if team == 'home' else self.away_score,
                'shots': len(team_shots),
                'xg_proxy': round(sum(e.shot_xg or 0 for e in team_shots), 3),
                'passes': sum(e.event_type == EventType.PASS for e in subset),
                'completed_passes': sum(e.event_type == EventType.PASS and e.successful is True for e in subset),
                'tackles': sum(e.event_type == EventType.TACKLE for e in subset),
                'interceptions': sum(e.event_type == EventType.INTERCEPTION for e in subset),
                'pressures': sum(e.event_type == EventType.PRESSURE for e in subset),
                'saves': sum(e.event_type == EventType.SAVE for e in subset),
            }
        return {'match_id': self.config.match_id, 'synthetic': True,
                'duration_seconds': 5400, 'total_events': len(self.events),
                'score': {'home': self.home_score, 'away': self.away_score},
                'home': team_summary('home'), 'away': team_summary('away'),
                'event_types': dict(Counter(e.event_type.value for e in self.events))}

    def validate(self) -> dict:
        errors = []
        last_time = -1
        h = a = 0
        previous_shot = None
        ids = set()
        for e in self.events:
            if e.event_id in ids:
                errors.append(f'duplicate event id: {e.event_id}')
            ids.add(e.event_id)
            if e.elapsed_seconds < last_time:
                errors.append(f'time reversed at {e.event_id}')
            last_time = e.elapsed_seconds
            if e.minute * 60 + e.second != e.elapsed_seconds:
                errors.append(f'clock mismatch at {e.event_id}')
            if e.event_type == EventType.SHOT:
                previous_shot = e
            elif e.event_type == EventType.GOAL:
                if (not previous_shot or previous_shot.shot_outcome != 'goal'
                        or previous_shot.team_id != e.team_id):
                    errors.append(f'goal without matching shot at {e.event_id}')
                if e.team_id == 'home':
                    h += 1
                else:
                    a += 1
                previous_shot = None
            elif e.event_type != EventType.PRESSURE:
                previous_shot = None
            if (e.score_home, e.score_away) != (h, a):
                errors.append(f'score mismatch at {e.event_id}')
        if not self.events or self.events[-1].event_type != EventType.FULL_TIME:
            errors.append('missing full time')
        if (h, a) != (self.home_score, self.away_score):
            errors.append('final score mismatch')
        return {'valid': not errors, 'errors': errors, 'events_checked': len(self.events)}


def generate_match(config: MatchConfig | None = None) -> MatchResult:
    return MatchSimulator(config or MatchConfig()).simulate()


def generate_match_events(match_id: str = 'match-001', count: int = 1000,
                          seed: int = 42) -> list[MatchEvent]:
    return generate_match(MatchConfig(match_id=match_id, seed=seed)).events[:count]
