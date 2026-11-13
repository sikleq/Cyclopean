"""The other builders: notes, patch, build, home, shop and search pages, names and icons."""
import re

from tests.helpers import ch, site_css, site_js


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
    # words a reader reads as labels (review 2026-10-05: "weak · alt weak"); 'ag2' is the new model; the family's name
    # leads (a Guardian group titled just "Alt", visual pass 2026-10-17 round 2)
    assert [member_label(m, w) for m in w] == ['Walker', 'Walker (Weak)', 'Walker (Alt)', 'Walker (Alt Weak)']
    medics = [{'id': i, 'name': 'Medic Trooper', 'alive': True} for i in ('trooper_medic', 'trooper_medic_ag2')]
    assert member_label(medics[1], medics) == 'Medic Trooper (New model)'
    b = fams['Barrel Mimic']
    # a tiered family's variants differ in looks only: the tier names the group (round 3)
    assert member_label(b[0], b) == 'Tier I' and member_label(b[-1], b) == 'Tier III'
    assert merged_label(['Tier I · model 1', 'Tier I · model 2']) == 'Tier I'
    assert merged_label(['Tier I · model 1', 'Tier II · model 1']) == 'All tiers'
    assert merged_label(['Walker', 'weak', 'alt', 'alt weak'], 4) == 'All variants'
    assert merged_label(['Walker', 'alt'], 4) == 'Walker · alt'


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


def test_notes_name_without_leading_the(monkeypatch):
    from builders import notes_view
    monkeypatch.setattr(notes_view, '_catalog', lambda: [
        {'file': 'heroes.vdata', 'id': 'hero_doorman', 'name': 'The Doorman', 'kind': 'hero', 'alive': True}])
    notes_view._by_name.cache_clear()
    assert notes_view._by_name()['doorman']['id'] == 'hero_doorman'
    notes_view._by_name.cache_clear()


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
    assert 'Street Brawl legendaries' in html and 'gcard p-v4' in html
    # a gone item the game never drew is one it never released: its own shelf, the "?" for art (owner 2026-10-21, q12)
    assert 'Never released' in html and 'Removed or disabled' not in html
    assert '<span class="gc-ic"><span class="glyph g-unknown"></span></span><span class="gc-nm">Old</span>' in html
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


def test_an_unnamed_ability_in_a_value_reads_like_its_group_header(monkeypatch):
    """Review 2026-10-05: "Kit: Ability 1  Boho bouncyprojectile → …" while the group header read "Bouncyprojectile"."""
    from builders import common
    monkeypatch.setattr(common, 'names_by_id', lambda: {})
    monkeypatch.setattr(common, '_catalog_owners', lambda: {'ability_boho_bouncyprojectile': 'hero_boho'})
    monkeypatch.setattr(common, '_game_entry_names', lambda: {})
    assert common.ids_to_names('ability_boho_bouncyprojectile') == 'Bouncyprojectile'


def test_calendar_shades_and_gaps():
    from builders.calendar_page import _gaps, _shade
    assert [_shade(n) for n in (0, 1, 3, 6, 10)] == [0, 1, 2, 3, 4]
    ps = [{'date': '2026-01-01', 'title': 'a'}, {'date': '2026-01-11', 'title': 'b'}, {'date': '2026-01-13', 'title': 'c'}]
    assert [g[0] for g in _gaps(ps)] == [10, 2]


def test_key_bindings_in_text_read_as_keys():
    from builders.patches_pages import _plain
    assert _plain("Press {g:citadel_binding:'Attack'} to fire") == 'Press [Attack] to fire'
    # a binding with a form word ("1st") was printed raw on 12 build pages
    assert _plain("{g:citadel_binding:1st:'Spectator.SpecNext'}Target") == '[Spec Next] Target'


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


def test_an_update_with_notes_lists_what_they_left_out():
    """Review 2026-10-05: the "From the files" tab of an update with notes repeated All changes (833 / 833) and said
    "Valve published no numbers" for City Never Sleeps: it lists only the rows not in the notes, said truly."""
    from builders.patches_pages import _generated_notes, _key_changes
    item = {'key': 'abilities.vdata:upgrade_x', 'file': 'abilities.vdata', 'id': 'upgrade_x', 'kind': 'item',
            'name': 'Extra', 'owner': None,
            'changes': [ch(key='abilities.vdata:upgrade_x:a', label='Range', status='documented'),
                        ch(key='abilities.vdata:upgrade_x:b', label='Radius', status='hidden')]}
    pages = frozenset({'abilities.vdata:upgrade_x'})
    html = _generated_notes({'entities': [item]}, only_hidden=True, pages=pages)
    assert 'Radius' in html and 'Range' not in html and 'no patch notes' not in html
    every = _generated_notes({'entities': [item]}, pages=pages)
    assert 'Range' in every and 'no patch notes' in every
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


def test_a_shared_edits_card_is_the_place_of_its_targets(monkeypatch):
    """Review 2026-10-05: Holliday's "Air Dash Duration" sat in one card for six heroes with no anchor of hers; her
    band's "patch ↗" opened the patch at its top. A shared card holds the anchor of each target without a card of its
    own (a hero's ability by its hero), and archive.change_anchors lists them."""
    from builders import shared_rows
    from builders.patches_pages import _changes_table, change_anchors
    cat = {'abilities.vdata:dash': {'file': 'abilities.vdata', 'id': 'dash', 'owner': 'hero_astro'},
           'abilities.vdata:upgrade_x': {'file': 'abilities.vdata', 'id': 'upgrade_x'},
           'npc_units.vdata:bot_weak': {'file': 'npc_units.vdata', 'id': 'bot_weak'}}
    monkeypatch.setattr(shared_rows, 'catalog', lambda: cat)
    block = {'key': '@shared:abilities.vdata:3:x', 'file': 'abilities.vdata', 'id': '@shared', 'kind': 'shared',
             'name': '3 entries', 'target_keys': list(cat), 'targets': ['a', 'b', 'c'],
             'changes': [ch(key='abilities.vdata:dash:d', label='Air Dash Duration', file='abilities.vdata')]}
    item = {'file': 'abilities.vdata', 'id': 'upgrade_x', 'kind': 'item', 'name': 'X', 'owner': None,
            'changes': [ch(key='abilities.vdata:upgrade_x:a', file='abilities.vdata')]}
    html = _changes_table([block, item], '../', 'p1')
    for i in ('dash', 'hero_astro', 'bot_weak', 'upgrade_x'):
        assert html.count(f'id="c-{i}"') == 1, i                 # the item keeps its own card's anchor
    assert re.search(r'<article class="ecard[^"]*" id="c-upgrade_x"', html)
    assert change_anchors([block, item]) == {'dash', 'hero_astro', 'bot_weak', 'upgrade_x'}


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


def test_stylesheet_colours_live_in_root_only():
    """AGENTS.md: every colour is a :root token; no hex / rgba literal in the rules."""
    css = site_css()
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    rest = css[css.index('}', css.index(':root {')) + 1:]
    assert [m.group(0) for m in re.finditer(r':[^;{}]*(#[0-9a-fA-F]{3,8}\b|rgba?\()', rest)] == []


def test_biggest_changes_stack_on_a_phone():
    """2026-10-06: a patch's "Biggest changes" was 235px wider than a 390px phone, its values off to the right. The
    table carries its own class and its rows become two-line grids under 700px."""
    import re as _re
    from pathlib import Path
    src = Path(__file__).resolve().parent.parent
    assert 'class="hist big px-frame"' in (src / 'builders' / 'patches_pages.py').read_text(encoding='utf-8')
    css = site_css()
    block = css[css.index('table.hist.big { overflow-x: visible; }') - 200:]
    assert '@media (max-width: 700px)' in block[:400]
    assert _re.search(r'table\.hist\.big tr\.ch \{ display: grid;', css)


def test_note_cards_and_matrix_icons_load_after_the_page():
    """2026-10-06: icons arriving mid-scroll re-balanced the note cards' CSS columns (patches/2024-10-10: 14 layouts,
    1.4 s, p95 83 ms) as they had cost the matrices a re-layering; both load at `load`. A banner's chips wrap
    (Astro's ran 67px past a 1440px window)."""
    js = site_js()
    assert """'table.dyn td.name img[loading="lazy"], .ecards img[loading="lazy"]'""" in js
    css = site_css()
    banner = css[css.index('.banner {'):css.index('}', css.index('.banner {'))]
    assert 'flex-wrap: wrap' in banner
    bc = css[css.index('.banner .bc {'):css.index('}', css.index('.banner .bc {'))]
    assert 'flex-wrap: wrap' in bc and 'min-width: 0' in bc


def test_the_build_picker_lists_every_build_newest_first():
    from builders.builds_pages import pick_list
    rows = [{'file': 'a', 'date': '2026-11-05T21:49:42Z'}, {'file': 'b', 'date': '2026-11-11T21:38:45Z'}]
    got = pick_list(rows, {'a': '6858', 'b': '6861'}, {'b': {'title': 'Ranked - Beta Season 2', 'date': '2026-11-05'}})
    assert [r[0] for r in got] == ['6861', '6858']
    assert got[0][1] == '6861, 2026-11-11: Ranked - Beta Season 2' and got[1][1] == '6858, 2026-11-05'
