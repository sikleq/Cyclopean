"""The eye's evidence (visual pass 2026-10-17, round 4: a skeptical player's journey from an eye to its proof).

1. "Shipped silently" only for a build newer than the notes' own build that carries nothing they announced; a build is
   dated by the game build's own date, not by the tracker's UTC commit (Deadman Danny's 10-14 rows said "shipped
   silently 2026-10-15, build 6785" — the build of the notes' own changes, dated Oct 14 by the game).
2. The build page the eye opens: each row its status (the eye), its anchor (the eye lands on the row, lit and open)
   and its source — file › entity › field path, the raw old → new, the file's diff in the tracker commit, "this
   update's notes: no line mentions this".
3. One way to the proof: the band's whole "N not in notes" chip is the link, every row keeps a (dimmed) eye, one icon
   for "not in notes", every eye link in the tab order."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DANNY = ROOT / 'data' / 'builds' / '6785_c9e64807.json.gz'
real_data = pytest.mark.skipif(not DANNY.exists(), reason='no build record')


def ch(**kw):
    base = {'op': 'change', 'cat': 'balance', 'label': 'Cooldown', 'old_s': '27', 'new_s': '29', 'dir': 'nerf',
            'pct': 7.4, 'grad': 2, 'status': 'hidden', 'path': 'x', 'builds': [100],
            'key': 'heroes.vdata:hero_haze:x', 'file': 'heroes.vdata', 'id': 'hero_haze'}
    base.update(kw)
    return base


# ---- 1. the silent hotfix -----------------------------------------------------------------------------------------


@real_data
def test_dannys_10_14_rows_shipped_with_the_notes_own_build():
    from builders import archive, evidence
    assert evidence.game_day('Oct 14 2026 20:01:37') == '2026-10-14' and evidence.game_day(None) == ''
    assert evidence.notes_window('2026-10-14')[0] == 6785          # 6782 (the window's first) carries no row at all
    with evidence.patch_builds(archive.builds_of('2026-10-14'), '../', '2026-10-14'):
        got = [evidence.row_evidence(c) for e in archive.patch('2026-10-14')['entities'] for c in e['changes']
               if e['id'].startswith(('hero_deadpack', 'ability_deadpack')) and c.get('status') == 'hidden']
    assert len(got) == 14
    for tip, href, late in got:
        assert not late and 'shipped silently' not in tip
        assert 'in the game files of build 6785 (2026-10-14)' in tip and href.startswith('../builds/6785.html#')


@real_data
def test_the_notes_own_build_carries_the_most_of_what_they_announced():
    """2026-01-30: 6198 carried 2 of the 140 announced changes a day early; 6211 is the notes' build, and its 112 hidden
    changes shipped with it, not silently after it."""
    from builders import evidence
    main, noted, day = evidence.notes_window('2026-01-30')
    assert main == 6211 and {6198, 6211} <= noted and day == '2026-01-30'


def test_a_silent_hotfix_is_newer_than_the_notes_own_build(monkeypatch):
    from builders import archive, evidence
    monkeypatch.setattr(evidence, 'notes_window', evidence.notes_window.__wrapped__)    # uncached: a fake patch
    rows = ([ch(status='documented', builds=[100])] * 3 + [ch(status='described', builds=[99])]
            + [ch(status='described', builds=[102])])
    monkeypatch.setattr(archive, 'patch', lambda pid: {'date': '2026-03-06', 'entities': [{'changes': rows}]})
    builds = [{'build': b, 'date': f'2026-03-{d}T00:00:00Z'} for b, d in ((99, '05'), (100, '06'), (101, '07'),
                                                                          (102, '08'))]
    with evidence.patch_builds(builds, '../', 'p1'):
        late = {b: evidence.row_evidence(ch(builds=[b]))[2] for b in (99, 100, 101, 102)}
        tip = evidence.row_evidence(ch(builds=[101]))[0]
    # before the notes' build, the notes' build, a build after it, a later build that carries an announced change
    assert late == {99: False, 100: False, 101: True, 102: False}
    assert 'shipped silently 2026-03-07, build 101' in tip


def test_without_an_announced_change_a_hotfix_is_dated_after_the_notes(monkeypatch):
    from builders import archive, evidence
    monkeypatch.setattr(evidence, 'notes_window', evidence.notes_window.__wrapped__)
    monkeypatch.setattr(archive, 'patch', lambda pid: {'date': '2024-06-14', 'entities': [{'changes': [ch()]}]})
    builds = [{'build': b, 'date': d} for b, d in ((4271, '2024-06-13T22:00:00Z'), (4281, '2024-06-14T20:00:00Z'),
                                                   (4291, '2024-06-17T20:00:00Z'))]
    with evidence.patch_builds(builds, '../', 'p1'):
        assert [evidence.row_evidence(ch(builds=[b]))[2] for b in (4271, 4281, 4291)] == [False, False, True]
    with evidence.patch_builds(builds, '../'):                     # no patch named: nothing reads as a hotfix
        assert not evidence.row_evidence(ch(builds=[4291]))[2]


# ---- 2. the build page --------------------------------------------------------------------------------------------


def _build_page(n: int) -> tuple[str, str]:
    from builders import builds_pages
    from builders.common import load_json
    r = next(x for x in load_json('builds/index.json') if x['build'] == n)
    return r['file'], builds_pages.build_page(load_json(f'builds/{r["file"]}'),
                                              builds_pages._patch_of_build().get(r['file']), None, None)


@real_data
def test_the_eye_lands_on_its_row_and_the_row_holds_its_source():
    from builders import archive, evidence
    file, html = _build_page(6785)
    c = next(c for e in archive.patch('2026-10-14')['entities'] for c in e['changes']
             if c['path'] == 'm_flRocketJumpForceWallMultiplier')
    with evidence.patch_builds(archive.builds_of('2026-10-14'), '../', '2026-10-14'):
        href = evidence.row_evidence(c)[1]
    aid = href.split('#')[1]
    assert href == f'../builds/6785.html#{aid}' and aid == evidence.row_anchor(c['key'])
    block = re.search(rf'<details class="src" id="{aid}"><summary>(.*?)</summary>(.*?)</details>', html)
    row, src = block.groups()
    assert '<span class="mark hidden"' in row and 'Rocket Jump Force Wall Multiplier' in row      # its status: the eye
    assert ('<code>abilities.vdata › ability_deadpack_primary_weapon_charge › m_flRocketJumpForceWallMultiplier</code>'
            '<span><code>0.5</code> → <code>0.65</code></span>') in src
    assert '<a class="src-d" href="#df-abilities.vdata">file diff ↗</a>' in src
    assert "This update's notes: no line mentions this" in src
    # the head links each data file's diff in the tracker commit: GitHub's anchor is the sha256 of the file's path
    sha = hashlib.sha256(b'game/citadel/pak01_dir/scripts/abilities.vdata').hexdigest()
    assert (f'<a id="df-abilities.vdata" href="https://github.com/SteamTracking/GameTracking-Deadlock/commit/'
            f'c9e648071661aaaa794507bb304cf52679eb2a10#diff-{sha}" rel="noopener">abilities.vdata ↗</a>') in html
    # a row the notes cover stays quiet; every row of the page has an anchor
    assert html.count('<span class="mark hidden" data-tooltip') == 8 and html.count('<details class="src"') == 37


@real_data
@pytest.mark.parametrize('n', [6785, 6790, 6444, 5554])
def test_the_anchors_the_eye_trusts_are_the_ones_the_page_writes(n):
    """evidence.build_rows (what an entity page's eye may link) == the ids the build page writes."""
    from builders import evidence
    file, html = _build_page(n)
    ids = re.findall(r'<details class="src" id="(r-[0-9a-f]{8})">', html)
    assert len(ids) == len(set(ids)) and set(ids) == evidence.build_rows(file)


def test_a_folded_row_has_no_source_and_a_new_entitys_fields_only_their_key_rows():
    from builders.builds_pages import page_entities, shown_keys
    from builders.cards import change_rows
    from builders.evidence import build_rows_scope
    rec = {'entities': [
        {'file': 'abilities.vdata', 'id': 'dagger', 'status': 'changed', 'changes': [
            {'op': 'remove', 'cat': 'balance', 'label': 'Hit Speed', 'path': 'a.old', 'old': 80, 'old_s': '80'},
            {'op': 'add', 'cat': 'balance', 'label': 'Hit Speed', 'path': 'a.new', 'new': 78, 'new_s': '78'},
            {'op': 'change', 'cat': 'balance', 'label': 'Range', 'path': 'b', 'old': 10, 'new': 12, 'old_s': '10',
             'new_s': '12'}]},
        {'file': 'heroes.vdata', 'id': 'hero_new', 'status': 'added', 'changes': [
            {'op': 'add', 'cat': 'balance', 'label': 'Max Health', 'path': 'm_mapStartingStats.EMaxHealth', 'new': 700,
             'new_s': '700'},
            {'op': 'add', 'cat': 'balance', 'label': 'Level 2: souls needed', 'path': 'm_mapLevelInfo.2', 'new': 5,
             'new_s': '5'}]}]}
    ents = page_entities(rec, {'heroes.vdata:hero_new:@add': 'hidden'})
    assert {c['status'] for c in ents[1]['changes']} == {'hidden'}          # a new entity's fields: its one row's
    with build_rows_scope({}, {}):
        html = ''.join(change_rows(e['changes'], added=e['status'] == 'added') for e in ents)
    # "Hit Speed 80 → 78" is folded from two fields: no source; "Range" has one; a new hero's key row has one, the
    # rest of its fields (under "All fields") none
    assert html.count('<details class="src"') == 2 and 'abilities.vdata › dagger › b' in html
    assert 'hero_new › m_mapStartingStats.EMaxHealth' in html and 'm_mapLevelInfo.2' not in html
    assert len(list(shown_keys(ents))) == 2


def _page_file(tmp_path: Path, html: str) -> Path:
    css = (ROOT / 'site' / 'styles.css').read_text(encoding='utf-8')
    js = (ROOT / 'site' / 'scripts.js').read_text(encoding='utf-8')
    html = re.sub(r'<link rel="stylesheet" href="https://fonts[^>]*>|<noscript>.*?</noscript>', '', html)
    html = re.sub(r'<link rel="stylesheet" href="\.\./styles\.css[^"]*">', lambda m: f'<style>{css}</style>', html)
    html = re.sub(r'<script src="\.\./scripts\.js[^"]*"></script>', lambda m: f'<script>{js}</script>', html)
    p = tmp_path / 'builds' / 'page.html'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html, encoding='utf-8')
    return p


@real_data
@pytest.mark.parametrize('phone', [False, True])
def test_arriving_at_a_row_opens_it_lit_and_clear_of_the_sticky_bars(browser, tmp_path, phone):
    from builders.evidence import row_anchor
    _, html = _build_page(6785)
    aid = row_anchor('abilities.vdata:ability_deadpack_primary_weapon_charge:m_flRocketJumpForceWallMultiplier')
    url = _page_file(tmp_path, html).as_uri() + '#' + aid
    ctx = (browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True) if phone
           else browser.new_context(viewport={'width': 1440, 'height': 900}))
    page = ctx.new_page()
    errors: list[str] = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(url)
    page.wait_for_timeout(200)
    got = page.evaluate(f"""() => {{
        const d = document.getElementById('{aid}'), row = d.querySelector('summary .erow');
        const bars = Math.max(...[...document.querySelectorAll('.top-nav, .toolbar')].map(b => b.getBoundingClientRect().bottom));
        return {{open: d.open, top: row.getBoundingClientRect().top, bars, bg: getComputedStyle(row).backgroundColor,
                 link: d.querySelector('a.src-d').href, head: document.getElementById('df-abilities.vdata').href,
                 wide: document.documentElement.scrollWidth - document.documentElement.clientWidth}}; }}""")
    assert got['open'] and got['top'] >= got['bars'] and got['top'] < 400
    assert got['bg'] not in ('rgba(0, 0, 0, 0)', 'transparent')              # lit: the :target row
    assert got['link'] == got['head'] and got['link'].startswith('https://github.com/')
    assert got['wide'] <= 0 and not errors
    ctx.close()


# ---- 3. one way to the proof ----------------------------------------------------------------------------------------


def test_one_icon_for_not_in_notes():
    from builders.common import STATUS_MARK, mark
    assert STATUS_MARK['unannounced'][0] == STATUS_MARK['hidden'][0] == 'eye'
    css = (ROOT / 'site' / 'styles.css').read_text(encoding='utf-8')
    assert '.mark.unannounced { --mk-on: ""; --mk: var(--mask-eye); }' in css
    assert '.mark.hidden, .mark.unannounced { color: var(--eye);' in css
    assert 'tabindex' not in mark('unannounced', 'w', '../builds/1.html')


def test_an_all_hidden_bands_rows_keep_a_dimmed_eye_that_links():
    from builders.cards import row
    css = (ROOT / 'site' / 'styles.css').read_text(encoding='utf-8')
    assert '.hblocks .pblock.all-hidden .erow:not(.late) .st .mark { opacity: .45; }' in css
    assert 'visibility: hidden' not in re.search(r'\.pblock\.all-hidden \.erow[^{]*\{[^}]*\}', css).group(0)
    html = row('hidden', '', 'x', tip='Not in the patch notes — build 6440', href='../builds/6440.html#r-1', late=False)
    assert '<a class="mark hidden" href="../builds/6440.html#r-1" data-tooltip' in html


CHIP = ('<p style="height:200px">x</p><a class="chip eye-chip" href="#b6444" data-tooltip="Not in the patch notes — '
        'in the game files of build 6444 · click to open that build" aria-label="2 not in notes — words">'
        '<span class="mark hidden" aria-hidden="true"></span><span class="ec-n">2 not in notes</span></a>')


def _chip_page(browser, touch: bool):
    css = (ROOT / 'site' / 'styles.css').read_text(encoding='utf-8')
    js = (ROOT / 'site' / 'scripts.js').read_text(encoding='utf-8')
    ctx = (browser.new_context(viewport={'width': 390, 'height': 800}, is_mobile=True, has_touch=True) if touch
           else browser.new_context(viewport={'width': 1200, 'height': 800}))
    page = ctx.new_page()
    page.set_content(f'<!doctype html><html><head><style>{css}</style></head><body>{CHIP}<script>{js}</script>'
                     '</body></html>')
    return ctx, page


def test_the_bands_chip_words_open_the_build(browser):
    ctx, page = _chip_page(browser, touch=False)
    page.hover('.ec-n')
    assert 'build 6444' in page.locator('.tip').text_content()
    page.click('.ec-n')                                     # its words, not only its 13px eye
    assert page.evaluate('() => location.hash') == '#b6444'
    ctx.close()


def test_on_a_phone_the_chip_shows_its_words_then_opens_the_build(browser):
    ctx, page = _chip_page(browser, touch=True)
    page.tap('.ec-n')
    assert page.evaluate('() => location.hash') == '' and 'tap again to open' in page.locator('.tip').text_content()
    page.tap('.ec-n')
    assert page.evaluate('() => location.hash') == '#b6444'
    ctx.close()


def test_a_bands_chip_is_one_link(monkeypatch):
    from builders.history_view import _eye_chip
    html = _eye_chip('all 2 not in notes', 'Not in the patch notes — build 6440 · click to open that build',
                     '../builds/6440.html#r-1')
    assert html.startswith('<a class="chip eye-chip" href="../builds/6440.html#r-1" data-tooltip="Not in the patch')
    assert html.count('<a ') == 1 and 'aria-label="all 2 not in notes — Not in the patch notes' in html
    assert _eye_chip('1 not in notes', 'w', None).startswith('<span class="chip eye-chip"><span class="mark hidden"')
