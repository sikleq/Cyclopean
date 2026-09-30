"""Unit tests for the data pipeline (no tracker clone needed)."""
from pipeline import kv3, semantics
from pipeline.diff import collapse_shared, diff_file
from pipeline.flatten import Num, canonical, flatten
from pipeline.match import MChange, parse_pairs, score, value_matches, words
from pipeline.news import bbcode_lines, parse_lines


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


# ---- semantics ---------------------------------------------------------------

def test_cooldown_increase_is_a_nerf():
    d, pct = semantics.direction('m_mapAbilityProperties.AbilityCooldown.m_strValue', 27, 29)
    assert d == 'nerf' and round(pct, 1) == 7.4


def test_damage_increase_is_a_buff_and_negative_debuff_magnitude():
    assert semantics.direction('m_mapAbilityProperties.Damage.m_strValue', 80, 150)[0] == 'buff'
    # -8% resist shred -> -7%: weaker effect
    assert semantics.direction('m_mapAbilityProperties.BulletResistReduction.m_strValue', -8, -7)[0] == 'nerf'


def test_units_have_no_owner_direction():
    assert semantics.direction('m_nMaxHealth', 5000, 5500, kind='building')[0] == 'changed'


def test_gradient_steps():
    assert semantics.gradient(3) == 1 and semantics.gradient(33) == 6 and semantics.gradient(500) == 10


def test_meters_display():
    assert semantics.display_value(787.4, meters=True) == '20m'


# ---- notes parsing & matching -------------------------------------------------

def test_bbcode_sections_and_bullets():
    text = '[p][b]\\[ Heroes ][/b][/p][list][*]Lash: Flog heal reduced from 50% to 40%[/list]'
    secs = parse_lines(bbcode_lines(text))
    assert secs[-1].title == 'Heroes'
    assert secs[-1].lines == ['Lash: Flog heal reduced from 50% to 40%']


def test_parse_pairs_simple_and_ranges():
    assert parse_pairs('Flog heal reduced from 50% to 40%') == [(50.0, 40.0)]
    assert parse_pairs('Gun falloff range reduced from 18m->54m to 16m->48m') == [(18.0, 16.0), (54.0, 48.0)]
    assert parse_pairs('Cooldown 45s -> 37s') == [(45.0, 37.0)]


def test_value_matches_meters_and_percent():
    assert value_matches(708.66, 18, meters=True)           # 18 m in source units
    assert value_matches(0.3, 30, meters=False)             # fraction vs percent
    assert value_matches(-8, 8, meters=False)               # magnitude


def test_score_prefers_exact_numbers_and_tier():
    c3 = MChange('abilities.vdata', 'ability_lash_flog', 'm_vecAbilityUpgrades[2].m_vecPropertyUpgrades{HealPctVsHeroes}.m_strBonus',
                 'change', 20, 15, 'balance', 'ability', 'hero_lash', 'T3: Heal vs heroes', False)
    c1 = MChange('abilities.vdata', 'ability_lash_flog', 'm_mapAbilityProperties.HealPctVsHeroes.m_strValue',
                 'change', 20, 15, 'balance', 'ability', 'hero_lash', 'Heal vs heroes', False)
    text = 'Flog T3 reduced from +20% heal to +15%'
    s3 = score(c3, text, parse_pairs(text), None, words(text), 3, set())
    s1 = score(c1, text, parse_pairs(text), None, words(text), 3, set())
    assert s3 >= 10 and s3 > s1


def test_same_notes_from_steam_and_forum_become_one_patch():
    from pipeline.news import Notes, Section
    from pipeline.patches import group
    lines = [f'Hero{i}: Damage increased from {i} to {i + 1}' for i in range(6)]
    steam = Notes('Minor Update - 09-16-2026', '2026-09-17', 'u1', 'steam', [Section('Heroes', lines)])
    forum = Notes('09-16-2026 Update', '2026-09-16', 'u2', 'forum', [Section('Heroes', lines + ['Extra line'])])
    teaser = Notes('City Never Sleeps', '2026-09-16', 'u3', 'steam', [Section('General', ['New map', 'Six heroes', 'Spooky'])])
    builds = [{'build': 1, 'date': '2026-09-16T20:00:00+00:00', 'file': 'x', 'fields': {'balance': 5}}]
    ps = group([steam, forum, teaser], builds)
    assert len(ps) == 1
    p = ps[0]
    assert p.title == '09-16-2026 Update' and p.builds == builds
    assert [s.title for s in p.notes.sections] == ['Heroes']      # the teaser is not a changelog


def test_big_build_without_notes_gets_its_own_patch():
    from pipeline.news import Notes, Section
    from pipeline.patches import group
    notes = Notes('01-01-2026 Update', '2026-01-01', 'u', 'forum',
                  [Section('Heroes', [f'H{i}: X increased from 1 to 2' for i in range(5)])])
    builds = [{'build': 1, 'date': '2026-01-01T20:00:00+00:00', 'file': 'a', 'fields': {'balance': 5}},
              {'build': 2, 'date': '2026-01-20T20:00:00+00:00', 'file': 'b', 'fields': {'balance': 900}}]
    ps = group([notes], builds)
    assert [p.id for p in ps] == ['2026-01-01', 'build-2']
    assert [b['build'] for b in ps[1].builds] == [2]


def test_compound_base_plus_scaling_pairs():
    assert parse_pairs('Heal on Melee hit increased from 100+1.5 to 120+1.75') == [(100.0, 120.0), (1.5, 1.75)]


def test_rate_matches_interval_in_notes():
    # "Stamina cooldown increased from 5 to 5.3" while the file stores regen 0.2 -> 0.18867 per second
    assert value_matches(0.2, 5, meters=False) and value_matches(0.18867, 5.3, meters=False)


def test_fix_lines_get_fix_status():
    from pipeline.match import annotate_line
    res = annotate_line('Fixed Haze sometimes not dashing', [], {}, {}, {}, {})
    assert res['status'] == 'fix'


def test_fixed_amount_is_not_a_bug_fix():
    from pipeline.match import annotate_line
    res = annotate_line('Removed a fixed amount of extra bonus souls', [], {}, {}, {}, {})
    assert res['status'] == 'unmatched'
    assert annotate_line('Plated Armor: Fixed on-hit damage', [], {}, {}, {}, {})['status'] == 'fix'


def test_global_slow_line_describes_every_slow_not_one():
    from pipeline.match import general_line
    mk = lambda eid, path, a, b: MChange('abilities.vdata', eid, path, 'change', a, b, 'balance', 'item', None, 'x', False)
    slows = [mk('a', 'm_mapAbilityProperties.SlowPercent.m_strValue', 25, 20),
             mk('b', 'm_mapAbilityProperties.SlowPercent.m_strValue', 99, 66),
             mk('c', 'm_mapAbilityProperties.GroundDashReductionPercent.m_strValue', -20, -18)]
    res = general_line('All move slow values reduced by ~20% globally', slows)
    assert res['status'] == 'described' and len(res['changes']) == 2
    res = general_line('All ground dash slows reduced by ~10% globally', slows)
    assert len(res['changes']) == 1


def test_small_coefficients_keep_decimals():
    assert semantics.display_value(0.005) == '0.005' and semantics.display_value(12.345) == '12.35'


def test_rounded_numbers_in_notes_still_document_the_change():
    c = MChange('abilities.vdata', 'x', 'm_mapAbilityProperties.DPS.m_subclassScaleFunction.m_flStatScale',
                'change', 0.54, 0.6, 'balance', 'ability', 'hero_atlas', 'Damage Per Second (spirit scaling)', False)
    text = 'Siphon Life DPS spirit scaling increased from 0.5 to 0.6'
    from pipeline.match import exact_pair, half_match
    pairs = parse_pairs(text)
    assert not exact_pair(c, pairs) and half_match(c, pairs)
    assert score(c, text, pairs, None, words(text), None, set()) >= 7


def test_projectile_speed_quoted_in_metres_is_rounded_not_mismatch():
    from pipeline.match import data_values, exact_pair
    c = MChange('abilities.vdata', 'upgrade_x', 'm_mapAbilityProperties.Speed.m_strValue', 'change', 2106, 3149.61,
                'balance', 'item', None, 'Speed', False)
    pairs = parse_pairs('Projectile speed increased from 53m/s to 80m/s')
    assert not exact_pair(c, pairs)
    assert score(c, 'x', pairs, None, words('projectile speed'), None, {'abilities.vdata:upgrade_x'}) >= 10
    assert data_values(c, pairs) == ['53.49m', '80m']


def test_two_step_change_in_one_window_matches_both_lines():
    from pipeline.match import exact_pair
    c = MChange('abilities.vdata', 'x', 'p', 'change', 100, 125, 'balance', 'ability', None, 'Bonus Health', False,
                chain=[100, 75, 125])
    assert exact_pair(c, parse_pairs('base health bonus reduced from 100 to 75'))
    assert exact_pair(c, parse_pairs('base health bonus increased from +75 to +125'))


def test_new_value_exact_on_added_property_is_documented():
    from pipeline.match import exact_pair
    c = MChange('abilities.vdata', 'a', 'p', 'add', None, 1.3, 'balance', 'ability', None, 'T3: Unstoppable', False)
    assert exact_pair(c, parse_pairs('changed from 2s Unstoppable to +1.3s Unstoppable'))


def test_forum_follow_ups_become_separate_notes(tmp_path, monkeypatch):
    from pipeline import news
    (tmp_path / '2025-08-18.txt').write_text(
        '08-18-2025 Update\nhttps://x/t\n[ Heroes ]\n- A: X from 1 to 2\n[ Follow-up 2025-08-20 ]\n- Billy: Health per boon reduced from 44 to 43\n',
        encoding='utf-8')
    monkeypatch.setattr(news, 'FORUM_DIR', tmp_path)
    ns = news.forum_notes()
    assert [(n.date, n.title) for n in ns] == [('2025-08-18', '08-18-2025 Update'),
                                               ('2025-08-20', '08-18-2025 Update · follow-up 2025-08-20')]
    assert ns[1].sections[0].lines == ['Billy: Health per boon reduced from 44 to 43']


def test_parse_pairs_words_between_number_and_to():
    assert parse_pairs('Flog T3 reduced from +40 degrees angle to +25') == [(40.0, 25.0)]
    assert parse_pairs('Wrecking Ball: Increase base Damage from 80 to 150') == [(80.0, 150.0)]
