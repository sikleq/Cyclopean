"""The Game section (coverage audit 2026-10-05, part 2): everything that is not one hero, item or unit — the Soul Urn,
crates, powerups, souls, respawn, the level curve, console variables — on pages of its own, the archive's console
variables whole, ability / item / hero name and description changes on their pages, and a check that every gameplay
row of data/patches lands on a page."""
import re

import pytest


def ch(**kw):
    base = {'op': 'change', 'cat': 'balance', 'label': 'Cooldown', 'old_s': '27', 'new_s': '29', 'dir': 'nerf',
            'pct': 7.4, 'grad': 2, 'status': 'hidden', 'path': 'x', 'key': 'k:x'}
    base.update(kw)
    return base


ROW = {'id': '2026-06-04', 'date': '2026-06-04', 'title': 'Minor Update - 06-04-2026'}


# ---- where an entry goes ---------------------------------------------------------------------------------------

@pytest.mark.parametrize('subject, where', [
    ('misc.vdata:citadel_idol_cashin#global', ('urn', 'urn')),
    ('abilities.vdata:ability_golden_idol#ability_other', ('urn', 'urn')),
    ('misc.vdata:xp_orb_idol_dropoff#global', ('urn', 'urn')),          # the Urn's souls before every soul orb
    ('misc.vdata:citadel_koth_cashin#global', ('urn', 'rift')),
    ('misc.vdata:xp_orb_trooper#global', ('souls', 'orbs')),
    ('generic_data.vdata:m_flLanePhaseGoldShareFrac#global', ('souls', 'share')),
    ('generic_data.vdata:m_ObjectiveParams#global', ('souls', 'objectives')),
    ('misc.vdata:citadel_breakable_item_container#global', ('breakables', 'crates')),
    ('misc.vdata:gun_powerup_pickup#global', ('pickups', 'powerups')),
    ('misc.vdata:wp_permanent_pickup_lv2#global', ('pickups', 'buffs')),
    ('generic_data.vdata:m_RejuvParams#global', ('pickups', 'rejuv')),
    ('heroes.vdata:@all:m_mapLevelInfo.10.m_bUseStandardUpgrade', ('progression', 'levels')),
    ('heroes.vdata:@all:m_MapModCostBonuses.EItemSlotType_Armor{16000}.flBonus', ('progression', 'invest')),
    ('heroes.vdata:hero_base#hero', ('progression', 'every')),
    ('abilities.vdata:@all:m_nUpgradeSlotCost', ('shop', 'prices')),
    ('abilities.vdata:@all:m_mapAttacks.EAttackType_Heavy.m_flAttackEventTime', ('combat', 'melee')),
    ('abilities.vdata:citadel_ability_dash#shared', ('combat', 'moves')),
    ('modifiers.vdata:modifier_citadel_catapult_damage_watcher#modifier', ('combat', 'rules')),
    ('npc_units.vdata:trooper_base#trooper', ('troopers', 'troopers')),
    ('npc_units.vdata:neutral_base#neutral', ('camps', 'camps')),
    ('generic_data.vdata:m_StreetBrawl#global', ('modes', 'brawl')),
    ('convar:citadel_player_spawn_time_max_ramp_1', ('respawn', 'respawn')),
    ('convar:citadel_crate_reward_base', ('breakables', 'crates')),        # a crate's reward is the crate's
    ('convar:citadel_koth_warning_time', ('urn', 'rift')),
    ('convar:citadel_trooper_gold_reward', ('souls', 'rewards')),
    ('convar:citadel_tick_gold_period_duration_s', ('souls', 'rewards')),
    ('misc.vdata:something_new#global', ('other', 'objects')),           # nothing is lost
])
def test_every_subject_has_a_system(subject, where):
    from builders.game_systems import place
    assert place(subject) == where


def test_the_game_takes_what_no_hero_item_or_unit_page_shows():
    from builders.game_systems import claimed, place_entity
    assert claimed({'file': 'abilities.vdata', 'id': 'ability_x', 'owner': 'hero_haze'})
    assert claimed({'file': 'abilities.vdata', 'id': 'upgrade_x', 'kind': 'item'})
    assert claimed({'file': 'abilities.vdata', 'id': 'citadel_ability_tier2boss_stomp', 'units': ['npc_boss_tier2']})
    assert claimed({'file': 'npc_units.vdata', 'id': 'trooper_normal'})
    assert not claimed({'file': 'npc_units.vdata', 'id': 'trooper_base', 'template': True})
    assert not claimed({'file': 'abilities.vdata', 'id': 'ability_golden_idol', 'kind': 'ability_other'})
    assert not claimed({'file': 'abilities.vdata', 'id': 'citadel_ability_jump', 'kind': 'shared'})
    # where the pages are built, exactly the rest: a hero with no page leaves its rows to the Game
    assert place_entity('abilities.vdata:ability_x', {'file': 'abilities.vdata', 'id': 'ability_x', 'owner': 'hero_z',
                                                      'kind': 'ability'}, pages=set()) == ('other', 'abilities')
    # scenery is no page's (classify.decor_entity): a shared edit spread over the breakable props lands on the cars
    assert place_entity('misc.vdata:vehicle_car_01', {'file': 'misc.vdata', 'id': 'vehicle_car_01'}) is None
    assert place_entity('generic_data.vdata:m_OutlineColorEnemy',
                        {'file': 'generic_data.vdata', 'id': 'm_OutlineColorEnemy'}) is None


def test_names_never_show_an_id():
    from builders.game_systems import name_of
    assert name_of('misc.vdata:citadel_idol_cashin') == 'Soul Urn delivery'
    assert name_of('npc_units.vdata:trooper_base', {'file': 'npc_units.vdata', 'id': 'trooper_base',
                                                    'template': True, 'name': 'trooper_base'}) == 'Trooper template'
    assert name_of('modifiers.vdata:modifier_citadel_something', {'file': 'modifiers.vdata',
                                                                  'id': 'modifier_citadel_something',
                                                                  'name': 'modifier_citadel_something'}) == 'Something'
    assert name_of('misc.vdata:citadel_breakable_prop_xyz_base', {'file': 'misc.vdata',
                                                                   'id': 'citadel_breakable_prop_xyz_base'}
                   ).endswith('(template)')
    assert name_of('loot_tables.vdata:all_items') == 'Loot table: All items'


def test_every_system_icon_is_in_the_game_files_or_a_site_glyph():
    from builders.common import GLYPHS
    from builders.game_systems import missing_icons, systems
    assert missing_icons() == []
    for s in systems():
        if s.icon.startswith('glyph:'):
            assert s.icon[6:] in GLYPHS, s.id


# ---- console variables ----------------------------------------------------------------------------------------

def cv(name, op='change', old=None, new=None, build=6601, flags='developmentonly gamedll defensive', status='hidden'):
    return {'name': name, 'op': op, 'old': old, 'new': new, 'build': build, 'flags': flags, 'status': status}


def test_console_variables_become_history_rows():
    from builders.game_systems import convar_changes
    rows = [cv('citadel_player_spawn_time_max_ramp_1', old='35', new='37', build=6690, status='documented'),
            cv('citadel_player_spawn_time_max_ramp_1', old='37', new='38', build=6694),
            cv('citadel_player_gold_reward_min', old='250', new='200'),
            cv('citadel_koth_warning_time', op='add', new='25', flags='gamedll clientdll replicated cheat'),
            cv('citadel_koth_spawn_window', op='remove', old='60', flags='gamedll cheat'),
            cv('citadel_crate_reward_base', op='desc', new='Reward'),                     # a description: no change
            cv('citadel_hud_scale', old='1', new='2', flags='clientdll archive'),          # the client's: archive only
            cv('citadel_crate_drop_duration_override', old='-1', new='5', flags='gamedll cheat'),   # a test hook
            cv('citadel_player_gold_reward_max', op='add', new='9', build=6395)]          # the tracking's first build
    got = {c['id']: c for c in convar_changes(rows, start_build=6395)}
    assert set(got) == {'citadel_player_spawn_time_max_ramp_1', 'citadel_player_gold_reward_min',
                        'citadel_koth_warning_time', 'citadel_koth_spawn_window'}
    spawn = got['citadel_player_spawn_time_max_ramp_1']
    # in the game's unit (game_systems.convar_value: a respawn ramp is seconds)
    assert (spawn['old_s'], spawn['new_s'], spawn['builds'], spawn['status']) == ('35s', '38s', [6690, 6694], 'documented')
    # a longer respawn is worse for whoever dies; fewer souls for a kill too
    assert spawn['dir'] == 'nerf' and got['citadel_player_gold_reward_min']['dir'] == 'nerf'
    assert got['citadel_koth_warning_time']['op'] == 'add' and got['citadel_koth_spawn_window']['op'] == 'remove'
    assert spawn['label'] == 'citadel_player_spawn_time_max_ramp_1'     # the one id a page shows (AGENTS)


def test_a_console_variable_without_a_side_moves_up_or_down():
    from builders.game_systems import convar_change, convar_side
    assert convar_side('citadel_player_gold_comeback_multiplier') == 0
    assert convar_change('citadel_player_gold_comeback_multiplier', 'change', '2.1', '2.268', 'hidden', [])['dir'] == 'up'
    assert convar_change('citadel_crate_respawn_interval', 'change', '360', '300', 'hidden', [])['dir'] == 'buff'


def test_the_rules_table_has_todays_values_and_their_history(monkeypatch):
    import builders.game_systems as gs
    from builders.game_rules import ledger, rules_page
    raw = [({'id': '2026-03-10', 'date': '2026-03-10'},
            [cv('citadel_player_spawn_time_max_ramp_1', op='add', new='30', build=6395),
             cv('citadel_hud_scale', op='add', new='1', build=6395, flags='clientdll')]),
           ({'id': '2026-06-30', 'date': '2026-06-30'}, [cv('citadel_player_spawn_time_max_ramp_1', old='30', new='35')]),
           ({'id': '2026-09-16', 'date': '2026-09-16'},
            [cv('citadel_player_spawn_time_max_ramp_1', old='35', new='38', build=6694)])]
    monkeypatch.setattr(gs, 'convar_start', lambda: 6395)       # the tracking's first build: a snapshot
    led = ledger(raw)
    html = rules_page(raw)
    spawn = led['citadel_player_spawn_time_max_ramp_1']
    assert spawn['value'] == '38' and [h[2:] for h in spawn['hist']] == [[30, 35], [35, 38]]
    assert 'citadel_player_spawn_time_max_ramp_1' in html and 'citadel_hud_scale' not in html
    assert re.search(r'data-hist=.*?\[6694,"2026-09-16",35,38\]', html)


# ---- templates --------------------------------------------------------------------------------------------------

def test_a_templates_change_shows_only_where_no_heir_shows_it():
    from builders.game_pages import _heir_sigs, template_rows
    shown = ch(path='m_flAttackShrineMaxRange', old_s='', new_s='11.43m', op='add')
    alone = ch(path='m_flBulletSpeed', old_s='457.2m/s', new_s='152.4m/s')
    by_ent = {'npc_units.vdata:trooper_base': [(ROW, [shown, alone])],
              'npc_units.vdata:trooper_normal': [(ROW, [dict(shown)])]}
    cat = {'npc_units.vdata:trooper_base': {'id': 'trooper_base', 'template': True},
           'npc_units.vdata:trooper_normal': {'id': 'trooper_normal'}}
    rows = template_rows('npc_units.vdata:trooper_base', by_ent['npc_units.vdata:trooper_base'], _heir_sigs(by_ent, cat))
    assert rows == [(ROW, [alone])]


# ---- a system's page ---------------------------------------------------------------------------------------------

def _game_by_ent():
    from builders.game_systems import ALL_PREFIX, CONVAR_PREFIX
    urn = ch(path='m_flBounty', label='Bounty', old_s='1000', new_s='800', dir='nerf', pct=-20.0,
             key='misc.vdata:citadel_idol_cashin:m_flBounty')
    spread = ch(path='m_flPrimaryDropChance', label='Primary Drop Chance', old_s='25', new_s='0', dir='down',
                shared_n=3, shared_what='map objects', key='misc.vdata:a:m_flPrimaryDropChance')
    level = ch(path='m_mapLevelInfo.10.m_unRequiredGold', label='Level 10: souls needed', old_s='5000', new_s='5200',
               dir='nerf', status='described', shared_n=61, shared_what='heroes', shared_every=True)
    warn = {'key': 'convars:citadel_koth_warning_time:citadel_koth_warning_time', 'path': 'citadel_koth_warning_time',
            'op': 'change', 'cat': 'balance', 'label': 'citadel_koth_warning_time', 'old_s': '25', 'new_s': '20',
            'dir': 'down', 'pct': -20.0, 'status': 'documented'}
    return {
        'misc.vdata:citadel_idol_cashin': [(ROW, [urn])],
        'misc.vdata:citadel_breakable_item_container': [(ROW, [spread])],
        'misc.vdata:citadel_breakable_prop_drop_powerups': [(ROW, [dict(spread)])],
        ALL_PREFIX + 'heroes.vdata': [(ROW, [level])],
        CONVAR_PREFIX + 'citadel_koth_warning_time': [(ROW, [warn])],
        'heroes.vdata:hero_haze': [(ROW, [ch()])],
    }


def test_a_system_page_is_a_history_of_its_entries():
    from builders.game_pages import collect, system_page
    by_ent = _game_by_ent()
    entries, hist = collect(by_ent, {})
    assert 'heroes' not in str(entries.get('urn')) and set(entries) == {'urn', 'breakables', 'progression'}
    urn = system_page('urn', entries['urn'], hist, {})
    text = re.sub(r'<[^>]+>', ' ', urn)
    assert 'Soul Urn delivery' in text and 'Bounty' in text and 'citadel_koth_warning_time' in text
    assert 'Console variables' in text and 'href="index.html">Game</a>' in urn
    # one edit spread over two breakables is ONE group naming both
    page = system_page('breakables', entries['breakables'], hist, {})
    crates = re.sub(r'<[^>]+>', ' ', page[page.index('id="history"'):])
    assert crates.count('Primary Drop Chance') == 1 and 'Breakable (powerups) · Crate' in crates
    # a rule for every hero is the part's own row, with how many it touches
    prog = system_page('progression', entries['progression'], hist, {})
    assert 'Level curve' in prog and 'all 61 heroes' in prog and 'shr-all' not in prog


def test_the_index_rules_and_matrix_are_the_sections_three_tabs():
    from builders.common import NAV, SECTION_TABS
    from builders.game_pages import collect, index_page
    assert ('game', 'Game', 'game/index.html') in NAV
    assert [t[0] for t in SECTION_TABS['game']] == ['index', 'stats', 'changes']
    entries, hist = collect(_game_by_ent(), {})
    html = index_page(entries, hist)
    assert 'href="urn.html"' in html and 'Urn &amp; Unstable Rift' in html
    # dates are never in the pixel fonts: the card's date sits in its own span
    assert re.search(r'class="d">last 2026-06-04<', html)


def test_the_old_shared_page_points_to_movement_and_combat():
    from builders import shared_page
    html = shared_page.redirect()
    assert 'data-redirect="../game/combat.html"' in html
    assert '../game/combat.html' in shared_page.index_link()


# ---- the home page and the search ------------------------------------------------------------------------------

def _patch(entities, convars=()):
    return {'id': ROW['id'], 'title': ROW['title'], 'date': ROW['date'], 'entities': entities,
            'extras': {'convars': list(convars)}}


def test_an_update_that_only_changed_the_game_is_in_the_feed(monkeypatch):
    """06-04 (the Soul Urn rework) was skipped: no hero, item or unit icon."""
    from builders import home_page
    import builders.game_systems as gs
    monkeypatch.setattr(gs, 'convar_start', lambda: 6395)
    p = _patch([{'key': 'misc.vdata:citadel_idol_cashin', 'file': 'misc.vdata', 'id': 'citadel_idol_cashin',
                 'kind': 'global', 'name': 'citadel_idol_cashin',
                 'changes': [ch(path='m_flBounty', old_s='1000', new_s='800', key='misc.vdata:citadel_idol_cashin:b')]}],
               [cv('citadel_player_spawn_time_max_ramp_1', old='35', new='38')])
    feed = home_page.update_feed(p)
    assert set(feed) == {'game'} and set(feed['game']) == {'game:urn', 'game:respawn'}
    assert feed['game']['game:urn']['rows'][0][0] == 'Soul Urn delivery'
    html = home_page._chip('game:urn', feed['game']['game:urn'], ROW['id'], {}, True, 0)
    assert 'href="game/urn.html#p-2026-06-04"' in html and 'Urn &amp; Unstable Rift' in html


def test_search_finds_the_systems_and_their_named_entries():
    from builders.game_pages import collect, search_rows
    entries, _ = collect(_game_by_ent(), {})
    rows = search_rows(entries)
    assert ['Urn & Unstable Rift', 'game/urn.html', 'Game'] == rows[[r[0] for r in rows].index('Urn & Unstable Rift')][:3]
    assert ['Soul Urn delivery', 'game/urn.html#ab-citadel_idol_cashin', 'Urn & Unstable Rift · Game'] in \
        [r[:3] for r in rows]


# ---- the archive's console variables -----------------------------------------------------------------------------

def test_the_archive_lists_every_console_variable_or_says_how_many_more():
    from builders.patches_pages import _extras_parts
    p = {'builds': [{'build': 6711, 'file': '6711_x.json.gz'}],
         'extras': {'convars': [cv('citadel_a', old='1', new='2')], 'convars_total': 3}}
    [(key, label, n, html)] = [x for x in _extras_parts(p, '../') if x[0] == 'console']
    assert n == 3 and '+2 more on the build pages' in html and 'builds/6711.html' in html
    whole = {'builds': [], 'extras': {'convars': [cv('citadel_a', old='1', new='2')], 'convars_total': 1}}
    assert 'more on the build pages' not in [x for x in _extras_parts(whole, '../') if x[0] == 'console'][0][3]


def test_slim_extras_keeps_every_console_variable_noted_first():
    from pipeline.match import slim_extras
    extras = {'loc': [], 'assets': [], 'convars': [cv(f'citadel_{i}', op='add', new='1', build=6711) for i in range(350)]
              + [cv('citadel_noted', old='1', new='2', build=6712, status='documented')]}
    out = slim_extras(extras, {})
    assert len(out['convars']) == out['convars_total'] == 351 and out['convars'][0]['name'] == 'citadel_noted'


# ---- name and description changes --------------------------------------------------------------------------------

CAT = {'abilities.vdata:ability_sleep_dagger': {'file': 'abilities.vdata', 'id': 'ability_sleep_dagger'},
       'abilities.vdata:upgrade_self_bubble': {'file': 'abilities.vdata', 'id': 'upgrade_self_bubble'},
       'heroes.vdata:hero_slork': {'file': 'heroes.vdata', 'id': 'hero_slork'}}


def test_a_localization_key_names_its_entity_and_part():
    from pipeline.entity_texts import key_part
    ids = {e['id']: k for k, e in CAT.items()}
    assert key_part('ability_sleep_dagger', ids) == ('abilities.vdata:ability_sleep_dagger', 'name')
    assert key_part('ability_sleep_dagger_desc', ids) == ('abilities.vdata:ability_sleep_dagger', 'desc')
    assert key_part('ability_sleep_dagger_t2_desc', ids) == ('abilities.vdata:ability_sleep_dagger', 't2')
    assert key_part('Upgrade_Self_Bubble', ids) == ('abilities.vdata:upgrade_self_bubble', 'name')
    assert key_part('hero_slork', ids) == ('heroes.vdata:hero_slork', 'name')
    assert key_part('ability_sleep_dagger_t1', ids) is None              # a tier's label, not its text
    assert key_part('hero_slork_desc', ids) is None and key_part('ability_sleep_dagger_quip', ids) is None


def test_a_windows_text_change_is_its_first_old_and_last_new_words():
    from pipeline.entity_texts import entity_texts
    loc = [{'key': 'upgrade_self_bubble', 'old': 'Shifting Shroud', 'new': 'Veil', 'build': 1},
           {'key': 'upgrade_self_bubble', 'old': 'Veil', 'new': 'Ethereal Shift', 'build': 2},
           {'key': 'ability_sleep_dagger_desc', 'old': 'Throw a <span class="highlight">dagger</span>',
            'new': 'Throw a <span class="x">dagger</span>', 'build': 1},           # markup only: nothing to read
           {'key': 'ability_sleep_dagger_t3_desc', 'old': '', 'new': '+1 Charge', 'build': 1},   # came with nothing
           {'key': 'hero_slork', 'old': 'Slork', 'new': 'Fathom', 'build': 2}]
    got = {(t['ent'], t['part']): t for t in entity_texts(loc, CAT)}
    assert set(got) == {('abilities.vdata:upgrade_self_bubble', 'name'), ('heroes.vdata:hero_slork', 'name')}
    bubble = got[('abilities.vdata:upgrade_self_bubble', 'name')]
    assert (bubble['old'], bubble['new'], bubble['builds']) == ('Shifting Shroud', 'Ethereal Shift', [1, 2])


def test_text_changes_are_rows_of_the_entity_never_counted():
    from builders.history_view import history_table
    from builders.text_rows import TEXT_PREFIX
    key = 'abilities.vdata:ability_sleep_dagger'
    by_ent = {key: [(ROW, [ch(key=f'{key}:cd')])],
              TEXT_PREFIX + key: [(ROW, [{'ent': key, 'part': 'name', 'old': 'Sleep Dagger', 'new': 'Dream Dagger'},
                                         {'ent': key, 'part': 't2', 'old': '+2s Sleep Duration',
                                          'new': '-4s Cooldown'}])]}
    html = history_table([('heroes.vdata:hero_x', 'Base stats', None), (key, 'Sleep Dagger', None)], [], by_ent, {}, '../')
    assert 'st-text' in html and 'Dream Dagger' in html and 'T2 description changed' in html
    assert '<del>+2s Sleep Duration</del>' in html and '<ins>-4s Cooldown</ins>' in html
    # the band counts its one change, not the texts
    banner = html[html.index('<summary class="banner'):html.index('</summary>')]
    assert re.findall(r'class="pip [^"]+"[^>]*>.*?(\d+)</span>', banner) == ['1']


def test_a_renamed_hero_says_its_old_names():
    from builders.text_rows import TEXT_PREFIX, former_names
    by_ent = {TEXT_PREFIX + 'heroes.vdata:hero_slork': [(ROW, [{'part': 'name', 'old': 'Slork', 'new': 'Fathom'}])]}
    assert former_names(by_ent, 'heroes.vdata:hero_slork', 'Fathom') == ['Slork']


# ---- on the real data: every gameplay row lands on a page ---------------------------------------------------------

def _regenerated() -> bool:
    from builders.common import load_json
    p = load_json('patches/2026-09-29.json.gz')
    return 'texts' in p.get('extras', {}) and any(e.get('target_keys') for e in p['entities'] if e['id'] == '@shared')


needs_data = pytest.mark.skipif(not _regenerated(), reason='data/patches predates texts / target_keys: regenerate')


@needs_data
def test_every_gameplay_row_lands_on_a_hero_item_unit_or_game_page():
    """Except a template's change one of its heirs shows (the heir's page has it) and work on a hero in development
    whose page waits (behind "Before release"); scenery (classify.decor_entity) is no gameplay."""
    from builders.cards import player_facing
    from builders.common import load_json
    from builders.entities_pages import _history, changed, page_entities, page_keys
    from builders.game_pages import _heir_sigs, collect
    from builders.game_systems import is_decor, is_template
    from builders.shared_rows import entities as spread_all
    ents = {f"{e['file']}:{e['id']}": e for e in load_json('entities.json')['entities']}
    by_ent, _ = _history()
    trow = {r['id']: r for r in load_json('tables/heroes.json')['heroes']}
    pages = page_keys(ents, *page_entities(ents, changed(by_ent), trow))
    entries, hist = collect(by_ent, ents, pages)
    in_game = {k for parts in entries.values() for got in parts.values() for k, _, _ in got}
    sigs = _heir_sigs(by_ent, ents)
    lost = []
    for row in load_json('patches/index.json'):
        p = load_json(f'patches/{row["id"]}.json.gz')
        for e in spread_all(p['entities']):
            info = {**e, **ents.get(e['key'], {})}
            rows = player_facing([c for c in e['changes'] if c['cat'] in ('balance', 'mechanic', 'availability')])
            if not rows or e['key'] in pages or is_decor(info):
                continue
            for c in rows:
                if c.get('status') == 'unreleased':
                    continue
                sig = (c.get('path'), str(c.get('old_s')), str(c.get('new_s')))
                if is_template(info) and sig in sigs.get((e['file'], row['id']), ()):
                    continue                  # a template's change an heir shows (the heir's page)
                if e['key'] not in in_game:
                    lost.append((row['id'], e['key'], c.get('label')))
    assert not lost, lost[:20]


@needs_data
def test_every_announced_console_variable_is_on_a_game_page():
    """Valve's own numbers ("Respawn Time at 20 minutes increased from 35s to 38s") never only in the archive."""
    from builders.common import load_json
    from builders.game_systems import convar_place
    missed = []
    for row in load_json('patches/index.json'):
        for x in load_json(f'patches/{row["id"]}.json.gz').get('extras', {}).get('convars', []):
            if x.get('status') in ('documented', 'described') and not convar_place(x):
                missed.append((row['id'], x['name']))
    assert not missed, missed


@needs_data
def test_the_soul_urn_rework_of_2026_06_04_is_on_its_page_and_the_feed():
    from builders import home_page
    from builders.common import load_json
    feed = home_page.update_feed(load_json('patches/2026-06-04.json.gz'))
    assert 'game:urn' in feed.get('game', {})
