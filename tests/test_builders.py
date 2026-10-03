"""Rendering helpers: tags, order, escaping."""
import re

from builders.hero_page import _strip_subject
from builders.render import change_li, entity_rows, fold_tier_swaps, sort_changes, tag_of


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


def test_units_sharing_a_name_get_their_variant():
    from builders.entities_pages import unit_variants
    walkers = [{'id': i, 'name': 'Walker', 'alive': True}
               for i in ('alt_npc_boss_tier2', 'alt_npc_boss_tier2_weak', 'npc_boss_tier2', 'npc_boss_tier2_weak')]
    barrels = [{'id': 'neutral_barrel_01_weak', 'name': 'Barrel Mimic I', 'alive': True},
               {'id': 'neutral_barrel_02_weak', 'name': 'Barrel Mimic I', 'alive': True}]
    v = unit_variants(walkers + barrels + [{'id': 'npc_trooper', 'name': 'Trooper', 'alive': True}])
    assert [v[w['id']] for w in walkers] == ['alt', 'alt weak', '', 'weak']
    assert [v[b['id']] for b in barrels] == ['model 1', 'model 2']
    assert 'npc_trooper' not in v                    # a unique name needs nothing


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
    html = ''.join(entity_rows('Seismic Impact', None, [ch(label='a'), ch(label='b', dir='buff'), ch(label='c')]))
    assert html.count('Seismic Impact') == 1
    assert re.search(r'class="pip nerf"><svg[^>]*>.*?</svg>2<', html) and re.search(r'class="pip buff"><svg[^>]*>.*?</svg>1<', html)
    assert 'eh has-hidden' in html


def test_unreleased_rows_marked_and_kept_in_hidden_view():
    html = ''.join(entity_rows('Test', None, [ch(status='unreleased')]))
    assert 'mark unreleased' in html and ' dev' in html and 'has-hidden' in html


def test_change_li_escapes_and_marks_hidden():
    html = change_li(ch(label='<b>x</b>'))
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
    html = visual(None, 'map')
    assert 'glyph g-map' in html and '<svg' in html and 'noimg' not in html


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
    assert _strip_subject('Abrams: Melee damage per boon increased by 10%', ['Abrams']) == \
        'Melee damage per boon increased by 10%'
    # another subject stays: the line is about the ability, not the hero
    assert _strip_subject('Seismic Impact: Damage increased', ['Abrams']) == 'Seismic Impact: Damage increased'


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


def test_top_pips_keeps_two_biggest_counters():
    from builders.render import top_pips
    html = top_pips([ch(dir='buff')] * 3 + [ch(dir='nerf')] * 2 + [ch(op='add', dir='changed')], 2)
    assert re.search(r'pip buff"><svg.*?</svg>3<', html) and re.search(r'pip nerf"><svg.*?</svg>2<', html)
    assert 'pip new' not in html


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


def test_hero_last_skips_engine_only_patches(monkeypatch):
    from builders import trail
    patches = {
        'patches/index.json': [{'id': 'p1', 'date': '2026-09-16'}, {'id': 'p2', 'date': '2026-09-29'}],
        'patches/p1.json.gz': {'entities': [{'file': 'abilities.vdata', 'id': 'a', 'owner': 'hero_atlas',
                                             'changes': [ch(key='abilities.vdata:a:x', dir='buff')]}]},
        'patches/p2.json.gz': {'entities': [{'file': 'heroes.vdata', 'id': 'hero_atlas', 'changes': [
            ch(key='heroes.vdata:hero_atlas:m_x', label='Roster Background Layout', old_s='A', new_s='B')]}]},
    }
    monkeypatch.setattr(trail, 'load_json', lambda name: patches[name])
    trail._hero_changes.cache_clear()
    row, changes = trail.hero_last('hero_atlas')
    assert row['id'] == 'p1' and len(changes) == 1
    trail._hero_changes.cache_clear()


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
    from builders.pixel_icons import GRID, TAG_ART, art_path, tag_svg
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
    assert tag_svg('buff').startswith('<svg class="ti"') and tag_svg('nope') == ''


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
    assert 'show-old' in bar and 'bvn' in bar and 'hide-buff' in bar and 'show-extra' in bar
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


def test_no_limit_reads_as_infinity():
    from builders.cards import is_noop
    from builders.render import shown_value
    assert shown_value('9999') == '∞' and shown_value('99999') == '∞' and shown_value('9999m') == '∞'
    assert shown_value('999') == '999'
    # the two spellings of "no limit" are one value
    assert is_noop({'op': 'change', 'old_s': '9999', 'new_s': '99999'})


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
    monkeypatch.setattr(errata_page, 'load_json', lambda rel: [row] if rel == 'patches/index.json' else patch)
    got = errata_page.rows()
    assert got[0]['valve'] == '20 → 28' and got[0]['files'] == '20 → 25' and got[0]['label'] == 'Spirit Power Steal'


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
