"""Extract the in-game shop's look and sounds from the local Deadlock VPK (run by hand, like
tools/extract_icons.py; CI has no VPK): the three catalog pages (Weapon "Fairfax", Vitality "MPS",
Spirit "Curiosity Catalog"), the paper card per category and tier, the torn-edge icon masks, the left
tab shapes and icons, and the UI sounds the shop plays on tile hover and tab click
(soundevents/ui.vsndevts: UI.Shop.Mod.Hover.{Weapon,Vitality,Spirit}, UI.Shop.Mod.*.Click).

    python tools/extract_shop_assets.py

Images -> icons/shop/*.webp, sounds -> sounds/shop/*.mp3 (both copied into dist/ by build_site.py).
Where it all sits on the page: panorama/styles/citadel_shop_mods_filtered.css, citadel_shop_mod_view.css
(see docs/shop.md).
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))

from extract_icons import RAW, VPK, VRF, _vrf  # noqa: E402

OUT = ROOT / 'icons' / 'shop'
SFX = ROOT / 'sounds' / 'shop'
SHOP = RAW / 'panorama' / 'images' / 'shop'
CATALOG = SHOP / 'catalog'
CATS = {'weapon': 'w', 'spirit': 's', 'vitality': 'v'}
BG_WIDTH = 1825             # the page art's own width: shown up to ~1120 css px, sharp on 2x screens
CARD = (160, 229)           # 2x the 80 x 114 tile
# sound file stem -> how many variants the event picks from at random
HOVER = {'weapon': 11, 'vitality': 10, 'spirit': 11}
PANELS = ('starred', 'weapon', 'magic', 'vitality')
PAGES = 6


def _webp(src: Path, dst: Path, size: tuple[int, int] | None = None, quality: int = 85,
          luminance_mask: bool = False) -> None:
    from PIL import Image
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im = im.convert('RGBA')
        if luminance_mask:
            # the game's opacity-masks are grey pictures, applied at half strength (the torn edge
            # fades, it does not cut); CSS masks read the alpha channel
            alpha = im.convert('L').point(lambda v: 128 + v // 2)
            im = Image.new('RGBA', im.size, (255, 255, 255, 255))
            im.putalpha(alpha)
        if size and im.size != size:
            im = im.resize(size, Image.LANCZOS)
        im.save(dst, 'WEBP', quality=quality, method=6)


def extract() -> None:
    if not VRF.exists() or not VPK.exists():
        raise SystemExit(f'need Source2Viewer-CLI ({VRF}) and the game VPK ({VPK})')
    sounds = [f'sounds/ui/ui_shop_mod_hover_{c}_{i:02d}' for c, n in HOVER.items() for i in range(1, n + 1)]
    sounds += [f'sounds/ui/ui_shop_panel_{p}' for p in PANELS]
    sounds += [f'sounds/ui/ui_shop_panel_page_{i:02d}' for i in range(1, PAGES + 1)]
    _vrf('panorama/images/shop/')
    _vrf(','.join(sounds))


def convert() -> list[str]:
    from PIL import Image
    missing: list[str] = []

    def need(p: Path) -> bool:
        if not p.exists():
            missing.append(str(p.relative_to(RAW)))
        return p.exists()

    for name, key in CATS.items():
        src = CATALOG / f'catalog_shop_bg_{name}_psd.png'
        if need(src):
            with Image.open(src) as im:
                h = round(im.height * BG_WIDTH / im.width)
            _webp(src, OUT / f'bg_{key}.webp', (BG_WIDTH, h), quality=80)
        # the item tooltip's header strip (citadel_tooltip_mod_details.css .HeaderContainer)
        src = CATALOG / f'catalog_tooltip_header_{name}_psd.png'
        if need(src):
            _webp(src, OUT / f'tip_{key}.webp', (680, 174))
        for t in range(1, 5):
            src = CATALOG / 'cards' / f'card_backer_{name}_t{t}_psd.png'
            if need(src):
                _webp(src, OUT / f'card_{key}_t{t}.webp', CARD)
    for i in range(1, 4):
        src = CATALOG / 'cards' / f'icon_mask0{i}_psd.png'
        if need(src):
            _webp(src, OUT / f'mask_{i}.webp', (152, 152), luminance_mask=True)
    # the card's torn-paper silhouette with the folded corner (#ModCard opacity-mask)
    if need(SHOP / 'card_backer_png.png'):
        _webp(SHOP / 'card_backer_png.png', OUT / 'card_mask.webp', CARD)
    for src, dst in ((CATALOG / 'catalog_shop_tab_shape_psd.png', 'tab_shape'),
                     (CATALOG / 'catalog_shop_tab_edge_overlay_psd.png', 'tab_edge')):
        if need(src):
            _webp(src, OUT / f'{dst}.webp')
    for tab in ('all', 'weapon', 'spirit', 'vitality'):
        src = CATALOG / f'catalog_shop_tab_icon_{tab}_psd.png'
        if need(src):
            _webp(src, OUT / f'tab_{tab}.webp')

    SFX.mkdir(parents=True, exist_ok=True)
    ui = RAW / 'sounds' / 'ui'
    files = [(f'ui_shop_mod_hover_{c}_{i:02d}', f'hover_{CATS[c]}_{i:02d}') for c, n in HOVER.items()
             for i in range(1, n + 1)]
    files += [(f'ui_shop_panel_{p}', f'panel_{p}') for p in PANELS]
    files += [(f'ui_shop_panel_page_{i:02d}', f'page_{i:02d}') for i in range(1, PAGES + 1)]
    for stem, dst in files:
        src = ui / f'{stem}.mp3'
        if need(src):
            shutil.copyfile(src, SFX / f'{dst}.mp3')
    return missing


def main() -> int:
    extract()
    missing = convert()
    for m in missing:
        print('missing:', m)
    print(f'shop assets: {len(list(OUT.glob("*.webp")))} images, {len(list(SFX.glob("*.mp3")))} sounds, '
          f'{len(missing)} missing')
    return 1 if missing else 0


if __name__ == '__main__':
    raise SystemExit(main())
