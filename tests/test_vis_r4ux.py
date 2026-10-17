"""Round 4 of the visual pass (2026-10-17), the "hidden changes" track: the change matrices' "Not in patch notes" filter
and the legend of the tiles' orange top, every matrix filter in the address, the home counter's way to them, anchored
targets that land below the sticky bars, one wording for "not in patch notes" / "no patch notes", and the month under
the first tile of each month of an entity's patch strip. Builders are checked on their markup; site/styles.css and
site/scripts.js in Chromium (`browser`: conftest.py) on the builders' own pages."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PHONE = {'width': 390, 'height': 844}


def _open(browser, tmp_path: Path, html: str, width: int = 1440, height: int = 900, phone: bool = False,
          hash_: str = ''):
    """`html` as tmp_path/x/page.html with the site's CSS and JS one level up (rel '../'), opened at `hash_`, offline."""
    shutil.copy(ROOT / 'site' / 'styles.css', tmp_path / 'styles.css')
    shutil.copy(ROOT / 'site' / 'scripts.js', tmp_path / 'scripts.js')
    (tmp_path / 'x').mkdir(exist_ok=True)
    f = tmp_path / 'x' / 'page.html'
    f.write_text(html, encoding='utf-8')
    opts = {'viewport': {'width': width, 'height': height}}
    if phone:
        opts.update(is_mobile=True, has_touch=True, device_scale_factor=2)
    ctx = browser.new_context(**opts)
    pg = ctx.new_page()
    pg.route('**/*', lambda r: r.continue_() if r.request.url.startswith('file:') else r.abort())
    errors: list[str] = []
    pg.on('pageerror', lambda e: errors.append(str(e)))
    pg.goto(f.as_uri() + hash_)
    pg.wait_for_timeout(150)
    return ctx, pg, errors


# ---- 1. the matrices: "Not in patch notes" and the orange top's legend -------------------------------------------

ROWS = [{'id': 'p1', 'date': '2026-01-01', 'title': '01-01-2026 Update'},
        {'id': 'p2', 'date': '2026-03-01', 'title': '03-01-2026 Update'},
        {'id': 'p3', 'date': '2026-05-01', 'title': '05-01-2026 Update'}]


def _s(what, field, tag, part, hid):
    return [what, field, '1', '2', tag, part, hid]


def _matrix(monkeypatch) -> str:
    """Three heroes: A has a cell partly out of the notes (p1) and one all out (p2), B one cell all in the notes, C
    nothing in the notes anywhere."""
    from builders import dynamics_page
    from builders.common import page
    d = {'rows': ROWS,
         'cells': {'hero:a': {'p1': {'buff': 3, 'nerf': 2}, 'p2': {'new': 2}}, 'hero:b': {'p3': {'buff': 1}}},
         'parts': {'hero:a': {'p1': {'stats': {'buff': 3}, 'abil': {'nerf': 2}}, 'p2': {'abil': {'new': 2}}},
                   'hero:b': {'p3': {'stats': {'buff': 1}}}},
         'samples': {'hero:a': {'p1': [_s('Base stats', 'Health', 'buff', 'stats', 0),
                                       _s('Bolt', 'Range', 'nerf', 'abil', 1)],
                                'p2': [_s('Bolt', 'New A', 'new', 'abil', 1), _s('Bolt', 'New B', 'new', 'abil', 1)]},
                     'hero:b': {'p3': [_s('Base stats', 'Speed', 'buff', 'stats', 0)]}},
         'hidden': {'hero:a': {'p1': 2, 'p2': 2}},
         'nets': {'hero:a': {'p1': 'buff', 'p2': 'buff'}, 'hero:b': {'p3': 'buff'}},
         'hcells': {'hero:a': {'p1': {'nerf': 1, 'buff': 1}, 'p2': {'new': 2}}},
         'hparts': {'hero:a': {'p1': {'abil': {'nerf': 1}, 'stats': {'buff': 1}}, 'p2': {'abil': {'new': 2}}}},
         'hsamples': {'hero:a': {'p1': [_s('Base stats', 'Armor', 'buff', 'stats', 1), _s('Bolt', 'Range', 'nerf', 'abil', 1)],
                                 'p2': [_s('Bolt', 'New A', 'new', 'abil', 1), _s('Bolt', 'New B', 'new', 'abil', 1)]}}}
    monkeypatch.setattr(dynamics_page, '_collect', lambda: d)
    entries = [('hero:a', 'Alpha', None, 'a.html', ''), ('hero:b', 'Beta', None, 'b.html', '')]
    body = '<h1>Hero changes</h1>' + dynamics_page.toolbar('hero', 0, '') + dynamics_page.matrix_html(entries, 'hero')
    return page('Hero changes', body, '../', 'heroes', wide=True)


def _cells(html: str) -> list:
    blob = re.search(r'class="dyn-data"[^>]*>(.*?)</script>', html, re.S).group(1)
    return json.loads(blob.replace('<\\/', '</'))['cells']


def test_a_cell_carries_its_rows_not_in_the_notes_only_where_they_differ(monkeypatch):
    """The filter needs a cell's hidden rows by tag and part (and their biggest changes): written only for a cell partly
    out of the notes — one all out reads its own counts, one all in has none (2026 hero cells are mostly all out)."""
    html = _matrix(monkeypatch)
    a1, a2, b3 = _cells(html)
    assert a1[4] == 2 and a1[6] == {'nerf': 1, 'buff': 1} and a1[7] == {'abil': {'nerf': 1}, 'stats': {'buff': 1}}
    assert a1[8][0][1] == 'Armor'               # its own biggest hidden one, not in the cell's samples
    assert len(a2) == 6 and len(b3) == 6 and b3[4] == 0
    # a row with nothing out of the notes is a fact for the filter (`nh`; `nhn`: none in the columns shown at first)
    assert re.search(r'<tr class="nh nhn"[^>]*data-name="Beta"', html)
    assert re.search(r'<tr class=""[^>]*data-name="Alpha"', html)


def test_the_hidden_samples_are_the_biggest_of_the_rows_out_of_the_notes():
    from builders.dynamics_page import _by_part, _pick, _ranked
    raw = [('Bolt', 'A', '1', '2', 'buff', 'abil', 50, 0), ('Bolt', 'B', '1', '2', 'nerf', 'abil', 30, 1),
           ('Base stats', 'C', '1', '2', 'buff', 'stats', 10, 1), ('Bolt', 'D', '1', '2', 'buff', 'abil', 5, 1)]
    hid = _by_part(_pick([x for x in _ranked(raw) if x[7]], 1))
    assert [x[1] for x in hid] == ['C', 'B'] and all(x[6] for x in hid)          # stats first, then abilities


def test_every_cell_of_the_real_matrices_splits_its_hidden_count_by_tag_and_part():
    from builders import dynamics_page
    d = dynamics_page._collect()
    for key, per in d['hidden'].items():
        for pid, n in per.items():
            assert sum(d['hcells'][key][pid].values()) == n, (key, pid)
            if key.startswith('hero:'):
                assert sum(v for p in d['hparts'][key][pid].values() for v in p.values()) == n, (key, pid)
            assert d['hsamples'][key][pid] and all(s[6] for s in d['hsamples'][key][pid])


def test_the_bar_has_the_filter_and_says_what_the_orange_top_means():
    from builders import dynamics_page
    for kind in ('hero', 'item', 'unit', 'game'):
        bar = dynamics_page.toolbar(kind, 0, '')
        assert f'<button class="px-btn dyn-hid" data-target="#dyn-{kind}" aria-pressed="false">' in bar
        assert 'Not in patch notes</button>' in bar and 'some changes not in patch notes' in bar
        assert bar.index('dyn-hid') < bar.index('show-old')             # the first filter after the search


def _tiles(pg) -> dict:
    return pg.evaluate("""() => Object.fromEntries([...document.querySelectorAll('table.dyn a.dsq')].map(a =>
      [a.closest('tr').dataset.name + ':' + a.getAttribute('href').split('#p-')[1],
       [a.className, a.querySelector('.dn').textContent, getComputedStyle(a).visibility]]))""")


def test_not_in_patch_notes_redraws_every_tile_from_those_rows(browser, tmp_path, monkeypatch):
    ctx, pg, errors = _open(browser, tmp_path, _matrix(monkeypatch))
    try:
        before = _tiles(pg)
        assert before['Alpha:p1'][1] == '5' and ' hid' in before['Alpha:p1'][0] and ' hid' not in before['Beta:p3'][0]
        pg.click('.dyn-hid')
        got = _tiles(pg)
        assert got['Alpha:p1'][1] == '2' and ' hid' in got['Alpha:p1'][0]          # its 2 rows out of the notes
        assert got['Alpha:p2'][1] == '2'
        assert pg.evaluate("getComputedStyle(document.querySelector('tr[data-name=Beta]')).display") == 'none'
        assert pg.get_attribute('.dyn-hid', 'aria-pressed') == 'true' and 'on' in pg.get_attribute('.dyn-hid', 'class')
        # with a part chosen: that part's rows out of the notes (Alpha p1: one nerf in its abilities)
        pg.click('.dyn-parts [data-part="abil"]')
        assert _tiles(pg)['Alpha:p1'][1] == '1'
        pg.click('.dyn-parts [data-part="all"]')
        # the card says what the tile shows: those rows, their count, their biggest change
        pg.hover('tr[data-name=Alpha] a.dsq[href$="p1"]')
        card = pg.inner_text('.dyn-tip')
        assert '2 not in patch notes' in card and 'Armor' in card and 'Health' not in card
        pg.mouse.move(5, 5)
        pg.click('.dyn-hid')
        # back as built (a redrawn one-tag tile wears the inline gradient for its `s-<tag>` class, as after any filter)
        def plain(t):
            return {k: [re.sub(r' s-\w+', '', v[0]), *v[1:]] for k, v in t.items()}
        assert plain(_tiles(pg)) == plain(before)
        assert not errors
    finally:
        ctx.close()


def test_a_tag_filter_keeps_the_orange_top_only_on_tiles_that_show_a_row_out_of_the_notes(browser, tmp_path,
                                                                                            monkeypatch):
    ctx, pg, errors = _open(browser, tmp_path, _matrix(monkeypatch))
    try:
        pg.click('.dyn-tags [data-dyn-tag="buff"]')
        got = _tiles(pg)
        assert ' hid' in got['Alpha:p1'][0] and got['Alpha:p1'][1] == '3'          # one of its 3 buffs is out
        assert got['Alpha:p2'][2] == 'hidden' and ' hid' not in got['Beta:p3'][0]
        assert not errors
    finally:
        ctx.close()


# ---- 2. the filters in the address; the home counter's way in ----------------------------------------------------

def test_a_matrix_opens_filtered_from_its_address_and_writes_every_filter_back(browser, tmp_path, monkeypatch):
    ctx, pg, errors = _open(browser, tmp_path, _matrix(monkeypatch), hash_='#hidden&tags=new&part=abil&old')
    try:
        assert pg.get_attribute('.dyn-hid', 'aria-pressed') == 'true'
        assert pg.get_attribute('.dyn-tags [data-dyn-tag="new"]', 'aria-pressed') == 'true'
        assert pg.get_attribute('.dyn-parts [data-part="abil"]', 'aria-pressed') == 'true'
        assert pg.evaluate("document.querySelector('table.dyn').className.split(' ').sort().join(' ')") == \
            'dyn only-hid show-old'
        assert pg.inner_text('.tb-fold .tb-n') == '(4 active)'
        pg.click('.dyn-hid')
        pg.fill('.dyn-bar input[type=search]', 'alp')
        pg.wait_for_function("location.hash.indexOf('q=alp') >= 0")
        assert pg.evaluate('location.hash') == '#old&part=abil&tags=new&q=alp'
        pg.click('.dyn-tags [data-dyn-tag="new"]')
        pg.click('.dyn-parts [data-part="all"]')
        pg.locator('.dyn-bar input[data-toggle-class="show-old"]').evaluate('i => i.click()')
        pg.fill('.dyn-bar input[type=search]', '')
        pg.wait_for_function("location.hash === ''")
        assert not errors
    finally:
        ctx.close()


def test_the_home_counter_opens_the_matrices_with_the_filter_on():
    from builders import home_page
    top = home_page._top(14829, 5598)
    assert '<a class="hs-go" href="heroes/changes.html#hidden"><span class="n">5598</span>' in top
    for sec in ('heroes', 'items', 'units', 'game'):
        assert f'<a href="{sec}/changes.html#hidden">{sec}</a>' in top
    assert 'patches/index.html' not in top


# ---- 3. anchored targets land below the sticky bars ---------------------------------------------------------------

@pytest.fixture(scope='module')
def no_notes_page() -> str:
    from builders import patches_pages
    from builders.common import load_json
    return patches_pages.patch_page(load_json('patches/build-6790.json.gz'), None, None)


@pytest.mark.parametrize('phone', [False, True])
def test_the_home_chip_lands_the_first_card_whole_below_the_bars(browser, tmp_path, no_notes_page, phone):
    """Review 2026-10-17: build 6790's "#hidden" landed with Deadman Danny's card head under the filter bar, "Close The
    Deal" without its hero."""
    size = PHONE if phone else {'width': 1440, 'height': 900}
    ctx, pg, errors = _open(browser, tmp_path, no_notes_page, phone=phone, hash_='#hidden', **size)
    try:
        got = pg.evaluate("""() => {
          const bars = [...document.querySelectorAll('.top-nav, .toolbar')].filter(b => b.getClientRects().length &&
            ['sticky', 'fixed'].includes(getComputedStyle(b).position));
          const under = Math.max(...bars.map(b => b.getBoundingClientRect().bottom));
          const card = [...document.querySelectorAll('#changes .ecard')].find(c => c.offsetParent !== null);
          return {under: under, card: card.getBoundingClientRect().top, y: scrollY}; }""")
        assert got['y'] > 0 and got['card'] >= got['under'] - 1, got
        assert not errors
    finally:
        ctx.close()


@pytest.mark.parametrize('phone', [False, True])
def test_a_card_named_in_the_address_lands_below_the_stuck_bar(browser, tmp_path, no_notes_page, phone):
    """A patch page's card (#c-…, a shared edit's anchor too) clears the site bar and the toolbar stuck under it,
    however tall it wraps (it was 72px whatever the bar)."""
    target = re.findall(r'<article class="ecard[^"]*" id="(c-[^"]+)"', no_notes_page)[2]
    size = PHONE if phone else {'width': 1440, 'height': 900}
    ctx, pg, errors = _open(browser, tmp_path, no_notes_page, phone=phone, hash_=f'#{target}', **size)
    try:
        got = pg.evaluate(f"""() => {{
          const bars = [...document.querySelectorAll('.top-nav, .toolbar')].filter(b => b.getClientRects().length &&
            ['sticky', 'fixed'].includes(getComputedStyle(b).position));
          const under = Math.max(...bars.map(b => b.getBoundingClientRect().bottom));
          return {{under: under, card: document.getElementById({target!r}).getBoundingClientRect().top}}; }}""")
        assert got['under'] - 1 <= got['card'] <= got['under'] + 40, got
        assert not errors
    finally:
        ctx.close()


# ---- 4. one wording ------------------------------------------------------------------------------------------------

GONE = ('no official notes', 'lines not found in the files', 'not in notes', 'changes · no notes', "'From the files'",
        'What the notes left out', "'heroes in development'")


def test_one_term_for_each_idea_in_the_builders_and_the_script():
    """Review 2026-10-17: ~10 phrasings for two ideas. "not in patch notes" (the eye), "no patch notes" (an update with
    none at all). The eye's own evidence words (builders/evidence.py) are another track's."""
    for f in [*sorted((ROOT / 'builders').glob('*.py')), ROOT / 'site' / 'scripts.js']:
        if f.name == 'evidence.py':
            continue
        code = '\n'.join(ln for ln in f.read_text(encoding='utf-8').splitlines()
                         if not ln.lstrip().startswith(('#', '//', '*', '/*')))
        for phrase in GONE:
            assert phrase not in code.replace('"""', ''), (f.name, phrase)


def test_counts_are_plural_only_when_more_than_one(monkeypatch):
    from builders import patch_counts, patches_pages
    monkeypatch.setattr(patches_pages, 'hero_names', lambda: {})
    row = {'id': 'p1', 'title': 'Update', 'date': '2026-10-06', 'builds': 2, 'has_notes': False, 'line_counts': {}}
    for n, words in ((1, '<b>1</b> change · no patch notes'), (21, '<b>21</b> changes · no patch notes')):
        monkeypatch.setattr(patch_counts, 'for_id', lambda pid, n=n: {'changes': n, 'unannounced': 0})
        assert words in patches_pages._index_row(row, {}, '../', False)
    monkeypatch.setattr('builders.patch_counts.for_id', lambda pid: {'unannounced': 1, 'not_in_notes': 1})
    monkeypatch.setattr('builders.patch_counts.off_pages', lambda c: 0)
    line = patches_pages._audit_line({'id': 'p1', 'sections': [], 'line_counts': {'fix': 1, 'mismatch': 1}})
    assert '1</b> change · no patch notes' in line
    line = patches_pages._audit_line({'id': 'p1', 'sections': [{}], 'line_counts': {'fix': 1, 'mismatch': 1}})
    assert '1</b> bug fix<' in line and '1</b> note disagrees with the files' in line


def test_the_home_chip_of_an_update_without_notes_says_how_many_changes(monkeypatch):
    from builders import home_page
    monkeypatch.setattr(home_page, 'update_feed', lambda *a, **k: {'heroes': {}})
    monkeypatch.setattr(home_page.archive, 'patch', lambda pid: {})
    monkeypatch.setattr('builders.patch_counts.for_id', lambda pid: {'not_in_notes': 12, 'changes': 38})
    monkeypatch.setattr('builders.patch_counts.off_pages', lambda c: 0)
    feed = home_page._feed([{'id': 'p1', 'title': 'Paint the Town', 'date': '2026-10-16', 'has_notes': False}], {},
                           frozenset(), {})
    assert '12 changes · no patch notes</a>' in feed


def test_a_band_of_an_update_without_notes_keeps_saying_so_under_a_filter(browser, tmp_path):
    """Review 2026-10-17: the band read "NO PATCH NOTES", then "ALL 2 NOT IN NOTES" with the eye pressed."""
    row = ('<div class="erow is-hidden"><span class="tg"><span class="tag buff">BUFF</span></span>'
           '<span class="lbl">Range</span></div>')
    band = ('<details class="pblock has-hidden all-hidden" id="p-{pid}" open><summary class="banner"><span class="bt">x'
            '</span><span class="bc"><span class="tsum"><span class="pip buff">2</span></span><span class="chip eye-chip">'
            '<span class="ec-n">{text}</span></span></span></summary><div class="hgroup" data-area="abil">'
            '<div class="hg-b">' + row * 2 + '</div></div></details>')
    body = ('<div class="toolbar hist-bar"><button class="px-btn hf-hidden" data-toggle-class="only-hidden" '
            'data-target="#history" aria-pressed="false">Not in patch notes</button></div><div id="history" '
            'class="hblocks">' + band.format(pid='p1', text='no patch notes')
            + band.format(pid='p2', text='all 2 not in patch notes') + '</div>')
    from builders.common import page
    ctx, pg, errors = _open(browser, tmp_path, page('X', body, '../'))
    try:
        pg.click('.hf-hidden')
        pg.wait_for_function("document.getElementById('history').classList.contains('filtering')")
        got = pg.evaluate("[...document.querySelectorAll('.ec-n')].map(e => e.textContent)")
        assert got == ['no patch notes', 'all 2 not in patch notes'] and not errors
    finally:
        ctx.close()


# ---- 5. the patch strip: the month under its first tile, the orange top in words ----------------------------------

def test_a_month_label_under_the_first_tile_of_each_month_and_the_year_where_it_changes():
    from builders.history_view import month_cues
    dates = ['2025-11-03', '2025-11-20', '2025-12-01', '2026-01-09', '2026-01-20', '2026-02-02', '2026-02-10',
             '2026-04-01', '2026-05-01']
    # Dec has its place, then gives it to the year one tile on; May is one tile from Apr and gives way
    assert month_cues(dates) == ['Nov', '', '', '2026', '', 'Feb', '', 'Apr', '']
    assert month_cues([]) == [] and month_cues(['2026-01-01']) == ['Jan']


def _strip_page(n: int, hidden: bool = True) -> str:
    from builders.common import page
    from builders.history_view import patch_strip
    items = [(f'p{i}', {'id': f'p{i}', 'date': f'{2024 + i // 12}-{i % 12 + 1:02d}-05', 'title': 'Update'},
              {'buff': 2}, int(hidden and i % 3 == 0), [], 'buff') for i in range(n)][::-1]       # newest first
    return page('X', f'<div class="head-strip"><span class="hs-l">Patches</span>{patch_strip(items)}</div>', '../')


@pytest.mark.parametrize('phone', [False, True])
def test_the_strip_labels_stay_inside_it_never_overlap_and_the_legend_sits_under_it(browser, tmp_path, phone):
    size = PHONE if phone else {'width': 1440, 'height': 900}
    ctx, pg, errors = _open(browser, tmp_path, _strip_page(40), phone=phone, **size)
    try:
        got = pg.evaluate("""() => {
          const strip = document.querySelector('.patch-strip').getBoundingClientRect();
          const labs = [...document.querySelectorAll('.ps-tile[data-m]')].filter(t => t.offsetParent !== null).map(t => {
            const r = t.getBoundingClientRect(), s = getComputedStyle(t, '::after');
            const w = parseFloat(s.width), top = r.bottom + parseFloat(s.marginTop);
            return {l: r.left + r.width / 2 - w / 2, r: r.left + r.width / 2 + w / 2, b: top + parseFloat(s.height),
                    text: s.content}; });
          const key = document.querySelector('.hs-key').getBoundingClientRect();
          const label = document.querySelector('.hs-l').getBoundingClientRect();
          const tile = [...document.querySelectorAll('.ps-tile')].find(t => t.offsetParent !== null)
            .getBoundingClientRect();
          return {labs: labs, stripB: strip.bottom, stripL: strip.left, stripR: strip.right, keyT: key.top,
                  keyL: key.left, tileL: [...document.querySelectorAll('.ps-tile')].find(t => t.offsetParent !== null)
                    .getBoundingClientRect().left,
                  labelMid: (label.top + label.bottom) / 2, tileMid: (tile.top + tile.bottom) / 2}; }""")
        labs = got['labs']
        assert len(labs) >= 3 and all(lb['b'] <= got['stripB'] for lb in labs), got
        assert all(a['r'] < b['l'] for a, b in zip(labs, labs[1:])), labs             # no two labels touch
        # under the labels, from the tiles' left edge (a short strip's legend sat 600px off at the head's right end)
        assert got['keyT'] >= max(lb['b'] for lb in labs) and got['stripL'] <= got['keyL'] <= got['tileL'] + 1
        assert abs(got['labelMid'] - got['tileMid']) < 4                               # "Patches" level with the tiles
        assert pg.evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth')
        assert not errors
    finally:
        ctx.close()


def test_no_legend_under_a_strip_without_the_orange_top():
    assert 'hs-key' not in _strip_page(5, hidden=False) and 'hs-key' in _strip_page(5)
