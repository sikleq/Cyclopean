"""An entity's history (builders/history_view.py): bands, groups, the patch strip and its tiles."""
import re

from tests.helpers import ch, site_css, site_js


def test_hero_page_lines_drop_the_hero_name():
    from builders.history_view import _drop_prefix          # (hero_page._strip_subject had no caller left)
    assert _drop_prefix('Abrams: Melee damage per boon increased by 10%', ['Abrams']) == \
        'Melee damage per boon increased by 10%'
    # another subject stays: the line is about the ability, not the hero
    assert _drop_prefix('Seismic Impact: Damage increased', ['Abrams']) == 'Seismic Impact: Damage increased'


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


def test_one_band_never_shows_two_groups_of_one_name():
    """Review 2026-10-05: two "Weapon (shotgun)" groups with the same rows, Kelvin's "Frozen Shelter" for the ability
    and its trigger, Wrecker's old and new "Wrecking Ball": identical rows under one name are one group, other ones
    say which is which."""
    from builders.history_view import history_table
    r1 = {'id': 'p1', 'date': '2026-01-01', 'title': '01-01-2026 Update'}
    keys = [('heroes.vdata:h', 'Base stats', None), ('abilities.vdata:gun', 'Weapon (shotgun)', None),
            ('abilities.vdata:gun_shared_base', 'Weapon (shotgun)', None), ('abilities.vdata:dome', 'Frozen Shelter', None),
            ('abilities.vdata:dome_trigger', 'Frozen Shelter', None), ('abilities.vdata:ball', 'Wrecking Ball', None),
            ('abilities.vdata:ball2', 'Wrecking Ball', None)]
    same = [ch(key='x', path='falloff', label='Falloff Start', old_s='22m', new_s='19.99m')]
    by_ent = {'abilities.vdata:gun': [(r1, same)], 'abilities.vdata:gun_shared_base': [(r1, [dict(c) for c in same])],
              'abilities.vdata:dome': [(r1, [ch(key='d', path='r', label='Radius')])],
              'abilities.vdata:dome_trigger': [(r1, [ch(key='t', path='w', label='Width')])],
              'abilities.vdata:ball': [(r1, [ch(key='b', path='r', label='Radius')])],
              'abilities.vdata:ball2': [(r1, [ch(key='b2', path='s', label='Speed')])]}
    html = history_table(keys, ['Hero'], by_ent, {}, '../', gone={'abilities.vdata:ball'})
    names = re.findall(r'<span class="nm">([^<]*)</span>', html)
    assert names.count('Weapon (shotgun)') == 1 and 'data-ab="gun gun_shared_base"' in html
    assert 'Frozen Shelter' in names and 'Frozen Shelter · trigger' in names
    assert names.count('Wrecking Ball') == 1 and 'Wrecking Ball (old version)' in names


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
    assert 'Can now cancel Shoulder Charge' in html and 'Fixed a bug' in html
    assert 'Technical' not in html and 'data-ab="ab_charge" data-area="abil"' in html
    # the toolbar: tags present, the eye, parts; the newest block in the page, the older one lazy
    assert 'data-f-tag="buff"' in html and 'data-f-tag="nerf"' in html and 'data-f-area="stats"' in html
    assert 'Not in patch notes' in html and html.index('id="p-p2"') < html.index('id="p-p1"')
    assert '<template class="hp-t">' in html.split('id="p-p1"')[1] and 'template' not in html.split('id="p-p1"')[0]
    # the old patch had only work on a hero in development: hidden behind the switch
    assert 'pblock dev-only' in html and 'Before release' in html
    released = history_view.history_table(keys, ['Abrams'], by_ent, by_subject, '../', areas=areas, in_dev=True)
    assert 'dev-only' not in released and 'hblocks show-dev' in released


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
    assert '2 changes, 2 not in patch notes' in strip and 'all 2 not in patch notes' in html


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
    monkeypatch.setattr(archive, 'change_anchors', lambda pid: frozenset({'upgrade_x', 'bot'}))
    assert patch_href('p2', '../', 'upgrade_x') == '../patches/p2.html#n-upgrade_x'
    assert patch_href('p1', '../', 'upgrade_x') == '../patches/p1.html#c-upgrade_x'
    assert patch_href('p1', '../') == '../patches/p1.html'
    # review 2026-10-05: 2,112 of 6,295 band links pointed at an id the patch page has no place for — the page itself
    # then; a unit family's band lands on the member the patch page has a card for
    assert patch_href('p1', '../', 'hero_astro') == '../patches/p1.html'
    assert patch_href('p1', '../', 'bot_weak', ['bot_weak', 'bot']) == '../patches/p1.html#c-bot'
    r1 = {'id': 'p1', 'date': '2026-01-01', 'title': '01-01-2026 Update'}
    key = 'abilities.vdata:upgrade_x'
    html = history_table([(key, 'X', None)], ['X'], {key: [(r1, [ch(key='a')])]}, {}, '../')
    assert 'href="../patches/p1.html#c-upgrade_x"' in html
    game = history_table([('game:urn', 'Urn', None), (key, 'X', None)], ['Urn'], {key: [(r1, [ch(key='a')])]}, {}, '../')
    assert 'href="../patches/p1.html"' in game                         # a Game system: the page itself


def test_valves_words_sit_under_the_rows_they_cover(monkeypatch):
    """Review 2026-10-05: a described row looked like any other — Valve's line is a quiet note under the ability's
    rows; a line about many entities ("Spirit Power scaling globally reduced by -7%") is said once per band;
    a documented row gets none (its line repeats "label old → new"). A change that came in a later build than the
    notes' own says so on its eye."""
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
    from builders import evidence          # the notes' own build is 100 (what a silent hotfix is newer than)
    monkeypatch.setattr(evidence, 'notes_window', lambda pid: (100, frozenset({100}), '2026-03-06'))
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
    assert 'came in build 104 (2026-03-09), after the patch' in html


def test_one_hidden_change_is_never_all_of_one():
    """Review 2026-10-05: "ALL 1 NOT IN NOTES"; an all-hidden band's rows keep a dimmed eye, each its row's proof
    (review 2026-10-17: they had none, the banner's was the only way to a build)."""
    from builders.history_view import history_table
    r1 = {'id': 'p1', 'date': '2026-01-01', 'title': '01-01-2026 Update'}
    key = 'abilities.vdata:upgrade_x'
    html = history_table([(key, 'X', None)], ['X'], {key: [(r1, [ch(key='a')])]}, {}, '../')
    assert '>1 not in patch notes<' in html and 'all 1 not in' not in html
    css = site_css()
    assert '.pblock.all-hidden .erow:not(.late) .st .mark { opacity: .7; }' in css
    # a row that came after the patch in a later build keeps its full eye there: its words are the proof (review 2026-10-05)
    from builders.cards import row
    assert 'class="erow st-hidden is-hidden late"' in row('hidden', '', 'x', tip='came in build 104 (2026-03-09), after the patch')
    assert ' late' not in row('hidden', '', 'x')


def test_strip_tiles_are_striped_squares_and_whole_ones_show():
    """Owner 2026-10-21 (Sloppy's dynamic cells; 14px tiles were too narrow): a 24px square with the stripes of every
    tag at rest (one colour showed half of what changed), the count on hover; the row never scrolls (2026-10-05: a
    bar under the strip; 2026-10-21: a scrolled row cut its oldest tile): the newest tiles that fit whole show."""
    import re
    from builders.history_view import patch_strip, tile_colour
    css = site_css()
    rule = re.search(r'\.patch-strip \{[^}]*\}', css).group(0)
    assert 'overflow: hidden' in rule and 'overflow-x: auto' not in rule
    assert re.search(r'\.ps-tile \{[^}]*flex: 0 0 24px[^}]*height: 24px[^}]*background: var\(--st, var\(--c', css)
    assert '.ps-tile.ps-out { display: none; }' in css
    js = site_js()
    assert "safe('strip-end'" in js and "classList.add('ps-out')" in js
    # the colour: the patch's net mark, else its most counted tag
    assert tile_colour({'buff': 1, 'nerf': 5}, 'mix') == 'changed' and tile_colour({'buff': 1}, 'nerf') == 'nerf'
    assert tile_colour({'new': 3, 'rework': 3, 'buff': 1}, '') == 'new'
    assert tile_colour({'up': 2}, '') == 'changed'
    hdr = [{'id': f'p{i}', 'date': f'2026-0{i}-01', 'title': f'0{i}-01-2026 Update'} for i in (1, 2)]
    html = patch_strip([(h['id'], h, {'buff': 2}, 0, [], 'buff') for h in hdr])
    assert 'class="ps-tile c-buff"' in html and 'style="--st:linear-gradient(' in html


def test_current_fold_is_open_and_events_carry_no_value():
    """Advisor round 4: Slum Shroom's page was one "Added to the game files · —" row under a closed
    "Current stats"; owner 2026-10-04: nothing folded by default, whatever the history's length."""
    from builders.history_view import now_fold
    from builders.render import vals_html
    assert '<details class="now px-frame" open>' in now_fold('Current stats', '<table></table>')
    assert now_fold('Current stats', '') == ''
    assert vals_html({'op': 'add', 'path': '@add', 'cat': 'balance', 'label': 'Added to the game files'}) == ''


def test_a_strip_tile_draws_its_tags_as_a_bar_across_its_foot():
    # owner 2026-11-13: 24px squares of top-to-bottom stripes were too small; the matrices keep their squares
    from builders.dynamics_page import stripes
    from builders.history_view import strip_bar
    g = stripes({'buff': 3, 'nerf': 1})
    assert g.startswith('linear-gradient(var(') and strip_bar(g).startswith('linear-gradient(90deg,var(')
    assert strip_bar('') == ''
