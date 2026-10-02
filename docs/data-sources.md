# Data sources

## 1. Game files — SteamTracking/GameTracking-Deadlock

- Cloned into `vendor/GameTracking-Deadlock` (ignored by git). `pipeline.tracker.sync()` fast-forwards it.
- Each commit = one build; subject starts with the build number (`6711 | 7422 files | …`).
  A build number can appear in two commits — pages are then named `6711`, `6711-2`.
- Balance data: `game/citadel/pak01_dir/scripts/*.vdata` (KV3 text). Compiled files already contain
  inherited fields — `_base` / `_multibase` are references only, no inheritance to resolve.
  Templates carry `_not_pickable` and are hidden on the site.
- Localization: `game/citadel/resource/localization/<group>/<group>_english.txt`.
  - hero names: `citadel_gc_hero_names` (`hero_x:n`)
  - ability / weapon names: `citadel_heroes` (key = ability id)
  - item names: `citadel_gc_mod_names`
  - property labels: `<Prop>_label`, `_postfix`, `_prefix` (`citadel_attributes`, `citadel_heroes`)
  - hero stat labels: `StatDesc_<Stat>` (exceptions in `pipeline/semantics.py`)
  - unit names: `m_sLocUnitName` → `citadel_main`
- Assets: `game/citadel/pak01_dir.txt` (every packed file with CRC) → model / VFX / sound / UI changes.
- Console variables: `DumpSource2/convars.txt` → `citadel_*` defaults (respawn times, bounties, new toggles).

Units: Source units → metres ÷ 39.37 (hero stats in `m_mapStartingStats` are already in m, m/s).

Noise excluded from diffs: `m_PopularItems` (pick rates, change every build), Street Brawl draft
buckets, bot difficulty, HUD button hints, spline tangents, recoil seeds.

### 1b. Predecessor tracker — Lifeismana/Deadlocked (archived)

- Cloned into `vendor/Deadlocked`. Same layout, builds 4243 (2024-06-06) … 5044; `tracker.builds()` puts its
  builds older than GameTracking's first build in front, each `Build` carries `repo` ('pre' / 'main').
- Builds 5034–5043 have no vdata (only the asset list and localization): a missing file means "no data",
  the next build is compared with the LAST KNOWN version (`history.last_known`).
- Localization lived in `game/citadel/resource/citadel_english.txt` (single file) and
  `pak01_dir/resource/localization/…` before the current layout; `loc.diff` compares tokens across all
  files so tokens that moved between files are not reported.
- Token files sometimes write `"key""value"` with no gap (`InlineAttribute_BonusMoveSpeed`,
  `viscous_gootapult` = Splatapult); `loc.parse` accepts it. Parsed files are cached per blob under
  `.cache/<loc.LOC_CACHE>/` — bump `LOC_CACHE` whenever `parse` changes.
- Ability text: `{g:citadel_inline_attribute:'SpiritDPS'}` prints `InlineAttribute_SpiritDPS`
  ("spirit damage over time"); `{g:citadel_binding:'MoveForward'}` is a key, shown as `[Move Forward]`;
  a value that already ends in the template's unit is not doubled (`+{s:Radius}m` with `2m` → `+2m`).
- Patches of May 2024 (before build 4243) still have no game data.

## 2. Official patch notes

- Steam News API: `ISteamNews/GetNewsForApp/v2/?appid=1422450&feeds=steam_community_announcements`,
  BBCode, from 2024-10-24 → `data/notes/steam.json` (merged, never shrinks).
- Forum `forums.playdeadlock.com/forums/changelog.10/` (all changelogs from May 2024) sits behind a
  browser challenge: threads were imported verbatim with a real browser into `data/notes/forum/<date>[-n].txt`
  (line 1 title, line 2 URL, then the text). Author follow-ups are appended after `[ Follow-up <date> ]`;
  threads whose first post only linked to Steam carry the Steam text after a `Source: Steam News …` line.
  Steam and forum copies of the same notes are de-duplicated (±2 days, ≥50% identical lines).
- Marketing posts (hero reveals, events) are stored as title + link only — they are not changelogs and
  are not republished.
- **Big update pages** (playdeadlock.com/cityneversleeps, /oldgods) ARE changelogs, laid out as a
  designed page: the HTML holds only the title, the words live in a webpack chunk
  `<slug>_english.json` (found via `main.js` → chunk id, `manifest.js` → content hash, which changes
  when Valve edits the text). `python tools/fetch_update_page.py <slug>` fetches it and writes
  `data/notes/forum/<date>.txt` by the rules in `data/overrides/update_pages.json`: the "Additional
  Update Notes" verbatim, feature cards as "Title: Body", lore (landmark stories, monster bios,
  taglines) only as name lists. City Never Sleeps: 195 lines (it had 2). Old Gods, New Blood (2026-01)
  has the same layout and is not imported yet.
- Checked against the forum's thread list on 2026-10-01 (82 threads): the only missing one was
  "09-29-2026" (11 interface lines after the City Never Sleeps link) → `2026-09-29-2.txt`. A changelog
  titled only by a date next to an announcement takes its name ("City Never Sleeps · 09-29-2026").

## 3. Icons — local game VPK

- `tools/extract_icons.py` runs Source2Viewer-CLI (`CYCLOPEAN_VRF`, or a copy in `vendor/vrf/`, or PATH) on
  `…/Deadlock/game/citadel/pak01_dir.vpk` (`CYCLOPEAN_VPK`) → PNG/SVG → WebP in `icons/`, keyed by entity id.
- vdata `panorama:"file://{images}/<p>.psd"` → VPK `panorama/images/<p>_psd.vtex_c`; `.svg` → `.vsvg_c`.
- `-f` is a case-sensitive prefix; `heroes/` root is passed as a file list (the folder also has 1.7 GB of backgrounds).
- **Never** pass `--vpk_cache`: it writes a manifest into the game folder.
- Missing icons must be allow-listed with a reason in `data/overrides/missing_icons.json`, otherwise the tool exits 1.
- The tool is run by hand (CI has no VPK): after a hero's release re-run it — the final art replaces the
  pre-release stand-in (Rat King kept his placeholder crop for two days, 2026-10-03). `validate_data.py`
  warns when a released hero still has its card art allow-listed as missing. Re-encoding gives new bytes
  for unchanged pictures: commit only the files whose pixels changed.
- Removed entities: the image path from the last build they existed in is used if the file is still packed
  (`historical_icons`). Placeholders are skipped: an ability borrowing art that belongs to another entity today
  (heroes in development used Nano's icons) or generic art (`weapon_damage`); art in `hud/abilities/<hero>/`
  always belongs to that hero's abilities.
- A few removed-entity images no longer packed anywhere come from `data/overrides/external_icons.json`
  (copies of the game files extracted by deadlock-api; downloaded once with the user's approval).

## 4. Reference

- `docs/reference/hero-stats-sheet.md` — the original Google Sheet columns and the file fields behind them.
- `data/reference/stat_icons.json` — CSS class → stat icon path in the VPK.
