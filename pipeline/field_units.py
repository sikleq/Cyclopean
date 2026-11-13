"""A field's unit: engine units and metres (`UNITS_PER_METER`), the property a path names (`property_name`),
lengths and speeds (`length_in_units`, `bare_engine_length`, `prop_speed`), the unit an engine number is shown in
(`engine_unit`) and a number with its unit (`with_unit`). Imports no other module of the pipeline."""
from __future__ import annotations

import re


UNITS_PER_METER = 39.37


# Street Brawl's own values too: without them the property was "m_strStreetBrawlValue" and every Street Brawl
# cooldown read "more is better" (Mini Turret's 18 → 26 BUFF; data audit 2026-11-13, 11 of 49 rows)
_VALUE_TAIL = re.compile(r'(\.m_subclassScaleFunction)?\.(m_strValue|m_strBonus|m_flStatScale|flScale|'
                         r'm_strStreetBrawlValue|m_strStreetBrawlBonus|m_flStreetBrawlStatScale)$')


_BRACED = re.compile(r'\{([^{}]+)\}$')


def property_name(path: str) -> str:
    """The property a path is about, not its containers: 'm_mapAbilityProperties.CooldownReduction.
    m_strValue' -> 'CooldownReduction', 'm_vecAbilityUpgrades[2].m_vecPropertyUpgrades{AbilityCooldown}.
    m_strBonus' -> 'AbilityCooldown', 'm_MapModCostBonuses.EItemSlotType_Armor[4].flBonus' -> 'flBonus'
    (the word "Cost" in the container flipped 110 investment bonuses)."""
    p = _VALUE_TAIL.sub('', path)
    last = p.rsplit('.', 1)[-1]
    m = _BRACED.search(last)
    return m.group(1) if m else re.sub(r'\[\d+\]$', '', last)


# "meters" says how an engine number is shown: False as is, True a distance (units / 39.37 -> m),
# SPEED a speed (units/s -> m/s)
SPEED = 'speed'


_NOT_A_LENGTH = re.compile(r'(Percent|Pct|Scale|Mult|Ratio|Frac|Time|Duration|Delay|Rate|Chance|Factor|Alpha|Angle|'
                           r'Yaw|Pitch|Degree|Interval|Cooldown|Damage|Health|DPS|Resist|Reward|Bounty|Gold|Fov|Count|'
                           # recoil, turning, spin, a decay or a blend bias are not travel (audit 2026-10-04: "Recoil
                           # Speed 0.127m/s", "Hover Speed Decay 0.02286m/s", "Initial Offset Lerp Bias 0.0127m") —
                           # as words: "KilLERPlane" and "ReTURN" are none (the soul orbs' Killer Plane speeds and the
                           # hook's Return Speed stayed engine units, #13)
                           r'Recoil|(?-i:Turn)|Spin|Accel|Rotat|Punch|Kick|Decay|Bias|(?-i:Lerp)|Penalty|'
                           # an exponent: Scrap Grenade's "Bounce Target Distance Power 1.5" read 0.0381m (review
                           # 2026-10-17)
                           r'(?-i:Power)$|Exponent)',
                           re.I)


# a field that ENDS in a length word is a length whatever it measures from ("Nearby Enemy Resist Range
# 2000" stayed engine units: "Resist" said not a length)
_ENDS_LENGTH = re.compile(r'(Range|Radius|Distance|Height|Width|Length)$')


_RATIO_WORD = re.compile(r'(Percent|Pct|Scale|Mult|Ratio|Frac|Factor)', re.I)


METRES = 'metres'          # already metres: shown as is with "m"


MPS = 'mps'                # already metres per second: shown as is with "m/s"


# a speed Valve writes as "20m" (Channel Move Speed, a T3 "+3m"): the "m" is m/s; a bare number stays
# bare (advisor round 4: "Channel Move Speed 20m → no limit"). Display only — describe() flags it as
# 'speed_m' and keeps 'meters' False, so the matcher's transforms do not move.
M_SPEED = 'm-speed'


FRACTION = 'fraction'      # a share written 0..1: shown ×100 with "%"


# shares the game writes as fractions and the notes as percents: "Move speed while shooting 55% -> 70%"
# read "0.55 -> 0.7", Boss Damage Scale "0.5 -> 0.2" (audit 2026-10-02, AB14)
_FRACTION_FIELD = re.compile(r'^m_fl(ShootMoveSpeedPercent|ZoomMoveSpeedPercent|DamageFalloffEndScale|'
                             r'BossDamageScale|NPCDamageScale|InstantGoldPercentage|'
                             # the healing powerup's share of max health (review 2026-10-05: read "0.02")
                             r'MaxHealthRegenPercent)$')


# ability properties Valve keeps as fractions and the notes print as percents: Puddle Punch's later hits (2026-03-06
# "Fourth Hit Damage Percentage → 0.26" is the notes' 26%)
_FRACTION_PROP = re.compile(r'^(Second|Third|Fourth)HitDamagePercentage$')


# engine floats Valve writes in metres / m/s already (the rope's climb speed 13 -> 14 in the 2024-09-12
# notes; the dash's drag thresholds 12 / 14 m/s against a 10 m dash in 0.68 s)
_ALREADY_MPS = re.compile(r'(ClimbSpeed|AirSpeedFor\w*Drag)')


# an ability property that is a travel speed and carries no unit is engine units per second: Zip
# Speed "660 -> 693" is 16.8 -> 17.6 m/s, Toss Speed 450 is 11.4 m/s (audit 2026-10-02, #14). Not
# a move speed / attack speed / slow (percents), a turn, tracking or sweep rate, recoil or fall.
# A capped speed is one too: Grey Talon's Rain of Arrows "Air Speed Max 150 → 161.42" is the notes' 3.8 → 4.1 m/s,
# a glide's "Fall Speed Max 30 → 15" 0.76 → 0.38 m/s (#13; they were kept out with the fall damage words)
_PROP_SPEED = re.compile(r'(Speed|Velocity)(Inner|Outer|UpWall|Wall|NonPlayer|Start|Max|Min)?$')


_PROP_NOT_TRAVEL = re.compile(r'(Move|AttackSpeed|Turn|Tracking|Sweep|Recoil|Reload|Bullet|Spin|'
                              r'Channel|Hit|Limit|Penalty|Slow|Bonus|Percent|Pct|Mult|Ratio|Scale|Check|Pitch|Vol|'
                              r'Duration|Time|Build|Lost|Boost|Change|PostGroundDash|Summon|'
                              r'Distance|Camera|Rotat|Anim|Preview)')       # DistanceForMaxProjSpeed is a length


def prop_speed(prop: str, unit: str = '') -> bool:
    return not unit and bool(_PROP_SPEED.search(prop)) and not _PROP_NOT_TRAVEL.search(prop)


# a property that is a speed wherever "speed" sits in its name: its "4.5m" is m/s ("Active Movespeed
# Penalty 4.5m → 6.5m", "Invis Move Speed Mod +4m"; audit 2026-10-04)
_SPEED_NAME = re.compile(r'Speed(?:Max|Min)?$|(?:Move|Sprint|Movement|Run|Walk|Air|Dash)speed', re.I)


def speed_prop(prop: str) -> bool:
    return bool(_SPEED_NAME.search(prop))


# a property named like a length with no unit in any build is engine units when its numbers are big
# ("Lift Height 120 → 200", "Follow Distance 120 → 60", Stomp "Activation Distance 600"): 1 m = 39.37
_PROP_LENGTH = re.compile(r'(Range|Radius|Distance|Dist|Height|Width|Length|Offset)', re.I)


_PROP_NOT_LENGTH = re.compile(r'(Percent|Pct|Scale|Mult|Ratio|Frac|Factor|Time|Duration|Delay|Count|Speed|Chance|'
                              r'Angle|Degree|Pitch|Yaw|Damage|Bonus$|Power$|Exponent)', re.I)


ENGINE_LENGTH_MIN = 20          # 20 engine units = 0.5 m: below it a bare number is more likely metres


def length_in_units(path: str, unit: str, values) -> bool:
    """Show this ability property's numbers as metres converted from engine units (display only)."""
    if unit or not (_PROP_RE.match(path) or _TIER_RE.match(path)):
        return False
    prop = property_name(path).split('|')[0]
    if not _PROP_LENGTH.search(prop) or _PROP_NOT_LENGTH.search(prop):
        return False
    nums = [abs(float(m.group(1))) for v in values if v is not None and not isinstance(v, bool)
            for m in [_RAW_NUM.match(str(v))] if m and not m.group(2)]
    return bool(nums) and max(nums) > ENGINE_LENGTH_MIN


BARE_LENGTH_MIN = 30      # a bare number from 30 under a tooltip's "m" is engine units (30 u = 0.76 m)


def bare_engine_length(unit: str, values) -> bool:
    """A field whose tooltip says "m" (or m/s) but whose values the files write bare and big is in engine units:
    Walker's Stomp "500" -> "472.441" is 12.7 m -> 12 m, it read "500m -> 472.44m" (data audit 2026-11-13: 9 rows,
    Laser 2000m, Riposte's Dash Speed 2400 m/s that is 61 m/s). A value written with its unit ("16m") is metres."""
    if unit not in ('m', 'm/s'):
        return False
    nums = []
    for v in values:
        if v is None or isinstance(v, bool):
            continue
        m = _RAW_NUM.match(str(v))
        if not m or m.group(2):
            return False
        nums.append(abs(float(m.group(1))))
    return bool(nums) and max(nums) >= BARE_LENGTH_MIN


def engine_unit(leaf: str) -> bool | str:
    """An engine float named like a length or a speed is in engine units: Walker 'Invul Modifier Range
    1338.58 → 866.14' is 34 → 22 m, a projectile 'Speed 1050 → 400' is 26.7 → 10.2 m/s (audit
    2026-10-01: 302 rows of abilities, 225 of units in raw units) — unless its name says metres
    ("Dash Jump Distance In Meters 18 → 19" was divided into 0.46 m)."""
    if _FRACTION_FIELD.match(leaf):
        return FRACTION
    if re.search(r'Meters?(?:PerSecond)?$|InMeters|Meters', leaf):
        # "…MeterPerSecond" is m/s already (the Rejuvenator's speed read 0.0254 m/s, divided twice)
        return MPS if re.search(r'(PerSecond|Speed)', leaf) else METRES
    if _ALREADY_MPS.search(leaf):
        return MPS
    if leaf.startswith('m_fl') and _ENDS_LENGTH.search(leaf) and not _RATIO_WORD.search(leaf[4:]):
        return True
    if not leaf.startswith('m_fl') or _NOT_A_LENGTH.search(leaf[4:]):
        return False
    if re.search(r'Speed|Velocity|[a-z]speed$', leaf):       # "m_flMaxMovespeed 600" is 15.24 m/s
        return SPEED
    return bool(re.search(r'(Range|Radius|Distance|Dist$|Height|Width|Length|Offset)', leaf))


_PLAIN_NUMBER = re.compile(r'^[-+]?\d+(\.\d+)?$')


def with_unit(s: str, unit: str) -> str:
    """'30' + 's' -> '30s'; a value that already carries a unit, or is not a number, stays."""
    return s + unit if unit and isinstance(s, str) and _PLAIN_NUMBER.match(s) else s


_TIER_RE = re.compile(r'^m_vecAbilityUpgrades\[(\d+)\]\.m_vecPropertyUpgrades\{([^}]+)\}\.(\w+)$')


_PROP_RE = re.compile(r'^m_mapAbilityProperties\.([^.]+)\.(.+)$')


_RAW_NUM = re.compile(r'^\s*([-+]?(?:\d+\.?\d*|\.\d+))\s*(m|s|%|u)?\s*$')
