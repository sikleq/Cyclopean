"""Build speed (perf track, 2026-10-05): the patch archive is read once, the counting rule and the value
printer are memoised, unchanged icons are not copied again — without changing a byte of the pages."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_archive_reads_each_patch_once(monkeypatch):
    from builders import archive
    reads: list[str] = []
    data = {'patches/index.json': [{'id': 'p1', 'date': '2026-09-16'}, {'id': 'p0', 'date': '2026-09-01'}],
            'patches/p1.json.gz': {'entities': [{'file': 'heroes.vdata', 'id': 'hero_a', 'changes': [
                {'cat': 'balance', 'op': 'change', 'old_s': '1', 'new_s': '2'},
                {'cat': 'visual', 'op': 'change', 'old_s': 'a', 'new_s': 'b'}]}]}}

    def load(name):
        reads.append(name)
        return data[name]
    monkeypatch.setattr(archive, 'load_json', load)
    archive.clear()
    try:
        assert [r['id'] for r in archive.by_date()] == ['p0', 'p1']
        assert archive.patch('p1') is archive.patch('p1')
        g = archive.gameplay('p1')
        assert [c['cat'] for c in g[0]['changes']] == ['balance']       # gameplay rows only
        assert archive.gameplay('p1') is g
        assert reads.count('patches/p1.json.gz') == 1 and reads.count('patches/index.json') == 1
    finally:
        archive.clear()


def test_player_facing_memo_gives_each_caller_its_own_list():
    from builders.cards import facing_scope, player_facing
    rows = [{'key': 'abilities.vdata:a:x', 'op': 'change', 'cat': 'balance', 'label': 'Cooldown', 'old_s': '27',
             'new_s': '29', 'dir': 'nerf', 'path': 'x', 'status': 'hidden'},
            {'key': 'abilities.vdata:a:y', 'op': 'change', 'cat': 'balance', 'label': 'Range', 'old_s': '5',
             'new_s': '5', 'path': 'y'}]                                  # a no-op: not player-facing
    first = player_facing(rows)
    assert [c['label'] for c in first] == ['Cooldown']
    first.clear()                                                         # a caller's list is its own
    again = player_facing(list(rows))                                     # another list of the same rows
    assert [c['label'] for c in again] == ['Cooldown']
    # equal rows in other dicts are computed on their own (the memo is by identity, never by a guess)
    copy = [dict(c, new_s='30') for c in rows]
    assert player_facing(copy)[0]['new_s'] == '30'
    with facing_scope():                                                  # a build page's own memo
        assert player_facing(rows)[0]['label'] == 'Cooldown'
    assert player_facing(rows)[0] is again[0]


def test_ids_to_names_memo_follows_the_catalog(monkeypatch):
    from builders import common
    monkeypatch.setattr(common, '_catalog_owners', lambda: {})
    a, b = {'ability_blood_bomb': 'Blood Bomb'}, {'ability_blood_bomb': 'Bloodbomb'}
    monkeypatch.setattr(common, 'names_by_id', lambda: a)
    assert common.ids_to_names('ability_blood_bomb, x') == 'Blood Bomb, x'
    monkeypatch.setattr(common, 'names_by_id', lambda: b)
    assert common.ids_to_names('ability_blood_bomb, x') == 'Bloodbomb, x'


def test_marks_counters_and_glyphs_are_css_masks_in_sync():
    """Nano's page carried 650 inline SVGs of 12 shapes (150 KB): status marks, tag counters and category
    glyphs are empty spans now and styles.css draws each shape as a mask — kept in sync with the art here."""
    import re
    from builders.common import GLYPHS, MARK_ART, STATUS_MARK, esc, mark, visual
    from builders.pixel_icons import svg_mask
    from builders.render import pip
    css = (ROOT / 'site' / 'styles.css').read_text(encoding='utf-8')
    rules = {}
    for sel, url in re.findall(r'([^{}\n]+)\{ --mk-on: ""; --mk: ([^;]+); \}', css):
        for s in sel.split(','):
            rules[s.strip()] = url
    eye = re.search(r'--mask-eye: (url\("[^"]+"\));', css).group(1)
    for status, (shape, _) in STATUS_MARK.items():
        url = rules[f'.mark.{status}']
        assert (eye if url == 'var(--mask-eye)' else url) == svg_mask(MARK_ART[shape]), status
        assert mark(status) == f'<span class="mark {status}" data-tooltip="{esc(STATUS_MARK[status][1])}"></span>'
    glyphs = dict(re.findall(r'\.glyph(?:\.g-([a-z]+))? \{ --gl: ([^;]+); \}', css))
    assert glyphs[''] == svg_mask(GLYPHS['rules'], evenodd=True)        # an unknown name draws 'rules'
    for name, d in GLYPHS.items():
        if name != 'rules':
            assert glyphs[name] == svg_mask(d, evenodd=True), name
    assert '<svg' not in mark('hidden') + pip('buff', 3) + visual(None, 'map')


def test_fonts_are_one_stylesheet_that_does_not_block_the_first_paint():
    """Google Fonts held the first paint back (blocking CSS, 150-270 ms; a cold index.html waited ~3 s for its
    DOMContentLoaded, since the script at the end of <body> waits for blocking stylesheets); the shop page
    asked for a second stylesheet. One request, media="print" until scripts.js switches it on."""
    import re
    from builders.common import page
    from builders.game_shop import FONTS as SHOP_FONTS
    html = page('T', '<p>x</p>', '', fonts=SHOP_FONTS)
    links = re.findall(r'<link rel="stylesheet" href="(https://fonts[^"]+)"([^>]*)>', html)
    assert len(links) == 2                                  # the switchable one + its <noscript> copy
    (url, attrs), (url2, attrs2) = links
    assert url == url2 and 'family=Archivo+Narrow' in url and 'family=Jersey+20' in url and 'display=swap' in url
    assert 'media="print"' in attrs and 'data-fonts' in attrs and attrs2 == ''
    assert '<noscript><link rel="stylesheet" href="' + url + '"></noscript>' in html
    assert 'Archivo' not in page('T', '<p>x</p>')
    js = (ROOT / 'site' / 'scripts.js').read_text(encoding='utf-8')
    assert "link[data-fonts]" in js and "l.media = 'all'" in js


def test_sync_tree_copies_only_what_changed(tmp_path):
    import build_site
    src, dst = tmp_path / 'icons', tmp_path / 'dist' / 'icons'
    (src / 'heroes').mkdir(parents=True)
    (src / 'heroes' / 'a.webp').write_bytes(b'aaaa')
    (src / 'b.svg').write_bytes(b'<svg/>')
    assert build_site.sync_tree(src, dst) == 2
    assert (dst / 'heroes' / 'a.webp').read_bytes() == b'aaaa'
    assert build_site.sync_tree(src, dst) == 0                           # nothing new: nothing copied
    (src / 'b.svg').write_bytes(b'<svg></svg>')
    st = (src / 'b.svg').stat()
    os.utime(src / 'b.svg', (st.st_atime, st.st_mtime + 5))
    assert build_site.sync_tree(src, dst) == 1
    assert (dst / 'b.svg').read_bytes() == b'<svg></svg>'
