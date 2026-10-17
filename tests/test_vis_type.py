"""Type pass of the 2026-10-17 visual review, round 3 (critic: one hero page mixed 31 family / size / weight
combinations — VT323 at 13-19px, IBM Plex at 10-17px in half steps, Jersey 20 at 20-32px; VT323 under 16px barely
legible: "SHARED ×17 ABILITIES & ITEMS", the patch strip's units, the Item Stats "Active" tags).

One type scale as `:root` tokens (`--fs-*`), each family on its own steps: the UI font 10-18px (+ one title date),
VT323 16 and 18px only, Jersey 20 from 20px, Jacquard 24 the wordmark. Every font size in styles.css is a step; the
builders and scripts write none. Checked on the stylesheet, on the site's components in a browser and, when there is a
dist/, on the built pages with the current stylesheet. `browser` is tests/conftest.py's."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / 'site' / 'styles.css').read_text(encoding='utf-8')

SCALE = {'2xs': 10, 'xs': 11, 'sm': 13, 'base': 14, 'md': 16, 'lg': 18, 'xl': 20, '2xl': 26, '3xl': 34, '4xl': 40,
         'brand': 28, 'brand-xl': 58}
UI_STEPS = {'2xs', 'xs', 'sm', 'base', 'md', 'lg', 'xl', '3xl'}   # xl: the back-to-top arrow; 3xl: a title date
LABEL_STEPS = {'md', 'lg'}                                         # VT323: never under 16px
PX_STEPS = {'xl', '2xl', '3xl', '4xl'}                             # Jersey 20: never under 20px
BRAND_STEPS = {'brand', 'brand-xl'}

# The only sizes that are not steps: the shop draws the game's own panel at the game's sizes in its design px
# (docs/shop.md: CostLabel, card names, the imbue strip, the tooltip's head in its stand-in fonts).
NOT_A_STEP = {
    '.gs-price': "the price on the painted tape: the game's CostLabel size per tier (game_shop.PRICE_SIZE), in design px",
    '.gc-nm': "a shop card's name: the game's 15 design px, shrunk to fit by scripts.js like the game's text-overflow",
    '.gc-imb': "the imbue strip on a card: the game's 12 design px",
    '.gt-name': "the item tooltip's name: the game's size in its stand-in font (Archivo Narrow)",
    '.gt-cost': "the item tooltip's price: the game's size in its stand-in font (Fredoka)",
}


def _rules(css: str):
    """(selector, body, inside :root) for every rule that holds declarations (media queries walked through)."""
    src = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    stack, start = [], 0
    for m in re.finditer(r'[{}]', src):
        if m.group() == '{':
            stack.append((' '.join(src[start:m.start()].split()), m.end()))
        elif stack:
            sel, body_at = stack.pop()
            body = src[body_at:m.start()]
            if '{' not in body:
                yield sel, body, sel == ':root'
        start = m.end()


def _decls(body: str):
    for d in re.finditer(r'(?<![\w-])(font(?:-size|-family)?)\s*:\s*([^;]+)', body):
        yield d.group(1), d.group(2).strip()


def _step(value: str) -> str | None:
    m = re.search(r'var\(--fs-([\w-]+)\)', value)
    return m.group(1) if m else None


def _family(value: str) -> str | None:
    for name, fam in (('--font-label', 'label'), ('--font-px-small', 'label'), ('--font-px', 'px'),
                      ('--font-brand', 'brand'), ('--font-ui', 'ui')):
        if f'var({name})' in value:
            return fam
    return None


def test_the_scale_is_root_tokens_in_px():
    root = next(body for sel, body, is_root in _rules(CSS) if is_root)
    got = {m.group(1): int(m.group(2)) for m in re.finditer(r'--fs-([\w-]+):\s*(\d+)px;', root)}
    assert got == SCALE
    steps = [SCALE[k] for k in ('2xs', 'xs', 'sm', 'base', 'md', 'lg', 'xl', '2xl', '3xl', '4xl')]
    assert steps == sorted(steps) and len(set(steps)) == len(steps)


def test_every_font_size_outside_root_is_a_step_of_the_scale():
    bad = []
    for sel, body, is_root in _rules(CSS):
        if is_root:
            continue
        for prop, value in _decls(body):
            if prop == 'font-family' or value == 'inherit':
                continue
            if prop == 'font-size' and value == '0':          # a label hidden in favour of its short twin, not a size
                continue
            step = _step(value)
            if step is not None:
                if step not in SCALE:
                    bad.append((sel, value, 'no such step'))
                continue
            if sel.split(',')[0].strip() in NOT_A_STEP:
                continue
            bad.append((sel, value, 'not a step'))
    assert not bad, bad


def test_each_family_keeps_to_its_own_steps():
    """VT323 at 16px and up (13-15px read as a smudge), Jersey 20 at 20px and up (its pixels need the size)."""
    allowed = {'label': LABEL_STEPS, 'px': PX_STEPS, 'brand': BRAND_STEPS, 'ui': UI_STEPS}
    bad = []
    for sel, body, is_root in _rules(CSS):
        if is_root:
            continue
        fam = step = None
        for prop, value in _decls(body):
            fam = _family(value) or fam
            if prop != 'font-family':
                step = _step(value) or step
        if fam is None or sel.split(',')[0].strip() in NOT_A_STEP:
            continue
        if step is None:
            if sel != 'h1, h2, h3':                            # their sizes are h1 / h2 / h3's own rules
                bad.append((sel, fam, 'a family without its size'))
            continue
        if step not in allowed[fam]:
            bad.append((sel, fam, step))
    assert not bad, bad


def test_the_tag_badge_is_the_ui_font_at_11px():
    """AGENTS.md: every tag badge in the UI font at 11px."""
    tag = re.search(r'\n\.tag \{([^}]*)\}', CSS).group(1)
    assert 'font: 600 var(--fs-xs)/1 var(--font-ui);' in tag and 'min-width: var(--tag-w);' in tag
    assert SCALE['xs'] == 11
    # the hover card's badges too (they were 10px)
    card_tag = re.search(r'table\.dt-rows \.tag \{([^}]*)\}', CSS).group(1)
    assert 'font' not in card_tag


def test_builders_and_scripts_write_no_font_size():
    """Sizes live in styles.css: an inline size in a builder or a script would be a step outside the scale. The shop's
    price sizes (the game's CostLabel per tier) and its name fitting (the game's own units) are the exception."""
    hits = []
    for f in sorted((ROOT / 'builders').glob('*.py')) + [ROOT / 'site' / 'scripts.js']:
        for i, line in enumerate(f.read_text(encoding='utf-8').splitlines(), 1):
            if re.search(r'font-size\s*:|fontSize\s*=\s*[\'"]\d|font\s*:\s*\d', line):
                hits.append(f'{f.name}:{i}')
    assert not hits, hits


# ---------- in a browser: the components as the builders write them ----------

def _components() -> str:
    from builders.render import pip, tag_badge
    return (
        '<nav class="top-nav"><div class="nav-inner"><a class="nav-brand"><span class="nav-brand-text">Cyclopean'
        '<small>deadlock.vpk</small></span></a><div class="nav-tabs"><a class="nav-tab active">Heroes</a></div>'
        '<a class="nav-build">game build 6793</a></div></nav><main class="page entity">'
        '<div class="crumbs">Heroes / Haze</div>'
        '<div class="hero-head"><div class="hh-id"><h1>Haze</h1><div class="chips"><span class="chip">Assassin</span>'
        '</div><div class="meta">First seen 2024-06-06</div></div><div class="keystats"><div class="keystat">'
        '<div class="v">8.2<span class="u">m/s</span></div><div class="l">Move speed</div></div></div>'
        '<div class="head-strip"><span class="hs-l">Patches</span></div></div>'
        '<section class="weapon-block"><div class="wb-id"><div><span class="wb-kicker">Weapon</span>'
        '<div class="wb-name">Censure &amp; Penance</div><div class="wb-name unnamed">No in-game name yet</div>'
        '<div class="wb-links"><a class="ac-last">' + pip('nerf', 1) + '2025-11-22</a><a class="ac-hist">History'
        '</a></div></div></div><div class="wb-top"><div class="wcell top"><div class="v">50.1</div><div class="l">DPS'
        '</div></div></div><div class="wb-alt"><span class="wb-alt-l">Alt fire</span><div class="wb-alt-cells">'
        '<div class="wcell"><div class="v">1.5<span class="u">s</span></div><div class="l">Reload</div></div></div>'
        '</div></section>'
        '<div class="ability-card"><div class="ac-head"><div class="ac-id"><div class="ac-name">Sleep Dagger</div>'
        '<span class="ac-sub">Ability 1</span><a class="ac-last">' + pip('nerf', 2) + '2026-09-16</a>'
        '<a class="ac-hist">History</a></div></div><div class="ac-hdr"><span class="chip">Cooldown <b>30s</b></span>'
        '</div><div class="ac-desc">Throw a dagger.</div><div class="tier"><span class="tn">T1</span>'
        '<span class="tt">-10% Bullet Resist</span></div></div>'
        '<div class="stat-flow"><div class="stat-panel"><h3>Vitality</h3><div class="sc-row"><span class="k">Run speed'
        '</span><span class="v">13<span class="u">m/s</span><span class="scale">+0.2×Spirit</span></span></div>'
        '</div></div>'
        '<div class="hblocks"><div class="banner hyear"><span class="bt">2026</span></div><details class="pblock" open>'
        '<summary class="banner named"><span class="bt"><span class="pdate">2026-09-29</span><span class="pname">'
        'City Never Sleeps</span></span><span class="bc">' + pip('buff', 1) + '<span class="chip eye-chip">1 not in '
        'notes</span><a class="pnotes" href="#">patch ↗</a></span></summary><div class="hpanel"><div class="hgroup">'
        '<div class="hg-b"><div class="esub">Bullet Dance <span class="tsum">' + pip('new', 1) + '</span></div>'
        '<div class="erow"><span class="st"></span><span class="tg">' + tag_badge('changed', 'CHANGED') + '</span>'
        '<span class="tx">Damage <span class="chip shr">shared ×17 abilities &amp; items</span></span><span class="vv">'
        '<span class="vals"><span class="old">5</span><span class="arrow">→</span><span class="new">6</span></span>'
        '<span class="pct" data-g="2">+20.0%</span></span></div><div class="vnote"><span class="vn-l">Patch notes'
        '</span>All dash slows reduced</div><details class="tech"><summary>Technical (2)</summary></details>'
        '</div></div></div></details></div>'
        '<div class="banner sub"><span class="bt">October 2026</span><span class="bc">7 updates</span></div>'
        '<a class="ix fu"><span class="ixd">2026-10-14</span><span class="ixt"><span class="t">Follow-up</span>'
        '<span class="b">2 builds</span></span><span class="ixs"><span class="ix-buff">+3</span></span></a>'
        '<div class="sum-tiles"><div class="sum-tile t-buff"><span class="n">21</span><span class="l">buffs</span>'
        '</div></div><div class="hchip"><div class="hc">' + pip('buff', 20) + pip('nerf', 3) + '</div></div>'
        '<div class="card"><span class="nm">Base Defense Sentry</span><span class="sub">x3</span><div class="last">'
        '<span class="tsum">' + pip('buff', 3) + '</span><span class="d">2026-10-16</span></div></div>'
        '<div class="htile"><span class="ht-t">Heroes</span><span class="ht-n">43</span><span class="ht-x">+1 '
        'pre-release</span></div><div class="lu-h">Heroes <b>3</b></div>'
        '<h3 class="gn-h">Heroes<span class="n">12</span></h3>'
        '<span class="it-act">Active</span><span class="fx-tag">Active</span><span class="sc">+20% <b>Melee</b></span>'
        '<details class="collapsible"><summary>Show all</summary></details>'
        '<div class="hgrid-cards"><a class="hgcard"><span class="hg-nm">Deadman Danny</span><span class="hg-rib">'
        'Pre-release</span></a></div>'
        '<div class="dyn-tip on"><div class="dt-head"><span class="dt-name">Bebop</span><span class="dt-patch">'
        '2025-12-29</span></div><div class="dt-counts">' + pip('buff', 3) + '</div><table class="dt-rows"><tr>'
        '<td class="dt-tg">' + tag_badge('nerf', 'NERF') + '</td><td class="dt-field">Stamina</td></tr></table>'
        '<div class="dt-foot">+6 more</div></div></main>')


_WALK = r"""() => {
  const out = [];
  const fam = s => s.split(',')[0].trim().replace(/^["']|["']$/g, '');
  for (const el of document.body.querySelectorAll('*')) {
    let txt = '';
    for (const n of el.childNodes) if (n.nodeType === 3) txt += n.nodeValue;
    const r = el.getBoundingClientRect();
    if (txt.trim() && r.width > 0) {
      const cs = getComputedStyle(el);
      out.push([el.className.toString(), txt.trim().slice(0, 30), fam(cs.fontFamily), parseFloat(cs.fontSize)]);
    }
    const ps = getComputedStyle(el, '::before');
    if (ps.content && /^"[^"]+"$/.test(ps.content) && ps.display !== 'none')
      out.push([el.className.toString() + '::before', ps.content, fam(ps.fontFamily), parseFloat(ps.fontSize)]);
  }
  return out;
}"""


def _check(walked) -> list:
    sizes = set(SCALE.values())
    bad = []
    for cls, txt, fam, size in walked:
        if size == 0:
            continue
        if size not in sizes:
            bad.append((cls, txt, fam, size, 'not a step'))
        elif fam == 'VT323' and size < 16:
            bad.append((cls, txt, fam, size, 'VT323 under 16px'))
        elif fam == 'Jersey 20' and size < 20:
            bad.append((cls, txt, fam, size, 'Jersey under 20px'))
    return bad


@pytest.mark.parametrize('width', [1440, 390])
def test_the_components_resolve_to_the_scale(browser, width):
    from test_perf_browser import _open
    page, errors = _open(browser, _components(), width=width)
    walked = page.evaluate(_WALK)
    assert len(walked) > 60
    assert not _check(walked)
    got = {cls: (fam, size) for cls, _, fam, size in walked}
    assert got['chip shr'] == ('VT323', 16)                   # was 14px: "SHARED ×17 ABILITIES & ITEMS"
    assert got['u'] == ('VT323', 16)                          # a unit beside a number: was 13-15px
    assert got['it-act'] == ('IBM Plex Sans', 11) and got['fx-tag'] == ('IBM Plex Sans', 11)   # VT323 14 / 13px
    assert got['tag changed'] == ('IBM Plex Sans', 11) and got['tag nerf'] == ('IBM Plex Sans', 11)
    assert got['ht-n'] == ('Jersey 20', 20) and got['wb-name unnamed'] == ('IBM Plex Sans', 14)
    assert not errors
    page.close()


def test_a_chip_is_one_height_in_its_place(browser):
    """Chips: one size of the label font, so one height a place (a row's shared chip was 2px shorter than its line's
    other chips' text)."""
    from builders.render import pip
    from test_perf_browser import _open
    body = ('<div class="chips"><span class="chip">Assassin</span><span class="chip dev">In development</span>'
            '<a class="chip eye-link"><span class="mark hidden"></span>49 not in patch notes</a></div>'
            '<div class="ability-card"><div class="ac-hdr"><span class="chip">Cooldown <b>30s</b></span>'
            '<span class="chip">Cast time <b>0.2s</b></span></div></div>'
            f'<div class="erow"><span class="st"></span><span class="tg"></span><span class="tx">A <span class="chip shr">shared ×5 troopers</span> '
            f'<span class="chip shr">shared ×17 abilities &amp; items</span>{pip("buff", 1)}</span><span class="vv"></span></div>')
    page, errors = _open(browser, body)
    hs = page.evaluate("""() => ['.chips', '.ac-hdr', '.erow'].map(s =>
      [...new Set([...document.querySelectorAll(s + ' .chip')].map(c => Math.round(c.getBoundingClientRect().height)))])""")
    assert all(len(h) == 1 for h in hs), hs
    assert not errors
    page.close()


def test_the_matrix_column_row_sticks_right_under_the_month_row(browser, tmp_path):
    """The month row's height follows its type (the --fs-sm step + its padding and line): the column row's sticky top
    is the same sum, so a scroll shows no gap and no overlap between them."""
    from test_vis_t2 import DESK, _matrix
    from test_vis_t2 import _open as open_page
    ctx, pg, errors = open_page(browser, tmp_path, _matrix(), DESK)
    try:
        cats, top = pg.evaluate("""() => [document.querySelector('table.dyn thead tr.cats').getBoundingClientRect().height,
          parseFloat(getComputedStyle(document.querySelector('table.dyn thead tr.cols th')).top)]""")
        assert abs(cats - top) < 0.5, (cats, top)
        assert not errors
    finally:
        ctx.close()


# ---------- the built pages (when there is a dist/), with the current stylesheet ----------

BUILT = ['index', 'heroes/haze', 'units/trooper_normal', 'items/warp_stone', 'game/combat', 'tables/items',
         'heroes/changes', 'patches/2026-10-14', 'patches/index']


@pytest.mark.parametrize('width', [1440, 390])
def test_built_pages_keep_to_the_scale(browser, width):
    dist = ROOT / 'dist'
    pages = [p for p in BUILT if (dist / f'{p}.html').exists()]
    if not pages:
        pytest.skip('no dist/ (python build_site.py)')
    ctx = browser.new_context(viewport={'width': width, 'height': 900}, is_mobile=width < 700, has_touch=width < 700)
    combos = {}
    try:
        for name in pages:
            pg = ctx.new_page()

            def route(r):
                url = r.request.url
                if not url.startswith('file:'):
                    return r.abort()
                if '/styles.css' in url:
                    return r.fulfill(path=str(ROOT / 'site' / 'styles.css'), content_type='text/css')
                return r.continue_()
            pg.route('**/*', route)
            pg.goto((dist / f'{name}.html').as_uri())
            walked = pg.evaluate(_WALK.replace('r.width > 0', 'r.width > 1 && el.checkVisibility()'))
            assert not _check(walked), (name, _check(walked)[:5])
            combos[name] = len({(fam, size) for _, _, fam, size in walked})
            assert pg.evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth'), name
            pg.close()
    finally:
        ctx.close()
    # family x size on a hero page: 25 before the pass (31 with weights), 12 after
    if 'heroes/haze' in combos:
        assert combos['heroes/haze'] <= 14, combos
