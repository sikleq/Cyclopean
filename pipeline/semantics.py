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
    r'bulletstofully|drainrate|durationformax|expandtime|spindecay|nonheroreduction)', re.I)
# … and what has to be bigger: health on respawn, a delay that grows with spirit, a bonus to the
# damage the ENEMY takes (Alchemical Fire), how long before rage drains
_HIGHER_FIRST = re.compile(r'(respawnhealth|wakeupdelay|draindelay|bonus\w*damagetaken)', re.I)
# fields where direction is not meaningful for the owner
_NEUTRAL = re.compile(r'(tangent|spline|curve|domain|seed|index|order|count_max_ui|_class|mask|bits|flags?$)', re.I)

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
    name = property_name(path)
    if _NEUTRAL.search(name):
        return 0
    if _HIGHER_FIRST.search(name):
        return 1
    if _LOWER_FIRST.search(name):
        return -1
    m = _LOWER_BETTER.search(name)
    if not m:
        return 1
    return 1 if _NEGATED.search(name[m.end():]) else -1


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
    if (float(old) in SENTINELS or float(new) in SENTINELS) and not UPGRADE_BONUS.search(path):
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
    'CritDamageReceivedScale': 'Headshot Damage Taken',
    'CritDamageBonusScale': 'Headshot Damage Bonus',
}

LEVEL_UP_LABELS = {
    'MODIFIER_VALUE_BASE_HEALTH_FROM_LEVEL': 'Health per boon',
    'MODIFIER_VALUE_BASE_BULLET_DAMAGE_FROM_LEVEL': 'Bullet damage per boon',
    'MODIFIER_VALUE_BASE_BULLET_DAMAGE_FROM_LEVEL_ALT_FIRE': 'Alt-fire damage per boon',
    'MODIFIER_VALUE_BASE_MELEE_DAMAGE_FROM_LEVEL': 'Melee damage per boon',
    'MODIFIER_VALUE_TECH_POWER': 'Spirit power per boon',
    'MODIFIER_VALUE_BULLET_ARMOR_DAMAGE_RESIST': 'Bullet resist per boon',
    'MODIFIER_VALUE_TECH_ARMOR_DAMAGE_RESIST': 'Spirit resist per boon',
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
                           r'Yaw|Pitch|Degree|Interval|Cooldown|Damage|Health|DPS|Resist|Reward|Bounty|Gold|Fov|Count)',
                           re.I)


def engine_unit(leaf: str) -> bool | str:
    """An engine float named like a length or a speed is in engine units: Walker 'Invul Modifier Range
    1338.58 → 866.14' is 34 → 22 m, a projectile 'Speed 1050 → 400' is 26.7 → 10.2 m/s (audit
    2026-10-01: 302 rows of abilities, 225 of units in raw units)."""
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
    'm_flDamageFalloffEndScale': ('Damage at Falloff End', False),
    'm_flRange': ('Max Range', True),
    'm_flCritBonusStart': ('Headshot Multiplier', False),
    'm_flCritBonusEnd': ('Headshot Multiplier (far)', False),
    'm_flCritBonusAgainstNPCs': ('Headshot Multiplier vs NPCs', False),
    'm_flBulletGravityScale': ('Bullet Gravity', False),
    'm_flBulletRadius': ('Bullet Radius', True),
    'm_Spread': ('Spread', False),
    'm_StandingSpread': ('Standing Spread', False),
    'm_flShootSpreadPenaltyPerShot': ('Spread per Shot', False),
    'm_flShootMoveSpeedPercent': ('Move Speed while Shooting', False),
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
}

# 'm_' always goes; a Hungarian type prefix goes when a capital follows ('m_flBonus', 'flBonus',
# 'nGoldThreshold'); 'm_projectileInfo' kept its 'm ' before (audit 2026-10-01: 193 labels)
_PREFIX_RE = re.compile(r'^(?:m_)?(?:(?:fl|n|i|b|str|e|vec|map|un|s|v|h|ar|bits|sz)(?=[A-Z]))?')
# split camelCase; keep plural acronyms whole ('NPCs' read 'NP Cs')
_CAMEL_RE = re.compile(r'(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z](?!s(?:[A-Z\d_]|$))[a-z])')
_UNIT_WORDS = ((' In Seconds', ' (s)'), (' In Meters', ' (m)'), (' Mins', ' (min)'))


def humanize(key: str) -> str:
    k = _PREFIX_RE.sub('', key)
    k = k.lstrip('_').replace('_', ' ')
    out = _CAMEL_RE.sub(' ', k).strip() or key
    for a, b in _UNIT_WORDS:
        out = out.replace(a, b)
    return out[:1].upper() + out[1:]


def _loc_label(tok: dict[str, str], name: str, ability: str | None = None) -> str | None:
    for key in ((f'{ability}_{name}_label' if ability else None), f'{name}_label', name):
        if key and key.lower() in tok:
            # loc text carries HTML entities ("Bullet &amp; Spirit Lifesteal"): plain text out
            val = html.unescape(re.sub(r'<[^>]+>', '', tok[key.lower()])).strip()
            if val and '{' not in val:
                return val
    return None


def stat_label(tok: dict[str, str], stat: str) -> str:
    base = stat[1:] if stat.startswith('E') and stat[1:2].isupper() else stat
    key = 'StatDesc_' + STAT_DESC_EXCEPTIONS.get(base, base)
    if key.lower() in tok:
        return re.sub(r'<[^>]+>', '', tok[key.lower()]).strip()
    return CUSTOM_STAT_LABELS.get(base) or humanize(base)


def override_label(tok: dict[str, str], token: str | None, entity: str = '') -> str | None:
    """The label the tooltip prints for a property with m_strLocTokenOverride: a property name
    ('BuffDuration' -> its _label) or a loc key ('#Citadel_…'). 293 rows said "Duration" where the
    game says "Shield Duration" (audit 2026-10-01)."""
    if not token:
        return None
    if token.startswith('#'):
        val = tok.get(token[1:].lower())
        return html.unescape(re.sub(r'<[^>]+>', '', val)).strip() if val and '{' not in val else None
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
    return d


def _describe(path: str, tok: dict[str, str], entity: str = '', kind: str = '', token: str | None = None) -> dict:
    m = _CORRUPTED_RE.match(path)
    if m:
        prop = m.group(1).split('|')[0]
        label = _loc_label(tok, prop, entity) or humanize(prop)
        return {'label': f'Corrupted: {label}', 'meters': False, 'group': 'corrupted', 'prop': prop}
    if path.startswith('m_CorruptedItemInfo.'):
        return {'label': 'Corrupted: ' + context_label(path.split('.', 1)[1], 2), 'meters': False, 'group': 'corrupted'}
    m = _PROP_RE.match(path)
    if m:
        prop, rest = m.group(1), m.group(2)
        label = override_label(tok, token, entity) or _loc_label(tok, prop, entity) or humanize(prop)
        if rest == 'm_strValue':
            return {'label': label, 'meters': False, 'group': 'property', 'prop': prop,
                    'unit': prop_unit(tok, prop, token)}
        if rest == 'm_strStreetBrawlValue':
            return {'label': f'{label} (Street Brawl)', 'meters': False, 'group': 'streetbrawl', 'prop': prop}
        if rest.endswith('m_flStatScale'):
            return {'label': f'{label} (spirit scaling)', 'meters': False, 'group': 'scaling', 'prop': prop}
        return {'label': f'{label} · {humanize(rest.rsplit(".", 1)[-1])}', 'meters': False, 'group': 'property-meta', 'prop': prop}
    m = _TIER_RE.match(path)
    if m:
        tier, key, field = int(m.group(1)) + 1, m.group(2), m.group(3)
        parts = key.split('|')
        prop = parts[0]
        label = override_label(tok, token, entity) or _loc_label(tok, prop, entity) or humanize(prop)
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
        prefix = (f'T{tier}' if kind in ('ability', 'ability_other', '')
                  else 'Enhanced' if kind == 'item' else 'Upgrade')
        unit = '%' if 'EMultiplyBase' in parts else '' if scaling or field != 'm_strBonus' else prop_unit(tok, prop, token)
        return {'label': f'{prefix}: {label}', 'meters': False, 'group': 'tier', 'prop': prop, 'tier': tier, 'unit': unit}
    if path.startswith('m_mapStartingStats.'):
        stat = path.split('.')[1]
        return {'label': stat_label(tok, stat), 'meters': False, 'group': 'stat', 'unit': stat_unit(tok, stat)}
    if path.startswith('m_mapStandardLevelUpUpgrades.'):
        mod = path.split('.')[1]
        label = LEVEL_UP_LABELS.get(mod) or _loc_label(tok, mod) or humanize(mod.replace('MODIFIER_VALUE_', '').lower())
        return {'label': label, 'meters': False, 'group': 'levelup'}
    if path.startswith('m_mapScalingStats.'):
        stat = path.split('.')[1]
        return {'label': f'{stat_label(tok, stat)} per Spirit', 'meters': False, 'group': 'scaling'}
    if path.startswith('m_mapWeaponInfos.'):
        field = path.split('.')[2] if path.count('.') >= 2 else path
        label, meters = WEAPON_FIELDS.get(field, (humanize(field), engine_unit(field)))
        slot = path.split('.')[1]
        if slot != 'primary':
            label = f'{label} ({humanize(slot)})'
        return {'label': label, 'meters': meters, 'group': 'weapon'}
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
    return {'label': context_label(path), 'meters': engine_unit(leaf), 'group': 'other'}


# ---- plain words for structures the game never labels (audit 2026-10-01) ----------------------
SHOP_SLOT = {'WeaponMod': 'Weapon', 'Armor': 'Vitality', 'Tech': 'Spirit'}
_LEVEL_RE = re.compile(r'^m_mapLevelInfo\.(?:"?)(\d+)(?:"?)\.(.+)$')
_LEVEL_FIELD = {'m_unRequiredGold': 'souls needed', 'm_bUseStandardUpgrade': 'gives a boon',
                'm_mapBonusCurrencies.EAbilityPoints': 'ability points',
                'm_mapBonusCurrencies.EAbilityUnlocks': 'ability unlocks'}
_INVEST_RE = re.compile(r'^m_MapModCostBonuses\.EItemSlotType_(\w+)\[(\d+)\]\.(\w+)$')
_INVEST_FIELD = {'flBonus': 'bonus', 'nGoldThreshold': 'souls spent', 'flPercentOnGraph': 'bar width'}
_PURCHASE_RE = re.compile(r'^m_mapPurchaseBonuses\.EItemSlotType_(\w+)\[(\d+)\]\.(\w+)$')
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
        return {'label': f'{slot} investment, step {int(m.group(2)) + 1}: {_INVEST_FIELD.get(m.group(3), humanize(m.group(3)))}',
                'meters': False, 'group': 'investment'}
    m = _PURCHASE_RE.match(path)
    if m:
        slot = SHOP_SLOT.get(m.group(1), m.group(1))
        return {'label': f'{slot} purchase bonus, tier {int(m.group(2)) + 1}: {humanize(m.group(3)).lower()}',
                'meters': False, 'group': 'investment'}
    m = _BOUND_RE.match(path)
    if m:
        return {'label': f'Kit: {_slot_name(m.group(1))}', 'meters': False, 'group': 'kit'}
    m = _POWERUP_VALUE_RE.match(path)
    if m:
        stage = 'early game' if m.group(2) == 'Min' else 'late game'
        what = m.group(1).replace('_PERCENT', '').replace('_', ' ').title()
        return {'label': f'Powerup: {what} ({stage})', 'meters': False, 'group': 'powerup'}
    if path == 'm_sModifer.m_flDuration':
        return {'label': 'Powerup: buff duration', 'meters': False, 'group': 'powerup'}
    if _SCATTER_RE.search(path):
        return {'label': 'Pellet pattern', 'meters': False, 'group': 'weapon'}
    return None


_ENUM_PREFIX_RE = re.compile(r'^(EItemSlotType_|MODIFIER_VALUE_|ESlot_|EModTier_|E(?=[A-Z][a-z]))')


def _segment(seg: str) -> str:
    m = re.match(r'^([^\[{]+)(?:\[(\d+)\]|\{([^}]*)\})?$', seg)
    if not m:
        return humanize(seg)
    name, idx, key = m.group(1), m.group(2), m.group(3)
    text = humanize(_ENUM_PREFIX_RE.sub('', name)) if name.startswith(('m_', '_')) else \
        _ENUM_PREFIX_RE.sub('', name).replace('_', ' ').strip()
    if idx is not None:
        text += f' #{int(idx) + 1}'
    if key:
        text += f' {key.split("|")[0]}'
    return text


# containers and flag fields a player knows by another name (audit 2026-10-01: 1,677 rows read
# "Projectile Info › Speed", "Modifer › Script Values MODIFIER_VALUE_… › Value", "Ability Behaviors Bits")
CONTAINER_WORDS = {'m_projectileInfo': 'Projectile', 'm_mapAttacks': '', 'EAttackType_Heavy': 'Heavy melee',
                   'EAttackType_Light': 'Light melee', 'EAttackType_HeavyAir': 'Air heavy melee',
                   'EAttackType_Slide': 'Slide melee', 'm_deploymentInfo': 'Deploy', 'm_sModifer': 'Effect',
                   'm_sModifier': 'Effect', 'm_ModifierProvidedByAura': 'Aura', 'm_FriendlyAuraModifier': 'Ally aura',
                   'm_ObjectiveRegen': 'Regen', 'm_EnemyTrooperDamageReduction': 'Vs troopers'}
FLAG_FIELDS = {'m_AbilityBehaviorsBits': 'Behaviour', 'm_nAbilityBehaviors': 'Behaviour',
               'm_nAbilityTargetTypes': 'Can target', 'm_nAbilityTargetFlags': 'Targeting rules',
               'm_bitsInterruptingStates': 'Interrupted by', 'm_nBehaviors': 'Behaviour',
               'm_eAbilityTargetingLocation': 'Targeting', 'm_eAbilityTargetingShape': 'Targeting shape'}
_SCRIPT_VALUE = re.compile(r'^m_vecScriptValues\{(?:MODIFIER_VALUE_)?([A-Z0-9_]+)[^}]*\}$')


def _context_segment(seg: str) -> str:
    m = _SCRIPT_VALUE.match(seg)
    if m:                                    # what the modifier changes: "Cooldown Reduction Percentage"
        return m.group(1).replace('_', ' ').title()
    base = re.sub(r'[\[{].*$', '', seg)
    if base in FLAG_FIELDS:
        return FLAG_FIELDS[base]
    if base in CONTAINER_WORDS:
        return CONTAINER_WORDS[base]
    return _segment(seg)


def context_label(path: str, depth: int = 3) -> str:
    """'m_mapPurchaseBonuses.EItemSlotType_WeaponMod[2].m_flValue'
    -> 'Purchase Bonuses › WeaponMod #3 › Value' (a bare leaf name is meaningless);
    'm_projectileInfo.m_flSpeed' -> 'Projectile › Speed'; a modifier's script value is named by what
    it changes, its trailing '.m_value' dropped; a word repeated by the path once."""
    parts = [p for p in path.split('.') if p]
    if len(parts) > 1 and parts[-1] == 'm_value' and _SCRIPT_VALUE.match(parts[-2]):
        parts = parts[:-1]
    shown = []
    for p in parts[-depth:]:
        s = _context_segment(p)
        if s and (not shown or shown[-1] != s):
            shown.append(s)
    return ' › '.join(shown)


_RAW_NUM = re.compile(r'^\s*([-+]?(?:\d+\.?\d*|\.\d+))\s*(m|s|%|u)?\s*$')
# "no limit" / "none" written as a number: Channel Move Speed 50 -> -1 is not a -98% nerf
SENTINELS = (-1.0, -2.0, 9999.0, 99999.0)


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


def display_raw(v, meters: bool | str = False) -> str:
    """A value as the records keep it (a number, or a string such as "12.19m"): a number written
    in metres is not divided again, engine units are."""
    if isinstance(v, str):
        m = _RAW_NUM.match(v)
        if m:
            x = float(m.group(1))
            if m.group(2) == 'm':
                return display_value(x) + ('m/s' if meters == SPEED else 'm')
            return display_value(x, meters)
    return display_value(v, meters)


def display_value(v, meters: bool | str = False) -> str:
    if v is None:
        return '—'
    if isinstance(v, bool):
        return 'yes' if v else 'no'
    if isinstance(v, (int, float)):
        x = float(v) / UNITS_PER_METER if meters else float(v)
        if x.is_integer():
            s = str(int(x))
        elif abs(x) < 1:
            # small coefficients need their own digits: 4 significant ones (Fixation's T3 scaling
            # 0.0003 -> 0.00035 read "0.0003 -> 0.0003" with 4 decimals), never "1e-05"
            s = f'{float(f"{x:.4g}"):.8f}'.rstrip('0').rstrip('.')
        else:
            s = f'{x:.2f}'.rstrip('0').rstrip('.')
        return s + ('m/s' if meters == SPEED else 'm' if meters else '')
    if isinstance(v, list):
        return ', '.join(display_value(x) for x in v)
    return str(v)
