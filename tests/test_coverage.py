"""Every change lands on a page (coverage audit 2026-10-05, owner: "I want to see ALL changes to everything in the
game"), and one count of what the patch notes left out.

- An edit the files copy into many entities ('@shared') keeps the KEYS of the entities it hit (pipeline/shared_groups.py)
  and is spread back over them on every hero / item / unit view (builders/shared_rows.py): 13,573 hero × row pairs and
  278 hero patch bands were on no hero page. A block on some of them is an ordinary row with a chip "shared ×N heroes";
  a rule for (almost) all of them folds into "All heroes: N changes" and is counted apart.
- "Not in patch notes" is one status and one count per patch (builders/patch_counts.py): City Never Sleeps read 1232
  on its page, 620 under "Only hidden" and 212 on the home page."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def ch(**kw):
    base = {'op': 'change', 'cat': 'balance', 'label': 'Cooldown', 'old_s': '27', 'new_s': '29', 'dir': 'nerf',
            'pct': 7.4, 'grad': 2, 'status': 'hidden', 'path': 'x'}
    base.update(kw)
    return base


def _cat(n_heroes=10, **extra):
    """A catalog: n released heroes in the files since build 100, hero_base (a template), a hero added in build 200."""
    cat = {f'heroes.vdata:hero_{i}': {'file': 'heroes.vdata', 'id': f'hero_{i}', 'kind': 'hero', 'name': f'Hero {i}',
                                      'first': [100, '2025-01-01'], 'last': [300, '2026-10-01']}
           for i in range(n_heroes)}
    cat['heroes.vdata:hero_base'] = {'file': 'heroes.vdata', 'id': 'hero_base', 'kind': 'hero', 'template': True,
                                     'first': [100, '2025-01-01'], 'last': [300, '2026-10-01']}
    cat['heroes.vdata:hero_new'] = {'file': 'heroes.vdata', 'id': 'hero_new', 'kind': 'hero',
                                    'first': [200, '2026-05-01'], 'last': [300, '2026-10-01']}
    cat.update(extra)
    return cat


WINDOW = ((200, '2026-05-01'), (201, '2026-05-02'))      # hero_new was added in the window's first build


# ---- pipeline: the '@shared' blocks keep their targets' keys ----------------------------------------------------

def test_a_shared_block_keeps_its_targets_keys_and_their_own_statuses():
    from pipeline.shared_groups import SharedGroups
    groups = SharedGroups()
    sig = ('heroes.vdata', 'm_mapStartingStats.EMaxHealth', '740', '730')
    for i, status in ((0, 'hidden'), (1, 'documented'), (2, 'unreleased')):
        first = ch(key=f'heroes.vdata:hero_{i}:p', status=status) if sig not in groups else None
        groups.add(sig, first, f'Hero {i}', f'heroes.vdata:hero_{i}', status)
    [ent] = groups.entities(_cat(), WINDOW, {'heroes.vdata': 'All heroes'})
    assert ent['target_keys'] == ['heroes.vdata:hero_0', 'heroes.vdata:hero_1', 'heroes.vdata:hero_2']
    assert ent['targets'] == ['Hero 0', 'Hero 1', 'Hero 2'] and ent['scope'] == 'some'
    [c] = ent['changes']
    # the block takes the most noted status; a target that differs keeps its own (a line named only that hero)
    assert c['status'] == 'documented'
    assert c['target_status'] == {'heroes.vdata:hero_0': 'hidden', 'heroes.vdata:hero_2': 'unreleased'}


def test_target_keys_are_never_fewer_than_the_names():
    """Two heroes under one name (a rename, "Melee") are one name but two pages."""
    from pipeline.shared_groups import SharedGroups
    groups = SharedGroups()
    sig = ('heroes.vdata', 'p', '1', '2')
    groups.add(sig, ch(), 'Same', 'heroes.vdata:hero_0', 'hidden')
    groups.add(sig, None, 'Same', 'heroes.vdata:hero_1', 'hidden')
    [ent] = groups.entities(_cat(), WINDOW, {})
    assert len(ent['target_keys']) == 2 and len(ent['targets']) == 1


def test_blocks_on_other_target_sets_stay_apart():
    """Two edits on different heroes whose first names agree were one block named after the first set."""
    from pipeline.shared_groups import SharedGroups
    groups = SharedGroups()
    for sig, keys in ((('heroes.vdata', 'a', '1', '2'), (0, 1, 2)), (('heroes.vdata', 'b', '1', '2'), (0, 1, 3))):
        for i in keys:
            groups.add(sig, ch(path=sig[1]) if sig not in groups else None, 'X', f'heroes.vdata:hero_{i}', 'hidden')
    ents = groups.entities(_cat(), WINDOW, {})
    assert len(ents) == 2 and len({e['key'] for e in ents}) == 2


def test_a_block_on_almost_every_hero_is_a_rule_for_all():
    """Counted over the heroes the window could diff: not a template, not one added inside the window."""
    from pipeline.shared_groups import scope
    cat = _cat(10)
    nine = tuple(f'heroes.vdata:hero_{i}' for i in range(9)) + ('heroes.vdata:hero_base',)
    assert scope('heroes.vdata', nine, cat, WINDOW) == 'all'
    assert scope('heroes.vdata', nine[:5], cat, WINDOW) == 'some'
    assert scope('heroes.vdata', nine, cat, None) == 'some'
    # one sub-ability among the items does not put every sub-ability under the measure
    items = {f'abilities.vdata:upgrade_{i}': {'file': 'abilities.vdata', 'id': f'upgrade_{i}', 'kind': 'item',
                                              'first': [100, '2025-01-01'], 'last': [300, '2026-10-01']}
             for i in range(20)}
    others = {f'abilities.vdata:sub_{i}': {'file': 'abilities.vdata', 'id': f'sub_{i}', 'kind': 'ability_other',
                                           'first': [100, '2025-01-01'], 'last': [300, '2026-10-01']}
              for i in range(30)}
    keys = tuple(items) + ('abilities.vdata:sub_0',)
    assert scope('abilities.vdata', keys, {**items, **others}, WINDOW) == 'all'


def test_window_of_takes_the_first_and_last_build():
    from pipeline.shared_groups import window_of
    builds = [{'build': 201, 'date': '2026-05-02 10:00'}, {'build': 200, 'date': '2026-05-01 09:00'}]
    assert window_of(builds) == ((200, '2026-05-01'), (201, '2026-05-02'))
    assert window_of([]) is None


# ---- builders: spread over the targets ---------------------------------------------------------------------------

def _block(scope='some', keys=('heroes.vdata:hero_0', 'heroes.vdata:hero_1', 'heroes.vdata:hero_base'), **kw):
    return {'key': '@shared:heroes.vdata:3:x', 'file': 'heroes.vdata', 'id': '@shared', 'kind': 'shared',
            'name': 'All heroes (3)', 'targets': ['Hero 0', 'Hero 1', 'hero_base'], 'target_keys': list(keys),
            'scope': scope, 'changes': [ch(key='heroes.vdata:hero_0:hp', path='hp', label='Max Health', old_s='740',
                                           new_s='730', target_status={'heroes.vdata:hero_1': 'documented'}, **kw)]}


def test_a_shared_block_spreads_over_its_targets():
    from builders.shared_rows import entities, spread
    out = spread(_block(), _cat(2))
    assert [e['key'] for e in out] == ['heroes.vdata:hero_0', 'heroes.vdata:hero_1']      # the template has no page
    c0, c1 = out[0]['changes'][0], out[1]['changes'][0]
    assert c0['key'] == 'heroes.vdata:hero_0:hp' and c1['key'] == 'heroes.vdata:hero_1:hp'
    assert (c0['status'], c1['status']) == ('hidden', 'documented') and 'target_status' not in c1
    assert c0['shared_n'] == 2 and c0['shared_what'] == 'heroes' and not c0['shared_all']
    own = {'key': 'heroes.vdata:hero_0', 'file': 'heroes.vdata', 'id': 'hero_0', 'changes': [ch()]}
    assert spread(own) == [own]
    assert spread({**_block(), 'target_keys': None}) == []              # a block written before target_keys
    assert len(entities([own, _block()], _cat(2))) == 3


def test_the_archive_names_a_block_by_what_it_covers():
    """Every block read "All heroes (N)", nine heroes' Max Health too."""
    from builders.shared_rows import block_name
    assert block_name(_block(), _cat(2)) == '2 heroes'
    assert block_name(_block('all'), _cat(2)) == 'All heroes (2)'


def test_a_shared_row_carries_its_chip_and_a_rule_for_all_is_a_link_row():
    """A rule for every hero is ONE row linking to its Game page's band — not the rows folded on every hero page
    (heroes/ grew from 13 to 37 MB with them, review 2026-10-05)."""
    from builders.cards import entity_rows
    from builders.shared_rows import spread
    some = spread(_block(), _cat(2))[0]['changes']
    html = entity_rows(some)
    assert 'Max Health <span class="chip shr">shared ×2 heroes</span>' in html and 'shr-all' not in html
    every = spread(_block('all'), _cat(2))[0]['changes']
    own = [ch(key='heroes.vdata:hero_0:regen', path='regen', label='Health Regen')]
    html = entity_rows(own + every, None, lambda sid: f'../game/{sid}.html#p-p9')
    assert html.index('Health Regen') < html.index('shr-all')
    assert 'All heroes: 1 change' in html and 'chip shr' not in html and '<details' not in html
    assert 'href="../game/progression.html#p-p9">Hero progression ›</a>' in html
    # a way to the Game page, not a change: no eye stripe, no status mark (the rows' marks are there)
    link = html[html.index('<div class="erow st-shared'):]
    assert 'is-hidden' not in link[:link.index('>')] and 'class="mark' not in link


def _bands(every_only: bool = False):
    from builders.history_view import history_table
    from builders.shared_rows import spread
    r1 = {'id': 'p1', 'date': '2026-01-01', 'title': '01-01-2026 Update'}
    r2 = {'id': 'p2', 'date': '2026-02-01', 'title': '02-01-2026 Update'}
    every = spread({**_block('all'), 'changes': [
        ch(key='heroes.vdata:hero_0:l1', path=f'l{i}', label=f'Level {i}: souls needed', dir='buff', pct=-10.0,
           old_s=str(1000 * i), new_s=str(900 * i)) for i in range(2, 8)]}, _cat(2))[0]['changes']
    own = [ch(key='heroes.vdata:hero_0:hp', label='Max Health', status='documented')]
    by_ent = {'heroes.vdata:hero_0': [(r2, every if every_only else own + every), (r1, [{**c} for c in own])]}
    return history_table([('heroes.vdata:hero_0', 'Base stats', None)], ['Hero 0'], by_ent, {}, '../')


def test_a_rule_for_all_is_counted_apart_on_the_band_and_the_strip():
    html = _bands()
    band = html[html.index('id="p-p2"'):html.index('id="p-p1"')]
    summary = band[:band.index('</summary>')]
    assert '+6 for all heroes' in summary
    assert 'class="pip nerf' in summary and 'class="pip buff' not in summary      # the own NERF only
    assert 'All heroes: 6 changes' in band and 'href="../game/progression.html#p-p2"' in band
    # the toolbar offers no tag only the rule for all has (a link row no tag filter keeps)
    bar = html[html.index('hist-bar'):html.index('id="history"')]
    assert 'data-f-tag="buff"' not in bar and 'data-f-tag="nerf"' in bar
    # the toolbar's eye counts the hero's own rows only (the level rows are hidden, the own one documented)
    assert 'Not in patch notes' not in html


def test_a_rule_for_all_is_one_link_row_per_band_whatever_it_touched():
    """Review 2026-10-05: Calico's 2026-01-22 band repeated "All abilities & items: 1 change" under 15 abilities and
    its chip read "+9 for all abilities & items" for ONE rule; a melee rule kept its own link and chip."""
    from builders.history_view import history_table
    r = {'id': 'p1', 'date': '2026-01-22', 'title': '01-22-2026 Update'}
    rule = dict(path='m_mapAbilityProperties.AbilityCooldownBetweenCharge.m_strValue', label='Charge Delay',
                old_s='0s', new_s='default', dir='changed', pct=None, file='abilities.vdata',
                shared_all=True, shared_n=568, shared_what='abilities & items')
    melee = dict(path='m_mapAbilityProperties.MeleeDamageTakenScale.m_strValue', label='Melee Damage Taken Scale',
                 old_s='35', new_s='—', op='remove', file='abilities.vdata', shared_all=True, shared_n=53,
                 shared_what='melee attacks')
    keys = [('heroes.vdata:hero_nano', 'Base stats', None)] + [(f'abilities.vdata:ab_{i}', f'Ability {i}', None)
                                                                for i in range(3)]
    by_ent = {f'abilities.vdata:ab_{i}': [(r, [ch(key=f'abilities.vdata:ab_{i}:own', label='Cooldown'),
                                              ch(key=f'abilities.vdata:ab_{i}:rule', **rule)]
                                           + ([ch(key=f'abilities.vdata:ab_{i}:melee', **melee)] if i == 0 else []))]
              for i in range(3)}
    html = history_table(keys, ['Calico'], by_ent, {}, '../', areas={k: 'abil' for k, _, _ in keys})
    band = html[html.index('id="p-p1"'):]
    assert band.count('All abilities &amp; items: 1 change') == 1 and band.count('All melee attacks: 1 change') == 1
    assert band.count('class="hgroup shr-band"') == 1
    summary = band[:band.index('</summary>')]
    assert '+1 for all abilities &amp; items' in summary and '+1 for all melee attacks' in summary
    # the band's own counters: the three abilities' own rows, not the rules
    assert 'class="pip nerf">3<' in summary


def test_a_band_with_only_a_rule_for_all_waits_behind_its_button():
    """Review 2026-10-05: 23% of the bands held only "+N for all heroes"; they stay in place, folded, behind
    "For all" (like "Before release"), and get no strip tile — as in the matrices and the trail squares."""
    html = _bands(every_only=True)
    assert re.search(r'<details class="pblock[^"]*every-only[^"]*" id="p-p2"(?![^>]*open)', html)
    assert 'ps-tile' not in html                     # only the hero's own band p1 is left: no strip of one tile
    assert 'data-toggle-class="show-every"' in html and 'For all <span class="n">1</span>' in html
    # the band with the hero's own change stands open
    assert re.search(r'<details class="pblock[^"]*" id="p-p1"[^>]* open', html)


def test_the_home_feed_spreads_some_and_skips_rules_for_all(monkeypatch):
    from builders import shared_rows
    from builders.home_page import update_feed
    monkeypatch.setattr(shared_rows, 'catalog', lambda: _cat(2))
    feed = update_feed({'entities': [_block(), _block('all')]})
    heroes = feed['heroes']
    assert set(heroes) == {'heroes.vdata:hero_0', 'heroes.vdata:hero_1'}
    assert heroes['heroes.vdata:hero_0']['n'] == 1 and heroes['heroes.vdata:hero_0']['hidden'] == 1
    assert heroes['heroes.vdata:hero_1']['hidden'] == 0              # documented for that hero


# ---- one count of "not in patch notes" -------------------------------------------------------------------------

def test_not_in_notes_is_hidden_and_every_change_of_an_update_without_notes():
    """Work before release has its own switch; an update with no notes at all (Rat King's build 6736) is not in the
    notes either — its rows lost the eye and dropped out of the eye filter (review 2026-10-05)."""
    from builders.cards import is_hidden, row
    assert 'is-hidden' in row('hidden', '', 'x') and 'is-hidden' not in row('unreleased', '', 'x')
    assert 'is-hidden' in row('unannounced', '', 'x')
    assert is_hidden([ch()]) and is_hidden([ch(status='unannounced')]) and not is_hidden([ch(status='unreleased')])


def test_a_band_of_an_update_without_notes_says_so():
    from builders.history_view import history_table
    r = {'id': 'build-6736', 'date': '2026-09-30', 'title': 'Listen up'}
    by_ent = {'heroes.vdata:hero_0': [(r, [ch(key='heroes.vdata:hero_0:hp', status='unannounced')])]}
    html = history_table([('heroes.vdata:hero_0', 'Base stats', None)], ['Hero 0'], by_ent, {}, '../')
    assert 'no patch notes' in html and 'Not in patch notes <span class="n">1</span>' in html


def _patch():
    misc = {'key': 'misc.vdata:pickup', 'file': 'misc.vdata', 'id': 'pickup', 'kind': 'global', 'name': 'Pickup',
            'changes': [ch(key='misc.vdata:pickup:a', label='Respawn Time')]}
    hero = {'key': 'abilities.vdata:ab', 'file': 'abilities.vdata', 'id': 'ab', 'kind': 'ability', 'owner': 'hero_0',
            'name': 'Charge', 'changes': [ch(key='abilities.vdata:ab:a', label='Radius'),
                                          ch(key='abilities.vdata:ab:b', label='Range', status='unreleased'),
                                          ch(key='abilities.vdata:ab:c', label='Particle', path='m_strParticle',
                                             old_s='A_B', new_s='C_D')]}
    item = {'key': 'abilities.vdata:upgrade_x', 'file': 'abilities.vdata', 'id': 'upgrade_x', 'kind': 'item',
            'name': 'X', 'changes': [ch(key='abilities.vdata:upgrade_x:a', status='documented')]}
    return {'id': 'p1', 'title': '01-01-2026 Update', 'date': '2026-01-01', 'sections': [{'lines': []}],
            'line_counts': {}, 'builds': [], 'entities': [misc, hero, item, _block()]}


PAGES = frozenset({'heroes.vdata:hero_0', 'heroes.vdata:hero_1', 'abilities.vdata:ab', 'abilities.vdata:upgrade_x'})


def test_one_count_per_patch(monkeypatch):
    from builders import patch_counts, shared_rows
    monkeypatch.setattr(shared_rows, 'catalog', lambda: _cat(2))
    c = patch_counts.count(_patch(), PAGES)
    # plumbing (the particle) is no change; the shared block counts once; the unreleased row apart
    assert c['changes'] == 5 and c['hidden'] == 3 and c['unreleased'] == 1 and c['documented'] == 1
    assert c['not_in_notes'] == 3
    assert c['hidden_on_pages'] == 2 and patch_counts.off_pages(c) == 1          # the pickup has no page


def test_off_pages_are_what_the_pages_do_not_show(monkeypatch):
    """`hidden_on_pages` counts by THE pages (entities_pages.page_keys): a helper unit and an ability a unit binds
    have unit pages, though home_page.page_of gives them none — they read "in game rules & map objects"."""
    from builders import patch_counts, shared_rows
    monkeypatch.setattr(shared_rows, 'catalog', lambda: _cat(2))
    helper = {'key': 'npc_units.vdata:bot', 'file': 'npc_units.vdata', 'id': 'bot', 'kind': 'helper', 'name': 'bot',
              'changes': [ch(key='npc_units.vdata:bot:a', label='Health')]}
    stomp = {'key': 'abilities.vdata:stomp', 'file': 'abilities.vdata', 'id': 'stomp', 'kind': 'ability_other',
             'units': ['bot'], 'name': 'Stomp', 'changes': [ch(key='abilities.vdata:stomp:a', label='Radius')]}
    urn = {'key': 'misc.vdata:urn', 'file': 'misc.vdata', 'id': 'urn', 'kind': 'global', 'name': 'Urn',
           'changes': [ch(key='misc.vdata:urn:a', label='Bounty', status='unannounced')]}
    p = {'entities': [helper, stomp, urn]}
    c = patch_counts.count(p, frozenset({'npc_units.vdata:bot', 'abilities.vdata:stomp'}))
    assert c['not_in_notes'] == 3 and c['hidden_on_pages'] == 2 and patch_counts.off_pages(c) == 1
    # with no pages at all, all three would be the Game's
    assert patch_counts.off_pages(patch_counts.count(p, frozenset())) == 3


def test_the_patch_page_list_and_home_say_the_same_number(monkeypatch):
    from builders import archive, home_page, patch_counts, patches_pages, shared_rows
    p = _patch()
    monkeypatch.setattr(shared_rows, 'catalog', lambda: _cat(2))
    monkeypatch.setattr(patch_counts, 'for_id', lambda pid: patch_counts.count(p, PAGES))
    monkeypatch.setattr(archive, 'patch', lambda pid: p)          # the build's shared archive (builders/archive.py)
    audit = patches_pages._audit_line(p)
    assert '<b>3</b> not in patch notes' in audit and '<b>1</b> of them in game rules' in audit
    row = patches_pages._index_row({**p, 'has_notes': True, 'builds': 1}, {}, '../', False)
    assert re.search(r'au-hidden">.*?<b>3</b>', row)
    feed = home_page._feed([{'id': 'p1', 'title': p['title'], 'date': p['date']}], {}, frozenset(), {})
    # review 2026-10-05: the count is a way in — the patch page with its eye filter pressed
    assert re.search(r'<a class="au au-hidden" href="patches/p1.html#hidden">.*?<b>3</b> not in patch notes', feed)
    assert '<a class="au au-hidden" href="#hidden">' in audit


def test_the_home_icons_go_where_the_pages_are_and_count_like_the_banner(monkeypatch):
    """Review 2026-10-05: the home icons routed by the patch record's name, so Medic Trooper and Neutral bug (name ==
    id there) fell off the home page while their pages showed the rows (6736: banner 39, icons 27 + 2); one edit on a
    family's members counted once on its icon and on every member in the banner."""
    from builders import home_page, patch_counts, shared_rows
    stomp = {'file': 'abilities.vdata', 'id': 'stomp', 'kind': 'ability_other', 'units': ['bot'], 'name': 'Stomp'}
    monkeypatch.setattr(shared_rows, 'catalog', lambda: _cat(2, **{'abilities.vdata:stomp': stomp}))
    monkeypatch.setattr(patch_counts, 'unit_main', lambda: {'bot': 'bot', 'bot_alt': 'bot', 'trooper_medic': 'trooper_medic'})
    medic = {'key': 'npc_units.vdata:trooper_medic', 'file': 'npc_units.vdata', 'id': 'trooper_medic', 'kind': 'trooper',
             'name': 'trooper_medic', 'changes': [ch(key='npc_units.vdata:trooper_medic:a', label='Sight range')]}
    bots = [{'key': f'npc_units.vdata:{b}', 'file': 'npc_units.vdata', 'id': b, 'kind': 'helper', 'name': b,
             'changes': [ch(key=f'npc_units.vdata:{b}:r', label='Respawn Time', old_s='30s', new_s='15s')]}
            for b in ('bot', 'bot_alt')]
    ab = {**stomp, 'key': 'abilities.vdata:stomp', 'changes': [ch(key='abilities.vdata:stomp:a', label='Radius')]}
    p = {'entities': [medic, *bots, ab]}
    pages = frozenset({'npc_units.vdata:trooper_medic', 'npc_units.vdata:bot', 'npc_units.vdata:bot_alt',
                       'abilities.vdata:stomp'})
    feed = home_page.update_feed(p, frozenset(), patch_counts.unit_main(), pages)
    assert set(feed) == {'units'} and set(feed['units']) == {'npc_units.vdata:trooper_medic', 'npc_units.vdata:bot'}
    assert feed['units']['npc_units.vdata:bot']['n'] == 2                       # Respawn Time once, Stomp's Radius
    c = patch_counts.count(p, pages)
    assert sum(v['hidden'] for v in feed['units'].values()) == c['hidden_on_pages'] == 3


# ---- on the real data (data/ regenerated with target_keys) ------------------------------------------------------

def _has_target_keys() -> bool:
    from builders.common import load_json
    for row in reversed(load_json('patches/index.json')):
        for e in load_json(f'patches/{row["id"]}.json.gz')['entities']:
            if e.get('id') == '@shared':
                return 'target_keys' in e
    return False


needs_keys = pytest.mark.skipif(not _has_target_keys(), reason='data/patches predates target_keys: regenerate')


@pytest.fixture(scope='module')
def history():
    from builders.entities_pages import _history
    return _history()


def _band(history, keys, pid):
    from builders.history_view import history_table
    by_ent, by_subject = history
    html = history_table(keys, [], by_ent, by_subject, '../')
    i = html.index(f'id="p-{pid}"')
    j = html.find('<details class="pblock', i)
    return re.sub(r'<[^>]+>', ' ', html[i:j if j > 0 else len(html)])


@needs_keys
def test_haze_has_her_max_health_of_2026_05_22(history):
    band = _band(history, [('heroes.vdata:hero_haze', 'Base stats', None)], '2026-05-22')
    assert re.search(r'Max Health\s+shared ×\d+ heroes.*?740.*?730', band, re.S)


@needs_keys
def test_abrams_has_the_dash_of_2026_07_28(history):
    band = _band(history, [('heroes.vdata:hero_atlas', 'Base stats', None)], '2026-07-28')
    assert re.search(r'Ground Dash Duration.*?0\.7s.*?0\.72s', band, re.S)


@needs_keys
def test_victor_links_to_the_heavy_melee_of_2025_07_29(history):
    """A rule for every melee attack: a link row on Victor's band, its rows on Game › Movement & combat."""
    band = _band(history, [('heroes.vdata:hero_frank', 'Base stats', None),
                           ('abilities.vdata:ability_melee_frank', 'Melee', None)], '2025-07-29')
    assert re.search(r'All melee attacks: \d+ changes\s+Movement &(?:amp;)? combat ›', band)
    by_ent, _ = history
    rows = [c for row, ch in by_ent['game:all:abilities.vdata'] if row['id'] == '2025-07-29' for c in ch]
    assert any(c['label'] == 'Heavy melee › Cooldown On Hit' and c['old_s'] == '0.9' for c in rows)


def _hero_keys(hid: str) -> list[tuple]:
    from builders.common import load_json
    return [(f'heroes.vdata:{hid}', 'Base stats', None)] + [
        (f"abilities.vdata:{e['id']}", e.get('name') or e['id'], None) for e in load_json('entities.json')['entities']
        if e['file'] == 'abilities.vdata' and e.get('owner') == hid]


@needs_keys
def test_haze_reads_channel_move_speed_of_2025_08_18_as_a_rule_for_all(history):
    """Review 2026-10-05: "50m/s → 1.3m/s −97.4% NERF" (engine units against metres) and "50 → no limit" as rows
    with a chip "shared ×491" on 268 pages; it is every ability's and item's, one link row."""
    band = _band(history, _hero_keys('hero_haze'), '2025-08-18')
    assert '97.4' not in band and not re.search(r'Channel Move Speed', band)
    assert re.search(r'All [a-z &;]+: \d+ changes?\s+Movement &(?:amp;)? combat ›', band)


@needs_keys
def test_haze_was_not_released_on_september_29(history):
    """heroes.vdata moved "Player Selectable" into "Hero Development State" on 2026-09-29: no change for her."""
    band = _band(history, _hero_keys('hero_haze'), '2026-09-29')
    assert 'Development State' not in band and 'Player Selectable' not in band


@needs_keys
def test_the_announced_dash_of_2026_07_28_is_not_hidden(history):
    """"Stamina bucket 3 heroes … ground dash time increased from 0.7s to 0.72s": the alias "dash" named the Dash
    ability, which did not move; the pair is Abrams' (and nine others')."""
    by_ent, _ = history
    rows = [c for row, ch in by_ent['heroes.vdata:hero_atlas'] if row['id'] == '2026-07-28' for c in ch
            if 'DashDuration' in c['path']]
    assert len(rows) == 2 and all(c['status'] in ('documented', 'described') for c in rows)


@needs_keys
def test_every_shared_block_keeps_as_many_keys_as_names():
    from builders.common import load_json
    for row in load_json('patches/index.json'):
        for e in load_json(f'patches/{row["id"]}.json.gz')['entities']:
            if e.get('id') == '@shared':
                assert len(e['target_keys']) >= len(e['targets']), (row['id'], e['key'])
                assert e['scope'] in ('all', 'some')


def test_city_never_sleeps_says_one_number_everywhere():
    """The patch page's check line and eye filter, the patch list and the home banner: one count."""
    from builders import home_page, patch_counts, patches_pages
    from builders.common import load_json
    pid = '2026-09-29'
    n = patch_counts.for_id(pid)['not_in_notes']
    p = load_json(f'patches/{pid}.json.gz')
    html = patches_pages.patch_page(p, None, None)
    audit = html[html.index('class="sum-audit"'):]
    assert re.search(rf'<b>{n}</b> not in patch notes', audit)
    assert f'Not in patch notes <span class="n">{n}</span>' in html
    row = next(r for r in load_json('patches/index.json') if r['id'] == pid)
    assert re.search(rf'au-hidden">.*?<b>{n}</b>', patches_pages._index_row(row, {}, '../', False))
    feed = home_page._feed([row], {}, frozenset(), {})
    assert re.search(rf'<b>{n}</b> not in patch notes', feed)
