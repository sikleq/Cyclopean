"""The game's own hero stat panels — Weapon / Vitality / Spirit Stats, the hero card of the shop and the
scoreboard (panorama/layout/citadel_hero_stats_{weapon,armor,tech}_panel.xml; the client fills them from the
hero's m_ShopStatDisplay) — and its Boon Rewards card, as data for the hero page.

Which stats a panel lists, and in what order, is the hero's own m_ShopStatDisplay (one list of tiles, one of
"other" tiles under it: melee under the gun, movement under vitality). A tile's name is the attribute localization's
StatDesc_* token. Its value is the Hero Stats column that reads the same thing (`COLUMN`), so the tile keeps that
column's history; any other stat is the hero's m_mapStartingStats shown the game's way: a 1.0 scale reads "0%",
a 0.222/s stamina recovery is a 4.5 s stamina cooldown, a bonus the hero does not start with is 0 (checked against
the game's panels for Warden, owner's shots 2026-10-22)."""
from __future__ import annotations

import re

PANELS = (('weapon', 'm_eWeaponStatsDisplay', 'CitadelHeroStats_Weapon'),
          ('vitality', 'm_eVitalityStatsDisplay', 'CitadelHeroStats_Vitality'),
          ('spirit', 'm_eSpiritStatsDisplay', 'CitadelHeroStats_Spirit'))

# E-stat -> its StatDesc_* token stem where the stem is not the stat's own name
LOC = {'EClipSize': 'ClipSizeBonus', 'EMaxMoveSpeed': 'RunSpeed', 'EOOCHealthRegen': 'OutOfCombatHealthRegen',
       'EHeroSpiritLifestealEffectiveness': 'SpiritLifestealEffectiveness',
       'EBaseWeaponDamageIncrease': 'BaseWeaponDamage', 'ETechCooldownBetweenChargeUses': 'TechCooldownBetweenCharges', 'EWeaponDPS': 'DPS'}

# E-stat -> the Hero Stats column (pipeline/hero_table.py) holding the same number, with its history
COLUMN = {'EBulletDamage': 'bullet_dmg', 'ERoundsPerSecond': 'bps', 'EClipSize': 'clip', 'EReloadTime': 'reload',
          'EBulletSpeed': 'bullet_speed', 'ELightMeleeDamage': 'light_melee', 'EHeavyMeleeDamage': 'heavy_melee',
          'EMaxHealth': 'hp', 'EBaseHealthRegen': 'hp_regen', 'EBulletArmorDamageReduction': 'bullet_resist',
          'ETechArmorDamageReduction': 'spirit_resist', 'EMaxMoveSpeed': 'move', 'ESprintSpeed': 'sprint',
          'EStamina': 'stamina', 'EWeaponDPS': 'dps'}

# the unit the game prints after the number
UNIT = {'EReloadTime': 's', 'EBulletSpeed': 'm/s', 'EMaxMoveSpeed': 'm', 'ESprintSpeed': 'm', 'EStaminaCooldown': 's',
        'EDashSpeedInMeters': 'm/s'}
PERCENT = {'EBaseWeaponDamageIncrease', 'EFireRate', 'EClipSizeIncrease', 'EReloadSpeed', 'EBulletSpeedIncrease',
           'EBulletLifesteal', 'ECritDamageBonusScale', 'EHealingOutput', 'EHeroSpiritLifestealEffectiveness',
           'EBulletArmorDamageReduction', 'ETechArmorDamageReduction', 'EMeleeResist', 'EDebuffResist',
           'ECritDamageReceivedScale', 'EStaminaRegenIncrease', 'ETechCooldown', 'ETechDuration', 'ETechRange',
           'ETechLifesteal', 'ETechCooldownBetweenChargeUses'}
# starting stats kept as a scale of 1: the panel prints the bonus over 1 ("Crit Bonus Scale 0%" for 1.0), the
# reduction under 1 ("Crit Reduction 0%", "Reload Reduction 0%" for 1.0), or the whole scale ("Lifesteal
# Effectiveness 100%")
OVER_ONE = {'ECritDamageBonusScale', 'ETechDuration', 'ETechRange'}
UNDER_ONE = {'ECritDamageReceivedScale', 'EReloadSpeed'}
WHOLE = {'EHeroSpiritLifestealEffectiveness'}

# the Boon Rewards card (citadel_main Citadel_Player_Level_*): what one boon adds, in the card's order, by the
# hero's m_mapStandardLevelUpUpgrades key and the Hero Stats column with its history
BOON_ROWS = (('MODIFIER_VALUE_BASE_BULLET_DAMAGE_FROM_LEVEL', 'Citadel_Player_Level_BaseBullet', 'bullet_dmg_lvl'),
             ('MODIFIER_VALUE_BASE_MELEE_DAMAGE_FROM_LEVEL', 'Citadel_Player_Level_BaseMelee', 'melee_lvl'),
             ('MODIFIER_VALUE_TECH_POWER', 'Citadel_Player_Level_SpiritPower', 'spirit_lvl'),
             ('MODIFIER_VALUE_BASE_HEALTH_FROM_LEVEL', 'Citadel_Player_Level_BaseHealth', 'hp_lvl'),
             ('MODIFIER_VALUE_BULLET_ARMOR_DAMAGE_RESIST', 'Citadel_Player_Level_BulletResist', 'bullet_resist_lvl'),
             ('MODIFIER_VALUE_TECH_RESIST', 'Citadel_Player_Level_TechResist', 'spirit_resist_lvl'),
             ('MODIFIER_VALUE_BONUS_ATTACK_RANGE', 'Citadel_Player_Level_WeaponRange', 'range_lvl'))

# the cards' own words, read from the build's localization
TEXT = ('CitadelHeroStats_Weapon', 'CitadelHeroStats_Vitality', 'CitadelHeroStats_Spirit',
        'CitadelHeroStats_SpiritPower_Impact', 'CitadelHeroStats_SpiritPower_Desc', 'CitadelHeroStats_Weapon_Falloff',
        'Citadel_Player_Level_RewardsTitle', 'Citadel_Player_Level_RewardsSubhead', 'Citadel_Player_Level_AP_Rewards',
        'Citadel_Player_Level_AP_Rewards_UnlockNote', 'Citadel_Player_Level_Stat_Rewards',
        'Citadel_Player_Level_Stat_RewardsMax', 'StatDesc_TechPower') + tuple(r[1] for r in BOON_ROWS)

_IMAGE = re.compile(r'/heroes/guns/(\w+)\.psd')
_HTML = re.compile(r'<[^>]+>')


def loc_key(stat: str) -> str:
    return 'StatDesc_' + LOC.get(stat, stat[1:])


def panels(hero: dict) -> dict[str, dict[str, list[str]]]:
    """{'weapon': {'stats': [...], 'other': [...]}, 'vitality': ..., 'spirit': ...} from m_ShopStatDisplay."""
    disp = hero.get('m_ShopStatDisplay') or {}
    out = {}
    for key, field, _ in PANELS:
        p = disp.get(field) or {}
        out[key] = {'stats': [s for s in p.get('m_vecDisplayStats') or [] if isinstance(s, str)],
                    'other': [s for s in p.get('m_vecOtherDisplayStats') or [] if isinstance(s, str)]}
    return out


def gun(hero: dict) -> dict:
    """The gun's tags (m_eWeaponAttributes "EWeaponAttribute_MediumRange | EWeaponAttribute_Projectile") and the
    picture the panel draws (m_strWeaponImage -> 'warden_gun', icons/guns/ by tools/extract_shop_assets.py)."""
    w = ((hero.get('m_ShopStatDisplay') or {}).get('m_eWeaponStatsDisplay') or {})
    attrs = [a.strip() for a in str(w.get('m_eWeaponAttributes') or '').split('|') if a.strip()]
    m = _IMAGE.search(str(w.get('m_strWeaponImage') or ''))
    return {'attrs': attrs, 'image': m.group(1) if m else None}


def _num(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def start_value(stat: str, start: dict) -> float | None:
    """A panel stat that no Hero Stats column holds, from m_mapStartingStats the game's way (module doc)."""
    if stat in OVER_ONE | UNDER_ONE | WHOLE:
        v = _num(start.get(stat))
        v = 1.0 if v is None else v
        return (v - 1) * 100 if stat in OVER_ONE else (1 - v) * 100 if stat in UNDER_ONE else v * 100
    v = _num(start.get(stat))
    return 0.0 if v is None else v


def own_values(hero: dict) -> dict[str, float | None]:
    """The panel stats with no column: their value today (EStaminaCooldown: one stamina point's recovery,
    1 / EStaminaRegenPerSecond — Warden's 0.222222/s is the panel's 4.5s)."""
    start = hero.get('m_mapStartingStats') or {}
    out: dict[str, float | None] = {}
    for p in panels(hero).values():
        for stat in p['stats'] + p['other']:
            if stat in COLUMN:
                continue
            if stat == 'EStaminaCooldown':
                r = _num(start.get('EStaminaRegenPerSecond'))
                out[stat] = 1 / r if r else None
            else:
                out[stat] = start_value(stat, start)
    for stat in hero.get('m_mapScalingStats') or {}:           # Spirit Power Impact lists them too
        if stat not in COLUMN and stat not in out and stat != 'EStaminaCooldown':
            out[stat] = start_value(stat, start)
    return out


def labels(tok: dict[str, str], heroes: dict) -> dict:
    """The words of every panel: stat names, the guns' tags, the cards' titles (one build's localization)."""
    stats, attrs = set(COLUMN), set()
    for hero in heroes.values():
        if not isinstance(hero, dict):
            continue
        for p in panels(hero).values():
            stats.update(p['stats'] + p['other'])
        stats.update(hero.get('m_mapScalingStats') or {})
        attrs.update(gun(hero)['attrs'])
    return {
        'stats': {s: tok.get(loc_key(s).lower()) for s in sorted(stats)},
        'attrs': {a: tok.get(f'attribute_{a}'.lower()) for a in sorted(attrs)},
        'text': {k: _HTML.sub('', tok.get(k.lower()) or '').strip() or None for k in TEXT},
    }
