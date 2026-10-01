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
    html = shop_page.shop_html(items, cards, '../')
    # the game's column order and one row per tier with its price
    assert html.index('cat-h w') < html.index('cat-h s') < html.index('cat-h v')
    assert 'shop-row t1' in html and 'shop-row t4' in html and '800' in html
    assert 'data-comp="upgrade_basic"' in html and 'data-up="upgrade_sharp"' in html
    assert 'it-act' in html and 'it-imb' in html
    assert 'Street Brawl legendaries' in html and 'Removed or disabled' in html


def test_heroes_grid_sorts_like_the_game():
    from builders.heroes_grid import heroes_grid_html
    live = [{'file': 'heroes.vdata', 'id': 'hero_doorman', 'name': 'The Doorman'},
            {'file': 'heroes.vdata', 'id': 'hero_viscous', 'name': 'Viscous'},
            {'file': 'heroes.vdata', 'id': 'hero_atlas', 'name': 'Abrams', 'state': 'EHeroDevState_PreRelease'}]
    rows = {'hero_doorman': {'sort_name': 'Doorman', 'type': 'ECitadelHeroType_Mystic', 'complexity': 1,
                             'color': [237, 149, 60]},
            'hero_viscous': {'new_player': True}}
    html = heroes_grid_html(live, [], rows, '../', lambda hid: '')
    assert html.index('Abrams') < html.index('The Doorman') < html.index('Viscous')
    # one grid (no "Great for new players" row: the owner asked), the game's colour on the plate
    assert 'Great for new players' not in html and '>Mystic<' in html and 'Pre-release' in html
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
