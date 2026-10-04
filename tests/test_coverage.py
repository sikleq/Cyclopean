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


def test_a_shared_row_carries_its_chip_and_a_rule_for_all_folds():
    from builders.cards import entity_rows
    from builders.shared_rows import spread
    some = spread(_block(), _cat(2))[0]['changes']
    html = entity_rows(some)
    assert 'Max Health <span class="chip shr">shared ×2 heroes</span>' in html and 'shr-all' not in html
    every = spread(_block('all'), _cat(2))[0]['changes']
    own = [ch(key='heroes.vdata:hero_0:regen', path='regen', label='Health Regen')]
    html = entity_rows(own + every)
    assert html.index('Health Regen') < html.index('<details class="fam shr-all has-hidden">')
    assert 'All heroes: 1 change' in html and 'chip shr' not in html


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
    assert 'All heroes: 6 changes' in band
    # the toolbar's eye counts the hero's own rows only (the level rows are hidden, the own one documented)
    assert 'Not in patch notes' not in html


def test_a_band_with_only_a_rule_for_all_is_muted_and_stays_closed():
    html = _bands(every_only=True)
    assert re.search(r'<details class="pblock[^"]*" id="p-p2"(?![^>]*open)', html)
    assert 'class="ps-tile shr"' in html and 'changes for all heroes' in html


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

def test_only_hidden_is_not_in_notes():
    """Work before release has its own switch and an update without notes hides nothing: neither is the eye."""
    from builders.cards import is_hidden, row
    assert 'is-hidden' in row('hidden', '', 'x') and 'is-hidden' not in row('unreleased', '', 'x')
    assert 'is-hidden' not in row('unannounced', '', 'x')
    assert is_hidden([ch()]) and not is_hidden([ch(status='unreleased')])


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


def test_one_count_per_patch(monkeypatch):
    from builders import patch_counts, shared_rows
    monkeypatch.setattr(shared_rows, 'catalog', lambda: _cat(2))
    c = patch_counts.count(_patch(), frozenset(), {})
    # plumbing (the particle) is no change; the shared block counts once; the unreleased row apart
    assert c['changes'] == 5 and c['hidden'] == 3 and c['unreleased'] == 1 and c['documented'] == 1
    assert c['hidden_on_pages'] == 2 and patch_counts.off_pages(c) == 1          # the pickup has no page


def test_the_patch_page_list_and_home_say_the_same_number(monkeypatch):
    from builders import home_page, patch_counts, patches_pages, shared_rows
    p = _patch()
    monkeypatch.setattr(shared_rows, 'catalog', lambda: _cat(2))
    monkeypatch.setattr(patch_counts, 'for_id', lambda pid: patch_counts.count(p, frozenset(), {}))
    monkeypatch.setattr(home_page, 'load_json', lambda rel: p)
    audit = patches_pages._audit_line(p)
    assert '<b>3</b> not in patch notes' in audit and '<b>1</b> of them in game rules' in audit
    row = patches_pages._index_row({**p, 'has_notes': True, 'builds': 1}, {}, '../', False)
    assert re.search(r'au-hidden">.*?<b>3</b>', row)
    feed = home_page._feed([{'id': 'p1', 'title': p['title'], 'date': p['date']}], {}, frozenset(), {})
    assert re.search(r'au-hidden">.*?<b>3</b> not in patch notes', feed)


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
def test_victor_has_the_heavy_melee_of_2025_07_29(history):
    band = _band(history, [('heroes.vdata:hero_frank', 'Base stats', None),
                           ('abilities.vdata:ability_melee_frank', 'Melee', None)], '2025-07-29')
    assert re.search(r'Heavy melee › Cooldown On Hit\s.*?0\.9.*?1\b', band, re.S)


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
    n = patch_counts.for_id(pid)['hidden']
    p = load_json(f'patches/{pid}.json.gz')
    html = patches_pages.patch_page(p, None, None)
    audit = html[html.index('class="sum-audit"'):]
    assert re.search(rf'<b>{n}</b> not in patch notes', audit)
    assert f'Not in patch notes <span class="n">{n}</span>' in html
    row = next(r for r in load_json('patches/index.json') if r['id'] == pid)
    assert re.search(rf'au-hidden">.*?<b>{n}</b>', patches_pages._index_row(row, {}, '../', False))
    feed = home_page._feed([row], {}, frozenset(), {})
    assert re.search(rf'<b>{n}</b> not in patch notes', feed)
