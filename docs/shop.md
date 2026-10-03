# Items page = the game's shop

`items/index.html` is drawn like Deadlock's in-game shop: tabs on the left (All Items, Weapon, Spirit,
Vitality, the game's order), each category a catalog page — Weapon "Fairfax · Artillery bought and
sold", Vitality "MPS · Mystic Pharmaceutical Stores", Spirit "Curiosity Catalog № 777". Code:
`builders/game_shop.py` (tabs, catalogs, tooltips), `builders/shop_page.py` (the All Items tab),
`site/styles.css` §12a, `site/scripts.js` (`gshop`).

## Where it comes from (tracker, `game/citadel/pak01_dir/panorama/`)

| What | Source |
|---|---|
| shop root, tabs | `layout/citadel_hud_hero_shop.xml`, `styles/citadel_hud_hero_shop.css` |
| category pages (one layout, re-skinned) | `layout/citadel_shop_mods_filtered.xml` + `.css` (`.showingWeapon/Tech/Armor`) |
| a card | `layout/citadel_shop_mod_view.xml` + `.css` |
| the tooltip | `layout/tooltips/citadel_tooltip_mod_details.xml` + `.css` |
| sounds | `soundevents/ui.vsndevts` (`UI.Shop.Mod.Hover.*`, `UI.Shop.Mod.*.Click`) |
| prices | `scripts/generic_data.vdata` `m_nItemPricePerTier` = 800 / 1600 / 3200 / 6400 |

There is no shop JavaScript in the game: order, states and tooltips are native code. Cards in a tier
are in name order (checked against the game, 2026-10-03).

## Geometry (the game's design px; the catalog is 1120 x 960)

The page art (`catalog_shop_bg_*`) already holds the logo, the tier frames, "TIER N" and the dark
"Experts only" box; the cards are laid over it.

| Tier row (x, y, width) | Weapon | Spirit | Vitality |
|---|---|---|---|
| T1 | 44, 120, 500 | same | same |
| T2 | 510, 10, 540 | same | same |
| T3 | 44, 480, **600** | 44, 480, 500 | 44, 480, 500 |
| T4 | **674**, 480, 400 | 510, 480, 560 | 510, 480, 550 |

- T2 and T4 rows sit 20px further right; the first card is 25px right of the row and 68px below it.
- A card is 76 x 114 with a 3px margin (pitch 82 x 120): 5 / 6 / 7 / 4 per row on Fairfax, 5 / 6 / 5 / 6
  on the other two — the same as the game.
- The price sits on the black tape painted into the art (`game_shop.PRICE_AT`, measured on the art).
- The board fills the page's width (`--u` = 1 design px = board width / 1120, in our frame); below 820px
  the tiers stack at the game's real card size on the page's paper colour.

## All Items

The game's `showingAllItems`: `catalog_shop_filter_bg` (three paper columns), the header strip
`shop_filtered_tree_header_full` ("WEAPON Stock up! · Spirit Big deal! · Vitality Feel good!"), a row per
tier with its price sticker (`pricetag_tier1..4`: §800, §1600, §3200 and the "Premium Quality §6400"
star; 100 x 45 tilted -2°, 5°, -3°, the star upright) and three columns of the same cards, 4 a row.
Ours below it: Street Brawl's draft-only T5 (dark cards) and the items no longer sold.

## A card and hover

- Paper per category and tier (`cards/card_backer_<cat>_t<N>`), cut by the torn silhouette with the
  folded corner (`shop/card_backer_png`); tier 4 is the dark card with light names.
- Passive item: square art with a torn edge (`icon_mask01..03` at half strength, by place in the tier).
  Active item: round art under an arched card. Imbue items: the IMBUE strip over the art.
- Item art is the shop art (`m_strShopIconLarge`, colour), not the HUD mask.
- Names: 15px, two lines, words never break; one too wide or too tall shrinks until it fits inside the card
  (the game's `text-overflow: shrink`; "Sharpshooter" → 12.5px), again after the window width changes.
- Hover (`HoveringItem`): every other card dims; what the item builds from lights up with a white
  outline; what it builds into pulses (scale 1.1 → 1.25, 2 s); the tooltip opens left of the card (right
  when there is no room); the category's hover sound plays. The tooltip also says the last patch that
  changed the item (ours).
- Not shown: Owned / Can't afford / Sell / the popular-item hero badge — they need a player in a match.

## Performance (measured 2026-10-03, 1600px window)

| | before | after |
|---|---|---|
| hover a card (style + layout) | 10.5 ms median, 33 ms max | 1.2 ms, 2.6 ms |
| open All Items | 246 ms | 11.5 ms |
| DOM nodes / page html (gzip) | 3261 / ~45 KB | 1806 / 15 KB |

- The rest dims under ONE layer over the board (`.gs-board::after`), the lit cards rise above it; no
  filter on 150 cards. A hover changes the classes of the few cards involved only; `hovering` stays on the
  board while the pointer crosses the gaps (90 ms).
- Cards are `contain: layout style`; Street Brawl and the removed items render when scrolled to
  (`content-visibility: auto`).
- Tooltips are `items/shop-tips.json` (26 KB gzip), fetched on the first pointer over the shop.

## Sounds

| Action | Event | Files (`sounds/shop/`) | Played at |
|---|---|---|---|
| hover a card | `UI.Shop.Mod.Hover.{Weapon,Spirit,Vitality}` | `hover_<w/s/v>_NN`, random of 11 / 11 / 10 | -14 / -12 / -15 dB, pitch 1.2 |
| click a tab | `UI.Shop.Mod.{Weapon,Magic,Vitality,Starred}.Click` | `panel_<x>` + random `page_NN` | -6 dB, page -3 dB under it |

Browsers allow sound only after a click or a key on the page; the speaker button under the tabs turns
them off (remembered in the browser).

Open the built site over http (`python -m http.server -d dist`), not as `file://`: browsers block CSS
masks and `fetch` there, so the tabs and cards lose their shapes and the sounds do not load.

## Refreshing the assets

`python tools/extract_shop_assets.py` (needs the game installed and Source2Viewer-CLI, like
`tools/extract_icons.py`) writes `icons/shop/*.webp` and `sounds/shop/*.mp3`. Re-run it when the shop's
look changes; the fonts (VALVEOracle, VALVEPulp) are not in the VPK — Archivo Narrow and Fredoka stand in.
