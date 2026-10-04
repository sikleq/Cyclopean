"""The entity page's CSS and scripts in a real browser, on pages built inside the test (no dist/ needed):
a phone-width tier table, a trail square under a filter, a filtered band's counters. Skipped where
Playwright or its Chromium is missing (CI runs pytest before any browser exists)."""
import shutil
from pathlib import Path

import pytest

sync_api = pytest.importorskip('playwright.sync_api')

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope='module')
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True)
        except Exception as e:          # no browser downloaded: not this test's business
            pytest.skip(f'no Chromium for Playwright: {e}')
        yield b
        b.close()


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
