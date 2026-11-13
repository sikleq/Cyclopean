"""The change matrices (builders/dynamics_page.py) and the buff / nerf weighing they share with the bands."""
from tests.helpers import ch, site_css


def test_change_matrix_rows_cells_and_switches(monkeypatch):
    from builders import dynamics_page
    rows = [{'id': 'p1', 'date': '2024-01-01', 'title': '01-01-2024 Update'},
            {'id': 'p2', 'date': '2026-09-29', 'title': 'City Never Sleeps · 09-29-2026'}]
    cells = {'hero:hero_atlas': {'p2': {'buff': 2, 'nerf': 1}}, 'hero:hero_x': {'p1': {'new': 1}}}
    samples = {'hero:hero_atlas': {'p2': [['Siphon Life', 'T3: Radius', '3', '2', 'nerf', 'abil', 1]]}}
    parts = {'hero:hero_atlas': {'p2': {'abil': {'nerf': 1}, 'stats': {'buff': 2}}}}
    monkeypatch.setattr(dynamics_page, '_collect', lambda: {'rows': rows, 'cells': cells, 'parts': parts,
                                                            'samples': samples, 'hidden': {'hero:hero_atlas': {'p2': 1}}})
    html = dynamics_page.matrix_html([('hero:hero_atlas', 'Abrams', None, 'hero_atlas.html', ''),
                                      ('hero:hero_x', 'Old', None, 'hero_x.html', 'extra'),
                                      ('hero:hero_none', 'Nothing', None, 'n.html', '')], 'hero')
    assert 'Nothing' not in html                                   # a row with no changes is not listed
    # stripes as one gradient in tag order (buff before nerf), the nerf held at its 12% minimum share
    assert 'var(--tag-buff) 0% 66.7%,var(--tag-nerf) 66.7% 100%' in html and 'net-buff' in html
    # review 2026-10-05: the eye in a tile's corner when the notes left something out, its count in the card's data
    assert '<a class="dsq net-buff hid" style="background:' in html and '"eye":' in html
    # a tile of one tag is a class (.dsq.s-new), no inline gradient
    assert '<a class="dsq net-buff s-new" href="hero_x.html#p-p1" data-k="1">' in html
    css = site_css()
    for t in ('new', 'rework', 'buff', 'nerf', 'del', 'on', 'off', 'mech', 'changed'):
        assert f'.dsq.s-{t} {{ background: var(--tag-{t}); }}' in css, t
    # >1 year old column: hidden with its colgroup column; a run of empty cells is one cell
    assert '<col class="old">' in html and '<td class=old></td>' in html and 'dd named' in html
    assert '--n-all:2;--n-new:1' in html
    # a tile opens the row's own page at that patch, not the patch page (off the bar since 10-03)
    # (`nh nhn`: nothing of it left out of the notes, out of sight under "Not in patch notes")
    assert 'href="hero_atlas.html#p-p2"' in html and 'tr class="extra nh nhn"' in html
    # the hover card's data: the cell's counts and its biggest changes, the number on the tile
    assert 'class="dyn-data"' in html and 'Siphon Life' in html and '<span class="dn">3</span>' in html
    # one tile per cell (no split, owner 10-01); the part counts ride in the data for the filter
    assert 'dsq split' not in html and 'tr class="sub' not in html and '{"abil":{"nerf":1}' in html
    bar = dynamics_page.toolbar('hero', 1, 'Pre-release')
    # tag chips select (only these tags), as on an entity page — not "hide this tag"
    assert 'show-old' in bar and 'bvn' in bar and 'data-dyn-tag="buff"' in bar and 'show-extra' in bar
    assert 'data-part="weapon"' in bar and 'data-part="all"' in bar


def test_the_item_matrix_reads_in_shop_order_with_slot_and_tier_filters():
    """Review 2026-10-05: 238 rows alphabetically, Weapon / Spirit / Vitality of every tier mixed, no filters; the
    hero matrix had no role filter (Hero Stats has one)."""
    from builders import dynamics_page
    items = [{'file': 'abilities.vdata', 'id': i, 'name': n, 'slot': s, 'tier': t, 'alive': True}
             for i, n, s, t in [('upgrade_b', 'Beta', 'EItemSlotType_Tech', 'EModTier_1'),
                                ('upgrade_a', 'Alpha', 'EItemSlotType_WeaponMod', 'EModTier_3'),
                                ('upgrade_c', 'Gamma', 'EItemSlotType_WeaponMod', 'EModTier_1'),
                                ('upgrade_d', 'Delta', 'EItemSlotType_Armor', 'EModTier_5')]]
    entries = dynamics_page.item_entries(items, {}, '../')
    # the game's shop order, Weapon / Spirit / Vitality (it read Weapon / Vitality / Spirit; 2026-10-17)
    assert [e[1] for e in entries] == ['Gamma', 'Alpha', 'Beta', 'Delta']
    assert entries[3][5] == {'data-cat': 'v', 'data-tier': '5'}
    bar = dynamics_page.toolbar('item', 0, 'Removed')
    assert 'data-rowf="cat" data-v="w"' in bar and 'data-rowf="tier" data-v="5"' in bar and '>Tier 5</button>' in bar
    hero_bar = dynamics_page.toolbar('hero', 0, 'Pre-release', ('Assassin', 'Brawler'))
    assert 'data-rowf="role" data-v="brawler"' in hero_bar
    heroes = dynamics_page.hero_entries([{'file': 'heroes.vdata', 'id': 'hero_atlas', 'name': 'Abrams',
                                          'state': 'EHeroDevState_Release'}], '../',
                                        {'hero_atlas': {'type': 'ECitadelHeroType_Brawler'}})
    assert heroes[0][5] == {'data-role': 'brawler'}


def test_matrix_merges_empty_runs_but_not_across_the_old_line():
    """2026-10-03: the item matrix had 29k cells, 27k of them empty — a run of empty cells is one cell."""
    from builders.dynamics_page import _gap, stripes
    assert _gap(1, False) == '<td></td>' and _gap(5, True) == '<td class=old colspan=5></td>'
    # a lone tag fills the tile; a tiny share still shows (12% minimum)
    assert stripes({'new': 1}) == 'linear-gradient(var(--tag-new) 0% 100%)'
    assert 'var(--tag-changed)' in stripes({'up': 1, 'buff': 30})


def test_buff_vs_nerf_weighs_the_changes():
    """Review 2026-10-05: "Buff vs nerf" was a majority of rows — one +50% buff lost to two −10% nerfs."""
    from builders.weights import band_score, net_class
    big = {'dir': 'buff', 'pct': 50.0, 'op': 'change'}
    small = {'dir': 'nerf', 'pct': -10.0, 'op': 'change'}
    net, vol = band_score([big, small, small])
    assert net == 1.5 and vol == 3.5 and net_class(net, vol) == 'net-buff'
    assert net_class(*band_score([big, {**big, 'dir': 'nerf'}])) == 'net-mix'
    assert band_score([{'op': 'add', 'dir': None, 'pct': None}]) == (1.0, 1.0)            # a NEW thing


def test_net_mark_is_one_rule_on_bands_cards_and_matrices(monkeypatch):
    """Review 2026-10-05: the change matrices weighed buff vs nerf, a band, a strip tile's card and a home icon said
    nothing (the home icon's underline counted a majority). weights.net_of is the one rule all of them read."""
    from builders import dynamics_page, history_view
    from builders.home_page import _chip, update_feed
    from builders.weights import net_chip, net_of
    big = ch(dir='buff', pct=50.0)
    small = ch(dir='nerf', pct=-10.0)
    assert net_of([big, small, small]) == 'buff'                    # one +50% buff outweighs two −10% nerfs
    assert net_of([small, small]) == 'nerf'
    assert net_of([big, ch(dir='nerf', pct=-50.0)]) == 'mix'
    assert net_of([ch(op='rework'), ch(cat='mechanic', dir='changed', pct=None)]) == ''    # nothing takes a side
    assert net_chip('buff') == '<span class="net-chip net-buff">net buff</span>' and net_chip('') == ''
    # the band's banner: one chip after the counters; none for a band of reworks only
    hdr = {'id': 'p1', 'date': '2026-01-01', 'title': '01-01-2026 Update'}
    summary, _ = history_view._banner('p1', hdr, [big, small, small], '../')
    assert summary.count('net-chip') == 1 and '<span class="net-chip net-buff">net buff</span>' in summary
    assert summary.index('class="tsum"') < summary.index('net-chip') < summary.index('patch ↗')
    assert 'net-chip' not in history_view._banner('p1', hdr, [ch(op='rework')], '../')[0]
    # the strip tile's card carries the band's mark and the words
    data = history_view.strip_data([('p1', hdr, {'buff': 1, 'nerf': 2}, 0, [], net_of([big, small, small]))])
    assert data['t'][0][6] == 'buff' and data['nets']['mix'] == 'mixed'
    # the home icon: its underline by the weighed sum, not by which side has more rows
    ents = [{'key': 'abilities.vdata:a1', 'file': 'abilities.vdata', 'id': 'a1', 'kind': 'ability', 'owner': 'hero_atlas',
             'name': 'Siphon Life', 'changes': [{**big, 'key': 'k1'}, {**small, 'key': 'k2', 'label': 'Radius'},
                                                {**small, 'key': 'k3', 'label': 'Range'}]}]
    s = update_feed({'entities': ents})['heroes']['heroes.vdata:hero_atlas']
    assert s['nerf'] == 2 and s['buff'] == 1
    assert 'class="lu net-buff"' in _chip('heroes.vdata:hero_atlas', s, 'p1', {'heroes.vdata:hero_atlas': 'Abrams'}, k=0)
    # a matrix tile: its class and its card's mark from the same rule (scripts.js never re-weighs)
    rows = [{'id': 'p1', 'date': '2026-09-29', 'title': '09-29-2026 Update'}]
    monkeypatch.setattr(dynamics_page, '_collect', lambda: {
        'rows': rows, 'cells': {'item:x': {'p1': {'buff': 1, 'nerf': 2}}}, 'parts': {}, 'samples': {}, 'hidden': {},
        'nets': {'item:x': {'p1': net_of([big, small, small])}}})
    html = dynamics_page.matrix_html([('item:x', 'X', None, 'x.html', '')], 'item')
    assert 'class="dsq net-buff"' in html and '"nets":{' in html and ',"buff"]]' in html


def test_band_chip_and_matrix_cell_weigh_the_same_rows(monkeypatch):
    """Review 2026-10-05: 44 hero cells and 1 item cell had a matrix tile of one side and a band chip of another (or
    none) — the cell weighed work on abilities still in development (Nano 2024-09-26: band "net nerf", tile buff)
    and missed an ability removed in the patch (its record names no owner: Holliday 2026-09-29 read 7 DEL on the
    band, 1 in the cell). One rule now (weights.weighed_rows): a rule for all and work before release are out of
    the net in both, a removed ability counts on its hero in both."""
    import re as _re
    from builders import archive, dynamics_page, game_systems, history_view
    rows = {r: {'id': r, 'date': f'2026-0{i}-01', 'title': f'0{i}-01-2026 Update'}
            for i, r in enumerate(('p1', 'p2', 'p3', 'p4'), start=1)}

    def c(ent, n, **kw):
        return ch(**{'key': f'{ent}:{n}', 'path': n, 'label': f'Field {n}', 'status': 'hidden', **kw})
    hero, ab, gone = 'heroes.vdata:hero_x', 'abilities.vdata:ab_x', 'abilities.vdata:ab_gone'
    per = {   # patch -> entity key -> rows
        'p1': {hero: [c(hero, 'a', dir='buff', pct=50.0),                      # +2.5
                      c(hero, 'b', dir='nerf', pct=-60.0, shared_all=True, shared_what='heroes')],   # rule for all
               ab: [c(ab, 'a', pct=-10.0), c(ab, 'b', pct=-10.0)]},             # -0.5 -0.5
        'p2': {hero: [c(hero, 'c', pct=-10.0, status='documented')],             # -0.5 released
               ab: [c(ab, n, dir='buff', pct=20.0, status='unreleased') for n in 'cde']},   # work before release
        'p3': {hero: [c(hero, 'd', dir='buff', pct=5.0)],
               gone: [c(gone, n, op='remove', dir=None, pct=None) for n in 'ab']},   # removed: -1 -1
        'p4': {ab: [c(ab, 'f', cat='mechanic', dir='changed', pct=None)]},        # no side
    }
    want = {'p1': 'buff', 'p2': 'nerf', 'p3': 'nerf', 'p4': ''}
    # the band: the hero page's history
    by_ent = {}
    for pid, ents in per.items():
        for key, cs in ents.items():
            by_ent.setdefault(key, []).append((rows[pid], cs))
    keys = [(hero, 'Base stats', None), (ab, 'Ability X', None), (gone, 'Gone Ability', None)]
    html = history_view.history_table(keys, ['X'], by_ent, {}, '../')
    band = {}
    for m in _re.finditer(r'<details class="pblock[^"]*" id="p-(\w+)"[^>]*>\s*<summary.*?</summary>', html, _re.S):
        got = _re.search(r'net-chip net-(\w+)', m.group(0))
        band[m.group(1)] = got.group(1) if got else ''
    # the matrix: the same patches as the archive gives them (a removed ability's record has no owner, no kind)
    cat = [{'file': 'heroes.vdata', 'id': 'hero_x', 'kind': 'hero', 'name': 'X'},
           {'file': 'abilities.vdata', 'id': 'ab_x', 'kind': 'ability', 'owner': 'hero_x', 'name': 'Ability X'},
           {'file': 'abilities.vdata', 'id': 'ab_gone', 'kind': 'ability', 'owner': 'hero_x', 'name': 'Gone Ability'}]

    def record(key, cs):
        file, _, eid = key.partition(':')
        info = {'key': key, 'file': file, 'id': eid, 'changes': cs}
        if eid == 'ab_gone':                     # removed in this patch: its record names no owner, no kind
            return info
        known = next(e for e in cat if e['id'] == eid)
        return {**info, 'kind': known['kind'], **({'owner': known['owner']} if 'owner' in known else {})}
    monkeypatch.setattr(archive, 'by_date', lambda: list(rows.values()))
    monkeypatch.setattr(archive, 'patch', lambda pid: {'id': pid, 'extras': {}})
    monkeypatch.setattr(archive, 'gameplay', lambda pid: [record(k, cs) for k, cs in per[pid].items()])
    monkeypatch.setattr(dynamics_page, 'load_json', lambda name: {'entities': cat, 'abilities': {}, 'heroes': []})
    monkeypatch.setattr(game_systems, 'convar_start', lambda: None)
    dynamics_page._collect.cache_clear()
    try:
        nets = dynamics_page._collect()['nets']['hero:hero_x']
        mx = dynamics_page.matrix_html([('hero:hero_x', 'X', None, 'x.html', '')], 'hero')
    finally:
        dynamics_page._collect.cache_clear()
    tiles = {pid: mark for mark, pid in _re.findall(r'class="dsq net-(\w+)[^"]*"[^>]*href="x\.html#p-(\w+)"', mx)}
    assert band == want and nets == want
    assert tiles == {p: m or 'mix' for p, m in want.items()}            # '' (no side) is the matrix's mix colour


def test_matrix_cell_drops_the_repeats_the_page_drops_and_reads_an_entity_as_one_list(monkeypatch):
    """2026-10-06, the last 5 of 4,476 cells: the hero page says an alt fire's row its gun repeats once (Shiv
    2025-05-08: band 1 DEL, cell 2) and a sub-ability's row its parent repeats once (Tengu 2024-06-06: 1 NEW, 3);
    an item's own and shared records are one list, so a shared Corrupted bonus folds into its Corrupted version
    (Veil Walker 2026-09-29: band 1 NEW, cell 2). The cell now counts what the band counts."""
    from builders import archive, dynamics_page, game_systems
    row = {'id': 'p1', 'date': '2026-01-01', 'title': '01-01-2026 Update'}
    gun, alt = 'citadel_weapon_x_set', 'citadel_weapon_x_alt'
    cat = [{'file': 'heroes.vdata', 'id': 'hero_x', 'kind': 'hero', 'name': 'X'},
           {'file': 'abilities.vdata', 'id': gun, 'kind': 'weapon', 'owner': 'hero_x', 'name': 'Gun'},
           {'file': 'abilities.vdata', 'id': alt, 'kind': 'weapon', 'owner': 'hero_x', 'name': alt},
           {'file': 'abilities.vdata', 'id': 'upgrade_y', 'kind': 'item', 'name': 'Y'}]
    cards = {gun: {'id': gun, 'owner': 'hero_x', 'slot': 'Weapon_Primary', 'name': 'Gun'}}
    spread = ch(label='Spread', path='m_flSpread', old_s='3', new_s='1.5', dir='buff', pct=-50.0)
    cor = 'm_CorruptedItemInfo.m_Upgrade.m_vecPropertyUpgrades{%s}.m_strBonus'
    own_cor = [ch(key=f'abilities.vdata:upgrade_y:{p}', label=f'Corrupted: {p}', path=cor % p, op='add', old_s=None,
                  new_s='+5', dir=None, pct=None, status='described') for p in ('Cooldown', 'Range')]
    shared_cor = [ch(key='abilities.vdata:upgrade_y:Health', label='Corrupted: Bonus Health', path=cor % 'Health',
                     op='add', old_s=None, new_s='+10', dir=None, pct=None, status='described', shared=True)]
    records = [{'key': f'abilities.vdata:{gun}', 'file': 'abilities.vdata', 'id': gun, 'kind': 'weapon',
                'owner': 'hero_x', 'changes': [dict(spread)]},
               {'key': f'abilities.vdata:{alt}', 'file': 'abilities.vdata', 'id': alt, 'kind': 'weapon',
                'owner': 'hero_x', 'changes': [dict(spread)]},                     # the gun's row again
               {'key': 'abilities.vdata:upgrade_y', 'file': 'abilities.vdata', 'id': 'upgrade_y', 'kind': 'item',
                'changes': own_cor},
               {'key': 'abilities.vdata:upgrade_y', 'file': 'abilities.vdata', 'id': 'upgrade_y', 'kind': 'item',
                'changes': shared_cor}]                                            # a shared block's record
    data = {'entities.json': {'entities': cat}, 'abilities.json': {'abilities': cards},
            'tables/heroes.json': {'heroes': []}}
    monkeypatch.setattr(archive, 'by_date', lambda: [row])
    monkeypatch.setattr(archive, 'patch', lambda pid: {'id': pid, 'extras': {}})
    monkeypatch.setattr(archive, 'gameplay', lambda pid: records)
    monkeypatch.setattr(dynamics_page, 'load_json', lambda name: data[name])
    monkeypatch.setattr(game_systems, 'convar_start', lambda: None)
    dynamics_page._collect.cache_clear()
    try:
        cells = dynamics_page._collect()['cells']
    finally:
        dynamics_page._collect.cache_clear()
    assert cells['hero:hero_x']['p1'] == {'buff': 1}                   # the alt fire's repeat is said once
    assert sum(cells['item:upgrade_y']['p1'].values()) == 1             # one Corrupted version, not 2
