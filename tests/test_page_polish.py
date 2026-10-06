"""The low items of the 2026-10-06 review: a neutral TEXT / NOTE badge, one width across a section's tabs, the home
tiles' counters, the change matrices' box height, sort hints on the stats tables, a rule for all's own number in a
strip tile's card, and one way to clear every builder's cache. (Empty tiles on the patch strip were tried and dropped:
the strip keeps the entity's latest 40 patches of its own, the owner's wording.)"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / 'site' / 'styles.css').read_text(encoding='utf-8')


def test_text_and_note_rows_carry_a_neutral_badge():
    """Their tag column was blank: a name / description change read like a row that had lost its tag."""
    from builders.history_view import history_table
    from builders.render import note_badge
    from builders.text_rows import text_rows
    assert note_badge('TEXT') == '<span class="tag note-tag">TEXT</span>'
    html = text_rows([{'part': 'name', 'old': 'Sleep Dagger', 'new': 'Dream Dagger'},
                      {'part': 'desc', 'old': 'Hits once.', 'new': 'Hits twice.'}])
    assert html.count('<span class="tg"><span class="tag note-tag">TEXT</span></span>') == 2
    r1 = {'id': 'p1', 'date': '2026-01-01', 'title': '01-01-2026 Update'}
    line = {'text': 'X: Sliding uphill feels smoother', 'status': 'code', 'changes': []}
    page = history_table([('abilities.vdata:x', 'X', None)], ['X'], {}, {'x': [(r1, line)]}, '../')
    assert 'class="erow st-code"><span class="st">' in page and '<span class="tag note-tag">NOTE</span>' in page
    assert '.tag.note-tag { --c: var(--text-dimmer); }' in CSS
    # no tag filter or counter takes it (scripts.js tagOf reads the filter tags only)
    js = (ROOT / 'site' / 'scripts.js').read_text(encoding='utf-8')
    assert "r.classList.contains('st-code') || r.classList.contains('st-text')" in js


def test_a_sections_tabs_share_one_width(monkeypatch):
    from builders import entities_pages
    from builders.game_pages import index_page
    from builders.game_rules import rules_page
    assert '<main class="page wide">' in index_page({}, {})
    html = rules_page([])
    assert '<main class="page wide">' in html
    # the title and the tabs where the other tabs have them; the table a centred column below
    assert re.search(r'<h1>Game rules</h1><div class="flex table-tabs">.*?</div><div class="rules-col">', html)
    written: dict[str, str] = {}
    monkeypatch.setattr(entities_pages, 'write', lambda path, text: written.__setitem__(path, text))
    ctx = {'rel': '../', 'units_t': {'units': [], 'columns': []}, 'by_id': {}, 'by_ent': {}, 'by_subject': {}}
    entities_pages._build_units(ctx, [])
    assert '<main class="page wide">' in written['units/index.html']        # as wide as Unit Stats and Unit changes


def test_the_heroes_tile_counts_what_its_index_shows():
    """The tile said 44 over an index of 39 heroes (5 pre-release behind its switch)."""
    from builders.home_page import _tiles, hero_tile
    states = ['release'] * 3 + ['prerelease'] * 2 + ['EHeroDevState_Release', 'EHeroDevState_PreRelease',
                                                     'EHeroDevState_InDevelopment', 'disabled', None]
    assert hero_tile([{'state': s} for s in states]) == (4, 3)              # a hero in development is on neither
    html = _tiles({'heroes': 39, 'units': 22}, [], [], [], {'heroes': '+5 pre-release'})
    assert '<span class="ht-n">39<span class=ht-x>+5 pre-release</span></span>' in html
    assert '<span class="ht-n">22</span>' in html


def test_sortable_headers_say_so_with_pixel_arrows():
    from builders.pixel_icons import SORT_ART, sort_mask
    for name, rows in SORT_ART.items():
        assert len(rows) == 10 and all(len(r) == 10 for r in rows), name
        assert f'--mask-{name}: {sort_mask(name)};' in CSS
    assert 'table.stats thead tr.cols th[aria-sort]::after' in CSS
    assert 'th[aria-sort="descending"]::after { --sort-ic: var(--mask-sort-down)' in CSS
    assert 'content: attr(data-arrow)' not in CSS                 # the font ▼ / ▲ is gone


def test_sort_hints_follow_the_sort_in_a_browser(browser):
    from test_perf_browser import _open, _stats
    page, errors = _open(browser, _stats({'Weapon': 2}))
    th = page.locator('table.stats thead tr.cols th[data-col="Weapon0"]')
    mask = "(el) => getComputedStyle(el, '::after').getPropertyValue('--sort-ic').trim()"
    assert th.evaluate(mask) == '' and th.evaluate("(el) => getComputedStyle(el, '::after').opacity") == '0.35'
    th.click()
    # the down arrow's art (pixel_icons.SORT_ART['sort-down']: its first run is the widest, at the top)
    assert th.get_attribute('aria-sort') == 'descending' and 'M1 3h8v1h-8z' in th.evaluate(mask)
    assert th.evaluate("(el) => getComputedStyle(el, '::after').opacity") == '1' and not errors


def test_the_matrix_box_ends_on_the_first_screen(browser):
    """At 1440x900 the box ran ~190px under the fold: its sideways scrollbar was two scrollbars away."""
    from test_perf_browser import _open
    rows = ''.join(f'<tr><td class="name">R{i}</td><td>{i}</td></tr>' for i in range(80))
    body = ('<div style="height: 260px"></div><div class="table-fade"><div class="table-scroll"><table class="dyn">'
            '<thead><tr class="cols"><th class="name">x</th><th class="dd">1</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div></div>')
    page, errors = _open(browser, body, width=1440, height=900)
    bottom = "() => document.querySelector('.table-scroll').getBoundingClientRect().bottom"
    assert 860 <= page.evaluate(bottom) <= 900 and not errors
    # a shorter window refits it (a height-only resize did nothing: the old height stuck)
    page.set_viewport_size({'width': 1440, 'height': 700})
    page.wait_for_timeout(100)
    assert 660 <= page.evaluate(bottom) <= 700
    phone, _ = _open(browser, body, width=390, height=800)
    assert phone.evaluate("() => document.querySelector('.table-scroll').style.maxHeight") == ''


def test_the_strip_keeps_the_entitys_latest_own_patches():
    """Owner's wording: the strip is the entity's latest 40 patches of its own — empty tiles for the patches that did
    not change it were tried (2026-10-06) and dropped: Haze showed ~27 of hers instead of 40."""
    from builders.history_view import STRIP_MAX, patch_strip
    hdr = {'id': 'x', 'date': '2026-01-01', 'title': '01-01-2026 Update'}
    many = [(f'q{i}', {**hdr, 'id': f'q{i}'}, {'buff': 1}, 0, [], '') for i in range(60)]
    html = patch_strip(many)
    assert html.count('data-k=') == STRIP_MAX == 40 and 'ps-tile gap' not in html and '.ps-tile.gap' not in CSS


def test_a_rule_for_all_has_its_own_number_in_a_tiles_card(browser):
    """A strip tile's counts leave out the rules for all (counted apart); their group in the card had no number."""
    from builders.history_view import patch_strip, tile_card
    from test_perf_browser import _open
    own = {'op': 'change', 'cat': 'balance', 'label': 'Radius', 'old_s': '3m', 'new_s': '4m', 'dir': 'buff', 'pct': 33.0,
           'status': 'documented', 'path': 'x'}
    rule = {**own, 'label': 'Level 20: souls needed', 'pct': 5.0, 'shared_all': True}
    hdr = [{'id': f'p{i}', 'date': f'2026-0{i}-01', 'title': f'0{i}-01-2026 Update'} for i in (1, 2)]
    card = tile_card([(('', '', 'x', 0, 0), [own]), (('All heroes', '', '', 0, 1), [rule, {**rule, 'label': 'L21'}])])
    items = [('p2', hdr[1], {'buff': 1}, 0, card, 'buff'), ('p1', hdr[0], {'buff': 1}, 0, card, '')]
    page, errors = _open(browser, patch_strip(items))
    page.hover('.ps-tile[data-k="0"]')
    tip = page.locator('.dyn-tip.on')
    assert tip.locator('.dt-grp .dt-every').text_content() == '2 changes'
    assert 'more' not in tip.inner_text() and not errors             # 1 own + 2 listed: nothing left to count


def test_one_call_forgets_every_builders_cache():
    """archive.clear() forgot the archive only: trail, patch_counts, stat_eyes, evidence kept the old data's answers."""
    import sys
    from builders import archive, caches, evidence, stat_eyes, trail  # noqa: F401  (loaded: their caches count)
    caches.clear_all()
    archive.index()
    evidence.build_anchors('nope.json.gz')
    assert archive.index.cache_info().currsize == 1 and evidence.build_anchors.cache_info().currsize == 1
    archive.clear()                                       # = caches.clear_all()
    cached = [(name, v) for name, mod in list(sys.modules.items()) if name.startswith('builders.') and mod
              for v in vars(mod).values() if hasattr(v, 'cache_info') and getattr(v, '__module__', None) == name]
    assert {n for n, _ in cached} >= {'builders.archive', 'builders.evidence', 'builders.trail', 'builders.stat_eyes'}
    assert all(v.cache_info().currsize == 0 for _, v in cached)
    assert caches.clear_all() == len(cached)
