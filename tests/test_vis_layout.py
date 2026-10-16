"""The layout pass of the 2026-10-17 visual review: global layout, tables, toolbars, touch ergonomics. Pages are built
inside the test with the site's generator, CSS and scripts (no dist/ needed); `browser` is tests/conftest.py's."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / 'site' / 'styles.css').read_text(encoding='utf-8')
JS = (ROOT / 'site' / 'scripts.js').read_text(encoding='utf-8')

DESK = {'viewport': {'width': 1440, 'height': 900}}
PHONE = {'viewport': {'width': 390, 'height': 844}, 'is_mobile': True, 'has_touch': True, 'device_scale_factor': 2}


def _open(browser, tmp_path: Path, body: str, ctx_args: dict, wide: bool = True, cls: str = ''):
    """A whole site page (nav, main, footer, the site's CSS and JS one level up), offline."""
    from builders.common import page
    shutil.copy(ROOT / 'site' / 'styles.css', tmp_path / 'styles.css')
    shutil.copy(ROOT / 'site' / 'scripts.js', tmp_path / 'scripts.js')
    (tmp_path / 'x').mkdir(exist_ok=True)
    f = tmp_path / 'x' / 'page.html'
    f.write_text(page('X', body, '../', 'heroes', wide=wide, cls=cls), encoding='utf-8')
    ctx = browser.new_context(**ctx_args)
    pg = ctx.new_page()
    pg.route('**/*', lambda r: r.continue_() if r.request.url.startswith('file:') else r.abort())
    errors: list[str] = []
    pg.on('pageerror', lambda e: errors.append(str(e)))
    pg.goto(f.as_uri())
    return ctx, pg, errors


def _table(groups: dict[str, int], n_rows: int = 60) -> str:
    from builders.tables_pages import render_table
    cols = [{'key': f'{g}{i}', 'label': f'{g} stat {i}', 'group': g, 'pol': 1, 'digits': 0}
            for g, n in groups.items() for i in range(n)]
    rows = [{'id': f'r{j}', 'name': f'Row {j}', 'history': {}, 'values': {c['key']: j * 3 + 1 for c in cols}}
            for j in range(n_rows)]
    return render_table(cols, rows, lambda r: f'<td class="name" data-col="name">{r["name"]}</td>', 'Name',
                        table_id='t')


def _stats_page(groups=None, n_rows: int = 60) -> str:
    from builders.tables_pages import _toolbar
    return '<h1>Stats</h1>' + _toolbar('Hero…') + _table(groups or {'Weapon': 14, 'Vitality': 8}, n_rows)


def _rect(pg, sel: str) -> dict:
    return pg.evaluate(f"(() => {{ const r = document.querySelector({sel!r}).getBoundingClientRect();"
                       " return {top: r.top, bottom: r.bottom, left: r.left, right: r.right, h: r.height}; })()")


# ---------- 1. a table's header row is never scrolled away under the site bar ----------

def test_a_tables_header_lands_under_the_stuck_toolbar_at_the_pages_end(browser, tmp_path):
    """Hero Stats: a box 820px tall starting 270px down took its header row to -64px once the page scrolled to its end
    (the box's own sticky header goes with the box). On a desktop the toolbar now stays under the site bar and the box
    fits under both: on the first screen whole (its sideways scrollbar in sight), at the page's end right under them."""
    ctx, pg, errors = _open(browser, tmp_path, _stats_page(), DESK)
    try:
        pg.wait_for_timeout(100)
        assert pg.evaluate("getComputedStyle(document.querySelector('main > .toolbar')).position") == 'sticky'
        assert _rect(pg, '.table-scroll')['bottom'] <= 900
        pg.evaluate('window.scrollTo(0, 1e6)')
        pg.wait_for_timeout(50)
        bar, head = _rect(pg, 'main > .toolbar'), _rect(pg, '#t thead')
        assert bar['top'] == 56                                       # flush under the site bar
        assert abs(head['top'] - bar['bottom']) <= 3, (head, bar)       # the header row right under the toolbar
        assert not errors
    finally:
        ctx.close()


def test_on_a_phone_the_header_lands_under_the_site_bar(browser, tmp_path):
    ctx, pg, errors = _open(browser, tmp_path, _stats_page(), PHONE)
    try:
        pg.wait_for_timeout(100)
        assert pg.evaluate("getComputedStyle(document.querySelector('main > .toolbar')).position") == 'static'
        pg.evaluate('window.scrollTo(0, 1e6)')
        pg.wait_for_timeout(50)
        assert 56 <= _rect(pg, '#t thead')['top'] <= 60                # was -104 at the page's end
        assert pg.evaluate('document.documentElement.scrollWidth') <= 390
        assert not errors
    finally:
        ctx.close()


def test_a_page_of_several_tables_fits_each_under_the_bars():
    """Unit Stats stacks five tables: only the page's last one leaves room for the footer, only the first one is
    held to the first screen (scripts.js table-fit)."""
    block = JS[JS.index("safe('table-fit'"):JS.index("safe('dyn-icons'")]
    assert "querySelectorAll('.table-fade > .table-scroll')" in block
    assert 'after < vh / 3' in block and 'desk && i === 0' in block
    assert 'fitH' not in JS                                            # the matrices' own fit is gone (one module)


# ---------- 2. a wide table says it scrolls ----------

def test_a_wide_table_shows_its_right_edge_until_scrolled_to_the_end(browser, tmp_path):
    ctx, pg, errors = _open(browser, tmp_path, _stats_page({'Weapon': 30}, 10), DESK)
    try:
        pg.wait_for_timeout(100)
        wrap = "document.querySelector('.table-fade')"
        assert not pg.evaluate(f"{wrap}.classList.contains('at-end')")
        assert pg.evaluate(f"getComputedStyle({wrap}, '::after').opacity") == '1'
        assert 'svg' in pg.evaluate(f"getComputedStyle({wrap}, '::before').webkitMaskImage")   # the arrow
        # the shadow sits on the content's edge: right of it only the box's border and its scrollbar
        r = pg.evaluate("(() => { const s = document.querySelector('.table-scroll');"
                        " return s.offsetWidth - s.clientWidth - s.clientLeft; })()")
        assert pg.evaluate(f"{wrap}.style.getPropertyValue('--fade-r')") == f'{r}px'
        pg.evaluate("document.querySelector('.table-scroll').scrollLeft = 1e6")
        pg.wait_for_function(f"{wrap}.classList.contains('at-end')")
        pg.wait_for_timeout(300)
        assert pg.evaluate(f"getComputedStyle({wrap}, '::after').opacity") == '0'
        assert not errors
    finally:
        ctx.close()
    assert 'background: linear-gradient(90deg, transparent, var(--bg-page))' not in CSS     # the invisible fade
    assert 'table.stats th, table.stats td { padding: 3px 4px;' in CSS


# ---------- 3, 4, 5. one page width, a flush toolbar, phone toolbars ----------

def test_wide_pages_start_where_the_brand_does(browser, tmp_path):
    ctx, pg, errors = _open(browser, tmp_path, _stats_page(n_rows=5), {'viewport': {'width': 1920, 'height': 1080}})
    try:
        brand, h1, bar = _rect(pg, '.nav-brand'), _rect(pg, 'main h1'), _rect(pg, 'main > .toolbar')
        assert brand['left'] == h1['left'] == bar['left'] == 134         # was 134 / 20 / 20
        foot = pg.evaluate("(() => { const f = document.querySelector('footer.site-foot');"
                           " return f.getBoundingClientRect().left + parseFloat(getComputedStyle(f).paddingLeft); })()")
        assert foot == 134
        assert not errors
    finally:
        ctx.close()
    assert '.page.wide { max-width: var(--content-w); }' in CSS and '.page.wide { max-width: none; }' not in CSS


def test_a_toolbar_sticks_flush_under_the_site_bar():
    assert 'position: sticky; top: var(--nav-h); z-index: var(--z-sticky);' in CSS
    assert 'top: calc(var(--nav-h) + 2px)' not in CSS


def test_on_a_phone_an_index_toolbar_scrolls_away_and_loses_its_separators(browser, tmp_path):
    body = ('<h1>Heroes</h1><div class="toolbar"><input type="search"><span class="sep"></span>'
            '<label class="switch"><input type="checkbox"><span class="track"></span>Pre-release</label>'
            '<span class="sep"></span><button class="px-btn">Movement</button></div>'
            '<div style="height: 3000px"></div>')
    for args, pos, sep in ((PHONE, 'static', 'none'), (DESK, 'sticky', 'block')):
        ctx, pg, errors = _open(browser, tmp_path, body, args)
        try:
            assert pg.evaluate("getComputedStyle(document.querySelector('main > .toolbar')).position") == pos
            assert pg.evaluate("getComputedStyle(document.querySelector('.toolbar .sep')).display") == sep
            assert not errors
        finally:
            ctx.close()


# ---------- 6. a group's name stays in sight; Item Stats on a phone ----------

def test_a_groups_name_stays_in_sight_over_a_group_running_off_the_screen(browser, tmp_path):
    from builders.tables_pages import render_table  # noqa: F401  (the markup: a span per group name)
    assert '<span class="cl">Weapon</span></th>' in _table({'Weapon': 2}, 1)
    ctx, pg, errors = _open(browser, tmp_path, _stats_page(), PHONE)
    try:
        pg.wait_for_timeout(100)
        box = _rect(pg, '.table-scroll')
        names = _rect(pg, '#t thead tr.cols th.name')

        def seen(group: str) -> bool:
            r = _rect(pg, f'#t thead th[data-group="{group}"] .cl')
            return r['left'] >= names['right'] - 1 and r['right'] <= box['right']
        assert seen('Weapon')                         # centred over 14 columns it sat ~250px off the screen
        pg.evaluate("document.querySelector('.table-scroll').scrollLeft = 1e6")
        pg.wait_for_timeout(50)
        assert seen('Vitality')
        assert not errors
    finally:
        ctx.close()


def test_item_stats_rows_are_one_line_on_a_phone(browser, tmp_path):
    body = ('<div class="table-fade"><div class="table-scroll"><table class="stats" id="items-table"><thead>'
            '<tr class="cols"><th class="name">Item</th><th data-col="tier">Tier</th><th data-col="cost">Cost</th>'
            '<th>Stats</th></tr></thead><tbody><tr><td class="name"><a href="#"><span class="nm">Close Quarters</span>'
            '</a></td><td data-col="tier">1</td><td data-col="cost">800</td><td class="sumc"><div class="chips">'
            + '<span class="sc"><b>+20%</b> <i>Melee Resist</i></span>' * 4 + '</div></td></tr></tbody></table></div></div>')
    ctx, pg, errors = _open(browser, tmp_path, body, PHONE)
    try:
        assert pg.evaluate("getComputedStyle(document.querySelector('td[data-col=tier]')).display") == 'none'
        chips = "document.querySelectorAll('#items-table .sc')"
        tops = pg.evaluate(f"[...{chips}].map(c => Math.round(c.getBoundingClientRect().top))")
        assert len(set(tops)) == 1                                      # one line, not two or three
        cell = _rect(pg, 'td.sumc')
        assert abs(_rect(pg, '#items-table .sc')['left'] - cell['left']) < 16    # from the column's left edge
        assert not errors
    finally:
        ctx.close()


# ---------- 7. the switch reads on / off ----------

def test_a_switch_reads_on_and_off(browser, tmp_path):
    body = ('<label class="switch"><input type="checkbox" id="a"><span class="track"></span>Off</label>'
            '<label class="switch"><input type="checkbox" id="b" checked><span class="track"></span>On</label>'
            '<i id="pat" style="background: var(--patina)"></i><i id="pg" style="background: var(--bg-page)"></i>')
    ctx, pg, errors = _open(browser, tmp_path, body, DESK)
    try:
        bg = "(s) => getComputedStyle(document.querySelector(s)).backgroundColor"
        assert pg.evaluate(bg, '#b + .track') == pg.evaluate(bg, '#pat')            # on: filled copper
        assert pg.evaluate(bg, '#a + .track') == pg.evaluate(bg, '#pg')             # off: the dark slot
        knob = "(s) => getComputedStyle(document.querySelector(s), '::after').left"
        assert pg.evaluate(knob, '#a + .track') == '4px' and pg.evaluate(knob, '#b + .track') == '18px'
        assert not errors
    finally:
        ctx.close()


# ---------- 8. Item Stats chips: no empty slot, one fill ----------

def test_a_chip_without_an_icon_has_no_empty_slot():
    from builders.tables_pages import _chip
    bare = _chip('sc', '+20%', 'Melee Resist', None, '', '../')
    assert 'class="pi"' not in bare and bare.startswith('<span class="sc"><b>+20%</b>')
    assert '.sc > b:first-child, .fx > b:first-child { margin-left: 3px; }' in CSS


def test_a_chips_rank_is_a_bar_not_its_fill(browser, tmp_path):
    body = ('<table class="stats"><tbody><tr><td><span class="sc f-v hm-b4" id="c"><b>+30</b> <i>Bonus Health</i>'
            '</span><span class="sc f-w" id="d"><b>+8%</b> <i>Weapon Damage</i></span></td></tr></tbody></table>')
    ctx, pg, errors = _open(browser, tmp_path, body, DESK)
    try:
        bg = "(s) => getComputedStyle(document.querySelector(s)).backgroundColor"
        assert pg.evaluate(bg, '#c') == pg.evaluate(bg, '#d')           # one fill, whatever the rank
        bar = "getComputedStyle(document.querySelector('#c'), '::before')"
        assert pg.evaluate(f"{bar}.content") != 'none' and pg.evaluate(f"{bar}.height") == '2px'
        assert not errors
    finally:
        ctx.close()


# ---------- 9, 10, 12. touch: the way up, finger-sized targets, words for a finger ----------

def test_on_a_touch_screen_the_way_up_shows_only_while_going_up(browser, tmp_path):
    from builders.history_view import history_table
    ch = {'op': 'change', 'cat': 'balance', 'label': 'Cooldown', 'old_s': '27', 'new_s': '29', 'dir': 'nerf',
          'pct': 7.4, 'grad': 2, 'status': 'documented', 'path': 'x'}
    rows = [({'id': f'p{i}', 'date': f'2025-{i:02d}-01', 'title': f'{i:02d}-01-2025 Update'}, [{**ch, 'key': f'k{i}'}])
            for i in range(1, 13)]
    hist = history_table([('abilities.vdata:x', 'X', None)], ['X'], {'abilities.vdata:x': rows}, {}, '../')
    ctx, pg, errors = _open(browser, tmp_path, '<div style="height: 4000px"></div>' + hist, PHONE, wide=False,
                            cls='entity')
    try:
        on = "document.querySelector('.back-to-top').classList.contains('on')"
        pg.evaluate('window.scrollTo(0, 2500)')
        pg.wait_for_timeout(50)
        assert not pg.evaluate(on)                                       # going down: out of the way
        pg.evaluate('window.scrollTo(0, 2300)')
        pg.wait_for_function(on)                                         # going up: there
        size = pg.evaluate("document.querySelector('.back-to-top').getBoundingClientRect().width")
        assert size == 32 and pg.evaluate("getComputedStyle(document.querySelector('.back-to-top')).opacity") < '1'
        assert not errors
    finally:
        ctx.close()


def test_small_links_get_a_fingers_hit_area_and_keep_their_look(browser, tmp_path):
    body = ('<div class="banner"><span class="bt">01-01-2026 Update</span><span class="bc">'
            '<a class="pnotes" href="#p">patch ↗</a></span></div>'
            '<p>x <span class="trail"><a class="sq t-buff" href="#a"></a><span class="sq"></span>'
            '<a class="sq t-nerf cur" href="#b"></a></span> y</p>')
    sizes = {}
    for name, args in (('desk', DESK), ('phone', PHONE)):
        ctx, pg, errors = _open(browser, tmp_path, body, args)
        try:
            sizes[name] = pg.evaluate(
                "(() => { const r = s => document.querySelector(s).getBoundingClientRect();"
                " return {pn: r('.pnotes').height, sq: r('.trail a.sq').height, trail: r('.trail').top,"
                " p: r('p').height, bt: r('.banner .bt').left}; })()")
            assert not errors
        finally:
            ctx.close()
    assert sizes['desk']['pn'] < 24 <= sizes['phone']['pn']
    assert sizes['desk']['sq'] == 12 and sizes['phone']['sq'] == 24
    # the look: the squares' line is as tall as before (their bigger boxes pushed it 6px taller at first)
    assert sizes['phone']['p'] == sizes['desk']['p']
    assert '@media (pointer: coarse)' in CSS and 'th.dd > a::after' in CSS


def test_touch_words_say_tap(browser, tmp_path):
    from builders.tables_pages import _toolbar
    body = (_toolbar('Hero…') + '<p><a class="mark hidden" href="#build" '
            'data-tooltip="Not in patch notes — in the game files of build 6790 · click to open that build"></a></p>')
    # a tablet: a phone hides the legend's second half altogether
    tablet = {'viewport': {'width': 820, 'height': 1180}, 'is_mobile': True, 'has_touch': True}
    for args, word in ((DESK, 'hover'), (tablet, 'tap')):
        ctx, pg, errors = _open(browser, tmp_path, body, args)
        try:
            tail = pg.evaluate("document.querySelector('.lg-tail').innerText").strip().lower()
            assert tail.startswith(f'· {word} a value'), tail
            if word == 'tap':
                pg.tap('a.mark')
                assert 'tap again to open that build' in pg.locator('.tip.on').inner_text()
                assert not pg.evaluate("location.hash")                   # the first tap only shows the words
            assert not errors
        finally:
            ctx.close()


# ---------- 11. quiet text you can still read ----------

def _token(name: str) -> str:
    return re.search(rf'--{name}:\s*(#[0-9a-f]{{6}})', CSS).group(1)


def _lum(hx: str) -> float:
    def ch(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hx[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def test_the_dimmest_text_reads_on_every_panel():
    """VT323 caps in --text-dimmer measured ~3:1 ("2 OF THEM IN GAME RULES & MAP OBJECTS", "×3")."""
    dimmer = _lum(_token('text-dimmer'))
    for bg in ('bg-page', 'bg-panel', 'bg-panel-2', 'bg-panel-3'):
        assert (dimmer + 0.05) / (_lum(_token(bg)) + 0.05) >= 4.5, bg
    assert dimmer < _lum(_token('text-dim'))                            # still quieter than the dim text
