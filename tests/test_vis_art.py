"""Art pass of 2026-10-17 (the critics' "strongest unfinished signal": placeholder glyphs instead of game art).

- tools/vtex.py: the textures Source2Viewer-CLI could not read (the art of the heroes released 2026-10-14) decoded
  by the site's own reader; extract_icons.decode_unread hands it only what the CLI left.
- extract_icons.name_placeholder: a hero in development whose every picture is its name in plain letters.
- data/overrides: no stale allow-list entry; every released hero has its art; units and Game systems take the art
  the game draws for the same thing.
- home page: units with no art fold into one '+N' tile; one tile behind every card's art.
"""
from __future__ import annotations

import json
import os
import struct
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))


def _vtex(width: int, height: int, mips: list[bytes], fmt: int = 28, extra: list[tuple[int, bytes]] = (),
          red2: bytes = b'\x1a' * 40) -> bytes:
    """A compiled texture as Valve's compiler lays it out: header, block table (RED2, DATA), the DATA block, the
    mips from the smallest to the largest. `red2` stands for the edit info the CLI cannot parse (value type 26)."""
    entries = b''.join(struct.pack('<III', kind, 0, len(blob)) for kind, blob in extra)
    data = struct.pack('<HH4f', 1, 8, 0, 0, 0, 0) + struct.pack('<HHHBBI', width, height, 1, fmt, len(mips), 0)
    data += struct.pack('<II', 8 if extra else 0, len(extra))       # extra data right after these two fields
    table_at = len(data)
    data += entries
    blobs_at = len(data)
    data += b''.join(blob for _, blob in extra)
    # patch each entry's offset (relative to its own offset field) to its blob
    data = bytearray(data)
    pos = blobs_at
    for i, (kind, blob) in enumerate(extra):
        field = table_at + 12 * i + 4
        struct.pack_into('<I', data, field, pos - field)
        pos += len(blob)
    header_len, table_len = 16, 24
    red2_at = header_len + table_len
    data_at = red2_at + len(red2)
    blocks = struct.pack('<4sII', b'RED2', red2_at - (header_len + 4), len(red2))
    blocks += struct.pack('<4sII', b'DATA', data_at - (header_len + 12 + 4), len(data))
    body = blocks + red2 + bytes(data) + b''.join(reversed(mips))
    return struct.pack('<IHHII', header_len + len(body), 12, 1, 8, 2) + body


def test_vtex_reads_the_full_picture_past_an_edit_info_the_cli_cannot_parse():
    import vtex
    big = bytes([10, 20, 30, 255] * 8)                       # 4 x 2 BGRA: blue 10, green 20, red 30
    small = bytes([1, 2, 3, 255] * 2)                         # 2 x 1
    im = vtex.decode(_vtex(4, 2, [big, small]))
    assert im.size == (4, 2) and im.getpixel((3, 1)) == (30, 20, 10, 255)
    # a picture padded to a power of two comes back at its own size
    padded = vtex.decode(_vtex(4, 2, [big], extra=[(1, struct.pack('<HHH', 0, 3, 2))]))
    assert padded.size == (3, 2)
    with pytest.raises(ValueError):
        vtex.decode(_vtex(4, 2, [big], fmt=13))              # a float format it does not read: said, not guessed


def test_vtex_turns_scaled_ycocg_back_into_colour():
    """A DXT5 picture stored as scaled YCoCg (the compiler's "Image YCoCg Conversion"): this pixel of the game's
    npcs/core picture is (42, 39, 40) in Source2Viewer's own PNG."""
    from PIL import Image
    import vtex
    im = Image.new('RGBA', (1, 1), (132, 125, 24, 40))
    assert vtex._from_ycocg(im).getpixel((0, 0)) == (42, 39, 40, 255)


def test_only_textures_the_cli_left_are_decoded(tmp_path):
    """extract_icons.decode_unread: a texture packed this run with no PNG, or a PNG from an earlier run (sprint
    boots kept their old art), is decoded; one the CLI wrote this run, or one packed by an earlier run, is not."""
    import extract_icons
    raw_c, raw = tmp_path / 'c', tmp_path / 'raw'
    pic = _vtex(2, 1, [bytes([0, 0, 255, 255] * 2)])
    for name in ('new', 'stale', 'read', 'old'):
        (raw_c / f'{name}_psd.vtex_c').parent.mkdir(parents=True, exist_ok=True)
        (raw_c / f'{name}_psd.vtex_c').write_bytes(pic)
    since = time.time() - 5
    raw.mkdir()
    (raw / 'stale_psd.png').write_bytes(b'old')
    os.utime(raw / 'stale_psd.png', (since - 100, since - 100))
    (raw / 'read_psd.png').write_bytes(b'cli')
    os.utime(raw_c / 'old_psd.vtex_c', (since - 100, since - 100))
    done = extract_icons.decode_unread(since, raw_c, raw)
    assert sorted(done) == ['new_psd.vtex_c', 'stale_psd.vtex_c']
    assert (raw / 'read_psd.png').read_bytes() == b'cli' and not (raw / 'old_psd.png').exists()
    from PIL import Image
    assert Image.open(raw / 'new_psd.png').getpixel((0, 0)) == (255, 0, 0, 255)


def test_a_hero_picture_that_is_only_its_name_is_no_art():
    """'DRUID' in white letters sat among the faces of the patch archive (review 2026-10-17)."""
    from PIL import Image, ImageDraw
    from extract_icons import name_placeholder
    word = Image.new('RGBA', (128, 128), (0, 0, 0, 0))
    ImageDraw.Draw(word).text((20, 58), 'DRUID', fill=(255, 255, 255, 255))
    assert name_placeholder(word)
    black = Image.new('RGBA', (128, 128), (0, 0, 0, 0))
    ImageDraw.Draw(black).text((20, 58), 'Gun slinger', fill=(0, 0, 0, 255))
    assert name_placeholder(black)
    face = Image.new('RGBA', (128, 128), (190, 120, 90, 255))           # a portrait fills its frame, in colour
    assert not name_placeholder(face)
    mask = Image.new('RGBA', (128, 128), (0, 0, 0, 0))                  # an ability's white mask is no portrait
    mask.paste((255, 255, 255, 255), (16, 16, 112, 112))
    assert not name_placeholder(mask)
    assert not name_placeholder(Image.new('RGBA', (8, 8), (0, 0, 0, 0)))


def _json(rel: str):
    return json.loads((ROOT / rel).read_text(encoding='utf-8'))


def test_the_missing_icon_allow_list_holds_no_art_the_site_has():
    """The four heroes released 2026-10-14 stayed allow-listed as 'No card art shipped yet (build 6723)' after their
    card art shipped: an entry for art the manifest has is stale."""
    allowed, manifest = _json('data/overrides/missing_icons.json'), _json('icons/manifest.json')
    assert not [k for k in allowed if k in manifest]
    assert all(isinstance(why, str) and why.strip() for why in allowed.values())


def test_every_released_hero_has_its_portraits_and_ability_art():
    """Violet's, Deadman Danny's, Baba's and Solomon's ability cards were site glyphs for days after release: the
    extractor had not been re-run, and the CLI could not read half of the new art."""
    manifest, allowed = _json('icons/manifest.json'), _json('data/overrides/missing_icons.json')
    released = {h['id'] for h in _json('data/tables/heroes.json')['heroes'] if h.get('state') == 'release'}
    assert {'hero_artist', 'hero_baba', 'hero_deadpack', 'hero_chessmaster'} <= released
    for hid in released:
        for sub in ('heroes', 'heroes/card', 'heroes/vertical'):
            assert f'{sub}:{hid}' in manifest or f'{sub}:{hid}' in allowed, (sub, hid)
    bare = [e['id'] for e in _json('data/entities.json')['entities']
            if e['file'] == 'abilities.vdata' and e.get('alive') and e.get('owner') in released
            and str(e.get('ability_slot') or '').startswith('Signature')
            and f'ability:{e["id"]}' not in manifest and f'item:{e["id"]}' not in manifest]
    assert not bare


def test_units_and_game_systems_take_the_art_the_game_draws_for_them():
    from builders.common import entity_icon, icon_manifest
    from builders.game_systems import missing_icons, shown
    man = icon_manifest()
    assert man['unit:citadel_chesspiece_bishop'] == 'units/_class/chessmaster_bishop.webp'     # its minimap mark
    assert man['unit:citadel_chesspiece_queen'] == 'units/_class/chessmaster_queen.webp'
    assert man['unit:citadel_artist_strokeblocker'] == 'units/_class/artist_livingink.webp'    # Living Ink's wall
    assert man['unit:npc_necro_skele'] == 'units/_class/necro_shambler.webp'
    # the Mid-Boss: its mark at full size, not the glowing minimap pip that was a speck on its card
    assert man['unit:npc_super_neutral'] == man['misc:neutral_camp_midboss'] == 'units/_class/map_rejuv.webp'
    assert entity_icon('misc.vdata', 'pickup_artist_drawing_mystic', 'misc', '') == 'icons/game/artist_portrait.webp'
    assert man['ability:ability_deadpack_zip_line'] == 'game/zipline_icon.webp'
    # every Game system shows game art (the shop's dark tab grid and the site's map glyph are gone)
    icons = {s.id: s.icon for s in shown()}
    assert not [sid for sid, ic in icons.items() if ic.startswith('glyph:')]
    assert icons['shop'] == 'game/icon_cart.svg' and icons['other'] == 'game/icon_book.svg'
    assert not missing_icons()
    for ic in icons.values():
        assert (ROOT / 'icons' / ic).exists(), ic


def test_home_folds_units_without_art_into_one_tile():
    from builders.home_page import _fold_tile, fold_bare
    rows = [('', {'dir': 'nerf', 'status': 'unannounced'})]
    got = [('npc_units.vdata:trooper_normal', {'n': 3, 'hidden': 0, 'rows': rows, 'kind': 'unit'}),
           ('npc_units.vdata:neutral_rooftop_pigeon_weak', {'n': 1, 'hidden': 1, 'rows': rows, 'kind': 'unit'}),
           ('npc_units.vdata:citadel_basketball', {'n': 1, 'hidden': 0, 'rows': rows, 'kind': 'unit'})]
    names = {'npc_units.vdata:neutral_rooftop_pigeon_weak': 'Overseer I'}
    drawn, bare = fold_bare(got, names)
    assert [k for k, _ in drawn] == ['npc_units.vdata:trooper_normal']
    assert [k for k, _ in bare] == ['npc_units.vdata:neutral_rooftop_pigeon_weak', 'npc_units.vdata:citadel_basketball']
    tile = _fold_tile(bare, '2026-09-29', names, named=False)
    assert tile.startswith('<a class="lu lu-fold net-nerf" href="patches/2026-09-29.html#changes"')
    assert '<span class="lu-fold-n">+2</span>' in tile and 'glyph' not in tile
    assert 'data-tooltip="2 more units without game art: Overseer I, Basketball"' in tile
    assert 'lu-eye' in tile and 'lu-nm' not in tile
    assert 'lu-nm' in _fold_tile(bare, 'p', names, named=True)


def test_the_built_home_page_draws_no_unit_glyph():
    """The built page (when there is one): no grey unit glyph among the feed's icons."""
    page = ROOT / 'dist' / 'index.html'
    if not page.exists():
        pytest.skip('no dist/ (python build_site.py)')
    html = page.read_text(encoding='utf-8')
    assert 'class="px glyph g-units"' not in html


def test_a_hero_with_no_portrait_shows_the_hero_glyph(monkeypatch):
    """A hero whose only picture was its name has no portrait now: the hero glyph, not an <img src="">."""
    from builders import hero_page
    monkeypatch.setattr('builders.trail.trail_html', lambda *a, **k: '')
    monkeypatch.setattr('builders.trail.last_counts', lambda key: (None, {}))
    monkeypatch.setattr(hero_page, '_recent_cutoff', lambda: '2026-01-01')
    cards = {'s1': {'id': 'ability_druid_sprout', 'owner': 'hero_druid', 'slot': 'Signature_3', 'kind': 'ability',
                    'name': 'ability_druid_sprout'}}
    h = {'id': 'hero_druid', 'file': 'heroes.vdata', 'name': 'Druid', 'alive': True,
         'state': 'EHeroDevState_InDevelopment', 'first': [5747, '2025-08-18']}
    ents = {c['id']: {**c, 'file': 'abilities.vdata'} for c in cards.values()}
    html = hero_page.hero_page(h, cards, None, [], ents, {}, {})
    head = html.split('class="hero-head"')[1].split('<h1>')[0]
    assert '<span class="portrait px-frame glyph g-hero"></span>' in head and '<img' not in head


def test_card_art_sits_on_one_tile_and_the_fold_tile_centres_its_count(browser):
    from test_perf_browser import _open
    page, errors = _open(browser,
                         '<div class="grid units"><a class="card"><img src="data:image/gif;base64,R0lGODlhAQABAAAAACw='
                         '"></a><a class="card"><span class="glyph g-units"></span></a></div>'
                         '<div class="lu-row"><a class="lu lu-fold net-mix" href="#"><span class="lu-fold-n">+13</span>'
                         '</a></div>')
    got = page.evaluate("""() => {
      const bg = s => getComputedStyle(document.querySelector(s)).backgroundColor;
      const n = document.querySelector('.lu-fold-n').getBoundingClientRect();
      const t = document.querySelector('.lu-fold').getBoundingClientRect();
      return [bg('.card img'), bg('.card .glyph'), n.width === t.width, n.height === t.height,
              getComputedStyle(document.querySelector('.lu-fold-n')).alignItems];
    }""")
    assert got[0] == got[1] and got[0] not in ('rgba(0, 0, 0, 0)', 'transparent')
    assert got[2:] == [True, True, 'center']
    assert not errors
