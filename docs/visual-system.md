# Visual system

Design rules, icons, tooltips and keyboard access. Split out of `architecture.md` on 2026-11-13; see it for the pipeline overview.

## Visual system (design review 2026-10-01, three designer agents, four rounds)

- **Page weight and first paint** (2026-10-05): No inline SVG for icons. Status marks (`common.mark`),
  tag counters (`render.pip`) and category glyphs (`common.visual` without art) are empty spans; styles.css
  draws the shape as a CSS mask on `::before`. All masks come from `pixel_icons.svg_mask`; `tests/test_perf.py`
  and test_entity_page.py keep the CSS in sync with the art. Nano's page 483 → 330 KB, the archive's HTML
  81 → 63 MB. **Fonts never hold the first paint.** One Google Fonts request per page, loaded as `media="print"`
  `data-fonts` and switched on by scripts.js once it has loaded. With the fonts server answering in 2.5 s:
  DCL / first paint 2.7 s before, 35-250 ms after. A change-matrix tile of one tag is a class (`.dsq.s-<tag>`),
  not an inline gradient.
- **Type scale** (type pass 2026-10-17; a critic counted 31 family / size / weight mixes on one hero page and VT323
  at 13-15px): every font size is a step of ONE scale, the `--fs-*` tokens in `:root` (`--fs-2xs` 10, `--fs-xs` 11,
  `--fs-sm` 13, `--fs-base` 14, `--fs-md` 16, `--fs-lg` 18, `--fs-xl` 20, `--fs-2xl` 26, `--fs-3xl` 34, `--fs-4xl` 40,
  `--fs-brand` 28). Each family keeps to its own steps: IBM Plex Sans — 11 tags, caps labels and
  caps chips, dense column heads, 13 secondary text / tables / tips / buttons / meta, bigger caps labels, counters and
  units, 14 body (history rows, values, names), 10 only for a count inside a 14-30px tile, 16 a text field (a phone
  does not zoom in on it), 18 a band's date, 34 a date that is a page's whole title. VT323 is gone (owner 2026-10-22):
  its labels, chips and counters became the UI font — 16px caps → 600 11px, 18px caps → 600 13px, lowercase → 500
  13px. Jersey 20 (headings, names, big numbers, weight 400, unambiguous pixel digits) — 20 / 26 / 34 /
  40, a name that must be smaller is IBM Plex 600 (Hero Stats, a phone's hero grid). Jacquard 24 is the wordmark only.
  The shop draws the game's panel at the game's sizes in design px (`.gs-price`, `.gc-nm`, `.gc-imb`, `.gt-name`,
  `.gt-cost`; docs/shop.md) — the only sizes that are not steps. A chip's `<b>` keeps the chip's weight. Key-stat and weapon-tile values are one Jersey step, 20px; the six headline weapon values 34px. The
  change matrix's column row sticks at `calc(var(--fs-sm) + 13px)`, the month row's height. `tests/test_vis_type.py`
  keeps all of this: no px font size in rules, builders or scripts.js (AGENTS.md has the rule).
- One entity-card component for every change list (`builders/cards.py`): one header height everywhere
  (36px framed icon, name, ▲▼✦✕ counters and the 12-patch history strip `builders/trail.py` on one
  line); rows on a grid status | tag | text | old → new with a % pill. Documented rows carry no mark (the
  normal case); hidden rows get an orange stripe. Engine plumbing rows fold into "Technical (N)" and are
  not counted in the patch summary; a field re-keyed between builds (DEL + NEW, same label) shows as one
  CHANGED row; a replaced upgrade tier (REWORK) puts both bonus lists on a muted full-width line, two
  lines at most (click expands).
- Section banners (Sloppy's band, in verdigris) for patch-note sections, months, hero-history patches.
- Patch page first screen: tag tiles + proportion bar, released heroes hit (portrait, its two biggest
  counters of any tag below, all of them in the chip tooltip), one line of the notes check (zero items
  hidden), ◀ ▶ patch switcher.
- Hero / item / unit pages ARE their history (owner, 2026-10-03: "closer to Sloppy"), in ONE centred
  column (`common.page(cls='entity')` → `<main class="page entity">`, max `--entity-w` 1180px). Head,
  today's values, strip, toolbar and bands share the same left and right edges. Before this, the history
  sat in 1120px pinned left under a 1640px head. Order: head (portrait / icon, name, chips; a hero's key
  stat tiles) → what it is today, OPEN (owner 2026-10-04: nothing folded by default). A hero gets a plain
  `section.now-open` with the weapon panel (all cells), the ability cards and the other stats as panels.
  An item's "Current values" and a unit's "Current stats" are `history_view.now_fold`, always `open`, and
  can still be folded; an item's sections are groups of the same component (see Hero / unit stats). Then History.
  One function for all
  three (`history_view.history_table`): bands are managed as described in the History bands section above, over ONE panel.
  Each part (base stats, gun, each ability) is an `.hgroup.has-ic`: its icon on a framed plate in a
  column of its own (`cards.ability_plate`, scaled smooth, the ultimate marked with a gold corner diamond:
  `hero_page.ULT_SLOT`, `history_table(ults=)`), then its name and rows. A single-entity page has no
  sub-header. The rows are what the files changed (`cards.entity_rows`) plus the note lines that live in
  the game's code (status `code`). A row reads as a sentence: the label, old → new right after it, the %
  at the right edge, and a dashed ruler to it on hover (the values' own `::after`, no markup). A DEL
  row's old value is struck through. One mark only: the eye on what the notes left out. A unit family's tier table (`table.tier-grid`) is at least 420px
  wide on a desktop and fills the panel below 700px (390px phone: no sideways scroll on any of the 455
  hero, item and unit pages). An item's sections are groups of the one "today" component, in columns (see Hero / unit
  stats). The ultimate's plate has the gold corner
  and no tooltip, because its name is written next to it.
- The history toolbar (`history_view.toolbar`, scripts.js `hist-filter`) is ONE compact row of
  badge-high controls (40px on Abrams, Calico, Viscous at 1440px). It holds the tags present
  (multi-select, `aria-pressed`), "Not in patch notes", the parts Stats / Weapon / Abilities, the
  abilities as 26px plates (the ultimate marked), and "Before release" as a toggle button like the eye.
  Every filter, the eye included, opens the bands it matches, folds the empty ones away and recounts each
  band's counters and its eye count from the shown rows. The built numbers come back when the filters
  clear. A band's title is plain text, so a click opens it in place; a small "patch ↗" goes to the
  archive. Every toggle (the eye, "Removed", the parts, "Before release") starts with
  `aria-pressed="false"`, and a reset by a strip tile or square clears it. A row that stands for changes
  it does not list carries `data-n="tag:changes:hidden …"`. This is the "Added to the game" head of a new
  entity (`cards.entity_rows`, `cards.behind_attr`), shown with its 12 key fields only. The filters use it
  to match and recount, so a filtered band reads like its built counters (Old Gods: NEW 71 with or
  without the NEW filter).
- Round 2 (advisor, 2026-10-03): a band where every row is hidden carries ONE eye, on its banner
  (`pblock.all-hidden`; the eye sat on 46% of hero rows) — since 2026-10-17 its rows keep a dimmed eye (opacity .7),
  each a link to its own proof (see "Entity page head and history updates", `builders/evidence.py`); engine vocabulary — flag sets "A | B",
  `PBF_*`, `k_e*`, bone names, pellet `m_vecScatterOffsets` — is plumbing (`row_rules.is_engine`) unless a
  note line covered the change; ability chips merge namesakes (`data-f-ab="id1 id2"`), removed ones
  fold behind "Removed (N)", a chip without art shows its name; a lazy band carries `data-tags /
  -abs / -areas` so a filter stamps only bands that can match. Matrix tag chips SELECT (as here), not
  hide. Unnamed units (`unit_families.is_named`) sit with the helpers and stay off the home feed. An
  item page splits its "Enhanced: …" rows into an "Enhanced version" group (`history_table(enhanced=
  True)`, parts Base / Enhanced; the item's own group has no header).
- Round 3: a unit's AI wiring is plumbing (`row_rules._NPC_AI_LABEL`: attack range target, aiming spread,
  ability chances, weak-point count / respawn, sweep, model scale…; "Viewer" labels too); values read as
  said (`render._sentinel`: "-1" → "no limit" except "-1%", empty → "—"; `_same_unit`: "50m → 20m");
  family groups are named by tier only; buildings count as named; Unit Stats shows only named units,
  drops a column that repeats another (Walk = Run), a glyph where there is no art; the history toolbar
  is not sticky (Sloppy's scrolls away); home counters count what the pages show (`update_feed` over
  every patch).
- Patch strip (`patch_strip.patch_strip`, Sloppy's entity strip): the entity's latest 80 patches (`STRIP_MAX`) as ONE
  row of tiles in the page head under the name on a hero, item, unit or Game page (`history_view.head_strip`),
  oldest → newest with the newest on the RIGHT, as in the change matrices and the trail squares (owner 2026-10-05:
  "новые справа везде"). Tiles are Sloppy's dynamic cells (owner 2026-10-21; enlarged 2026-11-13, "too small, nothing
  fits, the colours only on hover"): a 38x34 plate with the number of changes at rest and the tags as a bar across its
  foot, left to right (`--st` = `patch_strip.strip_bar(dynamics_page.stripes(...))`; `c-<tag>` from
  `patch_strip.tile_colour`, the net mark or the most counted tag, is the fallback); hover only frames it. The row never
  scrolls: scripts.js `strip-end` shows the newest tiles that fit whole and marks the older ones `ps-out` (hidden),
  again when the column's width changes (a scrolled row cut its oldest tile in sight). The notes leaving something
  out = the eye-coloured top edge. A tile opens `#p-<patch>`. Hovering
  it shows the hover card (below).
- Hover cards (scripts.js `dyn-tip`, ONE renderer `card()`): a change-matrix cell, an entity page's strip
  tile, an ability card's trail square and its "last change" link, and a home feed icon. Each card shows
  the patch (named ones in gold), counts by tag, "N not in patch notes", and the biggest changes (tag,
  eye, field, old → new). On an entity page they are grouped by ability with its plate. The data is ONE
  JSON blob per page, parsed on the first hover: `script.strip-data` (`patch_strip.strip_data` /
  `tile_card`: per tile per group the counts, the hidden count, and samples ranked across the patch;
  the strip card lists the top `TILE_SAMPLES` 6, a trail card the ability's own up to 4) and
  `script.feed-data` on the home page (`home_page.chip_card`, 2 per icon). The older bands are
  `<template>`s, so a card never reads the page. The change matrices' blob is parsed on the first hover
  too and shared with `dyn-parts` (`window.__dyn`). Tiles carry `aria-label` and no text tooltip, so two
  tooltips never stack. A card also opens on keyboard focus. A card's "biggest" (`patch_strip._rank`, also the home feed's
  `chip_card`) is the size of the % and then the tag order. A NEW / REWORK / DEL row without a % counts
  as 100%, so a release card shows what was added and not two small base-stat NERFs. The change
  matrices keep their own order (`dynamics_page._collect`); that is the owner's call.
  A card is at least 360px wide (`min(360px, calc(100vw - 16px))`), at most 420px; the net chip is tied to the last
  count (`countsHtml` wraps both in `.dt-tail`). Touch (`(hover: none)`): the first tap shows the card and stops the
  link, a second tap on the same tile follows it, a tap elsewhere hides it (its mouseover). Whether the card was up is
  read at `pointerdown` / `touchstart`, before the tap's own mouseover draws it (iOS drops the click of a tap whose
  mouseover showed something; Android sends it). The compatibility `focusout` a tap fires is ignored on touch.
  `patch-anchor` and `tabs` skip a click whose default was prevented. The shop (`gshop`) does the same for a `.gcard`:
  first tap lights it and shows its tooltip, second opens the item, a tap outside the board lets go (board
  `mouseleave` is ignored on touch).
- Touch screens (`@media (pointer: coarse)`, styles.css section 10) give links drawn under 24px a finger's hit area
  without changing their look: padding taken back by a negative margin (`.pnotes`, `.ac-hist`, `.ac-last`, `.lu-more`,
  footer links, `.nav-brand`, `.sc-row .v.has-hist`), a transparent border with `background-clip: padding-box` for
  trail squares (`.trail` gets `vertical-align: -6px` so its line keeps its height; the current square's ring becomes
  an outline at -6px), an `::after` box for a matrix date. On `(hover: none)` the back-to-top button is 32px at 6px
  from the corner, 0.72 opaque, and scripts.js `hist-filter` shows it only while the page goes up (≥ 6px moves). The
  tooltip module rewrites "click to open" to "tap again to open" on a touch screen (an eye link's first tap shows the
  words).
- Links inside a page (scripts.js `patch-anchor`): a strip tile, a trail square (`trail_html(local=True)`:
  `#p-<patch>` with `data-ab`; mixed buff+nerf patches are striped, not REWORK purple) and an ability
  card's "last change" (`trail.last_counts`, its tag counts) open the band on this page. This works even
  when a filter or "Before release" hid the band or
  only the ability's group (`window.__histReset(dev)`: the group is checked on its own, because the band
  can show through another ability's rows), and even when the address
  already names it. A square scrolls to its ability's group and lights it briefly. On the patch archive
  the squares still link to `patches/<id>.html` with a text tooltip.
- Round 4 (advisor, a player's eye): one wording — "not in patch notes" for the eye (toolbar, banners,
  home), "no patch notes" for an update with no changelog and no hero release, "notes we couldn't match" for a note line no change was found for,
  "Before release" for work on a hero before it shipped, "First seen <date>" (`common.first_seen`)
  instead of a build number; a count of one is singular ("1 change", "1 bug fix"). Labels split from field names
  use the game's words
  (`field_labels.game_words`: Tech → Spirit, Armor Damage Resist → Resist; `m_vecIntrinsicModifiers` →
  "Passive"); a time field without a tooltip unit gets "s" (`field_labels._TIME_FIELD`), a speed Valve
  writes as "20m" reads m/s (`speed_m` → `M_SPEED`, display only: the matcher's transforms are
  unchanged). Long values wrap;
  an entity event row ("Added to the game
  files", path `@add`) has no value cell. The home feed's icons look alike in every update (no names under them; the hover card,
  which a touch screen opens on the first tap, names the icon — the newest update's names made it four icons a row on
  a phone against six, review 2026-10-17); stats tables explain their notch. A "changed in the newest update" notch on index cards was tried and
  dropped (owner, 2026-10-03): the newest update marked 1 hero, two weeks would mark 102 items — it
  told nothing apart; the home feed and the search answer "what changed lately".
- Namesakes (`cards.disambiguate`, `history_hints`): two fields under one label each get the words of
  their property name the label lacks; a bare one beside a hinted one gets its skipped words or "base"
  ("T3: Damage · base" / "· heavy melee"), a stat moved to a new name "old field" / "new field", an
  engine field its last path segment. Hints are computed over the entity's whole history, so a row
  reads alike in every patch. A property's wiring (scale-function switches, provided-type flags) is
  plumbing even where the notes spoke (`row_rules._PROPERTY_WIRING`).
- Home search (`builders/site_search.py`, scripts.js `site-search`): `search.json` = [name, page, what,
  icon] for every hero, its current abilities (`#ab-<id>` opens the hero filtered to it), item and
  named unit, fetched on the first keystroke; names that start with the query first.
- Weight: only the newest `EAGER_PATCHES` (6) bands are in the DOM; older panels are a
  `<template class="hp-t">` stamped when opened, filtered or named by `#p-<patch>` (Nano: 12k → 1.5k
  elements at load).
- Hero page stats = the game's own panels (owner 2026-10-22, `builders/hero_panels.py`, data from
  `pipeline/hero_panels.py`): Weapon / Vitality / Spirit Stats side by side under the head (one under another below
  1180px / 700px) and the Boon Rewards card under them. Each panel lists the hero's `m_ShopStatDisplay` stats in its
  order, named by the game's `StatDesc_*` words, two tiles a row on the category's paper (`icons/shop/panel_{w,v,s}`);
  a stat at 0 is at half opacity, one that grows with Spirit Power is framed with the game's "× 0.008" badge. The weapon
  head: the gun's name, last change, History, tags, DPS, falloff range (no gun picture: owner 2026-10-22); the alt fire's row under
  the gun's tiles. Spirit Power Impact: the gun's spirit-scaled stats, then every ability property scaling with Spirit
  (`scale` without `scale_by`). Boon Rewards: the non-zero per-boon gains and "Stat Rewards max at Boon N" — that
  build's boon count, with its history. A tile a Hero Stats column holds keeps its history on hover. The hero page shows only what the
  game's panels show (owner 2026-10-22: extra tiles made them too tall); its "Advanced" button is a link to Hero Stats
  (`hero_panels.adv_link` → `tables/heroes.html#details&hero=<slug>`; scripts.js `stats-link` presses Details and
  centres that hero's row). Hero Stats holds every characteristic: its columns, then, hidden with Details
  (`tables_pages.DETAIL_GROUPS`), "Gun files" and "Hero files" — the files' numbers no column holds
  (`hero_panels.adv_columns`; values `g.*` / `h.*` from `pipeline/hero_panels.advanced`, with history; no sounds,
  particles, seeds; engine distances in metres). The weapon panel has no "History" link (`_gun_links(history=False)`);
  Boon Rewards is a band as wide as the panels. A hero with a stats row but none of these panels (none today) shows
  every stat, the gun's included, in the Stats panels under the abilities (`hero_page.more_stats`).
- Hero page guns and sub-abilities: the ability grid holds the four Signature slots only and skips a card with nothing to read
  (`hero_page.has_content`). The gun is always the weapon block (`hero_page.weapon_block`): with a
  stats row the game's panels, without one its name, last change, History link and trail plus "Gun numbers
  come with Hero Stats once the hero is playable". The alt fire (a Weapon_Secondary card) is a slim
  line "Alt fire" in the block (`_gun_links`); its history rows join the gun's group as "Alt fire: …"
  and a row the gun has in the same band is said once (`hero_page.alt_guns`, `fold_alt`).
  A nameless sub-ability no slot binds is named and drawn after the owned ability whose id it extends
  ("Ava · trigger", "Pounce · instant": `hero_page.sub_parents`), its rows the parent repeats in the
  same band go (`drop_parent_rows`), and the parent's toolbar chip holds it (`history_table(chip_of=)`).
  A removed chip whose name a current one has joins that chip's ids. A hero whose owner is another hero
  (`hero_page.borrowed_gun`) carries "No gun of its own yet", without name, last change, History or trail.
  `hero_page.gun_templates`: a gun's template entries (…_shared_base / …_shared_weapon_info) fold into the gun's group
  (`fold_into`, the general form of `fold_alt`; also in `history_folds`, so the change matrix weighs the same).
  `hero_page.prerelease_kit`: a nameless ability of the hero that is gone from the files and only ever changed while
  the hero was in development reads "<stand-in> (pre-release)" (Shiv's 2024 "Dive", "Blood Rage"; Drifter's
  "Ability 1"…).
  `catalog._DEPRECATED` also strips Valve's "- Disabled" mark ("Majestic Leap - Disabled" → "Majestic Leap", then
  `dead_namesakes`).
- Site shell (add to the Fonts / shell bullets): the site bar is a 3-column grid: brand left,
  Heroes | Items | Units centred, build badge right. On phones it is eye + scrolling tabs. The site shell does not centre wide tables. Centring every
  `.table-fade` gave the change matrices a 20-25px sideways scroll at 1700-1920px, and the first column
  slid under the sticky names. Tooltips and cards
  float above the sticky site bar (`--z-tooltip` 200 > `--z-nav` 100). The game's icons are scaled smooth
  (`img.px` is no longer pixelated), because they are 128px paintings
  shown at 20-96px. A switch (`data-toggle-class` checkbox) follows its box, also when the browser restores
  a ticked box on "back". Toggle buttons report `aria-pressed`.
- Site bar build (`common.build_badge`): every page's bar names the same newest game build, "game build N", taken from
  `common.latest_build` (the last record with a build number in `data/builds/index.json`) and linking to that build's
  page. `page(build=…)` is ignored; the three stats tables still pass their build (removable).
- Patch titles (`common.patch_title_html` / `patch_title_text`): the date once. A named update (City
  Never Sleeps, Matchmaking Update) shows its name in gold (`--gold`, no icon: it shifted the text) +
  the date and a gold banner bar; a dated one ("09-16-2026 Update") shows only its date + "update".
- Dates are never in the pixel fonts: IBM Plex, tabular figures (banners, tooltips, lists, cards).
- Stat history tooltip: one set of columns for every row (date | was | → | now | %), a first value
  sits under "now".
- % pills grade their colour strength by size (`render.pct_grade`, steps 5/15/30/60%; scripts.js
  `pctGrade` mirrors them); the history tooltip shows no pill for a first value or a 0.0% step.
- Item page: current values open above the history, in the one "today" component (`builders/now_values.py`).
- Heroes index (`builders/heroes_grid.py`), like the game's hero grid: one grid of tall portraits in
  the order of the game's sort names (`m_strHeroSortName`: The Doorman under D; no "new players" row —
  owner's call), the name plate in the hero's colour from the game (`m_colorUI` as `--hero` in the
  card's style — the one approved exception to ":root tokens only") and a PRE-RELEASE ribbon; no role,
  complexity or last-patch line (owner's call, 2026-10-01).
- Index cards on a phone (below 600px): Heroes three a row (`.hgrid-cards`, portrait crop 206/224, name 14px); Units
  and Game two a row (`.grid.units`, 56px icon).
- Unit families (`builders/unit_families.py`, owner 2026-10-03: "many identical units, only the tier
  changes"): units sharing a name once the tier numeral is dropped (Slum Shroom I-III, the five Gutter
  Ghouls of each tier, the four Walkers, the Base Guardians) are ONE card on the Units index (tiers and
  "×N" under the name), ONE page (the main member's: not an `alt_` copy, lowest tier, not the boss's
  `weak` copy; the others are redirect stubs `body[data-redirect]` that keep the `#p-` anchor), ONE row
  in Unit changes (the same change on several members counts once) and on the home feed. On the page a
  member is a group named by its tier ("Tier II"); an untiered copy is named by its family and what tells it apart
  ("Guardian (Alt)", "Walker (Alt Weak)", "<family> (New model)", `unit_families.member_label`);
  members whose rows in a patch are identical are one group ("Tier I", "All tiers", "All variants";
  `history_view` `merge`); the part buttons are the tiers. Unit Stats: the neutral camps are a TIER
  table (what every family shares per tier: health, damage, bounty) + a FAMILY table (a row per family,
  only the columns that differ: range; speeds a column per tier where a family's tiers differ, "Run
  Speed I / II / III") + the others (Mid-Boss, Sinner's Sacrifice); a family page's "Current stats" is
  one table, a stat per row and a tier per column (`table.tier-grid`); rows with no
  stat but a 1-HP placeholder are dropped (`tables_pages.has_stats`). Removed units hide behind a
  "Removed" switch. Helpers — the
  Hideout's toys, the bots' brain, entries with only a model / particles / sounds and not one gameplay
  field (`classify.unit_is_helper`, catalog kind `helper`; the code spawns them by class, abilities do
  not name them) — hide behind "Hideout, bots & effects" and with the removed rows in Unit changes.
- Hero / item / unit change matrices (`builders/dynamics_page.py`, Sloppy's "Dynamics"): heroes/changes.html,
  items/changes.html and units/changes.html, sub-tabs of the three indexes. A row per hero (its stats + every
  ability it owns), item or unit (in the Units index order), a column per patch (months above, gold day =
  named update; a month the old-patches cutoff splits is two headers, `_months`, so with the old columns
  hidden the newer part spans only its own dates), a cell = a square striped in the
  tag colours, each stripe as tall as its share (same counting rule as every counter). Switches: older
  patches (> 1 year, hidden by default; the table opens scrolled to the newest), buff vs nerf (one net
  colour), tag filters, "Not in patch notes" (below), pre-release heroes / removed items and units. Heroes index: pre-release heroes hide behind
  a switch, "Unreleased & hero labs" is folded.
- Hero changes: one tile per cell holds everything a patch did to the hero (stats, weapon, abilities);
  a filter — All / Stats / Weapon / Abilities (`dynamics_page.PARTS`, `part_of`: weapon = gun + melee) —
  redraws every tile from the part counts in the page JSON and narrows the hover card (owner, 10-01:
  a filter, not split tiles). Heroes index cards are only the portrait and the name on a plate in
  the hero's colour (no role, complexity or last-patch line — owner's call).
- Change matrix cells: a bevelled tile, its number of changes in the corner; hovering opens a card drawn by
  scripts.js from the page's `.dyn-data` JSON (who, which patch, counts with the tag icons, the three
  biggest changes, "+N more").
- **"Not in patch notes"** (2026-10-17): `dynamics_page.toolbar` puts a `button.px-btn.dyn-hid` (`EYE_MARK`) first
  after the search in every matrix bar, and `cap_key()` (`.cap-key`: a 12px tile with the eye-coloured top and "some
  changes not in patch notes") at its end. Pressing it redraws every tile from the rows the notes left out.
  `_collect` also returns `hcells`, `hparts` and `hsamples`: the cell's rows with `render.not_in_notes`, counted by
  tag and by part, and their biggest per part (`_ranked`, `_pick`, `_by_part`). A cell entry is `[patch, counts,
  samples, parts|null, hidden, net]`, plus, only for a cell PARTLY out of the notes, `_hidden_tail`: `[hidden counts,
  hidden parts (heroes; 0 else), hidden samples (0 = the cell's samples with s[6])]`. A cell with every row out reads
  its own fields (heroes/changes 706 → 760 KB HTML). Rows carry `nh` (nothing out of the notes) and `nhn` (none in
  the columns shown without "Older patches"); `table.dyn.only-hid` hides them. scripts.js `dynHidden(c,
  withSamples)` reads the fields, and `dyn-parts` redraws from them while `only-hid` is on. The orange top marks a
  tile that shows such a row under ANY filter, from the same counts. `dyn-tip`'s `matrixCard` lists those rows only
  and says "N not in patch notes". Toggle cost: 2-8 ms script, next frame ≤ 32 ms (items).
- **Filters in the address** (scripts.js `dyn-url`, the last module): `#hidden&old&bvn&extra&part=<p>&tags=<t,t>
  &role=<r>&cat=<w|s|v>&tier=<n>&q=<text>`. `hidden` is the eye, `old` "Older patches", `bvn` "Buff vs nerf", `extra`
  the rows switch ("Pre-release" for heroes, "Removed" for items, "Removed & helpers" for units), `part` and `role`
  (heroes), `cat` and `tier` (items), `q` the search. The address is read at load and on `hashchange` by pressing
  the bar's own controls, and written back with `history.replaceState` after every click, change and `searched`.
- Matrix performance (2026-10-03, item matrix 29k → 4.8k cells, 38k → 10k elements): the stripes are ONE
  inline gradient (`dynamics_page.stripes`, the same in scripts.js after a filter; 12% minimum share);
  a run of empty cells is one `<td colspan>` (`_gap`) that never crosses into the old columns, the column
  lines are its background; `table-layout: fixed` from a `<colgroup>` (30px per patch, `col.old` 0 while
  hidden; table width from `--n-new` / `--n-all`) — the automatic layout with colspans took 0.5 s per
  toggle. A tag filter redraws only the tiles that have the tag and are in sight; hidden ones are marked
  dirty and drawn when their columns / rows show.
- Patch calendar (`builders/calendar_page.py`, patches/calendar.html, Sloppy's Calendar): per year, months
  by days; a day's shade = game builds that day, a patch day a raised tile with its name (named update
  in gold); the year's numbers (patches, named, follow-ups, builds, median / longest / shortest stretch)
  and the cadence of all years by month.
- Stats tables (`builders/tables_pages.py`): items and units come as one table per category (Weapon /
  Spirit / Vitality; buildings, troopers, neutral camps) with only the columns that category fills,
  items split by tier rows, a unit kept under several ids with the same numbers is one row "×N", unit
  names from the game (`loc.unit_name`, `data/overrides/unit_names.json`: kill feed / attacker-class
  strings), never raw ids. Hero Stats hides pre-release heroes behind a switch. Every table centres its
  cells and headers and draws translucent lines both ways (`--grid`, `--grid-strong`), the stat history
  tooltip included (the name column stays left; "was → now" is one cell without lines around the arrow).
  Hero Stats (Sloppy's toolbar): a Boons box (0-35) shows the table at N boons — base + N × the per-boon
  column (`tables_pages.BOON_PER`; DPS grows with the bullet), role buttons (the game's m_eHeroType), the
  heatmap as a switch; numbers tinted by meaning (`COLUMN_TINT`: health green, weapon orange, spirit
  purple); a value with a history is underlined with dots. The page background is a fixed composited
  layer (`body::before`) and table tints are solid colours: scrolling a 46-column table stays smooth.
  Cell histories (`hero_table.history_changes`) bridge only holes in the data — a column whose SOURCE is
  missing from the build (`MISSING`: Valve cut unrevealed heroes' weapons out of abilities.vdata until
  their reveal, builds 5747-5878 and 6127-6281) is one change on the reveal build; an absent FIELD is a
  real state, so a stat removed and later restored shows both changes with their dates. Old builds:
  bullet speed from the flat `m_BulletSpeedCurve` before 5747, dash times from the shared dash ability
  (Innate 1) before 5706, an omitted burst interval is 0 (audit of data gaps, 2026-10-01).
- Items index = the game's shop (`builders/shop_page.py` + `game_shop.py`, see docs/shop.md).
- Navigation (2026-10-03, owner: "closer to Sloppy"): the bar is Heroes | Items | Units | Game; each section has
  the same three sub-tabs (`common.SECTION_TABS`): its index, its stats table (Hero / Item / Unit Stats; Game: Game / Game rules / Game changes)
  and its change matrix. Patches, builds, the calendar and Notes vs files are still built but off the
  bar: the footer's "Patch archive" and the date banners lead there. A matrix tile and the home feed open
  the entity's own page at that patch (`#p-<patch id>` on every history block; scripts.js opens it).
- Home (`builders/home_page.py`): the three sections as tiles, then "Latest changes" — for each of the
  last 4 updates with gameplay changes, the heroes, items and units it touched as icons (count, net
  buff / nerf edge, the eye when something was hidden) linking to that page at that update
  (`home_page.update_feed`: a hero's abilities count on the hero; '@shared', templates, helpers and
  unreleased work are left out).
  An update's sections (Heroes, Items, Units, Game) sit side by side, each its label over its icons (`.lu-groups`
  flex-wrap; a group is as wide as its icons, a long one takes the whole width and wraps). On a phone every section
  shows 18 icons (`PHONE_ICONS`) and a "+N more" link to the patch page, the newest update too. `home_page._top(total,
  hidden)` writes the logo, search and the two counters; below 600px the counters span the tiles' box width; the tiles
  are two a row down to 640px (each tile shows as many whole icons as fit: `.ht-art` wraps the rest out of sight).
  Units with no game art (`entity_icon` None) are not drawn as the unit glyph: `home_page.fold_bare` splits them off
  and `_fold_tile` draws one `a.lu.lu-fold` "+N" tile after the drawn icons (tooltip lists their names, link to the
  patch page's changes, no hover card / data-k). The phone's "+N more" link counts the units the fold tile stands for.
  An update's banner: the count not in patch notes is the entity pages' eye chip (`a.chip.eye-link`, as
  `history_view.hidden_link`), linking to the patch page's `#hidden`. The clauses that explain it (`au-off`, `au-shr`,
  `au-arch`) each sit in a `span.au-more` after a `span.au-dot` " · ", in 13px UI type. At most 700px they go one a
  line, without the dot, starting at the left (`.update > .banner .bc` flex-basis 100%). A group whose icons are all
  out of the notes gets `span.lu-all`, the eye alone beside its count, the words in its `data-tooltip` (owner
  2026-10-21: the boxed chip stood out of the feed); an update with no changelog and no hero release gets none (its banner says "no patch notes"). At most 640px the four
  tiles stay two a row, the title and the number share a line when they fit, and the 32px icons sit at the bottom.
  The home counter's second number is `div.hs.hidden`: `a.hs-go` opens `heroes/changes.html#hidden`
  (`home_page.HIDDEN_VIEW`: the Hero changes with "Not in patch notes" on), and `.hs-in` names the four sections,
  each linking to its own `<sec>/changes.html#hidden`. An update with no changelog and no hero release keeps its banner chip, an eye link to
  its `#hidden`, which reads "N changes · no patch notes" (singular for 1).
- Shared abilities (`builders/shared_page.py`): the abilities every hero has (kind 'shared'): heroes/shared.html (the hero history
  view), the hero matrix's "All heroes · movement & shared" row, search rows.
- Group names are centred, in a `span.cl` that is sticky inside its header (`left: --name-w + 8px`,
  `right: 48px`; scripts.js `table-sort` pins `--name-w` and `--cat-row-h`, again when the fonts are in): a group
  running off either edge keeps its name in sight. While a box is not scrolled to its end, `.table-fade::after` draws
  a shadow with a copper rule and `::before` an arrow (`--mask-more`, the sort triangle turned right); scripts.js
  `table-fade` keeps them off the box's scrollbars (`--fade-r`, `--fade-b`). Stats cells have 4px side padding.
  A change matrix's month label (`dynamics_page.month_label`: `span.ml`, the month's number "12" over the day row's
  "17" — month and day first; a year's first month, and the first in sight, read "2026 · 01"; its short form in
  `data-s`, "01"; a year's first month and day carry `.yr`, a gold divider on their left) is
  sticky inside its header (`left: --dyn-name + 4px`, `right: 22px`; the header clips with `overflow: clip` —
  `hidden` made each header its label's scroll box). scripts.js `dyn-months` reads the headers' places once per
  layout change (at start-up, fonts, Older patches, the box's width via ResizeObserver) and, on a sideways scroll
  only, picks a state where the long label has no room: `sr` / `sl` — the short label at the end in sight
  (`::after` right, `::before` left) — or `none`; a one-patch month (`th.dm.one`, built) always shows the short
  one. States are a colour / a visibility, written only when they change. Rejected: moving the labels from the
  script (a transform each frame) — on items/changes any change in the box costs a frame its paint and
  layerization (~5 ms; p50 27-38 ms per sideways frame on a 4x slower CPU), and none → transform re-laid the table
  out; toggling a sticky inset per label costs a layout each time.
- Every stats table (2026-10-03): a click on a group header folds the group to its first column
  (scripts.js `col-groups`); zeros are quieter (`td.zero`); a cell's history drops steps its rounding
  cannot show (`tables_pages._same_shown`: Max DPS 122.925 → 122.9251); `data-hist` is single-quoted
  JSON (`common.json_attr`, no `&quot;`). Boons redraw once per frame and re-rank the heat; the search
  waits for a pause in typing and takes comma-separated names ("haze, abrams").
- Low items (`render.note_badge`): a neutral badge (`.tag.note-tag`, no icon) — TEXT on a name / description change (`text_rows`),
  MODEL on a hero model whose file size moved several times over (`model_rows`),
  NOTE on a patch-note line the files cannot back whose wording names no kind (`history_groups._groups`); no tag filter
  or counter takes it. Every section tab page is `wide` (the index pages too; Game rules' search and table share one column
  at the left, under its title and tabs): the title and the tabs no longer jump between tabs. Home tiles: a
  tile's number is what its index shows at first; the Heroes tile counts released heroes and says "+N pre-release" apart
  (`home_page.hero_tile`: Hero Stats' 'release' / 'prerelease' and the catalog's EHeroDevState_* alike, any other state
  on neither; `_tiles(extra=)`). Units 22 = the Units index's 22 cards. Every table box (`.table-fade > .table-scroll`: stats tables and change matrices) is fitted by scripts.js
  `table-fit` (dyn-scroll keeps only the width fit and the scroll to the newest end): at most the room under the
  site bar and a stuck toolbar (`main > .toolbar` when its computed position is sticky) minus 16px; the page's last
  table (what follows it < a third of the screen) also leaves room for what follows (main's padding, the footer),
  so at the page's end its header row sits right under the bars; on a desktop (≥ 760px) the page's first table
  also ends on the first screen. Never shorter than 300px. Refit at `load`, when the fonts are in, on a new width,
  and on a height-only resize on a desktop only (a phone's URL bar comes and goes). Stats tables: every sortable header shows a quiet two-way arrow, the sorted one
  the way it sorts (`th[aria-sort]::after`, `pixel_icons.SORT_ART` → `--mask-sort`, `--mask-sort-down`, `--mask-sort-up`);
  the font ▼ / ▲ (`data-arrow`) is no longer drawn. Strip tile cards: a rule for all's group carries its own number
  ("All heroes 38 changes", the ref's fifth element in `strip_data` 'g'), and "+N more" counts its rows (they are not
  in the tile's counts). `builders/caches.clear_all()` clears every functools cache a `builders.*` module defines;
  `archive.clear()` calls it (it forgot the archive only: trail, patch_counts, stat_eyes and evidence kept answering
  from the old data). The patch strip keeps the entity's latest 80 patches of its own (40 until 2026-10-21; empty
  tiles for the patches between were tried and dropped: Haze showed ~27 of hers; `tests/test_page_polish.py` keeps
  80 and no gap tile).
- Page shell: `.page.wide` is `max-width: var(--content-w)` like the site bar, so the title, toolbar and table start at
  the brand's x (at 1920: 134px); the footer's side padding is `--gutter`.
- Site changelog (`changelog.html`, `home_page.changelog_page` from `data/changelog.json`): `page(cls='changelog')`
  makes it one column of about 80 characters (`max-width: calc(80ch + 2 * var(--gutter) + 40px)`).
- Palette: `--text-dimmer` #85918b (4.5:1 on every panel up to `--bg-panel-3`; was #6b7772, 3.2:1).
- Switches (`.switch`, a `data-toggle-class` checkbox): off = a dark slot (`--bg-page`) with a `--line-bright` frame and
  a `--text-dim` knob on the left; on = a `--patina` fill with a `--text-bright` knob on the right.
- Item Stats (`tables_pages.items_table`; data `pipeline/item_table.py`, rebuilt 2026-10-04 after owner
  complaint 6 "too plain": 14 hand-picked properties left 67-84% of the cells empty). The data is every
  number the item's tooltip card shows (`m_vecTooltipSectionInfo` + header values, `item_table.shown_props`),
  per build. A property that feeds a hero stat (`m_eProvidedPropertyType`) and is always on (no
  "Conditional" in `m_eStatsUsageFlags`, before 2025-04 `m_UsageFlags`) is keyed by the stat it provides
  (`stat_key`: TechPower and SpiritPower are one `tech_power`); a stat that `STAT_MIN_ITEMS` (3) shop
  items give is a column, grouped by `item_table.family()` (Weapon / Spirit / Vitality / Movement by the
  stat's name; an unknown new stat goes to Utility, never dropped), with the card's label, unit, icon
  (`css`) and direction (`semantics.polarity`). Cooldown and duration are Utility columns; every other
  number (`fx:<Prop>`: Headshot Booster's +45 Head Shot Bonus Damage, Cultist Sacrifice's conditional
  +50 Bonus Health, a stat only 1-2 items give) is one of the row's `effects`, with the card's label and
  printed value. History is tracked PER PROPERTY over every number of the item, on the card or not
  (`item_table.snapshot`, `collect`); which stat or effect a property feeds is decided by the newest
  build only (`_raw_keys`), and each key reads the property that feeds it now (`item_history`). Keyed by
  the provided stat, Valve's enum renames (6541: BASEATTACK_DAMAGE_PERCENT -> WEAPON_DAMAGE_INCREASE …),
  a usage flag flipped or a property newly listed on the card made 77 fake "added" steps and dropped the
  real history before them (review 2026-10-04). Per property a meta is kept (provided stat, conditional,
  card section, drawback, icon: `prop_meta` / `note_meta`); retired enum names are learned from it
  (`Enums.aliases`: a property switched X -> Y in build B and no shop item used X from B on). A property
  that got its first value in the very build another lost its own, feeding the same stat (BonusSpirit ->
  TechPower), or — a plain number — with the same value and a respelled name (…TooltipOnly, a typo fixed),
  is joined to it (`joined`). A property the item lost keeps its history under the key it fed last: a
  column stat as the column's hidden "gone" marker, a card number as a row's `removed` effect (struck
  through in the Effect cell while within the 45-day notch window). Each step carries
  `semantics.direction` (drawback flag of that build) as a fifth element and the row's `odir` the whole
  history's direction (`data-odir`); scripts.js `hist-tip` uses them before the column's polarity, so the
  table and the item page agree.
  A provided stat is an always-on stat only outside the card's Active section and outside a "triggered"
  Passive section (one listing its own timer / stacks: a plain number named …Duration / …Cooldown /
  …ChargeUp… / …Stack… / BuildUp…, `_triggered`, read as section 'Conditional'); otherwise it is an effect
  (Spirit Sap's -30 Spirit Power is the active's debuff). Effects from the Active section carry `active`
  and follow an "Active" tag (`.fx-tag`, `.fx.fx-act`). An unknown provided stat's family is "Other" (not
  "Utility": two Utility groups broke folding). Card speeds print m/s (`abilities.is_speed`: display units,
  EMaxMoveSpeed / ESprintSpeed, or a *SPEED* provided stat that is not a percent).
  The page: Item | Shop (tier, cost) | Stats — the always-on stats as chips in one cell (`stats_cell`) | Effect chips (`effects_cell`) | Utility | Builds;
  every chip carries its own history (`data-hist`). The "Stat columns" switch (or a click on a chip, which
  also sorts by that stat) opens one sortable column per stat by family; those cells are not in the page:
  scripts.js `item-filter` builds them from the chips on first open (`th[data-cell-cls]`, a `lazy`
  column in `render_table`; a stat the item lost travels as an empty `.sc.gone` marker with its history).
  Category band rows (`tr.sec[data-cat]`) and a 2px divider at each new tier (`tier-start`) stand aside
  while the table is sorted (`table.is-sorted`); item icons 28px on a framed plate, a 3px category stripe,
  units in the headers (`.u`), every table box hugs its table at the page's left edge (no auto margins;
  `.table-fade.center` and `render_table(center=)` are gone), under its title, bar and band.
  Dashes in the default view: 26% of the cells (was 71-84%), no row without a number. "Souls per point"
  converts every `[data-spp]` value (chips and stat cells) to cost / value; the heat then ranks it
  lower-is-better through `data-hpol` while `data-pol` keeps the stat's own direction for the history
  tooltip. Cost carries `data-hpol="0"` (it only repeats the tier).
  A chip whose property has no icon has no icon slot (`tables_pages._chip`; CSS `.sc > b:first-child`). The heat on a
  chip is a 2px bar along its foot (`--heat-c`, `.sc.hm-*::before`); the chip's fill stays the one every chip has. On a
  phone (≤ 760px) the chips run in one line from the column's left edge and the Tier column is hidden (`col-groups`
  recounts the spans on a turn across 760px).
- Heatmap (all stats tables, scripts.js `heatmap`): graded by rank — each column's distinct values (by
  size) ranked 0..1, the middle fifth plain, then 4 steps of green / red (`--heat-g1..4`, `--heat-b1..4`);
  an item's stat chip ranks with its column and shows it as a bar. On by default on Item Stats (`_toolbar(heat_on=True)`), a
  switch elsewhere. The sorted column has a gold header and a faint gold wash (`td.sorted-col`). Values rank with their sign (a drawback is the worst, not the biggest); a table with
  `data-heat-by="tier"` (Item Stats) ranks within each row's tier, except with "Souls per point" on.
- One recount for everything that hides columns (scripts.js `col-groups`, `table.__recount`): a folded
  group, the item filter's empty columns, Details and the stat columns; each group header spans exactly its
  visible columns, a folded group keeps the first column the filter left visible, band rows re-span. `col-groups` refolds every group on each recount (a group just unfolded drops its
  `grp-off`; only folded groups were refolded before, so an unfolded group stayed hidden); a column's cells
  change only when its header's state does (the `statcols` event re-applies to new cells).
- Table and matrix toolbars stick under the site bar on a desktop and are static at ≤ 760px wide or ≤ 560px tall
  (stuck on a phone they covered the table's own sticky header); the box fits under them (`table-fit`). Every
  `.toolbar` sticks flush at `top: var(--nav-h)` (it was +2px). On a phone an index's toolbar (`main.page.wide >
  .toolbar`) is static and `.toolbar .sep` is hidden. The legend's verb is `.lg-hover` / `.lg-tap`, swapped by
  `@media (hover: none)`. The legend chip wraps and is shortened on phones (`.lg-tail`). A stats table's or a
  change matrix's bar (`tables_pages._toolbar`, `dynamics_page.toolbar`) wraps everything after its search box in
  `tables_pages.filters_fold`: a `<details class="tb-fold">` "Filters" disclosure and a sibling `.tb-opts`. At
  ≤ 600px only the summary shows until opened (`.tb-fold[open] ~ .tb-opts`, no `:has()`); wider, `.tb-fold` is hidden
  and `.tb-opts` is `display: contents`. scripts.js `tb-fold` counts what differs from the page's start: a box turned
  on that was off (`defaultChecked`), a button pressed that started unpressed, a changed number (Boons) — "Filters (2
  active)"; a default-on Heatmap turned off does not count.
- Anchors below the sticky bars: every `.toolbar` has `scroll-margin-top: var(--nav-h)`, so a bar scrolled to by
  `#hidden` stops at its stuck place. scripts.js `sticky-h` measures the tallest shown sticky toolbar into
  `--stick-h` (at load, when the fonts are in, and on resize); `window.__stickH()` measures again at once, and `tabs`
  calls it when it opens a panel, before it scrolls to a card. `.ecard[id]`, `.ecard > .anc` and `.tab-panel[id]`
  keep `scroll-margin-top: calc(var(--nav-h) + var(--stick-h, 64px) + 8px)` (the 64px only before the script has
  measured). Entity bands keep `--hist-bar-h`, which `hist-filter` measures.
- Change matrices (scripts.js `dyn-scroll`): the box is as wide as the name column + a whole number of
  patch columns, so the newest end opens with the first column at the sticky names; month labels are
  clipped (a one-patch month's label overflowed and made the box scroll 25px too far); only "Older
  patches" re-scrolls to the end. On phones (≤600px) the name column is the icon only (44px). A resize keeps the place — height-only does nothing, a new width keeps the
  distance from the newest end; only "Older patches" re-scrolls to the end. A chosen row filter (`.dyn-rows` slot /
  tier / role) is `.on` as well as aria-pressed (it showed no pressed state). Item changes' rows and slot filters run
  Weapon, Spirit, Vitality (`dynamics_page.ITEM_SLOTS`, the game's `citadel_hud_hero_shop.xml` nav order). Item tiers
  are written by `tables_pages.tier_label` ("Tier 1"); Item Stats' stats column is headed "Always on"
  (`tables_pages.STATS_COL`; the "▸ columns" suffix is gone).
- Item Stats extras: closing "Stat columns" while one sorted the rows resets the sort (`table.__resetSort`);
  a "Souls per point" box restored on "back" converts the values at load.
- Tests: `tests/test_browser_tables.py` runs the site's script + stylesheet (site/js, site/css joined) on fixture pages in Chromium
  (Playwright; skipped where it is not installed — CI does not install it): fold / unfold returns the
  column count, signed and per-tier heat, sort reset, souls-per-point restore, matrix resize, tooltip
  step directions. All 7 fail on the previous scripts.js.

## Icons without per-entity art

| Rows | Source |
|---|---|
| troopers and Guardians share one portrait per class, each type with its role mark (`_why_marks` in `unit_icons.json`); Walkers, Patron, base turret, Mid Boss, Shrine, Sinner's Sacrifice | the portraits / markers the game's own ping wheel uses (`scripts/ping_wheel_messages.vdata`: "Push Shrine" → npcs/shield_generator, "Sinner's Here" → minimap/neutral_vault), rules in `data/overrides/unit_icons.json` |
| a hero's summon or placed object (Mini Turret, Spectral Wall, Goo Ball, Bounce Pad, Familiar's helpers, Fire Scarabs, Rat King's rats and swarm), the shield escort, the removed rejuvenator / soul pickup units | the art of the ability that makes it, matched by model and class (Mini Turret: McGinnis' turret portrait heroes/engineer_turret); the escort: the minimap's escort marker; removed pickups: their misc.vdata namesakes' art — same file |
| neutral camps without art | their family's art: same id stem (`neutral_lantern_weak` → `_normal`) or same name without the tier ("Gutter Ghoul I" → II) |
| map pickups (powerups, rejuvenator) | `m_strPingIcon` / nested `m_strHudIcon` of `misc.vdata` (`misc:<id>`) |
| Game entries with no art of their own (Soul Urn pickup / carrier / return, Unstable Rift, soul pickups and orbs, souls powerup, crates, neutral camps by tier, Rejuvenator buff, ziplines, Parry, Mantle, Teleporting, Stunned) | the art the game shows for the same thing elsewhere (minimap marker, ping-wheel or HUD icon), rules on `<file>:<id>` in `data/overrides/game_icons.json` → manifest keys `misc:` / `modifier:` / `ability:` (`common.entity_icon` reads `modifier:<id>`), files under `icons/game/` |
| Game tiles | `game_systems.json` `icon`: Breakables = the minimap crate marker, Hero progression = the HUD level-up icon, Modes = Street Brawl's HUD icon, Urn = the Soul Urn's minimap marker (the old art, ability_golden_idol's, is Wraith's Telekinesis the files borrow); their files are game_icons.json's `systems` |
| groups and rules ("All heroes (24)", game rules, console variables, loot tables) and units with no fitting art | site category glyphs (`common.GLYPHS`, pixel SVG, never presented as game art) |

`tools/extract_icons.py`: rule images go through `rule_art` (stored once, PNG → WebP, SVG copied); a marker whose
art fills under 35% of its canvas (`TRIM_BELOW`: minimap markers, 20×24 px of 64×64) is cut to its art and squared
(`trimmed`), portraits keep their framing. A `systems` image the VPK lacks is reported as missing (`game-art:<path>`,
exit 1 unless allow-listed). PREFIXES gained a few single-file prefixes (hud/brawl/icon_brawl, hud/levelup_,
hud/zipline_icon, hud/ledge_climb, hud/teleport_icon). Run from a worktree without `vendor/`:
`CYCLOPEAN_VRF=…/Source2Viewer-CLI.exe CYCLOPEAN_TRACKER=…/GameTracking-Deadlock CYCLOPEAN_PRE_TRACKER=…/Deadlocked`.

`data/overrides/unit_icons.json` has a `_why_more` note for the units that take another unit's art: chess pieces →
minimap marks, ink wall → Living Ink, skeleton → heroes/necro_shambler, cat → nano_catform, field sentry → engineer
turret; Mid-Boss → getting_started/map_rejuv, read by the new extractor prefix `panorama/images/getting_started/map_`.

Flat marks (ability icons, minimap and map-legend markers) are stored under `icons/units/_mark/`, not beside the
painted portraits. A unit card insets them 13px (10px on a phone) on its tile (`.card img[src*="/_mark/"]`), as the
Game cards inset theirs.

## Tooltips and Keyboard Access

- **Value histories** (`scripts.js `hist-tip`): values with a history (`[data-hist]`) join the tab order
  (scripts.js sets `tabIndex`; Item Stats' lazily built cells too) and show their history on focus (`aria-describedby`,
  Escape closes). Each step carries its direction from `semantics.direction`; a value's history carries its overall
  direction (`data-odir`), from the game field the column reads. Computed columns have no field: scripts.js judges by
  the column's polarity, with the sign. A table's values are one tab stop (roving tabindex): Tab enters at the value
  visited last (else the first shown one), ←/→ move in reading order, ↑/↓ to the same column in the nearest shown row.
- **Eye links** (`common.mark` with `href`, `history_view._eye_chip`): every eye that opens a build is a link in the
  tab order, a band's "N not in patch notes" chip is one link named "count — words" (renamed when a filter recounts);
  touch: the first tap shows the words ("tap again to open"), the second opens the build. A build page's row is a
  `<summary>`: Enter / Space open its source (`details.src`).
- **Sortable headers**: tab order, `aria-sort` (descending / ascending / none), Enter or Space sorts. Foldable group
  headers: `aria-expanded`, Enter / Space fold.
- **Hover cards** (scripts.js `dyn-tip`): a change-matrix cell, an entity page's strip tile, an ability card's trail
  square and its "last change" link, and a home feed icon. Each card shows the patch (named ones in gold), counts by
  tag, "N not in patch notes", and the biggest changes (tag, eye, field, old → new). A card's value column wraps
  between words (`overflow-wrap: break-word`): a long REWORK list wraps inside the card, a number never splits.
  A card is at least 360px wide (`min(360px, calc(100vw - 16px))`), at most 420px; the net chip is tied to the last
  count (`countsHtml` wraps both in `.dt-tail`). Touch (`(hover: none)`): the first tap shows the card and stops the
  link, a second tap on the same tile follows it, a tap elsewhere hides it (its mouseover). Whether the card was up is
  read at `pointerdown` / `touchstart`, before the tap's own mouseover draws it (iOS drops the click of a tap whose
  mouseover showed something; Android sends it). The compatibility `focusout` a tap fires is ignored on touch.
  `patch-anchor` and `tabs` skip a click whose default was prevented. The shop (`gshop`) does the same for a `.gcard`:
  first tap lights it and shows its tooltip, second opens the item, a tap outside the board lets go (board
  `mouseleave` is ignored on touch).
- **Category glyphs** (`common.visual` without art): an empty `<span class="px glyph g-<name>">`; it has no size of
  its own, so every place that shows one sizes it with its `img` (`.card img, .card .glyph` 72px, `.ecard-h .ei`, etc.).

Short `data-tooltip` texts are shown by one floating element from `site/js/02-tooltips.js` (clamped to the
viewport, flips below when there is no room above, tap to show on touch). Stat history cells use the
separate `.hist-tip`. Hero Stats column headers are short one-line labels; the full label is the
header's tooltip; niche columns live in a hidden "Details" group (`tables_pages.HERO_LAYOUT`).

Field categories that never count as gameplay (so never "hidden"): `technical` (scale-function wiring,
curve spline points), `streetbrawl` (incl. item draft weights), `ui`, `visual`, `audio`, `meta`. State masks are now a mechanic.
Changes copied into many entities (`@shared`, e.g. soul-investment bonuses in every hero) show once as
"All heroes (N)".

Matching rules live in `pipeline/match.py`; every fix to matching gets a test in
`tests/test_match.py`. Rules so far:

- numbers match under display transforms: raw, magnitude, fraction↔percent, units↔metres, rate↔interval (1/x);
- a value written in metres on one side and bare on the other is engine units on the bare side (`display_values.metres_pair`,
  used by `match.change_json` for the numbers and the %): "Channel Move Speed 50 → 1.3m" read −97.4% NERF on 93 abilities;
  it is 1.27 → 1.3 m/s, +2.4%;
- a hero's availability written in another field is no change (`match_window.mark_availability_moves`): on 2026-09-29
  heroes.vdata dropped `m_bPlayerSelectable` and gained `m_eHeroDevelopmentState`; for a hero whose old flag and new
  state agree both rows are dropped;
- compound values `100+1.5 → 120+1.75` = base + spirit scaling;
- `T1/T2/T3` in the line must agree with the tier of the field;
- a line without a subject (General section) needs both the numbers and a shared word (with synonyms:
  bounty↔gold/reward, guardian/walker↔tier/boss, respawn↔spawn);
- console variables take part in matching (respawn times, bounties live there);
- entities added in a window count as ONE change ("Added to the game files"), not one per field;
- a change repeated verbatim across many entities (`@shared`) counts once;
- an inline alias or name whose entity did not move falls back to the whole patch (`annotate_line`): "Stamina bucket
  3 heroes … ground dash time" stayed unmatched, so Abrams' dash rows carry the eye;
- owners of sub-abilities (`classify.hero_bound_abilities`): an ability no hero binds whose id is an owned ability +
  `_trigger` / `_cancel` / `_cancel_trigger` / `_teleport` / `_recast` is that hero's (Frozen Shelter's
  `ability_ice_dome_trigger`, McGinnis' `citadel_ability_fissure_wall_cancel`, Drifter's Ambush
  `drifter_shadow_mark_teleport`); a kit named after a hero's code without the `ability_` prefix too
  (`slork_scald`, `synth_blitz`, `tokamak_*`, `yakuza_*`).

### Game systems, number lists, added console variables

`pipeline/game_map.py` reads data/overrides/game_systems.json for the matcher: `place(subject)` (the same regexes
the Game pages use; builders/game_systems.py takes `claimed` / `is_template` from it), `phrases_in(text)` (the
systems' "subjects" a line names as whole words, a longer phrase hiding the ones inside it, a plural "s" counts) and
`convar_system(name)`.

`match.system_pools(by_ent, cat)`: per patch window, game system → its changed entries no hero / item / unit page
claims (map objects, game rules, effects, templates; not scenery or test objects: `game_map.is_decor` / `is_dev`,
which builders/game_systems.py imports with `place` and `convar_start`) plus the console variables its parts name.
A line with numbers (`system_lines_pools`: a pair, a "by N%", a granted value) that names a system gets those entries
as `Subject.numeric_ids` (`system_alias`): tried LAST, after the line's own alias / name and the whole-patch pass.
Both sides of a pair (or a whole list) need no shared word — "Jump Pad stun window increased from 0.6s to 0.9s" is
the catapult watcher's Duration — one number alone (an add, a percent) does (`two_sided`); never a field whose label
names another stat than the line (`names_other_stat`, `STAT_NOUNS`: "Movement Speed powerup movespeed 2 → 1" is not
the stamina powerup's Extra Stamina 2 → 1). A system's entries never link a line
without numbers (a system holds dozens; "Added Dash Speed to the Vitality stat screen" took the zipline's Latch End
Speed). A "Name:" prefix that is only a system word is no subject (the rules for all run first).

Number lists: `list_match` compares a list field element by element with a line that lists it ("Trooper bounty split
ratios updated from 1/0.65/0.28/… to 1/0.54/0.36/…", "Soul Sharing ratios 100/70/45/33% → …" as fractions, rounded
+8); an entry the notes skip because it stayed (Walkers' resist per nearby enemy starts with "0 enemies: 0%") is
allowed. A line whose system holds an exact list match takes the system pass before the whole patch (the 2025-05-08
"Trooper bounty split" line had linked 87 investment bonuses as "rounded").

An added console variable a system names joins the window's changes (`window_changes`; not the 6395 snapshot,
`match.convar_start`): "Unstable Rift spawn interval increased from every 6 minutes to every 7 minutes" is
citadel_koth_respawn_interval added at 420.

The untracked-topic early return (#47.2): an interface line ("keybinds", "minimap") that names an entity whose
gameplay files moved is matched first (`_names_moved`): "Added keybinds for 'Fly Up' and 'Fly Down'… Ivy's Air Drop
and Vindicta's Flight" describes their new Uses Flight Controls. Other topics (sound, map, bots, performance) still
end the line.

The Rejuvenator alias takes its aura (modifier_rejuv_pickup_aura / _punchable): "Mid Boss Rejuv claim time reduced
from 2.5s to 1.5s" is its Pickup Timer.

Result (all patches): 17 lines better (unmatched → documented / rounded / described, rounded → documented), 0 lines
lost; audit coverage 84% → 85%, real hidden kept 93% → 93%, eye precision 32% → 33%.

### Lists of named entries (add to "Patch windows" / Key functions → match)

`match_window.rekey_lists`: a window's rows of a list whose entries carry their own name (`LIST_IDS`: m_sPickup,
m_strItem, m_strLaneName; files `LIST_FILES`: misc, loot_tables, generic_data) are re-read from the window's
before / after states (`window_states`, `_state` parses a vdata once per build) and diffed by name
(`keyed_list`): "m_vecPrimaryPickups{hp_permanent_pickup}.m_flPickupWeight". One pickup inserted at #2 is one new
entry, not "#2: B → X, #3: C → B, …"; a list that came or went whole lists its entries; an entry's own name row goes
when its other rows say it came or went. The build records keep positions (keying in pipeline/flatten.py would need
`history --rebuild`, ~25 min, and every builds page re-checked).

### Rules from the audit of "hidden" changes (`pipeline/match_rules.py`)

An audit of ~1000 changes the first matcher called hidden (`tests/fixtures/audit_verdicts.jsonl`)
showed most were described in the notes in other words. `python tools/audit_score.py` scores the matcher
against it; `tests/test_audit.py` fails if coverage drops below 70% or fewer than 85% of the truly
hidden changes stay hidden (2026-10-01: coverage 76%, real hidden kept 90%).

| Pattern in the notes | Rule |
|---|---|
| "All ultimates' cooldowns nerfed by 15% (nearest multiple of 5)" | family (cooldown) × scope (ultimate slot) × ratio 1±15% with rounding tolerance |
| "Reduced all AP damage upgrades by 10%" | AP upgrades = T1–T3 fields (`m_vecAbilityUpgrades`), DPS counts as damage |
| "Walker bounty increased by 5%" | unit aliases (Walker / Guardian / Patron / Shrine / Mid Boss / Urn / Rejuvenator / neutrals / statues) |
| "Now builds from Sprint Boots" | component list changes of the item |
| "Sprint … (affects upgrades)" | same change in items built from it |
| "T2 changed from A to B" / "T3 also increases radius" | that tier's fields; topical ones first |
| one line about a new mechanic | sibling fields added/removed together (same block / same field prefix) |
| "Bullets no longer have gravity" | word links need a specific word (not just bullet/damage/spirit) |
| changes to heroes not released at that build | status `unreleased`, not `hidden` |
| "from 5,175 to 7,000" | thousands separators are stripped before reading pairs |
| "Base HP reduced by 10 for all heroes", "Bullet Cycle Time for all heroes increased by 5%", "Spirit Power scaling globally reduced by -7%" | `match_rules.global_delta_line`: stat family named before the verb × "by N" or "by N%" × entity kind; links every change of that field that moved by exactly N (or N%, "~N" ±30%) when at least 3 do |
| a bare "Sinclair" line, then "Now has +1% Spirit Resist per Boon." | the name is a sub-heading (`heading`): lines below get it as subject |
| notes published days before the files change (2024-12-06 notes, values in build 5433 on 12-14) | a notes-less window right after a changelog that carries ≥10 of its numbered lines exactly is merged into it (`absorb_late_windows`); single lines link to a hidden change of the same subject with exactly their numbers within 14 days (`late_landings`, shown as "landed later: build N") |
| "Strix Salvo - Cooldown from 30s to 25s" when only the hero's stamina moved | a hero line naming an ability / gun by a name of its own as a whole word (the `by_name` set in `match.annotate_line`; not every hero's "Melee", not "Heal" in "Health") links only that ability's fields; numbers in the line must agree with a linked field (one side within rounding, the same direction, or the multiplier given as a reduction: "Headshot reduction 25% → 35%" = taken × 0.75 → 0.65) |
| "T1 +1m/s Move Speed to +2m/s Move Speed" | `_TIER_TO`: a tier's pair without "from" |
| "Cooldown increased from 25s to 27s (moved to T2)" | `_MOVED_TO_TIER`: that tier's bonus to the same property is described |
| "Now does half damage to objectives" | `_HALF_DAMAGE` ("half damage to / on / against objectives / bosses", never a fix line) → pair 100 → 50; label synonym boss ↔ objective(s) |
| "Threadsap duration lasts 35% less" | `_PCT_LESS` reads "N% less / more" as "by N%" |
| "Scrap Grenade - Fixed some bugs with bouncing targeting" | the named ability's fields by word stems (`_stems`: -ing, final e) |
| "Repeat light melees while airborne…" | `topic_words`: in a "… Attack Light › X" label the attack's kind (melee / light / heavy / attack) names no field |
| "Street Brawl: …" | `classify.STREET_BRAWL_VALUE` rows (an ability's m_strStreetBrawlValue / Bonus / StatScale) only answer lines or sections that say Street Brawl; `MChange.base` (enrich `street_brawl_base`) is the value the mode's number replaces, one more step for pairs and percents |
| a default gun block (damage 0) that came or went on a non-gun ability | `match_window.mark_dud_guns`: its added / removed rows are technical |
| a nameless part (`match_window.nameless_part`: id = parent + `_trigger` / `_cancel` / `_recast`…, named like its parent or not at all — not Solomon's "Move King") gets `_multibase` / `_base` in the window | `match_window.mark_inherited_defaults`: its added rows are the template's defaults — technical |
| "Shields have been reworked and are now called Barriers" (2025-05-08) | blanket (`data/overrides/blanket_lines.json`): removals of `(Bullet\|Tech)Shield…` properties of items and abilities; the new Barrier numbers stay hidden |
| "Neutral bounties increased by 6%" / "Adjusted the boon reward schedule…" (2025-05-08) | blankets: neutrals' `m_flGoldReward` changes; the all-heroes `m_mapLevelInfo` table |

Result of the rules above (`tools/audit_score.py`, before → after, 2026-10-17): coverage 85% → 85%, real hidden kept
93% → 93%, non-gameplay filtered 68% → 79%, eye precision 33% → 33% (88 of 270). Over all patches, 30 unmatched lines now
read documented, described or rounded, and 9 described lines became documented. 27 lines lost a wrong link (another
ability's fields: "Pain Battery now starts charged" had linked Aura of Suffering), and 4 became "code". After round 4
(template defaults technical, shop-rework blankets, enrich 40): coverage 86%, real hidden kept 93%, non-gameplay
filtered 79%, eye precision 33% (88 of 263).
