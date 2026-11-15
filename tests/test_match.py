"""The matcher (pipeline/match.py): a patch-note line against the data changes of its window."""
from pipeline import semantics
from pipeline.match import MChange, parse_pairs, score, value_matches, words


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
    from pipeline.match import num
    from pipeline.match_rules import global_line
    mk = lambda eid, path, a, b: MChange('abilities.vdata', eid, path, 'change', a, b, 'balance', 'item', None, 'x', False)
    slows = [mk('a', 'm_mapAbilityProperties.SlowPercent.m_strValue', 25, 20),
             mk('b', 'm_mapAbilityProperties.SlowPercent.m_strValue', 99, 66),
             mk('c', 'm_mapAbilityProperties.GroundDashReductionPercent.m_strValue', -20, -18)]
    covered = global_line('All move slow values reduced by ~20% globally', slows, {}, num)
    # 25 -> 20 is the announced ~20%; 99 -> 66 (-33%) is NOT what the line says: it stays hidden
    assert [c.eid for c in covered] == ['a']
    assert len(global_line('All ground dash slows reduced by ~10% globally', slows, {}, num)) == 1


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
    from pipeline.match import num
    from pipeline.match_rules import global_line
    cat = {'abilities.vdata:ult': {'kind': 'ability', 'ability_slot': 'Signature_4'},
           'abilities.vdata:q': {'kind': 'ability', 'ability_slot': 'Signature_1'}}
    mk = lambda eid, a, b: MChange('abilities.vdata', eid, 'm_mapAbilityProperties.AbilityCooldown.m_strValue',
                                   'change', a, b, 'balance', 'ability', None, 'Cooldown', False)
    covered = global_line("All ultimate abilities' cooldowns increased by 15%", [mk('ult', 150, 170), mk('q', 20, 23)],
                          cat, num)
    assert [c.key for c in covered] == ['abilities.vdata:ult:m_mapAbilityProperties.AbilityCooldown.m_strValue']


def test_unit_named_inside_a_line_without_colon():
    from pipeline.match_rules import alias_keys
    assert 'npc_units.vdata:npc_boss_tier2' in alias_keys('Walker bounty increased by 5%')


def test_feature_fields_cluster():
    from pipeline.match_rules import cluster_root
    assert cluster_root('m_flParryCancelAirGlideDuration') == cluster_root('m_flParryCancelAirGravityScale')
    assert cluster_root('m_mapWeaponInfos.primary.m_iBullets') == 'm_mapWeaponInfos'


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


def test_parse_pairs_thousands_separator():
    assert parse_pairs('Side Walkers HP increased from 5,175 to 7,000.') == [(5175.0, 7000.0)]
    assert parse_pairs('Patron health from 12,000 to 13,500') == [(12000.0, 13500.0)]
    # an unspaced per-tier list is not a thousands number
    assert parse_pairs('Bounty from 160,180,200 to 170,190,210') != [(160180200.0, 170190210.0)]


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
    # data audit 2026-11-13: a "changed from A to B" swap gives no old value, quoted or not
    souls = MChange('f', 'ability_nano_dash', 'p', 'add', None, 300, 'balance', '', None, 'Souls', False, [1], False)
    _old_from_notes(souls, [(40.0, 300.0)], 'Calico: Leaping Slash T2 changed from +40 damage to +300 souls on hero kill')
    assert souls.op == 'add' and souls.old is None
    # a length on the line is never the old value of a field without metres (Air Drop: "bomb radius 14m to 20m")
    dmg = MChange('f', 'air', 'p', 'add', None, 20, 'balance', '', None, 'Outgoing Damage', False, [1], False)
    _old_from_notes(dmg, [(14.0, 20.0)], 'Ivy: Air Drop bomb radius increased from 14m to 20m')
    assert dmg.op == 'add' and dmg.old is None
    # ...but a value the files write in metres takes the old one in metres (Rule, Ratannia! showed 0.508m -> 16m)
    rad = MChange('f', 'rat', 'p', 'add', None, '16m', 'balance', '', None, 'Radius', False, [1], False)
    _old_from_notes(rad, [(20.0, 16.0)], 'Rat King: Rule, Ratannia! Street Brawl radius reduced from 20m to 16m')
    assert (rad.op, rad.old) == ('change', '20m')


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


def test_window_op_merge():
    from pipeline.match import merge_ops
    assert merge_ops('add', 'change') == 'add'          # "— → 0.75" was CHANGED
    assert merge_ops('change', 'remove') == 'remove'    # "16.2 → —" was CHANGED
    assert merge_ops('remove', 'add') == 'change'
    assert merge_ops('change', 'change') == 'change'
    assert merge_ops('add', 'remove') == 'change'       # never shipped: old == new == None, dropped


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


def test_minor_update_2026_11_04_lines_find_their_fields():
    """Four lines of the 11-04 notes: a hero's resistance stat (not an ability's spirit scaling), two values to one
    "for both", a cut by N% that is the tier bonus too, an item's new field named by a word's stem."""
    from pipeline.match import annotate_line, pair_hits

    def run(text, changes, idx, cat):
        by_ent = {}
        for c in changes:
            by_ent.setdefault(f'{c.file}:{c.eid}', []).append(c)
        return annotate_line(text, changes, by_ent, idx, cat, {})

    # Baba's Spirit Resist per Spirit 0.07 -> 0.05, not Baba's Brew's burn scaling 0.15 -> 0.13
    resist = MChange('heroes.vdata', 'hero_baba', 'm_mapScalingStats.ETechArmorDamageReduction.flScale', 'change',
                     0.07, 0.05, 'balance', 'hero', None, 'Spirit Resist per Spirit', False)
    burn = MChange('abilities.vdata', 'ability_baba_hexing_brew',
                   'm_mapAbilityProperties.DamagePerSecond.m_subclassScaleFunction.m_flStatScale', 'change',
                   0.15, 0.13, 'balance', 'ability', 'hero_baba', 'Damage Per Second (spirit scaling)', False)
    idx = {'baba': ['heroes.vdata:hero_baba']}
    cat = {'heroes.vdata:hero_baba': {'id': 'hero_baba', 'kind': 'hero'},
           'abilities.vdata:ability_baba_hexing_brew': {'id': 'ability_baba_hexing_brew', 'kind': 'ability',
                                                         'owner': 'hero_baba'}}
    res = run('Baba: Spirit Resistance scaling reduced from 0.7 to 0.5', [resist, burn], idx, cat)
    assert res['changes'] == [resist.key]

    # "from A and B to C for both": both pairs, and each to the field with its exact numbers
    assert parse_pairs('T2 slow from -24% Slow and -26% Dash distance to -28% for both') == [(-24, -28), (-26, -28)]
    up = 'm_vecAbilityUpgrades[1].m_vecPropertyUpgrades{%s}.m_strBonus'
    dash = MChange('abilities.vdata', 'sand', up % 'GroundDashReductionPercent', 'change', '-26', '-28', 'balance',
                   'ability', None, 'T2: Dash Distance', False)
    slow = MChange('abilities.vdata', 'sand', up % 'SlowPercent', 'change', '24', '28', 'balance', 'ability', None,
                   'T2: Move Speed', False)
    assert sorted(c.key for c in pair_hits([(23, dash), (21, slow)], [(-24, -28), (-26, -28)], 9)) \
        == sorted([dash.key, slow.key])

    # "Spirit scaling reduced by 8%": the base scaling and the T3 bonus that moved by as much
    base = MChange('abilities.vdata', 'strix', 'm_mapAbilityProperties.Damage.m_subclassScaleFunction.m_flStatScale',
                   'change', 1.0, 0.92, 'balance', 'item', None, 'Damage (spirit scaling)', False)
    t3 = MChange('abilities.vdata', 'strix', 'm_vecAbilityUpgrades[2].m_vecPropertyUpgrades{Damage}.m_strBonus',
                 'change', '0.35', '0.322', 'balance', 'item', None, 'T3: Damage (spirit scaling)', False)
    other = MChange('abilities.vdata', 'strix', 'm_vecAbilityUpgrades[0].m_vecPropertyUpgrades{Radius}.m_strBonus',
                    'change', '2', '3', 'balance', 'item', None, 'T1: Radius', False)
    idx = {'strix salvo': ['abilities.vdata:strix'], 'healbane': ['abilities.vdata:healbane']}
    cat = {'abilities.vdata:strix': {'id': 'strix', 'kind': 'item'},
           'abilities.vdata:healbane': {'id': 'healbane', 'kind': 'item'}}
    res = run('Strix Salvo: Spirit scaling reduced by 8%', [base, t3, other], idx, cat)
    assert set(res['changes']) == {base.key, t3.key}

    # an item's field that came, by the stem of a word: "Stacks … diminish" is Stacking Penalty Anchor
    anchor = MChange('abilities.vdata', 'healbane', 'm_mapAbilityProperties.StackingPenaltyAnchorPercent.m_strValue',
                     'add', None, '80', 'balance', 'item', None, 'Stacking Penalty Anchor', False)
    res = run('Healbane: Stacks now diminish 20% more aggressively (at 2 stacks 57.8%->54.7%, at 4 stacks 82.2% to 72%)',
              [anchor], idx, cat)
    assert res['changes'] == [anchor.key] and res['status'] == 'described'
    # … only when no field shares a word: Headhunter's heal line is its heal scaling, not the bonus damage's too
    sc = 'm_mapAbilityProperties.%s.m_subclassScaleFunction.m_flStatScale'
    heal = MChange('abilities.vdata', 'hh', sc % 'HealPercentPerHeadshot', 'add', None, 0.014, 'balance', 'item', None,
                   'Heal Percent Per Headshot (spirit scaling)', False)
    bonus = MChange('abilities.vdata', 'hh', sc % 'HeadShotBonusDamage', 'add', None, 0.3, 'balance', 'item', None,
                    'Head Shot Bonus Damage (spirit scaling)', False)
    idx['headhunter'], cat['abilities.vdata:hh'] = ['abilities.vdata:hh'], {'id': 'hh', 'kind': 'item'}
    assert run('Headhunter: Heal now scales with spirit power (0.014)', [heal, bonus], idx, cat)['changes'] == [heal.key]
    assert run('Headhunter: Toxic now scales with spirit power (0.3)', [bonus], idx, cat)['changes'] == [bonus.key]


def test_data_audit_2026_11_13_units_direction_and_text():
    from pipeline import semantics as s
    from pipeline.abilities import fmt_prop
    from pipeline.match import MChange, change_json
    # a bare engine length under the tooltip's "m" is converted: Walker's Stomp read "500m -> 472.44m"
    stomp = MChange('abilities.vdata', 'w', 'm_mapAbilityProperties.Radius.m_strValue', 'change', '500', '472.441',
                    'balance', 'unit', None, 'Radius', False, [5983], False, unit='m')
    assert (change_json(stomp)['old_s'], change_json(stomp)['new_s']) == ('12.7m', '12m')
    assert fmt_prop({'x_postfix': 'm'}, 'x', '550', 'a', bonus=True) == '+13.97m'
    assert fmt_prop({'x_postfix': 'm'}, 'x', '20m', 'a') == '20m'            # written in metres: as is
    # Street Brawl values have a direction; an ambiguous word has none
    assert s.direction('m_mapAbilityProperties.AbilityCooldown.m_strStreetBrawlValue', 18, 26, 'ability')[0] == 'nerf'
    assert s.direction('m_mapAbilityProperties.DamageThreshold.m_strValue', 400, 500, 'ability')[0] == 'changed'
    assert s.direction('m_mapAbilityProperties.Damage.m_strValue', 400, 500, 'ability')[0] == 'buff'
    # a tiny "speed" is a multiplier, an update time is a date
    assert s.display_value(-0.15, s.SPEED) == '-0.15'
    assert s.polarity('m_iUpdateTime') == 0
    # an item's label from the items' text file
    tok = {'bonustechpower_label': 'Spirit Power while Pathing', '@items:bonustechpower_label': 'Spirit Power'}
    assert s._loc_label(tok, 'BonusTechPower', 'upgrade_ethereal_shift') == 'Spirit Power'
    assert s._loc_label(tok, 'BonusTechPower', 'ability_x') == 'Spirit Power while Pathing'


def test_one_moved_element_of_a_number_list_matches_a_single_pair():
    """Ranked Beta Season 2 (2026-11-15): "points … from a final subrank decreased from 2000 to 1500" is the last
    element of m_vecSubRankXP (1000 ×5, 2000) -> (1000 ×5, 1500); a list where two elements moved stays whole."""
    from pipeline.match import annotate_line
    xp = MChange('ranked_seasons.vdata', 'season_2', 'm_vecRankInfo{all}.m_vecSubRankXP', 'change',
                 [1000] * 5 + [2000], [1000] * 5 + [1500], 'mechanic', 'global', None,
                 'Points per Subrank (all ranks)', False)
    text = ('Ranking Up: The points required to reach a new badge from a final subrank have been decreased from '
            '2000 to 1500. The points between subranks remain unchanged at 1000.')
    res = annotate_line(text, [xp], {'ranked_seasons.vdata:season_2': [xp]}, {}, {}, {})
    assert res['changes'] == [xp.key] and res['status'] == 'documented'
    two = MChange('x.vdata', 'y', 'm_vecList', 'change', [1, 2000], [2, 1500], 'mechanic', 'global', None,
                  'Points per Subrank', False)
    assert (2000, 1500) not in two.steps()


def test_one_edit_in_the_modifiers_of_many_abilities_is_one_block():
    """Build 6711: "+can't be purged" in each ability's own modifier ({modifier_x}) was 16 rows (todo 2026-10-17,
    done 2026-11-15); a property key is what moved, so six different properties stay six changes."""
    from pipeline.match import alike_in_modifiers, modifier_block_json
    def mk(eid, path):
        return MChange('abilities.vdata', eid, path, 'add', None, 'MODIFIER_ATTRIBUTE_CANNOT_BE_PURGED', 'mechanic',
                       'ability', None, f'{eid} Watcher › Attributes', False)
    mods = [mk(f'a{i}', f'm_AutoIntrinsicModifiers{{modifier_a{i}}}.m_bProcOnFriendlyBulletHits') for i in range(6)]
    props = [mk(f'b{i}', f'm_vecAbilityUpgrades[0].m_vecPropertyUpgrades{{Prop{i}}}.m_strBonus') for i in range(6)]
    got = alike_in_modifiers(mods + props + mods[:1])
    assert {id(c) for c in mods} <= set(got) and not {id(c) for c in props} & set(got)
    assert got[id(mods[0])][1] == 'm_AutoIntrinsicModifiers{*}.m_bProcOnFriendlyBulletHits'
    row = modifier_block_json(mods[0], got[id(mods[0])][1])
    assert row['label'] == 'Attributes' and row['shared'] is True
    assert alike_in_modifiers(mods[:5]) == {}
    # a modifier the entity keeps under a field of its own: the switch alone is the shared path
    paths = ['m_UIRecastModifier.m_nAttributes', 'm_PickUpAura.m_modifierProvidedByAura.m_nAttributes',
             'm_KillCheckModifier.m_nAttributes', 'm_InShopModifier.m_nAttributes', 'm_nAttributes',
             'm_GraveStoneModifier.m_modifierProvidedByAura.m_nAttributes']
    got = alike_in_modifiers([mk(f'c{i}', p) for i, p in enumerate(paths)])
    assert len(got) == 6 and {s[1] for s in got.values()} == {'m_nAttributes'}
