"""A hero's page (builders/hero_page.py): the weapon panel, the ability cards, the alt fire."""
import re


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


def test_gun_numbers_carry_their_units_on_the_number():
    from builders import hero_page
    cols = [{'key': k, 'label': lbl, 'group': 'Damage', 'digits': 2, 'pol': 1}
            for k, lbl in [('dps', 'DPS'), ('dps_max', 'Max DPS'), ('bullet_dmg', 'Bullet DMG'), ('bps', 'Bullets / s'),
                           ('clip', 'Ammo'), ('reload', 'Reload (s)'), ('bullet_speed', 'Bullet Speed (m/s)')]]
    row = {'values': {c['key']: 1.5 for c in cols}, 'history': {}, 'spirit_scaled': []}
    html = hero_page.more_stats(row, cols, 'Abrams', '../')        # a hero without the game's panels
    # review 2026-10-05: every unit rides on its number ("RELOAD S" beside "Full Reload 3.88 s")
    assert '>Reload<' in html and '<span class="u">s</span>' in html
    assert '<span class="u">m/s</span>' in html and '>Bullet Speed<' in html


def test_a_borrowed_stand_in_gun_is_no_gun(monkeypatch):
    """Review 2026-10-05: five heroes in development showed Infernus' Incendiary Remarks as their weapon, with its last
    change linking to a band their page does not have and a "History" link to nothing."""
    from builders import hero_page
    ents = {'citadel_weapon_inferno_set': {'id': 'citadel_weapon_inferno_set', 'owner': 'hero_inferno'},
            'citadel_weapon_nurse': {'id': 'citadel_weapon_nurse', 'owner': 'hero_nurse'}}
    assert hero_page.borrowed_gun('hero_nurse', 'citadel_weapon_inferno_set', ents)
    assert not hero_page.borrowed_gun('hero_inferno', 'citadel_weapon_inferno_set', ents)
    assert not hero_page.borrowed_gun('hero_nurse', 'citadel_weapon_nurse', ents)
    assert not hero_page.borrowed_gun('hero_nurse', None, ents)
    html = hero_page.weapon_block(None, None, [], 'Nurse', '../')
    assert 'No gun of its own yet' in html and 'ac-hist' not in html and 'ac-last' not in html


def test_the_alt_fire_shows_its_numbers_under_its_line(monkeypatch):
    """Review 2026-10-05: the weapon block had only a slim "Alt fire" line. Its numbers (Hero Stats' `alt`) are a
    compact row of cells under it, each with its history on hover; a default (1 pellet, 1 ammo a shot) says nothing;
    no row for an alt fire Hero Stats does not describe."""
    from builders import hero_page
    alt_cols = {k: {'key': k, 'label': lbl, 'group': 'Damage', 'digits': d, 'pol': p} for k, lbl, d, p in [
        ('dps', 'DPS', 1, 1), ('bullet_dmg', 'Bullet DMG', 2, 1), ('pellets', 'Pellets', 0, 1),
        ('bps', 'Bullets / s', 2, 1), ('clip', 'Ammo', 0, 1), ('ammo_shot', 'Ammo / Shot', 0, -1),
        ('reload', 'Reload (s)', 2, -1), ('bullet_speed', 'Bullet Speed (m/s)', 0, 1), ('range', 'Max Range (m)', 1, 1)]}
    monkeypatch.setattr(hero_page, '_alt_columns', lambda: alt_cols)
    row = {'values': {'dps': 50}, 'history': {}, 'spirit_scaled': [],
           'alt': {'weapon': 'gun_alt', 'values': {'dps': 33.3333, 'bullet_dmg': 42.0, 'pellets': 1.0, 'bps': 0.7937,
                                                   'clip': 10.0, 'ammo_shot': 5.0, 'reload': 2.1, 'bullet_speed': 38.1001,
                                                   'range': 25.4001},
                   # the old five-pellet alt fire's steps do not make "Pellets 1" news
                   'history': {'bullet_dmg': [[5920, '2025-10-02', 48.0, 42.0]],
                               'pellets': [[5017, '2024-08-01', 5.0, None], [5100, '2024-08-30', None, 1.0]]}}}
    cols = [{'key': 'dps', 'label': 'DPS', 'group': 'Damage', 'digits': 1, 'pol': 1}]
    html = hero_page.weapon_block({'name': 'Gun', 'id': 'gun'}, row, cols, 'Viscous', '../', {'id': 'gun_alt'})
    cells = html[html.index('wb-alt-cells'):]
    text = re.sub(r'<[^>]+>', ' ', cells)
    assert re.search(r'42\s+Bullet dmg', text) and re.search(r'5\s+Ammo/shot', text) and re.search(r'38\s+m/s', text)
    assert 'Pellets' not in text and cells.count('class="wcell') == 8
    assert 'data-title="Viscous · Alt fire · Bullet DMG"' in cells
    # another alt fire than the one Hero Stats describes: the line alone
    other = hero_page.weapon_block({'name': 'Gun', 'id': 'gun'}, row, cols, 'Viscous', '../', {'id': 'other_alt'})
    assert 'wb-alt-cells' not in other and 'Alt fire' in other


def test_a_stat_at_its_default_says_nothing_unless_it_moved():
    """Review 2026-10-05: "+Range / boon 0m" on 38 of 39 heroes, "Burst Interval 0s" on 32, "Pellets 1",
    "Headshot Taken × 1"; hidden unless the value ever really changed (Mirage's pellets, Bookworm's burst)."""
    from builders import hero_page
    cols = [{'key': k, 'label': lbl, 'group': 'Damage', 'digits': 2, 'pol': 1} for k, lbl in [
        ('dps', 'DPS'), ('range_lvl', '+Range / boon (m)'), ('pellets', 'Pellets'), ('pellet_spread', 'Pellet Spread'),
        ('burst', 'Burst'), ('burst_cycle', 'Burst Interval (s)'), ('gravity', 'Bullet Gravity')]]
    row = {'values': {'dps': 50, 'range_lvl': 0, 'pellets': 1, 'pellet_spread': 0, 'burst': 1, 'burst_cycle': 0,
                      'gravity': 0}, 'history': {'burst': [[1, '2025-01-01', 3, 1]], 'range_lvl': [[1, '2025-01-01', None, 0]]},
           'spirit_scaled': []}
    html = hero_page.more_stats(row, cols, 'X', '../')
    assert '+Range' not in html and 'Pellet' not in html and 'Burst Interval' not in html
    assert '>Burst<' in html                     # it went 3 -> 1: a real step keeps it
    assert 'Bullet Gravity' in html              # a real property: its zero means something


def test_hero_page_cards_only_what_the_hero_binds_now():
    """2026-10-03: Calico's page showed Catform pounce, Nekomata Ward and five more abilities she no
    longer binds; Infernus's showed the shared Jump / Mantle / Zipline."""
    from builders.hero_page import current_cards
    cards = {i: {'id': i, 'owner': o, 'slot': s} for i, o, s in [
        ('ult', 'hero_nano', 'Signature_4'), ('gun', 'hero_nano', 'Weapon_Primary'),
        ('a1', 'hero_nano', 'Signature_1'), ('catform_pounce', 'hero_nano', ''),
        ('ritual', 'hero_nano', None), ('jump', 'hero_nano', 'Ability_Jump'), ('x', 'hero_atlas', 'Signature_1')]}
    assert [c['id'] for c in current_cards(cards, 'hero_nano')] == ['gun', 'a1', 'ult']
