"""Stats tables: the hero / unit column functions against values from the original sheet, and the table pages
(builders/tables_pages.py)."""
import re

from pipeline.hero_table import evaluate
from pipeline.unit_table import evaluate as unit_eval

from tests.helpers import site_css


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


def test_hero_table_layout_keeps_every_column_and_hides_details():
    from builders.tables_pages import DETAILS, HERO_LAYOUT, laid_out
    cols = [{'key': 'dps', 'label': 'DPS', 'group': 'Damage'}, {'key': 'spread', 'label': 'Spread', 'group': 'Damage'},
            {'key': 'brand_new', 'label': 'Brand new stat', 'group': 'Damage'}]
    out = laid_out(cols, HERO_LAYOUT)
    assert [c['key'] for c in out] == ['dps', 'spread', 'brand_new']          # nothing dropped, details last
    assert out[0]['group'] == 'Weapon' and out[1]['group'] == DETAILS and out[2]['group'] == DETAILS
    assert all(len(short) <= 13 for _, entries in HERO_LAYOUT for _, short in entries)   # one-line headers


def test_a_hero_stats_column_nobody_has_today_waits_under_details(monkeypatch):
    """Review 2026-10-05: "Bullet res" read "—" for all 44 heroes; it goes under Details with its history."""
    from builders import tables_pages
    cols = [{'key': 'hp', 'label': 'Health', 'group': 'Vitality', 'pol': 1, 'digits': 0},
            {'key': 'bullet_resist', 'label': 'Bullet Resist', 'group': 'Vitality', 'pol': 1, 'digits': 0}]
    heroes = [{'id': 'hero_atlas', 'name': 'Abrams', 'state': 'release', 'type': 'x_Brawler',
               'values': {'hp': 800, 'bullet_resist': None}, 'history': {}, 'spirit_scaled': []}]
    monkeypatch.setattr(tables_pages, 'heroes_data', lambda: {'columns': cols, 'heroes': heroes, 'build': 1,
                                                              'date': '2026-10-01'})
    html = tables_pages.heroes_table()
    head = html.split('<thead>')[1].split('</thead>')[0]
    assert re.search(r'g-details[^>]*>[^<]*Bullet', head) and not re.search(r'g-details[^>]*>[^<]*Health', head)


def test_unit_table_names_and_copies():
    from builders.tables_pages import merge_copies, non_empty, unit_label
    assert unit_label({'id': 'npc_neutral_bug', 'name': 'npc_neutral_bug'}) == 'Bug'
    assert unit_label({'id': 'trooper_zipline_container', 'name': 'trooper_zipline_container'}) == 'Trooper Zipline Container'
    assert unit_label({'id': 'npc_boss_tier2', 'name': 'Walker'}) == 'Walker'
    rows = [{'id': f'w{i}', 'name': 'Walker', 'values': {'hp': 6000, 'x': None}} for i in range(4)]
    rows.append({'id': 'g', 'name': 'Guardian', 'values': {'hp': 5500, 'x': None}})
    merged = merge_copies(rows)
    assert [(r['name'], r.get('copies')) for r in merged] == [('Walker', 4), ('Guardian', None)]
    cols = [{'key': 'hp'}, {'key': 'x'}]
    assert [c['key'] for c in non_empty(cols, merged)] == ['hp']


def test_hero_stats_boons_and_roles():
    from builders.tables_pages import boon_attrs
    r = {'values': {'hp': 800, 'hp_lvl': 49, 'dps': 51.4, 'bullet_dmg': 3.6, 'bullet_dmg_lvl': 0.1}}
    assert boon_attrs(r, {'key': 'hp'}) == ' data-per="49"'
    # DPS grows with the bullet: 51.4 * 0.1 / 3.6 per boon
    assert boon_attrs(r, {'key': 'dps'}) == ' data-per="1.42778"'
    assert boon_attrs(r, {'key': 'reload'}) == ''


ITEM_COLS = [{'key': 'tier', 'label': 'Tier', 'group': 'Shop', 'pol': 0, 'digits': 0, 'unit': ''},
             {'key': 'cost', 'label': 'Cost', 'group': 'Shop', 'pol': -1, 'digits': 0, 'unit': '', 'css': 'souls'},
             {'key': 'health_max', 'label': 'Bonus Health', 'group': 'Vitality', 'pol': 1, 'digits': 0, 'unit': '',
              'css': 'health', 'stat': True},
             {'key': 'bullet_armor_damage_resist', 'label': 'Bullet Resist', 'group': 'Vitality', 'pol': 1,
              'digits': 0, 'unit': '%', 'css': 'bullet_armor_up', 'stat': True},
             {'key': 'cooldown', 'label': 'Cooldown', 'group': 'Utility', 'pol': -1, 'digits': 2, 'unit': 's',
              'css': 'cooldown'}]


BOOSTER = {'id': 'upgrade_headshot_booster', 'name': 'Headshot Booster', 'slot': 'Weapon',
           'values': {'tier': 1, 'cost': 800.0, 'health_max': 30.0, 'cooldown': 9.0},
           'shown': {'health_max': '+30', 'cooldown': '9s'},
           'effects': [{'key': 'fx:HeadShotBonusDamage', 'label': 'Head Shot Bonus Damage', 'value': '+45',
                        'css': 'bullet_damage', 'pol': 1, 'digits': 0}],
           'history': {'health_max': [[5554, '2025-05-08', 40.0, 30.0]],
                       'bullet_armor_damage_resist': [[5554, '2025-05-08', 4.0, None]],
                       'fx:HeadShotBonusDamage': [[6000, '2025-12-01', 40.0, 45.0]]}}


def test_item_stats_show_what_an_item_does():
    """Owner complaint 6 (2026-10-04): Item Stats was 67-84% dashes and never showed an item's own numbers.
    The always-on stats are chips in one cell (one sortable column each on demand), every other card
    number is an Effect chip with its label and unit, each with its own history."""
    from builders.tables_pages import effects_cell, item_columns, stats_cell
    cols = item_columns(ITEM_COLS)
    assert [c['key'] for c in cols] == ['tier', 'cost', 'stats', 'health_max', 'bullet_armor_damage_resist',
                                        'effect', 'cooldown', 'builds']
    stat_cols = [c for c in cols if c.get('stat')]
    assert all(c['lazy'] and c['cls'] == 'stc' for c in stat_cols)    # no per-stat cells in the page
    html = stats_cell(BOOSTER, stat_cols, '2025-01-01')
    assert 'class="sc f-v has-hist recent"' in html and 'data-col="health_max" data-sort="30.0"' in html
    assert '<b>+30</b> <i>Bonus Health</i>' in html and 'data-spp' in html
    assert 'data-hist=\'[[5554,"2025-05-08",40.0,30.0]]\'' in html
    # a stat the item lost keeps its history for the column view, as an empty marker
    assert 'class="sc gone has-hist recent" data-col="bullet_armor_damage_resist"' in html
    assert 'data-sort="1"' in html                                       # one stat now
    fx = effects_cell(BOOSTER, '2026-01-01')
    assert '<b>+45</b> <i>Head Shot Bonus Damage</i>' in fx and 'Headshot Booster · Head Shot Bonus Damage' in fx
    assert 'class="fx has-hist"' in fx and 'data-col="effect"' in fx and 'data-pol="0"' in fx
    empty = {**BOOSTER, 'values': {}, 'effects': [], 'history': {}}
    assert '<span class="dash">—</span>' in stats_cell(empty, stat_cols, '') and 'data-sort=""' in effects_cell(empty, '')


def test_item_table_bands_tiers_and_lazy_columns():
    from builders.tables_pages import item_columns, render_table, tier_starts
    rows = [{**BOOSTER, 'id': f'i{n}', 'name': f'I{n}', 'slot': slot, 'values': {**BOOSTER['values'], 'tier': tier}}
            for n, (slot, tier) in enumerate([('Weapon', 1), ('Weapon', 1), ('Weapon', 2), ('Spirit', 2)])]
    assert tier_starts(rows) == {'i0', 'i2', 'i3'}
    cols = item_columns(ITEM_COLS)
    html = render_table(cols, rows, lambda r: f'<td class="name">{r["name"]}</td>', 'Item',
                        section_of=lambda r: (r['slot'], f' data-cat="{r["slot"][0].lower()}"'),
                        cells_by_key={'stats': lambda r, c, cut: '<td class="sumc"></td>',
                                      'effect': lambda r, c, cut: '<td class="fxc"></td>',
                                      'builds': lambda r, c, cut: '<td class="xcol"></td>'},
                        group_cls={'Vitality': 'stc', 'Stats': 'sumc'})
    # one band row per category, spanning the table; the box at the page's left edge like every table's (2026-10-17)
    assert html.count('<tr class="sec"') == 2 and '<tr class="sec" data-cat="s">' in html
    assert 'class="sec-fill"' in html and 'class="table-fade"' in html
    # a lazy column: its header says how to build its cells, the rows have none
    assert re.search(r'data-col="health_max"[^>]*data-cell-cls="grp-start( g-odd)? stc"', html)
    assert 'data-col="health_max" data-sort' not in html
    # units in headers, the game's property icon before the label
    assert 'Cooldown <span class="u">s</span>' in html and 'Bullet Resist <span class="u">%</span>' in html
    assert 'stats/prop/cooldown.svg' in html
    assert '<th colspan="2" class="cat stc" data-group="Vitality">' in html


def test_item_effects_mark_the_active_and_recent_losses():
    """Review 2026-10-04: "+70% Spirit Lifesteal" while Infuser runs sat beside its always-on +13% with
    nothing between them; a number the item lost left no trace on the table."""
    from builders.tables_pages import effects_cell
    row = {**BOOSTER, 'effects': BOOSTER['effects'] + [
        {'key': 'fx:Lifesteal', 'label': 'Spirit Lifesteal', 'value': '+70%', 'css': None, 'pol': 1, 'digits': 0,
         'active': True}],
        'removed': [{'key': 'fx:PerKill', 'label': 'Weapon Damage per Kill', 'css': None, 'pol': 1, 'digits': 0,
                     'history': [[6700, '2026-09-20', 10.0, None, 'changed']]},
                    {'key': 'fx:Old', 'label': 'Old Thing', 'css': None, 'pol': 1, 'digits': 0,
                     'history': [[5000, '2024-08-01', 3.0, None, 'changed']]}],
        'odir': {'fx:HeadShotBonusDamage': 'buff'}}
    html = effects_cell(row, '2026-08-20')
    # the "Active" tag before the first active number, which is framed apart
    assert html.index('<span class="fx-tag">Active</span>') < html.index('class="fx fx-act')
    assert html.index('Head Shot Bonus Damage') < html.index('fx-tag')
    # lost lately: struck through with its history; lost long ago: only on the item's page
    assert 'class="fx fx-gone has-hist recent"' in html and '<b>10</b> <i>Weapon Damage per Kill</i>' in html
    assert 'Old Thing' not in html
    assert 'data-sort="2"' in html                                      # what the item does now
    assert 'data-odir="buff"' in html                                   # the whole history's direction


def test_item_stats_refuse_an_old_items_json():
    """Review 2026-10-04: the old items.json built a broken page (two Stats groups, empty cells) without
    failing; CI deploys committed data, so a stale file must stop the build."""
    import pytest
    from builders.tables_pages import check_items_data
    with pytest.raises(RuntimeError, match='old format'):
        check_items_data({'columns': ITEM_COLS[:2], 'items': [{'id': 'x', 'values': {}}]})
    with pytest.raises(RuntimeError):
        check_items_data({'columns': ITEM_COLS, 'items': [{'id': 'x', 'values': {}}]})
    check_items_data({'columns': ITEM_COLS, 'items': [BOOSTER]})


def test_item_unknown_stat_family_is_one_group_before_effects():
    """A new provided stat no family word matches is "Other", next to the stat families: as "Utility" it
    sat before Effect while Cooldown sat after it — two "Utility" groups the folding merged by name."""
    from builders.tables_pages import item_columns, render_table
    new = {'key': 'something_new', 'label': 'New', 'group': 'Other', 'pol': 1, 'digits': 0, 'unit': '', 'stat': True}
    cols = item_columns(ITEM_COLS[:4] + [new] + ITEM_COLS[4:])
    groups = [c['group'] for c in cols]
    assert groups == ['Shop', 'Shop', 'Stats', 'Vitality', 'Vitality', 'Other', 'Effect', 'Utility', 'Builds']
    html = render_table(cols, [BOOSTER], lambda r: '<td class="name"></td>', 'Item',
                        cells_by_key={'stats': lambda r, c, cut: '<td></td>', 'effect': lambda r, c, cut: '<td></td>',
                                      'builds': lambda r, c, cut: '<td></td>'}, table_attrs=' data-heat-by="tier"')
    assert html.count('data-group="Utility">') == 1 and '<table class="stats" data-heat-by="tier">' in html


def test_table_bar_scrolls_away_and_its_legend_wraps():
    """The sticky bar covered the column headers (a third of a phone); the 489px legend chip scrolled
    the page sideways at 390px; the heatmap is on by default on Item Stats."""
    from builders.tables_pages import _toolbar
    bar = _toolbar('Item…', heat_on=True)
    assert 'class="toolbar tbl-bar"' in bar and 'data-heatmap checked' in bar
    assert ('<span class="lg-tail"> · <span class="lg-hover">hover</span><span class="lg-tap">tap</span>'
            ' a value for its history</span>') in bar
    assert 'data-heatmap checked' not in _toolbar('Hero…')
    css = site_css()
    # static on a phone or a short window; a desktop keeps it under the site bar (tests/test_vis_layout.py)
    assert ('@media (max-width: 760px), (max-height: 560px) { .toolbar.tbl-bar, .toolbar.dyn-bar { position: static; } }'
            in css)
    assert '.chip.legend-hist { white-space: normal; max-width: 100%; }' in css
    # a unit without art: the glyph gets the icon's fixed box (Shrine's grew to a 300x210 picture)
    assert 'table.stats td.name img, table.stats td.name .glyph { flex: none; width: 22px; height: 22px;' in css
