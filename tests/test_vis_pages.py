"""Visual pass 2026-10-17, the "pages" track: the home page, the patch list and patch pages, the index grids, the hover
cards on a touch screen. site/styles.css + site/scripts.js on the builders' own markup in a real browser (the `browser`
fixture of tests/conftest.py)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PHONE = {'width': 390, 'height': 844}


def _open(browser, body: str, width: int = 1440, height: int = 900, touch: bool = False, init: str = '',
          main: str = 'page'):
    """A page of `body` with the site's CSS and JS inline; `touch`: a phone (is_mobile, has_touch: hover is none)."""
    css = (ROOT / 'site' / 'styles.css').read_text(encoding='utf-8')
    js = (ROOT / 'site' / 'scripts.js').read_text(encoding='utf-8')
    opts = {'viewport': {'width': width, 'height': height}}
    if touch:
        opts.update(is_mobile=True, has_touch=True)
    ctx = browser.new_context(**opts)
    page = ctx.new_page()
    errors: list[str] = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    head = f'<script>{init}</script>' if init else ''           # runs before the site's script
    page.set_content(f'<!doctype html><html><head><meta charset="utf-8">'
                     f'<meta name="viewport" content="width=device-width, initial-scale=1"><style>{css}</style>{head}</head>'
                     f'<body><main class="{main}">{body}</main><script>{js}</script></body></html>')
    return ctx, page, errors


# ---- 1. the patch list: every number in its own place --------------------------------------------------------------

# every box of a row with its cell; two boxes of different cells must not meet, none may leave the row
ROW_BOXES = r"""() => {
  const row = document.querySelector('.ix'), R = row.getBoundingClientRect(), boxes = [];
  const add = (sel, cell) => row.querySelectorAll(sel).forEach(e => {
    const r = e.getBoundingClientRect();
    if (r.width && r.height) boxes.push([cell, r]);
  });
  add('.ixd', 'date'); add('.ixt .t', 'title'); add('.ixt .b', 'title'); add('.ixh img', 'faces');
  add('.ixs > span > *', 'counts'); add('.ixa .au', 'notes'); add('.ixa .bar', 'notes');
  const meet = (a, b) => a.left < b.right - 0.5 && b.left < a.right - 0.5 && a.top < b.bottom - 0.5 && b.top < a.bottom - 0.5;
  const hits = [];
  boxes.forEach(([c1, r1], i) => boxes.slice(i + 1).forEach(([c2, r2]) => {
    if (c1 !== c2 && meet(r1, r2)) hits.push(c1 + ' x ' + c2);
  }));
  const out = boxes.filter(([, r]) => r.right > R.right + 0.5 || r.left < R.left - 0.5).map(([c]) => c);
  return {hits: [...new Set(hits)], out: [...new Set(out)], n: boxes.length};
}"""


@pytest.mark.parametrize('width', [1440, 1000, 820, 700, 390])
def test_a_patch_list_row_never_prints_a_number_over_another(browser, width, monkeypatch):
    """Review 2026-10-17: under 1100px the buff / nerf / new / removed counts (4 x 58px) sat in the 90px date column
    and painted over the notes' counts and bar ("✓10 👁46" under "✦31 ✕6")."""
    from builders import patch_counts, patches_pages
    monkeypatch.setattr(patch_counts, 'for_id', lambda pid: {'documented': 10, 'described': 5, 'hidden': 46,
                                                             'not_in_notes': 46, 'changes': 61})
    monkeypatch.setattr(patches_pages, 'hero_names', lambda: {})
    row = {'id': 'p1', 'title': 'Minor Update', 'date': '2026-10-14', 'builds': 4, 'has_notes': True,
           'line_counts': {'mismatch': 6}}
    stats = {'p1': {'tags': {'buff': 8, 'nerf': 14, 'new': 31, 'del': 6},
                    'heroes': ['hero_haze', 'hero_atlas', 'hero_inferno', 'hero_ghost', 'hero_forge']}}
    html = patches_pages._index_row(row, stats, '../', False)
    ctx, page, errors = _open(browser, f'<div class="ixlist">{html}</div>', width=width)
    got = page.evaluate(ROW_BOXES)
    assert got['n'] >= 12 and got['hits'] == [] and got['out'] == [], got
    assert page.evaluate('() => document.documentElement.scrollWidth') <= width and not errors
    ctx.close()


# ---- 2 + 3. a patch page: one column of cards, one row of tabs on a phone ------------------------------------------

@pytest.fixture(scope='module')
def patch_html() -> str:
    from builders import patches_pages
    from builders.common import load_json
    return patches_pages.patch_page(load_json('patches/2026-10-14.json.gz'), None, None)


def test_a_patch_page_is_one_centred_column_like_an_entity_page(patch_html):
    assert '<main class="page column">' in patch_html


def test_a_patch_pages_cards_are_one_under_another(browser):
    """Review 2026-10-17: two columns of cards of any height left black holes (Radiant Regeneration's one row beside
    Baba's 25, Deadman Danny alone with the right half empty)."""
    def card(name: str, rows: int) -> str:
        return (f'<article class="ecard"><div class="ecard-h"><span class="ei"></span><span class="nm">{name}</span></div>'
                f'<div class="eb">{"<p>row</p>" * rows}</div></article>')
    body = '<div class="ecards">' + card('Radiant Regeneration', 1) + card('Baba', 25) + card('Deadman Danny', 6) + '</div>'
    ctx, page, errors = _open(browser, body, width=1920, main='page column')
    boxes = page.evaluate("() => [...document.querySelectorAll('.ecard')].map(e => { const r = e.getBoundingClientRect();"
                          " return [r.left, r.width, r.top, r.bottom]; })")
    assert len({round(b[0]) for b in boxes}) == 1 and len({round(b[1]) for b in boxes}) == 1
    assert all(a[3] <= b[2] for a, b in zip(boxes, boxes[1:]))             # each below the one before
    width = page.evaluate("() => parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--entity-w'))")
    assert boxes[0][1] <= width and not errors
    ctx.close()


def test_a_build_pages_list_of_heroes_wraps_inside_the_column(browser, monkeypatch):
    """In the one column the Cosmetics list of build 6790 (40 hero names on one line) made the page 2646px wide."""
    from builders import builds_pages
    from builders.common import names_by_id
    heroes = sorted(k for k in names_by_id() if k.startswith('hero_'))[:40]
    assert len(heroes) == 40
    monkeypatch.setattr(builds_pages, 'cosmetics', lambda: {'events': [
        {'build': 6790, 'kind': 'base body', 'op': 'add', 'subjects': heroes}]})
    html = builds_pages.cosmetics_section(6790, '../')
    ctx, page, errors = _open(browser, html, width=1440, main='page column')
    assert page.evaluate('() => document.documentElement.scrollWidth') <= 1440 and not errors
    ctx.close()


def test_a_patch_pages_tabs_are_one_row_that_scrolls_on_a_phone(browser, patch_html):
    """Review 2026-10-17: the sticky tab bar wrapped to three rows on a phone (138px; 194 of 844px with the site
    bar). One row that scrolls sideways; opening a tab brings it into sight."""
    bar = re.search(r'<div class="tabs toolbar">.*?</div>', patch_html, re.S).group(0)
    panels = ''.join(f'<div class="tab-panel" id="{k}">{k}</div>' for k in re.findall(r'data-tab="([^"]+)"', bar))
    ctx, page, errors = _open(browser, bar + panels, touch=True, **PHONE)
    got = page.evaluate("""() => { const bar = document.querySelector('.tabs.toolbar');
      const tops = [...bar.children].map(b => Math.round(b.getBoundingClientRect().top / 8));     // a row, give or take
      return [bar.getBoundingClientRect().height, new Set(tops).size, bar.scrollWidth > bar.clientWidth, tops.length]; }""")
    assert got[0] < 64 and got[1] == 1 and got[2] and got[3] >= 4, got
    page.locator('.tabs.toolbar [data-tab]').last.dispatch_event('click')
    inside = page.evaluate("""() => { const bar = document.querySelector('.tabs.toolbar'), b = bar.querySelector('.on');
      const r = b.getBoundingClientRect(), br = bar.getBoundingClientRect();
      return r.left >= br.left - 0.5 && r.right <= br.right + 0.5; }""")
    assert inside and page.evaluate('() => document.documentElement.scrollWidth') <= 390 and not errors
    ctx.close()


def test_a_patch_title_keeps_its_date_whole(browser):
    """Review 2026-10-17: a phone broke "2026-10-14" after "2026-10-" under the patch's name."""
    from builders.common import patch_title_html
    body = (f'<div class="ptitle named"><h1>{patch_title_html({"title": "Minor Update", "date": "2026-10-14"})}</h1>'
            '<span class="steps"><a class="step" href="#">◀</a></span></div>')
    for width in (320, 340, 360, 390):          # wherever the line runs out
        ctx, page, _ = _open(browser, body, width=width)
        got = page.evaluate("""() => { const d = document.querySelector('.ptitle .pdate'),
          n = document.querySelector('.ptitle .pname');
          return [d.getClientRects().length, d.getBoundingClientRect().left, n.getBoundingClientRect().left,
                  d.getBoundingClientRect().top > n.getBoundingClientRect().bottom - 4]; }""")
        assert got[0] == 1, (width, got)
        if got[3]:                               # on a line of its own: it starts at the name's edge
            assert abs(got[1] - got[2]) < 1, (width, got)
        ctx.close()


# ---- 4 + 5. the home page ------------------------------------------------------------------------------------------

TWO_ROWS = [('Bullet Dance', {'op': 'change', 'cat': 'balance', 'label': 'Min Rounds Per Second', 'old_s': '10',
                              'new_s': '12', 'old': 10, 'new': 12, 'dir': 'buff', 'status': 'documented', 'path': 'a'}),
            ('Bullet Dance', {'op': 'change', 'cat': 'balance', 'label': 'Cooldown', 'old_s': '20s', 'new_s': '25s',
                              'old': 20, 'new': 25, 'dir': 'nerf', 'status': 'unannounced', 'path': 'b'})]
# short rows of five tags: a narrow card whose counts fill a line (the "MIXED" chip went to a line of its own)
FIVE_TAGS = [('', {'op': 'add', 'cat': 'balance', 'label': 'HP', 'new_s': '5', 'new': 5, 'status': 'documented',
                   'path': 'a'}),
             ('', {'op': 'rework', 'cat': 'balance', 'label': 'CD', 'old_s': 'a', 'new_s': 'b', 'status': 'documented',
                   'path': 'b'}),
             ('', {'op': 'change', 'cat': 'balance', 'label': 'DPS', 'old_s': '1', 'new_s': '2', 'old': 1, 'new': 2,
                   'dir': 'buff', 'status': 'documented', 'path': 'c'}),
             ('', {'op': 'change', 'cat': 'balance', 'label': 'Ammo', 'old_s': '4', 'new_s': '3', 'old': 4, 'new': 3,
                   'dir': 'nerf', 'status': 'documented', 'path': 'd'}),
             ('', {'op': 'remove', 'cat': 'balance', 'label': 'Slow', 'old_s': '1', 'old': 1, 'status': 'documented',
                   'path': 'e'})]


def _feed(monkeypatch, sections: dict[str, int], rows: list | None = None) -> str:
    """Two updates whose icons are `sections` (section -> how many), with the hover cards' data (`rows` each)."""
    from builders import archive, home_page, patch_counts
    rows = rows or TWO_ROWS
    ids = {'heroes': ['hero_haze', 'hero_atlas', 'hero_inferno', 'hero_ghost', 'hero_forge'],
           'items': ['upgrade_close_range', 'upgrade_clip_size'], 'units': ['npc_trooper_boss']}
    files = {'heroes': 'heroes.vdata', 'items': 'abilities.vdata', 'units': 'npc_units.vdata'}
    from builders.render import not_in_notes
    hidden = sum(1 for _, c in rows if not_in_notes(c))
    feed = {sec: {f'{files[sec]}:{i}': {'n': len(rows), 'hidden': hidden, 'buff': 1, 'nerf': 1, 'kind': '', 'rows': rows}
                  for i in ids[sec][:n]} for sec, n in sections.items()}
    monkeypatch.setattr(home_page, 'update_feed', lambda *a, **k: feed)
    monkeypatch.setattr(archive, 'patch', lambda pid: {'entities': []})
    monkeypatch.setattr(patch_counts, 'for_id', lambda pid: {'not_in_notes': 2, 'hidden_on_pages': 2})
    updates = [{'id': f'p{i}', 'title': 'Minor Update', 'date': f'2026-10-0{i}', 'has_notes': True} for i in (1, 2)]
    return home_page._feed(updates, {}, frozenset(), {})


def test_the_home_feeds_sections_sit_side_by_side_and_every_update_looks_alike(browser, monkeypatch):
    """Review 2026-10-17: the sections stood one under another under a 110px label column (five heroes and two items
    filled 360px of a 1640px card), and the newest update named its icons (four a row on a phone) while the others
    did not (six a row)."""
    html = _feed(monkeypatch, {'heroes': 5, 'items': 2, 'units': 1})
    assert 'lu-nm' not in html and 'lu-row named' not in html
    ctx, page, errors = _open(browser, html, width=1440)
    groups = page.evaluate("() => [...document.querySelectorAll('.update')[0].querySelectorAll('.lu-group')]"
                           ".map(g => { const r = g.getBoundingClientRect(); return [r.left, r.top]; })")
    assert len(groups) == 3 and len({round(t) for _, t in groups}) == 1
    assert groups[0][0] < groups[1][0] < groups[2][0]
    sizes = page.evaluate("() => [...document.querySelectorAll('.lu')].map(a => a.getBoundingClientRect().width)")
    assert len(sizes) == 16 and set(sizes) == {44}
    ctx.close()
    # a phone: the groups wrap, every icon stays inside its card
    ctx, page, errors = _open(browser, html, touch=True, **PHONE)
    out = page.evaluate("""() => [...document.querySelectorAll('.update')].flatMap(u => {
      const R = u.getBoundingClientRect();
      return [...u.querySelectorAll('.lu')].filter(a => a.getBoundingClientRect().right > R.right).map(a => a.href); })""")
    assert out == [] and page.evaluate('() => document.documentElement.scrollWidth') <= 390 and not errors
    ctx.close()


@pytest.mark.parametrize('width', [390, 760])
def test_the_home_counters_and_tiles_share_the_width(browser, width):
    """Review 2026-10-17: on a phone the two counters ended 24px short of the tiles, 6px off their left edge; on a
    tablet the tiles were one a row below 860px (each showed its 6 icons in a 720px box)."""
    from builders import home_page
    body = home_page._top(14706, 5560) + home_page._tiles({'heroes': 43, 'items': 156, 'units': 22, 'game': 12},
                                                          ['x.png'] * 6, ['u.png'] * 6, ['i.png'] * 6)
    ctx, page, errors = _open(browser, body, width=width, height=900, touch=width < 600)
    got = page.evaluate("""() => {
      const box = s => [...document.querySelectorAll(s)].map(e => e.getBoundingClientRect());
      const hs = box('.home-stats .hs'), tiles = box('.htile');
      const over = [...document.querySelectorAll('.home-stats .hs')].filter(e => e.scrollWidth > e.clientWidth).length;
      return {hsLeft: hs[0].left, hsRight: hs[hs.length - 1].right, hsTops: hs.map(r => Math.round(r.top)),
              tileLeft: tiles[0].left, tileRight: Math.max(...tiles.map(r => r.right)), over: over,
              tileTops: tiles.map(r => Math.round(r.top))}; }""")
    if width == 390:
        assert abs(got['hsLeft'] - got['tileLeft']) <= 1 and abs(got['hsRight'] - got['tileRight']) <= 1, got
        assert len(set(got['hsTops'])) == 1 and got['over'] == 0, got           # side by side, nothing sticks out
    else:
        assert got['tileTops'][0] == got['tileTops'][1] and got['tileTops'][2] > got['tileTops'][0], got
    assert page.evaluate('() => document.documentElement.scrollWidth') <= width and not errors
    ctx.close()


# ---- 6. the index grids on a phone ---------------------------------------------------------------------------------

def test_a_phone_shows_three_heroes_and_two_units_a_row(browser):
    """Review 2026-10-17: two 170x235 portraits a row (~5800px for 43 heroes); one unit or Game card a row, a 72px icon
    centred in a 350x150 box."""
    from builders.entities_pages import _card
    from builders.heroes_grid import hero_card
    heroes = ''.join(hero_card({'file': 'heroes.vdata', 'id': f'hero_{i}', 'name': n}, None, '../')
                     for i, n in enumerate(['Abrams', 'Deadman Danny', 'The Doorman', 'Grey Talon', 'Haze', 'Ivy']))
    units = ''.join(_card({'file': 'npc_units.vdata', 'id': f'u{i}', 'name': n, 'alive': True}, None, 'x2')
                    for i, n in enumerate(['Base Defense Sentry', 'Guardian', 'Patron', 'Walker']))
    body = f'<div class="hgrid-cards">{heroes}</div><div class="grid units">{units}</div>'
    ctx, page, errors = _open(browser, body, touch=True, **PHONE)
    rows = page.evaluate("""() => [ '.hgcard', '.grid.units .card' ].map(s => {
      const r = [...document.querySelectorAll(s)].map(e => e.getBoundingClientRect());
      return [new Set(r.map(x => Math.round(x.top))).size, Math.max(...r.map(x => x.height))]; })""")
    assert rows[0][0] == 2 and rows[0][1] < 150, rows                  # six heroes: two rows of three, short crops
    assert rows[1][0] == 2, rows                                        # four units: two rows of two
    names = page.evaluate("() => [...document.querySelectorAll('.hg-nm')].map(n => n.scrollWidth <= n.clientWidth)")
    assert all(names) and page.evaluate('() => document.documentElement.scrollWidth') <= 390 and not errors
    ctx.close()


# ---- 7. hover cards on a touch screen ------------------------------------------------------------------------------

# every click the page saw and whether a handler stopped its link (dyn-tip's capture phase runs first); then the test
# page itself keeps the link from leaving, so the next tap has a page to land on
CLICKS = """window.__clicks = [];
document.addEventListener('click', e => { window.__clicks.push(e.defaultPrevented); e.preventDefault(); }, false);"""


def test_on_a_phone_a_feed_icons_first_tap_shows_its_card_and_the_second_opens_it(browser, monkeypatch):
    """Review 2026-10-17: a tap sent hover and click together, so the icon's page opened at once and its card was never
    seen. The tooltip module's rule: the first tap shows, the second follows, a tap elsewhere hides; the compatibility
    mouseout / focusout a touch browser may fire between two taps (CI's Chromium, 2026-10-06) change nothing."""
    html = _feed(monkeypatch, {'heroes': 2})
    ctx, page, errors = _open(browser, '<p id="away" style="height:120px">x</p>' + html, touch=True, **PHONE)
    assert page.evaluate("() => matchMedia('(hover: none)').matches")
    page.evaluate(CLICKS)
    icon = page.locator('a.lu').first
    icon.tap()
    assert page.evaluate('() => window.__clicks') == [True]
    assert page.locator('.dyn-tip.on').count() == 1 and 'Bullet Dance' in page.locator('.dyn-tip').inner_text()
    # the card's foot speaks to a finger: its second tap opens it (it said "click for its history")
    assert page.locator('.dyn-tip .dt-foot').inner_text().endswith('tap again for its history at this patch')
    # a scroll event landing after the tap (the scroll that brought the icon into sight: CI's Linux Chromium sent it
    # late and it hid the card, 2026-10-17) moves nothing: the card stays
    page.evaluate("() => window.dispatchEvent(new Event('scroll'))")
    assert page.locator('.dyn-tip.on').count() == 1
    page.evaluate("""() => { const a = document.querySelector('a.lu');
      a.dispatchEvent(new MouseEvent('mouseout', {bubbles: true, relatedTarget: document.body}));
      a.dispatchEvent(new FocusEvent('focusout', {bubbles: true})); }""")
    icon.tap()
    assert page.evaluate('() => window.__clicks') == [True, False]           # the second tap follows the link
    ctx.close()
    # a tap elsewhere hides the card; the next tap on the icon shows it again instead of opening it
    ctx, page, errors = _open(browser, '<p id="away" style="height:120px">x</p>' + html, touch=True, **PHONE)
    page.evaluate(CLICKS)
    page.locator('a.lu').first.tap()
    page.locator('#away').tap()
    assert page.locator('.dyn-tip.on').count() == 0
    page.locator('a.lu').first.tap()
    # the icon's first tap, the tap on the paragraph, the icon's tap again: shown again, not opened
    assert page.evaluate('() => window.__clicks') == [True, False, True] and not errors
    ctx.close()


def test_with_a_mouse_a_feed_icon_opens_on_the_first_click(browser, monkeypatch):
    html = _feed(monkeypatch, {'heroes': 2})
    ctx, page, errors = _open(browser, html)
    page.evaluate(CLICKS)
    page.locator('a.lu').first.hover()
    assert page.locator('.dyn-tip.on').count() == 1
    page.locator('a.lu').first.click()
    assert page.evaluate('() => window.__clicks') == [False] and not errors
    ctx.close()


STRIP = ('<div class="patch-strip"><a class="ps-tile" href="#p-2026-01-01" data-k="0" aria-label="update">t</a></div>'
         '<script type="application/json" class="strip-data">{"t": [["2026-01-01", "2026-01-01 update", false, '
         '{"buff": 1}, 0, [], ""]], "g": [], "top": 9, "per": 3, "words": {"buff": "buffs"}, "word1": {"buff": "buff"},'
         ' "eye": ""}</script><div style="height:1400px"></div><section id="p-2026-01-01">band</section>'
         '<div style="height:1400px"></div>')


def test_on_a_phone_a_strip_tiles_first_tap_shows_its_card_before_jumping(browser):
    """The strip's own jump (scripts.js patch-anchor) waits for the second tap too."""
    ctx, page, errors = _open(browser, STRIP, touch=True, **PHONE)
    tile = page.locator('.ps-tile')
    tile.tap()
    assert page.evaluate('() => location.hash') == '' and page.locator('.dyn-tip.on').count() == 1
    page.evaluate("() => window.dispatchEvent(new Event('scroll'))")    # a late scroll event moves nothing
    tile.tap()
    assert page.evaluate('() => location.hash') == '#p-2026-01-01' and not errors
    ctx.close()


def test_a_scroll_that_moves_the_tile_hides_its_card(browser):
    ctx, page, errors = _open(browser, STRIP, touch=True, **PHONE)
    page.locator('.ps-tile').tap()
    assert page.locator('.dyn-tip.on').count() == 1
    page.evaluate('() => window.scrollBy(0, 300)')
    page.wait_for_function("() => !document.querySelector('.dyn-tip.on')")
    assert not errors
    ctx.close()


# the shop's tooltips come from one json: a stand-in for the fetch
SHOP_FETCH = """window.fetch = () => Promise.resolve({ok: true, json: () => Promise.resolve({upgrade_x: '<b>Close Quarters</b>'})});"""
# (the cards' size comes from the shop page's geometry, which this fixture leaves out: a size of their own)
CARD_BOX = 'style="position:relative;display:block;width:120px;height:80px"'
SHOP = ('<p id="away" style="height:100px">x</p><div class="gshop" data-sfx="" data-tips="tips.json" data-hover="w:1">'
        f'<div class="gs-board"><a class="gcard p-w1" {CARD_BOX} href="#item-x" data-id="upgrade_x" data-comp="" '
        f'data-up=""><span class="gc-nm">Close Quarters</span></a><a class="gcard p-w1" {CARD_BOX} href="#item-y" '
        'data-id="upgrade_y" data-comp="" data-up=""><span class="gc-nm">Other</span></a></div></div>')


def test_on_a_phone_a_shop_cards_first_tap_shows_its_tooltip_and_the_second_opens_it(browser):
    """Review 2026-10-17: a tap on a shop card opened the item at once; its tooltip was never seen."""
    ctx, page, errors = _open(browser, SHOP, touch=True, init=SHOP_FETCH, **PHONE)
    card = page.locator('.gcard').first
    card.tap()
    page.wait_for_function("() => !document.querySelector('.gs-tip').hidden")
    assert page.evaluate('() => location.hash') == '' and 'is-me' in card.get_attribute('class')
    assert 'Close Quarters' in page.locator('.gs-tip').inner_text()
    card.tap()
    assert page.evaluate('() => location.hash') == '#item-x'
    page.evaluate("() => history.replaceState(null, '', '#')")
    page.locator('#away').tap()                                     # a tap elsewhere lets the card go
    assert page.evaluate("() => document.querySelector('.gs-tip').hidden") and not errors
    ctx.close()


# ---- 8. the change matrix's hover card -----------------------------------------------------------------------------

CARD_BOX_JS = """() => { const tip = document.querySelector('.dyn-tip.on'), r = tip.getBoundingClientRect();
  const pips = [...tip.querySelectorAll('.dt-counts .pip')], chip = tip.querySelector('.net-chip');
  return {w: r.width, right: r.right, chip: chip.getBoundingClientRect().top,
          last: pips[pips.length - 1].getBoundingClientRect().top, first: pips[0].getBoundingClientRect().top}; }"""


@pytest.mark.parametrize('width', [1440, 390])
def test_a_hover_card_is_wide_enough_and_its_net_chip_rides_with_the_counts(browser, monkeypatch, width):
    """Review 2026-10-17: a narrow card was 288px wide, so "Bullet Dance" and "Min Rounds Per Second" took two lines
    each, and the MIXED chip sat on a line of its own under a full line of counts. 360px at least (inside a phone's
    screen), the chip tied to the last count."""
    html = _feed(monkeypatch, {'heroes': 1}, FIVE_TAGS)
    ctx, page, errors = _open(browser, html, width=width)
    page.locator('a.lu').first.hover()
    got = page.evaluate(CARD_BOX_JS)
    assert got['w'] >= min(360, width - 16) - 0.5 and got['right'] <= width, got
    assert abs(got['chip'] - got['last']) < 6, got                 # the chip on the last count's line
    assert not errors
    ctx.close()
