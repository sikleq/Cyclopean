"""Reading the game files: the KV3 parser, flattening an entity, the entity diff."""
from pipeline import kv3
from pipeline.diff import collapse_shared, diff_file
from pipeline.flatten import Num, canonical, flatten


# ---- kv3 ------------------------------------------------------------------

KV3_SAMPLE = '''<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} format:generic:version{7412167c-06e9-4698-aff2-e63eb59037e7} -->
{
\tgeneric_data_type = "CitadelAbilityVData"
\tupgrade_x =
\t{
\t\t_class = "citadel_item"
\t\tm_bFlag = true
\t\tm_flValue = -1.5e-2
\t\tm_img = panorama:"file://{images}/a.psd"
\t\tm_sub = subclass:
\t\t{
\t\t\t_class = "scale_function_tech_damage"
\t\t\tm_flStatScale = 2.2
\t\t}
\t\tm_list = [ "b", "a", ]
\t\tm_empty = null
\t\t// comment
\t\tm_ml = """line1
line2"""
\t}
}
'''


def test_kv3_parses_values_flags_and_comments():
    d = kv3.loads(KV3_SAMPLE)
    x = d['upgrade_x']
    assert d['generic_data_type'] == 'CitadelAbilityVData'
    assert x['m_bFlag'] is True
    assert x['m_flValue'] == -0.015
    assert x['m_img'] == 'file://{images}/a.psd'          # flag dropped
    assert x['m_sub']['m_flStatScale'] == 2.2               # subclass dict kept
    assert x['m_list'] == ['b', 'a']
    assert x['m_empty'] is None
    assert x['m_ml'] == 'line1\nline2'


# ---- flatten / diff ----------------------------------------------------------

def test_numeric_strings_equal_numbers_and_units_kept():
    f = flatten({'a': '4', 'b': 4, 'c': '1.5m'})
    assert f['a'] == f['b'] == 4.0
    assert isinstance(f['c'], Num) and f['c'].unit == 'm' and f['c'] == 1.5


def test_list_of_dicts_keyed_by_property_name():
    obj = {'m_vecAbilityUpgrades': [{'m_vecPropertyUpgrades': [
        {'m_strPropertyName': 'Damage', 'm_strBonus': '20'},
        {'m_strPropertyName': 'Radius', 'm_strBonus': '2m'}]}]}
    f = flatten(obj)
    assert 'm_vecAbilityUpgrades[0].m_vecPropertyUpgrades{Damage}.m_strBonus' in f


def test_weapon_info_rename_is_not_a_change():
    old = {'w': {'m_WeaponInfo': {'m_flBulletDamage': 5}}}
    new = {'w': {'m_mapWeaponInfos': {'primary': {'m_flBulletDamage': 5}}}}
    assert diff_file('abilities.vdata', old, new) == []
    assert canonical('m_WeaponInfo.m_iClipSize') == 'm_mapWeaponInfos.primary.m_iClipSize'


def test_popular_items_noise_excluded():
    old = {'hero_x': {'m_PopularItems': {'a': 1}, 'hp': 1}}
    new = {'hero_x': {'m_PopularItems': {'a': 2}, 'hp': 1}}
    assert diff_file('heroes.vdata', old, new) == []


def test_identical_change_in_many_entities_collapses_to_shared():
    old = {f'hero_{i}': {'m_x': 1, 'own': i} for i in range(8)}
    new = {f'hero_{i}': {'m_x': 2, 'own': i + (1 if i == 0 else 0)} for i in range(8)}
    res = diff_file('heroes.vdata', old, new)
    shared = [e for e in res if e.id == '@shared']
    assert shared and shared[0].changes[0].path == 'm_x'
    assert len(shared[0].changes[0].targets) == 8
    solo = [e for e in res if e.id == 'hero_0']
    assert solo and [c.path for c in solo[0].changes] == ['own']
    assert collapse_shared([]) == []


def test_added_and_removed_entities():
    res = diff_file('abilities.vdata', {'a': {'v': 1}}, {'b': {'v': 1}})
    status = {e.id: e.status for e in res}
    assert status == {'a': 'removed', 'b': 'added'}


def test_old_bullet_speed_curve_flattens_to_todays_field():
    old = {'m_WeaponInfo': {'m_BulletSpeedCurve': {'m_spline': [{'x': 0, 'y': 18000}, {'x': 100, 'y': 18000}],
                                                   'm_vDomainMaxs': [100, 18000]}}}
    new = {'m_mapWeaponInfos': {'primary': {'m_flBulletSpeed': 16200}}}
    assert flatten(old) == {'m_mapWeaponInfos.primary.m_flBulletSpeed': 18000}
    assert flatten(new) == {'m_mapWeaponInfos.primary.m_flBulletSpeed': 16200}
    # a real curve (speeds differ) is not a single speed: kept as it is
    bent = {'m_BulletSpeedCurve': {'m_spline': [{'x': 0, 'y': 100}, {'x': 1, 'y': 200}]}}
    assert 'm_BulletSpeedCurve.m_spline[1].y' in flatten(bent)


def test_a_unit_change_alone_is_a_change_and_rank_bands_keep_their_place():
    from pipeline.diff import diff_entity, diff_file
    assert [c.path for c in diff_entity({'r': '12'}, {'r': '12m'})] == ['r']
    s1 = {'m_unBaseWinLossPointGrant': 300, 'm_vecRankInfo': [{'m_vecSubRankXP': [1000, 2000]},
                                                               {'m_unRankEnd': 111, 'm_nBadgeShields': 5}]}
    s2 = {'m_unBaseWinLossPointGrant': 350, 'm_vecRankInfo': [{'m_vecSubRankXP': [1000, 1500]},
                                                               {'m_unRankEnd': 91, 'm_nBadgeShields': 3}]}
    got = diff_file('ranked_seasons.vdata', {'season_1': s1}, {'season_1': s1, 'season_2': s2})
    rows = {c.path: (c.old, c.new) for e in got if e.id == 'season_2' for c in e.changes}
    assert rows['m_unBaseWinLossPointGrant'] == (300, 350)          # a new season against the one before it
    assert rows['m_vecRankInfo{1}.m_nBadgeShields'] == (5, 3)       # the band whose end moved is one band
