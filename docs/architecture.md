# Architecture

```
GameTracking-Deadlock (vendor/, git clone, 1 commit = 1 game build)
        │  git show <rev>:<path>   (never checkout)
        ▼
pipeline/kv3.py        fast KV3 text parser (0.7 s for abilities.vdata; reference lib: 17 s)
pipeline/cache.py      parsed-file cache keyed by git blob sha  (.cache/kv3, not committed)
pipeline/flatten.py    entity -> {path: scalar}; schema aliases; noise exclusion
pipeline/diff.py       entity diff; identical changes in ≥6 entities -> '@shared' record with targets
pipeline/classify.py   field category (balance/mechanic/availability/meta/ui/visual/audio), entity kind
pipeline/extras.py     asset list diff (pak01_dir.txt CRCs), convars diff, steam.inf
pipeline/loc.py        english localization per build (names, labels, text diffs)
pipeline/history.py    -> data/builds/<build>_<commit8>.json.gz  (one record per tracker commit)
pipeline/enrich.py     adds labels / display values / BUFF-NERF direction using THAT build's loc
pipeline/catalog.py    -> data/entities.json  (every entity ever: kind, owner, first/last build, name)
pipeline/abilities.py  -> data/abilities.json (current ability/item cards: the in-game tooltip rebuilt —
                          m_AbilityTooltipDetails / m_vecTooltipSectionInfo, labels, units, spirit scaling, T1-T3 text)
pipeline/hero_table.py -> data/tables/heroes.json (columns evaluated on every build -> cell histories)
pipeline/unit_table.py -> data/tables/units.json  (troopers, buildings, neutrals; same idea)
pipeline/item_table.py -> data/tables/items.json  (tier, cost from generic_data, main properties)
pipeline/news.py       -> data/notes/steam.json (Steam News API); forum notes in data/notes/forum/*.txt
pipeline/patches.py    groups builds into patch windows (changelogs; notes-less big builds get their own)
pipeline/match.py      -> data/patches/<id>.json.gz  notes lines ⇄ data changes; documented/described/hidden/mismatch/fix
                          (+ line statuses heading/untracked/nodata; change status unreleased)
data/tracker_head.txt  last processed tracker commit: update-data.yml checks it against `git ls-remote`
                          every 15 min and only clones + rebuilds when the tracker moved. GitHub skips
                          most of those cron runs (1 of ~40 overnight on 2026-10-01), so a fallback runs
                          on the maintainer's PC: tools/watch_tracker.ps1 from the Task Scheduler every
                          20 min dispatches update-data when the tracker moved and nothing is running
pipeline/jsonio.py     JSON I/O; *.json.gz is gzip (deterministic, mtime=0) — indexes stay plain JSON
        │
        ▼  (data/ is committed; the site never needs the tracker)
build_site.py          single entrypoint; builders/*.py write dist/ (not committed)
site/styles.css        all colours are :root tokens
site/scripts.js        sorting, cell history tooltip, heatmap, filters, search
icons/                 WebP/SVG from the game VPK (tools/extract_icons.py), keyed by entity id
```

## Commands

| What | Command |
|---|---|
| Full data refresh + site | `python build_site.py --data` |
| Site only (from committed data) | `python build_site.py` |
| Some pages | `python build_site.py patches tables` |
| Regenerate all build records | `python -m pipeline.history --rebuild && python -m pipeline.enrich --all` |
| Icons from the local game | `python tools/extract_icons.py` |
| Debug the matcher on one patch | `python tools/inspect_patch.py 2026-09-16 unmatched mismatch` |
| Tests | `python -m pytest` |

## Change statuses (patch pages)

| Status | Meaning |
|---|---|
| documented | a note line has the same old → new numbers as the files |
| described | a note line talks about it without exact numbers (e.g. "All slows reduced by ~20%") |
| hidden | nothing in the notes covers it — the eye marker |
| mismatch (line) | the line names a property of the entity but the files say other numbers |
| fix (line) | a bug-fix line ("Fixed …") — usually no data change |
| rounded (line) | the notes round a value (0.54 → "0.5"); exact values shown |
| unannounced | a window with no changelog (e.g. City Never Sleeps): nothing can be "hidden"; the page shows
  the biggest changes and patch notes written from the files |
| unreleased | a change to a hero still in development at that build — flask mark, violet rows; kept in "Only hidden" |
| heading (line) | a bare entity name ("Sinclair") heading the lines below it: those lines get it as their subject |
| untracked (line) | sound / visuals / interface / map / bots / performance / forum links: not in the diffed vdata, so not a matcher failure (`match_rules.untracked_topic`; a line with numbers is never untracked) |
| nodata (line) | the patch predates every tracker (May 2024): nothing to compare with |
| repeated (line) | an edited Steam post carries a line that a later patch's notes have and match (the 2026-03-06 post holds 03-21 lines): points to that patch |
| unmatched (line) | should be in the data but no change was found — a real matcher gap |

## Tags (badges)

Chosen from what the data contains (all patches, 2026-10-01): NEW 20k, DEL 11k, NERF 5.2k, BUFF 4k,
CHANGED 2.5k, MECH 0.9k, availability 92. The badge never repeats the percentage (the value cell has it).

| Tag | When |
|---|---|
| NEW / DEL | field or entity added / removed |
| BUFF / NERF | numeric change, direction by the field's polarity (`pipeline/semantics.py`) |
| REWORK | an upgrade tier whose bonuses were removed and added in one patch (`render.fold_tier_swaps`) |
| MECH | mechanic field (behaviour flags, dependencies) without a direction |
| CHANGED | value without a known direction |
| ON / OFF | availability: `Disabled`/`In Development` truthy = OFF, `Player Selectable`/release state = ON |

On hero and patch pages changes are grouped: patch or hero → one header per ability (icon, name, tag
counters) → its rows without the name repeated. Abilities re-created under a new id borrow the icon of
their namesake with the same owner (`common.entity_icon`).

Tag look: the tag's own pixel icon + word, coloured on a tint of the tag colour with a 2px bar and
notched corners; the tint grows with the size of the change (`data-g`). Counters (▲3-style) are the
same icons + a number (`render.pip`). Icons are 10×10 ASCII grids in `builders/pixel_icons.py`, never
font glyphs (fallback fonts drew ⟳ as "C"); how to draw and review them: `.claude/skills/pixel-icons`.

**One counting rule.** Every counter on every page (home summary, patches index, heroes index, card
headers, ability sub-headers, history bands, the 12-patch strip) counts `cards.player_facing(changes)`:
renamed fields merged, swapped upgrade tiers folded into one REWORK (per entity, never across abilities),
engine plumbing (`cards.is_engine`, the "Technical" fold) left out. A patch that only touched plumbing is
not the hero's "last change" and does not take one of the three open history bands.

Polarity notes: an interval between an effect's ticks (`HealInterval`, `TickInterval`, `DamageInterval`…)
is lower-is-better — Infest Heal Interval 3 → 2 is a BUFF.

## Visual system (design review 2026-10-01, three designer agents, four rounds)

- Fonts: Jersey 20 (headings, names, big numbers — unambiguous pixel digits, weight 400 only) **only at
  20px and up**; smaller names (hero index, Hero Stats, ability sub-headers) use IBM Plex Sans 600.
  VT323 for labels, badges, dates (16px and up); IBM Plex Sans for body and tabular numbers.
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
- Hero / item / unit history (`builders/history_view.py`): one collapsible band per patch (latest 3
  open) over ONE full-width panel — an ability sub-header, its official lines (prefix dropped), then the
  file changes no line spelled out exactly; a single-entity page (item, unit) has no sub-header. The
  "Only hidden" filter sits in the History heading row (`hero_page.history_heading`).
- Hero page head: every main non-gun stat as a tile (`hero_page.KEY_STATS`: health, regen, resists,
  movement, melee, spirit growth), values centred; the secondary ones fold under "All stats". Weapon
  panel: six headline tiles (`hero_page.WEAPON_TOP`: DPS, Max DPS, Bullet dmg, Bullets/s, Ammo, Reload),
  the rest under "All weapon stats" (units ride on the number). "Changed lately" is a corner notch.
- Patch titles (`common.patch_title_html` / `patch_title_text`): the date once. A named update (City
  Never Sleeps, Matchmaking Update) shows ✦ name + date and a gold banner bar; a dated one ("09-16-2026
  Update") shows only its date + "update"; follow-ups say so.
- % pills grade their colour strength by size (`render.pct_grade`, steps 5/15/30/60%; scripts.js
  `pctGrade` mirrors them); the history tooltip shows no pill for a first value or a 0.0% step.
- Item page: current values in a sticky left column beside the history.
- Heroes index: under each portrait the newest patch that touched the hero or its abilities
  (`trail.hero_last`) — its two biggest counters and the date.
- Home "Biggest changes": one card per ability.
- Hero Stats: group labels left-aligned (visible at each group's start), a right-edge fade while more
  columns are off-screen (`.table-fade`, removed when scrolled to the end).

## Patch notes tab (`builders/notes_view.py`)

Valve's text is not reproduced as a wall of lines: each section's lines are grouped by subject (hero,
item, ability, unit — consecutive lines, a bare-name heading opens a group) under an icon header with tag
counters; the subject prefix is dropped from the lines; a hero's line shows the icon of the ability it
matched (or names); each line gets the tag of the change it matched (counters when it matched several
kinds); "from A to B" / "by N" numbers are highlighted in the direction's colour; the right column keeps
what the files say.

## Icons without per-entity art

| Rows | Source |
|---|---|
| troopers, Guardians, Walkers, Patron, Base Guardians, base turret, Mid Boss | the class portraits the game's own ping wheel uses (`scripts/ping_wheel_messages.vdata`), rules in `data/overrides/unit_icons.json` |
| neutral camps without art | their family's art: same id stem (`neutral_lantern_weak` → `_normal`) or same name without the tier ("Gutter Ghoul I" → II) |
| map pickups (powerups, rejuvenator) | `m_strPingIcon` / nested `m_strHudIcon` of `misc.vdata` (`misc:<id>`) |
| groups and rules ("All heroes (24)", game rules, map objects, modifiers, loot tables) | site category glyphs (`common.GLYPHS`, pixel SVG, never presented as game art) |
| ability card property rows | `m_strCSSClass` → `icons/stats/prop/<class>` (the in-game tooltip icon); spirit damage purple, bullet damage warm, healing green |

## Tooltips

Short `data-tooltip` texts are shown by one floating element from `site/scripts.js` (clamped to the
viewport, flips below when there is no room above, tap to show on touch). Stat history cells use the
separate `.hist-tip`. Hero Stats column headers are short one-line labels; the full label is the
header's tooltip; niche columns live in a hidden "Details" group (`tables_pages.HERO_LAYOUT`).

Field categories that never count as gameplay (so never "hidden"): `technical` (scale-function wiring,
state masks, curve spline points), `streetbrawl` (incl. item draft weights), `ui`, `visual`, `audio`, `meta`.
Changes copied into many entities (`@shared`, e.g. soul-investment bonuses in every hero) show once as
"All heroes (N)".

Matching rules live in `pipeline/match.py`; every fix to matching gets a test in
`tests/test_pipeline.py`. Rules so far:

- numbers match under display transforms: raw, magnitude, fraction↔percent, units↔metres, rate↔interval (1/x);
- compound values `100+1.5 → 120+1.75` = base + spirit scaling;
- `T1/T2/T3` in the line must agree with the tier of the field;
- a line without a subject (General section) needs both the numbers and a shared word (with synonyms:
  bounty↔gold/reward, guardian/walker↔tier/boss, respawn↔spawn);
- console variables take part in matching (respawn times, bounties live there);
- entities added in a window count as ONE change ("Added to the game files"), not one per field;
- a change repeated verbatim across many entities (`@shared`) counts once.

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

## Patch windows

`pipeline/patches.py`: window of a changelog = `[date − 3 h, next start)`. Builds usually land
17–26 h after the title date but sometimes before it; builds within `[start − 12 h, start + 30 h]`
are re-assigned to whichever neighbouring changelog they document better. Posts without a change
list (hero reveals, events) never open a window; a big build (≥150 gameplay fields) with no changelog
within 3 days becomes its own patch, named after an announcement within 2 days if there is one.

## Known schema drift (handled by aliases in `pipeline/flatten.py`)

| Build | Change |
|---|---|
| 5201 (2024-09) | `m_nAbilityBehaviors` → `m_AbilityBehaviorsBits` |
| 6468 (2026-04-30) | trooper flat DPS/resist fields → `m_VS*{…}` blocks (real restructure, not aliased) |
| 6711 (2026-09-29) | `m_WeaponInfo` → `m_mapWeaponInfos.primary` |
