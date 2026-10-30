from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field, model_validator

class EventType(str, Enum):
    PASS='pass'; CARRY='carry'; SHOT='shot'; GOAL='goal'; TACKLE='tackle'; PRESSURE='pressure'; RECOVERY='recovery'; INTERCEPTION='interception'; SAVE='save'; FOUL='foul'; CORNER='corner'; THROW_IN='throw_in'; GOAL_KICK='goal_kick'; KICK_OFF='kick_off'; HALF_TIME='half_time'; FULL_TIME='full_time'

class MatchEvent(BaseModel):
    event_id: str
    match_id: str
    minute: int = Field(ge=0, le=120)
    second: int = Field(ge=0, le=59)
    elapsed_seconds: int = Field(ge=0)
    period: int = Field(ge=1, le=2)
    possession_id: int = Field(ge=0)
    team_id: Literal['home','away'] | None = None
    player_id: str | None = None
    event_type: EventType
    x: float | None = Field(default=None, ge=0, le=100)
    y: float | None = Field(default=None, ge=0, le=100)
    end_x: float | None = Field(default=None, ge=0, le=100)
    end_y: float | None = Field(default=None, ge=0, le=100)
    receiver_id: str | None = None
    opponent_id: str | None = None
    successful: bool | None = None
    shot_xg: float | None = Field(default=None, ge=0, le=1)
    shot_outcome: Literal['goal','saved','blocked','off_target'] | None = None
    score_home: int = Field(ge=0)
    score_away: int = Field(ge=0)
    restart: str | None = None
    synthetic: Literal[True] = True

    @model_validator(mode='after')
    def consistency(self):
        if self.event_type == EventType.SHOT and (self.shot_xg is None or self.shot_outcome is None):
            raise ValueError('Shots require xG and outcome')
        if self.event_type in (EventType.PASS, EventType.CARRY):
            if self.end_x is None or self.end_y is None or self.successful is None:
                raise ValueError('Passes and carries require endpoint and success')
        if self.event_type == EventType.GOAL and self.team_id is None:
            raise ValueError('Goal must have a team')
        return self

class MatchConfig(BaseModel):
    match_id: str = 'match-001'
    seed: int = 42
    home_style: Literal['balanced','possession','direct','pressing'] = 'balanced'
    away_style: Literal['balanced','possession','direct','pressing'] = 'balanced'
    home_strength: float = Field(default=0.60, ge=0, le=1)
    away_strength: float = Field(default=0.60, ge=0, le=1)

class MatchResult(BaseModel):
    match_id: str
    config: MatchConfig
    events: list[MatchEvent]
    summary: dict
    validation: dict
