"""Hero / item / unit pages (owner 2026-10-04): one centred column, nothing folded, hover cards that say what a
patch changed, tags that look finished, a toolbar whose filters open what they match."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def ch(**kw):
    base = {'op': 'change', 'cat': 'balance', 'label': 'Cooldown', 'old_s': '27', 'new_s': '29',
            'dir': 'nerf', 'pct': 7.4, 'grad': 2, 'status': 'hidden', 'path': 'x'}
    base.update(kw)
    return base


def _blob(html: str) -> dict:
    m = re.search(r'<script type="application/json" class="strip-data">(.*?)</script>', html)
    assert m, 'the page carries its hover-card data'
    return json.loads(m.group(1).replace('<\\/', '</'))


def _history():
    """Abrams-like: three patches, the newest one touching three parts with mixed tags."""
    r1 = {'id': 'p1', 'date': '2026-01-01', 'title': '01-01-2026 Update'}
    r2 = {'id': 'p2', 'date': '2026-02-01', 'title': 'Big One · 02-01-2026'}
    r3 = {'id': 'p3', 'date': '2026-03-01', 'title': '03-01-2026 Update'}
    keys = [('heroes.vdata:hero_atlas', 'Base stats', '../icons/heroes/hero_atlas.webp'),
            ('abilities.vdata:ab_charge', 'Shoulder Charge', '../icons/abilities/charge.webp'),
            ('abilities.vdata:ab_ult', 'Seismic Impact', None)]
    by_ent = {
        'heroes.vdata:hero_atlas': [(r3, [ch(key='heroes.vdata:hero_atlas:hp', label='Health per boon', old_s='52',
                                             new_s='49', pct=-5.8, status='documented')]),
                                    (r1, [ch(key='heroes.vdata:hero_atlas:st', label='Stamina', dir='buff', pct=50.0)])],
        'abilities.vdata:ab_charge': [(r3, [ch(key='abilities.vdata:ab_charge:a', label='T1: Move Speed', old_s='40%',
                                               new_s='32%', pct=-20.0),
                                            ch(key='abilities.vdata:ab_charge:b', label='Radius', old_s='3m', new_s='2m',
                                               pct=-33.3, status='documented'),
                                            ch(key='abilities.vdata:ab_charge:c', label='Damage', old_s='50', new_s='55',
                                               dir='buff', pct=10.0)]),
                                      (r2, [ch(key='abilities.vdata:ab_charge:d', label='Range', dir='buff', pct=5.0)])],
        'abilities.vdata:ab_ult': [(r3, [ch(key='abilities.vdata:ab_ult:a', label='Cooldown', old_s='185s', new_s='215s',
                                            pct=16.2)])],
    }
    areas = {'heroes.vdata:hero_atlas': 'stats', 'abilities.vdata:ab_charge': 'abil', 'abilities.vdata:ab_ult': 'abil'}
    return keys, by_ent, areas


def test_strip_tiles_carry_a_card_of_what_the_patch_changed():
    """Owner complaint 1: a tile said '2026-09-16 update: 3 changes'. Now one JSON blob per page feeds a card:
    the patch, counts by tag, how much was not in the notes, the biggest changes grouped by ability."""
    from builders.history_view import TILE_SAMPLES, history_table
    keys, by_ent, areas = _history()
    html = history_table(keys, ['Abrams'], by_ent, {}, '../', areas=areas,
                         ults=frozenset({'abilities.vdata:ab_ult'}))
    strip = html.split('class="patch-strip"')[1].split('</div>')[0]
    assert 'data-tooltip' not in strip                     # no text tooltip stacked on the card
    assert strip.count('data-k=') == 3 and 'aria-label="2026-03-01 update: 5 changes, 3 not in patch notes"' in strip
    d = _blob(html)
    assert [t[0] for t in d['t']] == ['p3', 'p2', 'p1'] and d['t'][1][2] is True       # strip order; a named patch
    pid, title, named, counts, hidden, groups = d['t'][0]
    assert counts == {'nerf': 4, 'buff': 1} and hidden == 3
    # every group's counts add up to the tile; groups name their ability, carry its icon and ultimate flag
    total = {}
    for g in groups:
        for t, n in g[1].items():
            total[t] = total.get(t, 0) + n
    assert total == counts
    refs = {d['g'][g[0]][0]: d['g'][g[0]] for g in groups}
    assert set(refs) == {'Base stats', 'Shoulder Charge', 'Seismic Impact'}
    assert refs['Seismic Impact'][3] == 1 and refs['Shoulder Charge'][2] == 'ab_charge'
    # the biggest changes first: ranks run over the whole patch, the card shows rank < top
    samples = [s for g in groups for s in g[3]]
    assert sorted(s[5] for s in samples) == list(range(len(samples)))
    top = min(sum(counts.values()), TILE_SAMPLES)
    assert sum(1 for s in samples if s[5] < d['top']) == top
    biggest = min(samples, key=lambda s: s[5])
    assert biggest[:5] == ['Radius', '3m', '2m', 'nerf', 0]
    move = next(s for s in samples if s[0] == 'T1: Move Speed')
    assert move[1:5] == ['40%', '32%', 'nerf', 1]           # old, new as the row prints them; hidden
    assert d['icons'].keys() >= {'buff', 'nerf'} and 'svg' in d['eye']


def test_one_patch_still_feeds_the_trail_cards():
    """No strip for a one-patch history, but the ability cards' trail squares still read the data."""
    from builders.history_view import history_table
    keys, by_ent, areas = _history()
    one = {k: v[:1] for k, v in by_ent.items() if k == 'abilities.vdata:ab_ult'}
    html = history_table(keys, ['Abrams'], one, {}, '../', areas=areas)
    assert 'class="patch-strip"' not in html and _blob(html)['t'][0][0] == 'p3'


def test_band_title_stays_on_the_page_and_groups_have_a_plate():
    """Clicking a band's date left for the patch archive; ability icons were 28px bare glyphs."""
    from builders.history_view import history_table
    keys, by_ent, areas = _history()
    html = history_table(keys, ['Abrams'], by_ent, {}, '../', areas=areas,
                         ults=frozenset({'abilities.vdata:ab_ult'}))
    band = html.split('id="p-p3"')[1].split('</summary>')[0]
    assert '<span class="bt"><span class="pdate solo">' in band       # plain text: a click opens the band
    assert 'class="pnotes" href="../patches/p3.html"' in band          # the archive on purpose
    assert '<span class="ec-n">3 not in notes</span>' in band          # the eye count scripts.js recounts
    assert html.count('class="hgroup has-ic') >= 3 and '<div class="hg-b">' in html
    # the gold corner marks the ultimate; no tooltip beside its written name (AGENTS.md, review 2026-10-04)
    assert '<span class="ab-ic ult"><' in html and 'data-tooltip="Ultimate"' not in html
    # the plate is smooth: no pixelated "px" class on the game's 128px art
    assert '<img class="si2" src="../icons/abilities/charge.webp"' in html


def test_toolbar_tags_are_aria_pressed_buttons_of_the_one_badge():
    """Frontend audit: a chosen NERF turned green — the state "on" is also the ON tag's colour."""
    from builders.history_view import history_table
    keys, by_ent, areas = _history()
    html = history_table(keys, ['Abrams'], by_ent, {}, '../', areas=areas,
                         ults=frozenset({'abilities.vdata:ab_ult'}))
    bar = html.split('class="toolbar hist-bar"')[1]
    assert '<button class="tag nerf" data-f-tag="nerf" aria-pressed="false">NERF</button>' in bar
    assert 'class="hf-ab ult txt"' in bar and 'data-tooltip="Seismic Impact"' in bar   # no art: its name
    js = (ROOT / 'site' / 'scripts.js').read_text(encoding='utf-8')
    hist = js.split("safe('hist-filter'")[1].split("safe('patch-anchor'")[0]
    assert "btn.classList.toggle('on', i < 0)" not in js
    assert "setAttribute('aria-pressed', i < 0 ? 'true' : 'false')" in hist
    # every filter (the eye too) opens what it matches and the counters follow it
    assert 'state.ab || onlyHidden' in hist and "b.classList.contains('has-hidden')" in hist and 'recount(b' in hist
    # every toggle says its state from the start, and a reset by a strip tile clears it (the eye kept "true")
    for cls in ('hf-hidden', 'hf-gone-btn', 'hf-dev'):
        assert re.search(rf'<button class="px-btn {cls}"[^>]* aria-pressed="false">', _toolbar_with_all()), cls
    assert 'data-f-area="stats" aria-pressed="false"' in _toolbar_with_all()
    reset = hist.split('window.__histReset = function')[1].split('};')[0]
    assert "eye.setAttribute('aria-pressed', 'false')" in reset
    assert "bar.addEventListener('change'" not in hist          # no checkbox left in the bar


def _toolbar_with_all() -> str:
    """A bar with every control: tags, the eye, parts, abilities (one removed), "Before release"."""
    from builders.history_view import toolbar
    facts = {'tags': {'nerf', 'buff'}, 'hidden': 3, 'dev': 2, 'areas': {'stats', 'abil'},
             'abs': {'abilities.vdata:a', 'abilities.vdata:b', 'abilities.vdata:c'}}
    keys = [('heroes.vdata:h', 'Hero', None), ('abilities.vdata:a', 'A', 'a.webp'), ('abilities.vdata:b', 'B', 'b.webp'),
            ('abilities.vdata:c', 'C', 'c.webp')]
    return toolbar(facts, keys, {'heroes.vdata:h': 'stats'}, {'abilities.vdata:c'}, False, '../')


def test_one_tag_badge_everywhere():
    """Nine hand-made badges without the icon and a fill graded by size: one helper, one fill; the icon is
    CSS (a mask per tag, in sync with the pixel art), not ~600 inline SVGs a page."""
    from builders.pixel_icons import TAG_ART, tag_mask
    from builders.render import tag_badge, tag_html
    assert tag_html(ch(grad=9)) == tag_badge('nerf', 'NERF') == '<span class="tag nerf">NERF</span>'
    assert tag_badge('del', 'REMOVED', 'button', ' aria-pressed="false"') == \
        '<button class="tag del" aria-pressed="false">REMOVED</button>'
    for f in ('hero_page.py', 'entities_pages.py', 'notes_view.py', 'patches_pages.py', 'dynamics_page.py', 'cards.py'):
        src = (ROOT / 'builders' / f).read_text(encoding='utf-8')
        assert not re.search(r'<(span|button) class="tag [a-z{]', src), f
    css = (ROOT / 'site' / 'styles.css').read_text(encoding='utf-8')
    for t in TAG_ART:
        assert f'.tag.{t} {{ --ti-content: ""; --ti: {tag_mask(t)}; }}' in css, t


def test_vals_text_reads_like_the_row():
    from builders.render import vals_text
    assert vals_text(ch(old_s='50', new_s='20m')) == ('50m', '20m')
    assert vals_text(ch(op='add', old_s=None, new_s='0.6')) == ('', '0.6')
    assert vals_text(ch(op='remove', old_s='14', new_s=None)) == ('14', '')
    assert vals_text(ch(old_s='8m', new_s='-1')) == ('8m', 'no limit')
    assert vals_text(ch(old_s='A_ONE | A_TWO', new_s='A_ONE')) == ('', '−a two')
    assert vals_text({'op': 'add', 'path': '@add', 'cat': 'balance'}) == ('', '')


def test_trail_squares_open_the_band_on_the_page(monkeypatch):
    """An ability card's squares linked to the patch archive with a one-word tooltip; a buff+nerf patch was
    REWORK purple. On the entity's page they open the band (#p-) and show its card; mixed is striped."""
    from builders import trail
    rows = [{'id': f'p{i}', 'date': f'2026-0{i}-01', 'title': f'0{i}-01-2026 Update'} for i in range(1, 5)]
    hits = {'abilities.vdata:ab_x': {'p2': {'buff': 1, 'nerf': 2}, 'p4': {'nerf': 1}}}
    monkeypatch.setattr(trail, '_index', lambda: (rows, hits))
    trail._positions.cache_clear()
    local = trail.trail_html('abilities.vdata:ab_x', None, '../', local=True)
    assert 'href="#p-p2" data-p="p2" data-ab="ab_x"' in local and 'data-tooltip' not in local
    assert 'aria-label="2026-02-01 update · 1 buff, 2 nerfs"' in local
    assert 'style="background:linear-gradient(' in local                  # striped, not REWORK purple
    archive = trail.trail_html('abilities.vdata:ab_x', 'p4', '../')
    assert 'href="../patches/p4.html"' in archive and 'data-tooltip="2026-04-01 update · 1 nerf"' in archive
    assert ' cur' in archive
    assert trail.last_change('abilities.vdata:ab_x') == (rows[3], 'nerf')
    assert trail.dominant_of({'buff': 1, 'nerf': 1}) == 'rework'            # the shop card's one-colour pip
    trail._positions.cache_clear()


def test_hero_page_is_one_open_column(monkeypatch):
    """Owner 2026-10-04: the weapon, abilities and stats were three folds deep; the history sat left."""
    from builders import hero_page
    monkeypatch.setattr('builders.trail.trail_html', lambda *a, **k: '')
    monkeypatch.setattr('builders.trail.last_counts',
                        lambda key: ({'id': 'p9', 'date': '2026-09-16', 'title': '09-16-2026 Update'}, {'nerf': 1}))
    monkeypatch.setattr(hero_page, '_recent_cutoff', lambda: '2026-01-01')
    cols = [{'key': k, 'label': lbl, 'group': g, 'digits': 2, 'pol': 1} for k, lbl, g in [
        ('dps', 'DPS', 'Damage'), ('bullet_speed', 'Bullet Speed (m/s)', 'Damage'), ('hp', 'Health', 'Vitality'),
        ('stamina_regen', 'Stamina Regen', 'Mobility')]]
    row = {'values': {'dps': 51.4, 'bullet_speed': 610, 'hp': 800, 'stamina_regen': 0.2}, 'history': {}, 'spirit_scaled': []}
    cards = {'ult': {'id': 'ult', 'owner': 'hero_atlas', 'slot': 'Signature_4', 'kind': 'ability', 'name': 'Seismic Impact'},
             'gun': {'id': 'gun', 'owner': 'hero_atlas', 'slot': 'Weapon_Primary', 'kind': 'weapon', 'name': 'Case Closed'}}
    h = {'id': 'hero_atlas', 'file': 'heroes.vdata', 'name': 'Abrams', 'alive': True, 'state': 'EHeroDevState_Release',
         'first': [1, '2024-06-06']}
    html = hero_page.hero_page(h, cards, row, cols, {}, {}, {})
    assert '<main class="page entity">' in html
    assert '<details' not in html.split('class="h2row"')[0]                # nothing folded above the history
    assert '<section class="now-open">' in html and '<div class="wb-cells">' in html and '<h2>Stats</h2>' in html
    assert 'class="ab-ic ult"' in html and 'href="#p-p9" data-p="p9" data-ab="ult"' in html


def test_item_and_unit_values_are_open():
    from builders.history_view import now_fold
    assert now_fold('Current values', '<div></div>').startswith('<details class="now px-frame" open>')
    src = (ROOT / 'builders' / 'entities_pages.py').read_text(encoding='utf-8')
    assert src.count("cls='entity'") == 2


def test_page_class_and_centred_column_css():
    from builders.common import page
    assert '<main class="page entity">' in page('X', '', '../', cls='entity')
    assert '<main class="page wide">' in page('X', '', '../', wide=True)
    css = (ROOT / 'site' / 'styles.css').read_text(encoding='utf-8')
    assert '.page.entity { max-width: calc(var(--entity-w)' in css
    assert 'max-width: 1120px' not in css
    tag = css.split('\n.tag {')[1].split('}')[0]
    assert 'clip-path' not in tag and 'var(--font-ui)' in tag and 'min-width: var(--tag-w)' in tag
    assert 'data-g' not in css.split('/* ---------- 06. Badges')[1].split('.tsum')[0]
    assert 'img.px' not in css.split('/* ---------- 03.')[0]       # the game's art is scaled smooth
    # a row reads as a sentence: values right after the label (max-content), the % at the right edge
    assert '.hblocks .erow { grid-template-columns: 22px var(--tag-w) minmax(0, max-content) minmax(150px, 1fr); }' in css
    assert '.hblocks .erow .vals > .old:first-child:nth-last-child(2) { text-decoration: line-through' in css


def test_home_feed_icons_carry_a_card():
    """Home: "Graves: 17 changes, 17 not in patch notes" -> the icon's card names the biggest changes and the
    ability they belong to; the one-line tooltip goes (no two tooltips at once)."""
    from builders.home_page import CHIP_SAMPLES, _chip, chip_card, update_feed
    ents = [{'key': 'abilities.vdata:a1', 'file': 'abilities.vdata', 'id': 'a1', 'kind': 'ability', 'owner': 'hero_atlas',
             'name': 'Siphon Life', 'changes': [ch(key='abilities.vdata:a1:p', label='Radius', old_s='3m', new_s='2m',
                                                   pct=-33.3),
                                                ch(key='abilities.vdata:a1:q', label='Lifesteal', status='documented',
                                                   pct=-12.5),
                                                ch(key='abilities.vdata:a1:r', label='Range', dir='buff', pct=5.0)]}]
    s = update_feed({'entities': ents})['heroes']['heroes.vdata:hero_atlas']
    counts, hidden, samples = chip_card(s)
    assert counts == {'nerf': 2, 'buff': 1} and hidden == 2 and len(samples) == CHIP_SAMPLES
    assert samples[0] == ['Siphon Life', 'Radius', '3m', '2m', 'nerf', 1]
    chip = _chip('heroes.vdata:hero_atlas', s, 'p1', {'heroes.vdata:hero_atlas': 'Abrams'}, k=7)
    assert 'data-k="7"' in chip and 'data-name="Abrams"' in chip and 'data-tooltip' not in chip
    assert 'aria-label="Abrams: 3 changes, 2 not in patch notes"' in chip


def test_colours_only_in_root_and_no_has():
    """AGENTS.md: every colour is a :root token; :has() is banned on big pages."""
    css = (ROOT / 'site' / 'styles.css').read_text(encoding='utf-8')
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    root_end = css.index('}', css.index(':root {'))
    rest = css[root_end:]
    assert not re.findall(r'#[0-9a-fA-F]{3,8}\b', rest)
    assert not re.findall(r'\brgba?\(', rest)
    assert ':has(' not in css


def _added_unit():
    """A unit added to the game: 2 key fields, ADDED_KEY_LIMIT others (every second one hidden), an ON switch."""
    from builders.cards import ADDED_KEY_LIMIT
    new = {'op': 'add', 'old_s': None, 'pct': None, 'dir': None}
    keys = [ch(**new, key=f'npc_units.vdata:u:{p}', path=p, label=lbl, new_s='500')
            for p, lbl in (('m_iMaxHealth', 'Max Health'), ('m_nCost', 'Cost'))]
    rest = [ch(**new, key=f'npc_units.vdata:u:r{i}', path=f'm_flThing{i}', label=f'Thing {i}', new_s=str(i + 1),
               status='hidden' if i % 2 else 'documented') for i in range(ADDED_KEY_LIMIT)]
    on = ch(**new, cat='availability', key='npc_units.vdata:u:on', path='m_bEnabled', label='Enabled', new_s='true')
    return keys + rest + [on]


def test_a_new_units_head_row_says_what_it_stands_for():
    """Review 2026-10-04: a new unit's band showed "Added to the game" + its key fields, so a filter that kept
    every row recounted NEW 60 where the band said 71. The head row carries tag:changes:hidden of the rest."""
    from builders.cards import entity_rows, player_facing
    from builders.render import tag_of
    changes = _added_unit()
    html = entity_rows(changes)
    head = re.search(r'<div class="erow [^"]*" data-n="([^"]*)">', html)
    assert head and 'Added to the game' in html.split('data-n=')[1].split('</div>')[0]
    behind = {t: (int(n), int(h)) for t, n, h in (e.split(':') for e in head.group(1).split())}
    assert behind == {'new': (12, 6), 'on': (1, 1)}
    # the shown rows plus what the head stands for = what the band's counters count
    shown = html.count('<div class="erow') - 1
    built: dict[str, int] = {}
    for c in player_facing(changes):
        built[tag_of(c)[0]] = built.get(tag_of(c)[0], 0) + 1
    assert shown + sum(n for n, _ in behind.values()) == sum(built.values())
    # a patch's ordinary rows carry no such attribute
    assert 'data-n=' not in entity_rows(changes[:3])
    js = (ROOT / 'site' / 'scripts.js').read_text(encoding='utf-8')
    hist = js.split("safe('hist-filter'")[1].split("safe('patch-anchor'")[0]
    assert "r.getAttribute('data-n')" in hist and 'onlyHidden ? e[2] : e[1]' in hist and 'tagOk(r)' in hist


def test_cards_put_a_new_thing_ahead_of_a_small_number():
    """Review 2026-10-04: Rat King's release card showed two small base-stat NERFs, not his 14 new things. A
    NEW / REWORK / DEL row without a % ranks as 100% in the hover cards (strip, trail, home feed)."""
    from builders.history_view import _rank, tile_card
    from builders.home_page import chip_card
    added = ch(op='add', label='Rat Swarm', old_s=None, new_s='1', pct=None, dir=None, key='a:1')
    small = ch(label='Health', old_s='800', new_s='780', pct=-2.5, key='a:2')
    big = ch(label='Bullet Speed', dir='buff', old_s='100', new_s='250', pct=150.0, key='a:3')
    assert sorted([small, added, big], key=_rank) == [big, added, small]
    samples = tile_card([(('', '', 'x', 0), [small, added])])[0][3]
    assert [s[0] for s in sorted(samples, key=lambda s: s[5])] == ['Rat Swarm', 'Health']
    assert chip_card({'rows': [('', small), ('', added)], 'hidden': 2})[2][0][1] == 'Rat Swarm'


def test_phone_tier_table_matrices_and_item_cards_css():
    """Review 2026-10-04: (1) the open "Current stats" put a 420px tier table on 45 neutral pages at 390px;
    (2) centring every wide table gave the change matrices a 20px sideways scroll at 1700-1920px — the
    stats tables' centring is the item-stats track's `.table-fade.center`; (3) auto-fill left a third of an
    item's "Current values" empty; (4) dead rules (details.more, the bar's switch) went."""
    css = (ROOT / 'site' / 'styles.css').read_text(encoding='utf-8')
    phone = [b for b in css.split('@media (max-width: 700px) {')[1:] if 'table.tier-grid' in b.split('\n}')[0]]
    assert phone and 'table.tier-grid { width: 100%; min-width: 0; }' in phone[0]
    assert '.page.wide .table-fade' not in css
    assert '.ability-grid.item-secs { grid-template-columns: repeat(auto-fit, minmax(330px, 1fr)); }' in css
    assert 'details.more' not in css and '.hist-bar .switch' not in css
    js = (ROOT / 'site' / 'scripts.js').read_text(encoding='utf-8')
    anchor = js.split("safe('patch-anchor'")[1].split("safe('tabs'")[0]
    # a square's group is unhidden on its own: the band can show (another ability's rows) while it is filtered out
    assert 'reveal(group)' in anchor and 'reset(true)' in anchor
