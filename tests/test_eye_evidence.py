"""The eye says where a change the patch notes left out came from, and it is on every place that shows changes
(review 2026-10-06: the hidden-story and player-eye critics, #17.4 and #44).

- A row's eye names the build(s) whose files carry the change and opens that build's page in the archive at the
  entity (builders/evidence.py); a band's banner eye does the same for the band; the build page links the tracker's
  commit on GitHub.
- The eye on an ability card's trail squares, in a value's history steps (Hero / Unit / Item Stats, the hero page's
  tiles, Game rules: builders/stat_eyes.py) and on the Game index cards."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BUILDS = [{'build': 6440, 'date': '2026-04-10T20:00:00Z', 'file': '6440_x.json.gz'},
          {'build': 6444, 'date': '2026-04-11T09:00:00Z', 'file': '6444_ed400792.json.gz'}]


def ch(**kw):
    base = {'op': 'change', 'cat': 'balance', 'label': 'Cooldown', 'old_s': '27', 'new_s': '29', 'dir': 'nerf',
            'pct': 7.4, 'grad': 2, 'status': 'hidden', 'path': 'x', 'builds': [6440],
            'key': 'heroes.vdata:hero_haze:x', 'file': 'heroes.vdata', 'id': 'hero_haze'}
    base.update(kw)
    return base


def test_the_eye_names_the_build_and_opens_it(monkeypatch):
    from builders import common, evidence
    monkeypatch.setattr(common, 'build_pages', lambda: {'6440_x.json.gz': '6440', '6444_ed400792.json.gz': '6444'})
    monkeypatch.setattr(evidence, 'build_pages', common.build_pages)
    monkeypatch.setattr(evidence, 'build_anchors', lambda f: frozenset({'hero_haze'}) if f.startswith('6444') else frozenset())
    assert evidence.row_evidence(ch()) == (None, None, False)          # outside a patch: the eye's own words
    with evidence.patch_builds(BUILDS, '../'):
        tip, href, late = evidence.row_evidence(ch())
        assert tip.startswith('Not in the patch notes — in the game files of build 6440 (2026-04-10)')
        assert href == '../builds/6440.html' and not late             # the build page has no card of hers: no anchor
        # a silent hotfix: a later build than the patch's own, at the hero's card of that build
        tip, href, late = evidence.row_evidence(ch(builds=[6444]))
        assert 'shipped silently 2026-04-11, build 6444' in tip and href == '../builds/6444.html#c-hero_haze' and late
        # several builds; an update without notes says so
        tip, _, _ = evidence.row_evidence(ch(builds=[6444, 6440], status='unannounced'))
        assert tip.startswith('Update shipped without patch notes — in the game files of builds 6440 (2026-04-10) '
                              'and 6444 (2026-04-11)')
        assert evidence.row_evidence(ch(status='documented')) == (None, None, False)
        # a shared edit is one block in the build, no card per target: the page itself
        assert evidence.row_evidence(ch(builds=[6444], shared_n=6))[1] == '../builds/6444.html'
        tip, href = evidence.band_evidence([ch(), ch(builds=[6444]), ch(status='documented', builds=[6444])], 'hero_haze')
        assert 'builds 6440 (2026-04-10) and 6444 (2026-04-11)' in tip and href == '../builds/6440.html'


def test_an_ability_row_lands_on_its_heros_card_and_a_folded_row_keeps_its_builds(monkeypatch):
    from builders import evidence, shared_rows
    from builders.render import fold_tier_swaps
    monkeypatch.setattr(shared_rows, 'catalog', lambda: {'abilities.vdata:dagger': {'owner': 'hero_haze'}})
    monkeypatch.setattr(evidence, 'build_pages', lambda: {'6444_ed400792.json.gz': '6444'})
    monkeypatch.setattr(evidence, 'build_anchors', lambda f: frozenset({'hero_haze'}))
    ab = dict(key='abilities.vdata:dagger:x', file='abilities.vdata', id='dagger', builds=[6444])
    with evidence.patch_builds(BUILDS, '../'):
        assert evidence.row_evidence(ch(**ab))[1] == '../builds/6444.html#c-hero_haze'
        # a replaced tier is one REWORK row folded from its bonuses: the builds and the entity ride along
        swap = fold_tier_swaps([ch(**{**ab, 'key': 'abilities.vdata:dagger:t2a'}, op='add', label='T2: Range'),
                                ch(**{**ab, 'key': 'abilities.vdata:dagger:t2b'}, op='remove', label='T2: Cooldown')])
        assert swap[0]['op'] == 'rework' and swap[0]['builds'] == [6444]
        assert {k: swap[0].get(k) for k in ('file', 'id', 'key')} == {'file': None, 'id': None, 'key': None}
        assert evidence.row_evidence(swap[0])[1] == '../builds/6444.html#c-hero_haze'


def test_the_eye_is_a_link_and_only_a_silent_hotfix_keeps_it_in_an_all_hidden_band():
    from builders.cards import row
    from builders.common import mark
    words = 'Not in the patch notes — in the game files of build 6440'
    # the words once, as the link's name (the tooltip reads them there); a row's eye is out of the tab order — the
    # band's banner eye is the keyboard's way to the proof (review 2026-10-06: up to ~800 eyes on a hero page)
    assert mark('hidden', words, '../builds/6440.html') == (f'<a class="mark hidden" href="../builds/6440.html" '
                                                            f'data-tooltip aria-label="{words}"></a>')
    assert ' tabindex="-1" ' in mark('hidden', words, '../builds/6440.html', focusable=False)
    assert ' tabindex="-1" ' in row('hidden', '', 'x', tip=words, href='../builds/6440.html', late=False)
    assert ' late' not in row('hidden', '', 'x', tip='… build 6440', href='../builds/6440.html', late=False)
    assert 'is-hidden late' in row('hidden', '', 'x', tip='… shipped silently', href='../builds/6444.html', late=True)
    css = (ROOT / 'site' / 'styles.css').read_text(encoding='utf-8')
    assert 'a.mark.hidden:hover, a.mark.hidden:focus-visible { color: var(--text-bright); }' in css


def test_a_bands_banner_eye_opens_the_build(monkeypatch):
    from builders import archive, evidence
    from builders.history_view import history_table
    monkeypatch.setattr(archive, 'builds_of', lambda pid: BUILDS)
    monkeypatch.setattr(evidence, 'build_pages', lambda: {'6440_x.json.gz': '6440'})
    monkeypatch.setattr(evidence, 'build_anchors', lambda f: frozenset({'hero_haze'}))
    r1 = {'id': 'p1', 'date': '2026-04-10', 'title': '04-10-2026 Update'}
    key = 'heroes.vdata:hero_haze'
    html = history_table([(key, 'Haze', None)], ['Haze'], {key: [(r1, [ch(), ch(label='Range')])]}, {}, '../')
    chip = html.split('class="chip eye-chip">')[1].split('</span></span>')[0]
    assert chip.startswith('<a class="mark hidden" href="../builds/6440.html#c-hero_haze"')
    assert 'in the game files of build 6440 (2026-04-10)' in chip
    # the rows' eyes link too, and none of them is a hotfix: the all-hidden band keeps its one eye
    assert html.count('<a class="mark hidden" href="../builds/6440.html#c-hero_haze"') == 3 and ' late"' not in html


def test_the_build_page_links_the_trackers_commit():
    from builders.builds_pages import build_page, page_entities
    from builders.evidence import commit_url
    assert commit_url(5043, 'abc') == 'https://github.com/Lifeismana/Deadlocked/commit/abc'
    assert commit_url(5044, 'def') == 'https://github.com/SteamTracking/GameTracking-Deadlock/commit/def'
    assert commit_url(None, 'f').startswith('https://github.com/SteamTracking/')
    rec = {'build': 6444, 'commit': 'ed400792aa', 'date': '2026-04-11T09:00:00Z', 'entities': [
        {'file': 'heroes.vdata', 'id': 'hero_haze', 'status': 'changed', 'kind': 'hero', 'name': 'Haze',
         'changes': [{'op': 'change', 'cat': 'balance', 'label': 'Max Health', 'old_s': '740', 'new_s': '730',
                      'path': 'm_mapStartingStats.EMaxHealth'},
                     {'op': 'change', 'cat': 'visual', 'label': 'Model', 'old_s': 'a', 'new_s': 'b', 'path': 'm_m'}]},
        {'file': 'misc.vdata', 'id': 'crate', 'status': 'removed', 'kind': 'global', 'name': 'Crate', 'changes': []}]}
    html = build_page(rec, None, None, None)
    assert ('<a href="https://github.com/SteamTracking/GameTracking-Deadlock/commit/ed400792aa" rel="noopener">tracker '
            'commit ↗</a>') in html
    assert 'id="c-hero_haze"' in html and 'id="c-crate"' in html
    ents = page_entities(rec)
    assert [[c['label'] for c in e['changes']] for e in ents] == [['Max Health'], ['Removed from game data']]
    assert ents[0]['changes'][0]['status'] == 'raw' and 'status' not in rec['entities'][0]['changes'][0]   # copies


def test_on_a_phone_the_first_tap_shows_the_eyes_words_and_the_second_opens_the_build(browser):
    css = (ROOT / 'site' / 'styles.css').read_text(encoding='utf-8')
    js = (ROOT / 'site' / 'scripts.js').read_text(encoding='utf-8')
    ctx = browser.new_context(viewport={'width': 390, 'height': 800}, is_mobile=True, has_touch=True)
    page = ctx.new_page()
    errors: list[str] = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.set_content(f'<!doctype html><html><head><style>{css}</style></head><body><p style="height:200px">x</p>'
                     '<a class="mark hidden" href="#b6444" data-tooltip="Not in the patch notes — build 6444" '
                     f'aria-label="Not in the patch notes — build 6444"></a><script>{js}</script></body></html>')
    assert page.evaluate("() => matchMedia('(hover: none)').matches")
    page.tap('a.mark')
    assert page.evaluate('() => location.hash') == '' and 'on' in page.locator('.tip').get_attribute('class')
    assert 'build 6444' in page.locator('.tip').text_content()
    # the compatibility mouseout / focusout a touch browser may fire between two taps (CI's Linux Chromium did, and
    # they disarmed the link: the second tap only showed the words again, 2026-10-06) keep the link armed
    page.evaluate("""() => { const a = document.querySelector('a.mark');
      a.dispatchEvent(new MouseEvent('mouseout', {bubbles: true, relatedTarget: document.body}));
      a.dispatchEvent(new FocusEvent('focusout', {bubbles: true})); }""")
    page.tap('a.mark')
    assert page.evaluate('() => location.hash') == '#b6444' and not errors
    ctx.close()


@pytest.mark.skipif(not (ROOT / 'data' / 'builds' / '6444_ed400792.json.gz').exists(), reason='no build record')
def test_a_build_pages_anchors_are_its_cards():
    from builders.evidence import build_anchors
    got = build_anchors('6444_ed400792.json.gz')
    assert 'hero_haze' in got and not any(i.startswith('@') for i in got)
    assert build_anchors('nope.json.gz') == frozenset()


# ---- the eye in a value's history steps -------------------------------------------------------------------------


def _rows(monkeypatch, idx: dict, convars: dict | None = None):
    from builders import stat_eyes
    monkeypatch.setattr(stat_eyes, '_rows_by_build', lambda: idx)
    monkeypatch.setattr(stat_eyes, '_convars_by_build', lambda: convars or {})
    return stat_eyes


def test_a_step_is_hidden_by_its_field_by_its_numbers_or_when_nothing_was_in_the_notes(monkeypatch):
    hp = ch(path='m_mapStartingStats.EMaxHealth', old_s='740', new_s='730')
    regen = ch(path='m_mapStartingStats.EBaseHealthRegen', old_s='2', new_s='3', status='documented')
    gun = ch(path='m_mapWeaponInfos.primary.m_flCycleTime', old_s='0.2', new_s='0.18')
    se = _rows(monkeypatch, {('heroes.vdata:h', 100): (hp, regen), ('abilities.vdata:gun', 100): (gun,)})
    keys = ['heroes.vdata:h', 'abilities.vdata:gun']
    assert se.step_hidden(keys, 100, 'm_mapStartingStats.EMaxHealth')               # the field's own row
    assert not se.step_hidden(keys, 100, 'm_mapStartingStats.EBaseHealthRegen')
    assert se.step_hidden(keys, 100, 'm_WeaponInfo.m_flCycleTime')                  # the leaf: m_WeaponInfo → infos
    # no field (Item Stats): the row that moved the same numbers
    assert not se.step_hidden(keys, 100, None, 2.0, 3.0) and se.step_hidden(keys, 100, None, 740, 730)
    # a computed column (DPS): the eye only when nothing the entities changed in that build was in the notes
    assert not se.step_hidden(keys, 100, None, 55.1, 51.4)
    assert se.step_hidden(['abilities.vdata:gun'], 100, None, 55.1, 51.4)
    # a column with a field but no row of its own in that build: no eye from the build's other rows (review 2026-10-06:
    # 63 Hero Stats steps at a hero's release took one so)
    assert not se.step_hidden(['abilities.vdata:gun'], 100, 'm_WeaponInfo.m_flRange', 9, 10)
    assert not se.step_hidden(keys, 101) and not se.step_hidden(keys, None)


def test_a_rows_hidden_steps_carry_a_sixth_element(monkeypatch):
    se = _rows(monkeypatch, {('heroes.vdata:h', 100): (ch(path='m_x.A', old_s='1', new_s='2'),)},
               {('citadel_x', 100): 'hidden', ('citadel_x', 101): 'documented'})
    row = {'id': 'h', 'history': {'a': [[100, '2026-01-01', 1, 2], [101, '2026-02-01', 2, 3, 'buff']],
                                  'b': [[100, '2026-01-01', 1, 2, 'buff']]}}
    got = se.mark_row(row, ['heroes.vdata:h'], {'a': 'm_x.A', 'b': 'm_x.B'})
    assert got['history']['a'] == [[100, '2026-01-01', 1, 2, None, 1], [101, '2026-02-01', 2, 3, 'buff']]
    assert got['history']['b'] == [[100, '2026-01-01', 1, 2, 'buff', 1]]       # no row of B: the one with its numbers
    assert row['history']['a'][0] == [100, '2026-01-01', 1, 2]                 # a copy
    assert se.mark_convar('citadel_x', [[100, 'd', 1, 2], [101, 'd', 2, 3]]) == [[100, 'd', 1, 2, None, 1],
                                                                                  [101, 'd', 2, 3]]


def test_the_history_tip_draws_the_eye_on_a_hidden_step(browser):
    from test_perf_browser import _open
    hist = json.dumps([[1, '2026-01-01', 10, 12, None, 1], [2, '2026-02-01', 12, 14]])
    page, errors = _open(browser, f'<span class="has-hist" data-pol="1" data-digits="0" data-title="T" '
                                  f"data-hist='{hist}'>x</span>")
    page.hover('.has-hist')
    eyes = page.evaluate("() => [...document.querySelectorAll('.hist-tip li .p')].map(p => !!p.querySelector('.mark.hidden'))")
    assert eyes == [False, True] and not errors                             # newest first
    assert page.locator('.hist-tip .mark.hidden').get_attribute('aria-label') == 'not in patch notes'


# ---- the eye on the trail squares and the Game index cards -----------------------------------------------------


def test_the_trail_square_eye_is_drawn_one_to_one():
    from builders.pixel_icons import EYE_SMALL, eye_small_mask
    css = (ROOT / 'site' / 'styles.css').read_text(encoding='utf-8')
    assert all(len(r) == 10 for r in EYE_SMALL) and len(EYE_SMALL) == 10
    assert f'--mask-eye-sm: {eye_small_mask()};' in css
    assert re.search(r'\.trail \.sq\.hid::after \{[^}]*background: var\(--eye\)[^}]*--mask-eye-sm', css)


def test_a_game_card_says_how_many_changes_the_notes_left_out(monkeypatch):
    from builders import game_pages
    row = {'id': 'p1', 'date': '2026-01-01'}
    hist = {'misc.vdata:x': [(row, [ch(label='A'), ch(label='B', status='documented'), ch(label='C')])],
            'misc.vdata:y': [(row, [ch(label='A')])]}          # one edit over two entries counts once
    assert game_pages._stats(hist, ['misc.vdata:x', 'misc.vdata:y']) == (3, '2026-01-01', 2)
    html = game_pages.index_page({'souls': {'p': [('misc.vdata:x', 'X', ''), ('misc.vdata:y', 'Y', '')]}}, hist)
    card = html.split('class="card px-frame game-card"')[1].split('</a>')[0]
    assert '3 changes' in card and '<span class="gc-hid"><span class="mark hidden"></span>2 not in notes</span>' in card
