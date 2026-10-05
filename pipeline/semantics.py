"""Human meaning of diffed fields: labels, units, direction (BUFF/NERF).

Labels come from the game's own localization of the same build wherever the
game has one (`<Prop>_label`, `StatDesc_<Stat>`); the small hand maps below
cover fields the game never labels (weapon internals, NPC fields).
"""
from __future__ import annotations

import html
import re

UNITS_PER_METER = 39.37

# ---- direction -----------------------------------------------------------

# property/stat name fragments where a LOWER value is better for the owner
_LOWER_BETTER = re.compile(
    r'(cooldown|castdelay|cast_delay|casttime|reload|cycletime|spread|cost|price|'
    r'windup|lockout|recoil|delay(?!ed)|critdamagereceived|damagetaken|selfdamage|'
    r'chargetime|channeltime|backswing|fallofstart|penalty|fadetime|arming|'
    r'm_unrequiredgold|goldthreshold|requiredgold|resurrectiontime|respawn|'
    # time between an effect's ticks: shorter = it heals / hits more often (Infest Heal Interval 3 -> 2
    # is a buff); sound / think / trail intervals keep the default
    r'(?:heal|tick|volley|pulse|impact|damage|attack|explosion|explode)interval)',
    re.I,
)
# checked BEFORE the lists above, whole names a lower-is-better word inside would flip (audit
# 2026-10-01, 91 rows): what has to be shorter / smaller …
_LOWER_FIRST = re.compile(
    r'(decaydelay|postcast|armtime|chargeuptime|deploytime|timetogain|fadeto|telegraph|gravity|ammoconsumed|'
    r'bulletstofully|drainrate|durationformax|expandtime|spindecay|nonheroreduction|'
    # a dash covers a fixed distance (EGround/AirDashDistanceInMeters): longer = slower ("same
    # distance, slower to get there", 2025-07-29) — 22 rows read BUFF (audit 2026-10-01)
    r'dashduration|airdashtraveltime|'
    # how far a shotgun's pellets scatter sideways / up: a spread scale (Slork's 1 -> 0 read NERF)
    r'scatter(?:yaw|pitch)scale)', re.I)
# a slow on the player's own movement (mantle / climb rope when hit): smaller is better — checked on
# the whole path, the field itself is a generic "Percentage Multiplier Start"
_SELF_SLOW = re.compile(r'(SlowOnHit|SlowFromRecentDamage)Modifier\.', re.I)
# … and what has to be bigger: health on respawn, a delay that grows with spirit, a bonus to the
# damage the ENEMY takes (Alchemical Fire), how long before rage drains
_HIGHER_FIRST = re.compile(r'(respawnhealth|wakeupdelay|draindelay|bonus\w*damagetaken|'
                           # the parried enemy takes it: "Parry bonus damage reduced from 30% to 25%" is a nerf
                           r'victimdamagetaken|meleedamagetakenscale)', re.I)
# fields where direction is not meaningful for the owner; also where a thing sits or how it eases in
# (a summoned card's offset, Ice Path's pitch limits, a grab's damping, a dragon's spring: 30 rows read
# BUFF / NERF, audit 2026-10-04). Bare yaw / pitch stay: a recoil or spread pitch has a side
_NEUTRAL = re.compile(r'(tangent|spline|curve|domain|seed|index|order|count_max_ui|_class|mask|bits|flags?$|'
                      r'offset|pitch(?:up|down|min|max)|aimbias|damping|friction|spring(?:constant|length))', re.I)
# a field whose name says the opposite of what it does, by its whole path; checked before every other
# rule (data-quality audit 2026-10-04: these rows were tagged against their own patch note)
POLARITY_RULES = (
    # Vampiric Burst's active ADDS this share of the clip ("Added ammo on active increased from +50% to
    # +75%", 2024-10-10): not a reload time, though "reload" is in the name
    (re.compile(r'ActiveReloadPercent'), 1),
    # how fast the aim settles after recoil: faster is better ("recoil" is in the name; game logic, no note)
    (re.compile(r'RecoilRecoverySpeed'), 1),
    # Malice's slow on the ENEMY per stack ("Malice slow reduced from 20% to 15%", 2024-10-24: a nerf)
    (re.compile(r'MoveSpeedPenaltyPerStack'), 1),
    # Borrowed Decree's seconds between summons ("spawn interval improved from every 5s to every 4s")
    (re.compile(r'SummonFrequency'), -1),
    # Golden Goose Egg's souls per buff ("souls per buff improved from every 200 souls to every 150")
    (re.compile(r'BonusBuffsPerGold'), -1),
    # Improved Burst / Tankbuster's damage threshold ("Threshold damage increased from 125 to 200" is a
    # nerf, "Damage threshold requirement reduced from 200 to 175" a buff)
    (re.compile(r'MinimumDamage'), -1),
    # Goo Ball's lockout before it can stun the same target again ("stun frequency cooldown improved from
    # 1.5s to 1.25s", 2024-09-12)
    (re.compile(r'^m_DamagePreventionModifier\.m_flDuration$'), -1),
)

GRADIENT_STEPS = (5, 10, 15, 20, 25, 33, 45, 60, 80)


# "Cooldown Reduction", "Spread Penalty Decay": a lower-is-better word followed by one of these
# names the opposite quantity (audit 2026-10-01: ~45 rows were flipped)
_NEGATED = re.compile(r'(reduction|reduce|refund|decay)', re.I)
_VALUE_TAIL = re.compile(r'(\.m_subclassScaleFunction)?\.(m_strValue|m_strBonus|m_flStatScale|flScale)$')
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


def polarity(path: str) -> int:
    """+1 higher is better, -1 lower is better, 0 no direction — read from the property's own name."""
    for rx, pol in POLARITY_RULES:
        if rx.search(path):
            return pol
    name = property_name(path)
    if _NEUTRAL.search(name):
        return 0
    if _SELF_SLOW.search(path) and 'PercentageMultiplier' in name:
        return -1
    if _HIGHER_FIRST.search(name):
        return 1
    if _LOWER_FIRST.search(name):
        return -1
    m = _LOWER_BETTER.search(name)
    if not m:
        return 1
    # the negating word may come first: Rising Ram's "Reduce Cooldown On Hit Pct" 0 -> 50 is a buff
    # (it read NERF), Pain Battery's "Bonus Damage Decay Lockout Duration" longer is better
    return 1 if _NEGATED.search(name[m.end():]) or _NEGATED.search(name[:m.start()]) else -1


def direction(path: str, old, new, kind: str = '', drawback: bool = False,
              negative_base: bool = False) -> tuple[str, float | None]:
    """('buff'|'nerf'|'changed', signed percent or None) for a numeric change.

    Magnitudes are compared (|x|): debuffs are stored as negative numbers
    ("-8% resist"), so going -8 -> -7 is a weaker effect.
    Units (troopers, buildings, neutrals) have no owner-side direction.
    `drawback`: the game marks the property as the holder's own downside (m_bIsNegativeAttribute,
    drawn red in the tooltip): a bigger one is a nerf, whatever the name says (Golden Goose Egg's
    damage penalty -10% -> -15% read BUFF by the "penalty on the enemy" rule).
    """
    if not isinstance(old, (int, float)) or not isinstance(new, (int, float)) or isinstance(old, bool):
        return 'changed', None
    a, b = abs(float(old)), abs(float(new))
    pct = None if a == 0 else (b - a) / a * 100.0
    if _ARMOR_INVEST.search(path) and min(a, b) > 0 and max(a, b) >= 5 * min(a, b):
        # Vitality investment switched units twice (a % of base health <-> flat HP; builds 6044 and
        # 6403): "8 → 75 +837%" was a unit, not a buff (audit 2026-10-01)
        return 'changed', None
    if (is_sentinel(old, new) or is_sentinel(new, old)) and not UPGRADE_BONUS.search(path):
        return 'changed', None              # "no limit" (-1, 9999) on one side: no direction, no %
    if drawback and kind not in SHARED_KINDS:
        return ('changed' if a == b else 'nerf' if b > a else 'buff'), pct
    if kind in SHARED_KINDS:
        # objects both teams have (troopers, guardians, camps, pickups, game rules): no owner side,
        # so the tag says which way the number went (UP / DOWN) — except what plainly helps the
        # player who takes it: a camp's bounty, a powerup's strength, a shorter respawn
        for rx, pol_ in PLAYER_SIDE:
            if rx.search(path):
                x, y = float(old), float(new)
                if x == y:
                    return 'changed', pct
                return ('buff' if (y > x) == (pol_ > 0) else 'nerf'), pct
        if float(old) == float(new):
            return 'changed', pct
        return ('up' if float(new) > float(old) else 'down'), pct
    pol = polarity(path)
    if pol > 0 and path.startswith('m_mapStartingStats.'):
        # a hero's own base stat counts with its sign: a resist below zero is a penalty, so Pocket's
        # bullet resist −20% → −15% is the notes' "Base bullet resistance improved" (it read NERF), and
        # Celeste's −6% → −8% a nerf (audit 2026-10-04). The percent goes with the sign too: Pocket's
        # BUFF read "−20% → −15% −25.0%" (review 2026-10-04), it is +25%
        x, y = float(old), float(new)
        signed = None if x == 0 else (y - x) / abs(x) * 100.0
        return ('changed' if x == y else 'buff' if y > x else 'nerf'), signed
    if pol == 0 or a == b:
        return 'changed', pct
    if UPGRADE_BONUS.search(path) or pol < 0:
        # a T1-T3 bonus is added to the stat, so its SIGN counts: a cooldown bonus going
        # -20 -> -18 cuts 2s less (nerf), though the magnitude shrank (reported 2026-10-01).
        # Lower-is-better values compare with their sign too: an enemy healing penalty -65 -> -70
        # and "-40% damage received" -> -60% are both stronger (audit 2026-10-01)
        x, y = float(old), float(new)
        if x == y:
            return 'changed', pct
        if pol > 0 and x <= 0 and y <= 0 and (negative_base or _ENEMY_DEBUFF.search(property_name(path))):
            # a bonus to a debuff stored as a negative number (dash slow −50, shred −8): a bigger
            # magnitude is a stronger debuff. Sleep Dagger T3 −50 → −45 is the 09-16 "dash slows
            # reduced by ~10%", Enhanced Escalating Exposure −8 → −10 is "shred +8 → +10" (39 rows)
            return ('buff' if abs(y) > abs(x) else 'nerf'), pct
        better = (y > x) if pol > 0 else (y < x)
        return ('buff' if better else 'nerf'), pct
    better = (b > a) if pol > 0 else (b < a)
    return ('buff' if better else 'nerf'), pct


UPGRADE_BONUS = re.compile(r'm_vecAbilityUpgrades.*\.m_strBonus$')
_ARMOR_INVEST = re.compile(r'^m_MapModCostBonuses\.EItemSlotType_Armor\W.*\.flBonus$')
# a property that hits the enemy, written as a negative: a bigger (more negative) tier bonus is a stronger
# debuff even when the base value is 0 (Aura of Suffering T1 Enemy Dash Slow -25 -> -22 is a nerf)
_ENEMY_DEBUFF = re.compile(r'(enemy|slow|shred|debuff|armordamagereduction|resistreduction)', re.I)
SHARED_KINDS = ('trooper', 'building', 'neutral', 'unit', 'global')
# fields of shared objects with a side after all: the player who takes the camp / pickup / respawn
PLAYER_SIDE = (
    (re.compile(r'GoldReward|SoulReward|Bounty', re.I), 1),
    (re.compile(r'SpawnInterval|InitialSpawnDelay|InitialSpawnTime|MatchTimeMinsForLevel|RespawnTime', re.I), -1),
    (re.compile(r'^m_sModifer\.(m_flDuration$|m_vecModifierValues.*m_value(Min|Max)$)'), 1),
    (re.compile(r'MissingPctRegen'), 1),
)


def gradient(pct: float | None) -> int:
    """Badge intensity step 1..10 by |percent| (Sloppy scale)."""
    if pct is None:
        return 5
    p = abs(pct)
    for i, lim in enumerate(GRADIENT_STEPS, start=1):
        if p <= lim:
            return i
    return 10


# ---- labels --------------------------------------------------------------

STAT_DESC_EXCEPTIONS = {
    'MaxMoveSpeed': 'RunSpeed',
    'ClipSize': 'ClipSizeBonus',
    'WeaponDPS': 'DPS',
    'OOCHealthRegen': 'OutOfCombatHealthRegen',
    'TechCooldownBetweenChargeUses': 'TechCooldownBetweenCharges',
    'BaseWeaponDamageIncrease': 'BaseWeaponDamage',
}

CUSTOM_STAT_LABELS = {
    'CrouchSpeed': 'Crouch Speed',
    'MoveAcceleration': 'Move Acceleration',
    'GroundDashDistanceInMeters': 'Ground Dash Distance',
    'GroundDashDuration': 'Ground Dash Duration',
    'AirDashDistanceInMeters': 'Air Dash Distance',
    'AirDashDuration': 'Air Dash Duration',
    'StaminaRegenPerSecond': 'Stamina Regen',
    'LightMeleeDamage': 'Light Melee Damage',
    'HeavyMeleeDamage': 'Heavy Melee Damage',
    'CritDamageReceivedScale': 'Headshot Damage Taken ×',
    'CritDamageBonusScale': 'Headshot Damage Bonus ×',
}
# our own words win over the game's for these: "Crit Reduction 0.75 → 0.65" read as a nerf of a
# reduction; the value is the multiplier on headshot damage taken (audit 2026-10-01)
CUSTOM_FIRST = ('CritDamageReceivedScale', 'CritDamageBonusScale')

LEVEL_UP_LABELS = {
    'MODIFIER_VALUE_BASE_HEALTH_FROM_LEVEL': 'Health per boon',
    'MODIFIER_VALUE_BASE_BULLET_DAMAGE_FROM_LEVEL': 'Bullet damage per boon',
    'MODIFIER_VALUE_BASE_BULLET_DAMAGE_FROM_LEVEL_ALT_FIRE': 'Alt-fire damage per boon',
    'MODIFIER_VALUE_BASE_MELEE_DAMAGE_FROM_LEVEL': 'Melee damage per boon',
    'MODIFIER_VALUE_TECH_POWER': 'Spirit power per boon',
    'MODIFIER_VALUE_BULLET_ARMOR_DAMAGE_RESIST': 'Bullet resist per boon',
    'MODIFIER_VALUE_TECH_ARMOR_DAMAGE_RESIST': 'Spirit resist per boon',
    'MODIFIER_VALUE_TECH_RESIST': 'Spirit resist per boon',          # the key's name since build 6541
    'MODIFIER_VALUE_BONUS_ATTACK_RANGE': 'Weapon range per boon',
    'MODIFIER_VALUE_BOON_COUNT': 'Boons per level',
    'MODIFIER_VALUE_OUT_OF_COMBAT_HEALTH_REGEN': 'Out-of-combat regen per boon',
    'MODIFIER_VALUE_TECH_DAMAGE_MULTIPLIER': 'Spirit damage multiplier per boon',
    'MODIFIER_VALUE_TECH_DAMAGE_PERCENT': 'Spirit damage % per boon',
}

# "meters" says how an engine number is shown: False as is, True a distance (units / 39.37 -> m),
# SPEED a speed (units/s -> m/s)
SPEED = 'speed'
_NOT_A_LENGTH = re.compile(r'(Percent|Pct|Scale|Mult|Ratio|Frac|Time|Duration|Delay|Rate|Chance|Factor|Alpha|Angle|'
                           r'Yaw|Pitch|Degree|Interval|Cooldown|Damage|Health|DPS|Resist|Reward|Bounty|Gold|Fov|Count|'
                           # recoil, turning, spin, a decay or a blend bias are not travel (audit 2026-10-04: "Recoil
                           # Speed 0.127m/s", "Hover Speed Decay 0.02286m/s", "Initial Offset Lerp Bias 0.0127m")
                           r'Recoil|Turn|Spin|Accel|Rotat|Punch|Kick|Decay|Bias|Lerp|Penalty)',
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
                             r'BossDamageScale|NPCDamageScale|InstantGoldPercentage)$')
# engine floats Valve writes in metres / m/s already (the rope's climb speed 13 -> 14 in the 2024-09-12
# notes; the dash's drag thresholds 12 / 14 m/s against a 10 m dash in 0.68 s)
_ALREADY_MPS = re.compile(r'(ClimbSpeed|AirSpeedFor\w*Drag)')


# an ability property that is a travel speed and carries no unit is engine units per second: Zip
# Speed "660 -> 693" is 16.8 -> 17.6 m/s, Toss Speed 450 is 11.4 m/s (audit 2026-10-02, #14). Not
# a move speed / attack speed / slow (percents), a turn, tracking or sweep rate, recoil or fall.
_PROP_SPEED = re.compile(r'(Speed|Velocity)(Inner|Outer|UpWall|Wall|NonPlayer|Start)?$')
_PROP_NOT_TRAVEL = re.compile(r'(Move|AttackSpeed|Turn|Tracking|Sweep|Recoil|Fall|AirSpeed|Reload|Bullet|Spin|'
                              r'Channel|Hit|Limit|Penalty|Slow|Bonus|Percent|Pct|Mult|Ratio|Scale|Check|Pitch|Vol|'
                              r'Duration|Time|Build|Lost|Boost|Change|PostGroundDash|Summon|'
                              r'Distance|Camera|Rotat|Anim|Preview)')       # DistanceForMaxProjSpeed is a length


def prop_speed(prop: str, unit: str = '') -> bool:
    return not unit and bool(_PROP_SPEED.search(prop)) and not _PROP_NOT_TRAVEL.search(prop)


# a property that is a speed wherever "speed" sits in its name: its "4.5m" is m/s ("Active Movespeed
# Penalty 4.5m → 6.5m", "Invis Move Speed Mod +4m"; audit 2026-10-04)
_SPEED_NAME = re.compile(r'Speed$|(?:Move|Sprint|Movement|Run|Walk|Air|Dash)speed', re.I)


def speed_prop(prop: str) -> bool:
    return bool(_SPEED_NAME.search(prop))


# a property named like a length with no unit in any build is engine units when its numbers are big
# ("Lift Height 120 → 200", "Follow Distance 120 → 60", Stomp "Activation Distance 600"): 1 m = 39.37
_PROP_LENGTH = re.compile(r'(Range|Radius|Distance|Dist|Height|Width|Length|Offset)', re.I)
_PROP_NOT_LENGTH = re.compile(r'(Percent|Pct|Scale|Mult|Ratio|Frac|Factor|Time|Duration|Delay|Count|Speed|Chance|'
                              r'Angle|Degree|Pitch|Yaw|Damage|Bonus$)', re.I)
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
    if re.search(r'(Speed|Velocity)', leaf):
        return SPEED
    return bool(re.search(r'(Range|Radius|Distance|Dist$|Height|Width|Length|Offset)', leaf))


# weapon fields (m_mapWeaponInfos.primary.*): label, meters?
WEAPON_FIELDS = {
    'm_flBulletDamage': ('Bullet Damage', False),
    'm_iBullets': ('Pellets per Shot', False),
    'm_flCycleTime': ('Fire Interval', False),
    'm_iBurstShotCount': ('Burst Size', False),
    'm_flIntraBurstCycleTime': ('Burst Interval', False),
    'm_iClipSize': ('Ammo', False),
    'm_reloadDuration': ('Reload Time', False),
    'm_flReloadSingleBulletsInitialDelay': ('Reload Start Delay', False),
    'm_flBulletSpeed': ('Bullet Velocity', SPEED),
    'm_flDamageFalloffStartRange': ('Falloff Start', True),
    'm_flDamageFalloffEndRange': ('Falloff End', True),
    'm_flDamageFalloffEndScale': ('Damage at Falloff End', FRACTION),
    'm_flRange': ('Max Range', True),
    'm_flCritBonusStart': ('Headshot Multiplier', False),
    'm_flCritBonusEnd': ('Headshot Multiplier (far)', False),
    'm_flCritBonusAgainstNPCs': ('Headshot Multiplier vs NPCs', False),
    'm_flBulletGravityScale': ('Bullet Gravity', False),
    'm_flBulletRadius': ('Bullet Radius', True),
    'm_Spread': ('Spread', False),
    'm_StandingSpread': ('Standing Spread', False),
    'm_flShootSpreadPenaltyPerShot': ('Spread per Shot', False),
    'm_flShootMoveSpeedPercent': ('Move Speed while Shooting', FRACTION),
    'm_flZoomMoveSpeedPercent': ('Move Speed while Zoomed', FRACTION),
    'm_flBulletLifetime': ('Bullet Lifetime', False),
    'm_flPelletScatterSpreadFactor': ('Pellet Spread', False),
    'm_flMaxSpinCycleTime': ('Spun-up Fire Interval', False),
    'm_flSpinIncreaseRate': ('Spin-up Rate', False),
    'm_flSpinDecayRate': ('Spin-down Rate', False),
    'm_flPenetrationPercent': ('Penetration', False),
    'm_flExplosionRadius': ('Explosion Radius', True),
    'm_iAmmoConsumedPerShot': ('Ammo per Shot', False),
    'm_flBuildUpRate': ('Proc Build-up', False),
}

# NPC / building fields: label, meters?
UNIT_FIELDS = {
    'm_nMaxHealth': ('Health', False),
    'm_iStartingHealth': ('Starting Health', False),
    'm_iHealthGainPerMinute': ('Health per Minute', False),
    'm_flPlayerDPS': ('DPS vs Heroes', False),
    'm_flTrooperDPS': ('DPS vs Troopers', False),
    'm_flPlayerDamageResistPct': ('Resist vs Heroes', False),
    'm_flTrooperDamageResistPct': ('Resist vs Troopers', False),
    'm_flInvulRange': ('Invulnerability Range', True),
    'm_flBackDoorProtectionRange': ('Backdoor Protection Range', True),
    'm_flGoldReward': ('Soul Bounty', False),
    'm_flGoldRewardBonusPercentPerMinute': ('Bounty Growth per Minute', False),
    'm_flWalkSpeed': ('Walk Speed', SPEED),
    'm_flRunSpeed': ('Run Speed', SPEED),
    'm_flMeleeDamage': ('Melee Damage', False),
    'm_flMeleeHitRange': ('Melee Range', True),
    'm_flStompDamage': ('Stomp Damage', False),
    'm_flStompDamageMaxHealthPercent': ('Stomp Damage (% max HP)', False),
    'm_flStunDuration': ('Stun Duration', False),
    'm_flDPSPctGrowthPerMinute': ('DPS Growth per Minute', False),
    'm_flBaseDPS': ('Base DPS', False),
    'm_flEndDPS': ('End DPS', False),
    'm_flEndDPSTimeInSeconds': ('End DPS Time', False),
    'm_flMaxRange': ('Max Range', True),
    'm_flDamageResist': ('Damage Resist', False),
    'm_flOOCRegen': ('Out-of-combat Regen', False),
    # Walker's / the Patron's shield around them and how far a guardian sees heroes (audit 2026-10-04:
    # "Invul Modifier Range", "Sight Range Players")
    'm_flInvulModifierRange': ('Invulnerability aura range', True),
    'm_flSightRangePlayers': ('Sight range vs heroes', True),
}

# 'm_' always goes; a Hungarian type prefix goes when a capital follows ('m_flBonus', 'flBonus',
# 'nGoldThreshold'); 'm_projectileInfo' kept its 'm ' before (audit 2026-10-01: 193 labels)
_PREFIX_RE = re.compile(r'^(?:m_)?(?:(?:fl|n|i|b|str|e|vec|map|un|s|v|h|ar|bits|sz)(?=[A-Z]))?')
# split camelCase; keep plural acronyms whole ('NPCs' read 'NP Cs')
_CAMEL_RE = re.compile(r'(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z](?!s(?:[A-Z\d_]|$))[a-z])')
# a curve's m_vDomainMins / m_vDomainMaxs are its lower / upper corners ("Domain (min)" sat next to
# "Domain Maxs"); elsewhere "Mins" is minutes ("Match Time Mins For Level2 Pickups")
_UNIT_WORDS = ((' In Seconds', ' (s)'), (' In Meters', ' (m)'), ('Domain Maxs', 'Domain (max)'), (' Mins', ' (min)'))


# the game's words for Valve's internal ones, in labels the game never wrote (a field name split into
# words): "Tech" is Spirit, an armor stat is a resist (advisor round 4, 2026-10-03: 63 rows read "Tech
# Armor Damage Resist", "Intrinsic Modifiers boss intrinsic › Bullet Armor Damage Resist")
_GAME_WORDS = ((re.compile(r'\bBullet Armor Damage (Resist|Reduction)\b'), 'Bullet Resist'),
               (re.compile(r'\bTech Armor Damage (Resist|Reduction)\b'), 'Spirit Resist'),
               (re.compile(r'\bBullet Armor\b'), 'Bullet Resist'),
               (re.compile(r'\bTech Armor\b'), 'Spirit Resist'),
               (re.compile(r'\bTech\b'), 'Spirit'),
               (re.compile(r'\bVerticall\b'), 'Vertical'))          # Valve's typo in a weapon field (12 rows)


def game_words(text: str) -> str:
    for rx, word in _GAME_WORDS:
        text = rx.sub(word, text)
    return text


def humanize(key: str) -> str:
    k = _PREFIX_RE.sub('', key)
    k = k.lstrip('_').replace('_', ' ')
    out = _CAMEL_RE.sub(' ', k).strip() or key
    for a, b in _UNIT_WORDS:
        out = out.replace(a, b)
    return game_words(out[:1].upper() + out[1:])


def _loc_label(tok: dict[str, str], name: str, ability: str | None = None) -> str | None:
    for key in ((f'{ability}_{name}_label' if ability else None), f'{name}_label', name):
        if key and key.lower() in tok:
            # loc text carries HTML entities ("Bullet &amp; Spirit Lifesteal"): plain text out
            val = html.unescape(re.sub(r'<[^>]+>', '', tok[key.lower()])).strip()
            if val and '{' not in val and _names_something(val):
                return val
    return None


_PARENS = re.compile(r'\([^)]*\)')
_LETTER = re.compile(r'[^\W\d_]')


def _names_something(label: str) -> bool:
    """A label is more than a qualifier: Calico's Ava 'StatueHealth_label' became "(Normalized)" and 17
    rows read "(Normalized) 300HP → 200HP" (review 2026-10-04) — such text is no label, the field keeps
    the last one Valve gave it (labels.collect) or its name in words."""
    return bool(_LETTER.search(_PARENS.sub('', label)))


def stat_label(tok: dict[str, str], stat: str) -> str:
    return stat_label_src(tok, stat)[0]


def stat_label_src(tok: dict[str, str], stat: str) -> tuple[str, str]:
    """(label, 'loc' | 'curated' | 'fallback') of a hero stat."""
    base = stat[1:] if stat.startswith('E') and stat[1:2].isupper() else stat
    key = 'StatDesc_' + STAT_DESC_EXCEPTIONS.get(base, base)
    if key.lower() in tok and base not in CUSTOM_FIRST:
        return re.sub(r'<[^>]+>', '', tok[key.lower()]).strip(), 'loc'
    if base in CUSTOM_STAT_LABELS:
        return CUSTOM_STAT_LABELS[base], 'curated'
    return humanize(base), 'fallback'


def override_label(tok: dict[str, str], token: str | None, entity: str = '') -> str | None:
    """The label the tooltip prints for a property with m_strLocTokenOverride: a property name
    ('BuffDuration' -> its _label) or a loc key ('#Citadel_…'). 293 rows said "Duration" where the
    game says "Shield Duration" (audit 2026-10-01)."""
    if not token:
        return None
    if token.startswith('#'):
        val = tok.get(token[1:].lower())
        val = html.unescape(re.sub(r'<[^>]+>', '', val)).strip() if val and '{' not in val else None
        return val if val and _names_something(val) else None
    return _loc_label(tok, token, entity)


def prop_unit(tok: dict[str, str], prop: str, token: str | None = None) -> str:
    """The unit the tooltip prints after a property's value (its loc postfix): 's', '%', 'm', 'm/s'.
    Values had none ("Cooldown 30 → 38") on 6,395 rows."""
    for name in (token, prop):
        if name and not name.startswith('#'):
            post = tok.get(f'{name}_postfix'.lower(), '').strip()
            if post and '{' not in post and len(post) <= 4:
                return post
    return ''


def prop_sign(tok: dict[str, str], prop: str, token: str | None = None) -> str | None:
    """'-' when the tooltip prints a minus the value does not carry: an enemy slow is stored 30 and
    shown "-30% Move Speed" (`<prop>_prefix` = "-"). '' when the loc has another prefix ("+",
    "{s:sign}"), None when it has none for the property (audit 2026-10-04: 185 slows read as the
    hero's own "Move Speed 30% → 24%")."""
    found = None
    for name in (token, prop):
        if name and not name.startswith('#'):
            key = f'{name}_prefix'.lower()
            if key in tok:
                if tok[key].strip() == '-':
                    return '-'
                found = ''
    return found


# an enemy-facing value the tooltip prints with a minus (prop_sign): what it does to the enemy, by name
# ("Move Speed" -> "Movement Slow", "Fire Rate" -> "Fire Rate Slow", "Bullet Resist (Heavy)" ->
# "Bullet Resist reduction (Heavy)"); a label that already says so stays
_SAYS_LESS = re.compile(r'(slow|reduc|decreas|penalt|less\b|lower)', re.I)
_MOVE_SPEED = re.compile(r'\bMove ?[Ss]peed\b|\bMovespeed\b|\bMovement Speed\b')
_TIER_PREFIX = re.compile(r'^((?:T\d|Enhanced|Upgrade): )')


def enemy_label(label: str, prop: str) -> str:
    """The label of a value the game shows with a minus it does not store (prop_sign '-'): the
    magnitude is shown (`magnitude` in show()), so the label says what shrinks."""
    m = _TIER_PREFIX.match(label)
    head, body = (m.group(1), label[m.end():]) if m else ('', label)
    if not body or _SAYS_LESS.search(body):
        return label
    if 'slow' in prop.lower():
        body = _MOVE_SPEED.sub('Movement Slow', body, count=1) if _MOVE_SPEED.search(body) else body + ' Slow'
    else:
        paren = re.search(r'\s*\([^()]*\)$', body)
        body = f'{body[:paren.start()]} reduction{body[paren.start():]}' if paren else f'{body} reduction'
    return head + body


_PLAIN_NUMBER = re.compile(r'^[-+]?\d+(\.\d+)?$')


def with_unit(s: str, unit: str) -> str:
    """'30' + 's' -> '30s'; a value that already carries a unit, or is not a number, stays."""
    return s + unit if unit and isinstance(s, str) and _PLAIN_NUMBER.match(s) else s


def stat_unit(tok: dict[str, str], stat: str) -> str:
    base = stat[1:] if stat.startswith('E') and stat[1:2].isupper() else stat
    key = ('StatDesc_' + STAT_DESC_EXCEPTIONS.get(base, base) + '_postfix').lower()
    return tok.get(key, '')


# what a tier's scaling bonus scales with (m_eScaleStatFilter); almost always Spirit Power, but
# Fixation's T3 scales with weapon damage and read "(spirit scaling)" until 2026-10-01
SCALE_STAT_WORDS = {'EWeaponPower': 'weapon damage', 'EBaseWeaponDamageIncrease': 'weapon damage',
                    'EBulletDamage': 'weapon damage', 'EWeaponDamageScale': 'weapon damage',
                    'ELevelUpBoons': 'boon', 'ELightMeleeDamage': 'light melee damage', 'EHealingOutput': 'healing',
                    'ETechRange': 'range'}
# scale functions that name their stat by class, not by m_eSpecificStatScaleType
SCALE_CLASS_STAT = {'scale_function_healing_boon_scale': 'ELevelUpBoons',
                    'scale_function_base_weapon_damage': 'EBaseWeaponDamageIncrease',
                    'scale_function_ability_weapon_damage': 'EWeaponPower'}


def scale_stat(data: dict | None, prop: str) -> str | None:
    """The stat an ability property's coefficient multiplies (ETechPower, ELevelUpBoons…), from the data."""
    d = ((data or {}).get('m_mapAbilityProperties') or {}).get(prop)
    sf = d.get('m_subclassScaleFunction') if isinstance(d, dict) else None
    if not isinstance(sf, dict):
        return None
    return sf.get('m_eSpecificStatScaleType') or SCALE_CLASS_STAT.get(str(sf.get('_class', '')))


def scaling_suffix(parts) -> str:
    """' (spirit scaling)', ' (weapon damage scaling ×)'… for an upgrade keyed like
    'Prop|EAddToScale|EBaseWeaponDamageIncrease' (or given its fields as a list)."""
    what = next((SCALE_STAT_WORDS[p] for p in parts if p in SCALE_STAT_WORDS), 'spirit')
    return f' ({what} scaling ×)' if 'EMultiplyScale' in parts else f' ({what} scaling)'


_TIER_RE = re.compile(r'^m_vecAbilityUpgrades\[(\d+)\]\.m_vecPropertyUpgrades\{([^}]+)\}\.(\w+)$')
_PROP_RE = re.compile(r'^m_mapAbilityProperties\.([^.]+)\.(.+)$')
_CORRUPTED_RE = re.compile(r'^m_CorruptedItemInfo\.m_Upgrade\.m_vecPropertyUpgrades\{([^}]+)\}\.m_strBonus$')


def describe(path: str, tok: dict[str, str], entity: str = '', kind: str = '', scaled_by: str | None = None,
             token: str | None = None) -> dict:
    """{label, meters, group[, unit]} for a field path of an entity. `scaled_by`: the stat the property's
    coefficient multiplies (scale_stat), so a coefficient reads "(boon scaling)", not "(spirit scaling)".
    `token`: the property's m_strLocTokenOverride — the tooltip's own label and unit."""
    d = _describe(path, tok, entity, kind, token)
    word = SCALE_STAT_WORDS.get(scaled_by or '')
    if word and '(spirit scaling' in d['label']:
        d = {**d, 'label': d['label'].replace('(spirit scaling', f'({word} scaling')}
    if not d.get('unit') and d.get('meters') is False and d['group'] in _TIMED_GROUPS:
        name = d.get('prop') or re.sub(r'\{.*\}|\[\d+\]', '', path.rsplit('.', 1)[-1])
        if _TIME_FIELD.search(name):
            d = {**d, 'unit': 's'}
    # "Dash Jump Distance (m) 18m → 19m": the value carries the unit, the label need not say it
    if ' (m)' in d['label'] and (d.get('meters') in (METRES, True) or d.get('unit') == 'm'):
        d = {**d, 'label': d['label'].replace(' (m)', '')}
    if ' (s)' in d['label'] and d.get('unit') == 's':
        d = {**d, 'label': d['label'].replace(' (s)', '')}
    return d


# a time the game keeps in seconds but no tooltip names (advisor round 4: Fire Interval, Reload Time,
# Bullet Lifetime… 1,867 rows without "s"); a T1-T3 bonus or a corrupted value keeps its own unit
_TIME_FIELD = re.compile(r'(Time|Duration|Delay|Interval|Cooldown|Lifetime|InSeconds)$')
_TIMED_GROUPS = ('weapon', 'unit', 'other', 'property', 'powerup')


def _prop_label(tok: dict[str, str], prop: str, entity: str = '', token: str | None = None) -> tuple[str, str]:
    """(label, 'loc' | 'fallback'): the tooltip's label of a property, else its name split into words."""
    label = override_label(tok, token, entity) or _loc_label(tok, prop, entity)
    return (label, 'loc') if label else (humanize(prop), 'fallback')


def _describe(path: str, tok: dict[str, str], entity: str = '', kind: str = '', token: str | None = None) -> dict:
    """See describe(); 'src' says where the label came from: 'loc' (the game's text of that build),
    'curated' (our words for a field the game never labels) or 'fallback' (the field's name)."""
    d = _describe_raw(path, tok, entity, kind, token)
    d.setdefault('src', 'curated')
    return d


def _describe_raw(path: str, tok: dict[str, str], entity: str = '', kind: str = '', token: str | None = None) -> dict:
    m = _CORRUPTED_RE.match(path)
    if m:
        prop = m.group(1).split('|')[0]
        label, src = _prop_label(tok, prop, entity)
        # a corrupted bonus carries its property's unit like any bonus ("Incoming Healing -25" had none)
        return {'label': f'Corrupted: {label}', 'meters': False, 'group': 'corrupted', 'prop': prop, 'src': src,
                'unit': prop_unit(tok, prop)}
    if path.startswith('m_CorruptedItemInfo.'):
        return {'label': 'Corrupted: ' + context_label(path.split('.', 1)[1], 2, tok), 'meters': False, 'group': 'corrupted',
                'src': 'fallback'}
    m = _PROP_RE.match(path)
    if m:
        prop, rest = m.group(1), m.group(2)
        label, src = _prop_label(tok, prop, entity, token)
        if rest == 'm_strValue':
            unit = prop_unit(tok, prop, token)
            return {'label': label, 'meters': SPEED if prop_speed(prop, unit) else False, 'group': 'property',
                    'prop': prop, 'unit': unit, 'speed_m': speed_prop(prop), 'src': src,
                    'sign': prop_sign(tok, prop, token)}
        if rest == 'm_strStreetBrawlValue':
            return {'label': f'{label} (Street Brawl)', 'meters': False, 'group': 'streetbrawl', 'prop': prop, 'src': src}
        if rest.endswith('m_flStatScale'):
            return {'label': f'{label} (spirit scaling)', 'meters': False, 'group': 'scaling', 'prop': prop, 'src': src}
        return {'label': f'{label} · {humanize(rest.rsplit(".", 1)[-1])}', 'meters': False, 'group': 'property-meta',
                'prop': prop, 'src': src}
    m = _TIER_RE.match(path)
    if m:
        tier, key, field = int(m.group(1)) + 1, m.group(2), m.group(3)
        parts = key.split('|')
        prop = parts[0]
        label, src = _prop_label(tok, prop, entity, token)
        scaling = 'EAddToScale' in parts or 'EMultiplyScale' in parts
        if scaling:
            label += scaling_suffix(parts)
        if field == 'm_strStreetBrawlBonus':
            label += ' (Street Brawl)'
        elif field != 'm_strBonus':
            label += f' · {humanize(field)}'
        if 'EMultiplyBase' in parts:
            label += ' (% of base)'                 # Ground Strike T3 "+120%", not a flat +120
        # an item's only upgrade entry is its Enhanced version (Street Brawl's draft): "Enhanced
        # Escalating Exposure: shred +8 → +10" in the notes, "Upgrade:" on 646 rows until 2026-10-01
        # a hero's ability filed as a weapon by its class (Venator's ultimate) has T1-T3 too: "Upgrade: Bonus
        # Damage 150 → 65" where the notes say "T2" (audit 2026-10-04)
        prefix = (f'T{tier}' if kind in ('ability', 'ability_other', '', 'weapon', 'melee', 'shared')
                  else 'Enhanced' if kind == 'item' else 'Upgrade')
        unit = '%' if 'EMultiplyBase' in parts else '' if scaling or field != 'm_strBonus' else prop_unit(tok, prop, token)
        # a flat bonus to a travel speed is engine units/s like the speed (Lunge's T3 Dash Speed +550)
        plain = field == 'm_strBonus' and not scaling and 'EMultiplyBase' not in parts
        speed = plain and prop_speed(prop, unit)
        return {'label': f'{prefix}: {label}', 'meters': SPEED if speed else False, 'group': 'tier', 'prop': prop,
                'tier': tier, 'unit': unit, 'speed_m': speed_prop(prop), 'src': src,
                'sign': prop_sign(tok, prop, token) if plain else None}
    if path.startswith('m_mapStartingStats.'):
        stat = path.split('.')[1]
        if stat == 'EStaminaRegenPerSecond':
            # stamina per second (0.2) is what the game prints as a stamina cooldown (5s)
            return {'label': 'Stamina Cooldown', 'meters': False, 'group': 'stat', 'unit': 's', 'invert': True}
        # the stat panel's postfix is for BONUSES; a base value keeps a length, speed, time or a
        # resist's % — not a multiplier's ("Crit Bonus Scale 1% → 0.8%") or a regen's
        unit = stat_unit(tok, stat).strip()
        if stat.endswith('Speed') and unit == 'm':
            unit = 'm/s'                         # Valve's run / sprint postfix says "m" since 2026-01
        elif re.search(r'(Duration|Time|Cooldown)$', stat):
            unit = 's'
        elif unit == '%' and re.search(r'(Scale|Regen|PerSecond|Rate)', stat):
            unit = ''
        label, src = stat_label_src(tok, stat)
        return {'label': label, 'meters': False, 'group': 'stat', 'src': src,
                'unit': unit if unit in ('m', 'm/s', 's', '%') else ''}
    if path.startswith('m_mapStandardLevelUpUpgrades.'):
        mod = path.split('.')[1]
        loc_label = None if mod in LEVEL_UP_LABELS else _loc_label(tok, mod)
        label = LEVEL_UP_LABELS.get(mod) or loc_label or humanize(mod.replace('MODIFIER_VALUE_', '').lower())
        src = 'curated' if mod in LEVEL_UP_LABELS else 'loc' if loc_label else 'fallback'
        # range per boon is engine units (48 -> 59 is 1.22 -> 1.5 m, as the 2025-09-04 notes say)
        meters = mod == 'MODIFIER_VALUE_BONUS_ATTACK_RANGE'
        unit = '%' if 'RESIST' in mod else ''
        return {'label': label, 'meters': meters, 'group': 'levelup', 'unit': unit, 'src': src}
    if path.startswith('m_mapScalingStats.'):
        stat = path.split('.')[1]
        label, src = stat_label_src(tok, stat)
        return {'label': f'{label} per Spirit', 'meters': False, 'group': 'scaling', 'src': src}
    if path.startswith('m_mapWeaponInfos.') and not _SCATTER_RE.search(path):
        # (a shotgun's pellet offsets read "Scatter Offsets[10]" until 2026-10-04: plain_label names them)
        field = path.split('.')[2] if path.count('.') >= 2 else path
        src = 'curated' if field in WEAPON_FIELDS else 'fallback'
        label, meters = WEAPON_FIELDS.get(field, (humanize(field), engine_unit(field)))
        slot = path.split('.')[1]
        if slot != 'primary':
            label = f'{label} ({humanize(slot)})'
        return {'label': label, 'meters': meters, 'group': 'weapon', 'src': src}
    plain = plain_label(path)
    if plain:
        return plain
    leaf = path.rsplit('.', 1)[-1]
    leaf = re.sub(r'\{.*\}|\[\d+\]', '', leaf)
    if leaf in UNIT_FIELDS:
        label, meters = UNIT_FIELDS[leaf]
        parent = path.rsplit('.', 2)[-2] if path.count('.') >= 1 else ''
        if parent.startswith('m_VS'):
            label = f'{label} vs {humanize(parent[4:])}'
        m = _EMPOWERED_RE.search(path)
        if m:
            label = f'{label} (empowered, stage {m.group(1)})'
        m = _WEAK_POINT_RE.search(path)
        if m:
            label = f'Weak point ({m.group(1)}): {label[:1].lower() + label[1:]}'
        return {'label': label, 'meters': meters, 'group': 'unit'}
    return {'label': context_label(path, tok=tok), 'meters': engine_unit(leaf), 'group': 'other', 'src': 'fallback'}


# ---- plain words for structures the game never labels (audit 2026-10-01) ----------------------
SHOP_SLOT = {'WeaponMod': 'Weapon', 'Armor': 'Vitality', 'Tech': 'Spirit'}
_LEVEL_RE = re.compile(r'^m_mapLevelInfo\.(?:"?)(\d+)(?:"?)\.(.+)$')
_LEVEL_FIELD = {'m_unRequiredGold': 'souls needed', 'm_bUseStandardUpgrade': 'gives a boon',
                'm_mapBonusCurrencies.EAbilityPoints': 'ability points',
                'm_mapBonusCurrencies.EAbilityUnlocks': 'ability unlocks'}
# a step by its index (old records) or by its souls threshold ({6400}, flatten.NUMERIC_ID_FIELDS)
_INVEST_RE = re.compile(r'^m_MapModCostBonuses\.EItemSlotType_(\w+)(?:\[(\d+)\]|\{(\d+)\})\.(\w+)$')
_INVEST_FIELD = {'flBonus': 'bonus', 'nGoldThreshold': 'souls spent', 'flPercentOnGraph': 'bar width'}
_PURCHASE_RE = re.compile(r'^m_mapPurchaseBonuses\.EItemSlotType_(\w+)(?:\[(\d+)\]|\{(\d+)\})\.(\w+)$')
_BOUND_RE = re.compile(r'^m_mapBoundAbilities\.ESlot_(\w+)$')
_POWERUP_VALUE_RE = re.compile(r'^m_sModifer\.m_vecModifierValues\{MODIFIER_VALUE_([A-Z_]+)\}\.m_value(Min|Max)$')
_EMPOWERED_RE = re.compile(r'm_EmpoweredModifierLevel(\d+)\.')
_WEAK_POINT_RE = re.compile(r'm_vecWeakPoints\{([^}]+)\}')
_SCATTER_RE = re.compile(r'm_vecScatterOffsets')


def _slot_name(slot: str) -> str:
    m = re.match(r'Signature_(\d)$', slot)
    if m:
        return 'Ultimate' if m.group(1) == '4' else f'Ability {m.group(1)}'
    return {'Weapon_Primary': 'Weapon', 'Weapon_Secondary': 'Alt weapon', 'Weapon_Melee': 'Melee'}.get(
        slot, humanize(slot.replace('Ability_', '')))


def plain_label(path: str) -> dict | None:
    """'m_mapLevelInfo."22".m_unRequiredGold' -> 'Level 22: souls needed', investment bonuses,
    the hero's kit slots, powerups, the shotgun pellet pattern."""
    m = _LEVEL_RE.match(path)
    if m and m.group(2) in _LEVEL_FIELD:
        return {'label': f'Level {m.group(1)}: {_LEVEL_FIELD[m.group(2)]}', 'meters': False, 'group': 'levels'}
    m = _INVEST_RE.match(path)
    if m:
        slot = SHOP_SLOT.get(m.group(1), m.group(1))
        field = _INVEST_FIELD.get(m.group(4), humanize(m.group(4)))
        where = f'at {int(m.group(3)):,} souls' if m.group(3) else f', step {int(m.group(2)) + 1}'
        return {'label': f'{slot} investment {where}: {field}'.replace(' ,', ','), 'meters': False, 'group': 'investment'}
    m = _PURCHASE_RE.match(path)
    if m:
        slot = SHOP_SLOT.get(m.group(1), m.group(1))
        tier = int(m.group(3)) if m.group(3) else int(m.group(2)) + 1      # keyed by its tier, or an old index
        return {'label': f'{slot} purchase bonus, tier {tier}: {humanize(m.group(4)).lower()}',
                'meters': False, 'group': 'investment'}
    m = _BOUND_RE.match(path)
    if m:
        return {'label': f'Kit: {_slot_name(m.group(1))}', 'meters': False, 'group': 'kit'}
    m = _POWERUP_VALUE_RE.match(path)
    if m:
        stage = 'early game' if m.group(2) == 'Min' else 'late game'
        # only a trailing _PERCENT: '_PERCENTAGE' left "Cooldown Reductionage" (audit 2026-10-01)
        what = re.sub(r'_PERCENT(AGE)?$', '', m.group(1)).replace('_', ' ').title()
        # a sprint / move speed bonus is engine units (78.74 -> 118.11 is 2 -> 3 m/s)
        return {'label': f'Powerup: {what} ({stage})', 'meters': SPEED if 'SPEED' in m.group(1) and 'PERCENT' not in m.group(1)
                else False, 'group': 'powerup'}
    if path == 'm_sModifer.m_flDuration':
        return {'label': 'Powerup: buff duration', 'meters': False, 'group': 'powerup'}
    if _SCATTER_RE.search(path):
        return {'label': 'Pellet pattern', 'meters': False, 'group': 'weapon'}
    return None


_ENUM_PREFIX_RE = re.compile(r'^(EItemSlotType_|MODIFIER_VALUE_|ESlot_|EModTier_|E(?=[A-Z][a-z]))')


_TYPED_FIELD = re.compile(r'^(?:fl|n|i|b|str|vec|map|un|s|v|h|bits|sz|e)[A-Z][a-z]')


def _segment(seg: str, tok: dict[str, str] | None = None) -> str:
    m = re.match(r'^([^\[{]+)(?:\[(\d+)\]|\{([^}]*)\})?$', seg)
    if not m:
        return humanize(seg)
    name, idx, key = m.group(1), m.group(2), m.group(3)
    # a field name with a type prefix but no "m_" ("flCooldownOnBreak" of the shield trackers sat raw)
    field = name.startswith(('m_', '_')) or bool(_TYPED_FIELD.match(name))
    if not field and _ID_KEY.match(name) and _id_name(name, tok):
        text = _id_name(name, tok)            # an item / ability id as a segment: its name
    else:
        text = humanize(_ENUM_PREFIX_RE.sub('', name)) if field else \
            game_words(_ENUM_PREFIX_RE.sub('', name).replace('_', ' ').strip())
    if idx is not None:
        text += f' #{int(idx) + 1}'
    if key:
        text += f' {_key_text(key.split("|")[0], tok)}'
    return text


_ID_KEY = re.compile(r'^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$')
_ID_PREFIX = re.compile(r'^(?:npc_|citadel_|modifier_|ability_|upgrade_)+')


def _id_name(key: str, tok: dict[str, str] | None) -> str | None:
    """The game's name of an item / ability / hero id ("upgrade_deflecting_armor" -> its shop name),
    from the same build's text; None when it has none."""
    if not tok:
        return None
    name = tok.get(key) or tok.get(f'{key}:n')
    name = html.unescape(re.sub(r'<[^>]+>', '', name)).strip() if name else ''
    return name if name and '{' not in name else None


def _key_text(key: str, tok: dict[str, str] | None = None) -> str:
    """A map key that is an internal id reads as words: 'Intrinsic Modifiers npc_boss_intrinsic' sat on
    30 Walker rows (2026-10-03) -> 'Intrinsic Modifiers boss intrinsic'; an id the game names reads as
    that name ('Item Draft Weights › upgrade deflecting armor' -> the item's shop name, audit
    2026-10-04). Other keys stay as they are."""
    if not _ID_KEY.match(key):
        return key
    return _id_name(key, tok) or _ID_PREFIX.sub('', key).replace('_', ' ')


# containers and flag fields a player knows by another name (audit 2026-10-01: 1,677 rows read
# "Projectile Info › Speed", "Modifer › Script Values MODIFIER_VALUE_… › Value", "Ability Behaviors Bits")
CONTAINER_WORDS = {'m_projectileInfo': 'Projectile', 'm_mapAttacks': '', 'EAttackType_Heavy': 'Heavy melee',
                   'EAttackType_Light': 'Light melee', 'EAttackType_HeavyAir': 'Air heavy melee',
                   'EAttackType_Slide': 'Slide melee', 'm_deploymentInfo': 'Deploy', 'm_sModifer': 'Effect',
                   'm_sModifier': 'Effect', 'm_ModifierProvidedByAura': 'Aura', 'm_FriendlyAuraModifier': 'Ally aura',
                   'm_ObjectiveRegen': 'Regen', 'm_EnemyTrooperDamageReduction': 'Vs troopers',
                   # a unit's always-on modifier, by its id: "Intrinsic Modifiers boss intrinsic › …" (round 4)
                   'm_vecIntrinsicModifiers': 'Passive',
                   # the modifiers players know by what they are (data-quality audit 2026-10-04: "Rebirth
                   # Modifier › Duration", "Stagger Watcher Modifier › Build Up Modifier › …")
                   'm_RebirthModifier': 'Rejuvenator buff', 'm_TargetModifier': 'On target',
                   'm_BuildUpModifier': 'Build-up', 'm_StaggerWatcherModifier': 'Stagger'}
FLAG_FIELDS = {'m_AbilityBehaviorsBits': 'Behaviour', 'm_nAbilityBehaviors': 'Behaviour',
               'm_nAbilityTargetTypes': 'Can target', 'm_nAbilityTargetFlags': 'Targeting rules',
               'm_bitsInterruptingStates': 'Interrupted by', 'm_nBehaviors': 'Behaviour',
               'm_eAbilityTargetingLocation': 'Targeting', 'm_eAbilityTargetingShape': 'Targeting shape',
               # the states a modifier puts on its holder, and the ones it shields the holder from
               'm_nEnabledStateMask': 'Applies', 'm_nDisabledStateMask': 'Immune to',
               'm_iAuraSearchType': 'Aura affects', 'm_eItemSlotType': 'Item slot', 'm_eAbilityActivation': 'Activation',
               # a crowd control that wears off faster on a target hit by it again (Air Drop's grab, 2026-09-29)
               'm_bDurationReducibleByCrowdControlDiminish': 'Reduced by CC diminishing returns'}
_SCRIPT_VALUE = re.compile(r'^m_vec(?:Script|Modifier)Values\{(?:MODIFIER_VALUE_)?([A-Z0-9_]+)[^}]*\}$')
# the value leaf under a script / modifier value ("Effect › Modifier Values MODIFIER_VALUE_STAMINA ›
# Modifier Value" on powerups until 2026-10-02)
_VALUE_LEAF = re.compile(r'^m_(?:fl)?(?:[mM]odifier)?[vV]alue$')


_MODIFIER_TAIL = re.compile(r'(?<=[a-z])Modifier$')


def _context_segment(seg: str, tok: dict[str, str] | None = None, container: bool = False) -> str:
    m = _SCRIPT_VALUE.match(seg)
    if m:                                    # what the modifier changes: "Cooldown Reduction Percentage"
        return game_words(m.group(1).replace('_', ' ').title())
    base = re.sub(r'[\[{].*$', '', seg)
    if base in FLAG_FIELDS:
        return FLAG_FIELDS[base]
    if base in CONTAINER_WORDS:
        return CONTAINER_WORDS[base]
    if container and base.startswith('m_') and _MODIFIER_TAIL.search(base):
        # a container named after its modifier says what it is without the word: "Grab › Duration", not
        # "Grab Modifier › Duration" (281 rows on 46 pages, audit 2026-10-04)
        seg = _MODIFIER_TAIL.sub('', base) + seg[len(base):]
    return _segment(seg, tok)


def context_label(path: str, depth: int = 3, tok: dict[str, str] | None = None) -> str:
    """'m_mapPurchaseBonuses.EItemSlotType_WeaponMod[2].m_flValue'
    -> 'Purchase Bonuses › WeaponMod #3 › Value' (a bare leaf name is meaningless);
    'm_projectileInfo.m_flSpeed' -> 'Projectile › Speed'; a modifier's script value is named by what
    it changes, its trailing '.m_value' dropped; a word repeated by the path once. `tok`: the build's
    text, so an id the game names reads as its name."""
    parts = [p for p in path.split('.') if p]
    if len(parts) > 1 and _VALUE_LEAF.match(parts[-1]) and _SCRIPT_VALUE.match(parts[-2]):
        parts = parts[:-1]
    shown = []
    tail = parts[-depth:]
    for i, p in enumerate(tail):
        s = _context_segment(p, tok, container=i < len(tail) - 1)
        if s and (not shown or shown[-1] != s):
            shown.append(s)
    return ' › '.join(shown)


_RAW_NUM = re.compile(r'^\s*([-+]?(?:\d+\.?\d*|\.\d+))\s*(m|s|%|u)?\s*$')
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
