"""Human meaning of diffed fields: labels, units, direction (BUFF/NERF).

Here: a field's polarity and a change's direction and its % step. The labels (`field_labels`: the game's own
localization of the same build wherever the game has one, `<Prop>_label`, `StatDesc_<Stat>`, and hand maps for
fields it never labels), the units (`field_units`) and the printed values (`display_values`) live in their own
modules and are re-exported here.
"""
from __future__ import annotations

import re

# split 2026-11-13 into field_units (units, lengths, speeds), display_values (a value as the page prints it) and
# field_labels (a field's words): every name is re-exported here for its callers
from .field_units import (BARE_LENGTH_MIN, ENGINE_LENGTH_MIN, FRACTION, METRES, MPS, M_SPEED, SPEED, UNITS_PER_METER,  # noqa: F401
                          _ALREADY_MPS, _BRACED, _ENDS_LENGTH, _FRACTION_FIELD, _FRACTION_PROP, _NOT_A_LENGTH,
                          _PLAIN_NUMBER, _PROP_LENGTH, _PROP_NOT_LENGTH, _PROP_NOT_TRAVEL, _PROP_RE, _PROP_SPEED,
                          _RATIO_WORD, _RAW_NUM, _SPEED_NAME, _TIER_RE, _VALUE_TAIL, bare_engine_length, engine_unit,
                          length_in_units, prop_speed, property_name, speed_prop, with_unit)
from .display_values import (NO_LIMIT_BIG, SENTINELS, SPEED_MULTIPLIER_MAX, _UNITS_ALWAYS, display_raw, display_value,  # noqa: F401
                             is_sentinel, metres_pair, reencoded, show, sign_flip, units_when_bare)
from .field_labels import (ATTRIBUTES_LEAF, CONTAINER_WORDS, CUSTOM_FIRST, CUSTOM_STAT_LABELS, FLAG_FIELDS,  # noqa: F401
                           LEVEL_UP_LABELS, PLAIN_FIELDS, RANKED_FIELDS, SCALED_LEAF, SCALE_CLASS_STAT,
                           SCALE_STAT_WORDS, SHOP_SLOT, STAT_DESC_EXCEPTIONS, TIER_PREFIX, UNIT_FIELDS,
                           WEAK_POINT_NAMES, WEAPON_FIELDS, _BOSS_FIELD, _BOSS_NAME, _BOSS_WHAT, _BOUND_RE, _CAMEL_RE,
                           _CONTAINER_WORDS_LOW, _CORRUPTED_RE, _EMPOWERED_RE, _ENUM_PREFIX_RE, _FLAG_FIELDS_LOW,
                           _GAME_WORDS, _ID_KEY, _ID_PREFIX, _INVEST_FIELD, _INVEST_RE, _LETTER, _LEVEL_FIELD,
                           _LEVEL_RE, _MODIFIER_TAIL, _MOVE_SPEED, _NOT_SECONDS, _NOT_SPEED_VALUE, _PARENS, _PCT_TAIL,
                           _PCT_WORD, _POWERUP_VALUE_RE, _PREFIX_RE, _PURCHASE_RE, _RANKED_ENTITY, _RESIST_VALUE,
                           _SAYS_LESS, _SCATTER_RE, _SCRIPT_VALUE, _SPEED_VALUE, _TIMED_GROUPS, _TIME_FIELD,
                           _TYPED_FIELD, _UNIT_WORDS, _VALUE_LEAF, _WEAK_POINT_RE, _context_segment, _describe,
                           _describe_raw, _id_name, _key_text, _loc_label, _names_something, _percent_word,
                           _prop_label, _segment, _slot_name, boss_field, context_label, describe, enemy_label,
                           fallback_unit, game_words, humanize, loc_items_prefix, override_label, plain_label,
                           prop_sign, prop_unit, readable_label, scale_stat, scaled_parent, scaling_suffix, stat_label,
                           stat_label_src, stat_unit, weak_point_field, weak_point_label, weak_point_name)


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
# (not "width", "window", "drain": a wider wall, a longer recast window, more life drained are better — the notes
# say so: Baba's windows "increased from 1 to 1.5")
_AMBIGUOUS = re.compile(r'(threshold|interval|angle|height|limit|required|needed|frequency|drag|weight|'
                        r'self|lost|loss|taken|stagger|slope|graph|^[xy]$)', re.I)
_SELF_SLOW = re.compile(r'(SlowOnHit|SlowFromRecentDamage)Modifier\.', re.I)
# … and what has to be bigger: health on respawn, a delay that grows with spirit, a bonus to the
# damage the ENEMY takes (Alchemical Fire), how long before rage drains
_HIGHER_FIRST = re.compile(r'(respawnhealth|wakeupdelay|draindelay|bonus\w*damagetaken|'
                           # the parried enemy takes it: "Parry bonus damage reduced from 30% to 25%" is a nerf
                           r'victimdamagetaken|meleedamagetakenscale)', re.I)
# fields where direction is not meaningful for the owner; also where a thing sits or how it eases in
# (a summoned card's offset, Ice Path's pitch limits, a grab's damping, a dragon's spring: 30 rows read
# BUFF / NERF, audit 2026-10-04). Bare yaw / pitch stay: a recoil or spread pitch has a side
_NEUTRAL = re.compile(r'(tangent|spline|curve|domain|seed|index|order|count_max_ui|_class|mask|bits|flags?$|updatetime|'
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
        # no word says which way is better: "more is better" holds for damage, health, duration, range…, but a
        # threshold, an interval, an angle or a window can go either way — CHANGED (AGENTS rule 7; data audit
        # 2026-11-13: Spirit Burn's "Damage Threshold 400 → 500" read BUFF)
        return 0 if _AMBIGUOUS.search(name) else 1
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
        x, y = float(old), float(new)
        if x == y:
            return 'changed', pct
        # UP / DOWN say which way the number went, so the percent goes with its sign: "-35 → -50 DOWN +42.9%"
        # contradicted itself on 76 unit rows (review 2026-10-05); it is -42.9%
        return ('up' if y > x else 'down'), None if x == 0 else (y - x) / abs(x) * 100.0
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
# (a 'helper' — the Hideout's copy of Sinner's Sacrifice, the bots — is a unit too: its rows read BUFF / NERF next
# to the same rows UP / DOWN on the unit's page; review 2026-10-05)
SHARED_KINDS = ('trooper', 'building', 'neutral', 'unit', 'global', 'helper')
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
