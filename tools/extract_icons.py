"""Extract hero / ability / item / unit / Game section icons from the local Deadlock VPK.

Icons come ONLY from the game files (no CDN, no fan art). Source2Viewer-CLI
decompiles .vtex_c -> PNG and .vsvg_c -> SVG; we then convert PNGs to WebP and
store them under icons/ keyed by *entity id* (stable across renames).

    python tools/extract_icons.py            # extract + convert, report missing
    python tools/extract_icons.py --check    # only report what would be missing

Env overrides: CYCLOPEAN_VRF (Source2Viewer-CLI.exe), CYCLOPEAN_VPK (pak01_dir.vpk).

Gotchas (see docs/data-sources.md):
- `-f` is a case-sensitive path PREFIX starting at the VPK root.
- Never pass --vpk_cache: it writes a manifest file into the game folder.
- `<name>_psd_<hash>.vtex_c` duplicates exist; we always use the unhashed one.
- Ability and mod icons are white masks (the game tints them via CSS).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import cache, tracker  # noqa: E402

# Source2Viewer-CLI: env var, else a copy in vendor/vrf/ (git-ignored), else PATH.
VRF = Path(os.environ.get('CYCLOPEAN_VRF')
           or (ROOT / 'vendor' / 'vrf' / 'Source2Viewer-CLI.exe' if (ROOT / 'vendor' / 'vrf' / 'Source2Viewer-CLI.exe').exists()
               else shutil.which('Source2Viewer-CLI') or 'Source2Viewer-CLI'))
VPK = Path(os.environ.get(
    'CYCLOPEAN_VPK', r'C:\Program Files (x86)\Steam\steamapps\common\Deadlock\game\citadel\pak01_dir.vpk'))
RAW = ROOT / '.cache' / 'vpk_raw'
ICONS = ROOT / 'icons'
MANIFEST = ICONS / 'manifest.json'
ALLOW_MISSING = ROOT / 'data' / 'overrides' / 'missing_icons.json'

PREFIXES = (
    'panorama/images/heroes/guns/',
    'panorama/images/heroes/hero_names/',
    'panorama/images/hud/abilities/',
    'panorama/images/hud/modifiers/',
    'panorama/images/icons/',
    'panorama/images/items/',
    'panorama/images/upgrades/',
    'panorama/images/icons/properties/',
    'panorama/images/hud/core/',
    'panorama/images/hud/icons/',
    'panorama/images/npcs/',
    'panorama/images/minimap/',
    'panorama/images/shop/catalog/',
    # Game systems' art (data/overrides/game_icons.json, game_systems.json): file prefixes, not whole folders
    'panorama/images/hud/brawl/icon_brawl',
    'panorama/images/hud/levelup_',
    'panorama/images/hud/zipline_icon',
    'panorama/images/hud/ledge_climb',
    'panorama/images/hud/teleport_icon',
)
# heroes/ root files are passed as an explicit list: the folder also holds
# heroes/backgrounds/ (~1.7 GB) and -f has no exclude.
HERO_ROOT = 'panorama/images/heroes/'
CMDLINE_CHUNK = 16_000   # Windows command line limit is ~32K chars

_IMG_RE = re.compile(r'^file://\{images\}/(.+)\.(psd|png|tga|jpg|svg)$', re.I)

# (vdata field, output subfolder, max side in px for the stored WebP)
HERO_FIELDS = (
    ('m_strIconImageSmall', 'heroes', 128),
    ('m_strIconHeroCard', 'heroes/card', 280),
    ('m_strMinimapImage', 'heroes/minimap', 64),
    ('m_strTopBarVertical', 'heroes/vertical', 120),
    ('m_strWeaponImage', 'heroes/gun', 300),
)


def raw_path(ref: str) -> Path | None:
    """vdata image reference -> decompiled file under RAW."""
    m = _IMG_RE.match(str(ref).strip())
    if not m:
        return None
    rel, ext = m.group(1), m.group(2).lower()
    if ext == 'svg':
        return RAW / 'panorama' / 'images' / f'{rel}.svg'
    return RAW / 'panorama' / 'images' / f'{rel}_{ext}.png'


def extract_raw() -> None:
    if not VRF.exists():
        raise SystemExit(f'Source2Viewer-CLI not found: {VRF} (set CYCLOPEAN_VRF)')
    if not VPK.exists():
        raise SystemExit(f'VPK not found: {VPK} (set CYCLOPEAN_VPK)')
    RAW.mkdir(parents=True, exist_ok=True)
    _vrf(','.join(PREFIXES))
    listing = tracker.read('HEAD', tracker.ASSET_LIST) or ''
    root_files = [
        line.split(' ', 1)[0] for line in listing.splitlines()
        if line.startswith(HERO_ROOT) and '/' not in line.split(' ', 1)[0][len(HERO_ROOT):]
    ]
    chunk: list[str] = []
    for path in root_files:
        if sum(len(p) + 1 for p in chunk) + len(path) > CMDLINE_CHUNK:
            _vrf(','.join(chunk))
            chunk = []
        chunk.append(path)
    if chunk:
        _vrf(','.join(chunk))


def _vrf(filter_arg: str) -> None:
    cmd = [str(VRF), '-i', str(VPK), '-o', str(RAW), '-d', '-f', filter_arg]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)


TRIM_BELOW = 0.35   # a rule's marker drawn small on an empty canvas (minimap: 20x24 px of 64x64) is cut to its art


def trimmed(im):
    """A marker whose art fills less than TRIM_BELOW of its canvas, cut to the art (+1 px) and centred on a square
    transparent canvas; anything fuller is returned as it is (portraits keep their framing)."""
    from PIL import Image
    box = im.getchannel('A').getbbox()
    if not box or (box[2] - box[0]) * (box[3] - box[1]) >= TRIM_BELOW * im.width * im.height:
        return im
    box = (max(box[0] - 1, 0), max(box[1] - 1, 0), min(box[2] + 1, im.width), min(box[3] + 1, im.height))
    art = im.crop(box)
    side = max(art.size)
    out = Image.new('RGBA', (side, side), (0, 0, 0, 0))
    out.paste(art, ((side - art.width) // 2, (side - art.height) // 2))
    return out


def _to_webp(src: Path, dst: Path, max_side: int, trim: bool = False) -> None:
    from PIL import Image
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return                      # already converted from this raw file
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im = im.convert('RGBA')
        if trim:
            im = trimmed(im)
        if max(im.size) > max_side:
            im.thumbnail((max_side, max_side), Image.LANCZOS)
        im.save(dst, 'WEBP', quality=92, method=4)


RAW_OWNER: dict[str, str] = {}      # decompiled file -> manifest key of the entity that uses it


def _store(ref, out_rel: str, max_side: int, manifest: dict, missing: list, key: str) -> None:
    src = raw_path(ref) if ref else None
    if src is None or not src.exists():
        missing.append({'key': key, 'ref': ref})
        return
    RAW_OWNER.setdefault(str(src), key)
    if src.suffix == '.svg':
        dst = ICONS / f'{out_rel}.svg'
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    else:
        dst = ICONS / f'{out_rel}.webp'
        _to_webp(src, dst, max_side)
    manifest[key] = dst.relative_to(ICONS).as_posix()


def convert(rev: str = 'HEAD') -> tuple[dict, list]:
    heroes = cache.vdata(rev, tracker.SCRIPTS + 'heroes.vdata')
    abilities = cache.vdata(rev, tracker.SCRIPTS + 'abilities.vdata')
    units = cache.vdata(rev, tracker.SCRIPTS + 'npc_units.vdata')
    manifest: dict[str, str] = {}
    missing: list[dict] = []

    for hid, h in heroes.items():
        if not hid.startswith('hero_') or not isinstance(h, dict):
            continue
        for fld, sub, side in HERO_FIELDS:
            if h.get(fld):
                _store(h[fld], f'{sub}/{hid}', side, manifest, missing, f'{sub}:{hid}')

    # heroes shipped without a small icon (new releases have only the vertical
    # portrait): square crop of the portrait's top, which holds the face
    for hid, h in heroes.items():
        if not hid.startswith('hero_') or f'heroes:{hid}' in manifest or not isinstance(h, dict):
            continue
        src = raw_path(h.get('m_strTopBarVertical', ''))
        if src is None or not src.exists():
            continue
        from PIL import Image
        with Image.open(src) as im:
            im = im.convert('RGBA')
            side = im.width
            crop = im.crop((0, 0, side, side))
            crop.thumbnail((128, 128), Image.LANCZOS)
            dst = ICONS / 'heroes' / f'{hid}.webp'
            dst.parent.mkdir(parents=True, exist_ok=True)
            crop.save(dst, 'WEBP', quality=92, method=6)
        manifest[f'heroes:{hid}'] = dst.relative_to(ICONS).as_posix()
        missing[:] = [m for m in missing if m['key'] != f'heroes:{hid}']

    for aid, a in abilities.items():
        if not isinstance(a, dict):
            continue
        if a.get('m_strShopIconLarge'):
            _store(a['m_strShopIconLarge'], f'items/{aid}', 128, manifest, missing, f'item:{aid}')
        if a.get('m_strAbilityImage'):
            _store(a['m_strAbilityImage'], f'abilities/{aid}', 128, manifest, missing, f'ability:{aid}')

    for uid, u in units.items():
        if isinstance(u, dict) and u.get('m_strCustomUnitIcon'):
            _store(u['m_strCustomUnitIcon'], f'units/{uid}', 128, manifest, missing, f'unit:{uid}')

    misc = cache.vdata(rev, tracker.SCRIPTS + 'misc.vdata')
    for mid, m in misc.items():
        if not isinstance(m, dict):
            continue
        # the ping icon names the pickup ('powerup_gun'); the HUD one (nested in the
        # modifier block) is often the generic 'icon_powerup'
        ref = m.get('m_strPingIcon') or _find_field(m, 'm_strHudIcon')
        if ref and 'icon_powerup' not in str(ref):
            _store(ref, f'misc/{mid}', 128, manifest, missing, f'misc:{mid}')

    historical_icons(manifest, missing)
    unit_class_icons(manifest)
    external_icons(manifest, missing)
    missing += [{'key': f'game-art:{rel}', 'ref': rel} for rel in game_icons(manifest)]

    stat_map = json.loads((ROOT / 'data' / 'reference' / 'stat_icons.json').read_text(encoding='utf-8'))
    for group, entries in stat_map.items():
        if not isinstance(entries, dict):
            continue
        for cls, vpk_path in entries.items():
            if not isinstance(vpk_path, str):
                continue
            rel = vpk_path.replace('.vsvg_c', '.svg').replace('.vtex_c', '.png')
            src = RAW / rel
            if not src.exists():
                missing.append({'key': f'{group}:{cls}', 'ref': vpk_path})
                continue
            if src.suffix == '.svg':
                dst = ICONS / 'stats' / group / f'{cls}.svg'
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)
            else:
                dst = ICONS / 'stats' / group / f'{cls}.webp'
                _to_webp(src, dst, 64)
            manifest[f'{group}:{cls}'] = dst.relative_to(ICONS).as_posix()
    return manifest, missing


GENERIC_ICONS = ('weapon_damage', 'base_utility', 'base_weapon', 'base_tech', 'base_armor')
FIELDS_BY_FILE = {
    'heroes.vdata': [(f, f'{sub}:{{id}}', side) for f, sub, side in HERO_FIELDS],
    'abilities.vdata': [('m_strShopIconLarge', 'item:{id}', 128), ('m_strAbilityImage', 'ability:{id}', 128)],
}


def historical_icons(manifest: dict, missing: list) -> None:
    """Entities no longer in the game: use the image path from the last build they
    existed in, if that file is still packed. Skip placeholders: art that belongs
    to another entity today (a hero in development borrowing Nano's icons) or
    generic art (weapon_damage)."""
    ents = json.loads((ROOT / 'data' / 'entities.json').read_text(encoding='utf-8'))['entities']
    commit_of = {b.build: b.commit for b in tracker.builds() if b.build is not None}
    live_owner = dict(RAW_OWNER)        # art of entities in the game today (dead ones may share art)
    by_commit: dict[str, list[dict]] = {}
    for e in ents:
        if e.get('alive') or e['file'] not in FIELDS_BY_FILE or e.get('template'):
            continue
        commit = commit_of.get(e['last'][0])
        if commit:
            by_commit.setdefault(commit, []).append(e)
    for commit, group in by_commit.items():
        data = {f: cache.vdata(commit, tracker.SCRIPTS + f) for f in {e['file'] for e in group}}
        for e in group:
            val = data[e['file']].get(e['id'])
            if not isinstance(val, dict):
                continue
            for field, key_t, side in FIELDS_BY_FILE[e['file']]:
                key = key_t.format(id=e['id'])
                ref = val.get(field)
                if key in manifest or not ref:
                    continue
                src = raw_path(ref)
                if src is None or not src.exists() or any(g in src.stem.lower() for g in GENERIC_ICONS):
                    continue
                # an ability borrowing art that belongs to another entity today is a placeholder
                # (heroes in development used Nano's icons); a removed ITEM whose art went to its
                # reworked successor keeps that art
                if str(src) in live_owner and e.get('kind') != 'item' and not _art_of(e, src):
                    continue
                sub = key.split(':', 1)[0].replace('item', 'items').replace('ability', 'abilities')
                _store(ref, f'{sub}/{e["id"]}', side, manifest, missing, key)


_HERO_ART = re.compile(r'[\\/]hud[\\/]abilities[\\/]([a-z0-9_]+)[\\/]', re.I)


def _art_of(e: dict, src: Path) -> bool:
    """Art in hud/abilities/<hero>/ belongs to that hero's abilities, whoever borrows it today."""
    m = _HERO_ART.search(str(src))
    if not m:
        return False
    code = m.group(1).lower()
    owner = (e.get('owner') or '').removeprefix('hero_')
    return code == owner or e['id'].lower().startswith(code + '_')


def _find_field(node, name: str):
    """First value of `name` anywhere inside a vdata block."""
    if isinstance(node, dict):
        if node.get(name):
            return node[name]
        children = node.values()
    elif isinstance(node, list):
        children = node
    else:
        return None
    for child in children:
        found = _find_field(child, name)
        if found:
            return found
    return None


UNIT_RULES = ROOT / 'data' / 'overrides' / 'unit_icons.json'
GAME_RULES = ROOT / 'data' / 'overrides' / 'game_icons.json'
_TIER_SUFFIX = re.compile(r'_(weak|normal|strong|heavy)$')
_ROMAN = re.compile(r'\s+[IVX]+$')
RULE_ART: dict[str, str] = {}       # a rule's image (path under panorama/images/) -> its file under icons/, stored once


def rule_art(rel: str, sub: str) -> str | None:
    """A rule's image stored once under icons/<sub>/ (the first rule to use it picks the folder): PNG -> WebP, a marker
    lost on an empty canvas cut to its art (`trimmed`), SVG copied. None when the extracted VPK files lack it."""
    if rel in RULE_ART:
        return RULE_ART[rel]
    src = RAW / 'panorama' / 'images' / rel
    if not src.exists():
        return None
    stem = Path(rel).stem.removesuffix('_psd').removesuffix('_png')
    if src.suffix == '.svg':
        dst = ICONS / sub / f'{stem}.svg'
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    else:
        dst = ICONS / sub / f'{stem}.webp'
        _to_webp(src, dst, 128, trim=True)
    RULE_ART[rel] = dst.relative_to(ICONS).as_posix()
    return RULE_ART[rel]


def unit_class_icons(manifest: dict) -> None:
    """Units without their own icon, every id the site has seen (removed ones too):
    1. the class portrait the game's ping wheel uses, or a summon's ability art (data/overrides/unit_icons.json);
    2. a neutral camp borrows its family's art: same id stem ('neutral_lantern_weak' ->
       'neutral_lantern_normal') or same name without the tier ('Gutter Ghoul I' -> II)."""
    rules = json.loads(UNIT_RULES.read_text(encoding='utf-8'))['rules']
    ents = [e for e in json.loads((ROOT / 'data' / 'entities.json').read_text(encoding='utf-8'))['entities']
            if e['file'] == 'npc_units.vdata']
    for e in ents:
        key = f'unit:{e["id"]}'
        if key in manifest:
            continue
        for pattern, rel in rules:
            if re.search(pattern, e['id']):
                art = rule_art(rel, 'units/_class')
                if art:
                    manifest[key] = art
                break
    by_stem = {_TIER_SUFFIX.sub('', e['id']): manifest[f'unit:{e["id"]}'] for e in ents if f'unit:{e["id"]}' in manifest}
    by_name = {_ROMAN.sub('', e.get('name') or ''): manifest[f'unit:{e["id"]}'] for e in ents
               if f'unit:{e["id"]}' in manifest and e.get('name') and e['name'] != e['id']}
    for e in ents:
        key = f'unit:{e["id"]}'
        if key in manifest:
            continue
        art = by_stem.get(_TIER_SUFFIX.sub('', e['id']))
        if not art and e.get('name') and e['name'] != e['id']:
            art = by_name.get(_ROMAN.sub('', e['name']))
        if art:
            manifest[key] = art


GAME_KEYS = {'misc.vdata': 'misc', 'modifiers.vdata': 'modifier', 'abilities.vdata': 'ability'}


def game_icons(manifest: dict) -> list[str]:
    """The Game section's art (data/overrides/game_icons.json): its systems' tiles ('systems', stored under icons/game/
    for game_systems.json) and its entries with no art of their own — map objects, effects, abilities no hero owns —
    keyed as builders/common.entity_icon reads them ('misc:<id>', 'modifier:<id>', 'ability:<id>'). Returns the
    images the VPK files lacked."""
    cfg = json.loads(GAME_RULES.read_text(encoding='utf-8'))
    lacking = [rel for rel in cfg.get('systems', []) if not rule_art(rel, 'game')]
    ents = json.loads((ROOT / 'data' / 'entities.json').read_text(encoding='utf-8'))['entities']
    for e in ents:
        prefix = GAME_KEYS.get(e['file'])
        if not prefix or f'{prefix}:{e["id"]}' in manifest or (prefix == 'ability' and f'item:{e["id"]}' in manifest):
            continue
        for pattern, rel, *_ in cfg['rules']:
            if re.search(pattern, f'{e["file"]}:{e["id"]}'):
                art = rule_art(rel, 'game')
                if art:
                    manifest[f'{prefix}:{e["id"]}'] = art
                elif rel not in lacking:
                    lacking.append(rel)
                break
    return lacking


EXTERNAL = ROOT / 'data' / 'overrides' / 'external_icons.json'
EXTERNAL_RAW = ROOT / '.cache' / 'external_raw'


def external_icons(manifest: dict, missing: list) -> None:
    """Approved copies of removed game art (see data/overrides/external_icons.json)."""
    if not EXTERNAL.exists():
        return
    for key, url in json.loads(EXTERNAL.read_text(encoding='utf-8')).items():
        if key.startswith('_') or key in manifest:
            continue
        src = EXTERNAL_RAW / (key.replace(':', '__').replace('/', '_') + '.png')
        if not src.exists():
            import urllib.request
            req = urllib.request.Request(url, headers={'User-Agent': 'cyclopean-site-builder'})
            EXTERNAL_RAW.mkdir(parents=True, exist_ok=True)
            src.write_bytes(urllib.request.urlopen(req, timeout=30).read())
        sub, eid = key.split(':', 1)
        folder = {'item': 'items', 'ability': 'abilities'}.get(sub, sub)
        side = 280 if 'card' in sub else 64 if 'minimap' in sub else 128
        dst = ICONS / folder / f'{eid}.webp'
        _to_webp(src, dst, side)
        manifest[key] = dst.relative_to(ICONS).as_posix()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='report missing icons without writing')
    ap.add_argument('--skip-extract', action='store_true', help='reuse .cache/vpk_raw')
    args = ap.parse_args()
    if not args.skip_extract and not args.check:
        extract_raw()
    manifest, missing = convert()
    allowed = {}
    if ALLOW_MISSING.exists():
        allowed = json.loads(ALLOW_MISSING.read_text(encoding='utf-8'))
    unexpected = [m for m in missing if m['key'] not in allowed]
    if not args.check:
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps(dict(sorted(manifest.items())), indent=1), encoding='utf-8', newline='\n')
    print(f'icons: {len(manifest)} stored, {len(missing)} missing ({len(unexpected)} not allow-listed)')
    for m in unexpected[:40]:
        print('  MISSING', m['key'], m['ref'])
    return 1 if unexpected else 0


if __name__ == '__main__':
    raise SystemExit(main())
