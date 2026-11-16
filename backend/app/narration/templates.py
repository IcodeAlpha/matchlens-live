"""Narration templates (English, Spanish, Swahili; fan and analyst styles).

Deterministic, offline, free. The Spanish and Swahili strings were written
without a native-speaker review: have a fluent speaker check them before this is
shown to real users. Numbers are always passed in, never invented here.
"""
LANGS = ('en', 'es', 'sw')
STYLES = ('fan', 'analyst')

OUTCOME = {
    'en': {'saved': 'saved by the keeper', 'blocked': 'blocked', 'off_target': 'off target'},
    'es': {'saved': 'parada del portero', 'blocked': 'bloqueado', 'off_target': 'fuera'},
    'sw': {'saved': 'kipa ameokoa', 'blocked': 'shuti limezuiwa', 'off_target': 'shuti nje'},
}

TEMPLATES = {
    'en': {
        'fan': {
            'goal': "GOAL! {who} ({club}) scores on {m}'. It's {h}-{a}.",
            'red_card': "RED CARD on {m}': {who} ({club}) is sent off.",
            'big_chance': "Big chance on {m}': {who} ({club}), {outcome} (xG {xg}).",
        },
        'analyst': {
            'goal': "{m}' GOAL | {who} | {club} | {h}-{a} | xG {xg}",
            'red_card': "{m}' RED CARD | {who} | {club}",
            'big_chance': "{m}' BIG CHANCE | {who} | {club} | {outcome} | xG {xg}",
        },
    },
    'es': {
        'fan': {
            'goal': "¡GOL! {who} ({club}) marca en el minuto {m}. Es {h}-{a}.",
            'red_card': "Tarjeta roja en el minuto {m}: {who} ({club}) es expulsado.",
            'big_chance': "Ocasión clarísima en el minuto {m}: {who} ({club}), {outcome} (xG {xg}).",
        },
        'analyst': {
            'goal': "{m}' GOL | {who} | {club} | {h}-{a} | xG {xg}",
            'red_card': "{m}' TARJETA ROJA | {who} | {club}",
            'big_chance': "{m}' OCASIÓN CLARA | {who} | {club} | {outcome} | xG {xg}",
        },
    },
    'sw': {
        'fan': {
            'goal': "GOLI! {who} ({club}) afunga dakika ya {m}. Ni {h}-{a}.",
            'red_card': "Kadi nyekundu dakika ya {m}: {who} ({club}) amefukuzwa uwanjani.",
            'big_chance': "Nafasi kubwa dakika ya {m}: {who} ({club}), {outcome} (xG {xg}).",
        },
        'analyst': {
            'goal': "{m}' GOLI | {who} | {club} | {h}-{a} | xG {xg}",
            'red_card': "{m}' KADI NYEKUNDU | {who} | {club}",
            'big_chance': "{m}' NAFASI KUBWA | {who} | {club} | {outcome} | xG {xg}",
        },
    },
}


# Which numbers each (style, kind) text must contain, in any order, and no others.
def expected_numbers(style: str, kind: str, m: int, h: int, a: int, xg: float | None) -> list[str]:
    if kind == 'goal':
        nums = [str(m), str(h), str(a)] + ([f'{xg:.2f}'] if style == 'analyst' else [])
    elif kind == 'big_chance':
        nums = [str(m), f'{xg:.2f}']
    else:
        nums = [str(m)]
    return sorted(nums)