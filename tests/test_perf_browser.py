"""Front-end fixes of the perf track (2026-10-05) in a real browser: site/scripts.js + styles.css on fixture
markup. The `browser` fixture is tests/conftest.py's (CI installs Chromium)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


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


# a hover card's values (review 2026-10-05): "overflow-wrap: anywhere" split numbers between digits when a
# long field name took the card's width (the value column shrank below its numbers: Walker's "12880 → 8"
# + "000"); a long REWORK list must still wrap inside the card (it ran past the right edge before)
CARD_NUMBERS = (('nerf', 'Max Health', '12880', '8000'), ('nerf', 'Bonus Fire Rate', '30%', '20%'),
                ('buff', 'Bonus Health Regeneration Per Second While Out Of Combat After Taking No Damage', '3', '4'),
                ('buff', 'Slow', '-50%', '-45%'), ('nerf', 'Bullet Speed', '635m/s', '571.5m/s'),
                ('buff', 'Interval', '0.0003', '0.00035'))
CARD_REWORK = (('nerf', 'Max Health', '12880', '8000'),
               ('rework', 'Tier 3', '+20% Weapon Damage, +8 Spirit Power, -15% Cooldown',
                '+25% Weapon Damage, +10 Spirit Power, +1 Charge, -20% Cooldown, +2m Radius'))

# every word of the card's table on one line, and the table inside the card
SPLIT_WORDS = r"""() => {
  const out = [], tip = document.querySelector('.dyn-tip'), table = tip.querySelector('table');
  const walker = document.createTreeWalker(table, NodeFilter.SHOW_TEXT);
  for (let n; (n = walker.nextNode());) {
    const re = /\S+/g;
    for (let m; (m = re.exec(n.data));) {
      const r = document.createRange();
      r.setStart(n, m.index);
      r.setEnd(n, m.index + m[0].length);
      const lines = new Set([...r.getClientRects()].map(x => Math.round(x.top)));
      if (lines.size > 1) out.push(m[0]);
    }
  }
  return {split: out, over: table.getBoundingClientRect().right > tip.getBoundingClientRect().right + 0.5};
}"""


@pytest.mark.parametrize('width', [1440, 390])
@pytest.mark.parametrize('card', [CARD_NUMBERS, CARD_REWORK], ids=['numbers', 'rework'])
def test_hover_card_never_splits_a_number(browser, width, card):
    rows = ''.join(f'<tr><td class="dt-tg"><span class="tag {t}">{t.upper()}</span></td><td class="dt-field">{f}</td>'
                   f'<td class="dt-vals">{o}<i>→</i><b class="t-{t}">{n}</b></td></tr>' for t, f, o, n in card)
    page, errors = _open(browser, '<div class="dyn-tip on" style="left:8px;top:8px"><div class="dt-head">'
                                  '<span class="dt-name">Walker</span><span class="dt-patch">2026-09-16</span></div>'
                                  f'<table class="dt-rows">{rows}</table></div>', width=width)
    assert page.evaluate(SPLIT_WORDS) == {'split': [], 'over': False}
    assert not errors


def test_a_unit_card_without_art_shows_its_glyph_in_the_icon_square(browser):
    """The glyph became an empty span (its shape a CSS mask): on the Units index nothing sized it and Shrine,
    Overseer, Sinner's Sacrifice and Mini Turret lost their icon (0x0, review 2026-10-05)."""
    from builders.common import visual
    card = (f'<div class="grid units"><a class="card px-frame" href="#">{visual(None, "units")}'
            '<span class="nm">Shrine</span><span class="sub">Building</span></a></div>')
    page, _ = _open(browser, card)
    box = page.evaluate("() => { const g = document.querySelector('.card .glyph');"
                        " const r = g.getBoundingClientRect(), b = getComputedStyle(g, '::before');"
                        " return [r.width, r.height, parseFloat(b.width) > 0]; }")
    assert box == [72, 72, True]


def test_a_table_of_values_is_one_tab_stop_walked_with_the_arrows(browser):
    """Every value with a history was a tab stop: ~1,100 on Hero Stats before the next thing on the page."""
    hist = json.dumps([[1, '2026-01-01', 10, 12]]).replace('"', '&quot;')

    def cell(col: str, n: int) -> str:
        return (f'<td data-col="{col}" class="has-hist" data-pol="1" data-digits="0" data-title="{col}{n}" '
                f'data-hist="{hist}">{n}</td>')
    rows = ''.join(f'<tr><td class="name">R{i}</td>{cell("a", i)}{cell("b", i)}</tr>' for i in range(3))
    page, errors = _open(browser, '<button id="before">b</button><table class="stats"><tbody>'
                                  f'{rows}</tbody></table><button id="after">a</button>')
    title = "() => document.activeElement.getAttribute('data-title') || document.activeElement.id"
    assert page.evaluate("() => [...document.querySelectorAll('[data-hist]')].filter(e => e.tabIndex === 0).length") == 1
    page.focus('#before')
    page.keyboard.press('Tab')
    assert page.evaluate(title) == 'a0'
    page.keyboard.press('ArrowRight')
    assert page.evaluate(title) == 'b0'
    page.keyboard.press('ArrowDown')
    page.keyboard.press('ArrowDown')
    assert page.evaluate(title) == 'b2'
    assert 'b2' in page.locator('.hist-tip').inner_text()
    page.keyboard.press('ArrowRight')                  # the last value: stays
    page.keyboard.press('ArrowUp')
    assert page.evaluate(title) == 'b1'
    page.keyboard.press('Tab')                         # out of the table in one step
    assert page.evaluate(title) == 'after'
    page.keyboard.press('Shift+Tab')                   # back where the reader left it
    assert page.evaluate(title) == 'b1'
    # a filter hid that row: Tab enters at the first value still shown, the arrows skip the row
    page.evaluate("() => { document.querySelectorAll('tbody tr')[1].style.display = 'none'; }")
    page.focus('#before')
    page.keyboard.press('Tab')
    assert page.evaluate(title) == 'a0'
    page.keyboard.press('ArrowDown')
    assert page.evaluate(title) == 'a2'
    assert not errors


def test_a_name_column_sorts_both_ways_as_aria_sort_says(browser):
    """Words always sorted A→Z while aria-sort announced "descending", then "ascending"."""
    from builders.tables_pages import render_table
    rows = [{'id': f'r{j}', 'name': f'Row {j}', 'history': {}, 'values': {'w': j}} for j in range(3)]
    page, _ = _open(browser, render_table(
        [{'key': 'w', 'label': 'W', 'group': 'Weapon', 'pol': 1, 'digits': 0}], rows,
        lambda r: f'<td class="name" data-col="name" data-sort="{r["name"]}">{r["name"]}</td>', 'Name', table_id='t'))
    th = page.locator('#t thead tr.cols th[data-col="name"]')
    order = "() => [...document.querySelectorAll('#t tbody tr')].map(r => r.cells[0].textContent)"
    th.click()
    assert th.get_attribute('aria-sort') == 'descending' and page.evaluate(order) == ['Row 2', 'Row 1', 'Row 0']
    th.click()
    assert th.get_attribute('aria-sort') == 'ascending' and page.evaluate(order) == ['Row 0', 'Row 1', 'Row 2']


def test_a_strip_card_says_the_net_of_the_patch(browser):
    """Review 2026-10-05: a strip tile's card carries the band's weighed net (weights.net_of) as one chip after the
    counts; a patch whose rows take no side carries none."""
    from builders.history_view import patch_strip, tile_card
    row = {'op': 'change', 'cat': 'balance', 'label': 'Radius', 'old_s': '3m', 'new_s': '4m', 'dir': 'buff', 'pct': 33.0,
           'status': 'documented', 'path': 'x'}
    hdr = [{'id': f'p{i}', 'date': f'2026-0{i}-01', 'title': f'0{i}-01-2026 Update'} for i in (1, 2)]
    items = [('p2', hdr[1], {'buff': 1}, 0, tile_card([(('', '', '', 0), [row])]), 'buff'),
             ('p1', hdr[0], {'buff': 1}, 0, tile_card([(('', '', '', 0), [row])]), '')]
    page, errors = _open(browser, patch_strip(items))
    page.hover('.ps-tile[data-k="0"]')
    chip = page.locator('.dyn-tip.on .dt-counts .net-chip')
    assert chip.count() == 1 and chip.text_content() == 'net buff' and 'net-buff' in chip.get_attribute('class')
    page.hover('.ps-tile[data-k="1"]')
    assert page.locator('.dyn-tip.on .dt-counts').count() == 1 and page.locator('.dyn-tip.on .net-chip').count() == 0
    assert not errors


def test_matrix_row_icons_load_with_the_page_not_under_a_scroll(browser):
    """Perf 2026-10-05: each lazy row icon arriving mid-scroll cost a layout, a repaint and a new layering of the sticky
    name cells (items/changes in-p95 50 ms on a 4x slower CPU, 17 ms with the icons in). At `load` the matrices' icons
    load; other lazy images stay lazy."""
    gif = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=='
    page, errors = _open(browser, f'<table class="dyn"><tbody><tr><td class="name"><a href="#"><img src="{gif}" alt="" '
                                  f'loading="lazy">X</a></td></tr></tbody></table><img id="other" src="{gif}" alt="" '
                                  f'loading="lazy">')
    got = page.evaluate("() => [document.querySelector('table.dyn img').loading, document.getElementById('other').loading]")
    assert got == ['eager', 'lazy'] and not errors
