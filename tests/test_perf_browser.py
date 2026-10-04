"""Front-end fixes of the perf track (2026-10-05) in a real browser: site/scripts.js + styles.css on fixture
markup. Skipped where Playwright or its Chromium is not installed (CI)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sync_api = pytest.importorskip('playwright.sync_api')


@pytest.fixture(scope='module')
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:                      # no browser binary on this machine
            pytest.skip(f'chromium not available: {e}')
        yield b
        b.close()


def _open(browser, body: str, head: str = '', width: int = 1400, height: int = 900, before=None):
    css = (ROOT / 'site' / 'styles.css').read_text(encoding='utf-8')
    js = (ROOT / 'site' / 'scripts.js').read_text(encoding='utf-8')
    page = browser.new_page(viewport={'width': width, 'height': height})
    errors: list[str] = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    if before:
        before(page)
    page.set_content(f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style>{head}</head>'
                     f'<body>{body}<script>{js}</script></body></html>')
    return page, errors


def test_history_tip_compares_with_the_sign_like_the_tags(browser):
    """Without a step's own direction the tip compared sizes: Pocket's bullet resist −20 → −15 read as a nerf
    and Celeste's −6 → −8 as a buff, the opposite of the hero page's tags (semantics.direction)."""
    hist = json.dumps([[1, '2026-01-01', -20, -15], [2, '2026-02-01', -15, -18]])
    page, errors = _open(browser, f'<span class="has-hist" data-pol="1" data-digits="0" data-title="T" '
                                  f"data-hist='{hist}'>x</span>")
    page.hover('.has-hist')
    got = page.evaluate("() => [...document.querySelectorAll('.hist-tip li .n')].map(n => n.className)")
    assert got == ['n dir-nerf', 'n dir-buff']                    # newest first: −15 → −18, −20 → −15
    assert page.evaluate("() => document.querySelector('.hist-tip .t-overall span').className") == 'dir-buff'
    assert not errors


def test_history_tip_opens_on_keyboard_focus(browser):
    hist = json.dumps([[1, '2026-01-01', 10, 12]])
    page, _ = _open(browser, f'<button id="before">b</button><table class="stats"><tbody><tr><td class="has-hist" '
                             f"data-pol=\"1\" data-digits=\"0\" data-title=\"Abrams · HP\" data-hist='{hist}'>12</td>"
                             '</tr></tbody></table>')
    assert page.evaluate("() => document.querySelector('td.has-hist').tabIndex") == 0
    page.focus('#before')
    page.keyboard.press('Tab')
    assert page.evaluate("() => document.activeElement.classList.contains('has-hist')")
    tip = page.locator('.hist-tip')
    assert 'on' in tip.get_attribute('class') and 'Abrams · HP' in tip.inner_text()
    assert page.evaluate("() => document.activeElement.getAttribute('aria-describedby')") == 'hist-tip'
    page.keyboard.press('Escape')
    assert 'on' not in tip.get_attribute('class')


def _stats(groups: dict[str, int]) -> str:
    from builders.tables_pages import render_table
    cols = [{'key': f'{g}{i}', 'label': f'{g}{i}', 'group': g, 'pol': 1, 'digits': 0}
            for g, n in groups.items() for i in range(n)]
    rows = [{'id': f'r{j}', 'name': f'Row {j}', 'history': {}, 'values': {c['key']: v for c in cols}}
            for j, v in enumerate((2, 3, 1))]
    return render_table(cols, rows, lambda r: f'<td class="name" data-col="name">{r["name"]}</td>', 'Name',
                        table_id='t')


def test_sortable_and_foldable_headers_work_from_the_keyboard(browser):
    page, _ = _open(browser, _stats({'Weapon': 2, 'Vitality': 1}))
    th = page.locator('#t thead tr.cols th[data-col="Weapon0"]')
    assert th.get_attribute('tabindex') == '0' and th.get_attribute('aria-sort') == 'none'
    order = "() => [...document.querySelectorAll('#t tbody tr')].map(r => r.cells[0].textContent)"
    th.focus()
    page.keyboard.press('Enter')
    assert th.get_attribute('aria-sort') == 'descending' and page.evaluate(order) == ['Row 1', 'Row 0', 'Row 2']
    page.keyboard.press(' ')
    assert th.get_attribute('aria-sort') == 'ascending' and page.evaluate(order) == ['Row 2', 'Row 0', 'Row 1']
    page.keyboard.press('Enter')
    assert th.get_attribute('aria-sort') == 'none' and page.evaluate(order) == ['Row 0', 'Row 1', 'Row 2']
    cat = page.locator('#t thead tr.cats th[data-group="Weapon"]')
    cat.focus()
    page.keyboard.press('Enter')
    assert cat.get_attribute('aria-expanded') == 'false' and cat.evaluate('th => th.colSpan') == 1


def test_buff_vs_nerf_keeps_the_matrix_where_it_was(browser):
    """Any class toggled on the matrix threw a reader of older patches back to the newest end."""
    n = 60
    head = '<th class="name">Name</th>' + ''.join(f'<th class="dd">{i}</th>' for i in range(n))
    body = '<td class="name">Row</td>' + ''.join('<td></td>' for _ in range(n))
    html = ('<div class="toolbar dyn-bar"><label class="switch"><input type="checkbox" data-toggle-class="bvn" '
            'data-target="#dyn-hero"><span class="track"></span>Buff vs nerf</label></div>'
            f'<div class="table-fade"><div class="table-scroll"><table class="dyn" id="dyn-hero" '
            f'style="--n-all:{n};--n-new:{n}"><colgroup><col class="nm">{"<col>" * n}</colgroup>'
            f'<thead><tr class="cols">{head}</tr></thead><tbody><tr>{body}</tr></tbody></table></div></div>')
    page, _ = _open(browser, html, width=700)
    sc = '() => document.querySelector(".table-scroll").scrollLeft'
    page.evaluate('() => { document.querySelector(".table-scroll").scrollLeft = 120; }')
    page.click('.dyn-bar .switch')
    page.wait_for_timeout(50)
    assert page.evaluate("() => document.getElementById('dyn-hero').classList.contains('bvn')")
    assert page.evaluate(sc) == 120


def test_home_search_keeps_what_was_typed_while_the_list_loads(browser):
    """The keystrokes' renders were dropped while search.json was in flight: typing "haze" during the load
    left an empty list."""
    pending = []
    url = 'https://cyclopean.test/search.json'

    def before(page):
        page.route(url, lambda route: pending.append(route))
    page, _ = _open(browser, f'<div class="site-search"><input type="search" data-site-search="{url}" data-rel="" '
                             'role="combobox" aria-expanded="false"><div class="ss-list" id="ss-list" hidden></div></div>',
                    before=before)
    page.focus('input')
    page.keyboard.type('haze')
    page.wait_for_timeout(300)
    assert pending                                              # the list is still on its way
    rows = [['Haze', 'heroes/haze.html', 'Hero', ''], ['Abrams', 'heroes/atlas.html', 'Hero', '']]
    pending[0].fulfill(status=200, content_type='application/json', body=json.dumps(rows))
    page.wait_for_selector('.ss-list a')
    assert page.locator('.ss-list a .ss-nm').all_inner_texts() == ['Haze']
    assert page.get_attribute('input', 'aria-expanded') == 'true'
    page.keyboard.press('ArrowDown')
    assert page.get_attribute('input', 'aria-activedescendant') == 'ss-o0'


def test_the_fonts_stylesheet_is_switched_on_after_it_loads(browser):
    page, _ = _open(browser, '<p>x</p>', head='<link rel="stylesheet" href="data:text/css,p%7Bcolor:red%7D" '
                                             'media="print" data-fonts>')
    page.wait_for_function("() => document.querySelector('link[data-fonts]').media === 'all'")
