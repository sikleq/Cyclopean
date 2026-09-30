"""Extract hero / ability / item / unit icons from the local Deadlock VPK.

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


def _to_webp(src: Path, dst: Path, max_side: int) -> None:
    from PIL import Image
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return                      # already converted from this raw file
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im = im.convert('RGBA')
        if max(im.size) > max_side:
            im.thumbnail((max_side, max_side), Image.LANCZOS)
        im.save(dst, 'WEBP', quality=92, method=4)


def _store(ref, out_rel: str, max_side: int, manifest: dict, missing: list, key: str) -> None:
    src = raw_path(ref) if ref else None
    if src is None or not src.exists():
        missing.append({'key': key, 'ref': ref})
        return
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
