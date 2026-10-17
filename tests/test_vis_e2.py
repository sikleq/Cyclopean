"""Visual pass 2026-10-17, round 2, the entity pages: the hero's key stats and the weapon's numbers are grids whose
columns line up and whose rows come out whole; the patch strip sits in the head with a "Patches" label; a unit's,
an item's and a Game system's values today are ONE component flowing in columns; a history band's title leads with
its date; every tile's label is one style; a hover card's field column gets its share; a unit variant and the skin
chip read plainly. Pages are built inside the test and opened with the site's CSS and JS (`browser`: conftest.py)."""
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / 'site' / 'styles.css').read_text(encoding='utf-8')


def ch(**kw):
    base = {'op': 'change', 'cat': 'balance', 'label': 'Cooldown', 'old_s': '27', 'new_s': '29',
            'dir': 'nerf', 'pct': 7.4, 'grad': 2, 'status': 'documented', 'path': 'x'}
    base.update(kw)
    return base


def _open(browser, tmp_path: Path, html: str, width: int, height: int = 900, phone: bool = False):
    """The page in tmp_path/x/ with the site's CSS and JS one level up (rel '../'), offline."""
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
    pg.goto(f.as_uri())
    return ctx, pg, errors


def _box(pg, sel: str) -> dict:
    return pg.evaluate(f"(() => {{ const r = document.querySelector({sel!r}).getBoundingClientRect();"
                       " return {l: r.left, r: r.right, t: r.top, b: r.bottom, w: r.width, h: r.height}; })()")


def _boxes(pg, sel: str) -> list[dict]:
    return pg.evaluate(f"[...document.querySelectorAll({sel!r})].map(e => {{ const r = e.getBoundingClientRect();"
                       " return {l: r.left, r: r.right, t: r.top, b: r.bottom, w: r.width, h: r.height}; })")


def _no_side_scroll(pg) -> bool:
    return pg.evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth')


def _grid_ok(pg, sel: str) -> tuple[dict[int, list[dict]], set[int]]:
    """The tiles of a grid by row, and the x of every tile edge: rows whole (each reaches the box's right edge) and
    the columns lined up (few distinct edges) are what the tests check."""
    box, tiles = _box(pg, sel), _boxes(pg, f'{sel} > *')
    rows: dict[int, list[dict]] = {}
    for t in tiles:
        rows.setdefault(round(t['t']), []).append(t)
    for got in rows.values():
        assert abs(max(t['r'] for t in got) - box['r']) < 2, sel                # no hole, no row short of the edge
        assert abs(min(t['l'] for t in got) - box['l']) < 2, sel
    return rows, {round(t['l']) for t in tiles} | {round(t['r']) for t in tiles}


HERO_STATS = (('hp', 'Health'), ('hp_lvl', '+HP / boon'), ('hp_regen', 'HP Regen'), ('move', 'Move Speed (m/s)'),
              ('sprint', 'Sprint (m/s)'), ('stamina', 'Stamina'), ('stamina_regen', 'Stamina Regen (/s)'),
              ('ground_dash', 'Ground Dash (s)'), ('air_dash', 'Air Dash (s)'), ('light_melee', 'Light Melee'),
              ('heavy_melee', 'Heavy Melee'), ('melee_lvl', '+Melee / boon'), ('spirit_lvl', '+Spirit / boon'))


def _hero_html(monkeypatch, weapon_rest: int = 14, skin: bool = False) -> str:
    """Haze's head (13 key stats), her gun (6 + `weapon_rest` numbers) and a history of three patches."""
    from builders import hero_page
    monkeypatch.setattr('builders.trail.trail_html', lambda *a, **k: '')
    monkeypatch.setattr('builders.trail.last_counts', lambda key: None)
    monkeypatch.setattr(hero_page, 'cosmetics', lambda: {'heroes': {'hero_haze': ['base body'] if skin else []}})
    top = [('dps', 'DPS'), ('dps_max', 'Max DPS'), ('bullet_dmg', 'Bullet DMG'), ('bps', 'Bullets / s'),
           ('clip', 'Ammo'), ('reload', 'Reload (s)')]
    rest = [('bullet_dmg_lvl', '+Bullet DMG / boon')] + [(f'x{i}', f'Weapon number {i}') for i in range(weapon_rest - 1)]
    cols = ([{'key': k, 'label': lbl, 'group': 'Vitality', 'digits': 2, 'pol': 1} for k, lbl in HERO_STATS]
            + [{'key': k, 'label': lbl, 'group': 'Damage', 'digits': 2, 'pol': 1} for k, lbl in top + rest])
    row = {'values': {c['key']: 1.5 for c in cols}, 'history': {}, 'spirit_scaled': [],
           'weapon': 'citadel_weapon_haze', 'weapon_name': 'Censure & Penance'}
    h = {'id': 'hero_haze', 'file': 'heroes.vdata', 'name': 'Haze', 'alive': True, 'state': 'EHeroDevState_Release',
         'first': [1, '2024-06-06']}
    key = 'heroes.vdata:hero_haze'
    by_ent = {key: [({'id': f'p{i}', 'date': f'2026-0{i}-01', 'title': f'0{i}-01-2026 Update'},
                     [ch(key=f'{key}:hp{i}', label='Max Health', status='hidden')]) for i in range(1, 4)]}
    return hero_page.hero_page(h, {}, row, cols, {}, by_ent, {})


# ---- 1. key stats and 5. weapon numbers: grids whose columns line up, rows whole ------------------------------------


def test_lead_span_fills_whole_rows():
    from builders.hero_page import fit_cols, keystats_vars, lead_span
    assert [lead_span(n, 7) for n in (7, 13, 14)] == [1, 2, 1]
    assert [lead_span(n, 3) for n in (12, 13, 14)] == [1, 3, 2]
    for n in range(1, 30):
        for c in range(1, 9):
            assert (n - 1 + lead_span(n, c)) % c == 0                          # the rows come out whole
    assert keystats_vars(13) == '--ks-c:7;--ks-s:2;--ks-s5:3;--ks-s3:3'
    assert keystats_vars(15) == '--ks-c:8;--ks-s:2;--ks-s5:1;--ks-s3:1'
    assert [fit_cols(n, (4, 5)) for n in (14, 15, 16)] == [5, 5, 4]


def test_the_key_stats_and_weapon_numbers_line_up_in_whole_rows(browser, tmp_path, monkeypatch):
    """13 key stats split 7 + 6 and stretched, so the rows' columns missed each other; a phone's 13th spanned the
    screen alone; 14 weapon numbers at three a row left two stretched tiles (visual pass 2026-10-17, round 2)."""
    html = _hero_html(monkeypatch)
    # 13 tiles: Health spans 2 of 7 (two rows), 3 of 5 (three), a phone's whole row of 3 (five)
    for width, phone, ks_cols, ks_rows in ((1440, False, 7, 2), (800, False, 5, 3), (390, True, 3, 5)):
        ctx, pg, errors = _open(browser, tmp_path, html, width, 844, phone)
        try:
            rows, edges = _grid_ok(pg, '.keystats')
            assert len(edges) <= 2 * ks_cols, (width, edges)                  # every row on the same column lines
            assert len(rows) == ks_rows, width
            _, wedges = _grid_ok(pg, '.wb-cells')
            assert len(wedges) <= 2 * 8, width
            # a row's values share one line however their labels wrap
            for sel in ('.wb-cells > .wcell', '.keystats > .keystat'):
                tops: dict[int, set[int]] = {}
                for t in pg.query_selector_all(sel):
                    tops.setdefault(round(t.bounding_box()['y']), set()).add(round(t.query_selector('.v').bounding_box()['y']))
                assert all(len(v) == 1 for v in tops.values()), (width, sel, tops)
            assert _no_side_scroll(pg) and not errors
        finally:
            ctx.close()


def test_every_tile_label_is_one_style(browser, tmp_path, monkeypatch):
    """The six headline tiles and the key stats wore uppercase pixel labels, the other 14 numbers mixed-case sans."""
    ctx, pg, errors = _open(browser, tmp_path, _hero_html(monkeypatch), 1440)
    try:
        got = pg.evaluate("""['.keystat .l', '.wcell.top .l', '.wb-cells .wcell .l'].map(s => {
            const c = getComputedStyle(document.querySelector(s));
            return [c.fontFamily, c.fontSize, c.textTransform, c.color]; })""")
        assert got[0] == got[1] == got[2] and got[0][2] == 'uppercase'
        # every tile keeps the icon's corner slot (an empty one where the game has no stat icon)
        assert pg.evaluate("[...document.querySelectorAll('.wcell')].every(t => t.querySelector(':scope > .si'))")
        assert not errors
    finally:
        ctx.close()


# ---- 2. the patch strip in the head ------------------------------------------------------------------------------


def test_the_patch_strip_sits_in_the_head_with_its_label(browser, tmp_path, monkeypatch):
    """Two or three tiles alone under the portrait read as leftovers (Violet, Deadman Danny, Ablative Coat)."""
    html = _hero_html(monkeypatch)
    head = html.split('<div class="hero-head">')[1].split('<section class="now-open">')[0]
    assert '<div class="head-strip"><span class="hs-l">Patches</span><div class="patch-strip">' in head
    for width, phone in ((1440, False), (390, True)):
        ctx, pg, errors = _open(browser, tmp_path, html, width, 844, phone)
        try:
            pic, name, strip = _box(pg, '.hero-head .portrait'), _box(pg, '.hero-head h1'), _box(pg, '.head-strip')
            stats, label = _box(pg, '.hero-head .keystats'), _box(pg, '.head-strip .hs-l')
            assert strip['t'] > name['b'] and strip['b'] <= stats['t'] + 1     # under the name, over the stats
            if phone:
                assert abs(strip['l'] - pic['l']) <= 2 and strip['t'] >= pic['b']   # the head's whole width (frame: 2px)
            else:
                assert abs(strip['l'] - name['l']) < 2 and strip['b'] < pic['b']    # beside the portrait
            tile = _box(pg, '.head-strip .ps-tile')
            assert label['r'] < tile['l'] and label['b'] > tile['t'] and label['t'] < tile['b']    # on its line
            assert _no_side_scroll(pg) and not errors
        finally:
            ctx.close()


def test_a_hero_without_a_portrait_keeps_its_glyph_beside_the_name(browser, tmp_path, monkeypatch):
    """On a phone the glyph of a hero with no picture stayed 110px wide in an 88px column and ran under the name."""
    from builders import hero_page
    monkeypatch.setattr('builders.trail.trail_html', lambda *a, **k: '')
    monkeypatch.setattr('builders.trail.last_counts', lambda key: None)
    monkeypatch.setattr(hero_page, 'cosmetics', lambda: {'heroes': {}})
    h = {'id': 'hero_nobody_x', 'file': 'heroes.vdata', 'name': 'Druid', 'alive': True, 'state': 'EHeroDevState_Dev',
         'first': [1, '2025-08-18']}
    html = hero_page.hero_page(h, {}, None, [], {}, {}, {})
    assert 'portrait px-frame' in html and '<img class="portrait' not in html
    ctx, pg, errors = _open(browser, tmp_path, html, 390, 844, True)
    try:
        pic, name = _box(pg, '.hero-head .portrait'), _box(pg, '.hero-head h1')
        assert pic['r'] < name['l'] and abs(pic['w'] - 88) < 1 and not errors
    finally:
        ctx.close()


def test_an_item_head_holds_its_strip_at_the_names_edge(browser, tmp_path):
    from builders.entities_pages import item_page
    key = 'abilities.vdata:upgrade_x'
    by_ent = {key: [({'id': f'p{i}', 'date': f'2026-0{i}-01', 'title': f'0{i}-01-2026 Update'},
                     [ch(key=f'{key}:c{i}')]) for i in range(1, 4)]}
    it = {'id': 'upgrade_x', 'file': 'abilities.vdata', 'kind': 'item', 'alive': True, 'first': [1, '2024-06-06'],
          'name': 'Ablative Coat'}
    html = item_page(it, None, by_ent, {})
    assert html.index('<div class="page-head">') < html.index(
        '<div class="head-strip"><span class="hs-l">Patches</span>') < html.index('<h2>History')
    for width, phone in ((1440, False), (390, True)):
        ctx, pg, errors = _open(browser, tmp_path, html, width, 844, phone)
        try:
            icon, name, strip = _box(pg, '.page-head .head-icon'), _box(pg, '.page-head h1'), _box(pg, '.head-strip')
            assert name['l'] > icon['r'] and name['t'] < icon['b']                  # the name beside its icon
            assert abs(strip['l'] - (icon['l'] if phone else name['l'])) < 3 and strip['t'] > name['b']
            assert _no_side_scroll(pg) and not errors
        finally:
            ctx.close()
    # one patch: no strip, no label — only the hover cards' data
    one = item_page(it, None, {key: by_ent[key][:1]}, {})
    assert 'hs-l' not in one and 'class="strip-data"' in one


# ---- 3. the values today: one component flowing in columns ----------------------------------------------------------


def test_values_today_are_one_component(browser, tmp_path):
    """A unit's stats were equal-height boxes (Movement's one row in a box made for six), an item's values floated
    mid-card, a Game system's lists left empty boxes: groups now flow in columns, each value at its column's edge."""
    from builders.common import page
    from builders.now_values import LONG_GROUP, Row, flow, group
    assert group('Empty', []) == '' and flow(['', '']) == ''
    rows = [Row('Health', '300', 'h.svg'), Row('Resist', '25')]
    g = group('Vitality', rows)
    assert g.count('class="si"') == 2 and '<span class="si"></span>' in g      # a slot on every row…
    assert 'class="si"' not in group('Movement', [Row('Run Speed', '13')])     # …or on none
    assert '<h3>' not in group('', rows) and 'untitled' in group('', rows)     # an untitled item section: no bare bar
    assert ' long' in group('X', [Row(f'r{i}', '1') for i in range(LONG_GROUP + 1)])
    groups = [group(t, [Row(f'{t} {i}', f'{i}.5') for i in range(n)]) for t, n in
              (('Vitality', 3), ('Attack', 7), ('Movement', 1))]
    html = page('Unit', '<details class="now px-frame" open><summary>Current stats</summary><div class="now-body">'
                + flow(groups) + '</div></details>', '../', cls='entity')
    ctx, pg, errors = _open(browser, tmp_path, html, 1440)
    try:
        panels = _boxes(pg, '.stat-panel')
        assert len({round(p['l']) for p in panels}) == 3                         # three columns
        assert panels[2]['h'] < panels[1]['h'] / 3                              # Movement as tall as its one row
        for r in pg.query_selector_all('.sc-row'):
            row, v = r.bounding_box(), r.query_selector('.v').bounding_box()
            assert abs((row['x'] + row['width']) - (v['x'] + v['width'])) <= 11   # the value at the column's edge
        style = pg.evaluate("getComputedStyle(document.querySelector('.stat-panel')).boxShadow")
        assert style == 'none'                                                    # no box per group
        assert not errors
    finally:
        ctx.close()
    ctx, pg, errors = _open(browser, tmp_path, html, 390, 844, True)
    try:
        assert len({round(p['l']) for p in _boxes(pg, '.stat-panel')}) == 1 and _no_side_scroll(pg) and not errors
    finally:
        ctx.close()


def test_items_and_game_systems_use_the_component():
    from builders.entities_pages import item_page
    prop = lambda p, lb, v, css=None: {'prop': p, 'label': lb, 'value': v, 'scale': None, 'css': css}  # noqa: E731
    card = {'header': [{'prop': 'AbilityDuration', 'label': 'Duration', 'value': '4s', 'css': None}],
            'sections': [{'type': 'Innate', 'desc': '', 'props': [prop('A', 'Weapon Damage', '+20%', 'bullet_damage')]},
                         {'type': 'Active', 'desc': 'Silence.', 'props': [prop('B', 'Debuff Duration', '2s')]},
                         {'type': '', 'desc': 'Your bullets bleed.', 'props': [prop('C', 'Bleed', '3%')]}]}
    it = {'id': 'upgrade_x', 'file': 'abilities.vdata', 'kind': 'item', 'alive': True, 'first': [1, '2024-06-06'],
          'name': 'Silencer'}
    html = item_page(it, card, {}, {})
    body = html.split('<div class="now-body">')[1]
    assert body.startswith('<div class="stat-flow">') and body.count('class="stat-panel') == 3
    assert 'ability-card' not in body and '<table' not in body.split('</details>')[0]
    assert '<div class="sc-row p-bullet_damage">' in body and '<h3>Active</h3><div class="vg-top"><div class="chips vg-hdr">' in body
    assert '<section class="stat-panel untitled"><div class="vg-top"><div class="vg-desc">Your bullets bleed.' in body
    assert re.search(r'\.sc-row\.p-bullet_damage \.v', CSS)
    from builders import game_now
    urn = game_now.now_group('Soul Urn', game_now._value_rows([('Bounty', '800', '2026-01-01')]))
    assert urn.startswith('<section class="stat-panel"><h3>Soul Urn</h3><div class="sc-row">') and 'class="si"' not in urn


# ---- 4. a band's title: one template ---------------------------------------------------------------------------------


def test_a_bands_title_leads_with_its_date(browser, tmp_path):
    """A named band led with its name in pixel caps and a plain one with its date in another font: the dates jumped
    from band to band. The rule-for-all row reads as words ("All heroes: 15 changes · Hero progression › ✕15")."""
    from builders.common import band_title_html, page
    from builders.history_view import history_table
    assert band_title_html({'title': 'City Never Sleeps · 09-29-2026', 'date': '2026-09-29'}) == (
        '<span class="pdate">2026-09-29</span><span class="pname">City Never Sleeps</span>')
    assert band_title_html({'title': '09-16-2026 Update', 'date': '2026-09-16'}) == (
        '<span class="pdate">2026-09-16</span><span class="pkind">Update</span>')
    key = 'heroes.vdata:h'
    by_ent = {key: [({'id': 'p2', 'date': '2026-09-29', 'title': 'City Never Sleeps · 09-29-2026'},
                     [ch(key=f'{key}:a', label='Health'),
                      ch(key=f'{key}:all', label='Level 20: souls needed', shared_all=True, shared_n=40,
                         shared_what='heroes', file='heroes.vdata')]),
                    ({'id': 'p1', 'date': '2026-09-16', 'title': '09-16-2026 Update'}, [ch(key=f'{key}:b')])]}
    html = page('Haze', history_table([(key, 'Base stats', None)], ['Haze'], by_ent, {}, '../'), '../', cls='entity')
    assert '1 change for all heroes</span> <a class="shr-go" href="../game/progression.html#p-p2">see Hero progression ›' in html
    ctx, pg, errors = _open(browser, tmp_path, html, 1440)
    try:
        got = pg.evaluate("""[...document.querySelectorAll('.hblocks .pblock > .banner')].map(b => {
            const d = b.querySelector('.pdate'), w = d.nextElementSibling, s = getComputedStyle(d);
            return [Math.round(d.getBoundingClientRect().left), Math.round(w.getBoundingClientRect().left),
                    s.fontFamily, s.fontSize, getComputedStyle(b).backgroundImage]; })""")
        assert len(got) == 2 and got[0][:4] == got[1][:4]                       # date and name / "Update" in one place
        assert got[0][4] != got[1][4] and 'gradient' in got[1][4]               # the named band's ground is gold
        assert not errors
    finally:
        ctx.close()


# ---- 6. the hover card's field column -------------------------------------------------------------------------------


def test_a_hover_cards_field_keeps_its_share(browser, tmp_path):
    """"Min Sleep / Time" wrapped in a cramped column while a rework's long values took ~200px more than they needed."""
    from builders.common import page
    rows = (('nerf', 'Min Sleep Time', '0.3s', '0.2s'),
            ('rework', 'T1 upgrade', 'Duration 6s, Max Stacks 30',
             'Proc Damage Stack Count 20, Spirit Damage (spirit scaling) Proc Damage Stack Count 20, Spirit Damage'))
    table = ''.join(f'<tr><td class="dt-tg"><span class="tag {t}">{t.upper()}</span></td><td class="dt-field">{f}</td>'
                    f'<td class="dt-vals">{o}<i>→</i><b class="t-{t}">{n}</b></td></tr>' for t, f, o, n in rows)
    html = page('X', '<div class="dyn-tip px-frame on" style="left:8px;top:8px"><table class="dt-rows">'
                f'{table}</table></div>', '../')
    for width, phone in ((1440, False), (390, True)):
        ctx, pg, errors = _open(browser, tmp_path, html, width, 844, phone)
        try:
            lines = pg.evaluate("""(() => { const td = document.querySelector('td.dt-field'), r = document.createRange();
                r.selectNodeContents(td); return new Set([...r.getClientRects()].map(x => Math.round(x.top))).size; })()""")
            assert lines == 1, width
            assert not errors
        finally:
            ctx.close()


# ---- 7. a unit variant's title, the skin chip ----------------------------------------------------------------------


def test_a_variant_and_the_skin_chip_read_plainly(monkeypatch):
    """A Guardian group was titled just "Alt"; the head chip "skin base in files" was the files' words."""
    from builders.hero_page import SKIN_CHIP
    from builders.unit_families import families, member_label
    fam = families([{'id': i, 'name': 'Guardian', 'alive': True} for i in ('npc_boss_tier1', 'alt_npc_boss_tier1')])
    g = fam['Guardian']
    assert [member_label(m, g) for m in g] == ['Guardian', 'Guardian (Alt)']
    html = _hero_html(monkeypatch, skin=True)
    assert f'<span class="chip">{SKIN_CHIP}</span>' in html and 'skin base in files' not in html
    assert 'skin' not in _hero_html(monkeypatch, skin=False).split('<div class="chips">')[1].split('</div>')[0]
