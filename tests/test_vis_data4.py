"""Data review round 4 (2026-10-17): a hero's release post is the notes its build is checked against, the hidden
lists lose plumbing, silent changes read in a player's words, broad shop-rework lines cover their scope, one count
per patch.

- In Violet's release ("Paint the Town", build 6790) Solomon's silent Move Piece rework and Danny's tuning read like her
  launch lines: no eye on the home icons, none on the patch page, 0% "not in notes" in the archive. What the release
  post left out is hidden (pipeline.match.release_pass) and every place shows its eye (builders.common.checks_notes);
  only an update with no post at all keeps its one "no patch notes".
- Frozen Shelter's trigger "Activation added (instant cast)", "Charge Delay added (default)" were a template's defaults;
  ping markers, shop filters and a trooper's boss-weapon key are no gameplay; a removed ability names its hero.
- "T3: Damage 0.225 → 0.35" is a spirit scaling bonus; "Auto Cast Delay › Attributes" is "Auto Cast Delay effect";
  the currency is souls; a Game system's console variables are one group per band.
- Violet counted 17 on the home page and 19 on her patch chip: a nameless part's repeat of its parent counts once
  everywhere (patch_counts); a release's check line holds every counted row (Nurse Harrow's pre-release nerf)."""
import json
import re
from pathlib import Path

from pipeline.match import MChange, mark_inherited_defaults, release_pass

ROOT = Path(__file__).resolve().parent.parent


def _mc(file, eid, path, old, new, label, op='change', cat='balance', kind='ability', owner=None, **kw) -> MChange:
    return MChange(file, eid, path, op, old, new, cat, kind, owner, label, False, **kw)


def ch(**kw):
    base = {'op': 'change', 'cat': 'balance', 'label': 'Cooldown', 'old_s': '27', 'new_s': '29', 'dir': 'nerf',
            'pct': 7.4, 'grad': 2, 'status': 'hidden', 'path': 'x'}
    base.update(kw)
    return base


# ---- 1. a release post is the build's notes ------------------------------------------------------------------------

def test_what_a_release_post_left_out_is_hidden_and_its_kit_described():
    cat = {'heroes.vdata:hero_artist': {'file': 'heroes.vdata', 'id': 'hero_artist'},
           'abilities.vdata:ability_artist_tether': {'file': 'abilities.vdata', 'id': 'ability_artist_tether',
                                                     'owner': 'hero_artist'},
           'abilities.vdata:ability_chessmaster_movechesspiece': {'file': 'abilities.vdata', 'owner': 'hero_chessmaster',
                                                                  'id': 'ability_chessmaster_movechesspiece'}}
    hp = _mc('heroes.vdata', 'hero_artist', 'm_mapStartingStats.EMaxHealth', 780, 710, 'Max Health', kind='hero')
    solomon = _mc('abilities.vdata', 'ability_chessmaster_movechesspiece', 'm_mapAbilityProperties.Damage.m_strValue',
                  40, None, 'Damage', op='remove')
    every = _mc('heroes.vdata', 'hero_artist', 'm_flX', 1, 2, 'X', kind='hero', shared=True)
    for c in (hp, solomon, every):
        c.status = 'unannounced'
    events = [{'file': 'abilities.vdata', 'id': 'ability_artist_tether', 'change': {'status': 'unannounced'}},
              {'file': 'misc.vdata', 'id': 'citadel_breakable_prop_tough_crate_hideout',
               'change': {'status': 'unannounced'}}]
    release_pass(['hero_artist'], [hp, solomon, every], events, cat)
    assert (hp.status, solomon.status, every.status) == ('described', 'hidden', 'hidden')
    assert [e['change']['status'] for e in events] == ['described', 'hidden']


def test_checks_notes_is_true_for_notes_and_a_release_post_only():
    from builders.common import checks_notes
    assert checks_notes({'has_notes': True}) and checks_notes({'has_notes': False, 'release': ['hero_artist']})
    assert not checks_notes({'has_notes': False})


def _release_patch():
    hero = {'key': 'heroes.vdata:hero_0', 'file': 'heroes.vdata', 'id': 'hero_0', 'kind': 'hero', 'name': 'Hero 0',
            'changes': [ch(key='heroes.vdata:hero_0:hp', label='Max Health', status='described')]}
    other = {'key': 'abilities.vdata:ab', 'file': 'abilities.vdata', 'id': 'ab', 'kind': 'ability', 'owner': 'hero_1',
             'name': 'Move Piece', 'changes': [ch(key='abilities.vdata:ab:a', label='Damage', status='hidden')]}
    nurse = {'key': 'heroes.vdata:hero_2', 'file': 'heroes.vdata', 'id': 'hero_2', 'kind': 'hero', 'name': 'Hero 2',
             'changes': [ch(key='heroes.vdata:hero_2:x', label='Bullet damage per boon', status='unreleased')]}
    return {'id': 'build-1', 'title': 'Paint the Town', 'date': '2026-10-16', 'sections': [], 'line_counts': {},
            'builds': [], 'release': ['hero_0'], 'entities': [hero, other, nurse]}


PAGES = frozenset({'heroes.vdata:hero_0', 'heroes.vdata:hero_1', 'heroes.vdata:hero_2', 'abilities.vdata:ab'})


def _catalog():
    return {f'heroes.vdata:hero_{i}': {'file': 'heroes.vdata', 'id': f'hero_{i}', 'kind': 'hero', 'name': f'Hero {i}'}
            for i in range(3)}


def test_a_release_shows_the_eye_on_the_home_page_the_list_and_its_page(monkeypatch):
    from builders import archive, home_page, patch_counts, patches_pages, shared_rows
    p = _release_patch()
    monkeypatch.setattr(shared_rows, 'catalog', _catalog)
    c = patch_counts.count(p, PAGES)
    assert c['not_in_notes'] == 1 and c['described'] == 1 and c['unreleased'] == 1
    monkeypatch.setattr(patch_counts, 'for_id', lambda pid: c)
    monkeypatch.setattr(archive, 'patch', lambda pid: p)
    row = {'id': 'build-1', 'title': 'Paint the Town', 'date': '2026-10-16', 'has_notes': False,
           'release': ['hero_0'], 'builds': 1, 'line_counts': {}}
    feed = home_page._feed([row], {}, frozenset(), {}, PAGES)
    # the banner counts what the post left out; the icon of the other hero carries the eye
    assert re.search(r'</span>1 not in patch notes</a>', feed) and 'no patch notes' not in feed
    assert 'lu-eye' in feed or 'lu-all' in feed
    ix = patches_pages._index_row(row, {}, '../', False)
    assert re.search(r'au-hidden">.*?<b>1</b>', ix) and 'no notes' not in ix
    assert re.search(r'class="b-hid" style="width:(?!0\.0%)', ix)          # the bar's hidden part
    # every counted row in one bucket of the check line: 1 released + 1 other + 1 in development
    audit = patches_pages._audit_line(p)
    assert '<b>1</b> released with the hero' in audit and '<b>1</b> other changes' in audit
    assert '<b>1</b> heroes in development' in audit
    # an update with no post at all keeps its one "no patch notes"
    quiet = home_page._feed([{**row, 'release': None}], {}, frozenset(), {}, PAGES)
    assert 'no patch notes' in quiet and 'lu-eye' not in quiet


def test_a_releases_written_notes_mark_each_line():
    from builders.patches_pages import RELEASE_WORDS
    from builders.written_notes import notes_html
    hero = {'file': 'heroes.vdata', 'id': 'hero_0', 'name': 'Violet'}
    other = {'file': 'abilities.vdata', 'id': 'ab', 'owner': 'hero_1', 'name': 'Move Piece'}
    rows = [(hero, ch(label='Max Health', status='described'), True),
            (other, ch(label='Damage', status='hidden'), True)]
    html, n = notes_html(rows, lambda e: e['name'], {'hero_1': 'Solomon'}, {'described': RELEASE_WORDS})
    assert n == 2
    assert re.search(r'<li><span class="mark described" data-tooltip="Released with the hero[^"]*"></span>'
                     r'<span class="tag', html)
    assert '<li><span class="mark hidden"' in html
    plain, _ = notes_html(rows, lambda e: e['name'], {'hero_1': 'Solomon'})
    assert 'class="mark' not in plain                    # an update with no post: one status, said once


# ---- 2. plumbing out of the hidden lists, owners named -------------------------------------------------------------

def test_a_parts_template_defaults_are_plumbing():
    base = _mc('abilities.vdata', 'ability_ice_dome_trigger', '_multibase', None, 'ability_trigger_base', 'Multibase',
               op='add', cat='meta')
    act = _mc('abilities.vdata', 'ability_ice_dome_trigger', 'm_eAbilityActivation', None, 'INSTANT', 'Activation',
              op='add', cat='mechanic')
    moved = _mc('abilities.vdata', 'ability_ice_dome_trigger', 'm_flRadius', 1, 2, 'Radius')
    # a whole item moving to another template (a tier move) keeps its rows
    item_base = _mc('abilities.vdata', 'upgrade_infuser', '_multibase', 'tech_upgrade_t1', 'armor_upgrade_t4',
                    'Multibase', cat='meta')
    item_add = _mc('abilities.vdata', 'upgrade_infuser', 'm_iItemTier', None, 'EModTier_4', 'Tier', op='add')
    # a part named on its own is an ability of its own (Solomon's knightbuff trigger is "Move King")
    named_base = _mc('abilities.vdata', 'ability_chessmaster_knightbuff_trigger', '_multibase', None, 'x', 'Multibase',
                     op='add', cat='meta')
    named_add = _mc('abilities.vdata', 'ability_chessmaster_knightbuff_trigger', 'm_flRange', None, 500, 'Range',
                    op='add')
    cat = {'abilities.vdata:ability_ice_dome': {'name': 'Frozen Shelter'},
           'abilities.vdata:ability_ice_dome_trigger': {'name': 'Frozen Shelter'},
           'abilities.vdata:ability_chessmaster_knightbuff': {'name': 'Kingside Knight'},
           'abilities.vdata:ability_chessmaster_knightbuff_trigger': {'name': 'Move King'}}
    mark_inherited_defaults([base, act, moved, item_base, item_add, named_base, named_add], cat)
    assert act.cat == 'technical' and moved.cat == 'balance' and item_add.cat == 'balance'
    assert named_add.cat == 'balance'


def test_ping_markers_shop_filters_and_a_boss_weapon_key_are_no_gameplay():
    from pipeline.classify import category
    assert category('m_flPingTargetHeightOffset', None, 200.0) == 'ui'
    assert category('m_flPingTargetRadius', None, 70.0) == 'ui'
    assert category('m_eDisableShopFilters', None, 'EShopFilterSpiritDamage') == 'technical'
    assert category('m_BossWeaponName', None, 'boss') == 'technical'
    # a physics radius stays: Valve wrote "Urn collision radius increased by 20%" (2026-05-25)
    assert category('m_flPhysicsRadius', 12.0, 15.6) == 'balance'


def test_a_removed_ability_names_its_hero_in_the_written_notes():
    from builders.written_notes import who
    assert who({'file': 'abilities.vdata', 'id': 'tokamak_breach', 'owner': 'hero_tokamak'}, 'Breach',
               {'hero_tokamak': 'Tokamak'}) == 'Tokamak · Breach'


def test_a_removed_ability_takes_its_hero_from_the_catalog(monkeypatch):
    """Its record has no owner (no hero binds it in its own build); the catalog keeps the last one. Only the written
    line's subject: the record and the pages' routing stay as they are."""
    from builders import shared_rows
    from builders.written_notes import notes_html
    monkeypatch.setattr(shared_rows, 'catalog', lambda: {'abilities.vdata:tokamak_breach': {'owner': 'hero_tokamak'}})
    gone = {'file': 'abilities.vdata', 'id': 'tokamak_breach', 'name': 'Breach'}
    html, _ = notes_html([(gone, ch(op='remove', path='@remove', label='Removed from the game files'), True)],
                         lambda e: e['name'], {'hero_tokamak': 'Tokamak'})
    assert 'Tokamak · Breach: removed from the game' in html and 'owner' not in gone


# ---- 3. a player's words on silent changes -------------------------------------------------------------------------

def test_a_scaling_tier_bonus_keyed_by_its_property_says_so():
    from pipeline import enrich, semantics
    data = {'m_vecAbilityUpgrades': [{}, {}, {'m_vecPropertyUpgrades': [
        {'m_strPropertyName': 'MarksTotal', 'm_strBonus': '2'},
        {'m_strPropertyName': 'Damage', 'm_strBonus': '0.35', 'm_eUpgradeType': 'EAddToScale',
         'm_eScaleStatFilter': 'ETechPower'}]}]}
    path = 'm_vecAbilityUpgrades[2].m_vecPropertyUpgrades{Damage}.m_strBonus'
    parts = enrich.tier_scaling(data, path)
    assert parts == ['EAddToScale', 'ETechPower']
    assert enrich.tier_scaling(data, 'm_vecAbilityUpgrades[2].m_vecPropertyUpgrades{MarksTotal}.m_strBonus') is None
    # the bonus's sibling fields (its upgrade type, its property name) are plumbing, not a scaling bonus
    assert enrich.tier_scaling(data, 'm_vecAbilityUpgrades[2].m_vecPropertyUpgrades{Damage}.m_eUpgradeType') is None
    assert semantics.describe(path, {}, 'a', 'ability', None, None, parts)['label'] == 'T3: Damage (spirit scaling)'
    assert semantics.describe(path, {}, 'a', 'ability')['label'] == 'T3: Damage'
    # two bonuses to one property: flatten keys the scaling one apart, the bare key is the flat one (Explosive Barrel's
    # T3 "+40 Impact Damage" beside its "+0.25" scaling)
    twin = {'m_vecAbilityUpgrades': [{'m_vecPropertyUpgrades': [
        {'m_strPropertyName': 'ImpactDamage', 'm_strBonus': '40'},
        {'m_strPropertyName': 'ImpactDamage', 'm_strBonus': 0.25, 'm_eUpgradeType': 'EAddToScale',
         'm_eScaleStatFilter': 'ETechPower'}]}]}
    assert enrich.tier_scaling(twin, 'm_vecAbilityUpgrades[0].m_vecPropertyUpgrades{ImpactDamage}.m_strBonus') is None


def test_the_scaling_word_is_its_windows_own(monkeypatch):
    """One field can be a flat bonus in one build and a scaling one later (Warden's T3 Barrier +150): the canonical
    label stays plain, a window whose record says scaling adds the word."""
    from pipeline import labels, match
    path = 'm_vecAbilityUpgrades[2].m_vecPropertyUpgrades{Barrier}.m_strBonus'
    monkeypatch.setattr(labels, 'canonical', lambda key, d, fmap=None: {'label': 'T3: Barrier', 'unit': '', 'sign': ''})
    ce = {'kind': 'ability'}
    flat = match._window_change('abilities.vdata', 'a', {'path': path, 'op': 'add', 'new': 150, 'cat': 'balance'}, ce,
                                [1], False, {}, {})
    scaled = match._window_change('abilities.vdata', 'a', {'path': path, 'op': 'change', 'old': 1, 'new': 2,
                                                           'cat': 'balance',
                                                           'scale_parts': ['EAddToScale', 'ETechPower']}, ce,
                                  [2], False, {}, {})
    assert flat.shown == 'T3: Barrier' and scaled.shown == 'T3: Barrier (spirit scaling)'


def test_a_modifiers_attributes_read_as_its_effect():
    from pipeline.semantics import context_label
    assert context_label('m_AutoCastDelayModifier.m_nAttributes') == 'Auto Cast Delay effect'
    assert context_label('m_TargetModifier.m_nAttributes') == 'On target effect'
    assert context_label('m_Phase1Modifier.m_nAttributes') == 'Phase 1 effect'
    assert context_label('m_ProcEffectModifier.m_nAttributes') == 'Proc effect'       # not "Proc Effect effect"
    assert context_label('m_sModifier.m_nAttributes') == 'Effect'
    assert context_label('m_nAttributes') == 'Effect'


def test_an_items_series_keeps_one_order_whatever_the_run():
    """A set's order picked Superior Cooldown's renamed predecessor: two data runs gave two histories (and 11 items
    differed); the series are built in a fixed order now."""
    from pipeline.item_table import track
    a, b = {}, {}
    track(a, {}, 'x', 1, 'd', {'p:B': 1.0, 'p:A': 2.0})
    track(b, {}, 'x', 1, 'd', {'p:A': 2.0, 'p:B': 1.0})
    assert list(a['x']) == list(b['x']) == ['p:A', 'p:B']


def test_the_currency_is_souls_in_labels_the_game_never_wrote():
    from pipeline.semantics import describe, humanize
    assert humanize('m_flGoldPerMinuteAmount') == 'Souls Per Minute Amount'
    assert humanize('m_nTier1GoldKill') == 'Tier1 Kill Souls' and humanize('m_nTier1GoldOrbs') == 'Tier1 Soul Orbs'
    assert humanize('BonusBuffsPerGold') == 'Bonus Buffs Per Soul' and humanize('m_flPerGoldBonus') == 'Per Soul Bonus'
    assert humanize('m_flGoldenRatio') == 'Golden Ratio'
    assert describe('m_flRocketJumpForceUpBias', {}, 'x', 'ability')['label'] == 'Rocket Jump Upward Push'


def test_a_systems_console_variables_are_one_group_per_band():
    from builders.history_view import history_table
    r = {'id': 'p1', 'date': '2026-09-16', 'title': '09-16-2026 Update'}
    a = ch(key='convars:citadel_comeback_redirect_fraction', label='citadel_comeback_redirect_fraction',
           old_s='—', new_s='70%', op='add', path='citadel_comeback_redirect_fraction')
    b = ch(key='convars:citadel_tick_gold_pulse_per_period', label='citadel_tick_gold_pulse_per_period',
           old_s='3', new_s='2', path='citadel_tick_gold_pulse_per_period')
    keys = [('game:souls:sharing:convars', 'Console variables', None), ('game:souls:orbs:convars', 'Console variables',
                                                                           None)]
    by_ent = {'game:souls:sharing:convars': [(r, [a])], 'game:souls:orbs:convars': [(r, [b])]}
    html = history_table(keys, ['Souls'], by_ent, {}, '../', line_names=False,
                         areas={'game:souls:sharing:convars': 'sharing', 'game:souls:orbs:convars': 'orbs'},
                         merge=lambda names: ' · '.join(dict.fromkeys(names)))
    # one group holding both parts' variables, under both parts' filters
    assert html.count('class="hgroup') == 1 and 'data-area="sharing orbs"' in html
    assert 'citadel_comeback_redirect_fraction' in html and 'citadel_tick_gold_pulse_per_period' in html


# ---- 4. a broad line covers its scope ------------------------------------------------------------------------------

def test_the_shop_rework_lines_cover_shields_bounties_and_the_level_table():
    data = json.loads((ROOT / 'data' / 'overrides' / 'blanket_lines.json').read_text(encoding='utf-8'))
    from pipeline.match import _in_scope
    lines = {b['line']: b for b in data['lines'] if b['patch'] == '2025-05-08'}
    shields = lines['Shields have been reworked and are now called Barriers']['match']
    assert any(_in_scope(s, 'abilities.vdata', 'upgrade_headhunter',
                         'm_mapAbilityProperties.BulletShieldMaxHealth.m_strValue', 'remove', 'item') for s in shields)
    # the new barrier values are numbers the notes do not give: they keep the eye
    assert not any(_in_scope(s, 'abilities.vdata', 'upgrade_rocket_booster',
                             'm_mapAbilityProperties.CombatBarrier.m_strValue', 'add', 'item') for s in shields)
    bounties = lines['Neutral bounties increased by 6%']['match']
    assert any(_in_scope(s, 'npc_units.vdata', 'neutral_base', 'm_flGoldReward', 'change', 'neutral') for s in bounties)
    assert not any(_in_scope(s, 'npc_units.vdata', 'trooper_normal', 'm_flGoldReward', 'change', 'trooper')
                   for s in bounties)
    # an item's slot, tier and price stay hidden: the audit's verdicts call them real finds (Diviner's Kevlar,
    # Infuser, the tier prices)
    rework = lines['Full shop rework, including many new items']['match']
    assert not any(_in_scope(s, 'abilities.vdata', 'upgrade_diviners_kevlar', 'm_eItemSlotType', 'change', 'item')
                   for s in rework)


# ---- 5. one count ----------------------------------------------------------------------------------------------------

def test_a_parts_repeat_of_its_parent_counts_once_on_the_patch_page(monkeypatch):
    from builders import hero_page, patch_counts, shared_rows
    monkeypatch.setattr(shared_rows, 'catalog', _catalog)
    monkeypatch.setattr(hero_page, 'every_history_fold', lambda: {'ab_trigger': 'ab'})
    added = dict(op='add', label='Added to the game files', old_s='', new_s='', path='@add', status='described')
    parent = {'key': 'abilities.vdata:ab', 'file': 'abilities.vdata', 'id': 'ab', 'kind': 'ability', 'owner': 'hero_0',
              'name': 'Abstract Landscape', 'changes': [ch(key='abilities.vdata:ab:@add', **added)]}
    part = {'key': 'abilities.vdata:ab_trigger', 'file': 'abilities.vdata', 'id': 'ab_trigger', 'kind': 'ability',
            'owner': 'hero_0', 'name': 'Abstract Landscape',
            'changes': [ch(key='abilities.vdata:ab_trigger:@add', **added),
                        ch(key='abilities.vdata:ab_trigger:r', label='Radius', status='hidden')]}
    pages = frozenset({'heroes.vdata:hero_0', 'abilities.vdata:ab', 'abilities.vdata:ab_trigger'})
    rows = patch_counts.counted_rows({'entities': [parent, part]}, pages)
    assert [c['label'] for _, c, _ in rows] == ['Added to the game files', 'Radius']
    # the patch page's cards read the same entities: a part that only repeated its parent has no card
    only = {**part, 'changes': part['changes'][:1]}
    assert [e['id'] for e in patch_counts.fold_repeats([parent, only])] == ['ab']
    assert part['changes'][0]['label'] == 'Added to the game files'          # the record is not written into


def test_paint_the_town_counts_one_way_in_the_data():
    """The committed data: Violet's chip on the patch page counts what her home icon counts, the check line's buckets
    add up to the changes, Solomon's silent rework is hidden."""
    from builders import archive, patch_counts
    from builders.home_page import update_feed
    p = archive.patch('build-6790')
    c = patch_counts.for_id('build-6790')
    assert c['documented'] + c['described'] + c['not_in_notes'] + c['unreleased'] == c['changes']
    assert c['not_in_notes'] and not c.get('unannounced')
    chip = sum(1 for e, _, _ in patch_counts.counted_rows(p) if e and (e.get('owner') or e.get('id')) == 'hero_artist')
    feed = update_feed(p, frozenset(), patch_counts.unit_main(), patch_counts.page_set())
    assert chip == feed['heroes']['heroes.vdata:hero_artist']['n']
    solomon = feed['heroes']['heroes.vdata:hero_chessmaster']
    assert solomon['hidden'] == solomon['n'] > 0
