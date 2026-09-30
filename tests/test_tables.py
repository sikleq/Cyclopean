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
        'AbilityCooldown': {'m_strValue': '27'}, 'BonusHealth': {'m_strValue': '0'}}}
    v = item_eval(item, [0, 800, 1600, 3200, 6400, 9999])
    assert v['tier'] == 3 and v['cost'] == 3200 and v['cooldown'] == 27
    assert v['health'] is None          # zero = the item has no such bonus


def test_unit_columns_follow_field_moves():
    old = {'m_nMaxHealth': 300, 'm_flPlayerDPS': 28, 'm_WeaponInfo': {'m_flRange': 1574.8}}
    new = {'m_nMaxHealth': 300, 'm_VSPlayer': {'m_flBaseDPS': 30}, 'm_mapWeaponInfos': {'primary': {'m_flRange': 1574.8}}}
    a, b = unit_eval(old), unit_eval(new)
    assert a['dps_hero'] == 28 and b['dps_hero'] == 30
    assert round(a['range'], 1) == round(b['range'], 1) == 40.0
