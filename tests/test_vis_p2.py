"""Visual pass 2026-10-17, round 2, the "p2" track: the home page, patch pages, the indexes, unit art and the site bar.
Builders' output and the committed icons; site/styles.css + site/scripts.js on the builders' own markup in a real
browser (the `browser` fixture of tests/conftest.py)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))


def _json(rel: str):
    return json.loads((ROOT / rel).read_text(encoding='utf-8'))


def _open(browser, body: str, width: int = 1440, height: int = 900, touch: bool = False, main: str = 'page'):
    """A page of `body` with the site's CSS and JS inline; `touch`: a phone (is_mobile, has_touch)."""
    css = (ROOT / 'site' / 'styles.css').read_text(encoding='utf-8')
    js = (ROOT / 'site' / 'scripts.js').read_text(encoding='utf-8')
    opts = {'viewport': {'width': width, 'height': height}}
    if touch:
        opts.update(is_mobile=True, has_touch=True)
    ctx = browser.new_context(**opts)
    page = ctx.new_page()
    errors: list[str] = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.set_content(f'<!doctype html><html><head><meta charset="utf-8">'
                     f'<meta name="viewport" content="width=device-width, initial-scale=1"><style>{css}</style></head>'
                     f'<body><main class="{main}">{body}</main><script>{js}</script></body></html>')
    return ctx, page, errors


# ---- 1. unit art: every unit type told apart, flat marks inset on their tile ---------------------------------------

def test_unit_types_that_share_a_portrait_carry_their_role_mark():
    """Review 2026-10-17: Medic, Melee and plain Troopers (and the zipline trooper) were one red picture — four alike in
    a row on the home page — and Guardian and Base Guardian another. The game has one portrait for each class, so a
    type that shares it carries its role mark from the game files (extract_icons.marked_art)."""
    import extract_icons
    man = _json('icons/manifest.json')
    troopers = [man[f'unit:{u}'] for u in ('trooper_normal', 'trooper_medic', 'trooper_melee', 'trooper_zipline_container')]
    guardians = [man['unit:npc_boss_tier1'], man['unit:npc_barrack_boss']]
    assert len(set(troopers)) == 4 and len(set(guardians)) == 2
    # the namesakes (the other team's, the removed super troopers) carry the same mark as their type
    assert man['unit:alt_trooper_medic'] == man['unit:super_trooper_medic'] == man['unit:trooper_medic']
    assert man['unit:npc_barrack_boss_amber'] == man['unit:npc_barrack_boss']
    rules = _json('data/overrides/unit_icons.json')['rules']
    marks = [r[2] for r in rules if len(r) > 2]
    assert {'builds/citadel_build_tag_healing.svg', 'builds/citadel_build_tag_melee.svg',
            'hud/world_space/hero_info_panel_ultready_boss_barracks_psd.png'} <= set(marks)
    for rel in marks:            # every mark is a file the extractor pulls from the game's VPK
        assert any(f'panorama/images/{rel}'.startswith(p) for p in extract_icons.PREFIXES), rel
    for path in troopers + guardians:
        svg = (ROOT / 'icons' / path).read_text(encoding='utf-8')
        # the class portrait and the mark, both embedded (an <img> SVG loads nothing from outside); no colour of ours
        assert path.endswith('.svg') and svg.count('<image href="data:image/') == 2, path
        assert not re.search(r'#[0-9a-fA-F]{3,8}\b|rgba?\(|fill=|flood-color', svg), path


def test_named_units_on_the_index_never_share_a_picture():
    from builders.common import entity_icon
    from builders.unit_families import families, is_named
    ents = [e for e in _json('data/entities.json')['entities'] if e['file'] == 'npc_units.vdata' and not e.get('template')]
    seen: dict = {}
    for name, ms in families(ents).items():
        m = ms[0]
        if m.get('alive') and is_named(m) and m.get('kind') != 'helper':
            art = entity_icon(m['file'], m['id'], m.get('kind') or '', '')
            if art:
                seen.setdefault(art, []).append(name)
    assert not {a: ns for a, ns in seen.items() if len(ns) > 1}


def test_marked_svg_and_where_flat_marks_go():
    import extract_icons
    svg = extract_icons.marked_svg('data:image/webp;base64,AA', 'data:image/svg+xml;base64,BB', 128)
    assert svg.startswith('<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">')
    assert '<feMorphology in="SourceAlpha" operator="dilate" radius="3"/>' in svg          # a dark rim of its own alpha
    assert 'preserveAspectRatio="xMidYMid meet"' in svg and 'filter="url(#rim)"' in svg
    # small, on a dark disc in the top-right corner (owner 2026-10-21, question 7)
    assert '<circle cx="103.24" cy="24.76" r="21.76" opacity="0.75"/>' in svg and 'width="31" height="31"' in svg
    assert extract_icons.unit_art_dir('getting_started/map_rejuv_png.png') == 'units/_mark'
    assert extract_icons.unit_art_dir('hud/abilities/ratking/ratking_nibble_psd.png') == 'units/_mark'
    assert extract_icons.unit_art_dir('npcs/trooper_psd.png') == 'units/_class'
    assert extract_icons.unit_art_dir('heroes/engineer_turret_psd.png') == 'units/_class'
    man = _json('icons/manifest.json')
    assert man['unit:npc_super_neutral'] == 'units/_mark/map_rejuv.webp'
    assert man['unit:neutral_sinners_sacrifice'] == 'units/_mark/neutral_vault.webp'
    assert man['unit:npc_boss_tier2'] == 'units/_class/tier_2_boss.webp'


def test_a_flat_mark_sits_inside_its_unit_card_tile(browser):
    """Review 2026-10-17: the yellow Mid-Boss mark filled its tile edge to edge beside the painted portraits."""
    cards = ('<div class="grid units"><a class="card px-frame" id="p"><img class="px" src="icons/units/_class/t.webp">'
             '<span class="nm">Walker</span></a><a class="card px-frame" id="f"><img class="px" '
             'src="icons/units/_mark/m.webp"><span class="nm">Mid-Boss</span></a></div>')
    for width, touch, flat in ((1440, False, '13px'), (390, True, '10px')):
        ctx, page, errors = _open(browser, cards, width=width, touch=touch)
        pad = page.evaluate("() => ['#p img', '#f img'].map(s => getComputedStyle(document.querySelector(s)).paddingTop)")
        assert pad == ['5px', flat] and not errors
        ctx.close()


# ---- 2. "Not in patch notes" on the home page: the entity pages' chip ---------------------------------------------

def test_home_says_not_in_patch_notes_with_the_entity_chip(monkeypatch):
    from test_coverage import PAGES, _cat, _patch
    from builders import archive, home_page, patch_counts, shared_rows
    p = _patch()
    monkeypatch.setattr(shared_rows, 'catalog', lambda: _cat(2))
    c = patch_counts.count(p, PAGES)
    monkeypatch.setattr(patch_counts, 'for_id', lambda pid: {**c, 'hidden_shared': 5})
    monkeypatch.setattr(archive, 'patch', lambda pid: p)
    feed = home_page._feed([{'id': 'p1', 'title': p['title'], 'date': p['date']}], {}, frozenset(), {})
    # the banner: the chip history_view.hidden_link draws on an entity's head, then each clause after a " · "
    assert re.search(r'<a class="chip eye-link" href="patches/p1.html#hidden"><span class="mark hidden"[^>]*></span>'
                     r'3 not in patch notes</a>', feed)
    assert ('<span class="au-more"><span class="au-dot" aria-hidden="true">·</span><a class="au au-off" '
            'href="game/changes.html"><b>1</b> of them in game rules &amp; map objects</a></span>') in feed
    assert '<span class="au-dot" aria-hidden="true">·</span><span class="au au-shr"><b>5</b>' in feed
    # a group all out of the notes: the eye alone on its label, the words in its tooltip (owner 2026-10-21, q3)
    assert ('<span class="lu-all" data-tooltip="All not in patch notes"><span class="mark hidden"></span></span>'
            in feed)


def test_home_banner_chip_looks_like_the_entity_chip(browser):
    head = '<a class="chip eye-link" id="e" href="#hidden"><span class="mark hidden"></span>2 not in patch notes</a>'
    banner = ('<section class="update px-frame"><div class="banner"><span class="bt"><a href="#">Minor Update</a></span>'
              '<span class="bc"><a class="chip eye-link" id="h" href="#"><span class="mark hidden"></span>46 not in '
              'patch notes</a><span class="au-more"><span class="au-dot" aria-hidden="true">·</span>'
              '<a class="au au-off" id="o" href="#"><b>2</b> of them in game rules</a></span></span></div>'
              '<div class="lu-groups"><div class="lu-group"><span class="lu-h" id="g1">Heroes <b>5</b></span></div>'
              '</div></section>')
    ctx, page, errors = _open(browser, head + banner)
    look = """s => { const c = getComputedStyle(document.querySelector(s));
                     return [c.fontFamily, c.fontSize, c.textTransform, c.color, c.backgroundColor, c.boxShadow]; }"""
    assert page.evaluate(look, '#h') == page.evaluate(look, '#e')
    # the explaining clause is quiet sans, not 13px pixel caps run into the chip
    other = page.evaluate("() => { const c = getComputedStyle(document.querySelector('#o')); "
                          "return [c.textTransform, c.fontSize]; }")
    assert other == ['none', '13px']
    assert not errors
    ctx.close()


# ---- 3./4. patch page rows: no "?" gutter, a phone row uses the width ----------------------------------------------

def test_a_notes_line_nothing_was_found_for_carries_no_mark():
    """Review 2026-10-17: the grey "?" on most "Additional update notes" rows read as a broken icon; the summary keeps
    their count ("13 lines not found in the files")."""
    from builders.cards import row
    html = row('unmatched', '', 'Improved anti-cheat')
    assert '<span class="st"></span>' in html and 'mark' not in html
    assert 'class="mark described"' in row('described', '', 'x')


def test_a_value_that_appeared_reads_like_a_new_row():
    """'Corrupt Item Round — → 0' paired a dash with an arrow on City Never Sleeps' page."""
    from builders.notes_view import _files_cell
    add = {'op': 'add', 'old_s': '—', 'new_s': '0', 'label': 'Corrupt Item Round', 'cat': 'balance',
           'path': 'm_iCorruptItemRound'}
    cell = _files_cell({'status': 'described', 'changes': ['k']}, [add], None)
    assert cell == '<span class="proof">Corrupt Item Round <span class="v">0</span></span>'
    pair = {**add, 'op': 'change', 'old_s': '4', 'new_s': '5'}
    assert '<span class="v">4</span><span class="arrow">→</span><span class="v">5</span>' in \
        _files_cell({'status': 'described', 'changes': ['k']}, [pair], None)


def test_a_phone_patch_row_runs_its_tag_into_the_text(browser):
    """Review 2026-10-17: on a phone the badge and the "?" gutter took ~45% of a row; each line wrapped 3-4 times."""
    from builders.cards import row
    from builders.render import tag_badge
    text = 'Repeat light melees while airborne now have diminishing forward momentum and more words to wrap'
    rows = (row('documented', tag_badge('nerf', 'NERF'), text, extra='r1')
            + row('unmatched', '', text, extra='r2'))
    body = f'<article class="ecard"><div class="eb">{rows}</div></article>'
    ctx, page, errors = _open(browser, body, width=390, height=844, touch=True, main='page column')
    got = page.evaluate("""() => ['.r1', '.r2'].map(s => {
        const r = document.querySelector(s), R = r.getBoundingClientRect();
        const t = document.createRange(); t.selectNodeContents(r.querySelector('.tx'));
        const lines = [...t.getClientRects()];
        return {rowL: R.left, rowW: R.width, first: lines[0].left, last: lines[lines.length - 1].left,
                n: new Set(lines.map(l => Math.round(l.top))).size};
    })""")
    tagged, plain = got
    # the plain row's text starts at the row's edge (no gutter); a tagged row's second line too, under its tag
    assert plain['first'] - plain['rowL'] < 16 and tagged['last'] - tagged['rowL'] < 16, got
    assert tagged['first'] > tagged['last'] + 40                  # the first line starts after the tag
    assert tagged['n'] <= 3 and plain['n'] <= 3, got
    assert not errors
    ctx.close()


# ---- 5. home page on a phone ---------------------------------------------------------------------------------------

def test_home_on_a_phone_tiles_two_a_row_and_counts_at_the_left(browser):
    from builders.home_page import _tiles
    tiles = _tiles({'heroes': 43, 'items': 156, 'units': 22, 'game': 12}, ['a.webp'] * 6, ['u.webp'] * 6,
                   ['i.webp'] * 6, {'heroes': '+1 pre-release'})
    banner = ('<section class="update px-frame"><div class="banner"><span class="bt"><a href="#">Minor Update</a>'
              '</span><span class="bc"><a class="chip eye-link" id="c" href="#">46 not in patch notes</a></span></div>'
              '</section>')
    ctx, page, errors = _open(browser, tiles + banner, width=390, height=844, touch=True)
    boxes = page.evaluate("() => [...document.querySelectorAll('.htile')].map(t => { const r = t.getBoundingClientRect(); "
                          "return [Math.round(r.left), Math.round(r.top), Math.round(r.height)]; })")
    assert boxes[0][1] == boxes[1][1] and boxes[2][1] == boxes[3][1] and boxes[2][1] > boxes[0][1], boxes
    assert boxes[0][0] < boxes[1][0] and max(h for *_, h in boxes) < 160, boxes
    assert page.evaluate("() => document.documentElement.scrollWidth <= innerWidth")
    # the banner's count starts at the left under the title
    left = page.evaluate("() => [document.querySelector('.update .banner .bt').getBoundingClientRect().left, "
                         "document.querySelector('#c').getBoundingClientRect().left]")
    assert abs(left[0] - left[1]) < 2, left
    assert not errors
    ctx.close()


# ---- 6. one icon per Game system everywhere ------------------------------------------------------------------------

def test_a_game_system_icon_is_whole_in_the_change_matrix(browser):
    """Review 2026-10-17: Souls & economy's tall coil (35x67) was cropped to a swirl on the Game change matrix."""
    souls = (ROOT / 'icons' / 'stats' / 'prop' / 'souls.svg').as_uri()
    body = (f'<table class="dyn" id="dyn-game" data-what><tbody><tr><td class="name"><a href="#"><img src="{souls}" '
            f'alt="">Souls &amp; economy</a></td></tr></tbody></table><div class="dyn-tip"><div class="dt-head">'
            f'<img src="{souls}" alt=""></div></div>')
    ctx, page, errors = _open(browser, body)
    fit = page.evaluate("() => ['td.name img', '.dt-head img'].map(s => getComputedStyle(document.querySelector(s)).objectFit)")
    assert fit == ['contain', 'contain'] and not errors
    ctx.close()


def test_every_place_takes_a_game_system_icon_from_one_map():
    from builders.game_systems import icon_url, shown
    from builders.home_page import _chip
    for s in shown():
        url = icon_url(s, '')
        if url:
            assert url in _chip(f'game:{s.id}', {'n': 1, 'hidden': 0, 'rows': []}, 'p', {}, 0), s.id


# ---- 7. the site bar's build -------------------------------------------------------------------------------------

def test_every_page_names_the_newest_build_from_one_source():
    """Review 2026-10-17: only the home page and the stats tables showed a build, and they differed (6793 / 6790)."""
    from builders.common import latest_build, page
    newest = [r for r in _json('data/builds/index.json') if r.get('build') is not None][-1]
    assert latest_build()['build'] == newest['build']
    for html in (page('A', '', '../', 'units', build=newest['build'] - 3), page('B', '', '', '')):
        assert len(re.findall(r'class="nav-build"', html)) == 1
        assert f'>game build {newest["build"]}</a>' in html
    assert 'href="../builds/' in page('A', '', '../', 'units')


# ---- 8. patch page tabs and steps ----------------------------------------------------------------------------------

def test_patch_tabs_are_one_height_with_their_words_on_one_line(browser):
    tabs = ('<div class="tabs toolbar"><button class="px-btn on" id="a">Patch notes<span class="count">27</span></button>'
            '<button class="px-btn" id="b"><span class="mark hidden" data-tooltip="x"></span>Not in patch notes'
            '<span class="count">46</span></button></div>')
    ctx, page, errors = _open(browser, tabs)
    got = page.evaluate("""() => ['#a', '#b'].map(s => { const b = document.querySelector(s), r = document.createRange();
        r.selectNode([...b.childNodes].find(n => n.nodeType === 3));
        return [b.getBoundingClientRect().height, r.getBoundingClientRect().top]; })""")
    assert got[0] == got[1], got
    assert not errors
    ctx.close()


def test_the_newest_patch_names_both_steps():
    from builders import archive
    from builders.patches_pages import patch_page
    rows = archive.index()
    html = patch_page(archive.patch(rows[-1]['id']), rows[-2], None)
    steps = re.search(r'<span class="steps">(.*?)</span></div>', html).group(1)
    assert '◀ Older</a>' in steps and '<span class="step off" aria-disabled="true">Newer ▶</span>' in steps


# ---- 9. the changelog reads as a column ----------------------------------------------------------------------------

def test_the_changelog_lines_stay_readable(browser):
    from builders.home_page import changelog_page
    html = changelog_page()
    assert '<main class="page changelog">' in html
    body = ('<section class="section px-frame"><h3 class="section-title">A title<span class="dimmer">2026-10-17</span>'
            '</h3><ul class="change-list"><li><span class="lbl" id="l">' + 'word ' * 120 + '</span></li></ul></section>')
    ctx, page, errors = _open(browser, body, width=1440, main='page changelog')
    width = page.evaluate("() => document.querySelector('#l').getBoundingClientRect().width")
    assert width < 760, width                                      # ~80 characters, not ~1370px
    assert not errors
    ctx.close()
