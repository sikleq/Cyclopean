"""Stats tables and change matrices in a real browser: site/scripts.js + site/styles.css on pages built from
fixtures (no dist/, no data). The `browser` fixture is tests/conftest.py's (CI installs Chromium).

Review 2026-10-04: a folded column group never unfolded (Hero Stats 34 -> 21 -> 21 columns) and the
track's own browser check only compared colspan sums, which still matched."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _open(browser, body: str, width: int = 1400, height: int = 900):
    css = (ROOT / 'site' / 'styles.css').read_text(encoding='utf-8')
    js = (ROOT / 'site' / 'scripts.js').read_text(encoding='utf-8')
    page = browser.new_page(viewport={'width': width, 'height': height})
    errors: list[str] = []
    page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
    page.set_content(f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head>'
                     f'<body>{body}<script>{js}</script></body></html>')
    return page, errors


VISIBLE_COLS = """t => [...document.querySelectorAll(t + ' thead tr.cols th')]
  .filter(th => getComputedStyle(th).display !== 'none').length"""


def _stats_table(groups: dict[str, int], rows: int = 3, pol=None, values=None) -> str:
    from builders.tables_pages import render_table
    cols = [{'key': f'{g}{i}', 'label': f'{g}{i}', 'group': g, 'pol': 1 if pol is None else pol, 'digits': 0}
            for g, n in groups.items() for i in range(n)]
    data = [{'id': f'r{j}', 'name': f'Row {j}', 'history': {},
             'values': {c['key']: (values[j] if values else j + 1) for c in cols}} for j in range(rows)]
    return render_table(cols, data, lambda r: f'<td class="name" data-col="name">{r["name"]}</td>', 'Name',
                        table_id='t')


def test_a_folded_group_unfolds(browser):
    page, errors = _open(browser, _stats_table({'Weapon': 4, 'Vitality': 3, 'Spirit': 2}))
    start = page.evaluate(VISIBLE_COLS, '#t')
    for group, folded in (('Weapon', 3), ('Vitality', 2), ('Spirit', 1)):
        cat = page.locator(f'#t thead tr.cats th[data-group="{group}"]')
        cat.click()
        assert page.evaluate(VISIBLE_COLS, '#t') == start - folded
        assert cat.evaluate('th => th.colSpan') == 1
        cat.click()
        assert page.evaluate(VISIBLE_COLS, '#t') == start
        # every cell of the group is back too, not only the header
        assert page.evaluate("() => document.querySelectorAll('#t .grp-off').length") == 0
    assert errors == []


def test_heat_ranks_signed_values(browser):
    """A stat column holds bonuses: -30 Spirit Power is the worst, not the biggest (it read deep green)."""
    from builders.tables_pages import _toolbar
    vals = [-30, 5, 10, 15, 20, 25, 30]
    page, _ = _open(browser, _toolbar('Item…', heat_on=True) + _stats_table({'Spirit': 1}, rows=7, values=vals))
    cls = page.evaluate("() => [...document.querySelectorAll('#t tbody td[data-col=\"Spirit0\"]')].map(td => td.className)")
    assert 'hm-b4' in cls[0] and 'hm-g4' in cls[-1]


def _items_page(per_checked: bool = False) -> str:
    from builders.tables_pages import (_toolbar, effects_cell, item_columns, item_filter_chips, render_table,
                                       stats_cell)
    from tests.test_builders import BOOSTER, ITEM_COLS
    rows = [{**BOOSTER, 'id': f'i{n}', 'name': f'I{n}',
             'values': {**BOOSTER['values'], 'health_max': 10.0 * (n + 1), 'tier': 1 + n % 2}} for n in range(5)]
    cols = item_columns(ITEM_COLS)
    stat_cols = [c for c in cols if c.get('stat')]
    chips = item_filter_chips()
    if per_checked:
        chips = chips.replace('data-souls-per>', 'data-souls-per checked>')
    table = render_table(cols, rows, lambda r: f'<td class="name" data-col="name">{r["name"]}</td>', 'Item',
                         table_id='items-table',
                         row_attrs=lambda r: f' data-tier="{r["values"]["tier"]}" data-cost="800"',
                         cells_by_key={'stats': lambda r, c, cut: stats_cell(r, stat_cols, cut),
                                       'effect': lambda r, c, cut: effects_cell(r, cut),
                                       'builds': lambda r, c, cut: '<td class="xcol" data-col="builds"></td>'},
                         table_attrs=' data-heat-by="tier"')
    return _toolbar('Item…', extra=chips, heat_on=True) + table


def test_closing_stat_columns_drops_their_sort(browser):
    """Closed while a stat column sorted the rows, nothing visible showed or undid the sort."""
    page, errors = _open(browser, _items_page())
    page.locator('#items-table .sc[data-col="health_max"]').first.click()      # opens the columns, sorted
    assert page.evaluate("() => document.getElementById('items-table').classList.contains('is-sorted')")
    page.locator('label.switch:has(input[data-stat-cols])').click()
    state = page.evaluate("""() => { const t = document.getElementById('items-table');
      return [t.classList.contains('is-sorted'), t.querySelectorAll('th.sorted, td.sorted-col').length,
              [...t.tBodies[0].rows].filter(r => !r.classList.contains('sec')).map(r => r.cells[0].textContent)]; }""")
    assert state == [False, 0, ['I0', 'I1', 'I2', 'I3', 'I4']]
    assert errors == []


def test_item_heat_ranks_within_a_tier(browser):
    """Ranked over all tiers every tier-I number read red and every tier-IV one green. Tier 1 rows hold
    10 / 30 / 50 (ranked), tier 2 only 20 / 40 (too few to rank) — over all five, 20 would be red."""
    page, _ = _open(browser, _items_page())
    heat = page.evaluate("""() => [...document.querySelectorAll('#items-table .sc[data-col="health_max"]')]
      .map(c => (c.className.match(/hm-[gb]\\d/) || [''])[0])""")
    assert heat == ['hm-b4', '', '', '', 'hm-g4']


def test_history_tip_takes_the_steps_own_direction(browser):
    """A step's fifth element (the item page's direction) wins over the column's polarity: Toxic Bullets'
    anti-heal -30 -> -35 is a buff though its size grew under a "lower is better" name."""
    page, _ = _open(browser, '<span class="fx has-hist" data-pol="-1" data-digits="0" data-title="T" data-odir="buff" '
                             'data-hist=\'[[1,"2026-01-01",-25,-30,"nerf"],[2,"2026-02-01",-30,-35,"buff"]]\'>x</span>')
    page.hover('.fx')
    tip = page.evaluate("() => [...document.querySelectorAll('.hist-tip li .n')].map(n => n.className)")
    assert tip == ['n dir-buff', 'n dir-nerf']
    assert page.evaluate("() => document.querySelector('.hist-tip .t-overall span').className") == 'dir-buff'


def test_history_tip_reads_penalties_by_size_and_names_added_and_removed(browser):
    """Review 2026-10-05: "Sharpshooter Move Speed -0.5 → -1 -100.0%" (it is twice the penalty: +100%), and "—"
    for a value that went read as no value."""
    page, _ = _open(browser, '<span class="fx has-hist" data-pol="1" data-digits="2" data-title="T" '
                             'data-hist=\'[[1,"2026-01-01",null,-0.5],[2,"2026-02-01",-0.5,-1],[3,"2026-03-01",-1,null]]\'>x</span>')
    page.hover('.fx')
    text = page.locator('.hist-tip').inner_text()
    assert '+100.0%' in text and '-100.0%' not in text
    assert 'added' in text and 'removed' in text
    # the "Overall" line reads the same way as its steps (it said −100% over steps of +50% and +33%)
    page, _ = _open(browser, '<span class="fx has-hist" data-pol="1" data-digits="2" data-title="T" '
                             'data-hist=\'[[1,"2026-01-01",-0.5,-0.75],[2,"2026-02-01",-0.75,-1]]\'>x</span>')
    page.hover('.fx')
    overall = page.locator('.hist-tip .t-overall').inner_text()
    assert '(+100.0%)' in overall


def test_souls_per_point_restored_on_back(browser):
    """A "Souls per point" box the browser restored ticked showed raw values."""
    page, _ = _open(browser, _items_page(per_checked=True))
    got = page.evaluate("""() => { const t = document.getElementById('items-table');
      return [t.classList.contains('per-soul'),
              t.querySelector('.sc[data-col="health_max"] b').textContent]; }""")
    assert got == [True, '80']                                       # 800 souls / 10 health


def test_matrix_keeps_its_place_on_resize(browser):
    """A phone's URL bar hiding (a height-only resize) threw a reader of older patches to the newest end."""
    n = 40
    head = '<th class="name">Name</th>' + ''.join(f'<th class="dd">{i}</th>' for i in range(n))
    body = '<td class="name">Row</td>' + ''.join('<td></td>' for _ in range(n))
    html = (f'<div class="table-fade"><div class="table-scroll"><table class="dyn" style="--n-all:{n};--n-new:{n}">'
            f'<colgroup><col class="nm">{"<col>" * n}</colgroup><thead><tr class="cols">{head}</tr></thead>'
            f'<tbody><tr>{body}</tr></tbody></table></div></div>')
    page, _ = _open(browser, html, width=390, height=760)
    sc = '() => document.querySelector(".table-scroll").scrollLeft'
    assert page.evaluate(sc) > 0                                       # opens at the newest end
    page.evaluate('() => { document.querySelector(".table-scroll").scrollLeft = 300; }')
    page.set_viewport_size({'width': 390, 'height': 844})
    page.wait_for_timeout(100)
    assert page.evaluate(sc) == 300
    # a new width keeps the distance from the newest end
    gap = '() => { const s = document.querySelector(".table-scroll"); return s.scrollWidth - s.scrollLeft - s.clientWidth; }'
    before = page.evaluate(gap)
    page.set_viewport_size({'width': 480, 'height': 844})
    page.wait_for_timeout(100)
    assert abs(page.evaluate(gap) - before) <= 1
