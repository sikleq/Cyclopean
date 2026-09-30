"""Human meaning of diffed fields: labels, units, direction (BUFF/NERF).

Labels come from the game's own localization of the same build wherever the
game has one (`<Prop>_label`, `StatDesc_<Stat>`); the small hand maps below
cover fields the game never labels (weapon internals, NPC fields).
"""
from __future__ import annotations

import re

UNITS_PER_METER = 39.37

# ---- direction -----------------------------------------------------------

# property/stat name fragments where a LOWER value is better for the owner
_LOWER_BETTER = re.compile(
    r'(cooldown|castdelay|cast_delay|casttime|reload|cycletime|spread|cost|price|'
    r'windup|lockout|recoil|delay(?!ed)|critdamagereceived|damagetaken|selfdamage|'
    r'chargetime|channeltime|backswing|fallofstart|penalty|fadetime|arming|'
    r'm_unrequiredgold|goldthreshold|requiredgold|resurrectiontime|respawn)',
    re.I,
)
# fields where direction is not meaningful for the owner
_NEUTRAL = re.compile(r'(tangent|spline|curve|domain|seed|index|order|count_max_ui|_class|mask|bits|flags?$)', re.I)

GRADIENT_STEPS = (5, 10, 15, 20, 25, 33, 45, 60, 80)


def polarity(path: str) -> int:
    """+1 higher is better, -1 lower is better, 0 no direction."""
    leaf = re.sub(r'\.m_strValue$|\.m_strBonus$|\.m_flStatScale$|\.flScale$', '', path)
    if _NEUTRAL.search(leaf.rsplit('.', 1)[-1]):
        return 0
    return -1 if _LOWER_BETTER.search(leaf) else 1


def direction(path: str, old, new, kind: str = '') -> tuple[str, float | None]:
    """('buff'|'nerf'|'changed', signed percent or None) for a numeric change.

    Magnitudes are compared (|x|): debuffs are stored as negative numbers
    ("-8% resist"), so going -8 -> -7 is a weaker effect.
    Units (troopers, buildings, neutrals) have no owner-side direction.
    """
    if not isinstance(old, (int, float)) or not isinstance(new, (int, float)) or isinstance(old, bool):
        return 'changed', None
    pol = 0 if kind in ('trooper', 'building', 'neutral', 'unit', 'global') else polarity(path)
    a, b = abs(float(old)), abs(float(new))
    pct = None if a == 0 else (b - a) / a * 100.0
    if pol == 0 or a == b:
        return 'changed', pct
    better = (b > a) if pol > 0 else (b < a)
    return ('buff' if better else 'nerf'), pct


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
    'm_flBulletSpeed': ('Bullet Velocity', True),
    'm_flDamageFalloffStartRange': ('Falloff Start', True),
    'm_flDamageFalloffEndRange': ('Falloff End', True),
    'm_flDamageFalloffEndScale': ('Damage at Falloff End', False),
    'm_flRange': ('Max Range', True),
    'm_flCritBonusStart': ('Headshot Multiplier', False),
    'm_flCritBonusEnd': ('Headshot Multiplier (far)', False),
    'm_flCritBonusAgainstNPCs': ('Headshot Multiplier vs NPCs', False),
    'm_flBulletGravityScale': ('Bullet Gravity', False),
    'm_flBulletRadius': ('Bullet Radius', False),
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
    'm_flWalkSpeed': ('Walk Speed', True),
    'm_flRunSpeed': ('Run Speed', True),
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

_PREFIX_RE = re.compile(r'^m_(?:fl|n|i|b|str|e|vec|map|un|s|v|h|ar|bits|sz)?(?=[A-Z])')
_CAMEL_RE = re.compile(r'(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])')


def humanize(key: str) -> str:
    k = _PREFIX_RE.sub('', key)
    k = k.lstrip('_').replace('_', ' ')
    return _CAMEL_RE.sub(' ', k).strip() or key


def _loc_label(tok: dict[str, str], name: str, ability: str | None = None) -> str | None:
    for key in ((f'{ability}_{name}_label' if ability else None), f'{name}_label', name):
        if key and key.lower() in tok:
            val = re.sub(r'<[^>]+>', '', tok[key.lower()]).strip()
            if val and '{' not in val:
                return val
    return None


def stat_label(tok: dict[str, str], stat: str) -> str:
    base = stat[1:] if stat.startswith('E') and stat[1:2].isupper() else stat
    key = 'StatDesc_' + STAT_DESC_EXCEPTIONS.get(base, base)
    if key.lower() in tok:
        return re.sub(r'<[^>]+>', '', tok[key.lower()]).strip()
    return CUSTOM_STAT_LABELS.get(base) or humanize(base)


def stat_unit(tok: dict[str, str], stat: str) -> str:
    base = stat[1:] if stat.startswith('E') and stat[1:2].isupper() else stat
    key = ('StatDesc_' + STAT_DESC_EXCEPTIONS.get(base, base) + '_postfix').lower()
    return tok.get(key, '')


_TIER_RE = re.compile(r'^m_vecAbilityUpgrades\[(\d+)\]\.m_vecPropertyUpgrades\{([^}]+)\}\.(\w+)$')
_PROP_RE = re.compile(r'^m_mapAbilityProperties\.([^.]+)\.(.+)$')


def describe(path: str, tok: dict[str, str], entity: str = '', kind: str = '') -> dict:
    """{label, meters, group} for a field path of an entity."""
    m = _PROP_RE.match(path)
    if m:
        prop, rest = m.group(1), m.group(2)
        label = _loc_label(tok, prop, entity) or humanize(prop)
        if rest == 'm_strValue':
            return {'label': label, 'meters': False, 'group': 'property', 'prop': prop}
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
        label = _loc_label(tok, prop, entity) or humanize(prop)
        if 'EAddToScale' in parts or 'EMultiplyScale' in parts:
            label += ' (spirit scaling ×)' if 'EMultiplyScale' in parts else ' (spirit scaling)'
        if field == 'm_strStreetBrawlBonus':
            label += ' (Street Brawl)'
        elif field != 'm_strBonus':
            label += f' · {humanize(field)}'
        prefix = f'T{tier}' if kind in ('ability', 'ability_other', '') else 'Upgrade'
        return {'label': f'{prefix}: {label}', 'meters': False, 'group': 'tier', 'prop': prop, 'tier': tier}
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
        label, meters = WEAPON_FIELDS.get(field, (humanize(field), False))
        slot = path.split('.')[1]
        if slot != 'primary':
            label = f'{label} ({humanize(slot)})'
        return {'label': label, 'meters': meters, 'group': 'weapon'}
    leaf = path.rsplit('.', 1)[-1]
    leaf = re.sub(r'\{.*\}|\[\d+\]', '', leaf)
    if leaf in UNIT_FIELDS:
        label, meters = UNIT_FIELDS[leaf]
        parent = path.rsplit('.', 2)[-2] if path.count('.') >= 1 else ''
        if parent.startswith('m_VS'):
            label = f'{label} vs {humanize(parent[4:])}'
        return {'label': label, 'meters': meters, 'group': 'unit'}
    return {'label': context_label(path), 'meters': False, 'group': 'other'}


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


def context_label(path: str, depth: int = 3) -> str:
    """'m_mapPurchaseBonuses.EItemSlotType_WeaponMod[2].m_flValue'
    -> 'Purchase Bonuses › WeaponMod #3 › Value' (a bare leaf name is meaningless)."""
    parts = [p for p in path.split('.') if p]
    shown = [_segment(p) for p in parts[-depth:]]
    return ' › '.join(s for s in shown if s)


def display_value(v, meters: bool = False) -> str:
    if v is None:
        return '—'
    if isinstance(v, bool):
        return 'yes' if v else 'no'
    if isinstance(v, (int, float)):
        x = float(v) / UNITS_PER_METER if meters else float(v)
        if x.is_integer():
            s = str(int(x))
        else:
            # small coefficients (spirit scaling 0.005) need more decimals than stats
            s = (f'{x:.4f}' if abs(x) < 1 else f'{x:.2f}').rstrip('0').rstrip('.')
        return s + ('m' if meters else '')
    if isinstance(v, list):
        return ', '.join(display_value(x) for x in v)
    return str(v)
