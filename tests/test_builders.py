"""Rendering helpers: tags, order, escaping."""
import re

from builders.render import fold_tier_swaps, sort_changes, tag_of


def ch(**kw):
    base = {'op': 'change', 'cat': 'balance', 'label': 'Cooldown', 'old_s': '27', 'new_s': '29',
            'dir': 'nerf', 'pct': 7.4, 'grad': 2, 'status': 'hidden', 'path': 'x'}
    base.update(kw)
    return base


def test_tags():
    # no percentage in the badge: the value cell already shows it
    assert tag_of(ch()) == ('nerf', 'NERF')
    assert tag_of(ch(op='add'))[0] == 'new'
    assert tag_of(ch(op='remove'))[0] == 'del'
    assert tag_of(ch(cat='mechanic', dir='changed', pct=None)) == ('mech', 'MECH')
    assert tag_of(ch(dir='changed', pct=None)) == ('changed', 'CHANGED')


def test_a_corrupted_version_is_one_row():
    from builders.render import fold_corrupted
    p = 'm_CorruptedItemInfo.m_Upgrade.m_vecPropertyUpgrades{%s}.m_strBonus'
    rows = [{'op': 'add', 'path': p % 'AbilityCooldown', 'label': 'Corrupted: Cooldown', 'new_s': '-4', 'status': 'hidden'},
            {'op': 'add', 'path': p % 'BonusHealth', 'label': 'Corrupted: Base Health', 'new_s': '10', 'status': 'hidden'},
            {'op': 'add', 'path': p % 'X' + '.m_bFixedCorruptedBonus', 'label': 'Corrupted: X › Fixed Corrupted Bonus',
             'new_s': 'yes', 'status': 'hidden'},
            {'op': 'change', 'path': 'm_mapAbilityProperties.Radius.m_strValue', 'label': 'Radius', 'old_s': '5', 'new_s': '6'}]
    out = fold_corrupted(rows)
    assert len(out) == 2 and out[1]['label'] == 'Radius'
    # Broker's trade (City Never Sleeps): one NEW row, the bonuses listed, how they roll left out
    assert (out[0]['op'], out[0]['label'], out[0]['new_s']) == ('add', 'Corrupted version', 'Cooldown -4, Base Health +10')
    assert tag_of(out[0])[0] == 'new'
    # a later tweak of one or two bonuses stays row by row
    assert fold_corrupted(rows[:2]) == rows[:2]


def test_a_corrupted_version_names_its_penalties_and_tells_namesakes_apart(monkeypatch):
    """Review 2026-10-05: Unstoppable 'Excluded Penalties TechDuration, Bonus Health +175…'; Toxic Bullets
    'Incoming Healing -25%, Incoming Healing -25%'; one shared bonus made the row 'shared ×10 items'."""
    from builders import render
    monkeypatch.setattr(render, '_penalty_names', lambda: {'TechDuration': 'Ability Duration', 'FireRate': 'Fire Rate'})
    p = 'm_CorruptedItemInfo.m_Upgrade.m_vecPropertyUpgrades{%s}.m_strBonus'
    rows = [{'op': 'add', 'path': 'm_CorruptedItemInfo.m_vecExcludedPenalties', 'label': 'Corrupted: Excluded Penalties',
             'new_s': 'TechDuration, FireRate'},
            {'op': 'add', 'path': p % 'BonusHealth', 'label': 'Corrupted: Bonus Health', 'new_s': '175',
             'shared': True, 'shared_n': 10, 'shared_what': 'items'},
            {'op': 'add', 'path': p % 'HealAmpReceivePenaltyPercent', 'label': 'Corrupted: Incoming Healing', 'new_s': '-25%'},
            {'op': 'add', 'path': p % 'HealAmpRegenPenaltyPercent', 'label': 'Corrupted: Incoming Healing', 'new_s': '-25%'}]
    [row] = render.fold_corrupted(rows)
    assert row['new_s'] == ('Bonus Health +175, Incoming Healing · receive -25%, Incoming Healing · regen -25%'
                            ' · never rolls: Ability Duration, Fire Rate')
    assert 'shared_n' not in row and not row['shared']
    # the row of a later tweak reads the game's names too
    one = {'op': 'add', 'cat': 'balance', 'path': 'm_CorruptedItemInfo.m_vecExcludedPenalties', 'new_s': 'TechDuration'}
    assert render.vals_text(one) == ('', 'Ability Duration')


def test_rows_cards_and_matrix_cards_print_values_alike():
    """Review 2026-10-05: vals_text and the matrices' _sample_values were hand copies of vals_html (840 rows apart)."""
    from builders.dynamics_page import _sample_values
    from builders.render import vals_html, vals_text
    cases = [ch(path='m_mapAbilityProperties.AbilityCooldownBetweenCharge.m_strValue', old_s='0s', new_s='-1',
                pct=None, dir='changed'),
             ch(path='m_vecAbilityUpgrades[0].m_vecPropertyUpgrades{AbilityCooldown}.m_strBonus', old_s='-1s',
                new_s='-20s'),
             ch(path='x.m_strValue', old_s='-0.5m/s', new_s='-1m/s'),
             ch(path='y', old_s='30%', new_s='2', unit_switch=True, pct=None, dir='changed')]
    for c in cases:
        old, new = vals_text(c)
        html = vals_html(c)
        assert f'>{old}<' in html and f'>{new}<' in html, (c, old, new, html)
        assert _sample_values(c) == (old, new)
    assert vals_text(cases[0]) == ('0s', 'default')
    assert vals_text(cases[1]) == ('-1s', '-20s')
    assert vals_text(cases[3]) == ('30%', '2')


def test_an_enhanced_version_is_one_row():
    """Old Gods, New Blood: an item's Enhanced version that appears whole is ONE row and one change (452 NEW rows
    under one line of the notes); on the item page, inside its "Enhanced version" group, the row is "Bonuses"."""
    from builders.render import fold_versions
    p = 'm_vecAbilityUpgrades[0].m_vecPropertyUpgrades{%s}.m_strBonus'
    key = 'abilities.vdata:upgrade_active_reload:'
    rows = [{'op': 'add', 'path': p % x, 'key': key + p % x, 'label': f'Enhanced: {lab}', 'new_s': v, 'status': 'described'}
            for x, lab, v in (('BonusClipSizePercent', 'Max Ammo', '10%'), ('BonusFireRate', 'Fire Rate', '15%'),
                              ('BonusMoveSpeed', 'Move Speed', '3m/s'))]
    out = fold_versions(rows + [ch(label='Cooldown', key=key + 'cd')])
    assert len(out) == 2
    assert (out[0]['label'], out[0]['new_s'], out[0]['folded']) == ('Enhanced version',
                                                                     'Max Ammo +10%, Fire Rate +15%, Move Speed +3m/s', 3)
    stripped = [{**c, 'label': c['label'].removeprefix('Enhanced: ')} for c in rows]
    assert fold_versions(stripped)[0]['label'] == 'Bonuses'
    # a hero's T1 bonuses sit on the same path, but are no Enhanced version
    t1 = [{**c, 'key': 'abilities.vdata:ability_x:' + c['path'], 'label': 'T1: ' + c['label'][10:]} for c in rows]
    assert fold_versions(t1) == t1
    # a later tweak of a few Enhanced bonuses stays row by row
    assert fold_versions(rows[:2]) == rows[:2]


def test_unit_families_tiers_and_variants():
    """2026-10-03: Slum Shroom I-III, the four Walkers, the Barrel Mimics of two models are one family each."""
    from builders.unit_families import families, member_label, merged_label
    walkers = [{'id': i, 'name': 'Walker', 'alive': True}
               for i in ('alt_npc_boss_tier2', 'alt_npc_boss_tier2_weak', 'npc_boss_tier2', 'npc_boss_tier2_weak')]
    barrels = [{'id': f'neutral_barrel_0{m}_{t}', 'name': f'Barrel Mimic {r}', 'alive': True}
               for m in (1, 2) for t, r in (('weak', 'I'), ('normal', 'II'), ('strong', 'III'))]
    fams = families(walkers + barrels + [{'id': 'npc_trooper', 'name': 'Trooper', 'alive': True}])
    assert set(fams) == {'Walker', 'Barrel Mimic', 'Trooper'}
    # the main member: not an alt copy, not the weak copy of a boss; the lowest tier
    assert fams['Walker'][0]['id'] == 'npc_boss_tier2' and fams['Barrel Mimic'][0]['id'] == 'neutral_barrel_01_weak'
    w = fams['Walker']
    assert [member_label(m, w) for m in w] == ['Walker', 'weak', 'alt', 'alt weak']
    b = fams['Barrel Mimic']
    # a tiered family's variants differ in looks only: the tier names the group (round 3)
    assert member_label(b[0], b) == 'Tier I' and member_label(b[-1], b) == 'Tier III'
    assert merged_label(['Tier I · model 1', 'Tier I · model 2']) == 'Tier I'
    assert merged_label(['Tier I · model 1', 'Tier II · model 1']) == 'All tiers'
    assert merged_label(['Walker', 'weak', 'alt', 'alt weak'], 4) == 'All variants'
    assert merged_label(['Walker', 'alt'], 4) == 'Walker · alt'


def test_zero_added_or_removed_is_no_change():
    from builders.cards import is_noop
    assert is_noop({'op': 'add', 'path': 'p', 'new_s': '0'})            # Sleep Dagger's Explosion Radius 0
    assert is_noop({'op': 'remove', 'path': 'p', 'old_s': '0m'})
    assert is_noop({'op': 'change', 'old_s': '1.5', 'new_s': '1.5'})
    assert not is_noop({'op': 'add', 'path': 'p', 'new_s': '5'})
    assert not is_noop({'op': 'change', 'old_s': '20', 'new_s': '0'})   # tuned TO zero is a change
    assert not is_noop({'op': 'add', 'path': '@add', 'new_s': ''})       # an entity added to the game
    # the same value spelled two ways is not a change ("LOS Check: Bounds → Bounds")
    assert is_noop({'op': 'change', 'old_s': 'ELOSCheck_Bounds', 'new_s': 'Bounds'})
    assert is_noop({'op': 'change', 'old_s': 'Head Ignore Obscure Blockers', 'new_s': 'Head_IgnoreObscureBlockers'})
    assert not is_noop({'op': 'change', 'old_s': '1.5', 'new_s': '15'})


def test_availability_tags_follow_field_meaning():
    # 'Disabled: no -> yes' switches OFF, 'Player Selectable: no -> yes' switches ON
    assert tag_of(ch(cat='availability', label='Disabled', new_s='yes')) == ('off', 'OFF')
    assert tag_of(ch(cat='availability', label='In Development', new_s='no')) == ('on', 'ON')
    assert tag_of(ch(cat='availability', label='Player Selectable', new_s='yes')) == ('on', 'ON')
    assert tag_of(ch(cat='availability', label='State', new_s='EHeroDevState_PreRelease')) == ('off', 'OFF')
    assert tag_of(ch(cat='availability', label='State', new_s='EHeroDevState_Release')) == ('on', 'ON')


def test_order_new_buff_nerf_del_changed():
    order = [tag_of(c)[0] for c in sort_changes([
        ch(cat='mechanic', dir='changed', label='a'), ch(op='remove', label='b'), ch(dir='nerf', label='c'),
        ch(dir='buff', label='d'), ch(op='add', label='e'), ch(dir='changed', label='f')])]
    assert order == ['new', 'buff', 'nerf', 'del', 'mech', 'changed']


def test_tier_swap_folds_into_one_rework_row():
    rows = fold_tier_swaps([
        ch(op='remove', label='T2: Buff Duration', old_s='25', new_s=None, status='described'),
        ch(op='remove', label='T2: Fire Rate', old_s='14', new_s=None, status='described'),
        ch(op='add', label='T2: Stun Duration', old_s=None, new_s='0.6', status='hidden'),
        ch(op='add', label='T3: Impact Radius', old_s=None, new_s='6', status='documented'),
        ch(label='Damage', old_s='75', new_s='100', dir='buff', status='documented'),
    ])
    rework = [r for r in rows if r['op'] == 'rework']
    assert len(rework) == 1 and rework[0]['label'] == 'T2 upgrade'
    assert rework[0]['old_s'] == 'Buff Duration 25, Fire Rate 14' and rework[0]['new_s'] == 'Stun Duration 0.6'
    assert rework[0]['status'] == 'hidden'          # the least documented part decides
    assert {r['label'] for r in rows} == {'T2 upgrade', 'T3: Impact Radius', 'Damage'}   # T3 only added: kept


def test_entity_rows_name_once_with_counters():
    """The ability's header (cards.sub_head) names it once with its counters; its rows do not repeat it.
    (render.entity_rows, the table version, had no caller left besides these tests.)"""
    from builders.cards import entity_rows, sub_head
    rows = [ch(label='a', key='abilities.vdata:x:a'), ch(label='b', dir='buff', key='abilities.vdata:x:b'),
            ch(label='c', key='abilities.vdata:x:c')]
    html = sub_head('Seismic Impact', None, 'abilities', rows, hidden=True) + entity_rows(rows)
    assert html.count('Seismic Impact') == 1
    assert '<span class="pip nerf">2</span>' in html and '<span class="pip buff">1</span>' in html
    assert 'esub has-hidden' in html


def test_unreleased_rows_marked_but_not_counted_as_not_in_notes():
    """Work on a hero in development keeps its mark; it is not "not in patch notes" (render.NOT_IN_NOTES)."""
    from builders.cards import change_row
    html = change_row(ch(status='unreleased'))
    assert 'mark unreleased' in html and 'st-unreleased' in html and 'is-hidden' not in html


def test_change_row_escapes_and_marks_hidden():
    from builders.cards import change_row
    html = change_row(ch(label='<b>x</b>'))
    assert '&lt;b&gt;' in html and 'mark hidden' in html and 'st-hidden' in html


def test_flag_lists_show_only_the_difference():
    from builders.render import vals_html
    html = vals_html(ch(cat='mechanic', old_s='CITADEL_ABILITY_BEHAVIOR_A | CITADEL_ABILITY_BEHAVIOR_B',
                        new_s='CITADEL_ABILITY_BEHAVIOR_B | CITADEL_ABILITY_BEHAVIOR_MOVEMENT', dir='changed', pct=None))
    assert '+movement' in html and '−a' in html and 'CITADEL' not in html


def test_text_change_keys_read_as_names(monkeypatch):
    from builders import patches_pages
    monkeypatch.setattr(patches_pages, 'names_by_id', lambda: {'ability_afterburn': 'Afterburn', 'hero_atlas': 'Abrams'})
    assert patches_pages.loc_key_label('ability_afterburn_t1_desc') == 'Afterburn · T1 description'
    assert patches_pages.loc_key_label('ability_afterburn_burn_header') == 'Afterburn · burn header'
    assert patches_pages.loc_key_label('hero_atlas:n') == 'Abrams · name'
    assert patches_pages.loc_key_label('citadel_commend_toast_seconds') == 'commend toast seconds'


def test_unnamed_entities_never_show_internal_ids():
    from builders.common import pretty_id
    assert pretty_id('citadel_weapon_frank_set', 'hero_frank') == 'Weapon'
    assert pretty_id('citadel_weapon_viscous_alt', 'hero_viscous') == 'Alt weapon'
    assert pretty_id('ability_druid_sprout', 'hero_druid') == 'Sprout'
    assert pretty_id('citadel_ability_shiv_dive', 'hero_shiv') == 'Dive'
    assert pretty_id('ability_doorman_ult', 'hero_doorman') == 'Ultimate'
    assert pretty_id('ability_doorman_ability03', 'hero_doorman') == 'Ability 3'


def test_id_lists_in_values_show_names(monkeypatch):
    from builders import common
    monkeypatch.setattr(common, 'names_by_id', lambda: {'ability_blood_bomb': 'Blood Bomb'})
    assert common.ids_to_names('ability_blood_bomb, ability_blood_bomb') == 'Blood Bomb, Blood Bomb'
    assert common.ids_to_names('CITADEL_ABILITY_BEHAVIOR_CLEAVE') == 'CITADEL_ABILITY_BEHAVIOR_CLEAVE'


def test_hero_table_layout_keeps_every_column_and_hides_details():
    from builders.tables_pages import DETAILS, HERO_LAYOUT, laid_out
    cols = [{'key': 'dps', 'label': 'DPS', 'group': 'Damage'}, {'key': 'spread', 'label': 'Spread', 'group': 'Damage'},
            {'key': 'brand_new', 'label': 'Brand new stat', 'group': 'Damage'}]
    out = laid_out(cols, HERO_LAYOUT)
    assert [c['key'] for c in out] == ['dps', 'spread', 'brand_new']          # nothing dropped, details last
    assert out[0]['group'] == 'Weapon' and out[1]['group'] == DETAILS and out[2]['group'] == DETAILS
    assert all(len(short) <= 13 for _, entries in HERO_LAYOUT for _, short in entries)   # one-line headers


def test_rows_without_game_art_get_a_category_glyph():
    from builders.common import glyph_for, visual
    assert glyph_for('heroes.vdata', '@shared') == 'heroes'
    assert glyph_for('generic_data.vdata', 'm_IdolParams') == 'rules'
    html = visual(None, 'map')        # the shape is CSS (.glyph.g-map, a mask)
    assert html == '<span class="px glyph g-map"></span>' and 'noimg' not in html


def test_patch_notes_grouped_by_entity_with_tags_and_numbers(monkeypatch):
    from builders import notes_view
    monkeypatch.setattr(notes_view, '_catalog', lambda: [
        {'file': 'abilities.vdata', 'id': 'upgrade_kevlar', 'name': "Diviner's Kevlar", 'kind': 'item', 'alive': True}])
    notes_view._by_name.cache_clear()
    notes_view._abilities_of.cache_clear()
    change = ch(key='k1', file='abilities.vdata', id='upgrade_kevlar', label='Spirit Power', old_s='35', new_s='40',
                dir='buff', status='documented', ent_name="Diviner's Kevlar")
    p = {'id': '2026-07-28', 'entities': [], 'sections': [{'title': 'Items', 'lines': [
        {'text': "Diviner's Kevlar: Spirit power increased from +35 to +40", 'subject': "Diviner's Kevlar",
         'status': 'documented', 'changes': ['k1']},
        {'text': "Diviner's Kevlar: No longer grants a shield", 'subject': "Diviner's Kevlar",
         'status': 'unmatched', 'changes': []}]}]}
    monkeypatch.setattr('builders.trail.trail_html', lambda *a, **k: '')
    html = notes_view.notes_table(p, {'k1': change}, '../')
    assert 'class="banner"' in html and html.count('class="ecard-h"') == 1            # section banner, one card
    assert html.count("Diviner&#x27;s Kevlar") == 1                                     # name only in the header
    assert 'Spirit power increased from <span class="o">+35</span> to <span class="n dir-buff">+40</span>' in html
    assert 'tag buff' in html and 'No longer grants a shield' in html
    assert 'tag del' in html                       # a line without a matched change still gets a tag (No longer → DEL)
    notes_view._by_name.cache_clear()
    notes_view._abilities_of.cache_clear()


def test_hero_page_lines_drop_the_hero_name():
    from builders.history_view import _drop_prefix          # (hero_page._strip_subject had no caller left)
    assert _drop_prefix('Abrams: Melee damage per boon increased by 10%', ['Abrams']) == \
        'Melee damage per boon increased by 10%'
    # another subject stays: the line is about the ability, not the hero
    assert _drop_prefix('Seismic Impact: Damage increased', ['Abrams']) == 'Seismic Impact: Damage increased'


def test_ability_card_leaves_out_an_empty_tier(monkeypatch):
    """97 bare "T1 / T2 / T3" lines (no text, no bonuses) sat on the cards of heroes in development."""
    from builders import hero_page, trail
    monkeypatch.setattr(trail, 'last_counts', lambda key: None)
    monkeypatch.setattr(trail, 'trail_html', lambda *a, **k: '')
    card = {'id': 'ability_zzz_x', 'kind': 'ability', 'name': 'Zap', 'owner': 'hero_zzz', 'slot': 'Signature_1',
            'tiers': [{'tier': 1, 'text': '', 'bonuses': []}, {'tier': 2, 'text': '+1 Charge', 'bonuses': []},
                      {'tier': 3, 'text': '', 'bonuses': [{'label': 'Damage', 'value': '+20'}]}]}
    html = hero_page.ability_card(card, '../')
    assert '>T1<' not in html and '>T2<' in html and 'Damage +20' in html


def test_notes_name_without_leading_the(monkeypatch):
    from builders import notes_view
    monkeypatch.setattr(notes_view, '_catalog', lambda: [
        {'file': 'heroes.vdata', 'id': 'hero_doorman', 'name': 'The Doorman', 'kind': 'hero', 'alive': True}])
    notes_view._by_name.cache_clear()
    assert notes_view._by_name()['doorman']['id'] == 'hero_doorman'
    notes_view._by_name.cache_clear()


def test_history_is_one_panel_per_patch_with_sub_headers():
    from builders.history_view import history_table
    row = {'id': '2026-09-16', 'date': '2026-09-16', 'title': '09-16-2026 Update'}
    keys = [('heroes.vdata:hero_atlas', 'Base stats', None), ('abilities.vdata:ab_charge', 'Shoulder Charge', None)]
    by_ent = {'abilities.vdata:ab_charge': [(row, [ch(key='c1', label='T1: Move Speed')])],
              'heroes.vdata:hero_atlas': [(row, [ch(key='c2', label='Health per boon')])]}
    html = history_table(keys, ['Abrams'], by_ent, {}, '../')
    assert html.count('class="hpanel') == 1 and html.count('class="hgroup') == 2
    assert 'ecard' not in html and html.count('class="esub') == 2
    # a page about one entity repeats no sub-header with its own name
    one = history_table(keys[1:], ['Shoulder Charge'], {'abilities.vdata:ab_charge': by_ent['abilities.vdata:ab_charge']},
                        {}, '../')
    assert 'esub' not in one and 'T1: Move Speed' in one


def test_replaced_tier_row_gets_full_width_line():
    from builders.cards import change_rows
    html = change_rows([ch(op='remove', label='T2: Fire Rate', old_s='14', new_s=None),
                        ch(op='add', label='T2: Stun Duration', old_s=None, new_s='0.6')])
    assert 'erow st-hidden is-hidden rw' in html and 'T2 upgrade' in html


def test_player_facing_is_the_one_counting_rule():
    from builders.cards import player_facing
    engine = ch(key='heroes.vdata:hero_atlas:m_x', label='Roster Background Layout', old_s='A', new_s='B')
    swap = [ch(key='abilities.vdata:a:t2a', op='remove', label='T2: Fire Rate', old_s='14', new_s=None),
            ch(key='abilities.vdata:a:t2b', op='add', label='T2: Stun Duration', old_s=None, new_s='0.6')]
    other = [ch(key='abilities.vdata:b:t2c', op='add', label='T2: Range', old_s=None, new_s='3')]
    out = player_facing([engine] + swap + other)
    # engine plumbing out; ability a's swapped tier is one REWORK; ability b's T2 is not folded into a's
    assert [c['op'] for c in out] == ['rework', 'add']


def test_weapon_panel_six_tiles_and_units_on_the_number():
    from builders import hero_page
    cols = [{'key': k, 'label': lbl, 'group': 'Damage', 'digits': 2, 'pol': 1}
            for k, lbl in [('dps', 'DPS'), ('dps_max', 'Max DPS'), ('bullet_dmg', 'Bullet DMG'), ('bps', 'Bullets / s'),
                           ('clip', 'Ammo'), ('reload', 'Reload (s)'), ('bullet_speed', 'Bullet Speed (m/s)')]]
    row = {'values': {c['key']: 1.5 for c in cols}, 'history': {}, 'spirit_scaled': []}
    html = hero_page.weapon_block({'name': 'Case Closed', 'id': 'w'}, row, cols, 'Abrams', '../')
    assert html.count('wcell top') == 6 and 'Reload s' in html
    assert '<span class="u">m/s</span>' in html and '>Bullet Speed<' in html


def test_hero_page_cards_only_what_the_hero_binds_now():
    """2026-10-03: Calico's page showed Catform pounce, Nekomata Ward and five more abilities she no
    longer binds; Infernus's showed the shared Jump / Mantle / Zipline."""
    from builders.hero_page import current_cards
    cards = {i: {'id': i, 'owner': o, 'slot': s} for i, o, s in [
        ('ult', 'hero_nano', 'Signature_4'), ('gun', 'hero_nano', 'Weapon_Primary'),
        ('a1', 'hero_nano', 'Signature_1'), ('catform_pounce', 'hero_nano', ''),
        ('ritual', 'hero_nano', None), ('jump', 'hero_nano', 'Ability_Jump'), ('x', 'hero_atlas', 'Signature_1')]}
    assert [c['id'] for c in current_cards(cards, 'hero_nano')] == ['gun', 'a1', 'ult']


def test_hero_chip_shows_two_counters_tooltip_has_all():
    from builders.patches_pages import _hero_chip
    html = _hero_chip('hero_atlas', 'Abrams', {'new': 9, 'buff': 8, 'nerf': 9, 'del': 8}, '../', '')
    assert html.count('class="pip') == 2 and 'pip new' in html and 'pip nerf' in html
    assert 'data-tooltip="Abrams: 9 new, 8 buffs, 9 nerfs, 8 removed"' in html


def test_last_change_skips_engine_only_patches(monkeypatch):
    """The history squares and an ability card's "last change" count what a player reads: a patch that only
    moved engine plumbing is not the entity's last change. The archive is read once per build
    (builders/archive.py)."""
    from builders import archive, trail
    patches = {
        'patches/index.json': [{'id': 'p1', 'date': '2026-09-16'}, {'id': 'p2', 'date': '2026-09-29'}],
        'patches/p1.json.gz': {'entities': [{'file': 'heroes.vdata', 'id': 'hero_atlas', 'key': 'heroes.vdata:hero_atlas',
                                             'changes': [ch(key='heroes.vdata:hero_atlas:x', dir='buff')]}]},
        'patches/p2.json.gz': {'entities': [{'file': 'heroes.vdata', 'id': 'hero_atlas', 'key': 'heroes.vdata:hero_atlas',
                                             'changes': [ch(key='heroes.vdata:hero_atlas:m_x',
                                                            label='Roster Background Layout', old_s='A', new_s='B')]}]},
    }
    monkeypatch.setattr(archive, 'load_json', lambda name: patches[name])
    archive.clear()
    trail._index.cache_clear()
    trail._positions.cache_clear()
    try:
        row, counts = trail.last_counts('heroes.vdata:hero_atlas')
        assert row['id'] == 'p1' and counts == {'buff': 1}
    finally:
        archive.clear()
        trail._index.cache_clear()
        trail._positions.cache_clear()


def test_patch_titles_show_the_date_once():
    from builders.common import patch_name, patch_title_html, patch_title_text
    assert patch_name('City Never Sleeps · 09-29-2026') == 'City Never Sleeps'
    assert patch_name('Gameplay Update - 03-06-2026') == 'Gameplay Update'
    assert patch_name('09-16-2026 Update') is None
    assert patch_name('06-30-2026 Update · follow-up 2026-07-28') is None
    row = {'title': '09-16-2026 Update', 'date': '2026-09-16'}
    assert patch_title_html(row).count('2026-09-16') == 1 and '09-16-2026' not in patch_title_html(row)
    assert patch_title_text({'title': 'City Never Sleeps · 09-29-2026', 'date': '2026-09-29'}) == 'City Never Sleeps · 2026-09-29'


def test_pct_pill_strength_follows_size():
    from builders.render import pct_grade, vals_html
    assert [pct_grade(x) for x in (2, -7, 20, -45, 122)] == [1, 2, 3, 4, 5]
    assert 'data-g="3"' in vals_html(ch(old_s='40', new_s='32', pct=-20.0))


def test_pixel_icons_are_10x10_without_lone_pixels():
    from builders.pixel_icons import GRID, TAG_ART, art_path, svg_mask, tag_mask
    for tag, rows in TAG_ART.items():
        assert len(rows) == GRID and all(len(r) == GRID for r in rows), tag
        for y, line in enumerate(rows):
            for x, ch_ in enumerate(line):
                if ch_ != '#':
                    continue
                around = [rows[j][i] for j in range(max(0, y - 1), min(GRID, y + 2))
                          for i in range(max(0, x - 1), min(GRID, x + 2)) if (i, j) != (x, y)]
                assert '#' in around, f'lone pixel in {tag} at {x},{y}'
    assert art_path(('#.#', '###')) == 'M0 0h1v1h-1zM2 0h1v1h-1zM0 1h3v1h-3z'
    assert tag_mask('buff') == svg_mask(art_path(TAG_ART['buff']), GRID)
    assert "viewBox='0 0 10 10'" in tag_mask('buff') and "fill-rule='evenodd'" in svg_mask('M0 0h1v1H0z', evenodd=True)


def test_added_entity_shows_a_summary_not_every_field():
    from builders.cards import change_rows
    rows = [ch(op='add', path='m_mapStartingStats.EMaxHealth', label='Max Health', old_s=None, new_s='780'),
            ch(op='add', path='m_mapBoundAbilities.ESlot_Signature_1', label='Bound Abilities › Signature 1', old_s=None,
               new_s='Splatter')]
    rows += [ch(op='add', path=f'm_mapLevelInfo.{i}.m_unRequiredGold', label=f'{i} › Required Gold', old_s=None,
                new_s=str(i * 100)) for i in range(1, 30)]
    html = change_rows(rows, added=True)
    assert 'Added to the game files · 31 fields' in html and 'Max Health' in html and 'Splatter' in html
    assert 'All fields (29)' in html


def test_engine_values_read_as_words():
    from builders.render import readable_value
    assert readable_value('EHeroDevState_PreRelease') == 'Pre Release'
    assert readable_value('CITADEL_UNIT_TARGET_NEUTRAL') == 'Neutral'
    assert readable_value('file://{images}/events/voting_sept2026/sticker_baba.psd') == 'sticker_baba'
    assert readable_value('12.5') == '12.5' and readable_value('Splatter') == 'Splatter'


def test_renamed_field_is_judged_and_unit_only_renames_drop():
    from builders.cards import merge_renames
    rows = merge_renames([ch(op='remove', label='Weapon Damage', old_s='45', new_s=None, dir='changed',
                             path='m_mapAbilityProperties.WeaponDamage.m_strValue'),
                          ch(op='add', label='Weapon Damage', old_s=None, new_s='40', dir='changed',
                             path='m_mapAbilityProperties.BonusWeaponDamage.m_strValue')])
    assert len(rows) == 1 and rows[0]['op'] == 'change' and rows[0]['dir'] == 'nerf'
    same = merge_renames([ch(op='remove', label='Radius', old_s='100', new_s=None),
                          ch(op='add', label='Radius', old_s=None, new_s='2.54m')])
    assert same == []


def test_table_edited_row_by_row_folds_into_one_summary():
    from builders.cards import change_rows
    rows = [ch(label=f'Level {n}: souls needed', old_s=str(n * 1000), new_s=str(n * 950), dir='buff', pct=-5.0)
            for n in range(19, 25)]
    html = change_rows(rows)
    assert 'details class="fam' in html and 'Level 19–24: souls needed' in html and '6 rows' in html
    assert html.count('class="erow') == 7          # the summary + the 6 rows behind it
    few = change_rows([ch(label='T1: Cooldown'), ch(label='T2: Cooldown')])
    assert 'fam' not in few


def test_whole_level_added_is_one_row_and_moved_fields_drop():
    from builders.cards import change_rows, merge_renames
    rows = [ch(op='add', label='Level 35: souls needed', old_s=None, new_s='47000'),
            ch(op='add', label='Level 35: gives a boon', old_s=None, new_s='yes'),
            ch(op='add', label='Level 35: ability points', old_s=None, new_s='1')]
    html = change_rows(rows)
    assert html.count('class="erow') == 1 and 'Level 35 added' in html and '47000 souls' in html
    assert merge_renames([ch(op='remove', label='Pickup Radius', old_s='85', new_s=None),
                          ch(op='add', label='Pickup Radius › Base', old_s=None, new_s='85')]) == []


def test_items_index_is_the_game_shop_matrix(monkeypatch):
    from builders import shop_page
    monkeypatch.setattr('builders.trail.last_change', lambda key: None)
    items = [{'file': 'abilities.vdata', 'id': f'upgrade_{n}', 'name': n.title(), 'alive': True} for n in
             ('basic', 'sharp', 'spell', 'brawl', 'old')]
    items[-1]['alive'] = False
    cards = {'upgrade_basic': {'item': {'tier': '1', 'slot': 'WeaponMod', 'activation': 'Passive', 'cost': 800}},
             'upgrade_sharp': {'item': {'tier': '2', 'slot': 'WeaponMod', 'activation': 'Active', 'cost': 1600,
                                        'components': ['upgrade_basic']}},
             'upgrade_spell': {'item': {'tier': '1', 'slot': 'Tech', 'activation': 'Passive', 'imbue': True, 'cost': 800}},
             'upgrade_brawl': {'item': {'tier': '5', 'slot': 'Armor', 'street_brawl': True, 'cost': 9999}}}
    import json
    html, tips = shop_page.shop_html(items, cards, '../')
    # tabs in the game's order, a catalog page per category, All Items with the game's three columns
    assert html.index('data-gs="all"') < html.index('data-gs="w"') < html.index('data-gs="s"') < html.index('data-gs="v"')
    assert 'class="gs-page w"' in html and 'class="gs-page all"' in html
    assert html.index('ga-col w') < html.index('ga-col s') < html.index('ga-col v') and 'price_t4.webp' in html
    # paper of the card's category and tier, round for an active item, the Imbue strip, what it builds from/into
    assert 'class="gcard p-w2 act"' in html and 'class="gcard p-s1 m1"' in html and 'class="gc-imb"' in html
    assert 'data-comp="upgrade_basic"' in html and 'data-up="upgrade_sharp"' in html
    # Street Brawl's T5 on the dark card, removed items last; tooltips are a separate json
    assert 'Street Brawl legendaries' in html and 'gcard p-v4' in html and 'Removed or disabled' in html
    assert '<template' not in html and 'data-tips="shop-tips.json"' in html
    tips = json.loads(tips)
    assert set(tips) == {'upgrade_basic', 'upgrade_sharp', 'upgrade_spell', 'upgrade_brawl', 'upgrade_old'}
    assert 'Upgrades from</b> Basic' in tips['upgrade_sharp'] and 'Upgrades to</b> Sharp' in tips['upgrade_basic']


def test_shop_catalog_geometry_is_the_games():
    """citadel_shop_mods_filtered.css: the cards per row the game shows (Fairfax tier 3 seven wide,
    tier 4 four; MPS and the Curiosity Catalog five and six), the first card where the art leaves room."""
    from builders.game_shop import price_at, tier_box
    per = {cat: [tier_box(cat, t)[2] for t in (1, 2, 3, 4)] for cat in 'wsv'}
    assert per == {'w': [5, 6, 7, 4], 's': [5, 6, 5, 6], 'v': [5, 6, 5, 6]}
    assert tier_box('w', 1)[:2] == (66, 185)            # card at 69, 188: under "TIER 1"
    assert tier_box('v', 4)[:2] == (552, 545)           # tier 2 / 4 rows sit 20px further right
    assert price_at('w', 4) != price_at('v', 4) and price_at('s', 4) == price_at('v', 4)


def test_heroes_grid_sorts_like_the_game():
    from builders.heroes_grid import heroes_grid_html
    live = [{'file': 'heroes.vdata', 'id': 'hero_doorman', 'name': 'The Doorman'},
            {'file': 'heroes.vdata', 'id': 'hero_viscous', 'name': 'Viscous'},
            {'file': 'heroes.vdata', 'id': 'hero_atlas', 'name': 'Abrams', 'state': 'EHeroDevState_PreRelease'}]
    rows = {'hero_doorman': {'sort_name': 'Doorman', 'type': 'ECitadelHeroType_Mystic', 'complexity': 1,
                             'color': [237, 149, 60]},
            'hero_viscous': {'new_player': True}}
    html = heroes_grid_html(live, [], rows, '../')
    assert html.index('Abrams') < html.index('The Doorman') < html.index('Viscous')
    # one grid (no "Great for new players" row: the owner asked), the game's colour on the plate
    # one grid, a portrait and a name: no role, complexity or last-patch line (owner, 2026-10-01)
    assert 'Great for new players' not in html and 'Mystic' not in html and 'hg-cx' not in html and 'Pre-release' in html
    assert 'style="--hero: rgb(237 149 60)"' in html


def test_interface_lines_get_their_own_tab_and_lists_become_chips():
    from builders import notes_view
    secs = [{'title': 'Gameplay', 'lines': [{'text': 'Tough Crates: need a Heavy Melee', 'status': 'unmatched'}]},
            {'title': 'User Interface', 'lines': [{'text': 'Player Names: find your party', 'status': 'untracked',
                                                   'topic': 'interface'}]},
            {'title': 'Additional Update Notes', 'lines': [
                {'text': 'New and improved SFX', 'status': 'untracked', 'topic': 'sound'},
                {'text': 'Graves can now destroy traps', 'status': 'unmatched'}]}]
    play, iface = notes_view.split_sections(secs)
    assert [s['title'] for s in play] == ['Gameplay', 'Additional Update Notes']
    assert [s['title'] for s in iface] == ['User Interface', 'Additional Update Notes']
    html = notes_view.interface_table(iface)
    assert '<b>Player Names</b>' in html and 'tag' not in html
    assert notes_view._list_chips('Theater, Chinatown, Haunted Lot, Plaza', '../').count('nchip') == 5   # wrapper + 4
    assert notes_view._list_chips('a long sentence, not a list', '../') is None


def test_change_matrix_rows_cells_and_switches(monkeypatch):
    from builders import dynamics_page
    rows = [{'id': 'p1', 'date': '2024-01-01', 'title': '01-01-2024 Update'},
            {'id': 'p2', 'date': '2026-09-29', 'title': 'City Never Sleeps · 09-29-2026'}]
    cells = {'hero:hero_atlas': {'p2': {'buff': 2, 'nerf': 1}}, 'hero:hero_x': {'p1': {'new': 1}}}
    samples = {'hero:hero_atlas': {'p2': [['Siphon Life', 'T3: Radius', '3', '2', 'nerf', 'abil']]}}
    parts = {'hero:hero_atlas': {'p2': {'abil': {'nerf': 1}, 'stats': {'buff': 2}}}}
    monkeypatch.setattr(dynamics_page, '_collect', lambda: {'rows': rows, 'cells': cells, 'parts': parts,
                                                            'samples': samples})
    html = dynamics_page.matrix_html([('hero:hero_atlas', 'Abrams', None, 'hero_atlas.html', ''),
                                      ('hero:hero_x', 'Old', None, 'hero_x.html', 'extra'),
                                      ('hero:hero_none', 'Nothing', None, 'n.html', '')], 'hero')
    assert 'Nothing' not in html                                   # a row with no changes is not listed
    # stripes as one gradient in tag order (buff before nerf), the nerf held at its 12% minimum share
    assert 'var(--tag-buff) 0% 66.7%,var(--tag-nerf) 66.7% 100%' in html and 'net-buff' in html
    # a tile of one tag is a class (.dsq.s-new), no inline gradient
    assert '<a class="dsq net-buff s-new" href="hero_x.html#p-p1" data-k="1">' in html
    from pathlib import Path
    css = (Path(__file__).resolve().parent.parent / 'site' / 'styles.css').read_text(encoding='utf-8')
    for t in ('new', 'rework', 'buff', 'nerf', 'del', 'on', 'off', 'mech', 'changed'):
        assert f'.dsq.s-{t} {{ background: var(--tag-{t}); }}' in css, t
    # >1 year old column: hidden with its colgroup column; a run of empty cells is one cell
    assert '<col class="old">' in html and '<td class=old></td>' in html and 'dd named' in html
    assert '--n-all:2;--n-new:1' in html
    # a tile opens the row's own page at that patch, not the patch page (off the bar since 10-03)
    assert 'href="hero_atlas.html#p-p2"' in html and 'tr class="extra"' in html
    # the hover card's data: the cell's counts and its biggest changes, the number on the tile
    assert 'class="dyn-data"' in html and 'Siphon Life' in html and '<span class="dn">3</span>' in html
    # one tile per cell (no split, owner 10-01); the part counts ride in the data for the filter
    assert 'dsq split' not in html and 'tr class="sub' not in html and '{"abil":{"nerf":1}' in html
    bar = dynamics_page.toolbar('hero', 1, 'Pre-release')
    # tag chips select (only these tags), as on an entity page — not "hide this tag"
    assert 'show-old' in bar and 'bvn' in bar and 'data-dyn-tag="buff"' in bar and 'show-extra' in bar
    assert 'data-part="weapon"' in bar and 'data-part="all"' in bar


def test_matrix_merges_empty_runs_but_not_across_the_old_line():
    """2026-10-03: the item matrix had 29k cells, 27k of them empty — a run of empty cells is one cell."""
    from builders.dynamics_page import _gap, stripes
    assert _gap(1, False) == '<td></td>' and _gap(5, True) == '<td class=old colspan=5></td>'
    # a lone tag fills the tile; a tiny share still shows (12% minimum)
    assert stripes({'new': 1}) == 'linear-gradient(var(--tag-new) 0% 100%)'
    assert 'var(--tag-changed)' in stripes({'up': 1, 'buff': 30})


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


def test_calendar_shades_and_gaps():
    from builders.calendar_page import _gaps, _shade
    assert [_shade(n) for n in (0, 1, 3, 6, 10)] == [0, 1, 2, 3, 4]
    ps = [{'date': '2026-01-01', 'title': 'a'}, {'date': '2026-01-11', 'title': 'b'}, {'date': '2026-01-13', 'title': 'c'}]
    assert [g[0] for g in _gaps(ps)] == [10, 2]


def test_hero_stats_boons_and_roles():
    from builders.tables_pages import boon_attrs
    r = {'values': {'hp': 800, 'hp_lvl': 49, 'dps': 51.4, 'bullet_dmg': 3.6, 'bullet_dmg_lvl': 0.1}}
    assert boon_attrs(r, {'key': 'hp'}) == ' data-per="49"'
    # DPS grows with the bullet: 51.4 * 0.1 / 3.6 per boon
    assert boon_attrs(r, {'key': 'dps'}) == ' data-per="1.42778"'
    assert boon_attrs(r, {'key': 'reload'}) == ''


def test_number_lists_are_values_not_flags():
    from builders.render import flags_html
    # a recoil range or prices by tier keep their order: no "+-0.1 +0.1" chips (314 rows, 2026-10-02)
    assert flags_html('', '-0.1, 0.1') is None
    assert flags_html('0, 500, 1200', '0, 500, 1250') is None
    assert 'flag add' in flags_html('A | B', 'A | B | C')


def test_key_bindings_in_text_read_as_keys():
    from builders.patches_pages import _plain
    assert _plain("Press {g:citadel_binding:'Attack'} to fire") == 'Press [Attack] to fire'
    # a binding with a form word ("1st") was printed raw on 12 build pages
    assert _plain("{g:citadel_binding:1st:'Spectator.SpecNext'}Target") == '[Spec Next] Target'


def test_no_limit_reads_as_no_limit():
    from builders.cards import is_noop
    from builders.render import shown_value
    # one wording for 9999 and -1 (audit 2026-10-04: "∞ → no limit" read as a change)
    assert shown_value('9999') == 'no limit' and shown_value('99999') == 'no limit' and shown_value('9999m') == 'no limit'
    assert shown_value('999') == '999'
    # the spellings of "no limit" are one value
    assert is_noop({'op': 'change', 'old_s': '9999', 'new_s': '99999'})
    assert is_noop({'op': 'change', 'old_s': '9999', 'new_s': '-1',
                    'path': 'm_mapAbilityProperties.ChannelMoveSpeed.m_strValue'})


def test_flags_written_without_spaces_read_as_words():
    from builders.render import flags_html, readable_value
    v = 'CITADEL_ABILITY_BEHAVIOR_CHANNELLED|CITADEL_ABILITY_BEHAVIOR_NO_TARGET'
    assert readable_value(v) == 'Channelled | No Target'
    assert '+channelled' in flags_html('', v)


def test_build_page_lists_cosmetics_groundwork(monkeypatch):
    from builders import builds_pages
    ev = {'build': 6711, 'kind': 'base body', 'op': 'added', 'subjects': ['hero_bookworm'], 'files': 30}
    snd = {'build': 6711, 'kind': 'cosmetic sounds', 'op': 'added', 'subjects': ['hero_poster'], 'files': 22}
    monkeypatch.setattr(builds_pages, 'cosmetics', lambda: {'events': [ev, snd], 'heroes': {}})
    monkeypatch.setattr(builds_pages, 'names_by_id', lambda: {'hero_bookworm': 'Paige'})
    html = builds_pages.cosmetics_section(6711, '../')
    assert 'Base body' in html and '>Paige</a>' in html and 'heroes/bookworm.html' in html and 'hero poster' in html
    assert builds_pages.cosmetics_section(6710, '../') == ''


def test_notes_vs_files_lists_valves_numbers_and_the_files(monkeypatch):
    from builders import errata_page
    row = {'id': '2026-05-22', 'date': '2026-05-22', 'line_counts': {'mismatch': 1}}
    ch = {'key': 'k', 'label': 'Spirit Power Steal', 'old_s': '20', 'new_s': '25'}
    ent = {'file': 'abilities.vdata', 'id': 'upgrade_spirit_snatch', 'kind': 'item', 'name': 'Spirit Snatch',
           'changes': [ch]}
    patch = {'entities': [ent], 'sections': [{'lines': [
        {'text': 'Spirit Snatch: Spirit Power Steal increased from 20 to 28', 'status': 'mismatch', 'changes': ['k']}]}]}
    from builders import archive
    monkeypatch.setattr(archive, 'load_json', lambda rel: [row] if rel == 'patches/index.json' else patch)
    archive.clear()
    try:
        got = errata_page.rows()
    finally:
        archive.clear()
    assert got[0]['valve'] == '20 → 28' and got[0]['files'] == '20 → 25' and got[0]['label'] == 'Spirit Power Steal'


def test_notes_vs_files_names_the_hero_of_a_gun(monkeypatch):
    """A gun reads "Celeste · Weapon": the row read e['owner_name'], which only the patch page's copies had."""
    from builders import errata_page
    monkeypatch.setattr(errata_page, 'hero_names', lambda: {'hero_zzz': 'Celeste'})
    e = {'file': 'abilities.vdata', 'id': 'citadel_weapon_zzz_set', 'kind': 'weapon', 'owner': 'hero_zzz'}
    row = {'patch': {'id': 'p', 'date': '2026-01-01'}, 'line': 'x', 'valve': '1 → 2', 'files': '1 → 3',
           'entity': e, 'label': 'Damage'}
    assert '<span>Celeste · Weapon</span>' in errata_page.table([row], '../')


def test_home_feed_puts_changes_on_their_pages():
    """2026-10-03, the site is about entities: the home feed shows what an update did to each hero, item and
    unit page — a hero's ability counts on the hero; '@shared', templates, helpers and unreleased work don't."""
    from builders.home_page import page_of, update_feed
    ch = lambda **kw: {'cat': 'balance', 'key': 'k', 'label': 'x', 'old_s': '1', 'new_s': '2', 'op': 'change', **kw}
    ents = [
        {'key': 'abilities.vdata:a1', 'file': 'abilities.vdata', 'id': 'a1', 'kind': 'ability', 'owner': 'hero_atlas',
         'changes': [ch(key='abilities.vdata:a1:p', status='hidden', dir='buff')]},
        {'key': 'abilities.vdata:upgrade_x', 'file': 'abilities.vdata', 'id': 'upgrade_x', 'kind': 'item',
         'changes': [ch(key='abilities.vdata:upgrade_x:p', status='documented', dir='nerf')]},
        {'key': 'npc_units.vdata:@shared', 'file': 'npc_units.vdata', 'id': '@shared', 'kind': 'unit',
         'changes': [ch(key='npc_units.vdata:@shared:p')]},
        {'key': 'npc_units.vdata:bot', 'file': 'npc_units.vdata', 'id': 'bot', 'kind': 'helper',
         'changes': [ch(key='npc_units.vdata:bot:p')]},
        {'key': 'abilities.vdata:dev', 'file': 'abilities.vdata', 'id': 'dev', 'kind': 'ability', 'owner': 'hero_new',
         'changes': [ch(key='abilities.vdata:dev:p', status='unreleased')]},
    ]
    feed = update_feed({'entities': ents})
    assert set(feed) == {'heroes', 'items'}
    assert feed['heroes']['heroes.vdata:hero_atlas']['hidden'] == 1 and feed['items']['abilities.vdata:upgrade_x']['nerf'] == 1
    assert page_of({'file': 'npc_units.vdata', 'id': 'trooper_base', 'kind': 'trooper'},
                   frozenset({'npc_units.vdata:trooper_base'})) is None


def test_entity_history_rows_marks_filters_and_lazy_blocks():
    """2026-10-03, the entity page is the history: rows are what the files changed (+ changes in the
    game's code), bug fixes / looks / unmatched lines and engine plumbing stay off; one toolbar; work on
    an unreleased hero hides behind "Before release"; a band that stays folded waits in a <template>, every
    band with the entity's own changes is open and in the page (review 2026-10-05)."""
    from builders import history_view
    r1 = {'id': 'p1', 'date': '2026-01-01', 'title': '01-01-2026 Update'}
    r2 = {'id': 'p2', 'date': '2026-02-01', 'title': '02-01-2026 Update'}
    keys = [('heroes.vdata:hero_atlas', 'Base stats', None), ('abilities.vdata:ab_charge', 'Shoulder Charge', None)]
    by_ent = {'heroes.vdata:hero_atlas': [(r2, [ch(key='c1', label='Health per boon', status='documented')]),
                                          (r1, [ch(key='c3', label='Stamina', status='unreleased')])],
              'abilities.vdata:ab_charge': [(r2, [ch(key='c2', label='T1: Move Speed', dir='buff'),
                                                  ch(key='c4', label='Particle', path='m_strParticleFile',
                                                     old_s='a.vpcf', new_s='b.vpcf', cat='balance')])]}
    by_subject = {'abrams': [(r2, {'text': 'Abrams: Can now cancel Shoulder Charge', 'status': 'code', 'subject': 'Abrams'}),
                             (r2, {'text': 'Abrams: Fixed a bug', 'status': 'fix', 'subject': 'Abrams'})]}
    areas = {'heroes.vdata:hero_atlas': 'stats', 'abilities.vdata:ab_charge': 'abil'}
    html = history_view.history_table(keys, ['Abrams'], by_ent, by_subject, '../', areas=areas)
    assert 'Can now cancel Shoulder Charge' in html and 'Fixed a bug' not in html
    assert 'Technical' not in html and 'data-ab="ab_charge" data-area="abil"' in html
    # the toolbar: tags present, the eye, parts; the newest block in the page, the older one lazy
    assert 'data-f-tag="buff"' in html and 'data-f-tag="nerf"' in html and 'data-f-area="stats"' in html
    assert 'Not in patch notes' in html and html.index('id="p-p2"') < html.index('id="p-p1"')
    assert '<template class="hp-t">' in html.split('id="p-p1"')[1] and 'template' not in html.split('id="p-p1"')[0]
    # the old patch had only work on a hero in development: hidden behind the switch
    assert 'pblock dev-only' in html and 'Before release' in html
    released = history_view.history_table(keys, ['Abrams'], by_ent, by_subject, '../', areas=areas, in_dev=True)
    assert 'dev-only' not in released and 'hblocks show-dev' in released


def test_engine_vocabulary_stays_off_the_pages_unless_the_notes_spoke():
    """2026-10-03 advisor: 452 'Behaviour' flag rows, pellet offsets, Walker's weak-point joints read as
    noise; a flag change a note line covers ("No longer interrupts sliding") stays."""
    from builders.cards import is_engine
    flags = {'cat': 'mechanic', 'label': 'Behaviour', 'status': 'hidden',
             'old_s': 'CITADEL_ABILITY_BEHAVIOR_A', 'new_s': 'CITADEL_ABILITY_BEHAVIOR_A | CITADEL_ABILITY_BEHAVIOR_B'}
    assert is_engine(flags) and not is_engine({**flags, 'status': 'described'})
    assert is_engine({'cat': 'mechanic', 'label': 'Projectile › Behaviour', 'old_s': 'PBF_StickToWorld', 'new_s': None})
    assert is_engine({'cat': 'mechanic', 'label': 'Scatter Offsets[3]', 'path': 'm_mapWeaponInfos.primary.m_vecScatterOffsets[3]',
                      'old_s': '2, 0', 'new_s': None})
    assert not is_engine({'cat': 'balance', 'label': 'Silence Duration', 'old_s': None, 'new_s': '0.3'})


def test_item_history_puts_the_enhanced_version_in_its_own_group():
    """2026-10-03: 14% of item rows read "Enhanced: …" — on the item page they are a group of their own."""
    from builders.history_view import history_table
    row = {'id': 'p1', 'date': '2026-09-29', 'title': 'City Never Sleeps · 09-29-2026'}
    key = 'abilities.vdata:upgrade_x'
    by_ent = {key: [(row, [ch(key='a', label='Bonus Health', dir='buff'), ch(key='b', label='Enhanced: Bonus Health')])]}
    html = history_table([(key, 'X', None)], ['X'], by_ent, {}, '../', enhanced=True)
    assert 'Enhanced version' in html and 'Enhanced: ' not in html
    assert 'data-f-area="base"' in html and 'data-f-area="enh"' in html
    assert html.count('class="esub') == 1                 # the item's own rows need no header


def test_values_say_no_limit_and_carry_their_unit_on_both_sides():
    """Advisor round 3, 2026-10-03: "Channel Move Speed 8m → −1", "Weapon Damage 20% →", "50 → 20m"."""
    from builders.render import vals_html
    assert 'no limit' in vals_html(ch(old_s='8m', new_s='-1', pct=None))
    assert '>—<' in vals_html(ch(old_s='20%', new_s='', pct=None))
    assert '>50m<' in vals_html(ch(old_s='50', new_s='20m'))
    assert '>-1%<' in vals_html(ch(old_s='-2%', new_s='-1%'))           # a real penalty stays a number


def test_two_fields_under_one_label_get_told_apart():
    """Advisor round 3, 2026-10-03: 104 pairs like "Healing Reduction" (receive / regen penalty)."""
    from builders.cards import disambiguate
    rows = disambiguate([{'label': 'Healing Reduction', 'path': 'm_mapAbilityProperties.HealAmpReceivePenaltyPercent.m_strValue'},
                         {'label': 'Healing Reduction', 'path': 'm_mapAbilityProperties.HealAmpRegenPenaltyPercent.m_strValue'},
                         {'label': 'Cooldown', 'path': 'm_mapAbilityProperties.AbilityCooldown.m_strValue'}])
    assert [r['label'] for r in rows] == ['Healing Reduction · receive', 'Healing Reduction · regen', 'Cooldown']


def test_a_bare_namesake_gets_a_word_too():
    """Advisor round 4: Puddle Punch's T3 "Damage −50 → −40" beside "Damage · heavy melee 50 → 40" read as
    one stat; "Spirit Power · tech" said nothing (Tech is Spirit); a scale function's switch is plumbing."""
    from builders.cards import disambiguate, is_engine
    up = 'm_vecAbilityUpgrades[2].m_vecPropertyUpgrades{%s}.m_strBonus'
    rows = disambiguate([{'label': 'T3: Damage', 'path': up % 'Damage'},
                         {'label': 'T3: Damage', 'path': up % 'DamageHeavyMelee'}])
    assert [r['label'] for r in rows] == ['T3: Damage · base', 'T3: Damage · heavy melee']
    prop = 'm_mapAbilityProperties.%s.m_strValue'
    rows = disambiguate([{'label': 'Spirit Power', 'path': prop % 'TechPower'},
                         {'label': 'Spirit Power', 'path': prop % 'BonusSpirit'}])
    assert [r['label'] for r in rows] == ['Spirit Power · base', 'Spirit Power · bonus']
    rows = disambiguate([{'label': 'Spirit Power', 'path': prop % 'TechPower', 'op': 'change', 'new_s': '0'},
                         {'label': 'Spirit Power', 'path': prop % 'SpiritPower', 'op': 'add', 'new_s': '8'}])
    assert [r['label'] for r in rows] == ['Spirit Power · old field', 'Spirit Power · new field']
    spread = 'm_mapWeaponInfos.primary.m_ShootSpreadPenaltyPerShotNormalization.%s'
    rows = disambiguate([{'label': 'Spread Normalization', 'path': spread % 'm_SpreadPerShotFactor'},
                         {'label': 'Spread Normalization', 'path': spread % 'm_FireRatePctRange'}])
    assert [r['label'] for r in rows] == ['Spread Normalization · per shot factor', 'Spread Normalization · fire rate range']
    # the same row reads alike in a patch where its namesake did not move
    from builders.history_view import history_table
    p1 = {'id': 'p1', 'date': '2026-03-21', 'title': '03-21-2026 Update'}
    p2 = {'id': 'p2', 'date': '2025-07-04', 'title': '07-04-2025 Update'}
    key = 'abilities.vdata:viscous_telepunch'
    by_ent = {key: [(p1, [ch(key='a', label='T3: Damage', path=up % 'Damage'),
                          ch(key='b', label='T3: Damage', path=up % 'DamageHeavyMelee')]),
                    (p2, [ch(key='c', label='T3: Damage', path=up % 'Damage', old_s='-35', new_s='-30')])]}
    html = history_table([(key, 'Puddle Punch', None)], ['Viscous'], by_ent, {}, '../')
    bands = html.split('id="history"')[1]            # the strip's hover-card data repeats the labels
    assert bands.count('T3: Damage · base') == 2 and bands.count('T3: Damage · heavy melee') == 1
    switch = {'cat': 'mechanic', 'label': 'Cooldown · Function Disabled', 'status': 'hidden', 'old_s': 'no', 'new_s': 'yes',
              'path': 'm_mapAbilityProperties.AbilityCooldown.m_subclassScaleFunction.m_bFunctionDisabled'}
    assert is_engine(switch)
    assert not is_engine({**switch, 'path': 'm_mapAbilityProperties.AbilityCooldown.m_subclassScaleFunction.m_flStatScale'})


def test_player_terms_and_the_strip_puts_the_newest_on_the_right():
    """Advisor round 4, 2026-10-03: one wording for the eye ("Not in patch notes"), a date instead of
    "build 6711", the count left out of the notes on a strip tile. Owner 2026-10-05: the newest patch on
    the right everywhere (the strip ran newest-left while the matrices ran newest-right)."""
    from builders.common import first_seen
    from builders.history_view import history_table
    assert first_seen([6711, '2026-09-29T21:00:00Z']) == '<div class="meta">First seen 2026-09-29</div>'
    r1 = {'id': 'p1', 'date': '2026-01-01', 'title': '01-01-2026 Update'}
    r2 = {'id': 'p2', 'date': '2026-02-01', 'title': '02-01-2026 Update'}
    key = 'abilities.vdata:upgrade_x'
    by_ent = {key: [(r1, [ch(key='a', status='documented')]), (r2, [ch(key='b'), ch(key='c', label='Range')])]}
    html = history_table([(key, 'X', None)], ['X'], by_ent, {}, '../')
    strip = html.split('class="patch-strip"')[1].split('</div>')[0]
    assert strip.index('#p-p1') < strip.index('#p-p2')
    assert '2 changes, 2 not in patch notes' in strip and 'all 2 not in notes' in html


def test_an_entity_page_puts_its_strip_under_the_head():
    """Review 2026-10-05: History started 1365-2096 px down a hero page (Sloppy's first band: y=312); the strip
    is the row under the head on hero, item and unit pages, its data blob with it."""
    from builders.history_view import head_strip, history_table
    r1 = {'id': 'p1', 'date': '2026-01-01', 'title': '01-01-2026 Update'}
    r2 = {'id': 'p2', 'date': '2026-02-01', 'title': '02-01-2026 Update'}
    key = 'abilities.vdata:upgrade_x'
    by_ent = {key: [(r1, [ch(key='a', status='documented')]), (r2, [ch(key='b')])]}
    told: dict = {}
    html = history_table([(key, 'X', None)], ['X'], by_ent, {}, '../', facts_out=told)
    assert 'patch-strip' not in html and 'strip-data' not in html
    row = head_strip(told)
    assert row.startswith('<div class="head-strip">') and 'patch-strip' in row and 'strip-data' in row
    assert 'patch-strip' in history_table([(key, 'X', None)], ['X'], by_ent, {}, '../')    # a Game page keeps it


def test_a_bands_patch_link_lands_on_the_entity(monkeypatch):
    """Review 2026-10-05: "patch ↗" opened the top of the patch page (Sloppy lands on the hero's block): it goes to
    what the notes said about the entity (#n-) when they name it, else to its card under All changes (#c-)."""
    from builders import archive
    from builders.history_view import history_table, patch_href
    monkeypatch.setattr(archive, 'note_anchors', lambda pid: frozenset({'upgrade_x'}) if pid == 'p2' else frozenset())
    assert patch_href('p2', '../', 'upgrade_x') == '../patches/p2.html#n-upgrade_x'
    assert patch_href('p1', '../', 'upgrade_x') == '../patches/p1.html#c-upgrade_x'
    assert patch_href('p1', '../') == '../patches/p1.html'
    r1 = {'id': 'p1', 'date': '2026-01-01', 'title': '01-01-2026 Update'}
    key = 'abilities.vdata:upgrade_x'
    html = history_table([(key, 'X', None)], ['X'], {key: [(r1, [ch(key='a')])]}, {}, '../')
    assert 'href="../patches/p1.html#c-upgrade_x"' in html
    game = history_table([('game:urn', 'Urn', None), (key, 'X', None)], ['Urn'], {key: [(r1, [ch(key='a')])]}, {}, '../')
    assert 'href="../patches/p1.html"' in game                         # a Game system: the page itself


def test_valves_words_sit_under_the_rows_they_cover(monkeypatch):
    """Review 2026-10-05: a described row looked like any other — Valve's line is a quiet note under the ability's
    rows; a line about many entities ("Spirit Power scaling globally reduced by -7%") is said once per band;
    a documented row gets none (its line repeats "label old → new"). A change that shipped in a later build of
    the window says so on its eye."""
    from builders import archive
    from builders.history_view import history_table
    idx = {'abilities.vdata:a:x': (0, 1), 'abilities.vdata:a:y': (2,), 'abilities.vdata:a:z': (3,)}
    lines = (('Alpha: Wake Up delay no longer increases with spirit scaling', 'described', 1),
             ('Spirit Power scaling globally reduced by -7%', 'described', 40),
             ('Alpha: Range increased from 10m to 12m', 'documented', 1),
             ('Alpha: Wake Up delay no longer increases with spirit scaling', 'described', 1))
    monkeypatch.setattr(archive, 'note_lines', lambda pid: (idx, lines))
    monkeypatch.setattr(archive, 'builds_of', lambda pid: [{'build': 100, 'date': '2026-03-06T00:00:00Z'},
                                                           {'build': 104, 'date': '2026-03-09T00:00:00Z'}])
    r1 = {'id': 'p1', 'date': '2026-03-06', 'title': '03-06-2026 Update'}
    rows = [ch(key='abilities.vdata:a:x', path='x', label='Wake Up Delay', status='described'),
            ch(key='abilities.vdata:a:y', path='y', label='Range', status='documented'),
            ch(key='abilities.vdata:a:z', path='z', label='Radius', status='described'),
            ch(key='abilities.vdata:a:w', path='w', label='Width', status='hidden', builds=[104])]
    keys = [('heroes.vdata:h', 'Base stats', None), ('abilities.vdata:a', 'Alpha', None)]
    html = history_table(keys, ['Hero'], {'abilities.vdata:a': [(r1, rows)]}, {}, '../')
    notes = re.findall(r'class="vnote"><span class="vn-l">Patch notes</span>([^<]*)', html)
    assert notes == ['Spirit Power scaling globally reduced by -7%', 'Wake Up delay no longer increases with spirit scaling']
    assert html.index('class="vnotes"') < html.index('class="hgroup')          # the band's line first
    assert 'shipped silently 2026-03-09, build 104' in html


def test_an_update_with_notes_lists_what_they_left_out():
    """Review 2026-10-05: the "From the files" tab of an update with notes repeated All changes (833 / 833) and said
    "Valve published no numbers" for City Never Sleeps: it lists only the rows not in the notes, said truly."""
    from builders.patches_pages import _generated_notes, _key_changes
    item = {'file': 'abilities.vdata', 'id': 'upgrade_x', 'kind': 'item', 'name': 'Extra', 'owner': None,
            'changes': [ch(key='abilities.vdata:upgrade_x:a', label='Range', status='documented'),
                        ch(key='abilities.vdata:upgrade_x:b', label='Radius', status='hidden')]}
    html = _generated_notes({'entities': [item]}, only_hidden=True)
    assert 'Radius' in html and 'Range' not in html and 'no patch notes' not in html
    assert 'Range' in _generated_notes({'entities': [item]}) and 'no patch notes' in _generated_notes({'entities': [item]})
    key = [{'entity': 'abilities.vdata:upgrade_x', 'name': 'Extra', 'kind': 'item', 'change': c} for c in item['changes']]
    shown = _key_changes({'key_changes': key}, '../', only_hidden=True)
    assert 'Radius' in shown and 'Range' not in shown


def test_a_patch_pages_item_and_unit_cards_carry_anchors():
    """The item's / unit's card under All changes is where its page's "patch ↗" lands (#c-<id>)."""
    from builders.patches_pages import _changes_table
    item = {'file': 'abilities.vdata', 'id': 'upgrade_x', 'kind': 'item', 'name': 'X', 'owner': None,
            'changes': [ch(key='abilities.vdata:upgrade_x:a', file='abilities.vdata')]}
    html = _changes_table([item, {**item}], '../', 'p1')
    assert html.count('id="c-upgrade_x"') == 1


def test_one_hidden_change_is_never_all_of_one():
    """Review 2026-10-05: "ALL 1 NOT IN NOTES"; an all-hidden band keeps ONE eye, on its banner (advisor round 2,
    confirmed by the review: its rows keep the stripe)."""
    from builders.history_view import history_table
    r1 = {'id': 'p1', 'date': '2026-01-01', 'title': '01-01-2026 Update'}
    key = 'abilities.vdata:upgrade_x'
    html = history_table([(key, 'X', None)], ['X'], {key: [(r1, [ch(key='a')])]}, {}, '../')
    assert '>1 not in notes<' in html and 'all 1 not in' not in html
    from pathlib import Path
    css = (Path(__file__).resolve().parent.parent / 'site' / 'styles.css').read_text(encoding='utf-8')
    assert '.pblock.all-hidden .erow .st .mark { visibility: hidden; }' in css


def test_the_strip_never_scrolls():
    """Owner 2026-10-05 (screenshot: a scrollbar under the strip): tiles shrink to fit, a phone keeps the
    newest; no horizontal scrolling on the row."""
    import re
    from pathlib import Path
    css = Path(__file__).resolve().parent.parent.joinpath('site', 'styles.css').read_text(encoding='utf-8')
    rule = re.search(r'\.patch-strip \{[^}]*\}', css).group(0)
    assert 'overflow: hidden' in rule and 'overflow-x: auto' not in rule
    assert re.search(r'\.ps-tile \{[^}]*flex: 0 1 30px[^}]*min-width', css)
    assert '.ps-tile:nth-last-child(n+16) { display: none; }' in css


def test_current_fold_is_open_and_events_carry_no_value():
    """Advisor round 4: Slum Shroom's page was one "Added to the game files · —" row under a closed
    "Current stats"; owner 2026-10-04: nothing folded by default, whatever the history's length."""
    from builders.history_view import now_fold
    from builders.render import vals_html
    assert '<details class="now px-frame" open>' in now_fold('Current stats', '<table></table>')
    assert now_fold('Current stats', '') == ''
    assert vals_html({'op': 'add', 'path': '@add', 'cat': 'balance', 'label': 'Added to the game files'}) == ''


def test_site_search_lists_heroes_abilities_items_and_units():
    """Advisor round 4: no way to jump to "what changed on X" from the home page."""
    from builders.site_search import search_rows
    hero = {'file': 'heroes.vdata', 'id': 'hero_atlas', 'name': 'Abrams', 'alive': True}
    item = {'file': 'abilities.vdata', 'id': 'upgrade_x', 'name': 'Extra Charge', 'alive': False, 'kind': 'item'}
    unit = {'file': 'npc_units.vdata', 'id': 'npc_boss_tier2', 'kind': 'guardian', 'alive': True}
    cards = {'ab_charge': {'id': 'ab_charge', 'owner': 'hero_atlas', 'name': 'Shoulder Charge', 'slot': 'Signature_1'}}
    rows = search_rows([hero], [item], [('Walker', unit)], cards, lambda c, hid: list(c.values()))
    by_name = {r[0]: r for r in rows}
    assert by_name['Shoulder Charge'][1].endswith('#ab-ab_charge') and by_name['Shoulder Charge'][2] == 'Abrams · ability'
    assert by_name['Extra Charge'][2] == 'Item · removed' and by_name['Walker'][2] == 'Unit'


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
                        group_cls={'Vitality': 'stc', 'Stats': 'sumc'}, center=True)
    # one band row per category, spanning the table; the box centred on the page
    assert html.count('<tr class="sec"') == 2 and '<tr class="sec" data-cat="s">' in html
    assert 'class="sec-fill"' in html and 'class="table-fade center"' in html
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
    from pathlib import Path
    from builders.tables_pages import _toolbar
    bar = _toolbar('Item…', heat_on=True)
    assert 'class="toolbar tbl-bar"' in bar and 'data-heatmap checked' in bar
    assert '<span class="lg-tail"> · hover a value for its history</span>' in bar
    assert 'data-heatmap checked' not in _toolbar('Hero…')
    css = (Path(__file__).resolve().parent.parent / 'site' / 'styles.css').read_text(encoding='utf-8')
    assert '.toolbar.tbl-bar, .toolbar.dyn-bar { position: static; }' in css
    assert '.chip.legend-hist { white-space: normal; max-width: 100%; }' in css
    # a unit without art: the glyph gets the icon's fixed box (Shrine's grew to a 300x210 picture)
    assert 'table.stats td.name img, table.stats td.name .glyph { flex: none; width: 22px; height: 22px;' in css


def test_stylesheet_colours_live_in_root_only():
    """AGENTS.md: every colour is a :root token; no hex / rgba literal in the rules."""
    from pathlib import Path
    css = (Path(__file__).resolve().parent.parent / 'site' / 'styles.css').read_text(encoding='utf-8')
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    rest = css[css.index('}', css.index(':root {')) + 1:]
    assert [m.group(0) for m in re.finditer(r':[^;{}]*(#[0-9a-fA-F]{3,8}\b|rgba?\()', rest)] == []
