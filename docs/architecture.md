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
pipeline/extras.py     asset list diff (pak01_dir.txt CRCs), changed files per hero/unit, convars diff, steam.inf
pipeline/protobuf_diff.py  Protobufs/*.proto: fields / enum values / messages added, removed, changed
pipeline/strings_diff.py   text strings of client/server/host/engine2 (*_strings.txt), byte noise dropped
pipeline/loc.py        english localization per build (names, labels, text diffs)
pipeline/history.py    -> data/builds/<build>_<commit8>.json.gz  (one record per tracker commit)
pipeline/enrich.py     adds labels / display values / BUFF-NERF direction using THAT build's loc
pipeline/semantics.py  a field's polarity and a change's direction (BUFF / NERF, %); re-exports the three below
  field_units.py       engine units ↔ metres, lengths, speeds, the unit an engine number is shown in (imports no
                          other pipeline module)
  display_values.py    a value as the page prints it (sentinels, metres on one side, re-encoded values)
  field_labels.py      a field's words: the game's labels and the hand tables for the fields it never labels
pipeline/catalog.py    -> data/entities.json  (every entity ever: kind, owner, first/last build, name)
pipeline/abilities.py  -> data/abilities.json (current ability/item cards: the in-game tooltip rebuilt —
                          m_AbilityTooltipDetails / m_vecTooltipSectionInfo, labels, units, spirit scaling, T1-T3 text)
pipeline/hero_table.py -> data/tables/heroes.json (columns evaluated on every build -> cell histories)
pipeline/unit_table.py -> data/tables/units.json  (troopers, buildings, neutrals; same idea)
pipeline/item_table.py -> data/tables/items.json  (every number of each shop item's card, by build)
pipeline/labels.py     one label / unit / sign per field over its whole history (map built from data/builds
                          + the newest build's loc; used by match.py and abilities.py, not persisted)
pipeline/flags.py      bit sets and enums a player plays with: which bits are gameplay, their words, the side
                          an added bit takes (used by enrich, match and the builders)
pipeline/news.py       -> data/notes/steam.json (Steam News API); forum notes in data/notes/forum/*.txt
pipeline/patches.py    groups builds into patch windows (changelogs; notes-less big builds get their own)
pipeline/match.py      -> data/patches/<id>.json.gz  notes lines ⇄ data changes; documented/described/hidden/mismatch/fix
                          (+ line statuses heading/untracked/nodata; change status unreleased; extras: every
                          console variable (noted ones first) and texts uncapped; loc rows cut at 400);
                          annotate_line runs in steps over one `_Line` context; re-exports the three below
  match_values.py      MChange, the numbers and words of a line, a number against a change
  match_window.py      a window's builds merged into one change per field, its marks, lists re-keyed by id
  match_passes.py      key changes, the record's extras, lines landed later / repeated / about the code
pipeline/match_rules.py  rules for lines over many entities (boons, "all …"), aliases, untracked topics
pipeline/shared_groups.py  a patch's '@shared' blocks: target_keys, scope (all / some), target_status
pipeline/entity_texts.py   a patch's name / description changes of abilities, items and heroes (extras.texts)
data/tracker_head.txt  last processed tracker commit: update-data.yml checks it against `git ls-remote`
                          every 15 min and only clones + rebuilds when the tracker moved. GitHub skips
                          most of those cron runs (1 of ~40 overnight on 2026-10-01), so a fallback runs
                          on the maintainer's PC: tools/watch_tracker.ps1 from the Task Scheduler every
                          20 min dispatches update-data when the tracker moved and nothing is running
pipeline/jsonio.py     JSON I/O; *.json.gz is gzip (deterministic, mtime=0) — indexes stay plain JSON
        │
        ▼  (data/ is committed; the site never needs the tracker)
build_site.py          single entrypoint; builders/*.py write dist/ (not committed)
  builders/cards.py    the cards and rows of a change list; its row rules (renames, plumbing, no-ops,
                          player_facing) are builders/row_rules.py
  builders/history_view.py  an entity's history; its patch strip is builders/patch_strip.py, a band's groups
                          builders/history_groups.py (both re-exported)
site/css/NN-*.css      the stylesheet in parts, joined in name order into dist/styles.css; colours only :root tokens
site/js/NN-*.js        the script in parts (one IIFE across them), joined into dist/scripts.js: sorting, cell
                          history tooltip, heatmap, filters, search
icons/                 WebP/SVG from the game VPK (tools/extract_icons.py), keyed by entity id
```

## Topic documents

| File | What |
|---|---|
| `docs/matching.md` | How patch-note lines meet the files: statuses and tags. |
| `docs/values-and-labels.md` | How a field gets its words, its unit and its printed value. |
| `docs/visual-system.md` | Design rules, icons, tooltips and keyboard access. |
| `docs/pages.md` | What each kind of page shows and how it is built. |
| `docs/data-sources.md` | Where the data comes from. |
| `docs/hero-stats-table.md` | The hero table's columns and their fields. |
| `docs/shop.md` | The Items page as the game's shop. |

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
| Shop look and sounds from the local game | `python tools/extract_shop_assets.py` |
| Page performance (scroll p95, elements, layout / style time; before & after) | `python tools/perf_probe.py [--urls …] [--label before]` |

## Build speed

- **The patch archive is read once a build** (`builders/archive.py`): `index()`, `by_date()`, `patch(pid)` and
  `gameplay(pid)` (= `row_rules.gameplay_entities`) are cached for the whole build. Every builder that walks the
  patches goes through it (entity histories, change matrices, history squares, home feed, patch / build / errata
  pages). **The cached records are shared: no builder writes into them.** A page that needs an extra field copies
  first (`patch_page` builds `change_by_key` from `{**c, 'ent_name': …}`).
- `common.ids_to_names` is memoised per string, tied to the catalogs it read; `render.readable_value` and
  `trail.trail_html` are `lru_cache`d; `cards.change_rows` calls `is_engine` once a row.
- `build_site.sync_tree` copies only new or changed icons and sounds (size + modification time) instead of
  `copytree` rewriting ~1,400 files every build.
- Site build: 10.6 s → 6.0 s (patches 3.9 → 2.1 s, builds 2.3 → 2.0 s, entities 2.8 → 1.5 s, home 0.5 → 0.1 s).

## CI

`.github/workflows/build.yml` installs Playwright + Chromium (cached) and runs `pytest -rs`;
`tests/conftest.py` has the one `browser` fixture; with `CI` set a missing browser fails.

The `alert` job (`tools/build_alert.py`) keeps one open issue, "Site build is failing", while the build on main is
broken: a failure opens it and mentions the owner, so GitHub notifies them, and the next good build closes it. Running
the workflow by hand with `alert_drill` fails on purpose, to check the whole path; the site stays as it is.

## Key functions

| # | Function | What it does |
|---|---|---|
| 1 | `build_site.py:main` | The entrypoint: `refresh_data` with `--data` (tracker → history → enrich → catalog → cosmetics → abilities → tables → news → match), `copy_assets` (`sync_tree`), then the STEPS (patches, builds, entities, tables, home). |
| 2 | `pipeline/history.py:entity_changes` | One tracker commit against the one before → a `data/builds` record, via `flatten.flatten` and `diff.diff_entity`. |
| 3 | `pipeline/enrich.py:enrich_record` | Labels, display values, units and BUFF / NERF on a build record, with that build's localization. |
| 4 | `pipeline/semantics.py:direction` | buff / nerf / up / down / changed and the % of one numeric change, from the property's polarity (signed for a hero's base stats). |
| 5 | `pipeline/labels.py:build` / `resolve` | One label, unit and sign per field over its whole history (the newest text's), used by the matcher and the ability cards. |
| 6 | `pipeline/classify.py:hero_bound_abilities` / `shared_abilities` | Who owns an ability: the hero that binds it; abilities more than half the heroes bind belong to none. |
| 7 | `pipeline/catalog.py:build` | `data/entities.json`: every entity ever, its kind, owner, names, first / last build. |
| 8 | `pipeline/match_window.py:window_changes` | A patch window's builds merged into one change per field (`merge_ops`). |
| 9 | `pipeline/match.py:annotate_line` | One patch-note line ⇄ the data changes: documented / described / mismatch / fix / code …; steps `_read_line` → `_line_subject` → `_line_aim` → `_line_numbers` → `_line_words` over one `_Line`. |
| 10 | `pipeline/match.py:build_patch` | Writes `data/patches/<id>.json.gz` (statuses, unreleased heroes, `@shared` groups, counts). |
| 11 | `builders/archive.py:patch` / `gameplay` | The patch archive read once a build and shared read-only by every builder. |
| 12 | `builders/row_rules.py:gameplay_entities` | What a page lists of a patch: gameplay rows only, repeated variants merged. |
| 13 | `builders/row_rules.py:player_facing` | THE counting rule (renames merged, tiers / corrupted / levels folded, plumbing and no-ops out), memoised. |
| 14 | `builders/cards.py:entity_rows` / `change_rows` | The rows of one entity in one patch: on its own page / on the archive pages. |
| 15 | `builders/render.py:tag_of`, `vals_html`, `shown_value` | A change's badge (class, word), its old → new cell, a value as the page prints it. |
| 16 | `builders/history_view.py:history_table` | An entity's history: one band per patch, groups per part, the toolbar facts, the patch strip and its hover-card blob. |
| 17 | `builders/hero_page.py:hero_page` / `entities_pages.build_all` | A hero's page (head, weapon, ability cards, history); `build_all` writes every hero, item and unit page. |
| 18 | `builders/dynamics_page.py:_collect` / `matrix_html` | One pass over the archive for the three change matrices (counts per row and patch, part counts, hover samples). |
| 19 | `builders/tables_pages.py:render_table` / `hist_attrs` | Every stats table (groups, sortable columns, heat, lazy columns) and a value's history attributes. |
| 20 | `site/js/*.js` modules `hist-filter`, `dyn-tip`, `hist-tip` | The history toolbar's filters and recounts, the one hover-card renderer, the value-history tooltip. |

Row 13's counting rule has one signature in code, `render.same_change(c)`, which every member-folding counter uses
(`patch_counts`, the home icons, the bands with `merge`, the change matrix, the Game index): the label and the values,
plus the entity key for an entity that came or went. One edit over a unit family or a Game system therefore counts once,
while four new sketch pickups are four changes. A merged group (a family or a Game system) carries every member's rows
(`history_groups._groups`). The patch page's tiles count `patch_counts.counted_rows`, so they add up to its "All changes"
count.

`patch_counts.fold_repeats` drops a nameless part's / alt fire's rows that repeat its parent's / gun's in the patch
(`hero_page.every_history_fold` + `repeats_dropped`), as `home_page.update_feed`, the hero bands and the change matrix
already did; `_placed_rows` and the patch page's All changes cards read it: the patch page's tiles, hero chips, tabs,
cards and written notes count what the home icon counts.

## Performance

Measured 2026-10-05 on the maintainer's PC (Windows 11, Python 3.13). **Site build** (`python build_site.py`,
committed data): 10.6 s → 6.0 s — patches 3.9 → 2.1 s, builds 2.3 → 2.0 s, entities 2.8 → 1.5 s, home 0.5 → 0.1 s.
Under cProfile: 102 s → 16 s; `player_facing` 95,882 calls → 23,465 computed, `shown_value`'s work cached per string,
the archive opened 128 times instead of ~1,500. **Pages** (`tools/perf_probe.py`, headless Chromium 1600x900, first
page cold): index.html DOMContentLoaded 2,978 → 171 ms (the Google Fonts stylesheet no longer blocks), elements
1,389 → 1,085, HTML 138 → 95 KB; heroes/nano 483 → 330 KB, elements 1,392 → 1,203; heroes/haze 288 → 197 KB;
units/npc_boss_tier2 204 → 129 KB, elements 865 → 692. Scroll p95 stays 16.7-16.8 ms on all pages (budget 25 ms).

**Scrolling inside the change matrices** (perf_probe `in-p95`; 2026-10-05). items/changes.html read 16.7 or 33.4 ms run
to run on the maintainer's PC — a main-thread cost hidden under one frame unless the PC is busy. Profiled with a
CDP trace on a 4× slower CPU (`tools/perf_probe.py --throttle 4`, new): each lazy row icon that arrived mid-scroll
cost a layout, a repaint and a new layering (Layerize) of the ~200 sticky name cells (one composited layer each).
CSS variants (no column-line gradient, no bevel shadows, no sticky cells, no text-shadow on the counts) changed the
raster time on the worker threads, not the frames; eager icons took the cold inner scroll from p95 50 ms to 17.
scripts.js `dyn-icons` switches `table.dyn td.name img[loading=lazy]` to eager at `load` (the first screen starts
lazy as before). Before → after, `--throttle 4`, median of 3–4 alternated runs: items 33.4 → 16.7 ms (a busier run:
75 → 33), heroes 16.7 → 16.7, units 16.8 → 16.8; at full speed all three 16.7. Known, left as it is: Chromium
replays the whole matrix display list (~29k ops) for every raster tile (no culling under any variant tried), and
the column lines' repeating gradient is ~65% of that raster time — removing it would change the look.
