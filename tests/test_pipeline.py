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


def test_upgrade_bonus_direction_follows_the_sign():
    # Shoulder Charge T3 "-20s cooldown" -> "-18s": a smaller reduction is a nerf
    p = 'm_vecAbilityUpgrades[2].m_vecPropertyUpgrades{AbilityCooldown}.m_strBonus'
    assert semantics.direction(p, -20, -18)[0] == 'nerf'
    assert semantics.direction(p, -18, -20)[0] == 'buff'


def test_damage_increase_is_a_buff_and_negative_debuff_magnitude():
    assert semantics.direction('m_mapAbilityProperties.Damage.m_strValue', 80, 150)[0] == 'buff'
    # -8% resist shred -> -7%: weaker effect
    assert semantics.direction('m_mapAbilityProperties.BulletResistReduction.m_strValue', -8, -7)[0] == 'nerf'


def test_polarity_reads_the_property_name_not_its_container():
    d = semantics.direction
    # investment bonuses live in m_MapModCostBonuses: "Cost" in the container must not flip the bonus
    assert d('m_MapModCostBonuses.EItemSlotType_Armor[4].flBonus', 22, 34)[0] == 'buff'
    assert d('m_MapModCostBonuses.EItemSlotType_Armor[5].nGoldThreshold', 7200, 6400)[0] == 'buff'
    # "Reduction" / "Refund" / "Decay" after a lower-is-better word turn it around
    assert d('m_mapAbilityProperties.CooldownReduction.m_strValue', 10, 15)[0] == 'buff'
    assert d('m_mapAbilityProperties.StaminaCooldownReduction.m_strValue', 10, 14)[0] == 'buff'
    assert d('m_mapAbilityProperties.CooldownBetweenChargeReduction.m_strValue', 40, 55)[0] == 'buff'
    assert d('m_mapWeaponInfos.primary.m_flShootSpreadPenaltyDecay', 2.5, 5)[0] == 'buff'
    # a lower-is-better value compares with its sign: an enemy healing penalty -65 -> -70 is stronger
    assert d('m_mapAbilityProperties.HealAmpReceivePenaltyPercent.m_strValue', -65, -70)[0] == 'buff'
    assert d('m_mapAbilityProperties.InAirDamageReceived.m_strValue', -40, -60)[0] == 'buff'
    # unchanged: cooldowns, enemy slows, resist shred
    assert d('m_mapAbilityProperties.AbilityCooldown.m_strValue', 27, 29)[0] == 'nerf'
    assert d('m_mapAbilityProperties.SlowPercent.m_strValue', 25, 35)[0] == 'buff'
    assert d('m_mapAbilityProperties.BulletArmorReduction.m_strValue', -10, -12)[0] == 'buff'


def test_shorter_tick_interval_is_a_buff():
    # Rem: Infest Heal Interval 3 -> 2 heals more often
    assert semantics.direction('m_mapAbilityProperties.InfestHealInterval.m_strValue', 3, 2)[0] == 'buff'
    assert semantics.direction('m_mapAbilityProperties.TickInterval.m_strValue', 0.5, 1)[0] == 'nerf'


def test_shared_objects_go_up_or_down_unless_the_player_side_is_plain():
    d = semantics.direction
    assert d('m_nMaxHealth', 4600, 5000, kind='building')[0] == 'up'
    assert d('m_flSightRangePlayers', 1500, 1338.58, kind='building')[0] == 'down'
    # a camp's bounty and a shorter respawn help whoever takes it
    assert d('m_flGoldReward', 275, 220, kind='neutral')[0] == 'nerf'
    assert d('m_iSpawnIntervalInSeconds', 300, 240, kind='global')[0] == 'buff'
    assert d('m_sModifer.m_flDuration', 60, 80, kind='global')[0] == 'buff'


def test_units_have_no_owner_direction():
    # no buff/nerf for a building's health: both teams have it (the tag says UP instead)
    assert semantics.direction('m_nMaxHealth', 5000, 5500, kind='building')[0] not in ('buff', 'nerf')


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


def test_a_post_without_text_only_names_a_window():
    """2026-10-02 "Listen up, Crumbums! Your King is here." (Rat King) came without text: it names the
    notes-less build of its day, but opens no window and drops no follow-up of that date."""
    from pipeline.news import TITLE_ONLY, Notes, Section
    from pipeline.patches import group
    reveal = Notes('Listen up, Crumbums! Your King is here.', '2026-01-20', 'u', TITLE_ONLY, [])
    notes = Notes('01-01-2026 Update', '2026-01-01', 'n', 'forum',
                  [Section('Heroes', [f'H{i}: X increased from 1 to 2' for i in range(5)])])
    builds = [{'build': 1, 'date': '2026-01-01T20:00:00+00:00', 'file': 'a', 'fields': {'balance': 5}},
              {'build': 2, 'date': '2026-01-20T20:00:00+00:00', 'file': 'b', 'fields': {'balance': 200}}]
    ps = group([notes, reveal], builds)
    assert [p.title for p in ps] == ['01-01-2026 Update', 'Listen up, Crumbums! Your King is here.']
    # beside a changelog, a small build stays in its window: the title-only post makes no new one
    small = [builds[0], {'build': 2, 'date': '2026-01-02T20:00:00+00:00', 'file': 'b', 'fields': {'balance': 200}}]
    reveal2 = Notes('Reveal', '2026-01-02', 'u', TITLE_ONLY, [])
    assert [p.id for p in group([notes, reveal2], small)] == ['2026-01-01']


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
    # 25 -> 20 is the announced ~20%; 99 -> 66 (-33%) is NOT what the line says: it stays hidden
    assert res['status'] == 'described' and len(res['changes']) == 1
    res = general_line('All ground dash slows reduced by ~10% globally', slows)
    assert len(res['changes']) == 1


def test_global_line_with_an_amount_covers_every_hero_it_moved():
    from pipeline.match import num
    from pipeline.match_rules import global_delta_line
    hp = 'm_mapStartingStats.EMaxHealth'
    mk = lambda eid, a, b, path=hp: MChange('heroes.vdata', eid, path, 'change', a, b, 'balance', 'hero', None, 'x',
                                            False, chain=[a, b])
    cat = {f'heroes.vdata:h{i}': {'kind': 'hero'} for i in range(6)}
    heroes = [mk('h0', 800, 790), mk('h1', 770, 760), mk('h2', 900, 890), mk('h3', 700, 720), mk('h4', 650, 640),
              mk('h5', 6.6, 6.5, 'm_mapStartingStats.EMaxMoveSpeed')]
    hit = global_delta_line('Base HP reduced by 10 for all heroes', heroes, cat, num)
    assert sorted(c.eid for c in hit) == ['h0', 'h1', 'h2', 'h4']          # +20 and the move speed are not it
    assert global_delta_line('Base move speed reduced by 0.1', heroes, cat, num) is None   # one hero is not a rule
    guns = [MChange('abilities.vdata', f'w{i}', 'm_mapWeaponInfos.primary.m_flCycleTime', 'change', 0.2, 0.21,
                    'balance', 'weapon', None, 'x', False, chain=[0.2, 0.21]) for i in range(3)]
    wcat = {f'abilities.vdata:w{i}': {'kind': 'weapon'} for i in range(3)}
    assert len(global_delta_line('Bullet Cycle Time for all heroes increased by 5%', guns, wcat, num)) == 3
    # a narrower family wins over "health": item bonus health, not hero max health
    items = [MChange('abilities.vdata', f'i{i}', 'm_mapAbilityProperties.BonusHealth.m_strValue', 'change', a, a - 25,
                     'balance', 'item', None, 'x', False, chain=[a, a - 25]) for i, a in enumerate((150, 125, 90))]
    icat = {f'abilities.vdata:i{i}': {'kind': 'item'} for i in range(3)}
    assert len(global_delta_line('Bonus Health on all Weapon and Spirit items is reduced by ~25', items, icat, num)) == 3
    # "+3 and 4%": 46 -> 46 * 1.04 + 3 = 50.8 -> 51 in the files
    boon = [MChange('heroes.vdata', f'h{i}', 'm_mapStandardLevelUpUpgrades.MODIFIER_VALUE_BASE_HEALTH_FROM_LEVEL', 'change',
                    a, b, 'balance', 'hero', None, 'x', False, chain=[a, b]) for i, (a, b) in enumerate(((46, 51), (39, 44), (52, 57)))]
    assert len(global_delta_line('Hero health growth increased by +3 and 4%', boon, cat, num)) == 3
    # review 2026-10-01: an "increased by 5%" line never covers a decrease or a big jump on small values
    odd = [MChange('abilities.vdata', f'w{i}', 'm_mapWeaponInfos.primary.m_flCycleTime', 'change', 0.5, b,
                   'balance', 'weapon', None, 'x', False, chain=[0.5, b]) for i, b in enumerate((0.3, 0.2, 0.7))]
    assert global_delta_line('Bullet Cycle Time for all heroes increased by 5%', odd, wcat, num) is None
    # two stats in one line: both families are covered
    two = [mk(f'h{i}', 6.6, 6.5, 'm_mapStartingStats.EMaxMoveSpeed') for i in range(3)] + \
          [mk(f'h{i}', 2.0, 1.9, 'm_mapStartingStats.ESprintSpeed') for i in range(3)]
    assert len(global_delta_line('Move speed and sprint speed reduced by 0.1', two, cat, num)) == 6


def test_ultimate_cooldown_line_covers_only_ultimates_with_that_ratio():
    from pipeline.match import general_line
    cat = {'abilities.vdata:ult': {'kind': 'ability', 'ability_slot': 'Signature_4'},
           'abilities.vdata:q': {'kind': 'ability', 'ability_slot': 'Signature_1'}}
    mk = lambda eid, a, b: MChange('abilities.vdata', eid, 'm_mapAbilityProperties.AbilityCooldown.m_strValue',
                                   'change', a, b, 'balance', 'ability', None, 'Cooldown', False)
    res = general_line("All ultimate abilities' cooldowns increased by 15%", [mk('ult', 150, 170), mk('q', 20, 23)], cat)
    assert res['changes'] == ['abilities.vdata:ult:m_mapAbilityProperties.AbilityCooldown.m_strValue']


def test_unit_named_inside_a_line_without_colon():
    from pipeline.match_rules import alias_keys
    assert 'npc_units.vdata:npc_boss_tier2' in alias_keys('Walker bounty increased by 5%')


def test_feature_fields_cluster():
    from pipeline.match_rules import cluster_root
    assert cluster_root('m_flParryCancelAirGlideDuration') == cluster_root('m_flParryCancelAirGravityScale')
    assert cluster_root('m_mapWeaponInfos.primary.m_iBullets') == 'm_mapWeaponInfos'


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


def test_note_that_landed_in_a_later_build_is_linked():
    from types import SimpleNamespace
    from pipeline.match import late_landings
    cat = {'heroes.vdata:hero_x': {'file': 'heroes.vdata', 'id': 'hero_x', 'name': 'X'}}
    line = {'text': "Diviner's Kevlar: Cooldown Reduction reduced from 12% to 10%", 'subject': "Diviner's Kevlar",
            'status': 'unmatched', 'changes': []}
    early = (SimpleNamespace(id='a', date='2024-12-06', title='A'),
             {'sections': [{'title': 'Items', 'lines': [line]}], 'entities': [],
              'counts': {'hidden': 0}, 'line_counts': {'unmatched': 1}})
    change = {'key': 'k', 'label': 'Cooldown Reduction', 'old_s': '12', 'new_s': '10', 'cat': 'balance',
              'status': 'hidden', 'builds': [5433]}
    later = (SimpleNamespace(id='b', date='2024-12-14', title='B'),
             {'sections': [], 'entities': [{'name': "Diviner's Kevlar", 'owner': None, 'changes': [change]}],
              'counts': {'hidden': 1, 'documented': 0}, 'line_counts': {}})
    too_late = (SimpleNamespace(id='c', date='2025-02-01', title='C'), later[1])
    assert late_landings([early, too_late], cat) == 0
    assert late_landings([early, later], cat) == 1
    assert line['status'] == 'documented' and line['late']['builds'] == [5433]
    assert change['status'] == 'documented' and later[1]['counts'] == {'hidden': 0, 'documented': 1}


def test_a_change_hotfixed_across_a_window_edge_is_one_line():
    """2025-11-21 "Lucky Shot: Damage reduced from 125% to 110%": 125 -> 120 in build 5983 (the notes'
    window), 120 -> 110 an hour later in 5984 (the follow-up's window). Both steps are the line."""
    from types import SimpleNamespace
    from pipeline.match import late_landings
    line = {'text': 'Lucky Shot: Damage reduced from 125% to 110%', 'subject': 'Lucky Shot',
            'status': 'unmatched', 'changes': []}
    first = {'key': 'k', 'label': 'Bonus Weapon Damage', 'old_s': '125%', 'new_s': '120%', 'cat': 'balance',
             'status': 'hidden', 'builds': [5983]}
    second = {**first, 'old_s': '120%', 'new_s': '110%', 'builds': [5984]}
    own = (SimpleNamespace(id='a', date='2025-11-21', title='A'),
           {'sections': [{'lines': [line]}], 'entities': [{'name': 'Lucky Shot', 'owner': None, 'changes': [first]}],
            'counts': {'hidden': 1, 'documented': 0}, 'line_counts': {'unmatched': 1}})
    later = (SimpleNamespace(id='b', date='2025-11-22', title='B'),
             {'sections': [], 'entities': [{'name': 'Lucky Shot', 'owner': None, 'changes': [second]}],
              'counts': {'hidden': 1, 'documented': 0}, 'line_counts': {}})
    assert late_landings([own, later], {}) == 1
    assert line['status'] == 'documented' and line['changes'] == ['k'] and line['late']['patch'] == 'b'
    assert first['status'] == second['status'] == 'documented'
    assert own[1]['counts'] == {'hidden': 0, 'documented': 1} and later[1]['counts'] == {'hidden': 0, 'documented': 1}


def test_notes_less_window_implementing_a_changelog_is_merged(monkeypatch):
    from pipeline import match
    from pipeline.patches import Patch
    monkeypatch.setattr(match, 'ABSORB_MIN', 2)
    monkeypatch.setattr(match, 'build_patch', lambda p, cat: {'rebuilt': [b['build'] for b in p.builds]})
    lines = [{'text': f'Kevlar: Stat{w} increased from {i} to {i + 1}', 'subject': 'Kevlar', 'status': 'unmatched',
              'changes': []} for w, i in (('alpha', 1), ('beta', 5))]
    notes = match.Patch('2024-12-06', 'A', '2024-12-06', notes=object(), builds=[{'build': 1, 'date': '2024-12-06'}])
    later = Patch('build-2', 'B', '2024-12-14', notes=None, builds=[{'build': 2, 'date': '2024-12-14'}])
    changes = [{'label': f'Stat{w}', 'old_s': str(i), 'new_s': str(i + 1), 'cat': 'balance', 'status': 'unannounced'}
               for w, i in (('alpha', 1), ('beta', 5))]
    results = [(notes, {'sections': [{'lines': lines}]}),
               (later, {'sections': [], 'entities': [{'name': 'Kevlar', 'owner': None, 'changes': changes}]})]
    merged, absorbed = match.absorb_late_windows(results, {})
    assert absorbed == ['build-2'] and len(merged) == 1 and merged[0][1] == {'rebuilt': [1, 2]}


def test_line_of_an_edited_post_points_to_the_later_patch():
    from types import SimpleNamespace
    from pipeline.match import repeated_lines
    text = 'Celestial Blessing: Heal min increased from 300 to 400'
    early = {'sections': [{'lines': [{'text': text, 'status': 'unmatched'}]}], 'line_counts': {'unmatched': 1}}
    later = {'sections': [{'lines': [{'text': text, 'status': 'documented'}]}], 'line_counts': {'documented': 1}}
    results = [(SimpleNamespace(id='2026-03-06', title='A'), early), (SimpleNamespace(id='2026-03-21', title='B'), later)]
    assert repeated_lines(results) == 1
    ln = early['sections'][0]['lines'][0]
    assert ln['status'] == 'repeated' and ln['see']['patch'] == '2026-03-21'
    assert early['line_counts'] == {'unmatched': 0, 'repeated': 1}


def test_unit_kind_reads_the_id_before_the_class():
    from pipeline.classify import unit_kind
    # neutral camps and Guardians are npc_trooper subclasses in the data
    assert unit_kind('neutral_lantern_weak', {'_class': 'npc_trooper'}) == 'neutral'
    assert unit_kind('npc_boss_tier1', {'_class': 'npc_trooper_boss'}) == 'building'
    assert unit_kind('npc_super_neutral', {}) == 'neutral'
    assert unit_kind('trooper_medic', {'_class': 'npc_trooper'}) == 'trooper'


def test_date_titled_changelog_takes_the_announcement_name():
    from pipeline.news import Notes
    from pipeline.patches import _titled
    ann = Notes('City Never Sleeps', '2026-09-29T17:00:00+00:00', 'https://x', 'forum', [])
    notes = Notes('09-29-2026', '2026-09-29', 'https://y', 'forum', [])
    assert _titled(notes, [ann]) == 'City Never Sleeps · 09-29-2026'
    assert _titled(Notes('09-16-2026 Update', '2026-09-16', 'u', 'forum', []), [ann]) == '09-16-2026 Update'


def test_parse_pairs_thousands_separator():
    assert parse_pairs('Side Walkers HP increased from 5,175 to 7,000.') == [(5175.0, 7000.0)]
    assert parse_pairs('Patron health from 12,000 to 13,500') == [(12000.0, 13500.0)]
    # an unspaced per-tier list is not a thousands number
    assert parse_pairs('Bounty from 160,180,200 to 170,190,210') != [(160180200.0, 170190210.0)]


def test_weapon_name_comes_from_the_owning_hero():
    from pipeline import loc
    tok = {'citadel_weapon_atlas_set': 'Case Closed', 'citadel_weapon_atlas_set_desc': 'Reloads single shells'}
    assert loc.entity_name(tok, 'citadel_weapon_bull_set', 'hero_atlas') == 'Case Closed'
    assert loc.loc_base(tok, 'citadel_weapon_bull_set', 'hero_atlas') == 'citadel_weapon_atlas_set'
    assert loc.entity_name(tok, 'citadel_weapon_bull_set') == 'citadel_weapon_bull_set'   # no owner: id
    assert loc.entity_name({'x': 'Own'}, 'x', 'hero_atlas') == 'Own'                      # own name first
    tok = {'citadel_weapon_shiv_set': 'Busted Flush'}
    assert loc.entity_name(tok, 'citadel_weapon_shiv_alt', 'hero_shiv') == 'citadel_weapon_shiv_alt'  # alt fire


def test_loc_pairs_without_a_gap_are_read():
    from pipeline import loc
    text = ('"lang" { "Tokens" {\n\t\t"viscous_gootapult""Splatapult"\n'
            '\t\t"MaxBounces_label"\t"Bounces"\n\t\t"x_desc" "a \\"q\\" b"\n} }')
    tok = loc.parse(text)
    # Valve sometimes writes "key""value" with no whitespace; the game reads it, so do we
    assert tok['viscous_gootapult'] == 'Splatapult'
    assert tok['maxbounces_label'] == 'Bounces' and tok['x_desc'] == 'a "q" b'


def test_units_without_a_loc_name_take_the_games_other_strings():
    from pipeline import loc
    tok = {'titan_unit': 'Patron', 'citadel_attackerclass_class_trooper_medic': 'Medic Trooper', 'guardian_unit': 'Guardian'}
    assert loc.unit_name(tok, 'alt_npc_boss_tier3', {}) == 'Patron'
    assert loc.unit_name(tok, 'trooper_medic', {}) == 'Medic Trooper'
    assert loc.unit_name(tok, 'npc_boss_tier1', {'m_sLocUnitName': '#guardian_unit'}) == 'Guardian'
    assert loc.unit_name(tok, 'npc_neutral_bug', {}) == 'npc_neutral_bug'     # never named: the site prettifies it


def test_history_bridges_only_holes_in_the_data():
    from pipeline.hero_table import MISSING, history_changes
    # Billy's weapon was cut from the files on 2025-08-18..08-20: one change 11.26 -> 11.62, not two
    pts = [[5700, '2025-08-01', 11.26], [5747, '2025-08-18', MISSING], [5789, '2025-08-20', 11.62]]
    assert history_changes(pts) == [[5789, '2025-08-20', 11.26, 11.62]]
    assert history_changes([[1, 'a', 5.0], [2, 'b', MISSING], [3, 'c', 5.0]]) == []
    # a stat REMOVED and later restored (an absent field, None) is two real changes with their dates
    assert history_changes([[1, 'a', 16.0], [2, 'b', None], [3, 'c', 15.0]]) == [[2, 'b', 16.0, None], [3, 'c', None, 15.0]]
    # gone at the end stays a removal; a later start is a first value
    assert history_changes([[1, 'a', 5.0], [2, 'b', MISSING]]) == [[2, 'b', 5.0, None]]
    assert history_changes([[1, 'a', None], [2, 'b', 3.0]]) == [[2, 'b', None, 3.0]]


def test_old_builds_bullet_speed_and_dash():
    from pipeline.hero_table import _dash, bullet_speed, burst_cycle
    curve = {'m_BulletSpeedCurve': {'m_spline': [{'x': 0, 'y': 39370}, {'x': 100, 'y': 39370}]}}
    assert round(bullet_speed({}, curve, None)) == 1000             # a flat curve is the speed (before 5747)
    assert burst_cycle({}, {'m_flCycleTime': 0.1}, None) == 0.0      # omitted = the game's default
    hero = {'m_mapBoundAbilities': {'ESlot_Ability_Innate_1': 'citadel_ability_dash'}}
    abil = {'citadel_ability_dash': {'m_mapAbilityProperties': {'AbilityDuration': {'m_strValue': '0.6'}}}}
    assert _dash('EGroundDashDuration', 'AbilityDuration')(hero, {}, abil) == 0.6   # before 5706: the shared dash


def test_old_bullet_speed_curve_flattens_to_todays_field():
    old = {'m_WeaponInfo': {'m_BulletSpeedCurve': {'m_spline': [{'x': 0, 'y': 18000}, {'x': 100, 'y': 18000}],
                                                   'm_vDomainMaxs': [100, 18000]}}}
    new = {'m_mapWeaponInfos': {'primary': {'m_flBulletSpeed': 16200}}}
    assert flatten(old) == {'m_mapWeaponInfos.primary.m_flBulletSpeed': 18000}
    assert flatten(new) == {'m_mapWeaponInfos.primary.m_flBulletSpeed': 16200}
    # a real curve (speeds differ) is not a single speed: kept as it is
    bent = {'m_BulletSpeedCurve': {'m_spline': [{'x': 0, 'y': 100}, {'x': 1, 'y': 200}]}}
    assert 'm_BulletSpeedCurve.m_spline[1].y' in flatten(bent)


def test_returned_entity_diffs_against_its_last_version(monkeypatch):
    from pipeline import cache, history, tracker
    path = tracker.VDATA_PATHS[0]
    blobs = {'b1': {'x': {'dmg': 10, 'cd': 5}}, 'b2': {}, 'b3': {'x': {'dmg': 12, 'cd': 5}}}
    monkeypatch.setattr(tracker, 'VDATA_PATHS', (path,))
    monkeypatch.setattr(tracker, 'blob_id', lambda commit, p: commit if p == path else None)
    monkeypatch.setattr(cache, 'vdata_blob', lambda blob: blobs[blob])
    builds = [tracker.Build(c, '2025-01-0' + c[1], int(c[1]), (path,)) for c in ('b1', 'b2', 'b3')]
    known: dict = {}
    history.entity_changes(builds[0], builds[0], known)                     # baseline
    gone = history.entity_changes(builds[0], builds[1], known)
    back = history.entity_changes(builds[1], builds[2], known)
    assert [e['status'] for e in gone] == ['removed']
    # Valve cut it and put it back: "dmg 10 -> 12", not "everything added"
    assert [(e['status'], [(c['path'], c['old'], c['new']) for c in e['changes']]) for e in back] == \
        [('returned', [('dmg', 10, 12)])]


def test_notes_give_the_old_value_of_a_field_that_appeared():
    from pipeline.match import MChange, _old_from_notes, change_json
    c = MChange('abilities.vdata', 'ability_stacking_damage', 'm_mapAbilityProperties.HeadshotStacks.m_strValue',
                'add', None, 3, 'balance', 'ability', 'hero_haze', 'Headshot Stacks', False, [6600], False)
    _old_from_notes(c, [(2.0, 3.0)])            # "Headshot stack count increased from +2 to +3"
    j = change_json(c)
    assert (j['op'], j['old_s'], j['new_s'], j['dir']) == ('change', '2', '3', 'buff')
    other = MChange('f', 'e', 'p', 'add', None, 5, 'balance', '', None, 'X', False, [1], False)
    _old_from_notes(other, [(2.0, 3.0)])        # the line's numbers are about something else
    assert other.op == 'add' and other.old is None


def test_the_holders_own_downside_grows_as_a_nerf():
    from pipeline.enrich import drawbacks
    egg = {'m_mapAbilityProperties': {'OutgoingDamagePenaltyPercent': {'m_strValue': '-15', 'm_bIsNegativeAttribute': True},
                                      'BonusHealth': {'m_strValue': '100'}}}
    assert drawbacks(egg) == {'OutgoingDamagePenaltyPercent'}
    path = 'm_mapAbilityProperties.OutgoingDamagePenaltyPercent.m_strValue'
    # Golden Goose Egg: "Damage Penalty increased from -10% to -15%" is worse for its owner
    assert semantics.direction(path, -10, -15, 'item', drawback=True)[0] == 'nerf'
    assert semantics.direction(path, -15, -10, 'item', drawback=True)[0] == 'buff'


def test_mechanics_audit_cases():
    # investment steps keyed by their souls threshold: a step inserted at 6,400 shifts nothing
    o = {'m_MapModCostBonuses': {'EItemSlotType_Armor': [{'nGoldThreshold': 800, 'flBonus': 8},
                                                         {'nGoldThreshold': 6400, 'flBonus': 34}]}}
    assert 'm_MapModCostBonuses.EItemSlotType_Armor{6400}.flBonus' in flatten(o)
    assert semantics.describe('m_MapModCostBonuses.EItemSlotType_Armor{6400}.flBonus', {})['label'] == \
        'Vitality investment at 6,400 souls: bonus'
    # a % <-> flat HP switch is not an 837% buff
    assert semantics.direction('m_MapModCostBonuses.EItemSlotType_Armor{800}.flBonus', 8, 75, 'hero') == ('changed', None)
    # a placeholder speed curve does not beat the field after build 5747
    w = {'m_flBulletSpeed': 25000, 'm_BulletSpeedCurve': {'m_spline': [{'x': 0, 'y': 22500}, {'x': 1, 'y': 22500}]}}
    assert flatten(w, curve_wins=False) == {'m_flBulletSpeed': 25000}
    assert flatten(w) == {'m_flBulletSpeed': 22500}
    # directions: a longer dash over a fixed distance is slower; a smaller self-slow is better; the
    # parried enemy's damage taken is ours to raise
    assert semantics.direction('m_mapStartingStats.EGroundDashDuration', 0.68, 0.7, 'hero')[0] == 'nerf'
    assert semantics.direction('m_MantleSlowOnHitModifier.m_flPercentageMultiplierStart', 80, 64, 'ability')[0] == 'buff'
    assert semantics.direction('m_mapAbilityProperties.VictimDamageTakenScale.m_strValue', 30, 25, 'ability')[0] == 'nerf'
    # values Valve writes in metres / m/s are not divided again
    assert semantics.display_raw(18, semantics.engine_unit('m_flDashJumpDistanceInMeters')) == '18m'
    assert semantics.display_raw(13, semantics.engine_unit('m_flClimbSpeedUp')) == '13m/s'
    # base stat units: speeds in m/s, times in s, no % on a multiplier
    tok = {'statdesc_runspeed_postfix': 'm', 'statdesc_critdamagebonusscale_postfix': '%'}
    assert semantics.describe('m_mapStartingStats.ERunSpeed', tok)['unit'] == 'm/s'
    assert semantics.describe('m_mapStartingStats.EGroundDashDuration', tok)['unit'] == 's'
    assert semantics.describe('m_mapStartingStats.ECritDamageBonusScale', tok)['unit'] == ''


def test_hero_table_audit_cases():
    from pipeline.hero_table import _lvl, borrowed_guns
    hero = {'m_mapStandardLevelUpUpgrades': {'MODIFIER_VALUE_TECH_RESIST': 0.625, 'MODIFIER_VALUE_BONUS_ATTACK_RANGE': 59}}
    assert _lvl('MODIFIER_VALUE_TECH_ARMOR_DAMAGE_RESIST', 'MODIFIER_VALUE_TECH_RESIST')(hero, {}, {}) == 0.625
    assert round(_lvl('MODIFIER_VALUE_BONUS_ATTACK_RANGE', meters=True)(hero, {}, {}), 2) == 1.5
    gun = {'m_mapBoundAbilities': {'ESlot_Weapon_Primary': 'citadel_weapon_inferno_set'}}
    assert borrowed_guns({'hero_inferno': gun, 'hero_baba': gun, 'hero_atlas':
                          {'m_mapBoundAbilities': {'ESlot_Weapon_Primary': 'citadel_weapon_bull_set'}}}) == {'hero_baba'}


def test_values_carry_the_tooltip_unit_and_label():
    tok = {'abilitycooldown_postfix': 's', 'buffduration_label': 'Shield Duration', 'buffduration_postfix': 's',
           'enemyslow_postfix': '%'}
    d = semantics.describe('m_mapAbilityProperties.AbilityCooldown.m_strValue', tok, 'x', 'ability')
    assert d['unit'] == 's' and semantics.with_unit('30', d['unit']) == '30s'
    # the tooltip names a property by its m_strLocTokenOverride
    d = semantics.describe('m_mapAbilityProperties.SpeedOnLandDuration.m_strValue', tok, 'x', 'ability', token='BuffDuration')
    assert (d['label'], d['unit']) == ('Shield Duration', 's')
    d = semantics.describe('m_vecAbilityUpgrades[2].m_vecPropertyUpgrades{EnemySlow}.m_strBonus', tok, 'x', 'ability')
    assert semantics.with_unit('-50', d['unit']) == '-50%'
    assert semantics.with_unit('12.19m', 'm') == '12.19m' and semantics.with_unit('—', 's') == '—'


def test_units_and_reencodings():
    assert semantics.engine_unit('m_flRunSpeed') == semantics.SPEED
    assert semantics.engine_unit('m_flSightRangePlayers') is True
    assert semantics.engine_unit('m_flBossDamageScale') == semantics.FRACTION     # a share: 0.5 is 50%
    assert semantics.engine_unit('m_flAbilityDamageScale') is False
    assert semantics.display_raw(18000, semantics.SPEED) == '457.2m/s'
    assert semantics.display_raw('12.19m', True) == '12.19m'               # already metres: not divided again
    p = 'm_mapAbilityProperties.ChannelMoveSpeed.m_strValue'
    assert semantics.reencoded(200, '5.1m', p)                              # 200 units/s is 5.1 m/s
    assert semantics.reencoded(1, 100, 'm_mapAbilityProperties.ImbuedCooldownMultiplier.m_strValue')
    assert not semantics.reencoded(1, 100, 'm_mapAbilityProperties.Damage.m_strValue')
    assert semantics.direction(p, 50, -1, 'ability') == ('changed', None)   # -1 = no cap


def test_shares_speeds_and_curve_corners():
    """Audit 2026-10-02: shares as percents, travel speeds in m/s, a curve's corners named min/max."""
    w = semantics.describe('m_mapWeaponInfos.primary.m_flShootMoveSpeedPercent', {}, 'citadel_weapon_bebop_set', 'weapon')
    assert semantics.show(0.55, w['meters']) == '55%' and semantics.show('0.7', w['meters']) == '70%'
    assert semantics.show(0.1, semantics.FRACTION) == '10%'
    zip_ = semantics.describe('m_mapAbilityProperties.ZipSpeed.m_strValue', {}, 'citadel_ability_zip_line', 'ability')
    assert semantics.show('693', zip_['meters']) == '17.6m/s'
    for prop in ('TossSpeedUpWall', 'ReturnSpeedNonPlayer', 'AttackingDashSpeed', 'InitialProjectileVelocity'):
        assert semantics.prop_speed(prop), prop
    for prop in ('ChannelMoveSpeed', 'MoveSpeedBonusPct', 'TrackingSpeed', 'ZipMasteryExtraSpeedBonus',
                 'BonusBulletSpeedPercent', 'FallSpeedMax', 'PostGroundDashSpeed', 'SummonTurnSpeed'):
        assert not semantics.prop_speed(prop), prop
    assert not semantics.prop_speed('ZipSpeed', 'm/s')            # the tooltip's own unit: already m/s
    assert semantics.humanize('m_vDomainMaxs') == 'Domain (max)'
    assert semantics.humanize('m_vDomainMins') == 'Domain (min)'
    assert semantics.humanize('m_iMatchTimeMinsForLevel2Pickups') == 'Match Time (min) For Level2 Pickups'
    # a powerup's modifier value is named by what it changes, not "Modifier Values MODIFIER_VALUE_X › Modifier Value"
    assert semantics.context_label('m_sModifer.m_vecModifierValues{MODIFIER_VALUE_STAMINA}.m_flModifierValue') == \
        'Effect › Stamina'


def test_npc_abilities_belong_to_their_unit():
    from pipeline.classify import unit_bound_abilities
    units = {'npc_boss_tier2': {'m_mapBoundAbilities': {'ESlot_Signature_1': 'citadel_ability_tier2boss_stomp'}},
             'alt_npc_boss_tier2': {'m_mapBoundAbilities': {'ESlot_Signature_1': 'citadel_ability_tier2boss_stomp'}},
             'trooper_zipline_container': {'m_mapBoundAbilities': {'ESlot_Ability_ZipLine': 'citadel_ability_zip_line'}}}
    bound = unit_bound_abilities(units, {'citadel_ability_zip_line': 'hero_base'})
    assert bound == {'citadel_ability_tier2boss_stomp': ['alt_npc_boss_tier2', 'npc_boss_tier2']}
    # judged as the unit: Walker's laser 150 -> 125 DPS is DOWN, not a player's NERF
    assert semantics.direction('m_mapAbilityProperties.DPS.m_strValue', 150, 125, 'unit')[0] == 'down'


def test_added_and_removed_entities_that_matter():
    from pipeline.match import event_worthy
    assert event_worthy({'kind': 'ability_other', 'id': 'viscous_gootapult', 'name': 'Splatapult'})
    assert not event_worthy({'kind': 'ability_other', 'id': 'synth_dematerialize', 'name': 'synth_dematerialize'})
    assert event_worthy({'kind': 'ability_other', 'id': 'citadel_ability_tier3boss_damage_pulse',
                         'name': 'citadel_ability_tier3boss_damage_pulse', 'units': ['npc_boss_tier3']})
    assert event_worthy({'kind': 'global', 'id': 'ammo_permanent_pickup', 'gameplay': True})
    assert not event_worthy({'kind': 'global', 'id': 'm_KillStreakFireParticle', 'gameplay': False})
    assert not event_worthy({'kind': 'modifier', 'id': 'modifier_speed_boost', 'name': 'x'})
    assert not event_worthy({'kind': 'melee', 'id': 'ability_melee_mirage', 'name': 'Melee'})   # the hero's event
    # the name a removed ability had in game comes from the catalog (its text left with it)
    from pipeline.match import event_name
    gone = {'id': 'ability_priest_barrage', 'name': 'ability_priest_barrage', 'status': 'removed'}
    assert event_name(gone, {'name': 'Witching Hour'}) == 'Witching Hour'
    assert event_worthy({'kind': 'ability_other', 'id': gone['id'], 'name': event_name(gone, {'name': 'Witching Hour'})})
    assert event_name({'id': 'x_y', 'name': 'Shown'}, {'name': 'Catalog'}) == 'Shown'


def test_readable_names_for_ids_and_stand_ins():
    from builders.common import pretty_id
    assert pretty_id('slork_ability_invis', 'hero_slork') == 'Invis'
    assert pretty_id('citadel_ability_tier2boss_aoe_wave') == 'AoE wave'
    assert pretty_id('hero_airheart') == 'Airheart'
    assert semantics.show('20%', semantics.FRACTION) == '20%'            # already a percent: not ×100
    fencer = semantics.describe('m_vecAbilityUpgrades[2].m_vecPropertyUpgrades{DashSpeed}.m_strBonus', {},
                                'ability_fencer_lunge', 'ability')
    assert semantics.show('550', fencer['meters']) == '13.97m/s'
    assert not semantics.prop_speed('DistanceForMaxProjSpeed') and not semantics.prop_speed('CameraPreviewSpeed')


def test_polarity_audit_cases():
    d = lambda prop, a, b, **kw: semantics.direction(f'm_mapAbilityProperties.{prop}.m_strValue', a, b, 'ability', **kw)[0]
    assert d('AbilityPostCastDuration', 0.5, 0.2) == 'buff'          # busy for less time after the cast
    assert d('ArmTime', 3, 2) == 'buff'
    assert d('RespawnHealthPercent', 40, 50) == 'buff'               # Soul Rebirth: more health on rebirth
    assert d('BonusBaseWeaponDamageTaken', 50, 40) == 'nerf'         # Alchemical Fire: the enemy takes less
    assert d('NonHeroReductionPercent', 40, 50) == 'nerf'            # weaker against non-heroes
    assert d('m_flShootSpreadPenaltyDecayDelay', 0, 0.3) == 'nerf'
    tier = 'm_vecAbilityUpgrades[2].m_vecPropertyUpgrades{GroundDashReductionPercent}.m_strBonus'
    # a bonus to a debuff stored negative: Sleep Dagger T3 -50 -> -45 is weaker ("dash slows -10%")
    assert semantics.direction(tier, -50, -45, 'ability', negative_base=True)[0] == 'nerf'
    assert semantics.direction(tier, -8, -10, 'item', negative_base=True)[0] == 'buff'
    slow = 'm_vecAbilityUpgrades[0].m_vecPropertyUpgrades{EnemyDashSlowPercent}.m_strBonus'
    assert semantics.direction(slow, -25, -22, 'ability')[0] == 'nerf'     # a weaker enemy slow, base 0
    cd = 'm_vecAbilityUpgrades[0].m_vecPropertyUpgrades{AbilityCooldown}.m_strBonus'
    assert semantics.direction(cd, -20, -18, 'ability')[0] == 'nerf'  # a cooldown bonus keeps its sign rule


def test_small_coefficients_keep_their_digits():
    assert semantics.display_value(0.00035) == '0.00035'
    assert semantics.display_value(0.0003) == '0.0003'
    assert semantics.display_value(1e-05) == '0.00001'
    assert semantics.display_value(1.2345) == '1.23'
    assert semantics.scaling_suffix(['EAddToScale', 'EBaseWeaponDamageIncrease']) == ' (weapon damage scaling)'
    assert semantics.scaling_suffix(['EMultiplyScale', 'ETechPower']) == ' (spirit scaling ×)'


def test_bare_entity_name_line_is_a_heading():
    from pipeline.match import heading
    idx = {'sinclair': ['heroes.vdata:hero_magician'], 'boundless spirit': ['abilities.vdata:upgrade_x']}
    assert heading('Sinclair', idx) == 'Sinclair'
    assert heading('Boundless Spirit:', idx) == 'Boundless Spirit'
    assert heading('Now has +1% Spirit Resist per Boon.', idx) is None
    assert heading('Mo & Krill', idx) is None           # unknown name: not a heading


def test_untracked_topics_never_swallow_numbers():
    from pipeline.match_rules import untracked_topic
    assert untracked_topic('Updated sounds for Wraith Card Trick projectile') == 'sound'
    assert untracked_topic('New slam animation.') == 'visual'
    assert untracked_topic('Pass at making rooftops smoother to navigate') == 'map'
    assert untracked_topic('Inspired by: https://forums.playdeadlock.com/threads/x.1539/') == 'link'
    assert untracked_topic('Abandon Match dialog is now more clear') == 'interface'
    assert untracked_topic('Updated effects revisions') == 'visual'
    # gameplay lines stay unmatched (a matcher gap to fix, not "not in data")
    assert untracked_topic('Side Walkers HP increased from 5,175 to 7,000 on the map') is None
    assert untracked_topic('Burrow is no longer affected by Shoulder Charge') is None
    assert untracked_topic('Knockdown now removes movement effects') is None
    assert untracked_topic('No longer blocked by Veil Walker') is None
    # the section decides for a bare line in "Sound, Music, and VO Changes"
    assert untracked_topic('Added for most heroes.', 'Sound, Music, and VO Changes') == 'sound'
    # engine words are never balance data, numbers or not; 'server' with a number is
    assert untracked_topic('Increased tick rate from 60hz to 64hz') == 'performance'
    assert untracked_topic('Added support for DLSS as an FSR2 alternative') == 'performance'
    assert untracked_topic('Trooper Soul Orbs now have a 90ms buffer to allow the server to catch up') is None
    # zipline / bounce pad / geometry / 'setting' are gameplay words too (review 2026-10-01)
    assert untracked_topic('Damage over time no longer prevents zipline usage') is None
    assert untracked_topic('Reduces your speed rather than setting it to a low cap') is None
    # a hero or ability line is only untracked for its sound or looks
    assert untracked_topic('Bounce Pad now provides allies with air control', has_subject=True) is None
    assert untracked_topic('Leap gets stuck on the map geometry', has_subject=True) is None
    assert untracked_topic('New slam animation.', has_subject=True) == 'visual'
    # a numbered line that merely credits a forum thread is gameplay
    assert untracked_topic('Spirit Snatch: steal 12% Spirit Resist (Thanks to https://forums.x/t/1)') is None


def test_inline_images_are_not_note_lines():
    assert bbcode_lines('[img]{STEAM_CLAN_IMAGE}/45164767/8b22ee.jpg[/img]\n[*] Real line') == ['Real line']


def test_window_op_merge():
    from pipeline.match import merge_ops
    assert merge_ops('add', 'change') == 'add'          # "— → 0.75" was CHANGED
    assert merge_ops('change', 'remove') == 'remove'    # "16.2 → —" was CHANGED
    assert merge_ops('remove', 'add') == 'change'
    assert merge_ops('change', 'change') == 'change'
    assert merge_ops('add', 'remove') == 'change'       # never shipped: old == new == None, dropped


def test_plain_labels_for_unlabelled_structures():
    lab = lambda p: semantics.describe(p, {}, 'x', 'hero')['label']   # noqa: E731
    assert lab('m_mapLevelInfo."22".m_unRequiredGold') == 'Level 22: souls needed'
    assert lab('m_mapLevelInfo."14".m_mapBonusCurrencies.EAbilityPoints') == 'Level 14: ability points'
    assert lab('m_MapModCostBonuses.EItemSlotType_Armor[4].flBonus') == 'Vitality investment, step 5: bonus'
    assert lab('m_mapBoundAbilities.ESlot_Signature_3') == 'Kit: Ability 3'
    assert lab('m_sModifer.m_vecModifierValues{MODIFIER_VALUE_FIRE_RATE}.m_valueMin') == 'Powerup: Fire Rate (early game)'
    assert semantics.humanize('m_projectileInfo') == 'Projectile Info'
    assert semantics.humanize('m_flSightRangeNPCs') == 'Sight Range NPCs'
    assert semantics.humanize('m_iSpawnIntervalInSeconds') == 'Spawn Interval (s)'


def test_update_page_keeps_changes_drops_lore():
    from pipeline import update_page
    text = {'X_Blue_Name': 'Broadway', 'X_Landmark_1_Title': 'Uptown', 'X_Landmark_1_Body': 'Our first stop on the tour.',
            'X_MustDo_Crates_Kicker': 'Smash open', 'X_MustDo_Crates_Title': 'Tough Crates',
            'X_MustDo_Crates_Body': 'Require a <1>Heavy Melee</1> to break.', 'X_Notes_1': '<1>Improved anti-cheat</1>',
            'X_Notes_2': 'And many other misc changes...'}
    rules = {'title': 'T', 'date': '2026-01-01', 'skip': '^And many other', 'sections': [
        {'title': 'Map', 'items': [{'line': 'Lane names — Blue Lane is {X_Blue_Name}'},
                                   {'list': 'Landmarks', 'keys': r'^X_Landmark_\d+_Title$'}]},
        {'title': 'Gameplay', 'items': [{'cards': '^X_MustDo_'}]},
        {'title': 'Additional Update Notes', 'items': [{'verbatim': r'^X_Notes_\d+$'}]}]}
    lines = update_page.to_lines(text, rules)
    assert lines == ['[ Map ]', '- Lane names — Blue Lane is Broadway', '- Landmarks — Uptown',
                     '[ Gameplay ]', '- Tough Crates: Require a Heavy Melee to break.',
                     '[ Additional Update Notes ]', '- Improved anti-cheat']
    assert not any('first stop' in ln for ln in lines)          # lore is never republished


def test_subject_less_lines_find_their_subject_or_stay_untracked():
    """P12/P13 (2026-10-02): a line without "Hero:" took every field of the patch that moved the
    same way ("Base Guardian Health +20%" -> Bebop's regen and two items)."""
    from pipeline import match_rules as rules
    from pipeline.match import _close_hero, annotate_line, inline_names
    # an alias that IS a name the line uses stays an alias (it is not inside a longer name)
    keys = rules.alias_keys('Base Guardian Health increased by 20%', ('base guardian',))
    assert 'npc_units.vdata:npc_barrack_boss' in keys and 'npc_units.vdata:npc_boss_tier1' not in keys
    # synonyms fire on stemmed words: "collision size" is a radius
    assert {'collision', 'size'} <= rules.expand_label_words(words('Bullet Radius'))
    # a family without "all" needs a number: a line about respawn MUSIC claims no respawn field
    mk = lambda eid, path, a, b: MChange('abilities.vdata', eid, path, 'change', a, b, 'balance', 'item', None, 'x', False)
    respawn = [mk('a', 'm_flRespawnTime', 10, 12)]
    assert rules.global_line('Lowered volumes for death sounds and respawn music', respawn, {}, float) is None
    # other families keep their wordy lines ("Vitality investment tree bonus reverted back to % base hp")
    invest = [mk('h', 'm_MapModCostBonuses.EItemSlotType_Armor{16000}.flBonus', 1120, 48)]
    assert rules.global_line('Vitality investment tree bonus reverted back to % base hp', invest, {}, float)
    # an entity named inside the line (not in parentheses) is its subject
    idx = {'medic pack': ['misc.vdata:medic_pack'], 'bebop': ['heroes.vdata:hero_bebop'],
           'vindicta': ['heroes.vdata:hero_hornet']}
    cat = {'misc.vdata:medic_pack': {'id': 'medic_pack', 'kind': 'global'},
           'heroes.vdata:hero_bebop': {'id': 'hero_bebop', 'kind': 'hero'},
           'heroes.vdata:hero_hornet': {'id': 'hero_hornet', 'kind': 'hero'}}
    assert inline_names('Medic Pack ally search radius from 30 to 35', idx, cat) == {'misc.vdata:medic_pack'}
    assert inline_names('Light melee damage reduced by 20% (except for Bebop)', idx, cat) == set()
    # Valve's typo of a hero name still names the hero
    assert _close_hero('Vindcita', idx) == ['heroes.vdata:hero_hornet']
    assert _close_hero('Fixed', idx) is None
    # the numbers of a subject-less line go to the named entity only
    pack = MChange('misc.vdata', 'medic_pack', 'm_flRadius', 'change', 30, 35, 'balance', 'global', None, 'AOE Radius', False)
    other = MChange('abilities.vdata', 'x', 'm_mapAbilityProperties.Radius.m_strValue', 'change', 30, 35, 'balance',
                    'item', None, 'Radius', False)
    by_ent = {'misc.vdata:medic_pack': [pack], 'abilities.vdata:x': [other]}
    res = annotate_line('Medic Pack ally search radius from 30 to 35', [pack, other], by_ent, idx, cat, {})
    assert res['changes'] == [pack.key]
    # a named entity with no change in the window is not the subject ("Fire Rate powerup" vs the item)
    assert inline_names('Medic Pack ally search radius from 30 to 35', idx, cat, {'abilities.vdata:x': [other]}) == set()
    # named inside the line, the numbers still need a word of the field: heal 14% -> 12% is not a range
    rng = MChange('misc.vdata', 'medic_pack', 'm_flMaxRange', 'change', 14, 12, 'balance', 'global', None, 'Max Range', False)
    res = annotate_line('Medic Pack heal reduced from 14% to 12%', [rng], {'misc.vdata:medic_pack': [rng]}, idx, cat, {})
    assert res['status'] != 'documented'
    assert 'health' in words('Walker HP increased by 40%')
    # nor does a line about its sounds describe it
    res = annotate_line('Updated Medic Pack start and end sounds', [rng], {'misc.vdata:medic_pack': [rng]}, idx, cat, {})
    assert res['changes'] == []


def test_cosmetic_files_name_their_heroes():
    """2026-10-02: news of "underwear textures" for Paige and Victor — the files had them since 6711."""
    from pipeline.cosmetics import ASSET_KINDS, hero_codes, subject_of
    heroes = {'hero_bookworm': {'m_strModelName': 'models/heroes_wip/bookworm/bookworm.vmdl'},
              'hero_nano': {'m_strModelName': 'models/heroes_staging/nano/nano_v2/nano.vmdl'},
              'hero_krill': {'m_strModelName': 'models/heroes_staging/digger/digger.vmdl'},
              'hero_priest': {'m_strModelName': 'models/heroes_wip/priest/priest.vmdl'}}
    codes = hero_codes(heroes, {'hero_nano': 'Calico', 'hero_krill': 'Mo & Krill'})
    assert subject_of('bookworm', codes) == 'hero_bookworm'
    assert subject_of('calico', codes) == 'hero_nano' and subject_of('mo_krill', codes) == 'hero_krill'
    assert subject_of('priest_crossbow', codes) == 'hero_priest'           # a variant of the hero's graph
    assert subject_of('ratking', codes) == 'ratking'                      # unknown: kept as is
    kind = lambda p: next((k for k, rx in ASSET_KINDS if rx.match(p)), None)     # noqa: E731
    assert kind('models/heroes_wip/bookworm/materials/bookworm_basebody_color_png_1eb21a27.vtex_c') == 'base body'
    assert kind('animgraphs/animgraph2/hero/hero_cosmetic.vnmgraph+abrams.vnmgraph_c') == 'cosmetic animation'
    assert kind('models/heroes_wip/bookworm/materials/bookworm_head.vmat_c') is None


def test_a_line_listing_properties_links_each_of_them():
    """P13: "Neutral respawn times, hp, and bounty reduced by 30%" linked the bounty only."""
    from pipeline.match import list_hits, list_parts
    mk = lambda eid, path, a, b, label: MChange('npc_units.vdata', eid, path, 'change', a, b, 'balance', 'neutral',  # noqa: E731
                                                None, label, False)
    spawn = mk('camp', 'm_flSpawnInterval', 420, 290, 'Spawn Interval (s)')
    hp = mk('n', 'm_nMaxHealth', 500, 350, 'Health')
    bounty = mk('n', 'm_flGoldReward', 100, 70, 'Soul Bounty')
    regen = mk('n', 'm_flOOCRegen', 10, 7, 'Out-of-combat Regen')         # moved by 30% too, but not listed
    head = 'Neutral respawn times, hp, and bounty '
    assert len(list_parts(head)) == 3 and list_parts('Walker HP ') == []
    got = list_hits(head, [spawn, hp, bounty, regen], 30, head + 'reduced by 30%', set())
    assert sorted(c.label for c in got) == ['Health', 'Soul Bounty', 'Spawn Interval (s)']
    dmg = MChange('abilities.vdata', 'siphon', 'm_mapAbilityProperties.DPS.m_strValue', 'change', 40, 36, 'balance',
                  'ability', 'hero_atlas', 'Damage Per Second', False)
    sc = MChange('abilities.vdata', 'siphon', 'm_mapAbilityProperties.DPS.m_subclassScaleFunction.m_flStatScale',
                 'change', 0.5, 0.45, 'balance', 'ability', 'hero_atlas', 'Damage Per Second (spirit scaling)', False)
    got = list_hits('Siphon Life damage and spirit scaling ', [dmg, sc], 10, 'reduced by 10%', set())
    assert len(got) == 2 and dmg in got and sc in got


def test_light_melee_line_covers_every_hero():
    """Hero audit #11: "Light melee base damage reduced by 20% (except for …)" took Parry's damage taken."""
    from pipeline.match import num
    from pipeline.match_rules import global_delta_line
    mk = lambda eid, path, a, b: MChange('heroes.vdata', eid, path, 'change', a, b, 'balance', 'hero', None, 'x',  # noqa: E731
                                         False, chain=[a, b])
    cat = {f'heroes.vdata:h{i}': {'kind': 'hero'} for i in range(5)}
    light = [mk(f'h{i}', 'm_mapStartingStats.ELightMeleeDamage', 63, 50) for i in range(4)]
    heavy = [mk('h4', 'm_mapStartingStats.EHeavyMeleeDamage', 116, 93)]
    hit = global_delta_line('Light melee base damage reduced by 20% (except for Viscous, Calico and Bebop)',
                            light + heavy, cat, num)
    assert sorted(c.eid for c in hit) == ['h0', 'h1', 'h2', 'h3']


def test_each_number_pair_gets_its_best_field():
    """P13: "Base HP increased from 6725 to 12500 and growth reduced from 470 to 200" is two fields."""
    from pipeline.match import label_words, pair_hits
    mk = lambda path, a, b, label: MChange('npc_units.vdata', 'mid', path, 'change', a, b, 'balance', 'neutral',  # noqa: E731
                                           None, label, False)
    start = mk('m_iStartingHealth', 6725, 12500, 'Starting Health')
    grow = mk('m_iHealthGainPerMinute', 470, 200, 'Health per Minute')
    other = mk('m_flX', 470, 200, 'Something Else')
    got = pair_hits([(12, grow), (11, start), (7, other)], [(6725, 12500), (470, 200)], 9)
    assert grow in got and start in got and other not in got
    # growth is a phrase of the label, not the word "boon"
    assert 'growth' in label_words(grow)
    assert 'growth' not in label_words(mk('m_mapLevelInfo.21.m_bUseStandardUpgrade', 0, 1, 'Level 21: gives a boon'))


def test_now_grants_and_no_longer_grants_are_values():
    """769 numeric lines were unmatched; the largest group: an item stat that appeared or went away."""
    from pipeline.match import granted_pair
    assert granted_pair('Superior Stamina: Now grants +75 Health') == [(0.0, 75.0)]
    assert granted_pair('Withering Whip: No longer grants +50 Health') == [(50.0, 0.0)]
    assert granted_pair('Now has 3 charges and 10s cooldown') == []          # two numbers: not one value
    assert granted_pair('Reduced spread') == []
    # a tier name or an aside is no second number; "now reduces X by N" / "now lasts N" / "is now N" too
    assert granted_pair('Exploding Uppercut T3 no longer grants +100% Ammo') == [(100.0, 0.0)]
    assert granted_pair('Rapid Recharge: Now gains +12% Weapon Damage (T1 Extra Charge gives +6%)') == [(0.0, 12.0)]
    assert granted_pair('Crow Familiar now reduces bullet armor by 6%') == [(0.0, 6.0)]
    assert granted_pair('Barriers now last for 16s') == [(0.0, 16.0)]
    assert granted_pair('Alchemical Flask T2 is now +50 Damage') == [(0.0, 50.0)]
    assert granted_pair('Luggage Cart is now 20% larger (20% wider hitbox as well)') == []     # a change, not a value
    from pipeline.match import _same_kind
    shield = lambda label: MChange('abilities.vdata', 'v', 'p', 'add', None, 185, 'balance', 'item', None, label, False)  # noqa: E731
    lw = words('Veil Walker: Now gives +185 Spirit Shield Health')
    assert _same_kind(shield('Spirit Shield Health'), lw) and not _same_kind(shield('Bullet Shield Health'), lw)
    # "Now has a 8s cooldown" while it was 3s: the stated new value counts; the invented 0 does not
    cd = MChange('abilities.vdata', 'x', 'm_mapAbilityProperties.AbilityCooldown.m_strValue', 'change', 3, 8, 'balance',
                 'item', None, 'Cooldown', False)
    pairs = granted_pair('Now has a 8s cooldown')
    assert score(cd, 'Now has a 8s cooldown', pairs, None, {'cooldown'}, None, set(), granted=True) >= 9
    assert score(cd, 'Now has a 8s cooldown', pairs, None, {'cooldown'}, None, set()) < 9


def test_spawn_timers_say_minutes_without_the_word():
    """"Vaults spawn time/interval changed from 10/5 to 8/4" is 600/300 -> 480/240 seconds in the files."""
    from pipeline import match_rules as rules
    from pipeline.match import annotate_line
    camp = MChange('misc.vdata', 'neutral_camp_vaults', 'm_flSpawnInterval', 'change', 300, 240, 'balance', 'global',
                   None, 'Spawn Interval (s)', False)
    by_ent = {'misc.vdata:neutral_camp_vaults': [camp]}
    res = annotate_line('Vaults spawn time/interval changed from 10/5 to 8/4', [camp], by_ent, {}, {}, {})
    assert res['status'] == 'documented'
    assert 'misc.vdata:neutral_camp_vaults' in rules.alias_keys('Vaults spawn time')
    assert semantics.context_label('m_sModifer.flCooldownOnBreak') == 'Effect › Cooldown On Break'


def test_a_map_key_that_is_an_id_reads_as_words():
    """2026-10-03: 30 Walker rows read 'Intrinsic Modifiers npc_boss_intrinsic › Bullet Armor Damage Resist'."""
    from pipeline import semantics
    label = semantics.context_label('m_sModifer.m_mapThings{npc_boss_intrinsic}.m_flSize')
    assert 'npc_' not in label and 'boss intrinsic' in label
    assert semantics._key_text('EModTier_1') == 'EModTier_1' and semantics._key_text('Value') == 'Value'


def test_labels_use_the_games_words():
    """Advisor round 4 (2026-10-03): labels split from field names said "Tech Armor Damage Resist" (63
    rows) and "Intrinsic Modifiers boss intrinsic › …" — the game says Spirit / Bullet Resist, and a
    unit's intrinsic modifier is its passive."""
    from pipeline import semantics
    assert semantics.humanize('TechArmorDamageReduction') == 'Spirit Resist'
    assert semantics.humanize('MODIFIER_VALUE_TECH_ARMOR_DAMAGE_RESIST_REDUCTION'.title().replace('_', '')) \
        == 'Modifier Value Spirit Resist Reduction'
    assert semantics.humanize('TechPowerPerKill') == 'Spirit Power Per Kill'
    assert semantics.humanize('m_flTechnicalDelay') == 'Technical Delay'       # a word, not a prefix
    path = 'm_vecIntrinsicModifiers{npc_boss_intrinsic}.m_vecScriptValues{MODIFIER_VALUE_BULLET_ARMOR_DAMAGE_RESIST}.m_value'
    assert semantics.context_label(path) == 'Passive › Bullet Resist'
    assert semantics.context_label('m_mapItemSlotInfo.EItemSlotType_Tech.m_arMaxPurchasesForTier').startswith(
        'Item Slot Info › Spirit')


def test_labels_read_without_engine_words():
    """Review 2026-10-05: 1,533 rows on 102 pages read engine words — boss tiers, "Phase01", "Pct", an aura's
    container, CamelCase keys, "Ao E"."""
    from pipeline import semantics
    assert semantics.describe('m_flT1BossDPSMaxResist', {})['label'] == 'Damage Resist at most vs Guardian'
    assert semantics.describe('m_flT2BossDamageResistPct', {})['unit'] == '%'
    assert semantics.describe('m_flAttackT3BossPhase2MaxRange', {})['label'] == 'Max Range vs Patron Phase 2'
    assert semantics.describe('m_flBarrackBossDPS', {})['label'] == 'DPS vs Base Guardian'
    assert semantics.humanize('m_flAttackTimePhase01') == 'Attack Time Phase 1'
    assert semantics.humanize('m_flPounceToTargetDist') == 'Pounce To Target Distance'
    assert semantics.context_label('m_AoEModifier.m_flWaveHeight') == 'AoE Modifier › Wave Height'
    assert semantics.context_label('m_IceDomeModifier.m_EnemyAuraModifier.m_modifierProvidedByAura.m_nEnabledStateMask') \
        == 'Enemy Aura › Applies'
    assert semantics.context_label('m_modifierProvidedByAura.m_flModifierProvidedByAuraDuration').startswith('Lingers')
    assert semantics.context_label('fl_MaxExtraGravityScale') == 'Max Extra Gravity Scale'
    assert semantics.context_label('ECritDamageBonusScale') == 'Crit Damage Bonus Scale'
    d = semantics.describe('m_mapAbilityProperties.NonHeroHealPct.m_strValue', {})
    assert (d['label'], d['unit']) == ('Non Hero Heal', '%')
    assert semantics.describe('m_mapAbilityProperties.DamageGrowthPctPerMin.m_strValue', {})['label'] \
        == 'Damage Growth % Per Min'
    # a coefficient is no percent, a fraction field is shown ×100
    assert not semantics.describe('m_vecAbilityUpgrades[2].m_vecPropertyUpgrades{DealMaxHealthDamagePct|EAddToScale}'
                                  '.m_strBonus', {}, kind='ability').get('unit')
    d = semantics.describe('m_mapAbilityProperties.FourthHitDamagePercentage.m_strValue', {})
    assert d['meters'] == semantics.FRACTION and semantics.show('0.26', d['meters'], d.get('unit', '')) == '26%'
    # a modifier's resist value is a percent (Walker's passive)
    path = 'm_vecIntrinsicModifiers{npc_boss_intrinsic}.m_vecScriptValues{MODIFIER_VALUE_BULLET_ARMOR_DAMAGE_RESIST}.m_value'
    assert semantics.describe(path, {})['unit'] == '%'
    assert not semantics.describe(path.replace('_RESIST}', '_RESIST_REDUCTION_PER_HERO}'), {}).get('unit')


def test_a_bare_channel_move_speed_is_engine_units_whatever_the_other_side():
    """Review 2026-10-05: "Channel Move Speed 50 → no limit" sat next to "1.27m/s → 1.3m/s" in one band (24 rows):
    Valve wrote it in units until 2025-08-18, so a bare side is units even when the other is no number."""
    from pipeline import semantics
    path = 'm_mapAbilityProperties.ChannelMoveSpeed.m_strValue'
    assert semantics.units_when_bare(path, '50', '-1') == ('1.27m', '-1')
    assert semantics.units_when_bare(path, '1.3m', '2m') == ('1.3m', '2m')
    assert semantics.units_when_bare('m_mapAbilityProperties.Radius.m_strValue', '50', '-1') == ('50', '-1')


def test_a_units_tag_and_percent_go_the_same_way():
    """Review 2026-10-05: "T1 Boss DPS Max Resist -35 → -50 DOWN +42.9%" — UP / DOWN say where the number went,
    the percent with its sign; a helper unit (the Hideout's Sinner's Sacrifice) reads UP / DOWN like its family."""
    import pytest
    from pipeline import semantics
    assert semantics.direction('m_flT1BossDPSMaxResist', -35, -50, 'trooper') == ('down', pytest.approx(-42.857, 0.01))
    assert semantics.direction('m_flBulletSpeed', 457.2, 152.4, 'helper')[0] == 'down'


def test_times_carry_seconds_and_metre_speeds_read_per_second():
    """Advisor round 4: Fire Interval / Reload Time / Bullet Lifetime had no unit (1,867 rows), and
    "Channel Move Speed 20m" read as a length. A T1-T3 bonus keeps its own unit."""
    from pipeline import semantics
    assert semantics.describe('m_mapWeaponInfos.primary.m_flCycleTime', {})['unit'] == 's'
    assert semantics.describe('m_mapWeaponInfos.primary.m_reloadDuration', {})['unit'] == 's'
    assert semantics.describe('m_flStunDuration', {})['unit'] == 's'
    assert semantics.describe('m_mapAbilityProperties.AbilityPostCastDuration.m_strValue', {})['unit'] == 's'
    # a plain T1-T3 bonus to a time no tooltip gives a unit is seconds like the time (review 2026-10-05: Doorman's
    # "T3: Late Checkout Cooldown 13 → 15" is the notes' 10s → 13s); a scaling coefficient is not
    assert semantics.describe('m_vecAbilityUpgrades[2].m_vecPropertyUpgrades{AbilityCooldown}.m_strBonus',
                              {}, kind='ability').get('unit') == 's'
    assert not semantics.describe('m_vecAbilityUpgrades[2].m_vecPropertyUpgrades{AbilityDuration|EAddToScale}.m_strBonus',
                                  {}, kind='ability').get('unit')
    assert semantics.describe('m_flCooldownOnHit', {})['unit'] == 's'
    assert semantics.describe('m_flTimeToGiveUp', {})['unit'] == 's'
    assert not semantics.describe('m_flCastDelayMaxDist', {}).get('unit') == 's'
    assert not semantics.describe('m_flGrowthStartTimeInMinutes', {}).get('unit') == 's'
    assert not semantics.describe('m_mapWeaponInfos.primary.m_flBulletDamage', {}).get('unit')
    d = semantics.describe('m_mapAbilityProperties.ChannelMoveSpeed.m_strValue', {})
    assert d['speed_m'] and d['meters'] is False             # the matcher's transforms stay as they were
    assert semantics.show('20m', semantics.M_SPEED) == '20m/s'
    assert semantics.show('50', semantics.M_SPEED) == '50'
    assert semantics.show(-1, semantics.M_SPEED) == '-1'


def test_boon_rescale_is_nobodys_mistake():
    """2024-09-26 "Boon count increased from 11 to 14" + "Non-Health boon bonuses rescaled …": the hero
    lines quote growth in the old scale (Kelvin 1.2 -> 0.9 is 1.2 -> 0.707 in the files) — a "mismatch"
    was ours, not Valve's. 2025-06-17: 20 -> 32 stat levels (Wraith -18% is 0.351 -> 0.18)."""
    from pipeline import match_rules as rules
    from pipeline.match import num, pct_close
    notes = ' '.join(['Boon count increased from 11 to 14 (added to 16/18/20k).',
                      'Non-Health boon bonuses rescaled over the 14 levels'])
    f, no_health = rules.boon_rescale(notes)
    assert abs(f - 11 / 14) < 1e-9 and no_health
    assert rules.boon_rescale('total stat levels increased from 20 to 32 (but rescaled in value)') == (0.625, False)
    assert rules.boon_rescale('Boon distribution') is None
    path = 'm_mapStandardLevelUpUpgrades.MODIFIER_VALUE_BASE_BULLET_DAMAGE_FROM_LEVEL'
    kelvin = MChange('heroes.vdata', 'hero_kelvin', path, 'change', 1.2, 0.707, 'balance', 'hero', None,
                     'Bullet damage per boon', False, scale=f)
    assert score(kelvin, 'Bullet damage growth reduced from 1.2 to 0.9', [(1.2, 0.9)], None,
                 {'bullet', 'growth'}, None, set()) >= 10
    wraith = MChange('heroes.vdata', 'hero_wraith', path, 'change', 0.351, 0.18, 'balance', 'hero', None,
                     'Bullet damage per boon', False, scale=0.625)
    assert pct_close(wraith, 18, -1)
    # the patch-wide lines link the boon levels and the plainly rescaled values
    lvl = MChange('heroes.vdata', 'hero_kelvin', 'm_mapLevelInfo.16.m_bUseStandardUpgrade', 'change', False, True,
                  'mechanic', 'hero', None, 'Level 16: gives a boon', False)
    other = MChange('heroes.vdata', 'hero_haze', path, 'change', 0.7, 0.55, 'balance', 'hero', None, 'x', False, scale=f)
    assert rules.boon_lines('Boon count increased from 11 to 14', [lvl, other], (f, True), num) == [lvl]
    assert rules.boon_lines('Non-Health boon bonuses rescaled over the 14 levels', [lvl, other], (f, True), num) == [other]


def test_a_mismatch_needs_a_word_of_the_property_itself():
    """2025-07-04 "Guardian base resistance increased from 40% to 60% (decays 10 minutes…)" was a
    "mismatch" with Tier2 Gold Kill 4500 -> 3500: "guardian" brings "tier", minutes x60 made 3600."""
    from pipeline.match import annotate_line
    gold = MChange('generic_data.vdata', 'm_ObjectiveParams', 'm_iTier2GoldKill', 'change', 4500, 3500, 'balance',
                   'global', None, 'Tier2 Gold Kill', False)
    keys = {'generic_data.vdata:m_ObjectiveParams'}
    res = annotate_line('Guardian base resistance increased from 40% to 60% (decays 10 minutes still)', [gold],
                        {k: [gold] for k in keys}, {}, {}, {})
    assert res['status'] != 'mismatch'
    from pipeline.match import names_whole_property
    mk = lambda label: MChange('abilities.vdata', 'x', 'p', 'change', 4, 2, 'balance', 'ability', None, label, False)  # noqa: E731
    assert not names_whole_property(mk('T3: Charge Delay'), words('Time Wall T3 increased from +1 Charge to +2'))
    assert names_whole_property(mk('Cast Delay'), words('Echo Shard: Cast delay reduced from 0.3s to 0.25s'))
    assert names_whole_property(mk('Bullet Damage'), words('Calico: Bullet Damage increased from 2 to 2.2'))
    from pipeline.match import _tokens, mismatch_field
    urn = 'Time Urn will Autorun back to Home regardless of nearby players reduced from 75s to 45s'
    assert not mismatch_field(mk('Time To Damage'), words(urn), set(), _tokens(urn))
    haze = 'Bullet Dance Bonus Bullet Damage reduced from 10 to 7'
    assert mismatch_field(mk('Bullet Damage'), words(haze), set(), _tokens(haze))
    assert parse_pairs('Golden Statues level 2 drops now happen at 15 minutes instead of 20') == [(20.0, 15.0)]
    assert parse_pairs('Active now grants +20% Fire Rate instead of Bullet Lifesteal') == []
    assert {'move', 'speed'} <= words('Movespeed scaling with Spirit Power reduced from 0.028 to 0.02')
    # "Now gains 1% Bullet Resist per Boon (0->14%)": 0 -> 1, the parenthesis is the total
    resist = MChange('heroes.vdata', 'hero_dynamo', 'm_mapStandardLevelUpUpgrades.MODIFIER_VALUE_BULLET_ARMOR', 'change',
                     0, 1, 'balance', 'hero', None, 'Bullet resist per boon', False)
    keys = {'heroes.vdata:hero_dynamo'}
    from pipeline.match import Subject  # noqa: F401
    idx = {'dynamo': ['heroes.vdata:hero_dynamo']}
    cat = {'heroes.vdata:hero_dynamo': {'id': 'hero_dynamo', 'kind': 'hero'}}
    res = annotate_line('Dynamo: Now gains 1% Bullet Resist per Boon (0->14%)', [resist], {k: [resist] for k in keys},
                        idx, cat, {})
    assert res['status'] == 'documented'


def test_wordy_lines_link_flags_resist_swaps_components_and_removals():
    """2026-10-03: textual lines whose subject changed but no word matched a label."""
    from pipeline.match import annotate_line, flag_words
    beh = MChange('abilities.vdata', 'decay', 'm_AbilityBehaviorsBits', 'change', 'CITADEL_ABILITY_BEHAVIOR_A',
                  'CITADEL_ABILITY_BEHAVIOR_A | CITADEL_ABILITY_BEHAVIOR_DONT_INTERRUPT_SLIDE_ON_CAST', 'mechanic', 'item',
                  None, 'Behaviour', False)
    assert {'interrupt', 'slide'} <= flag_words(beh)
    idx = {'decay': ['abilities.vdata:decay'], 'fury trance': ['abilities.vdata:fury'],
           'headhunter': ['abilities.vdata:hh'], 'soul rebirth': ['abilities.vdata:sr']}
    cat = {k: {'id': k.split(':')[1], 'kind': 'item'} for ks in idx.values() for k in ks}

    def run(text, changes):
        by_ent = {}
        for c in changes:
            by_ent.setdefault(f'{c.file}:{c.eid}', []).append(c)
        return annotate_line(text, changes, by_ent, idx, cat, {})

    assert run('Decay: No longer interrupts sliding, to match other similar actives', [beh])['changes'] == [beh.key]
    # review 2026-10-05: a state's -ing word is the line's verb ("slide" = SLIDING_DISABLED, Bullet Dance 2026-04-30)
    state = MChange('abilities.vdata', 'decay', 'm_mapModifiers.x.m_nEnabledStateMask', 'change',
                    'MODIFIER_STATE_SLIDING_DISABLED | MODIFIER_STATE_X', 'MODIFIER_STATE_X', 'mechanic', 'item', None,
                    'Applies', False)
    assert 'slide' in flag_words(state)
    assert run('Decay: Restored being able to slide while using it', [state])['changes'] == [state.key]
    mk = lambda eid, path, a, b, label, cat_='balance': MChange('abilities.vdata', eid, path, 'change', a, b, cat_,  # noqa: E731
                                                                 'item', None, label, False)
    bul, spi = mk('fury', 'p.BulletResist', '40', None, 'Bullet Resist'), mk('fury', 'p.SpiritResist', None, '40', 'Spirit Resist')
    assert len(run('Fury Trance: Active Bullet Resistance changed to Spirit Resistance', [bul, spi])['changes']) == 2
    comp = mk('hh', 'm_vecComponentItems', 'upgrade_a', 'upgrade_b', 'Component Items', 'mechanic')
    assert run('Headhunter: Now requires Headshot Booster', [comp])['changes'] == [comp.key]
    off = mk('sr', 'm_bDisabled', False, True, 'Disabled', 'availability')
    assert run('Soul Rebirth: Removed from the game', [off])['changes'] == [off.key]


def test_a_line_about_unmoved_files_is_in_the_code():
    """2026-10-03: "Vyper: Sliding uphill now allows for lateral movement" — nothing of Vyper's files moved:
    the change is in the game's code ('code'), not a matcher miss — unless the files move a little later."""
    from types import SimpleNamespace
    from pipeline.match import code_lines
    ln = {'text': 'Vyper: Sliding uphill now allows for lateral movement', 'subject': 'Vyper', 'status': 'unmatched',
          'changes': [], '_quiet': ['heroes.vdata:hero_viper']}
    own = (SimpleNamespace(id='a', date='2026-04-10', title='A'),
           {'sections': [{'lines': [ln]}], 'entities': [], 'line_counts': {'unmatched': 1}})
    moved = {'file': 'heroes.vdata', 'id': 'hero_viper', 'changes': [{'cat': 'balance'}]}
    later = (SimpleNamespace(id='b', date='2026-04-12', title='B'), {'sections': [], 'entities': [moved]})
    assert code_lines([own, later]) == 0 and ln['status'] == 'unmatched' and '_quiet' not in ln
    ln['_quiet'] = ['heroes.vdata:hero_viper']
    assert code_lines([own]) == 1 and ln['status'] == 'code' and own[1]['line_counts'] == {'unmatched': 0, 'code': 1}


def test_a_quiet_line_about_sounds_or_looks_is_untracked_and_numbers_stay_unmatched():
    """Review of the first 'code' round: "Revision to buff and cast to look less modern" is a look, not code;
    "Fire Rate: +1.5% to +2%" left unmatched is our miss more likely than code."""
    from types import SimpleNamespace
    from pipeline.match import code_lines

    def one(text):
        ln = {'text': text, 'status': 'unmatched', 'changes': [], '_quiet': ['abilities.vdata:x']}
        data = {'sections': [{'lines': [ln]}], 'entities': [], 'line_counts': {'unmatched': 1}}
        code_lines([(SimpleNamespace(id='a', date='2026-04-10', title='A'), data)])
        return ln, data['line_counts']

    ln, lc = one('Petrifying Bola: Added cast and buff sounds')
    assert ln['status'] == 'untracked' and ln['topic'] == 'sound' and lc == {'unmatched': 0, 'untracked': 1}
    ln, _ = one('Petrifying Bola: Revision to buff and cast to look less modern')
    assert ln['status'] == 'untracked' and ln['topic'] == 'visual'
    ln, _ = one('Fire Rate: +1.5% to +2%')
    assert ln['status'] == 'unmatched' and '_quiet' not in ln
    ln, _ = one('Shiv: T3 now also slows')           # a tier name is not a number
    assert ln['status'] == 'code'


def test_builds_into_links_the_other_items_component_list():
    """"Berserker: Now builds into Frenzy": Berserker's files did not move, Frenzy's ComponentItems did."""
    from pipeline.match import annotate_line, MChange
    berserker = 'abilities.vdata:upgrade_berserker'
    frenzy = 'abilities.vdata:upgrade_frenzy'
    cat = {berserker: {'id': 'upgrade_berserker', 'kind': 'item'}, frenzy: {'id': 'upgrade_frenzy', 'kind': 'item'}}
    idx = {'berserker': [berserker], 'frenzy': [frenzy]}
    comp = MChange('abilities.vdata', 'upgrade_frenzy', 'm_vecComponentItems', 'change', ['a'],
                   ['a', 'upgrade_berserker'], 'balance', 'item', None, 'Components', False)
    by_ent = {frenzy: [comp]}
    out = annotate_line('Berserker: Now builds into Frenzy', [comp], by_ent, idx, cat, {})
    assert out['status'] == 'described' and out['changes'] == [comp.key]


def test_a_corrupted_bonus_reads_like_a_tier_bonus():
    """Review 2026-10-05: Blood Tribute 'Move Speed +2m' (a speed), Arctic Blast's slow 'Move Speed +30%' (the game
    prints '-30%': an enemy slow), a property named by its tooltip token."""
    p = 'm_CorruptedItemInfo.m_Upgrade.m_vecPropertyUpgrades{%s}.m_strBonus'
    tok = {'slowpercent_label': 'Move Speed', 'slowpercent_prefix': '-', 'slowpercent_postfix': '%',
           'bonusmovespeed_label': 'Move Speed', 'bonusmovespeed_postfix': 'm'}
    d = semantics.describe(p % 'BonusMoveSpeed', tok, 'upgrade_blood_tribute', 'item')
    assert d['speed_m'] and d['unit'] == 'm'
    d = semantics.describe(p % 'SlowPercent', tok, 'upgrade_arctic_blast', 'item')
    assert d['sign'] == '-' and d['label'] == 'Corrupted: Move Speed'
    assert semantics.enemy_label(d['label'], 'SlowPercent') == 'Corrupted: Movement Slow'


def _event(file, eid, name, kind, path='@add'):
    return {'file': file, 'id': eid, 'name': name, 'kind': kind,
            'change': {'key': f'{file}:{eid}:{path}', 'path': path, 'status': 'hidden'}}


def test_a_line_naming_what_came_describes_the_event():
    """City Never Sleeps: "Haunts (new neutral camps): Specimen, Gutter Ghouls, Barrel Mimics, …, Shrooms" names
    the camps by their plural without the tier; "Tough Crates: …" and the map line "Bell Tower: …" name entries
    the files give no name. The Overseer is in no line and stays hidden (review 2026-10-05)."""
    from pipeline.match import name_events
    haunts = {'text': 'Haunts (new neutral camps) — Specimen, Gutter Ghouls, Barrel Mimics, Past Dues, Shrooms',
              'status': 'described', 'changes': ['x']}
    crates = {'text': 'Tough Crates: These Tough Crates require a Heavy Melee to break open', 'status': 'unmatched',
              'changes': []}
    bell = {'text': 'Bell Tower: Ascend to the top of the Chinatown Bell Tower for a soul hotspot.',
            'status': 'untracked', 'topic': 'map', 'changes': []}
    sections = [{'title': 'Map', 'lines': [haunts, crates, bell]}]
    evs = [_event('npc_units.vdata', 'neutral_barrel_01_weak', 'Barrel Mimic II', 'neutral'),
           _event('npc_units.vdata', 'neutral_shroom_weak', 'Slum Shroom I', 'neutral'),
           _event('npc_units.vdata', 'neutral_overseer_weak', 'Overseer I', 'neutral'),
           _event('misc.vdata', 'citadel_breakable_prop_tough_crate', 'citadel_breakable_prop_tough_crate', 'global'),
           _event('misc.vdata', 'citadel_breakable_bell_chinatown', 'citadel_breakable_bell_chinatown', 'global')]
    assert name_events(sections, evs) == 4
    assert [e['change']['status'] for e in evs] == ['described', 'described', 'hidden', 'described', 'described']
    assert crates['status'] == 'described' and crates['changes'] == ['misc.vdata:citadel_breakable_prop_tough_crate:@add']
    assert bell['status'] == 'described' and 'topic' not in bell
    assert 'npc_units.vdata:neutral_barrel_01_weak:@add' in haunts['changes']


def test_a_name_inside_another_word_is_no_event_line():
    from pipeline.match_rules import event_phrases, names_event
    # "Tesla Bullets" does not name "Cat Bullet"; "shields" does not name "Mud Shield"
    assert not names_event('Added sound for Tesla Bullets proc', event_phrases('a:cat_bullet', 'Cat Bullet'))
    assert not names_event('Shields have been reworked', event_phrases('a:mud', 'Mud Shield'))
    assert names_event('Stage Hands, Crabbage Pots', event_phrases('n:x', 'Crabbage Pot III'))


def test_blanket_lines_cover_only_their_scope():
    """'All hero stats rebalanced alongside the shop rework' covers the heroes' base stats and growth, never their
    other fields; 'Full shop rework, including many new items' covers the items that came or went, never the
    numbers of the items that stayed (audit TRUE_HIDDEN: Extra Health 160 -> 175)."""
    from pipeline.match import blanket_lines
    blankets = [
        {'patch': 'p', 'line': 'All hero stats rebalanced',
         'match': [{'file': 'heroes.vdata', 'path': '^m_mapStartingStats[.]', 'ops': ['change']}]},
        {'patch': 'p', 'line': 'Full shop rework', 'match': [{'file': 'abilities.vdata', 'path': '^@(add|remove)$',
                                                              'kinds': ['item']}]},
        {'patch': 'other', 'line': 'Full shop rework', 'match': [{'path': '.'}]},
    ]
    stat = MChange('heroes.vdata', 'hero_atlas', 'm_mapStartingStats.EMaxHealth', 'change', 570, 720, 'balance',
                   'hero', None, 'Max Health', False)
    sound = MChange('heroes.vdata', 'hero_atlas', 'm_flStepSoundTime', 'change', 1, 2, 'balance', 'hero', None, 'x', False)
    item = MChange('abilities.vdata', 'upgrade_extra_health', 'm_mapAbilityProperties.BonusHealth.m_strValue', 'change',
                   160, 175, 'balance', 'item', None, 'Bonus Health', False)
    lines = [{'text': 'All hero stats rebalanced alongside the shop rework.', 'status': 'unmatched', 'changes': []},
             {'text': 'Full shop rework, including many new items.', 'status': 'unmatched', 'changes': []}]
    evs = [_event('abilities.vdata', 'upgrade_arctic_blast', 'Arctic Blast', 'item'),
           _event('abilities.vdata', 'citadel_ability_x', 'X', 'ability')]
    n = blanket_lines('p', [{'title': 'Misc', 'lines': lines}], [stat, sound, item], evs, {}, blankets)
    assert n == 2
    assert (stat.status, sound.status, item.status) == ('described', 'hidden', 'hidden')
    assert [e['change']['status'] for e in evs] == ['described', 'hidden']
    assert lines[0]['status'] == lines[1]['status'] == 'described'
    assert lines[0]['changes'] == [stat.key] and stat.lines == [lines[0]['text']]


def test_the_blanket_file_is_valid():
    """Every entry names a patch, a line, why, and scopes that compile (data/overrides/blanket_lines.json)."""
    import re
    from pipeline.match import load_blankets
    assert load_blankets()
    for b in load_blankets():
        assert b['patch'] and b['line'] and b['why'] and b['match']
        for sc in b['match']:
            assert set(sc) <= {'file', 'path', 'ops', 'kinds', 'id'}, sc
            for k in ('path', 'id'):
                if k in sc:
                    re.compile(sc[k])
