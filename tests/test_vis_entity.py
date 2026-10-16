"""Visual pass 2026-10-17, the entity pages (hero / item / unit / Game system): the "now" panels fill the width, the
ability cards end at their last tier, the weapon's name is a header row over even rows of numbers, the trail draws
dots for quiet patches, a band's chips share one spec, the % follows its value, an empty year waits with its bands,
the strip / matrix tile keeps its stripes whole, a phone's rows use the width, the hero head keeps the name beside
the portrait, the rework list says "more", and the Walker's weak points have names. Pages are built inside the test
and opened with the site's CSS and JS (the `browser` fixture is tests/conftest.py's)."""
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


# ---- 1. the "now" panels fill the width ------------------------------------------------------------------------


def _item(card: dict) -> str:
    from builders.entities_pages import item_page
    it = {'id': 'upgrade_x', 'file': 'abilities.vdata', 'kind': 'item', 'alive': True, 'first': [1, '2024-06-06'],
          'name': 'Silencer'}
    return item_page(it, card, {}, {})


def _prop(p: str, label: str, value: str) -> dict:
    return {'prop': p, 'label': label, 'value': value, 'scale': None, 'css': None}


SILENCER = {'header': [{'prop': 'AbilityDuration', 'label': 'Duration', 'value': '4s', 'css': None},
                       {'prop': 'AbilityCooldown', 'label': 'Cooldown', 'value': '36s', 'css': None}],
            'sections': [{'type': 'Innate', 'desc': '', 'props': [_prop('WeaponDamage', 'Weapon Damage', '+20%')]},
                         {'type': 'Active', 'desc': 'For the next 4s, your bullets apply Silence.',
                          'props': [_prop('DebuffDuration', 'Debuff Duration', '2s'),
                                    _prop('AbilityCooldown', 'Cooldown', '36s')]}]}


def test_an_items_header_values_sit_in_the_card_they_belong_to():
    """Silencer's "Duration 4s" floated centred over its cards, belonging to none: it is its Active's."""
    from builders.entities_pages import header_host
    html = _item(SILENCER)
    active = html.split('<div class="ac-name">Active</div>')[1].split('<table')[0]
    assert '<div class="ac-hdr">' in active and 'Duration <b>4s</b>' in active
    assert 'Cooldown <b>' not in active                                 # listed in the card already: not repeated
    assert 'item-hdr' not in html
    assert [header_host([{'type': t} for t in kinds]) for kinds in (
        ('Innate', 'Active'), ('Innate', 'Passive'), ('Innate',), ('Innate', ''), ('Passive', 'Active'))] == [1, 1, 0, 1, 1]
    assert header_host([]) is None
    # an item without sections keeps its values as a row of chips (left, not centred)
    bare = _item({'header': [{'prop': 'AbilityCooldown', 'label': 'Cooldown', 'value': '12s', 'css': None}], 'sections': []})
    assert '<div class="chips item-hdr">' in bare
    assert re.search(r'\.item-hdr \{[^}]*\}', CSS) and 'justify-content: center' not in re.search(
        r'\.item-hdr \{[^}]*\}', CSS).group()


def test_a_lone_item_card_fills_the_panel_with_each_label_near_its_value(browser, tmp_path):
    """Warp Stone's one card sat mid-panel with ~300px of nothing each side (max-width 580px, centred)."""
    card = {'header': [], 'sections': [{'type': 'Active', 'desc': 'Teleport ahead.', 'props': [
        _prop('A', 'Teleport Range', '11m'), _prop('B', 'Bullet Resist', '+30%'), _prop('C', 'Buff Duration', '6s'),
        _prop('D', 'Cooldown', '16s')]}]}
    ctx, pg, errors = _open(browser, tmp_path, _item(card), 1440)
    try:
        grid, one = _box(pg, '.item-secs'), _box(pg, '.item-secs > .ability-card')
        assert abs(one['l'] - grid['l']) < 4 and abs(one['r'] - grid['r']) < 4            # the frame's 2px margin
        rows = _boxes(pg, '.item-secs tr')
        assert len({round(r['l']) for r in rows}) >= 3                    # the rows flow in columns
        for tr in pg.query_selector_all('.item-secs tr'):
            lab, val = tr.query_selector('td').bounding_box(), tr.query_selector('td.v').bounding_box()
            assert val['x'] + val['width'] - lab['x'] < 330                # a label stays near its value
        assert not errors
    finally:
        ctx.close()
    ctx, pg, errors = _open(browser, tmp_path, _item(SILENCER), 1440)
    try:
        cards, grid = _boxes(pg, '.item-secs > .ability-card'), _box(pg, '.item-secs')
        assert abs(cards[0]['l'] - grid['l']) < 4 and abs(cards[-1]['r'] - grid['r']) < 4
        assert cards[0]['h'] < cards[1]['h']                                # a one-row Innate is not stretched
    finally:
        ctx.close()


def _stat_page(groups: dict[str, int]) -> str:
    from builders.common import page
    from builders.hero_page import stat_tables
    cols, values = [], {}
    for g, n in groups.items():
        for i in range(n):
            k = f'{g}{i}'
            cols.append({'key': k, 'label': f'{g} stat {i}', 'group': g, 'digits': 1, 'pol': 1})
            values[k] = i + 1.5
    row = {'values': values, 'history': {}, 'spirit_scaled': []}
    return page('Unit', '<details class="now px-frame" open><summary>Current stats</summary><div class="now-body">'
                + stat_tables(row, cols, 'Unit') + '</div></details>', '../', cls='entity')


def test_stat_panels_share_the_width_left_to_right(browser, tmp_path):
    """Three 280px panels sat centred with dead gutters (units, Game systems): they fill the box, a row's panels as
    tall as its tallest; a lone panel lays its rows in columns (its value 1100px from its label otherwise)."""
    ctx, pg, errors = _open(browser, tmp_path, _stat_page({'Vitality': 3, 'Attack': 7, 'Movement': 2}), 1440)
    try:
        flow, panels = _box(pg, '.stat-flow'), _boxes(pg, '.stat-panel')
        assert abs(panels[0]['l'] - flow['l']) < 2 and abs(panels[-1]['r'] - flow['r']) < 2
        assert len({round(p['h']) for p in panels}) == 1                    # one row, one height
        assert not errors
    finally:
        ctx.close()
    ctx, pg, errors = _open(browser, tmp_path, _stat_page({'Vitality': 9}), 1440)
    try:
        flow, panel = _box(pg, '.stat-flow'), _box(pg, '.stat-panel')
        assert abs(panel['w'] - flow['w']) < 2
        assert len({round(r['l']) for r in _boxes(pg, '.sc-row')}) >= 2     # in columns
        for r in _boxes(pg, '.sc-row'):
            assert r['w'] < 600
    finally:
        ctx.close()
    ctx, pg, errors = _open(browser, tmp_path, _stat_page({'Vitality': 3, 'Attack': 7, 'Movement': 2}), 390, 844, True)
    try:
        assert _no_side_scroll(pg) and not errors
    finally:
        ctx.close()


# ---- 2. ability cards end at their last tier -------------------------------------------------------------------


def _ability(cid: str, rows: int, tiers: int) -> dict:
    return {'id': cid, 'kind': 'ability', 'owner': 'hero_haze', 'slot': 'Signature_1', 'name': cid.title(),
            'desc': 'Throw a dagger.', 'header': [{'prop': 'AbilityCooldown', 'label': 'Cooldown', 'value': '30s', 'css': None},
                                                  {'prop': 'AbilityCastDelay', 'label': 'Cast time', 'value': '0.2s', 'css': None}],
            'important': [_prop(f'P{i}', f'Property {i}', f'{i}s') for i in range(rows)], 'basic': [],
            'tiers': [{'tier': i + 1, 'text': f'+{i}s Duration', 'bonuses': []} for i in range(tiers)]}


def test_ability_cards_end_at_their_last_tier(browser, tmp_path, monkeypatch):
    """Cards stretched to the row's tallest with T1-T3 pinned to the bottom left 150-200px holes (Smoke Bomb, Bullet
    Dance); the usual two header chips share one line."""
    from builders import hero_page
    from builders.common import page
    monkeypatch.setattr('builders.trail.trail_html', lambda *a, **k: '')
    monkeypatch.setattr('builders.trail.last_counts', lambda key: None)
    cards = [hero_page.ability_card(_ability(c, n, 3), '../', 'Ability 1')
             for c, n in (('dagger', 7), ('bomb', 1), ('fixation', 2), ('dance', 5))]
    body = '<section class="now-open"><h2>Abilities</h2><div class="ability-grid">' + ''.join(cards) + '</div></section>'
    ctx, pg, errors = _open(browser, tmp_path, page('Haze', body, '../', cls='entity'), 1440)
    try:
        boxes = _boxes(pg, '.ability-card')
        assert len({round(b['t']) for b in boxes}) == 1 and boxes[1]['h'] < boxes[0]['h'] - 100
        for c in pg.query_selector_all('.ability-card'):
            card, last = c.bounding_box(), c.query_selector('.tier:last-child').bounding_box()
            assert card['y'] + card['height'] - (last['y'] + last['height']) < 4      # no hole under T3
        assert not errors
    finally:
        ctx.close()
    # the chips' size (the fonts are offline here, so their line is checked on the built site's screenshots)
    assert re.search(r'\.ability-card \.ac-hdr \.chip \{[^}]*font-size: 15px', CSS)
    assert '.tiers { margin-top: auto; }' not in CSS


# ---- 3. the weapon: a header row over even rows of numbers -----------------------------------------------------


def test_weapon_rows_come_out_even():
    from builders.hero_page import wb_per_row
    assert [wb_per_row(n) for n in (0, 1, 6, 8, 9, 12, 13, 14, 16, 17)] == [1, 1, 6, 8, 5, 6, 7, 7, 8, 6]


def _weapon_page(n_rest: int) -> str:
    from builders import hero_page
    from builders.common import page
    top = [('dps', 'DPS'), ('dps_max', 'Max DPS'), ('bullet_dmg', 'Bullet DMG'), ('bps', 'Bullets / s'),
           ('clip', 'Ammo'), ('reload', 'Reload (s)')]
    rest = [(f'x{i}', f'Weapon number {i}') for i in range(n_rest)]
    cols = [{'key': k, 'label': lbl, 'group': 'Damage', 'digits': 2, 'pol': 1} for k, lbl in top + rest]
    row = {'values': {c['key']: 1.5 for c in cols}, 'history': {}, 'spirit_scaled': []}
    block = hero_page.weapon_block({'name': 'Censure & Penance', 'id': 'w'}, row, cols, 'Haze', '../')
    return page('Haze', f'<section class="now-open">{block}</section>', '../', cls='entity')


def test_the_weapon_name_heads_the_block_and_no_row_ends_in_a_hole(browser, tmp_path, monkeypatch):
    """A 250px column put the name on two lines over ~400px of nothing; 6 + 6 + 2 numbers left a hole of four."""
    monkeypatch.setattr('builders.trail.trail_html', lambda *a, **k: '')
    monkeypatch.setattr('builders.trail.last_counts', lambda key: None)
    for width, phone in ((1440, False), (1000, False), (390, True)):
        ctx, pg, errors = _open(browser, tmp_path, _weapon_page(14), width, 844, phone)
        try:
            name, nums = _box(pg, '.wb-name'), _box(pg, '.wb-nums')
            assert name['b'] <= nums['t'] and name['h'] < 40                  # one line, above the numbers
            box = _box(pg, '.wb-cells')
            cells = _boxes(pg, '.wb-cells > .wcell')
            rows: dict[int, list[dict]] = {}
            for c in cells:
                rows.setdefault(round(c['t']), []).append(c)
            for got in rows.values():
                assert abs(max(c['r'] for c in got) - box['r']) < 2, width     # every row reaches the right edge
            if width == 1440:
                assert [len(v) for v in rows.values()] == [7, 7]
            assert _no_side_scroll(pg) and not errors
        finally:
            ctx.close()


# ---- 4. the trail: dots for quiet patches, none for one change ---------------------------------------------------


def test_a_trail_of_one_change_is_not_drawn_on_its_own_page(monkeypatch):
    from builders import trail
    rows = [{'id': f'p{i}', 'date': f'2026-0{i}-01', 'title': f'0{i}-01-2026 Update'} for i in range(1, 6)]
    hits = {'abilities.vdata:one': {'p3': {'buff': 1}}, 'abilities.vdata:two': {'p2': {'buff': 1}, 'p4': {'nerf': 1}}}
    monkeypatch.setattr(trail, '_index', lambda: (rows, hits, {}))
    trail._positions.cache_clear()
    trail.trail_html.cache_clear()
    try:
        assert trail.trail_html('abilities.vdata:one', None, '../', local=True) == ''
        two = trail.trail_html('abilities.vdata:two', None, '../', local=True)
        assert two.count('<span class="sq"></span>') == 3 and two.count('<a class="sq') == 2
        # a patch page keeps the one square of its own patch
        assert 'class="sq t-buff cur"' in trail.trail_html('abilities.vdata:one', 'p3', '../')
    finally:
        trail._positions.cache_clear()
        trail.trail_html.cache_clear()
    # a quiet patch is a faint dot, not a framed box that reads as an unchecked checkbox
    rule = re.search(r'\.trail span\.sq \{[^}]*\}', CSS).group()
    assert 'box-shadow: none' in rule and '2px 2px no-repeat' in rule


# ---- 5. a band's chips, 6. the % after its value, 7. an empty year -------------------------------------------------


def _band_page(extra_rows=()) -> str:
    from builders.common import page
    from builders.history_view import history_table
    r1 = {'id': 'p1', 'date': '2026-09-16', 'title': '09-16-2026 Update'}
    rows = [ch(key='abilities.vdata:a:r', label='Radius', old_s='3m', new_s='4m', dir='buff', pct=33.3, status='hidden'),
            ch(key='abilities.vdata:a:c', label='Cooldown', dir='nerf', pct=7.4), *extra_rows]
    return page('Haze', history_table([('abilities.vdata:a', 'Sleep Dagger', None)], ['Sleep Dagger'],
                                      {'abilities.vdata:a': [(r1, rows)]}, {}, '../'), '../', cls='entity')


def test_a_bands_chips_share_one_spec(browser, tmp_path):
    """Five chip looks in three sizes on one banner (net mark, eye, "+N for all", "description changed", patch ↗)."""
    ctx, pg, errors = _open(browser, tmp_path, _band_page(), 1440)
    try:
        got = pg.evaluate("""[...document.querySelectorAll('.hblocks .banner .bc > :not(.tsum)')].map(e => {
            const s = getComputedStyle(e); return [e.className, Math.round(e.getBoundingClientRect().height),
            s.fontSize, s.fontFamily, s.textTransform]; })""")
        assert {g[0].split()[0] for g in got} >= {'net-chip', 'chip', 'pnotes'}
        assert len({tuple(g[1:]) for g in got}) == 1 and got[0][1] == 20 and got[0][2] == '11px'
        assert not errors
    finally:
        ctx.close()
    for cls in ('eye-chip', 'shr-chip', 'txt-chip', 'pnotes'):
        assert re.search(rf'\.hblocks \.banner \.bc > \.{cls} \{{ --c: var\(--', CSS), cls


def test_the_percent_follows_its_value(browser, tmp_path):
    """The % sat at x≈1270 while its value ended near x=600."""
    ctx, pg, errors = _open(browser, tmp_path, _band_page(), 1440)
    try:
        new, pct = _box(pg, '.erow .vals .new'), _box(pg, '.erow .vals .pct')
        assert 0 <= pct['l'] - new['r'] <= 16 and pct['t'] < new['b'] and pct['b'] > new['t']    # on its line
        assert not errors
    finally:
        ctx.close()


def test_a_year_of_bands_behind_a_switch_waits_with_them(browser, tmp_path):
    """Silencer's "2026" stood over nothing: its only band held rules for all items (hidden by default)."""
    from builders.common import page
    from builders.history_view import YEAR_BANNERS_MIN, band_kind, history_table, year_class
    assert band_kind('<details class="pblock has-hidden every-only" id="p-x">') == 'every'
    assert band_kind('<details class="pblock dev-only" id="p-x">') == 'dev'
    assert band_kind('<details class="pblock" id="p-x">') == ''
    assert [year_class(k) for k in (['every'], ['every', 'every'], ['dev'], ['every', 'dev'], ['every', ''], [])] == [
        ' every-only', ' every-only', ' dev-only', ' ed-only', '', '']
    key = 'abilities.vdata:upgrade_x'
    hist = [({'id': f'p{i}', 'date': f'2025-0{i}-01', 'title': f'0{i}-01-2025 Update'},
             [ch(key=f'{key}:{i}', label=f'Thing {i}')]) for i in range(1, YEAR_BANNERS_MIN + 1)]
    hist.append(({'id': 'q1', 'date': '2026-09-29', 'title': '09-29-2026 Update'},
                 [ch(key=f'{key}:all', label='Sell price', shared_all=True, shared_n=200, shared_what='items',
                     file='abilities.vdata')]))
    html = page('Silencer', history_table([(key, 'Silencer', None)], ['Silencer'], {key: hist}, {}, '../',
                                          every_label='For all items'), '../', cls='entity')
    assert '<h3 class="banner sub hyear every-only"><span class="bt">2026</span>' in html
    assert '<h3 class="banner sub hyear"><span class="bt">2025</span>' in html
    ctx, pg, errors = _open(browser, tmp_path, html, 1440)
    try:
        years = "[...document.querySelectorAll('.hyear')].map(h => h.offsetParent !== null)"
        assert pg.evaluate(years) == [False, True]
        pg.click('.hist-bar .hf-every')
        assert pg.evaluate(years) == [True, True]
        assert not errors
    finally:
        ctx.close()


# ---- 8. the tile: the stripes whole, the count on a plate ------------------------------------------------------


def test_a_tile_keeps_its_stripes_whole_and_its_count_on_a_plate(browser, tmp_path):
    """The eye notch bit a black hole out of the stripes; the count was dark ink on whatever stripe lay under it and
    "28" ran into the eye on a phone's 17px tile."""
    from builders.common import page
    from builders.history_view import patch_strip
    assert not re.search(r'\.(ps-tile|dsq)\.hid::(before|after)', CSS)
    assert re.search(r'\.ps-tile\.hid, \.dsq\.hid \{ border-top: 4px solid var\(--eye\); \}', CSS)
    hdr = [{'id': f'p{i}', 'date': f'2026-0{i}-01', 'title': f'0{i}-01-2026 Update'} for i in range(1, 10)]
    items = [(h['id'], h, {'buff': 20, 'nerf': 8}, 3 if i % 2 else 0, [], 'mix') for i, h in enumerate(hdr)]
    ctx, pg, errors = _open(browser, tmp_path, page('X', f'<div class="head-strip">{patch_strip(items)}</div>', '../',
                                                    cls='entity'), 390, 844, True)
    try:
        for t in pg.query_selector_all('.ps-tile'):
            tile, n = t.bounding_box(), t.query_selector('.dn').bounding_box()
            assert n['x'] >= tile['x'] and n['x'] + n['width'] <= tile['x'] + tile['width'] + 0.5   # "28" fits its tile
        st = pg.evaluate("(() => { const s = getComputedStyle(document.querySelector('.ps-tile .dn'));"
                         " return [s.backgroundColor, s.color]; })()")
        assert st[0] not in ('rgba(0, 0, 0, 0)', 'transparent')
        hid = pg.evaluate("getComputedStyle(document.querySelector('.ps-tile.hid')).borderTopWidth")
        assert hid == '4px' and not errors
    finally:
        ctx.close()


# ---- 9. a phone's rows, 11. the banner's chips on a phone, 12. the rule-for-all row --------------------------------


def test_a_phones_rows_use_the_width(browser, tmp_path):
    """On a 390px phone the icon column, the eye and the tag started the label at x≈188: every change wrapped to
    2-3 lines and a console variable broke mid-word."""
    from builders.common import page
    from builders.history_view import history_table
    r1 = {'id': 'p1', 'date': '2026-09-29', 'title': '09-29-2026 Update'}
    keys = [('heroes.vdata:h', 'Base stats', None), ('abilities.vdata:a', 'Fixation', None)]
    by_ent = {'heroes.vdata:h': [(r1, [ch(key='heroes.vdata:h:hp', label='Health', old_s='700', new_s='730', dir='buff',
                                          pct=4.3)])],
              'abilities.vdata:a': [(r1, [
                  ch(key='abilities.vdata:a:s', label='Headshot Stacks', old_s='2', new_s='3', dir='buff', pct=50.0),
                  ch(key='abilities.vdata:a:c', op='add', old_s=None, pct=None, dir=None, new_s='true',
                     label='citadel_movement_temp_blocker_new'),
                  ch(key='abilities.vdata:a:all', label='Level 20: souls needed', shared_all=True, shared_n=40,
                     shared_what='heroes', file='heroes.vdata')])]}
    html = page('Haze', history_table(keys, ['Haze'], by_ent, {}, '../', areas={'heroes.vdata:h': 'stats'}), '../',
                cls='entity')
    assert 'citadel_<wbr>movement_<wbr>temp_<wbr>blocker_<wbr>new' in html
    ctx, pg, errors = _open(browser, tmp_path, html, 390, 844, True)
    try:
        assert _no_side_scroll(pg)
        icon, head = _box(pg, '.hgroup.has-ic > .ab-ic'), _box(pg, '.hgroup.has-ic .esub .nm')
        assert head['l'] > icon['r'] and head['t'] < icon['b']             # the icon is in the sub-head
        row = pg.query_selector('.hgroup.has-ic .erow')
        label, vals = row.query_selector('.tx').bounding_box(), row.query_selector('.vals').bounding_box()
        assert label['x'] < 150                                            # it started at 188
        assert abs(vals['y'] - label['y']) < 4                             # a short value on the label's line
        # the console variable breaks after an underscore, not inside a word
        words = pg.evaluate("""(() => { const tx = [...document.querySelectorAll('.erow .tx')]
            .find(t => t.textContent.startsWith('citadel_')); const r = document.createRange(); const out = [];
            const walk = document.createTreeWalker(tx, NodeFilter.SHOW_TEXT); let n, top = null, line = '';
            while ((n = walk.nextNode())) {
              for (let i = 0; i < n.length; i++) { r.setStart(n, i); r.setEnd(n, i + 1);
                const t = Math.round(r.getBoundingClientRect().top);
                if (top !== null && t > top + 2) { out.push(line); line = ''; } top = t; line += n.data[i]; } }
            out.push(line); return out; })()""")
        assert all(w.endswith('_') for w in words[:-1]), words
        # the band's chips start their own line at the left; the rule-for-all row's counts follow its words
        bc, bt = _box(pg, '.banner .bc'), _box(pg, '.banner .bt')
        first = _box(pg, '.banner .bc > *')
        assert bc['t'] >= bt['b'] - 1 and abs(first['l'] - bt['l']) < 20
        shr_t, shr_n = _box(pg, '.erow.shr-all .shr-t'), _box(pg, '.erow.shr-all .vv')
        assert shr_n['l'] >= shr_t['l'] - 1
        assert not errors
    finally:
        ctx.close()


# ---- 10. the hero head on a narrow screen ----------------------------------------------------------------------


def test_the_hero_head_keeps_the_name_beside_the_portrait(browser, tmp_path, monkeypatch):
    """Under 980px the head was one column: a 110px portrait alone over 250-600px of nothing, the name below it."""
    from builders import hero_page
    monkeypatch.setattr('builders.trail.trail_html', lambda *a, **k: '')
    monkeypatch.setattr('builders.trail.last_counts', lambda key: None)
    cols = [{'key': k, 'label': lbl, 'group': 'Vitality', 'digits': 2, 'pol': 1}
            for k, lbl in (('hp', 'Health'), ('hp_regen', 'HP Regen'), ('move', 'Move Speed (m/s)'), ('stamina', 'Stamina'))]
    row = {'values': {'hp': 730, 'hp_regen': 2, 'move': 8.2, 'stamina': 3}, 'history': {}, 'spirit_scaled': []}
    h = {'id': 'hero_haze', 'file': 'heroes.vdata', 'name': 'Haze', 'alive': True, 'state': 'EHeroDevState_Release',
         'first': [1, '2024-06-06']}
    html = hero_page.hero_page(h, {}, row, cols, {}, {}, {})
    for width, side in ((1440, 150), (800, 110), (390, 88)):
        ctx, pg, errors = _open(browser, tmp_path, html, width, 844, width < 600)
        try:
            pic, name, stats = _box(pg, '.hero-head .portrait'), _box(pg, '.hero-head h1'), _box(pg, '.hero-head .keystats')
            assert abs(pic['w'] - side) < 1, width
            assert name['l'] > pic['r'] and name['t'] < pic['b'], width        # side by side
            if width < 980:
                assert stats['t'] >= pic['b'] and stats['l'] <= pic['l'] + 1   # the stats take the width below
            else:
                assert stats['l'] > pic['r']
            assert _no_side_scroll(pg) and not errors
        finally:
            ctx.close()


# ---- 13. a fold's mark leads, a cut list says "more" --------------------------------------------------------------


def test_a_fold_mark_leads_its_words_and_a_cut_list_says_more(browser, tmp_path):
    from builders.cards import row
    from builders.common import page
    assert re.search(r'details\.txt > summary \.erow \.tx::before \{ content: "\+"', CSS)
    assert 'details.txt > summary .erow .tx::after' not in CSS and 'details.fam > summary .erow .tx::after' not in CSS
    long = ', '.join(f'Lifesteal Duration {i}s' for i in range(40))
    short = 'Bullet Damage +7'
    vals = lambda t: f'<span class="vals wrap"><span class="old">{t}</span><span class="arrow">→</span><span class="new">{t}</span></span>'  # noqa: E731
    rows = (row('documented', '', 'T3 upgrade', vals(long), 'rw') + row('documented', '', 'T2 upgrade', vals(short), 'rw'))
    html = page('X', f'<div id="history" class="hblocks"><div class="hpanel"><div class="hgroup"><div class="hg-b">{rows}'
                     '</div></div></div></div>', '../', cls='entity')
    ctx, pg, errors = _open(browser, tmp_path, html, 1440)
    try:
        pg.wait_for_function("document.querySelector('.erow.rw').classList.contains('clamped')")
        flags = pg.evaluate("[...document.querySelectorAll('.erow.rw')].map(r => r.classList.contains('clamped'))")
        assert flags == [True, False]
        more = "getComputedStyle(document.querySelector('.erow.rw .vv'), '::after').content"
        assert pg.evaluate(more) == '"more ▾"'
        pg.click('.erow.rw .vv')
        assert pg.evaluate(more) == '"less ▴"'
        assert pg.evaluate("document.querySelector('.erow.rw .vals.wrap').classList.contains('open')")
        assert not errors
    finally:
        ctx.close()


# ---- 14. the Walker's weak points have names ------------------------------------------------------------------------


def test_the_walkers_weak_points_have_names(tmp_path, monkeypatch):
    """"Weak point (joint_rear_left): health" showed an internal id (AGENTS.md: never on a page); its current and full
    health both read "health"."""
    import gzip
    import json
    from builders import common
    from pipeline import semantics
    assert semantics._describe_raw('m_vecWeakPoints{joint_rear_left}.m_nMaxHealth', {}, 'npc_boss_tier2', 'unit')[
        'label'] == 'Rear left leg weak point › Max Health'
    assert semantics._describe_raw('m_vecWeakPoints{head}.m_nOnBreakBonusDamage', {}, 'npc_boss_tier2', 'unit')[
        'label'] == 'Head weak point › On Break Bonus Damage'
    old = [('m_vecWeakPoints{joint_rear_left}.m_nMaxHealth', 'Weak point (joint_rear_left): health',
            'Rear left leg weak point › Max Health'),
           ('m_vecWeakPoints{canister}.m_nHealth', 'Weak Points canister › Health', 'Canister weak point › Health'),
           ('m_vecWeakPoints{joint_front_x}.m_nHitGroup', 'Weak Points joint front x › Hit Group',
            'Front x weak point › Hit Group'),
           ('m_vecWeakPoints{head}.m_nHealth', 'Head weak point › Health', 'Head weak point › Health'),
           ('m_flWeakPointRespawnAtHealthPct', 'Weak Point Respawn At Health', 'Weak Point Respawn At Health')]
    for path, label, want in old:
        assert semantics.readable_label(label, path) == want
    rec = {'entities': [{'changes': [{'path': p, 'label': lb} for p, lb, _ in old]}]}
    (tmp_path / 'patches').mkdir()
    with gzip.open(tmp_path / 'patches' / 'x.json.gz', 'wt', encoding='utf-8') as f:
        json.dump(rec, f)
    monkeypatch.setattr(common, 'DATA', tmp_path)
    got = [c['label'] for c in common.load_json('patches/x.json.gz')['entities'][0]['changes']]
    assert got == [w for _, _, w in old] and not any('_' in g for g in got)
