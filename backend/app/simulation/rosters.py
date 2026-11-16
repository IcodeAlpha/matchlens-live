"""Fictional squads for synthetic matches.

Every club and player name here is invented. Any resemblance to a real club or
person is coincidental, and tests/test_showcase_export.py checks the club names
against a blocklist of real clubs. Do not add real names or logos.
"""
from __future__ import annotations

import random

CLUBS = [
    ('Northgate FC', 'NOR', '#2f6fdd'), ('Harbourside Athletic', 'HAR', '#e8a317'),
    ('Kestrel Rovers', 'KES', '#c0392b'), ('Ironbridge Town', 'IRO', '#7f8c8d'),
    ('Westmoor Albion', 'WES', '#27ae60'), ('Eastfield Wanderers', 'EAS', '#8e44ad'),
    ('Lakeside Rangers', 'LAK', '#16a5a5'), ('Stonebridge United', 'STO', '#d35400'),
    ('Copperfield City', 'COP', '#b5651d'), ('Ashgrove FC', 'ASH', '#34495e'),
    ('Silverlake Athletic', 'SIL', '#5dade2'), ('Redcliff Rovers', 'RED', '#e74c3c'),
]
FIRST = ['Tomas', 'Idris', 'Kwame', 'Mateo', 'Luca', 'Hiro', 'Samir', 'Anders', 'Rafael',
         'Dmitri', 'Joao', 'Kofi', 'Emeka', 'Lars', 'Mehmet', 'Pablo', 'Yusuf', 'Andre',
         'Nikola', 'Omar', 'Felix', 'Jamal', 'Tariq', 'Bruno', 'Marek', 'Wanjiru', 'Kiptoo',
         'Sven', 'Ravi', 'Diego', 'Elias', 'Matias', 'Chidi', 'Ismael', 'Viktor', 'Hassan',
         'Julian', 'Santiago', 'Oskar', 'Baraka']
START = ['Mar', 'Ken', 'Dal', 'Vor', 'Tam', 'Ols', 'Bren', 'Zan', 'Hol', 'Kir', 'Nar', 'Pel',
         'Sav', 'Tor', 'Wen', 'Yar', 'Ber', 'Cas', 'Dru', 'Fen', 'Gal', 'Jor', 'Lem', 'Mol']
MID = ['a', 'e', 'i', 'o', 'an', 'el', 'or', 'ik', 'ar', 'on']
END = ['son', 'dez', 'ov', 'ski', 'ton', 'berg', 'ford', 'ani', 'ura', 'kis', 'man', 'sen',
       'ek', 'ido', 'wa', 'ley']
POSITIONS = {1: 'GK', 2: 'RB', 3: 'LB', 4: 'CB', 5: 'CB', 6: 'DM', 7: 'RW',
             8: 'CM', 9: 'ST', 10: 'AM', 11: 'LW'}


def _squad(rng: random.Random, side: str, club: tuple[str, str, str]) -> dict:
    used: set[str] = set()
    players = []
    for number in range(1, 12):
        while True:
            name = f"{rng.choice(FIRST)} {rng.choice(START)}{rng.choice(MID)}{rng.choice(END)}"
            if name not in used:
                used.add(name)
                break
        players.append({'number': number, 'player_id': f'{side}-{number}',
                        'name': name, 'position': POSITIONS[number]})
    return {'side': side, 'name': club[0], 'short': club[1], 'color': club[2],
            'players': players}


def build_rosters(seed: int) -> dict:
    """Deterministic: the same seed always yields the same two squads."""
    rng = random.Random(f'roster-{seed}')
    home, away = rng.sample(CLUBS, 2)
    return {'home': _squad(rng, 'home', home), 'away': _squad(rng, 'away', away)}