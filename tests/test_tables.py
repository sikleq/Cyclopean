"""Hero / unit table column functions against values from the original sheet."""
from pipeline.hero_table import evaluate
from pipeline.unit_table import evaluate as unit_eval


def _hero(weapon: dict, **stats) -> tuple[dict, dict]:
    hero = {
        'm_mapBoundAbilities': {'ESlot_Weapon_Primary': 'w'},
        'm_mapStartingStats': stats,
        'm_mapStandardLevelUpUpgrades': {'MODIFIER_VALUE_BASE_BULLET_DAMAGE_FROM_LEVEL': 0.226286},
        'm_mapLevelInfo': {str(i): {'m_bUseStandardUpgrade': i > 1} for i in range(1, 16)},
    }
    return hero, {'w': {'m_WeaponInfo': weapon}}


def test_abrams_like_single_bullet_reload_matches_sheet():
    hero, abilities = _hero({'m_flBulletDamage': 4.05, 'm_iBullets': 9, 'm_flCycleTime': 0.6, 'm_iClipSize': 9,
                             'm_reloadDuration': 0.3525, 'm_bReloadSingleBullets': True,
                             'm_flReloadSingleBulletsInitialDelay': 0.705}, EMaxHealth=570)
    v = evaluate(hero, abilities)
    assert round(v['reload'], 4) == 1.0575                       # sheet value
    assert round(v['reload_full'], 4) == round(0.705 + 9 * 0.3525, 4)
    assert round(v['bullet_dmg_max'], 3) == round(4.05 + 0.226286 * 14, 3)   # 14 boons, as in the sheet
    assert round(v['dps'], 2) == round(4.05 * 9 / 0.6, 2)
    assert v['hp'] == 570


def test_burst_weapon_bullets_per_second():
    hero, abilities = _hero({'m_flBulletDamage': 10, 'm_flCycleTime': 0.5, 'm_iBurstShotCount': 3,
                             'm_flIntraBurstCycleTime': 0.1, 'm_iClipSize': 30})
    v = evaluate(hero, abilities)
    assert round(v['bps'], 4) == round(3 / (2 * 0.1 + 0.5), 4)


def test_item_cost_from_tier_price_table():
    from pipeline.item_table import evaluate as item_eval
    item = {'m_iItemTier': 'EModTier_3', 'm_mapAbilityProperties': {
        'AbilityCooldown': {'m_strValue': '27'}, 'BonusHealth': {'m_strValue': '0',
                                                                 'm_eProvidedPropertyType': 'MODIFIER_VALUE_HEALTH_MAX'}}}
    v = item_eval(item, [0, 800, 1600, 3200, 6400, 9999])
    assert v['tier'] == 3 and v['cost'] == 3200 and v['cooldown'] == 27
    assert 'health_max' not in v          # zero = the item has no such bonus


def _item(sections, props, tier=1):
    """An abilities.vdata item: tooltip sections [(type, [prop, ...])] over m_mapAbilityProperties."""
    return {'m_iItemTier': f'EModTier_{tier}', 'm_mapAbilityProperties': props,
            'm_vecTooltipSectionInfo': [{'m_eAbilitySectionType': f'EArea_{kind}',
                                         'm_vecSectionAttributes': [{'m_vecAbilityProperties': names}]}
                                        for kind, names in sections]}


HP = 'MODIFIER_VALUE_HEALTH_MAX'
SP = 'MODIFIER_VALUE_TECH_POWER'


def test_item_numbers_come_from_its_card():
    """2026-10-04: 14 hardcoded columns hid every item's own number (Headshot Booster +45)."""
    from pipeline.item_table import evaluate
    item = _item([('Innate', ['BonusHealth']), ('Passive', ['HeadShotBonusDamage', 'AbilityCooldown']),
                  ('Active', ['TechPower'])],
                 {'BonusHealth': {'m_strValue': '30', 'm_eProvidedPropertyType': HP},
                  'HeadShotBonusDamage': {'m_strValue': '45'},
                  'AbilityCooldown': {'m_strValue': '9'},
                  # a stat given only while the active runs is the item's effect, not an always-on stat
                  'TechPower': {'m_strValue': '150', 'm_eProvidedPropertyType': SP,
                                'm_eStatsUsageFlags': 'ConditionallyApplied'},
                  'Radius': {'m_strValue': '22m'}})                 # not on the card: not read
    v = evaluate(item, [0, 800])
    assert v == {'tier': 1, 'cost': 800.0, 'health_max': 30.0, 'fx:HeadShotBonusDamage': 45.0, 'cooldown': 9.0,
                 'fx:TechPower': 150.0}
    # before m_eStatsUsageFlags (2025-04) the game marked the same with m_UsageFlags
    old = _item([('Active', ['TechPower'])], {'TechPower': {
        'm_strValue': '150', 'm_eProvidedPropertyType': SP, 'm_UsageFlags': 'APUsageFlag_ModifierConditional'}})
    assert 'fx:TechPower' in evaluate(old, [0, 800])
    # TechPower and SpiritPower provide one stat: one Spirit Power column
    a = _item([('Innate', ['TechPower'])], {'TechPower': {'m_strValue': '14', 'm_eProvidedPropertyType': SP}})
    b = _item([('Innate', ['SpiritPower'])], {'SpiritPower': {'m_strValue': '20', 'm_eProvidedPropertyType': SP}})
    assert evaluate(a, [])['tech_power'] == 14 and evaluate(b, [])['tech_power'] == 20


def test_stat_families_by_the_provided_stat():
    from pipeline.item_table import family
    assert family('MODIFIER_VALUE_WEAPON_DAMAGE_INCREASE') == 'Weapon'
    assert family('MODIFIER_VALUE_BULLET_ARMOR_DAMAGE_RESIST') == 'Vitality'     # a resist, not a bullet stat
    assert family('MODIFIER_VALUE_MOVEMENT_SLOW_RESISTANCE') == 'Vitality'
    assert family('MODIFIER_VALUE_SPRINT_SPEED_BONUS') == 'Movement'
    assert family('MODIFIER_VALUE_TECH_POWER') == 'Spirit'
    assert family('MODIFIER_VALUE_SOMETHING_NEW') == 'Utility'                 # never dropped


def test_item_columns_are_the_stats_several_items_give():
    from pipeline.item_table import STAT_MIN_ITEMS, derive_columns, row_effects
    card = {'BonusHealth': {'label': 'Bonus Health', 'value': '+30', 'css': 'health'},
            'BonusSprintSpeed': {'label': 'Sprint Speed', 'value': '+0.75m', 'css': 'move_speed'},
            'HeadShotBonusDamage': {'label': 'Head Shot Bonus Damage', 'value': '+45', 'css': 'bullet_damage'}}
    items = [{'values': {'health_max': 30.0 + i, 'cooldown': 9.0},
              'raw': {'health_max': ('BonusHealth', HP), 'cooldown': ('AbilityCooldown', '')},
              'card': card} for i in range(STAT_MIN_ITEMS)]
    items[0]['values']['sprint_speed_bonus'] = 0.75                  # one item only: an effect, not a column
    items[0]['raw']['sprint_speed_bonus'] = ('BonusSprintSpeed', 'MODIFIER_VALUE_SPRINT_SPEED_BONUS')
    cols = derive_columns(items)
    keys = [c['key'] for c in cols]
    assert keys == ['tier', 'cost', 'health_max', 'cooldown', 'duration']
    hp = cols[2]
    assert (hp['label'], hp['group'], hp['unit'], hp['css'], hp['pol'], hp['stat']) == \
        ('Bonus Health', 'Vitality', '', 'health', 1, True)
    assert cols[3]['group'] == 'Utility' and cols[3]['pol'] == -1 and cols[3]['unit'] == 's'
    # what has no column is listed with the card's label and value, in the card's order
    raw = {'health_max': ('BonusHealth', HP), 'sprint_speed_bonus': ('BonusSprintSpeed', 'x'),
           'fx:HeadShotBonusDamage': ('HeadShotBonusDamage', '')}
    fx = row_effects(raw, {'sprint_speed_bonus': 0.75, 'fx:HeadShotBonusDamage': 45.0}, card, set(keys))
    assert [(e['label'], e['value'], e['digits']) for e in fx] == [('Sprint Speed', '+0.75m', 2),
                                                                     ('Head Shot Bonus Damage', '+45', 0)]


def test_item_stat_added_later_is_an_addition():
    """A key first seen after the item's own first build starts from None there, so its history says
    "added on <date>" instead of treating the late value as the first one."""
    from pipeline.hero_table import history_changes
    from pipeline.item_table import track
    series, first = {}, {}
    track(series, first, 'upgrade_x', 100, '2025-01-01', {'tier': 1, 'cost': 800.0})
    track(series, first, 'upgrade_x', 200, '2025-02-01', {'tier': 1, 'cost': 800.0, 'health_max': 30.0})
    track(series, first, 'upgrade_x', 300, '2025-03-01', {'tier': 1, 'cost': 800.0})
    assert history_changes(series['upgrade_x']['health_max']) == [[200, '2025-02-01', None, 30.0],
                                                                  [300, '2025-03-01', 30.0, None]]
    assert history_changes(series['upgrade_x']['cost']) == []


def test_unit_columns_follow_field_moves():
    old = {'m_nMaxHealth': 300, 'm_flPlayerDPS': 28, 'm_WeaponInfo': {'m_flRange': 1574.8}}
    new = {'m_nMaxHealth': 300, 'm_VSPlayer': {'m_flBaseDPS': 30}, 'm_mapWeaponInfos': {'primary': {'m_flRange': 1574.8}}}
    a, b = unit_eval(old), unit_eval(new)
    assert a['dps_hero'] == 28 and b['dps_hero'] == 30
    assert round(a['range'], 1) == round(b['range'], 1) == 40.0
