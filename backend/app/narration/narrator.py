from __future__ import annotations

from app.narration.templates import LANGS, OUTCOME, STYLES, TEMPLATES


def _names(teams: dict) -> tuple[dict, dict]:
    players = {p['player_id']: p['name'] for side in teams.values() for p in side['players']}
    clubs = {side['side']: side['name'] for side in teams.values()}
    return players, clubs


def narrate(moment: dict, teams: dict, lang: str, style: str) -> str:
    """Render one key moment. Raises KeyError for an unknown language, style or kind."""
    if lang not in LANGS or style not in STYLES:
        raise KeyError(f'unsupported language/style: {lang}/{style}')
    players, clubs = _names(teams)
    xg = moment.get('xg')
    return TEMPLATES[lang][style][moment['kind']].format(
        m=moment['elapsed_seconds'] // 60,
        who=players.get(moment['player_id'], moment['player_id']),
        club=clubs.get(moment['team_id'], ''),
        h=moment['score_home'], a=moment['score_away'],
        xg=f'{xg:.2f}' if xg is not None else '',
        outcome=OUTCOME[lang].get(moment.get('outcome') or '', ''),
    )


def narrate_all(moment: dict, teams: dict) -> dict:
    return {s: {l: narrate(moment, teams, l, s) for l in LANGS} for s in STYLES}