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


def test_the_alt_fire_has_its_own_gun_numbers():
    """Review 2026-10-05: Viscous, Shiv, Yamato showed only a slim "Alt fire" line — no file the site reads carried the
    alt gun's numbers. The gun bound to ESlot_Weapon_Secondary is evaluated like the gun on the weapon alone (per-boon
    growth is the hero's), with what one shot takes of the clip; None for a hero without one, MISSING for an alt fire
    the build cut from abilities.vdata."""
    from pipeline.hero_table import ALT_COLUMNS, MISSING, evaluate_alt
    hero, abilities = _hero({'m_flBulletDamage': 10.34, 'm_flCycleTime': 0.21, 'm_iClipSize': 20})
    assert evaluate_alt(hero, abilities) is None
    hero['m_mapBoundAbilities']['ESlot_Weapon_Secondary'] = 'alt'
    abilities['alt'] = {'m_mapWeaponInfos': {'primary': {
        'm_flBulletDamage': 42, 'm_flCycleTime': 1.26, 'm_iClipSize': 10, 'm_reloadDuration': 2.1,
        'm_iAmmoConsumedPerShot': 5, 'm_flBulletSpeed': 1500, 'm_flRange': 1000}}}
    v = evaluate_alt(hero, abilities, 6746)
    assert v['bullet_dmg'] == 42 and round(v['dps'], 2) == round(42 / 1.26, 2) and v['ammo_shot'] == 5
    assert round(v['bullet_speed'], 1) == 38.1 and round(v['range'], 1) == 25.4 and v['clip'] == 10
    assert 'dps_max' not in v and 'bullet_dmg_lvl' not in v and set(v) == {c.key for c in ALT_COLUMNS}
    # the primary's numbers stay the primary's
    assert evaluate(hero, abilities)['bullet_dmg'] == 10.34
    # a hero in development firing another hero's guns: the stand-in's alt fire is not its own
    assert set(evaluate_alt(hero, abilities, borrowed=True).values()) == {MISSING}
    del abilities['alt']
    assert set(evaluate_alt(hero, abilities).values()) == {MISSING}


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


def test_item_stat_on_a_trigger_is_an_effect():
    """Review 2026-10-04: Spirit Sap's -30 Spirit Power (the active's debuff on the target) was an
    always-on chip because the game left its usage flags empty; Active Reload's Move Speed after a
    perfect reload too (a Passive section with its own cooldown / duration)."""
    from pipeline.item_table import evaluate
    sap = _item([('Innate', ['BonusHealth']), ('Active', ['TechPowerReduction'])],
                {'BonusHealth': {'m_strValue': '50', 'm_eProvidedPropertyType': HP},
                 'TechPowerReduction': {'m_strValue': '-30', 'm_eProvidedPropertyType': SP}})
    assert evaluate(sap, []) == {'tier': 1, 'cost': None, 'health_max': 50.0, 'fx:TechPowerReduction': -30.0}
    move = {'m_strValue': '0.75m', 'm_eProvidedPropertyType': 'MODIFIER_VALUE_MOVEMENT_SPEED_MAX'}
    reload_ = _item([('Passive', ['BonusMoveSpeed', 'AbilityDuration'])],
                    {'BonusMoveSpeed': move, 'AbilityDuration': {'m_strValue': '7'}})
    assert 'fx:BonusMoveSpeed' in evaluate(reload_, [])
    # a plain Passive stat (Superior Cooldown's +20% cooldown reduction) stays a stat
    cdr = {'m_strValue': '20', 'm_eProvidedPropertyType': 'MODIFIER_VALUE_COOLDOWN_REDUCTION_PERCENTAGE'}
    assert 'cooldown_reduction_percentage' in evaluate(_item([('Passive', ['CooldownReduction'])],
                                                             {'CooldownReduction': cdr}), [])


def _history(builds: list[tuple[int, dict]]) -> dict:
    """item_table's history of 'upgrade_x' over [(build, item)] (newest last), as build() assembles it."""
    from pipeline.item_table import _raw_keys, collect, evaluate, item_history
    snaps = [(b, f'2026-01-{b:02d}', {'upgrade_x': it}, [0, 800]) for b, it in builds]
    series, metas, enums = collect(snaps)
    last = builds[-1][1]
    raw, now = _raw_keys(last), evaluate(last, [0, 800])
    cols = {k for k in now if not k.startswith('fx:')}
    return item_history(series['upgrade_x'], metas['upgrade_x'], raw, now, cols, enums.aliases())


OLD_WD, NEW_WD = 'MODIFIER_VALUE_BASEATTACK_DAMAGE_PERCENT', 'MODIFIER_VALUE_WEAPON_DAMAGE_INCREASE'


def test_item_history_follows_the_property_not_the_stat_name():
    """Review 2026-10-04: keyed by the provided stat, Valve's enum rename (6541) and a property newly
    listed on the card made 77 fake "added" entries and dropped what came before (Extended Magazine's
    Weapon Damage 15 -> 12 -> 6 -> 8 read "added 2026-06-03: 8")."""
    def mag(wd: str, ptype: str, card=('WeaponDamage',)):
        return _item([('Innate', list(card))],
                     {'WeaponDamage': {'m_strValue': wd, 'm_eProvidedPropertyType': ptype},
                      'Close': {'m_strValue': '15m'}})
    h = _history([(1, mag('15', OLD_WD)), (2, mag('12', OLD_WD)),       # a change before the rename stays
                  (3, mag('12', NEW_WD)),                                # renamed enum, same value: nothing
                  (4, mag('12', NEW_WD, ('WeaponDamage', 'Close')))])    # newly on the card: no addition
    assert h['history'] == {'weapon_damage_increase': [[2, '2026-01-02', 15.0, 12.0, 'nerf']]}
    assert h['removed'] == []


def test_item_history_joins_a_renamed_property():
    """A property renamed with the stat it gives (BonusSpirit -> TechPower) keeps its predecessor's
    history; a respelled plain number (…TooltipOnly, a typo fixed) too, but not a coincidence."""
    def it(props: dict, card: list):
        return _item([('Innate', card)], props)
    old = {'BonusSpirit': {'m_strValue': '25', 'm_eProvidedPropertyType': SP},
           'RicochetTargetsTooltipOnly': {'m_strValue': '2'}, 'MaxStacks': {'m_strValue': '20'}}
    new = {'TechPower': {'m_strValue': '8', 'm_eProvidedPropertyType': SP},
           'RicochetTargets': {'m_strValue': '2'}, 'AbilityCooldown': {'m_strValue': '20'}}
    h = _history([(1, it(old, list(old))), (2, it(old, list(old))), (3, it(new, list(new)))])
    assert h['history']['tech_power'] == [[3, '2026-01-03', 25.0, 8.0, 'nerf']]
    assert 'fx:RicochetTargets' not in h['history']
    # MaxStacks 20 -> a 20s cooldown is not one property: the cooldown is new, the stacks are gone
    assert h['history']['cooldown'] == [[3, '2026-01-03', None, 20.0, 'changed']]
    assert [(r['key'], r['history']) for r in h['removed']] == \
        [('fx:MaxStacks', [[3, '2026-01-03', 20.0, None, 'changed']])]


def test_item_history_steps_carry_the_item_pages_direction():
    """Review 2026-10-04: the table coloured |new| vs |old| under one polarity, 33 steps opposite to the
    item page: Toxic Bullets' anti-heal -30 -> -35 is a buff, Glass Cannon's drawback -15 -> -13 too."""
    def it(heal: str, loss: str):
        return _item([('Innate', ['MaxHealthLossPercent']), ('Passive', ['HealAmpReceivePenaltyPercent'])],
                     {'HealAmpReceivePenaltyPercent': {'m_strValue': heal, 'm_eStatsUsageFlags': 'ConditionallyApplied',
                                                       'm_eProvidedPropertyType': 'MODIFIER_VALUE_HEAL_AMP_RECEIVE_PERCENT'},
                      'MaxHealthLossPercent': {'m_strValue': loss, 'm_bIsNegativeAttribute': 'true',
                                               'm_eProvidedPropertyType': 'MODIFIER_VALUE_HEALTH_MAX_PERCENT'}})
    h = _history([(1, it('-30', '-15')), (2, it('-35', '-13'))])
    assert h['history']['fx:HealAmpReceivePenaltyPercent'] == [[2, '2026-01-02', -30.0, -35.0, 'buff']]
    assert h['history']['health_max_percent'] == [[2, '2026-01-02', -15.0, -13.0, 'buff']]
    assert h['odir'] == {'fx:HealAmpReceivePenaltyPercent': 'buff', 'health_max_percent': 'buff'}


def test_item_card_speeds_print_metres_per_second():
    """Review 2026-10-04: Sprint Speed chips said "+2m" under an "m/s" column."""
    from pipeline.abilities import is_speed
    from pipeline.item_table import _unit
    assert is_speed({'m_eProvidedPropertyType': 'MODIFIER_VALUE_SPRINT_SPEED_BONUS'})
    assert is_speed({'m_eDisplayType': 'EMaxMoveSpeed'})
    assert not is_speed({'m_eProvidedPropertyType': 'MODIFIER_VALUE_MOVEMENT_SPEED_SLOW_PERCENT'})
    assert not is_speed({'m_eProvidedPropertyType': 'MODIFIER_VALUE_TECH_RANGE_PERCENT'})
    assert _unit('+2m', 'MODIFIER_VALUE_SPRINT_SPEED_BONUS') == 'm/s' and _unit('15m') == 'm'


def test_stat_families_by_the_provided_stat():
    from pipeline.item_table import family
    assert family('MODIFIER_VALUE_WEAPON_DAMAGE_INCREASE') == 'Weapon'
    assert family('MODIFIER_VALUE_BULLET_ARMOR_DAMAGE_RESIST') == 'Vitality'     # a resist, not a bullet stat
    assert family('MODIFIER_VALUE_MOVEMENT_SLOW_RESISTANCE') == 'Vitality'
    assert family('MODIFIER_VALUE_SPRINT_SPEED_BONUS') == 'Movement'
    assert family('MODIFIER_VALUE_TECH_POWER') == 'Spirit'
    # never dropped, and never a second "Utility" group apart from cooldown / duration (it broke folding)
    assert family('MODIFIER_VALUE_SOMETHING_NEW') == 'Other'


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
