"""The entity page's CSS and scripts in a real browser, on pages built inside the test (no dist/ needed):
a phone-width tier table, a trail square under a filter, a filtered band's counters. The `browser` fixture is
tests/conftest.py's (CI installs Chromium)."""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _open(browser, tmp_path: Path, html: str, width: int, height: int = 900):
    """The page in tmp_path/x/ with the site's CSS and JS one level up (rel '../'), offline."""
    shutil.copy(ROOT / 'site' / 'styles.css', tmp_path / 'styles.css')
    shutil.copy(ROOT / 'site' / 'scripts.js', tmp_path / 'scripts.js')
    (tmp_path / 'x').mkdir(exist_ok=True)
    f = tmp_path / 'x' / 'page.html'
    f.write_text(html, encoding='utf-8')
    ctx = browser.new_context(viewport={'width': width, 'height': height})
    pg = ctx.new_page()
    pg.route('**/*', lambda r: r.continue_() if r.request.url.startswith('file:') else r.abort())
    errors: list[str] = []
    pg.on('pageerror', lambda e: errors.append(str(e)))
    pg.goto(f.as_uri())
    return ctx, pg, errors


def ch(**kw):
    base = {'op': 'change', 'cat': 'balance', 'label': 'Cooldown', 'old_s': '27', 'new_s': '29',
            'dir': 'nerf', 'pct': 7.4, 'grad': 2, 'status': 'hidden', 'path': 'x'}
    base.update(kw)
    return base


def test_a_tier_table_fits_a_phone(browser, tmp_path):
    """Review 2026-10-04: the open "Current stats" put a 420px-wide tier table on 45 neutral pages: 457px of
    page in a 390px window, Tier III cut off."""
    from builders.entities_pages import unit_page
    members = [{'id': f'neutral_dock_creature_{w}', 'file': 'npc_units.vdata', 'kind': 'neutral', 'alive': True,
                'first': [1, '2024-06-06'], 'name': f'Dock Creature {t}'}
               for w, t in (('weak', 'I'), ('normal', 'II'), ('strong', 'III'))]
    cols = [{'key': k, 'label': lbl, 'digits': 2} for k, lbl in (
        ('hp', 'Health'), ('dmg', 'Bullet Damage'), ('run', 'Run Speed (m/s)'), ('fire', 'Fire Interval (s)'),
        ('bounty', 'Soul Bounty'), ('grow', 'Bounty growth %/min'))]
    urow = {m['id']: {'values': {'hp': 1133 * (i + 1), 'dmg': 38.1, 'run': 4.06, 'fire': 1.08, 'bounty': 1133 + i,
                                 'grow': 12.7 + i}} for i, m in enumerate(members)}
    ctx, pg, errors = _open(browser, tmp_path, unit_page(members, urow, cols, {}, {}, {}), 390, 844)
    try:
        assert pg.locator('table.tier-grid').is_visible()
        sw, cw = pg.evaluate('[document.documentElement.scrollWidth, document.documentElement.clientWidth]')
        assert sw <= cw, f'{sw}px of page in a {cw}px window'
        right = pg.evaluate("document.querySelector('table.tier-grid').getBoundingClientRect().right")
        assert right <= cw
        assert not errors
    finally:
        ctx.close()


def _abrams():
    from builders.history_view import history_table
    r1 = {'id': 'p1', 'date': '2026-01-01', 'title': '01-01-2026 Update'}
    r3 = {'id': 'p3', 'date': '2026-03-01', 'title': '03-01-2026 Update'}
    keys = [('heroes.vdata:hero_atlas', 'Base stats', None),
            ('abilities.vdata:ab_charge', 'Shoulder Charge', None),
            ('abilities.vdata:ab_ult', 'Seismic Impact', None)]
    by_ent = {
        'heroes.vdata:hero_atlas': [(r1, [ch(key='heroes.vdata:hero_atlas:st', label='Stamina', dir='buff', pct=50.0)])],
        'abilities.vdata:ab_charge': [(r3, [ch(key='abilities.vdata:ab_charge:a', label='Radius', pct=-33.3)])],
        'abilities.vdata:ab_ult': [(r3, [ch(key='abilities.vdata:ab_ult:a', label='Cooldown', pct=16.2)])],
    }
    areas = {'heroes.vdata:hero_atlas': 'stats', 'abilities.vdata:ab_charge': 'abil', 'abilities.vdata:ab_ult': 'abil'}
    return history_table(keys, ['Abrams'], by_ent, {}, '../', areas=areas)


def test_a_square_shows_its_group_under_another_abilitys_filter(browser, tmp_path):
    """Review 2026-10-04: with Shoulder Charge chosen, Siphon Life's square scrolled nowhere — its band showed
    (Shoulder Charge's rows), its group stayed filtered out, the light flashed on a hidden element."""
    from builders.common import page
    square = '<a class="sq" href="#p-p3" data-p="p3" data-ab="ab_ult">square</a><div style="height:2400px"></div>'
    ctx, pg, errors = _open(browser, tmp_path, page('Abrams', square + _abrams(), '../', cls='entity'), 1440, 900)
    try:
        pg.click('.hist-bar [data-f-ab="ab_charge"]')
        ult = '.hgroup[data-ab="ab_ult"]'
        pg.wait_for_function(f"document.querySelector('{ult}').classList.contains('f-out')")
        assert pg.locator('#p-p3').is_visible()
        pg.evaluate('window.scrollTo(0, 0)')
        pg.click('a.sq')
        assert pg.evaluate(f"document.querySelector('{ult}').offsetParent !== null")
        top = pg.evaluate(f"document.querySelector('{ult}').getBoundingClientRect().top")
        assert 0 <= top < 900
        assert pg.get_attribute('.hist-bar [data-f-ab="ab_charge"]', 'aria-pressed') == 'false'
        assert not errors
    finally:
        ctx.close()


def test_a_square_opens_work_before_release(browser, tmp_path):
    """A band that only holds work before release is hidden until "Before release" is on: a square naming it
    turns that on (the button says so) and the band opens in view."""
    from builders.common import page
    from builders.history_view import history_table
    r1 = {'id': 'p1', 'date': '2026-01-01', 'title': '01-01-2026 Update'}
    r2 = {'id': 'p2', 'date': '2026-02-01', 'title': '02-01-2026 Update'}
    keys = [('heroes.vdata:h', 'Base stats', None), ('abilities.vdata:a', 'Alpha', None),
            ('abilities.vdata:b', 'Beta', None)]
    by_ent = {'heroes.vdata:h': [(r2, [ch(key='heroes.vdata:h:hp', label='Health')])],
              'abilities.vdata:a': [(r1, [ch(key='abilities.vdata:a:x', label='Radius', status='unreleased')])],
              'abilities.vdata:b': [(r2, [ch(key='abilities.vdata:b:x', label='Range', dir='buff', pct=5.0)])]}
    hist = history_table(keys, ['Hero'], by_ent, {}, '../', areas={'heroes.vdata:h': 'stats'})
    square = '<a class="sq" href="#p-p1" data-p="p1" data-ab="a">square</a><div style="height:2400px"></div>'
    ctx, pg, errors = _open(browser, tmp_path, page('Hero', square + hist, '../', cls='entity'), 1440, 900)
    try:
        assert not pg.locator('#p-p1').is_visible()
        pg.click('a.sq')
        assert pg.evaluate("document.querySelector('.hgroup[data-ab=\"a\"]').offsetParent !== null")
        assert pg.get_attribute('.hist-bar .hf-dev', 'aria-pressed') == 'true'
        assert not errors
    finally:
        ctx.close()


def test_a_filter_keeps_a_new_units_counters(browser, tmp_path):
    """Review 2026-10-04: Old Gods' band said NEW 71 and, under the NEW filter that kept every row, NEW 60 —
    the "Added to the game" head stands for the rows it does not list (data-n)."""
    from builders.common import page
    from builders.history_view import history_table
    from builders.cards import ADDED_KEY_LIMIT
    new = {'op': 'add', 'old_s': None, 'pct': None, 'dir': None}
    added = ([ch(**new, key='npc_units.vdata:u:hp', path='m_iMaxHealth', label='Max Health', new_s='500')]
             + [ch(**new, key=f'npc_units.vdata:u:r{i}', path=f'm_flThing{i}', label=f'Thing {i}', new_s=str(i + 1),
                   status='hidden' if i % 2 else 'documented') for i in range(ADDED_KEY_LIMIT + 3)])
    r1 = {'id': 'p1', 'date': '2026-01-01', 'title': '01-01-2026 Update'}
    r2 = {'id': 'p2', 'date': '2026-02-01', 'title': '02-01-2026 Update'}
    hist = history_table([('npc_units.vdata:u', 'Unit', None)], ['Unit'],
                         {'npc_units.vdata:u': [(r1, added), (r2, [ch(key='npc_units.vdata:u:hp', label='Max Health')])]},
                         {}, '../')
    ctx, pg, errors = _open(browser, tmp_path, page('Unit', hist, '../', cls='entity'), 1440, 900)
    pip = "document.querySelector('#p-p1 summary .tsum .pip.new').lastChild.nodeValue"
    eye = "document.querySelector('#p-p1 summary .ec-n').textContent"
    try:
        built, built_eye = pg.evaluate(pip), pg.evaluate(eye)
        assert built == str(len(added))
        pg.click('.hist-bar [data-f-tag="new"]')
        pg.wait_for_function("document.getElementById('history').classList.contains('filtering')")
        assert pg.evaluate(pip) == built                       # every row kept: the built number
        assert pg.evaluate(eye) == built_eye.replace('all ', '')
        pg.click('.hist-bar [data-f-tag="new"]')
        pg.wait_for_function("!document.getElementById('history').classList.contains('filtering')")
        assert pg.evaluate(pip) == built                       # the built number back
        pg.click('.hist-bar .hf-hidden')
        pg.wait_for_function("document.getElementById('history').classList.contains('filtering')")
        hidden = sum(1 for c in added if c['status'] == 'hidden')
        assert pg.evaluate(pip) == str(hidden)                 # only the ones the notes left out
        assert not errors
    finally:
        ctx.close()


def test_a_rule_for_all_heroes_is_counted_apart_by_the_filters(browser, tmp_path):
    """Coverage audit 2026-10-05: a rule for every hero (the level curve) is ONE link row "All heroes: N changes ·
    Hero progression ›" on each hero's band (review 2026-10-05: folded, its rows grew heroes/ to 37 MB); no tag or
    eye filter keeps it, a band where only it would match folds away (Haze under NERF kept 4 bands with no row of
    her own), and the banner's "+N for all heroes" hides while a filter is on."""
    from builders.common import page
    from builders.history_view import history_table

    def every(dirn):
        return [ch(key=f'heroes.vdata:h:l{i}', path=f'l{i}', label=f'Level {i}: souls needed', dir=dirn, pct=-10.0,
                   old_s=str(1000 * i), new_s=str(900 * i), shared_n=40, shared_what='heroes', shared_all=True,
                   file='heroes.vdata') for i in range(2, 8)]
    own = [ch(key='heroes.vdata:h:hp', label='Max Health'), ch(key='heroes.vdata:h:rg', label='Regen', status='documented')]
    r1 = {'id': 'p1', 'date': '2026-01-01', 'title': '01-01-2026 Update'}
    r0 = {'id': 'p0', 'date': '2025-12-01', 'title': '12-01-2025 Update'}
    hist = history_table([('heroes.vdata:h', 'Base stats', None)], ['Hero'],
                         {'heroes.vdata:h': [(r1, own + every('buff')), (r0, every('nerf'))]}, {}, '../')
    ctx, pg, errors = _open(browser, tmp_path, page('Hero', hist, '../', cls='entity'), 1440, 900)
    shown = """() => [...document.querySelectorAll('#history .erow')].filter(r => r.parentNode.tagName !== 'SUMMARY'
        && !r.closest('.f-out') && (r.offsetParent !== null || r.closest('details:not([open])'))).length"""
    try:
        assert pg.inner_text('.hist-bar .hf-hidden .n') == '1'
        link = pg.locator('#p-p1 .erow.shr-all a.shr-go')
        assert link.get_attribute('href') == '../game/progression.html#p-p1'
        assert pg.locator('details.shr-all').count() == 0                 # no fold of the rows themselves
        assert pg.locator('.hist-bar [data-f-tag="buff"]').count() == 0   # only the rule for all had BUFFs
        pg.click('.hist-bar .hf-hidden')
        pg.wait_for_function("document.getElementById('history').classList.contains('filtering')")
        assert pg.evaluate(shown) == 1                                    # Max Health only, the link row out
        assert pg.locator('#p-p1 .erow.shr-all').evaluate('r => r.classList.contains("f-out")')
        assert pg.evaluate("document.querySelector('#p-p1 summary .ec-n').textContent") == '1 not in notes'
        assert pg.locator('#p-p1 summary .shr-chip').evaluate('c => c.classList.contains("n0")')
        pg.click('.hist-bar .hf-hidden')
        pg.click('.hist-bar [data-f-tag="nerf"]')                         # the hero's own NERF, and p0's rule
        pg.wait_for_function("document.getElementById('history').classList.contains('filtering')")
        assert not pg.locator('#p-p1').evaluate('b => b.classList.contains("f-out")')
        assert pg.locator('#p-p0').evaluate('b => b.classList.contains("f-out")')     # only the rule for all
        pg.click('.hist-bar [data-f-tag="nerf"]')                         # cleared: everything back
        pg.wait_for_function("!document.getElementById('history').classList.contains('filtering')")
        assert not pg.locator('#p-p1 summary .shr-chip').evaluate('c => c.classList.contains("n0")')
        assert not errors
    finally:
        ctx.close()


def test_the_history_bar_stays_and_a_long_page_has_a_way_up(browser, tmp_path):
    """Review 2026-10-05: the filters scrolled away (Sloppy's stay); #hidden presses the eye; a filter's first match
    lands below the bar; a back-to-top button past one screen; on a phone the bar scrolls away."""
    from builders.common import page
    from builders.history_view import history_table
    rows = [({'id': f'p{i}', 'date': f'2025-{i:02d}-01', 'title': f'{i:02d}-01-2025 Update'},
             [ch(key=f'k{i}', label='Cooldown', status='documented' if i % 2 else 'hidden')]) for i in range(1, 13)]
    hist = history_table([('abilities.vdata:x', 'X', None)], ['X'], {'abilities.vdata:x': rows}, {}, '../')
    filler = '<div style="height:1500px"></div>'
    ctx, pg, errors = _open(browser, tmp_path, page('X', filler + hist, '../', cls='entity'), 1440, 900)
    try:
        assert pg.evaluate("getComputedStyle(document.querySelector('.hist-bar')).position") == 'sticky'
        pg.evaluate('window.scrollTo(0, 3000)')
        pg.wait_for_function("document.querySelector('.back-to-top').classList.contains('on')")
        bar = pg.evaluate("document.querySelector('.hist-bar').getBoundingClientRect().top")
        assert 0 <= bar < 80                                               # stuck under the site bar
        pg.click('.hist-bar [data-f-tag="nerf"]')
        pg.wait_for_function("document.getElementById('history').classList.contains('filtering')")
        first = pg.evaluate("[...document.querySelectorAll('details.pblock')].find(b => !b.classList.contains('f-out'))"
                            ".getBoundingClientRect().top")
        bottom = pg.evaluate("document.querySelector('.hist-bar').getBoundingClientRect().bottom")
        assert first >= bottom - 1
        pg.click('.back-to-top')
        pg.wait_for_function('window.scrollY === 0')
        assert not errors
    finally:
        ctx.close()
    ctx, pg, errors = _open(browser, tmp_path, page('X', hist, '../', cls='entity'), 390, 844)
    try:
        assert pg.evaluate("getComputedStyle(document.querySelector('.hist-bar')).position") == 'static'
        pg.evaluate("location.hash = '#hidden'")
        pg.wait_for_function("document.querySelector('.hf-hidden').getAttribute('aria-pressed') === 'true'")
        assert pg.evaluate("document.getElementById('history').classList.contains('only-hidden')")
        assert not errors
    finally:
        ctx.close()


def test_a_merged_group_answers_to_each_of_its_members(browser, tmp_path):
    """Review 2026-10-05: a group of identical rows of several entries kept only the first id, so #ab-<second>
    (a search link: "Breakable lion statue") and the second entry's chip emptied the history."""
    from builders.common import page
    from builders.history_view import history_table
    r1 = {'id': 'p1', 'date': '2026-01-01', 'title': '01-01-2026 Update'}
    keys = [('game:breakables', 'Breakables', None), ('misc.vdata:jar', 'Jar', None), ('misc.vdata:lion', 'Lion', None),
            ('misc.vdata:crate', 'Crate', None)]
    same = [ch(key='x:respawn', label='Respawn Time')]
    by_ent = {'misc.vdata:jar': [(r1, same)], 'misc.vdata:lion': [(r1, [dict(c) for c in same])],
              'misc.vdata:crate': [(r1, [ch(key='y', label='Health')])]}
    areas = {k: 'abil' for k, _, _ in keys[1:]}
    hist = history_table(keys, ['Breakables'], by_ent, {}, '../', areas=areas, merge=lambda names: ' · '.join(names))
    ctx, pg, errors = _open(browser, tmp_path, page('Breakables', hist, '../', cls='entity'), 1440, 900)
    try:
        assert pg.locator('.hgroup[data-ab~="lion"]').count() == 1
        pg.click('.hist-bar [data-f-ab="lion"]')
        pg.wait_for_function("document.getElementById('history').classList.contains('filtering')")
        assert not pg.locator('#p-p1').evaluate('b => b.classList.contains("f-out")')
        assert pg.locator('.hgroup[data-ab~="lion"]').is_visible()
        assert not pg.locator('.hgroup[data-ab="crate"]').is_visible()
        assert not errors
    finally:
        ctx.close()


def test_hidden_opens_a_patch_pages_tab_of_what_the_notes_left_out(browser, tmp_path):
    """Review 2026-10-05: on an update with notes, #hidden pressed the raw All changes filter (first rows: engine
    words); it opens the "Not in patch notes" tab of readable lines; the filter keeps its own tab's hash."""
    from builders.common import page
    body = ('<div class="tabs toolbar"><button class="px-btn on" data-tab="notes" aria-pressed="true">Patch notes</button>'
            '<button class="px-btn" data-tab="generated" aria-pressed="false">Not in patch notes</button>'
            '<button class="px-btn" data-tab="changes" aria-pressed="false">All changes</button></div>'
            '<div class="tab-panel on" id="notes">notes</div>'
            '<div class="tab-panel" id="generated" data-hidden-tab><ul class="gen-notes"><li>line</li></ul></div>'
            '<div class="tab-panel" id="changes"><div class="toolbar"><button class="px-btn hf-hidden" '
            'data-toggle-class="only-hidden" data-target="#changes" aria-pressed="false">Not in patch notes</button>'
            '</div></div>')
    ctx, pg, errors = _open(browser, tmp_path, page('Patch', body, '../'), 1440, 900)
    try:
        pg.evaluate("location.hash = '#hidden'")
        pg.wait_for_function("document.getElementById('generated').classList.contains('on')")
        assert pg.get_attribute('.hf-hidden', 'aria-pressed') == 'false'
        pg.click('[data-tab="changes"]')
        pg.click('.hf-hidden')
        pg.wait_for_function("document.querySelector('.hf-hidden').getAttribute('aria-pressed') === 'true'")
        pg.wait_for_timeout(50)
        assert pg.evaluate('location.hash') == '#changes'
        assert not errors
    finally:
        ctx.close()


def test_an_ability_head_counts_what_the_filter_shows(browser, tmp_path):
    """Review 2026-10-05: under the eye, Haze's Bullet Dance head still read 10 over the 1 row shown (15 of 36
    groups kept their built numbers); a filter recounts each head like the banner and puts it back after."""
    from builders.common import page
    from builders.history_view import history_table
    r1 = {'id': 'p1', 'date': '2026-01-01', 'title': '01-01-2026 Update'}
    a_rows = [ch(key=f'abilities.vdata:a:{i}', path=f'a{i}', label=f'Thing {i}', dir='buff', pct=10.0,
                 status='hidden' if i == 0 else 'documented') for i in range(5)]
    b_rows = [ch(key=f'abilities.vdata:b:{i}', path=f'b{i}', label=f'Other {i}', status='hidden') for i in range(2)]
    keys = [('heroes.vdata:h', 'Base stats', None), ('abilities.vdata:a', 'Alpha', None),
            ('abilities.vdata:b', 'Beta', None)]
    hist = history_table(keys, ['Hero'], {'abilities.vdata:a': [(r1, a_rows)], 'abilities.vdata:b': [(r1, b_rows)]},
                         {}, '../')
    ctx, pg, errors = _open(browser, tmp_path, page('Hero', hist, '../', cls='entity'), 1440, 900)
    head = ".hgroup[data-ab='{}'] .esub .tsum .pip.{}"
    pip = "document.querySelector(\"" + head.format('a', 'buff') + "\").lastChild.nodeValue"
    try:
        assert pg.evaluate(pip) == '5'
        pg.click('.hist-bar .hf-hidden')
        pg.wait_for_function("document.getElementById('history').classList.contains('filtering')")
        assert pg.evaluate(pip) == '1'                                   # Alpha's one row the notes left out
        assert pg.evaluate("document.querySelector(\"" + head.format('b', 'nerf') + "\").lastChild.nodeValue") == '2'
        pg.click('.hist-bar .hf-hidden')
        pg.wait_for_function("!document.getElementById('history').classList.contains('filtering')")
        assert pg.evaluate(pip) == '5'                                   # the built number back
        pg.click('.hist-bar [data-f-tag="nerf"]')                        # Alpha has no NERF: its BUFF pip goes
        pg.wait_for_function("document.getElementById('history').classList.contains('filtering')")
        assert pg.evaluate("getComputedStyle(document.querySelector(\"" + head.format('a', 'buff') + "\")).display") == 'none'
        assert not errors
    finally:
        ctx.close()
