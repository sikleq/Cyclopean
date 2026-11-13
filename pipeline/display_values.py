"""A value as the page prints it: sentinels ("no limit"), values re-encoded between builds (`reencoded`), metres
on one side (`metres_pair`), a sign the game flips (`sign_flip`), `display_raw`, `display_value` and `show`."""
from __future__ import annotations

import re

from .field_units import FRACTION, METRES, MPS, M_SPEED, SPEED, UNITS_PER_METER, _RAW_NUM, property_name, with_unit


# "no limit" / "none" written as a number: Channel Move Speed 50 -> -1 is not a -98% nerf. -2 was one
# too, but the only -2 in every patch is Cheat Death's real −2 m/s slow (audit 2026-10-04)
SENTINELS = (-1.0, 9999.0, 99999.0)


NO_LIMIT_BIG = (9999.0, 99999.0)


def is_sentinel(v, other=None) -> bool:
    """`v` is the game's "no limit / default" and not a number on a scale: 9999 always; -1 only when the
    other side of the change is not another negative number — Sharpshooter's move speed penalty −0.5 →
    −1 m/s is a real, bigger penalty (it read CHANGED), Channel Move Speed 50 → −1 is "no limit"."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return False
    if x in NO_LIMIT_BIG:
        return True
    if x != -1.0:
        return False
    try:
        return other is None or float(other) >= 0
    except (TypeError, ValueError):
        return True


def reencoded(old, new, path: str = '') -> bool:
    """The same value written another way (audit 2026-10-01, ~86 rows shown as huge changes):
    engine units -> metres ("200" -> "5.1m" is 200/39.37), a fraction -> a percent in a field named
    so (Echo Shard's Imbued Cooldown Multiplier 1 -> 100)."""
    def parse(v):
        if isinstance(v, bool) or v is None:
            return None, ''
        if isinstance(v, (int, float)):
            return float(v), ''
        m = _RAW_NUM.match(str(v))
        return (float(m.group(1)), m.group(2) or '') if m else (None, '')
    (a, ua), (b, ub) = parse(old), parse(new)
    if a is None or b is None or a == b or 0 in (a, b):
        return False
    near = lambda x, y: abs(x - y) <= 0.02 * max(abs(x), abs(y))     # noqa: E731
    if ua != ub and 'm' in (ua, ub):
        units, metres = (a, b) if ub == 'm' else (b, a)
        return near(units / UNITS_PER_METER, metres)
    if not re.search(r'(Multiplier|Percent|Pct|Scale|Frac)', property_name(path)):
        return False
    return 0 < abs(a) <= 1 and near(a * 100, b) or 0 < abs(b) <= 1 and near(b * 100, a)


def metres_pair(old, new) -> tuple:
    """(old, new) on ONE scale: when one side is written in metres ("1.3m") and the other is a bare number, the bare
    one is engine units and is rewritten in metres ("50" -> "1.27m"). Valve moved every Channel Move Speed from
    units to m/s on 2025-08-18: "50 -> 1.3m" read 50 m/s -> 1.3 m/s, a −97.4% NERF on 93 abilities, while it is
    1.27 -> 1.3 m/s, +2% (review 2026-10-05). "No limit" (-1, 9999) and zero stay as they are."""
    def parse(v):
        if isinstance(v, bool) or v is None:
            return None, ''
        if isinstance(v, (int, float)):
            return float(v), ''
        m = _RAW_NUM.match(str(v))
        return (float(m.group(1)), m.group(2) or '') if m else (None, '')
    (a, ua), (b, ub) = parse(old), parse(new)
    if a is None or b is None or (ua == 'm') == (ub == 'm') or ua not in ('', 'm') or ub not in ('', 'm'):
        return old, new

    def in_metres(x: float) -> str:
        return f'{float(f"{x / UNITS_PER_METER:.4g}"):g}m'
    if ua == '' and a not in SENTINELS and a != 0:
        return in_metres(a), new
    if ub == '' and b not in SENTINELS and b != 0:
        return old, in_metres(b)
    return old, new


_UNITS_ALWAYS = re.compile(r'^m_mapAbilityProperties\.ChannelMoveSpeed\.m_strValue$')


def units_when_bare(path: str, old, new) -> tuple:
    """(old, new) of a field whose bare numbers are engine units in every build: Channel Move Speed was written in
    units until 2025-08-18 and in "m" after, so a bare side is units even when the other side carries no "m" —
    "Channel Move Speed 50 → no limit" next to "1.27m/s → 1.3m/s" in the same band (24 rows, review 2026-10-05)."""
    if not _UNITS_ALWAYS.match(path):
        return old, new

    def conv(v):
        if isinstance(v, bool) or v is None:
            return v
        m = _RAW_NUM.match(str(v))
        if not m or m.group(2) or float(m.group(1)) in SENTINELS or float(m.group(1)) == 0:
            return v
        return f'{float(f"{float(m.group(1)) / UNITS_PER_METER:.4g}"):g}m'
    return conv(old), conv(new)


def sign_flip(old, new) -> bool:
    """−22% → 22%: the same size, the other sign. Alone it is a change; with the property's provided
    type flipped in the same window (REDUCTION_PERCENT → INCREASE_PERCENT, Riposte 2026-03-06) it is
    one value written the other way round (match `retyped`)."""
    def parse(v):
        if isinstance(v, bool) or v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        m = _RAW_NUM.match(str(v))
        return float(m.group(1)) if m else None
    a, b = parse(old), parse(new)
    return a is not None and b is not None and a != 0 and a == -b


def display_raw(v, meters: bool | str = False) -> str:
    """A value as the records keep it (a number, or a string such as "12.19m"): a number written
    in metres is not divided again, engine units are."""
    if isinstance(v, str):
        m = _RAW_NUM.match(v)
        if m:
            x = float(m.group(1))
            if m.group(2) == 'm':
                return display_value(x) + ('m/s' if meters in (SPEED, MPS, M_SPEED) else 'm')
            if m.group(2) == '%':
                return display_value(x) + '%'          # already a percent, whatever the field
            return display_value(x, False if meters == M_SPEED else meters)
    return display_value(v, False if meters == M_SPEED else meters)


def show(v, meters: bool | str = False, unit: str = '', invert: bool = False, magnitude: bool = False) -> str:
    """A record value as a change row prints it: units as the field says, the tooltip's unit, and a
    rate shown the way the game does (stamina per second 0.2 -> a 5s cooldown). `magnitude`: the
    tooltip prints the minus itself (prop_sign '-', an enemy slow): the label says "Slow", the value
    is its size (Card Trick's slow stored −30 one build and 30 the next reads 30% both times)."""
    if v is not None and not isinstance(v, bool):
        m = _RAW_NUM.match(str(v))
        if invert and m and float(m.group(1)):
            v = round(1 / float(m.group(1)), 4)
        elif magnitude and m and float(m.group(1)) < 0:
            v = str(v).replace('-', '', 1) if isinstance(v, str) else abs(v)
    return with_unit(display_raw(v, meters), unit)


SPEED_MULTIPLIER_MAX = 5     # 5 engine units per second is 0.13 m/s: no speed in the game is that slow


def display_value(v, meters: bool | str = False) -> str:
    if v is None:
        return '—'
    if isinstance(v, bool):
        return 'yes' if v else 'no'
    if isinstance(v, (int, float)):
        if meters == FRACTION:
            return display_value(round(float(v) * 100, 6)) + '%'
        if meters and float(v) == -1.0:
            return '-1'           # the game's "no limit / default", not −0.0254 m (37 rows, audit 2026-10-04)
        if meters == SPEED and abs(float(v)) < SPEED_MULTIPLIER_MAX:
            # a "speed" this small is a multiplier, not engine units per second: Mauling Leap's Velocity Carryover
            # -0.15 read "-0.00381m/s" (data audit 2026-11-13)
            return display_value(v)
        x = float(v) / UNITS_PER_METER if meters and meters not in (METRES, MPS) else float(v)
        if x.is_integer():
            s = str(int(x))
        elif abs(x) < 1:
            # small coefficients need their own digits: 4 significant ones (Fixation's T3 scaling
            # 0.0003 -> 0.00035 read "0.0003 -> 0.0003" with 4 decimals), never "1e-05"
            s = f'{float(f"{x:.4g}"):.8f}'.rstrip('0').rstrip('.')
        else:
            s = f'{x:.2f}'.rstrip('0').rstrip('.')
        return s + ('m/s' if meters in (SPEED, MPS) else 'm' if meters else '')
    if isinstance(v, list):
        return ', '.join(display_value(x) for x in v)
    return str(v)
