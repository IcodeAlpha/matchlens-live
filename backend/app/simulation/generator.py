"""Reproducible synthetic football match generator (90 minutes, no stoppage time).

All coordinates are attack-normalized: each possessing team attacks towards x=100.
Shot xG is a heuristic proxy, not a fitted expected-goals model.

v2 adds fouls, yellow/red cards (sent-off players stop acting and weaken their
team), free kicks, corner deliveries, dead time at stoppages, role-aware players
(strikers shoot, defenders tackle) and recalibrated rates. The same seed always
gives the same match, but v2 seeds give different matches to v1.

Rates were tuned to land inside broad, author-chosen top-flight ranges (see
scripts/realism_report.py). They are NOT fitted to any real dataset.
"""
from __future__ import annotations

import math
import random
from collections import Counter

from app.schemas.events import EventType, MatchConfig, MatchEvent, MatchResult

PASS_BASE = .93   # base pass success before distance, pressure and team strength

# shirt number -> (typical x in own attack-normalized frame, involvement weight)
ROLES = {2: (32, 1.0), 3: (32, 1.0), 4: (28, 1.0), 5: (28, 1.0), 6: (45, 1.1),
         7: (72, 1.0), 8: (55, 1.2), 9: (80, 1.0), 10: (68, 1.1), 11: (72, 1.0)}

# how often each role wins the ball, fouls or recovers (strikers press more than they tackle)
DEF_FACTOR = {2: 1.2, 3: 1.2, 4: 1.3, 5: 1.3, 6: 1.5, 7: .6, 8: 1.0, 9: .25, 10: .5, 11: .6}


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
        self.sent_off: dict[str, set[int]] = {'home': set(), 'away': set()}
        self.yellows: Counter = Counter()
        self.delay = 0.0          # dead time (s) added before the next action
        self.corner_depth = 0

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

    # -- players ---------------------------------------------------------
    def pick(self, team: str, exclude: int | None = None,
             at_x: float | None = None, defensive: bool = False) -> int:
        """An outfield player (2-11) still on the pitch, weighted by how likely
        his role is to be involved at pitch position at_x (in that team's own
        attack-normalized frame). at_x=None picks uniformly."""
        pool = [n for n in range(2, 12)
                if n not in self.sent_off[team] and n != exclude]
        if not pool:
            return 2
        if at_x is None:
            return self.rng.choice(pool)
        weights = [(.03 + ROLES[n][1] * math.exp(-((at_x - ROLES[n][0]) / 22) ** 2))
                   * (DEF_FACTOR[n] if defensive else 1.0) for n in pool]
        return self.rng.choices(pool, weights=weights, k=1)[0]

    def taker(self, team: str, preferred: int = 9) -> int:
        return preferred if preferred not in self.sent_off[team] else self.pick(team)

    def switch(self, new_team: str, x: float, y: float,
               restart: EventType | None = None, player: int | None = None) -> None:
        self.team = new_team
        self.possession_id += 1
        self.x, self.y = clamp(x), clamp(y)
        self.player = player if player is not None else self.pick(new_team, at_x=self.x)
        if restart is not None:
            self.emit(restart, player=self.player, restart=restart.value)

    def settings(self, team: str) -> tuple[str, float]:
        if team == 'home':
            style, strength = self.config.home_style, self.config.home_strength
        else:
            style, strength = self.config.away_style, self.config.away_strength
        # Playing with ten (or fewer) men weakens a team.
        return style, max(0.0, strength - .08 * len(self.sent_off[team]))

    def advance(self, low: float, high: float, end: float) -> bool:
        self.clock = min(end, self.clock + self.rng.uniform(low, high) + self.delay)
        self.delay = 0.0
        return self.clock < end

    # -- set pieces ------------------------------------------------------
    def corner(self, team: str) -> None:
        self.switch(team, 99.5, self.rng.choice([2.0, 98.0]), EventType.CORNER)
        self.delay += 12
        taker = self.player
        tx, ty = self.rng.uniform(86, 96), self.rng.uniform(28, 72)
        success = self.rng.random() < .32
        receiver = self.pick(team, exclude=taker, at_x=tx)
        self.emit(EventType.PASS, player=taker, end_x=tx, end_y=ty,
                  receiver=receiver, successful=success, restart='corner')
        if success:
            self.x, self.y, self.player = tx, ty, receiver
            if self.corner_depth < 2 and self.rng.random() < .55:
                self.corner_depth += 1
                self.shot(False, xg_scale=.55)      # headers convert less often
                self.corner_depth -= 1
        else:
            defender = self.pick(opponent(team), at_x=100 - tx, defensive=True)
            self.switch(opponent(team), 100 - tx, 100 - ty, player=defender)
            self.emit(EventType.RECOVERY, player=defender)

    def foul(self) -> None:
        team, defending = self.team, opponent(self.team)
        fouler = self.pick(defending, at_x=100 - self.x, defensive=True)
        self.emit(EventType.FOUL, team=defending, player=fouler,
                  opponent_id=f'{team}-{self.player}')
        roll = self.rng.random()
        booked = self.yellows[(defending, fouler)] > 0
        yellow_p = .145 * (.45 if booked else 1.0)        # booked players take care
        card = 'red' if roll < .0015 else 'yellow' if roll < .0015 + yellow_p else None
        if card == 'yellow':
            self.yellows[(defending, fouler)] += 1
            self.emit(EventType.YELLOW_CARD, team=defending, player=fouler)
            if self.yellows[(defending, fouler)] >= 2:       # second yellow
                card = 'red'
            else:
                card = None
        if card == 'red':
            self.emit(EventType.RED_CARD, team=defending, player=fouler)
            self.sent_off[defending].add(fouler)
            self.delay += 20
        self.delay += self.rng.uniform(8, 18)
        self.emit(EventType.FREE_KICK, player=self.player, restart='free_kick')
        if self.x >= 76 and abs(self.y - 50) <= 24 and self.rng.random() < .20:
            self.shot(False, xg_scale=.7)                     # direct free kick

    # -- shots -----------------------------------------------------------
    def shot(self, pressured: bool, xg_scale: float = 1.0) -> None:
        team, player = self.team, self.player
        xg = round(shot_xg(self.x, self.y, pressured) * xg_scale, 4)
        outcome = ('goal' if self.rng.random() < xg else
                   self.rng.choices(['saved', 'blocked', 'off_target'],
                                    weights=[28, 30, 42], k=1)[0])
        self.emit(EventType.SHOT, player=player, xg=xg, outcome=outcome)
        if outcome == 'goal':
            if team == 'home':
                self.home_score += 1
            else:
                self.away_score += 1
            self.emit(EventType.GOAL, player=player)
            self.delay += 35
            self.switch(opponent(team), 50, 50, EventType.KICK_OFF,
                        self.taker(opponent(team)))
        elif outcome == 'saved':
            self.emit(EventType.SAVE, team=opponent(team), player=1,
                      opponent_id=f'{team}-{player}', successful=True)
            if self.rng.random() < .25:
                self.corner(team)
            else:
                self.delay += 6
                self.switch(opponent(team), 10, self.rng.uniform(30, 70), EventType.GOAL_KICK, 1)
        elif outcome == 'blocked':
            if self.rng.random() < .55:
                self.corner(team)
            else:
                defender = self.pick(opponent(team), at_x=100 - self.x, defensive=True)
                self.switch(opponent(team), 100 - self.x, 100 - self.y, player=defender)
                self.emit(EventType.RECOVERY, player=defender)
        else:
            self.delay += 6
            self.switch(opponent(team), 8, self.rng.uniform(30, 70), EventType.GOAL_KICK, 1)

    # -- open play -------------------------------------------------------
    def action(self) -> None:
        r = self.rng
        team = self.team
        style, strength = self.settings(team)
        other_style, other_strength = self.settings(opponent(team))
        pressure_chance = (.19 if other_style == 'pressing' else .115) + .05 * other_strength
        pressured = r.random() < pressure_chance
        if pressured:
            self.emit(EventType.PRESSURE, team=opponent(team),
                      player=self.pick(opponent(team), at_x=100 - self.x),
                      opponent_id=f'{team}-{self.player}')

        if r.random() < .013 + (.015 if pressured else 0):
            self.foul()
            return

        # Not every final-third entry becomes a shot. Wide and distant attempts
        # are less likely; this decision is separate from shot conversion.
        centrality = 1 - abs(self.y - 50) / 50
        if self.x >= 75:
            shot_chance = clamp(.052 + (self.x - 75) * .0033, .052, .13)
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
            defender = self.pick(opponent(team), at_x=100 - self.x, defensive=True)
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
                PASS_BASE - .0055 * length + .045 * (strength - .5)
                - (.08 if pressured else 0), .55, .98
            )
            success = r.random() < success_probability
            receiver = self.pick(team, exclude=self.player, at_x=nx)
            self.emit(EventType.PASS, player=self.player, end_x=nx, end_y=ny,
                      receiver=receiver, successful=success)
            if success:
                self.x, self.y, self.player = nx, ny, receiver
            else:
                roll = r.random()
                if nx >= 85 and r.random() < .28:
                    self.corner(team)                        # deflected behind
                elif roll < .20:
                    defender = self.pick(opponent(team), at_x=100 - nx, defensive=True)
                    self.emit(EventType.INTERCEPTION, team=opponent(team),
                              player=defender, x=nx, y=ny,
                              opponent_id=f'{team}-{self.player}', successful=True)
                    self.switch(opponent(team), 100 - nx, 100 - ny, player=defender)
                    self.emit(EventType.RECOVERY, player=defender)
                elif roll < .50:                             # out of play
                    self.delay += 5
                    if nx >= 96:
                        self.switch(opponent(team), 8, r.uniform(30, 70), EventType.GOAL_KICK, 1)
                    else:
                        self.switch(opponent(team), 100 - nx, 100 - ny, EventType.THROW_IN)
                else:                                        # loose ball, no interception
                    defender = self.pick(opponent(team), at_x=100 - nx, defensive=True)
                    self.switch(opponent(team), 100 - nx, 100 - ny, player=defender)
                    self.emit(EventType.RECOVERY, player=defender)
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
                defender = self.pick(opponent(team), at_x=100 - nx, defensive=True)
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
            self.delay = 0.0
            if period == 2:
                self.switch('away', 50, 50, EventType.KICK_OFF, self.taker('away'))
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
                'fouls': sum(e.event_type == EventType.FOUL for e in subset),
                'corners': sum(e.event_type == EventType.CORNER for e in subset),
                'yellow_cards': sum(e.event_type == EventType.YELLOW_CARD for e in subset),
                'red_cards': sum(e.event_type == EventType.RED_CARD for e in subset),
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
        gone: dict[str, set[str]] = {'home': set(), 'away': set()}
        for e in self.events:
            if e.event_id in ids:
                errors.append(f'duplicate event id: {e.event_id}')
            ids.add(e.event_id)
            if e.elapsed_seconds < last_time:
                errors.append(f'time reversed at {e.event_id}')
            last_time = e.elapsed_seconds
            if e.minute * 60 + e.second != e.elapsed_seconds:
                errors.append(f'clock mismatch at {e.event_id}')
            if (e.team_id in gone and e.player_id in gone[e.team_id]
                    and e.event_type != EventType.RED_CARD):
                errors.append(f'sent-off player acted at {e.event_id}')
            if e.event_type == EventType.RED_CARD and e.team_id:
                gone[e.team_id].add(e.player_id)
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