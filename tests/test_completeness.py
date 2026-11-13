"""Concept audit 2026-11-13: what was in data/ and on no page, or on a page as an empty shell — Street Brawl, removed
entities' cards, build pages' junk and cuts, a new entity's numbers and its later edits, neutral attacks, empty folds,
console variables on no Game page, list labels."""
from builders import arrivals, brawl, build_tech, builds_pages
from builders.cards import change_row, entity_rows, writes_rows
from builders.list_labels import fixed_label


# ---- 1. Street Brawl ---------------------------------------------------------------------------------------------

def _draft(op, path, old, new, key='heroes.vdata:hero_atlas', status='hidden'):
    return {'op': op, 'cat': 'streetbrawl', 'path': f'm_mapItemDraftWeights.{path}', 'old_s': old, 'new_s': new,
            'label': 'Item Draft Weights › x', 'status': status, 'key': f'{key}:m_mapItemDraftWeights.{path}',
            'builds': [6127]}


def test_street_brawl_rules_are_gameplay_rows_in_words_and_draft_weights_are_not():
    rule = {'op': 'change', 'cat': 'streetbrawl', 'old': 35, 'new': 40, 'old_s': '35', 'new_s': '40',
            'path': 'm_vecItemDraftRoundsPerGameRound[4].m_chanceRare.m_mapOutcomesToWeights.2',
            'label': 'Chance Rare › Outcomes To Weights › 2'}
    weight = _draft('add', 'upgrade_dps_aura', '—', '2.4')
    got = brawl.gameplay_rows([rule, weight])
    assert [c['label'] for c in got] == ['Round 5 draft: 2 rare items (weight)']
    assert got[0]['cat'] == 'balance' and rule['cat'] == 'streetbrawl'          # a copy: the archive is shared
    # the 2026-09-29 re-keying: the new key reads the same, so DEL + NEW of one value is no change
    assert brawl.rule_label({'path': 'm_vecItemDraftRoundsPerGameRound[4].m_chanceRare.2'}) == got[0]['label']
    assert brawl.rule_label({'path': 'm_mapItemTierToItemDraftBuckets.EModTier_3.m_mapBuckets.Good'}) == \
        'Draft of tier 3 items: Good bucket (weight)'
    assert brawl.rule_label({'path': 'm_BackdoorProtection.m_flBackdoorProtectionDamageMitigationFromPlayers_Streetbrawl',
                             'label': 'Backdoor Protection › Backdoor Protection Damage Mitigation From Players '
                                      'Streetbrawl'}) == \
        'Backdoor Protection › Damage mitigation from players (Street Brawl)'


def test_a_patchs_draft_weights_are_one_row_listing_hero_item_old_new():
    shared = {'file': 'heroes.vdata', 'id': '@shared', 'target_keys': ['heroes.vdata:hero_atlas', 'heroes.vdata:hero_haze'],
              'changes': [_draft('change', 'upgrade_dps_aura', '2.4', '1')]}
    own = {'file': 'heroes.vdata', 'id': 'hero_atlas', 'changes': [_draft('change', 'upgrade_return_fire', '1', '2.4')]}
    row = brawl.draft_row({'entities': [shared, own]})
    assert row['label'] == 'Item draft weights: 2 heroes, 2 items' and row['op'] == 'change'
    assert brawl.draft_row({'entities': [{'file': 'heroes.vdata', 'id': 'hero_atlas', 'changes': []}]}) is None
    html = change_row(row)
    assert html.count('class="erow') == 1                  # ONE counted row; its lines are no rows
    assert '<details class="drafts">' in html and html.count('<li>') == 2
    assert 'upgrade_' not in html and 'hero_' not in html  # names, never ids


def test_draft_weights_are_a_group_of_game_modes_and_count_once(monkeypatch):
    from builders import game_pages, patch_counts
    row = brawl.draft_row({'entities': [{'file': 'heroes.vdata', 'id': 'hero_atlas',
                                         'changes': [_draft('add', 'upgrade_dps_aura', '—', '2.4')]}]})
    entries, hist = game_pages.collect({brawl.DRAFT_SUBJECT: [({'id': 'p', 'date': '2026-01-22'}, [row])]}, {}, set())
    assert ('game:modes:brawl:drafts', '', '') in entries['modes']['brawl']
    assert hist['game:modes:brawl:drafts'][0][1] == [row]
    p = {'id': 'p', 'entities': [{'file': 'heroes.vdata', 'id': 'hero_atlas', 'key': 'heroes.vdata:hero_atlas',
                                  'changes': [_draft('add', 'upgrade_dps_aura', '—', '2.4'),
                                              _draft('add', 'upgrade_return_fire', '—', '1')]}], 'extras': {}}
    got = patch_counts.count(p, frozenset())
    assert got['changes'] == 1 and got['not_in_notes'] == 1


# ---- 2. no card is a name over nothing ----------------------------------------------------------------------------

def test_a_removed_entity_on_a_build_page_says_so():
    rec = {'entities': [{'file': 'abilities.vdata', 'id': 'ability_riptide', 'status': 'removed', 'kind': 'ability',
                         'changes': [{'op': 'remove', 'cat': 'visual', 'path': 'm_strIcon', 'old': 'x'}]}]}
    ents = builds_pages.page_entities(rec)
    assert ents and ents[0]['changes'][0]['path'] == '@remove'
    assert writes_rows(ents[0]['changes'])


def test_an_entity_whose_rows_are_all_no_ops_has_no_card():
    noop = [{'op': 'add', 'cat': 'mechanic', 'path': 'm_AOEModifier.m_bDurationReducible', 'new_s': 'no',
             'label': 'AOE Modifier › Duration Reducible', 'status': 'hidden'}]
    assert not writes_rows(noop)
    rec = {'entities': [{'file': 'abilities.vdata', 'id': 'upgrade_cold_front', 'status': 'changed', 'changes': noop}]}
    assert builds_pages.page_entities(rec) == []
    from builders.patches_pages import shown_entities
    assert shown_entities([{'file': 'abilities.vdata', 'id': 'upgrade_cold_front', 'changes': noop}]) == []


# ---- 3. build pages ----------------------------------------------------------------------------------------------

def test_binary_strings_without_a_word_are_not_listed():
    assert build_tech.is_word_string('CCitadelModifier_Spirit') and not build_tech.is_word_string('.l/gwk')
    junk = {'client': {'n_added': 2, 'n_removed': 0, 'added': ['.l/gwk', 'A&8x'], 'removed': []}}
    assert build_tech.strings_section(junk, 6000, None) == ''
    mixed = {'client': {'n_added': 3, 'n_removed': 0, 'added': ['.l/gwk', 'StreetBrawlRound'], 'removed': []}}
    html = build_tech.strings_section(mixed, 6000, None)
    assert 'StreetBrawlRound' in html and '.l/gwk' not in html and 'and 2 more' in html


def test_a_build_page_shows_every_text_variable_and_other_field():
    loc = [{'key': f'citadel_x_{i}', 'old': f'a{i}', 'new': f'b{i}'} for i in range(620)]
    convars = [{'name': f'citadel_v{i}', 'op': 'change', 'old': '1', 'new': '2'} for i in range(450)]
    rec = {'build': None, 'date': '2026-01-01T00:00', 'commit': None, 'loc': loc, 'convars': convars,
           'entities': [{'file': 'misc.vdata', 'id': 'xp_orb', 'status': 'changed',
                         'changes': [{'op': 'change', 'cat': 'visual', 'path': 'm_particle', 'label': 'Particle',
                                      'old_s': 'a.vpcf', 'new_s': 'b.vpcf'}]}]}
    html = builds_pages.build_page(rec, None, None, None)
    assert html.count('citadel_v') >= 450 and 'b619' in html
    assert 'Other data fields' in html and 'a.vpcf' in html and 'Cosmetic fields changed' not in html


def test_a_build_page_folds_entities_past_its_limit_keeping_a_hero_in_one_card(monkeypatch):
    monkeypatch.setattr(builds_pages, 'ENTITY_LIMIT', 2)
    ents = [{'file': 'heroes.vdata', 'id': 'hero_a'}, {'file': 'misc.vdata', 'id': 'x'},
            {'file': 'abilities.vdata', 'id': 'ab', 'owner': 'hero_a'}, {'file': 'misc.vdata', 'id': 'y'}]
    first, more = builds_pages.split_limit(ents)
    assert [e['id'] for e in first] == ['hero_a', 'x', 'ab'] and [e['id'] for e in more] == ['y']


def test_a_build_pages_console_variables_carry_their_status(monkeypatch):
    from builders import archive
    monkeypatch.setattr(archive, 'patch', lambda pid: {'extras': {'convars': [
        {'name': 'citadel_idle_time', 'op': 'change', 'build': 6600, 'status': 'hidden'},
        {'name': 'citadel_idle_time', 'op': 'change', 'build': 6601, 'status': 'documented'}]}})
    assert builds_pages.convar_statuses('p', 6600) == {('citadel_idle_time', 'change'): 'hidden'}


# ---- 4. a new entity's numbers and its later edits ---------------------------------------------------------------

def test_a_new_entity_says_what_it_came_with_and_keeps_its_later_edits(monkeypatch):
    recs = {
        'a.json.gz': {'entities': [{'file': 'abilities.vdata', 'id': 'upgrade_spirit_snatch', 'status': 'added', 'changes': [
            {'op': 'add', 'cat': 'balance', 'path': 'm_mapAbilityProperties.TechPowerReduction.m_strValue',
             'label': 'Spirit Power Reduction', 'new_s': '-30', 'new': -30},
            {'op': 'add', 'cat': 'balance', 'path': 'm_mapAbilityProperties.SpiritDamage.m_strValue',
             'label': 'Spirit Damage', 'new_s': '50', 'new': 50}]}]},
        'b.json.gz': {'entities': [{'file': 'abilities.vdata', 'id': 'upgrade_spirit_snatch', 'status': 'changed', 'changes': [
            {'op': 'change', 'cat': 'balance', 'path': 'm_mapAbilityProperties.TechPowerReduction.m_strValue',
             'label': 'Spirit Power Reduction', 'old_s': '-30', 'new_s': '-26', 'old': -30, 'new': -26}]}]}}
    monkeypatch.setattr(arrivals, '_record', lambda f: recs.get(f))
    p = {'builds': [{'build': 5375, 'file': 'a.json.gz'}, {'build': 5390, 'file': 'b.json.gz'}],
         'entities': [{'file': 'abilities.vdata', 'id': 'upgrade_spirit_snatch', 'key': 'abilities.vdata:upgrade_spirit_snatch',
                       'changes': [{'op': 'add', 'cat': 'mechanic', 'path': '@add', 'label': 'Added to the game files',
                                    'status': 'described', 'builds': [5375]}]}]}
    got = arrivals.complete(p)
    rows = got['entities'][0]['changes']
    assert 'Spirit Power Reduction -30' in rows[0]['came_with'] and 'Spirit Damage 50' in rows[0]['came_with']
    assert (rows[1]['old_s'], rows[1]['new_s'], rows[1]['builds'], rows[1]['status']) == ('-30', '-26', [5390], 'hidden')
    assert p['entities'][0]['changes'][0].get('came_with') is None          # the shared record is never written into
    from builders.render import vals_html
    assert 'Spirit Damage 50' in vals_html(rows[0])


# ---- 5. a neutral's attacks are its unit's ------------------------------------------------------------------------

def test_a_neutrals_attack_effects_belong_to_its_page():
    from builders.entities_pages import page_keys
    from builders.home_page import page_route
    from pipeline.classify import unit_bound_modifiers
    units = {'neutral_library_strong': {'m_vNeutralAbilities': ['citadel_neutral_attack_lob_book'],
                                        'm_sNeutralMelee': 'citadel_neutral_light_melee_strong'}}
    assert unit_bound_modifiers(units) == {'citadel_neutral_attack_lob_book': ['neutral_library_strong'],
                                           'citadel_neutral_light_melee_strong': ['neutral_library_strong']}
    unit = {'file': 'npc_units.vdata', 'id': 'neutral_library_strong'}
    mod = {'file': 'modifiers.vdata', 'id': 'citadel_neutral_attack_lob_book', 'units': ['neutral_library_strong']}
    ents = {'npc_units.vdata:neutral_library_strong': unit, 'modifiers.vdata:citadel_neutral_attack_lob_book': mod}
    keys = page_keys(ents, [], [], [unit])
    assert 'modifiers.vdata:citadel_neutral_attack_lob_book' in keys
    assert page_route('modifiers.vdata:citadel_neutral_attack_lob_book', mod, keys, {}) == \
        ('npc_units.vdata:neutral_library_strong', 'units')


# ---- 6. no fold over nothing --------------------------------------------------------------------------------------

def test_new_console_variables_and_new_bonuses_with_no_key_field_are_listed():
    words = 'alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima mike'.split()
    cvs = [{'op': 'add', 'cat': 'balance', 'path': f'citadel_idol_{w}', 'label': f'citadel_idol_{w}', 'new_s': '1',
            'status': 'hidden', 'convar': True, 'key': f'convars:citadel_idol_{w}:citadel_idol_{w}'} for w in words]
    html = entity_rows(cvs)
    assert 'Added to the game<' not in html and html.count('class="erow') == 13
    tiers = [{'op': 'add', 'cat': 'balance', 'path': f'm_vecAbilityUpgrades[{i % 3}].m_vecPropertyUpgrades{{P{i}}}.m_strBonus',
              'label': f'T{i % 3 + 1}: Bonus {i}', 'new_s': str(i + 1), 'status': 'hidden'} for i in range(15)]
    html = entity_rows(tiers)
    assert html.count('class="erow') >= 15


# ---- 7. console variables a match plays by are on a Game page -----------------------------------------------------

def test_gameplay_console_variables_have_a_game_place():
    from builders.game_systems import convar_place
    for name, where in (('citadel_trailingteam_bias_threshold_max', ('urn', 'urn')),
                        ('citadel_idle_time', ('other', 'rules')),
                        ('citadel_breakable_prop_reject_cooldown', ('breakables', 'crates')),
                        ('citadel_mantle_auto_step_check_inset', ('combat', 'rules')),
                        ('citadel_match_pre_trooper_spawn_brawl_time', ('modes', 'brawl'))):
        assert convar_place({'name': name, 'flags': 'gamedll'}) == where, name
    assert convar_place({'name': 'citadel_boss_tier2_bull_wip', 'flags': 'gamedll'}) is None


# ---- 8. labels and the footer -------------------------------------------------------------------------------------

def test_list_rows_read_as_words():
    assert fixed_label('generic_data.vdata:m_LaneInfo:value[2].m_strLaneName', 'value #3 › Lane Name') == \
        'Lane 3 › Lane Name'
    assert fixed_label('generic_data.vdata:m_StreetBrawl:m_vecBuyTime[4]', 'Buy Time #5') == 'Buy Time, round 5'
    assert fixed_label('heroes.vdata:hero_x:m_mapPurchaseBonuses.x', 'Vitality purchase bonus, tier 3: value') == \
        'Vitality purchase bonus, tier 3'
    assert fixed_label('heroes.vdata:hero_x:m_x', 'Companion Abilities #1 › Companion') == \
        'Companion Abilities #1 › Companion'


def test_the_footer_links_the_builds():
    from builders.common import page
    html = page('t', '', '../', 'heroes')
    assert 'href="../builds/index.html">Builds</a>' in html
