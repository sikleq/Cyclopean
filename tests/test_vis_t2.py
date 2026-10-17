"""Tables and matrices of the 2026-10-17 visual review, round 2: whole month labels on the change matrices, tables that
line up with their page, a phone's folded filter bar, one item-tier notation and shop order, the Game rules table on a
phone. Pages are built in the test with the site's generator, CSS and scripts (no dist/ needed); `browser` is
tests/conftest.py's."""
from __future__ import annotations

import re
import shutil
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / 'site' / 'styles.css').read_text(encoding='utf-8')
JS = (ROOT / 'site' / 'scripts.js').read_text(encoding='utf-8')

DESK = {'viewport': {'width': 1440, 'height': 900}}
WIDE = {'viewport': {'width': 1920, 'height': 1080}}
PHONE = {'viewport': {'width': 390, 'height': 844}, 'is_mobile': True, 'has_touch': True, 'device_scale_factor': 2}


def _open_html(browser, tmp_path: Path, html: str, ctx_args: dict):
    """A whole page (the site's CSS and JS one level up), offline."""
    shutil.copy(ROOT / 'site' / 'styles.css', tmp_path / 'styles.css')
    shutil.copy(ROOT / 'site' / 'scripts.js', tmp_path / 'scripts.js')
    (tmp_path / 'x').mkdir(exist_ok=True)
    f = tmp_path / 'x' / 'page.html'
    f.write_text(html, encoding='utf-8')
    ctx = browser.new_context(**ctx_args)
    pg = ctx.new_page()
    pg.route('**/*', lambda r: r.continue_() if r.request.url.startswith('file:') else r.abort())
    errors: list[str] = []
    pg.on('pageerror', lambda e: errors.append(str(e)))
    pg.goto(f.as_uri())
    return ctx, pg, errors


def _open(browser, tmp_path: Path, body: str, ctx_args: dict):
    from builders.common import page
    return _open_html(browser, tmp_path, page('X', body, '../', 'heroes', wide=True), ctx_args)


def _left(pg, sel: str) -> float:
    return pg.evaluate(f"document.querySelector({sel!r}).getBoundingClientRect().left")


# ---------- 1. a month's label is whole, short or out of sight — never cut ----------

# months of 1-6 patches (a one-patch month cannot hold "2025-07"), 62 patches: wider than a 1440 window
_PER_MONTH = (3, 1, 2, 4, 1, 5, 2, 1, 6, 3, 2, 1, 4, 5, 2, 3, 1, 6, 4, 2, 4)


def _dates() -> list[str]:
    out, d = [], date(2024, 11, 1)
    for n in _PER_MONTH:
        out += [(d + timedelta(days=3 + 4 * i)).isoformat() for i in range(n)]
        d = (d + timedelta(days=32)).replace(day=1)
    return out


def _matrix(n_rows: int = 6, kind: str = 'hero') -> str:
    """A change matrix as dynamics_page.matrix_html lays it out (its own head; empty cells): the cutoff splits a
    month, so its newer part is a `cont` header; 54 newer patches, wider than a 1440 window."""
    from builders.dynamics_page import _head
    dates = _dates()
    rows = [{'id': d, 'date': d, 'title': ''} for d in dates]
    cutoff = dates[7][:8] + '10'                                      # inside a month: two old patches, two new
    n_new = sum(d >= cutoff for d in dates)
    cells = ''.join(f'<td{" class=old" if d < cutoff else ""}></td>' for d in dates)
    body = ''.join(f'<tr data-cat="w"><td class="name"><a href="#">Row {i}</a></td>{cells}</tr>' for i in range(n_rows))
    return (f'<div class="table-fade"><div class="table-scroll"><table class="dyn" id="dyn-{kind}" '
            f'style="--n-all:{len(dates)};--n-new:{n_new}">{_head(rows, cutoff, "Hero")}<tbody>{body}</tbody></table>'
            f'</div></div>')


_SWEEP = """async (step) => {
  const sc = document.querySelector('.table-scroll'), name = document.querySelector('thead tr.cats th.name');
  const frames = () => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
  const max = sc.scrollWidth - sc.clientWidth, cut = [], states = {};
  for (let x = 0; ; x = Math.min(x + step, max)) {
    sc.scrollLeft = x;
    await frames();
    const L = name.getBoundingClientRect().right, box = sc.getBoundingClientRect();
    const R = box.left + sc.clientLeft + sc.clientWidth;
    for (const th of document.querySelectorAll('thead tr.cats th.dm')) {
      const cs = getComputedStyle(th);
      if (cs.display === 'none' || cs.color === 'rgba(0, 0, 0, 0)') continue;     // hidden, or the split month's part
      const t = th.getBoundingClientRect(), s = th.querySelector('.ml');
      if (t.right <= L + 0.5 || t.left >= R - 0.5) continue;                      // out of sight
      const c = s.classList, st = c.contains('none') ? 'none' : c.contains('sl') || c.contains('sr') ||
        th.classList.contains('one') ? 'short' : 'full';
      states[st] = (states[st] || 0) + 1;
      if (getComputedStyle(s).visibility === 'hidden') continue;
      // what shows: the label (a one-patch month's is short), or the short one at an end of the transparent long one
      const box = s.getBoundingClientRect();
      let left = box.left, right = box.right;
      if (c.contains('sl')) right = left + parseFloat(getComputedStyle(s, '::before').width);
      if (c.contains('sr')) left = right - parseFloat(getComputedStyle(s, '::after').width);
      if (right - left < 8 || left < L - 0.5 || right > R + 0.5 || left < t.left - 0.5 || right > t.right + 0.5)
        cut.push([x, th.textContent, st, Math.round(left), Math.round(right), Math.round(L), Math.round(R)]);
    }
    if (x >= max) break;
  }
  return {cut, states, max};
}"""


@pytest.mark.parametrize('ctx_args', [DESK, PHONE], ids=['desk', 'phone'])
@pytest.mark.parametrize('show_old', [False, True])
def test_no_month_label_is_ever_cut_at_any_scroll_position(browser, tmp_path, ctx_args, show_old):
    """Hero / Item / Unit / Game changes: the first month read "025-12" — its label, centred over the whole month,
    sat half under the sticky names (review 2026-10-17). The label is sticky in its header and dyn-months makes it
    short ("Dec") or hides it when even that has no room: swept every 9px, Older patches off and on."""
    ctx, pg, errors = _open(browser, tmp_path, _matrix(), ctx_args)
    try:
        if show_old:
            pg.evaluate("document.getElementById('dyn-hero').classList.add('show-old')")
        got = pg.evaluate(_SWEEP, 9)
        assert got['max'] > 300 and not got['cut'], got['cut'][:5]
        assert got['states'].get('full') and got['states'].get('short')     # one-patch months read "Dec"
        assert not errors
    finally:
        ctx.close()


def test_a_label_shortens_only_when_its_month_has_no_room(browser, tmp_path):
    """Whole wherever it fits: at the newest end every month in sight with two columns or more reads "2026-03"."""
    ctx, pg, errors = _open(browser, tmp_path, _matrix(), DESK)
    try:
        pg.wait_for_timeout(100)
        got = pg.evaluate("""() => {
          const sc = document.querySelector('.table-scroll'), L = document.querySelector('thead tr.cats th.name')
            .getBoundingClientRect().right, R = sc.getBoundingClientRect().right;
          return [...document.querySelectorAll('thead tr.cats th.dm')].filter(th => {
            const t = th.getBoundingClientRect();
            return getComputedStyle(th).display !== 'none' && t.left >= L && t.right <= R && t.width >= 59;
          }).map(th => [th.textContent, th.querySelector('.ml').className]);
        }""")
        assert len(got) >= 8 and all(cls == 'ml' for _, cls in got), got
        assert not errors
    finally:
        ctx.close()


def test_month_label_carries_its_short_form():
    from builders.dynamics_page import month_label
    assert month_label('2025-12') == '<span class="ml" data-s="Dec">2025-12</span>'
    assert 'data-s="May"' in month_label('2026-05')
    # sticky in its header (the compositor moves it); scripts.js only switches its state, never its place: a label moved
    # from a script re-laid the matrix out every frame of a sideways scroll. A vertical scroll returns at once
    block = JS[JS.index("safe('dyn-months'"):JS.index("safe('table-fit'")]
    assert 'sl === lastSl) return;' in block and '.style.' not in block and 'var EDGE = 4, FADE = 22;' in block
    assert ('th.dm > .ml { display: inline-block; position: sticky; left: calc(var(--dyn-name) + 4px); right: 22px;'
            in CSS)
    from builders.dynamics_page import _head
    head = _head([{'id': d, 'date': d, 'title': ''} for d in ('2026-01-05', '2026-02-03', '2026-02-09')], '', 'Hero')
    assert '<th class="dm one" colspan="1"><span class="ml" data-s="Jan">2026-01</span></th>' in head
    assert '<th class="dm" colspan="2"><span class="ml" data-s="Feb">2026-02</span></th>' in head


def test_a_vertical_scroll_leaves_the_month_labels_alone(browser, tmp_path):
    """A label's place and state change with the sideways scroll only: scrolling down writes nothing."""
    ctx, pg, errors = _open(browser, tmp_path, _matrix(60), DESK)
    try:
        pg.wait_for_timeout(100)
        writes = pg.evaluate("""async () => {
          const sc = document.querySelector('.table-scroll'), frames = () => new Promise(r =>
            requestAnimationFrame(() => requestAnimationFrame(r)));
          sc.scrollLeft = 200; await frames();
          let n = 0;
          const mo = new MutationObserver(l => { n += l.length; });
          document.querySelectorAll('.ml').forEach(s => mo.observe(s, {attributes: true}));
          for (let y = 0; y < 1500; y += 100) { sc.scrollTop = y; await frames(); }
          const down = n;
          sc.scrollLeft = 20; await frames();
          return [down, n - down];
        }""")
        assert writes[0] == 0 and writes[1] > 0, writes
        assert not errors
    finally:
        ctx.close()


# ---------- 2. tables line up with their page ----------

def _units_like() -> str:
    from builders.tables_pages import _toolbar, render_table

    def table(groups: dict[str, int]) -> str:
        cols = [{'key': f'{g}{i}', 'label': f'{g} stat {i}', 'group': g, 'pol': 1, 'digits': 0}
                for g, n in groups.items() for i in range(n)]
        rows = [{'id': f'r{j}', 'name': f'Row {j}', 'history': {}, 'values': {c['key']: j for c in cols}}
                for j in range(3)]
        return render_table(cols, rows, lambda r: f'<td class="name" data-col="name">{r["name"]}</td>', 'Unit')
    band = '<div class="banner sub tbl-sec building"><span class="bt">{}</span><span class="bc">3</span></div>'
    return ('<h1>Unit Stats</h1>' + _toolbar('Unit…') + band.format('Buildings') + table({'Vitality': 9, 'Attack': 7})
            + band.format('Troopers') + table({'Vitality': 3}) + band.format('Neutral') + table({'Attack': 2}))


def test_unit_stats_tables_start_at_their_bands_left_edge(browser, tmp_path):
    """Unit Stats: four tables of four widths, centred under full-width bands, had four left edges (review
    2026-10-17): every table starts where its band, the bar and the title do."""
    ctx, pg, errors = _open(browser, tmp_path, _units_like(), WIDE)
    try:
        lefts = pg.evaluate("[...document.querySelectorAll('main h1, main > .toolbar, .tbl-sec, .table-fade')]"
                            ".map(e => Math.round(e.getBoundingClientRect().left))")
        widths = pg.evaluate("[...document.querySelectorAll('.table-fade')].map(e => e.getBoundingClientRect().width)")
        assert len(set(lefts)) == 1, lefts
        assert len(set(widths)) == 3 and max(widths) < 1500                 # each hugs its table
        assert not errors
    finally:
        ctx.close()


def test_a_matrix_starts_under_its_bar(browser, tmp_path):
    """At 1920 a matrix narrower than the page sat 23px right of its bar and title."""
    from builders.dynamics_page import toolbar
    ctx, pg, errors = _open(browser, tmp_path, '<h1>Hero changes</h1>' + toolbar('hero', 0, '') + _matrix(), WIDE)
    try:
        assert _left(pg, '.table-fade') == _left(pg, 'main > .toolbar') == _left(pg, 'main h1')
        assert not errors
    finally:
        ctx.close()
    assert '.table-fade.center' not in CSS and "classList.add('center')" not in JS


def _rules_html(monkeypatch) -> str:
    import builders.game_systems as gs
    from builders.game_rules import rules_page
    from test_game_section import cv
    raw = [({'id': '2026-03-10', 'date': '2026-03-10'},
            [cv('citadel_player_spawn_time_max_ramp_1', op='add', new='30', build=6395),
             cv('citadel_bounty_aoe_radius_non_troopers_non_hero', op='add', new='1378', build=6395)]),
           ({'id': '2026-06-30', 'date': '2026-06-30'}, [cv('citadel_player_spawn_time_max_ramp_1', old='30', new='35')]),
           ({'id': '2026-09-20', 'date': '2026-09-20'},
            [cv('citadel_player_spawn_time_min', op='add', new='5', build=6700)])]
    monkeypatch.setattr(gs, 'convar_start', lambda: 6395)
    return rules_page(raw)


def test_game_rules_starts_under_its_title(browser, tmp_path, monkeypatch):
    """Game rules centred its 776px table and search under a title and tabs at the left (review 2026-10-17)."""
    ctx, pg, errors = _open_html(browser, tmp_path, _rules_html(monkeypatch), DESK)
    try:
        h1 = _left(pg, 'main h1')
        assert _left(pg, '.rules-col > .toolbar') == _left(pg, 'table.game-rules') == h1
        assert not errors
    finally:
        ctx.close()


# ---------- 3. a phone folds a table's filters ----------

def _items_bar_page() -> str:
    from builders.tables_pages import _toolbar, item_filter_chips
    rows = ''.join(f'<tr data-cat="w" data-tier="1" data-kind="passive"><td class="name" data-col="name">Item {i}</td>'
                   f'<td data-col="cost" data-sort="800">800</td></tr>' for i in range(40))
    table = ('<div class="table-fade"><div class="table-scroll"><table class="stats" id="items-table"><thead>'
             '<tr class="cats"><th class="name"></th><th class="cat">Shop</th></tr><tr class="cols">'
             '<th class="name" data-col="name">Item</th><th data-col="cost">Cost</th></tr></thead>'
             f'<tbody>{rows}</tbody></table></div></div>')
    return '<h1>Item Stats</h1>' + _toolbar('Item…', extra='<span class="sep"></span>' + item_filter_chips(),
                                            heat_on=True) + table


def test_a_phone_folds_the_filters_behind_one_button(browser, tmp_path):
    """Hero changes' bar took ~440px of an 844px phone, Item Stats' ~400px, before the first row (review
    2026-10-17): on a phone all but the search folds into "Filters", which counts what is on; folded, the options
    keep their state; the summary opens with the keyboard."""
    ctx, pg, errors = _open(browser, tmp_path, _items_bar_page(), PHONE)
    try:
        pg.wait_for_timeout(50)
        assert pg.evaluate("getComputedStyle(document.querySelector('.tb-opts')).display") == 'none'
        bar = pg.evaluate("document.querySelector('main > .toolbar').getBoundingClientRect().height")
        assert bar < 80                                                    # the search and the button: one row
        summary = pg.locator('.tb-fold > summary')
        assert summary.inner_text().strip() == 'Filters'
        summary.tap()
        assert pg.evaluate("getComputedStyle(document.querySelector('.tb-opts')).display") == 'flex'
        pg.tap('button[data-f="cat"][data-v="w"]')
        pg.tap('label.switch:has(input[data-stat-cols]) .track')
        pg.wait_for_timeout(50)
        summary.tap()
        assert pg.evaluate("getComputedStyle(document.querySelector('.tb-opts')).display") == 'none'
        assert re.sub(r'\s+', ' ', summary.inner_text()).strip() == 'Filters (2 active)'
        assert pg.get_attribute('button[data-f="cat"][data-v="w"]', 'aria-pressed') == 'true'
        assert pg.evaluate("document.querySelector('input[data-stat-cols]').checked")
        # the heatmap is on by default: turning it off is no filter, turning the columns off again leaves one
        summary.focus()
        pg.keyboard.press('Enter')
        assert pg.evaluate("document.querySelector('.tb-fold').open")
        pg.tap('label.switch:has(input[data-stat-cols]) .track')
        pg.tap('label.switch:has(input[data-heatmap]) .track')
        pg.wait_for_timeout(50)
        assert '(1 active)' in summary.inner_text()
        assert pg.evaluate('document.documentElement.scrollWidth') <= 390
        assert not errors
    finally:
        ctx.close()


def test_a_desktop_bar_has_no_fold(browser, tmp_path):
    """A wider screen keeps the bar as it was: no "Filters" button, the switches beside the search."""
    ctx, pg, errors = _open(browser, tmp_path, _items_bar_page(), DESK)
    try:
        assert pg.evaluate("getComputedStyle(document.querySelector('.tb-fold')).display") == 'none'
        assert pg.evaluate("getComputedStyle(document.querySelector('.tb-opts')).display") == 'contents'
        search, heat = (pg.evaluate(f"document.querySelector({s!r}).getBoundingClientRect().top")
                        for s in ('.toolbar input[type=search]', 'label.switch:has(input[data-heatmap])'))
        assert abs(search - heat) < 12
        assert not errors
    finally:
        ctx.close()


def test_every_table_and_matrix_bar_folds():
    from builders.dynamics_page import toolbar
    from builders.tables_pages import _toolbar
    for bar in (_toolbar('Hero…', details=True), toolbar('hero', 1, 'Pre-release', ('Brawler',)), toolbar('item', 3, 'Removed')):
        head, opts = bar.split('<div class="tb-opts">')
        assert '<input type="search"' in head and '<summary class="px-btn">Filters <span class="tb-n"></span>' in head
        assert 'type="checkbox"' in opts and 'type="checkbox"' not in head
    assert ':has(' not in CSS.split('.tb-fold { display: none; }')[1].split('/* ----------')[0]


def test_a_matrix_row_filter_looks_pressed(browser, tmp_path):
    """Item changes' Weapon / Tier 2 and Hero changes' roles filtered the rows but looked like the rest (aria-pressed
    alone): a chosen one is `.on`, like the part buttons and Item Stats' chips."""
    from builders.dynamics_page import toolbar
    ctx, pg, errors = _open(browser, tmp_path, toolbar('item', 0, '') + _matrix(2, 'item'), DESK)
    try:
        btn = 'button[data-rowf="cat"][data-v="s"]'
        pg.click(btn)
        assert 'on' in pg.get_attribute(btn, 'class').split()
        pg.click('button[data-rowf="cat"][data-v="w"]')
        assert 'on' not in pg.get_attribute(btn, 'class').split()
        pg.click('button[data-rowf="cat"][data-v="w"]')
        assert not pg.evaluate("document.querySelectorAll('.dyn-rows .on').length")
        assert not errors
    finally:
        ctx.close()


# ---------- 4. one tier notation, the game's shop order ----------

def test_item_tiers_read_tier_1_and_categories_follow_the_shop():
    """Tier read "TIER 4" on a chip, "Tier I" on Item Stats, "I" on Item changes; Item changes ran Weapon / Vitality /
    Spirit, Item Stats and the game's shop Weapon / Spirit / Vitality (review 2026-10-17)."""
    from builders.dynamics_page import ITEM_SLOTS, toolbar
    from builders.tables_pages import ITEM_SECTIONS, item_filter_chips
    chips = item_filter_chips()
    assert [f'>Tier {n}</button>' in chips for n in (1, 2, 3, 4)] == [True] * 4 and 'Tier I' not in chips
    bar = toolbar('item', 0, '')
    assert re.findall(r'data-rowf="tier" data-v="\d" aria-pressed="false">([^<]+)<', bar) == [
        'Tier 1', 'Tier 2', 'Tier 3', 'Tier 4', 'Tier 5']
    assert re.findall(r'data-rowf="cat" data-v="(\w)"', bar) == ['w', 's', 'v']
    assert [lbl for _, _, lbl in ITEM_SLOTS] == [slot for slot, _, _ in ITEM_SECTIONS] == ['Weapon', 'Spirit', 'Vitality']
    # the Stats header is a plain "Always on" (it read "Always on ▸ columns")
    assert 'columns"; color: var(--patina)' not in CSS and 'th.sumc::after' not in CSS


# ---------- 5. Game rules on a phone ----------

def test_game_rules_names_break_at_underscores_and_the_counts_ride_under_the_date(browser, tmp_path, monkeypatch):
    """A phone broke "citadel_bounty_a / oe_deny_radius" mid-word, and Changes and Last change — mostly dashes —
    took 45% of the width (review 2026-10-17)."""
    html = _rules_html(monkeypatch)
    assert '<code>citadel_<wbr>player_<wbr>spawn_<wbr>time_<wbr>max_<wbr>ramp_<wbr>1</code>' in html
    ctx, pg, errors = _open_html(browser, tmp_path, html, PHONE)
    try:
        got = pg.evaluate("""() => {
          const shown = el => getComputedStyle(el).display !== 'none';
          // a piece between two break chances never wraps inside itself
          const split = [...document.querySelectorAll('td.nm code')].flatMap(c => [...c.childNodes])
            .filter(n => n.nodeType === 3).filter(n => {
              const r = document.createRange(); r.selectNodeContents(n); return r.getClientRects().length > 1; })
            .map(n => n.textContent);
          return {split, cn: [...document.querySelectorAll('table.game-rules .cn')].some(shown),
                  under: [...document.querySelectorAll('td.lc .lc-n')].filter(shown).map(e => e.textContent),
                  heads: [...document.querySelectorAll('table.game-rules thead th')].filter(shown).map(e => e.textContent),
                  wide: document.documentElement.scrollWidth};
        }""")
        assert not got['split'] and not got['cn'] and got['wide'] <= 390
        assert got['heads'] == ['Console variable', 'Now', 'Last change']
        assert sorted(got['under']) == ['1 change', 'NEW']
        assert not errors
    finally:
        ctx.close()
    ctx, pg, errors = _open_html(browser, tmp_path, html, DESK)
    try:
        assert pg.evaluate("[...document.querySelectorAll('table.game-rules thead th')].map(e => e.textContent)") == [
            'Console variable', 'Now', 'Changes', 'Last change']
        assert not pg.evaluate("[...document.querySelectorAll('.lc-n')].some(e => getComputedStyle(e).display !== 'none')")
        assert not errors
    finally:
        ctx.close()
