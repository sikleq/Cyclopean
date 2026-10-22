---
name: deadlock-ui-researcher
description: Find how Deadlock's own interface draws something (panel, card, tooltip, icon, colour, font, effect, UI text) in the game files, to rebuild it on the site.
---

# Deadlock UI research (game files only)

Answer "how does the game draw X" from the game's own files, read-only, and return what the site needs to rebuild it.
Worked examples: the hero stat panels (docs/architecture.md, "Hero page stats"; pipeline/hero_panels.py) and the shop
(docs/shop.md).

## Where things are

All paths below are relative to the repo root. Read the tracker only through `git show` / `git grep` / `git log`
(AGENTS.md: never touch its working tree). `T` = `vendor/GameTracking-Deadlock`, `P` = `game/citadel/pak01_dir`.

| What | Where |
|---|---|
| Layout of a panel (decompiled XML) | `T`: `P/panorama/layout/**.xml` (292 files; tooltips/, popups/, ability_hud_elements/) |
| Its styles (decompiled CSS) | `T`: `P/panorama/styles/**.css` — a layout's `<include src="s2r://panorama/styles/x.vcss">` is the tracker's `x.css`; named colours and fonts (`spiritColor`, `offWhite`, `serif`) are `@define`s in `citadel_base_styles.css`, which also sets the default `Label` (font, colour, 18px) |
| Property / stat icons (`prop_*` classes) | `P/panorama/styles/ability_property_icons.css` (which SVG, `wash-color` tint); their size in tooltips: `styles/tooltips/citadel_tooltip_mod_details.css` (`.ImportantStatImage`) |
| Data a panel is filled from | `T`: `P/scripts/*.vdata` — heroes.vdata (`m_ShopStatDisplay`, `m_heroStatsDisplay`, `m_mapScalingStats`, `m_mapStandardLevelUpUpgrades`), abilities.vdata (`m_mapAbilityProperties`: `m_strCSSClass` = icon, `m_subclassScaleFunction` = what scales it), generic_data.vdata, misc.vdata |
| Words | `T`: `game/citadel/resource/localization/<group>/*_english.txt` — `citadel_main` (UI: `CitadelHeroStats_*`, `Citadel_Player_Level_*`), `citadel_attributes` (`StatDesc_*`, `Attribute_EWeaponAttribute_*`); `pipeline/loc.py` reads them (keys lower-cased) |
| Every file in the VPK, with size (images, particles, sounds are not decompiled in the tracker) | `T`: `game/citadel/pak01_dir.txt` |
| Images already extracted (PNG / SVG) | `.cache/vpk_raw/panorama/images/**` — a CSS `url("s2r://panorama/images/x/y_psd.vtex")` is `.cache/vpk_raw/panorama/images/x/y_psd.png`, a `.vsvg` is `.svg`. Only some folders are extracted (e.g. part of `hud/`): check the exact file, a neighbour with a similar name is often a different picture |
| Anything not extracted yet | `tools/extract_icons.py` `_vrf('<path prefix>')` (Source2Viewer-CLI on the installed VPK; never `--vpk_cache`; newer textures: `tools/vtex.py`) |
| What it looked like before | `git log --format='%h %ad %s' --date=short -- <path>` in `T`; 2024 builds in `vendor/Deadlocked` |
| Shipped site art | `icons/shop/`, `icons/guns/`, `icons/stats/` (made by `tools/extract_shop_assets.py`, `tools/extract_icons.py`) |

## Steps

1. Find the panel: `git grep -n -i '<word on screen>' HEAD -- <localization>` gives the token; `git grep -l '#<token>'
   HEAD -- P/panorama/layout` gives the layout. Or search layouts by the class name (`CitadelHeroStatsWeapon`).
   A panel shown on hover lives inside a tooltip: `P/panorama/layout/tooltips/*.xml` names the panel class it hosts
   (the Boon Rewards card is `citadel_ui_player_level_bonus_display.xml` inside `tooltips/citadel_tooltip_level_rewards.xml`,
   not the HUD's `citadel_hud_player_level_up_bonus.xml`). Similar names are often different screens: confirm by its text.
2. Read the layout: its `<include src=…vcss>` styles, its snippets, the ids the client fills, and which localization
   key it really uses (two tokens often say the same: `…_StatMax` vs `…_Stat_RewardsMax`).
3. Read the styles: sizes, colours (resolve `@define`s), backgrounds and their image paths, states (`.isZeroValue`,
   `.HasScalingStat`, `:hover`).
4. Find the data: which vdata field holds the list / values (most panels are filled by C++ from a vdata list; the
   list itself is in the data). Check every hero / item, not one: report when it is the same for all.
5. Values the client computes in C++ are NOT in the files: derive them, check against a screenshot the owner gave,
   and say "derived" with the rule (e.g. Stamina Cooldown 4.5s = 1 / EStaminaRegenPerSecond 0.222).
6. Images: confirm each one exists in `pak01_dir.txt` and in `.cache/vpk_raw`; give its size.

## Answer

Short, in English, as a table: element → file path (repo-relative) → field / selector → value → confidence
(**files**: read in the files; **derived**: computed, with the rule; **guess**: say what would confirm it). Add the
site's side when asked: colours become `:root` tokens (AGENTS.md), font sizes are steps of the scale, icons only from
the VPK. Do not paste whole files; quote the lines that matter.

## Limits

- Read only. Never write into `vendor/`, the game folder or `data/`; scratch files go to the session scratchpad.
- No CDN, wiki or fan-site art (AGENTS.md rule 8); if the files do not have it, say so.
- The repo is public: no user paths in anything written to it.
