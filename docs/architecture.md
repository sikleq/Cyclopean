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
pipeline/item_table.py -> data/tables/items.json  (every number of each shop item's card, by build)
pipeline/labels.py     one label / unit / sign per field over its whole history (map built from data/builds
                          + the newest build's loc; used by match.py and abilities.py, not persisted)
pipeline/flags.py      bit sets and enums a player plays with: which bits are gameplay, their words, the side
                          an added bit takes (used by enrich, match and the builders)
pipeline/news.py       -> data/notes/steam.json (Steam News API); forum notes in data/notes/forum/*.txt
pipeline/patches.py    groups builds into patch windows (changelogs; notes-less big builds get their own)
pipeline/match.py      -> data/patches/<id>.json.gz  notes lines ⇄ data changes; documented/described/hidden/mismatch/fix
                          (+ line statuses heading/untracked/nodata; change status unreleased; extras: every
                          console variable (noted ones first) and texts uncapped; loc rows cut at 400)
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
| Shop look and sounds from the local game | `python tools/extract_shop_assets.py` |
| Page performance (scroll p95, elements, layout / style time; before & after) | `python tools/perf_probe.py [--urls …] [--label before]` |

## Build speed

- **The patch archive is read once a build** (`builders/archive.py`): `index()`, `by_date()`, `patch(pid)` and
  `gameplay(pid)` (= `cards.gameplay_entities`) are cached for the whole build. Every builder that walks the
  patches goes through it (entity histories, change matrices, history squares, home feed, patch / build / errata
  pages). **The cached records are shared: no builder writes into them.** A page that needs an extra field copies
  first (`patch_page` builds `change_by_key` from `{**c, 'ent_name': …}`).
- `common.ids_to_names` is memoised per string, tied to the catalogs it read; `render.readable_value` and
  `trail.trail_html` are `lru_cache`d; `cards.change_rows` calls `is_engine` once a row.
- `build_site.sync_tree` copies only new or changed icons and sounds (size + modification time) instead of
  `copytree` rewriting ~1,400 files every build.
- Site build: 10.6 s → 6.0 s (patches 3.9 → 2.1 s, builds 2.3 → 2.0 s, entities 2.8 → 1.5 s, home 0.5 → 0.1 s).

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
| code (line) | the line is about a hero / ability / item whose gameplay files did not move in the window nor within `LATE_DAYS` after it ("Vyper: Sliding uphill now allows for lateral movement"): the change lives in the game's code, which is not compared (`match.code_lines`, last pass). Not for lines with numbers (more likely our miss) — those stay unmatched; a quiet line about sounds or looks becomes untracked instead |
| unmatched (line) | should be in the data but no change was found — a real matcher gap |

## Tags (badges)

Chosen from what the data contains (all patches, 2026-10-01): NEW 20k, DEL 11k, NERF 5.2k, BUFF 4k,
CHANGED 2.5k, MECH 0.9k, availability 92. The badge never repeats the percentage (the value cell has it).

| Tag | When |
|---|---|
| NEW / DEL | field or entity added / removed |
| BUFF / NERF | numeric change, direction by the polarity of the PROPERTY's own name (`semantics.property_name`, not its container: "Cost" in `m_MapModCostBonuses` flipped 110 investment bonuses); "Reduction / Refund / Decay" after a lower-is-better word turns it around (Cooldown Reduction); lower-is-better values compare with their sign (an enemy healing penalty −65 → −70 is stronger) |
| UP / DOWN | numeric change on an object both teams have (troopers, guardians, walkers, camps, pickups, game rules): the number went up / down, no better/worse — except `semantics.PLAYER_SIDE` (camp bounty, powerup strength, shorter respawn / spawn timers), which are BUFF / NERF for whoever takes them |
| REWORK | an upgrade tier whose bonuses were removed and added in one patch (`render.fold_tier_swaps`) |
| MECH | mechanic field (behaviour flags, dependencies) without a direction |
| CHANGED | value without a known direction |
| ON / OFF | availability: `Disabled`/`In Development` truthy = OFF, `Player Selectable`/release state = ON; a "Disabled On Heroes" list that grew = OFF, shrank = ON |

On hero and patch pages changes are grouped: patch or hero → one header per ability (icon, name, tag
counters) → its rows without the name repeated. Abilities re-created under a new id borrow the icon of
their namesake with the same owner (`common.entity_icon`).

Tag look (`render.tag_badge`, the only badge markup, used by all builders): the word in the UI font
(600 11px uppercase), one width for every tag (`--tag-w`, 80px: CHANGED fits), a muted tint of the tag
colour with a 2px bar on the left, and one fill. The size of a change is shown by the % next to it, never
by the badge. The % is coloured text whose ink strength follows `data-g`, not a second box. There is no
clip-path, because it cut the focus and "chosen" rings. The tag's pixel icon is the badge's CSS
`::before`: a mask per tag (`pixel_icons.tag_mask`, written into styles.css as `.tag.<t> { --ti: … }`),
drawn in the badge's own colour. `tests/test_entity_page.py` keeps the CSS in sync with `TAG_ART`. Counters
(`render.pip`) draw the badge's mask (`.pip.<tag>::before`). A chosen filter tag is `aria-pressed="true"`,
never the class `on`, because `.tag.on` is the ON tag's green.

**One counting rule.** Every counter on every page (home summary, patches index, heroes index, card
headers, ability sub-headers, history bands, the 12-patch strip) counts `cards.player_facing(changes)`:
renamed fields merged, swapped upgrade tiers folded into one REWORK (per entity, never across abilities),
engine plumbing (`cards.is_engine`, the "Technical" fold) left out. A patch that only touched plumbing is
not the hero's "last change" and does not take one of the three open history bands. `cards.player_facing`
is memoised on the identity of the change dicts; it ran 96k times on ~23k inputs.

**One count of "not in patch notes".** "Not in patch notes" — the eye — is ONE status set everywhere
(`render.NOT_IN_NOTES` = hidden and unannounced; `not_in_notes(c)`): what Valve did not write down, including every
change of an update that had no notes at all (Rat King's build 6736 lost its eye and dropped out of the eye filter
when only hidden counted). Such a band's eye chip reads "no patch notes". Work on a hero still in development
(unreleased, "Before release") is not it. A patch's numbers come from ONE function (`builders/patch_counts.py`,
`for_id(pid)`): `not_in_notes` (the eye's number everywhere), the per-status counts, and `hidden_on_pages` — those of
them a hero, item or unit page shows by THE pages' keys (`patch_counts.page_set` = `entities_pages.page_entities` /
`page_keys` over the keys with changes of their own), so "N of them in game rules & map objects" is exactly what the
Game section shows.

The home icons route rows by THE pages (`home_page.page_route` over `patch_counts.page_set`, the catalog's
owner / units, unit families via `patch_counts.unit_main`), not by the patch record's name: unnamed units
(Neutral bug, Medic Trooper) are on the home page.

`patch_counts.count` counts the console variables, and one edit over a unit family's members or a Game
system's entries once (`_counted_as`: the family page, the Game system; a rule for every hero is its Game
system's, row by row). Left: a shared edit counts once in the banner and on each target's icon; scenery and
template rows only the patch archive lists are in the banner's Game number but on no icon.

**What a page lists** starts at `cards.gameplay_entities` (gameplay rows only; one object kept under
several ids with the same edit — Walker's `alt_`/`_weak` copies, two crate ids — merges into one
"Walker · 4 variants" card, `cards.merge_variants`). Inside a card, 4+ rows of one family (labels equal
but for a number: "Level 19…36: souls needed", "Vitality investment, step N") fold into one summary row
with the % range (`cards.family_rows`).

**Labels for structures the game never labels** (`semantics.plain_label`): level table ("Level 22: souls
needed / gives a boon / ability points"), investment bonuses ("Vitality investment, step 5: bonus"), the
hero's kit ("Kit: Ability 3"), powerups ("Powerup: Fire Rate (early game)"), the pellet pattern, walker
stages ("Health (empowered, stage 1)"), weak points. `humanize` drops `m_` and Hungarian prefixes even
before a lower-case letter, keeps plural acronyms (NPCs) and turns "In Seconds" into "(s)". Values:
`render.readable_value` turns engine enums into words (`EHeroDevState_PreRelease` → "Pre Release").
Not gameplay (`pipeline/classify.py`): vote stickers, AG2 names, rich presence, HUD/name offsets, unit
name keys, trooper hit-react clips → visual/ui; collision hulls, soul-orb flight physics, NPC sight → technical.

A field added then tuned within one patch window is NEW, tuned then removed is DEL (`match.merge_ops`);
a renamed field (DEL + NEW, same label) is judged like any change, and dropped when only its unit changed.

**An entity back after a removal** (build records: `status: returned`; Valve cut unrevealed heroes'
kits out of the files until their reveal) is diffed against its last version before the removal
(`history.entity_changes` keeps the removed entity's blob): the patch shows "Back in the game files"
plus "was → now" for what changed meanwhile. Removed and back inside one patch window → field changes
only. Old schema shapes are rewritten into today's when flattening (`flatten._legacy`: the flat
`m_BulletSpeedCurve` of builds before 5747 is `m_flBulletSpeed`), so a format change is not a game
change and old bullet-speed tuning reads as Bullet Speed, not an engine detail.

**A newly added entity** (build records: `status: added`) is one NEW thing: its counters count 1,
its card shows "Added to the game files · N fields", the stats a player compares and its own abilities
(`cards.ADDED_KEY`, at most 12), and folds the rest (level tables, item-cost curves every hero shares)
under "All fields".

**Folded tables** keep thousands in their range (`cards._NUM_IN_LABEL`: "6,400–28,800 souls").

Polarity notes: an interval between an effect's ticks (`HealInterval`, `TickInterval`, `DamageInterval`…)
is lower-is-better — Infest Heal Interval 3 → 2 is a BUFF. A property the game marks as the holder's own
downside (`m_bIsNegativeAttribute`, drawn red in the tooltip; `enrich.drawbacks`, the change carries
`drawback`) grows as a NERF whatever its name says (Golden Goose Egg's damage penalty −10% → −15%). Path rules in `semantics.POLARITY_RULES` come first; a flag
row's tag comes from `pipeline/flags.py`. A hero's signed base stat (m_mapStartingStats) has a signed percent
too: −20% → −15% is +25%.

Audit of the patch pages (2026-10-01):
- a field added or removed with a 0 / "no" value changes nothing (`cards.is_noop`; a field tuned to 0
  inside a window kept its first category and showed "Explosion Radius 0 · NEW");
- a field that appears with the value Valve says it was raised to takes the notes' old value
  (`match._old_from_notes`: "Headshot stack count increased from +2 to +3" while the files only gained
  `HeadshotStacks = 3` is a BUFF 2 → 3, not a NEW);
- a tier's scaling bonus names what it scales with (`semantics.scaling_suffix`: "(weapon damage
  scaling)" for `EBaseWeaponDamageIncrease`, spirit otherwise); numbers below 1 keep 4 significant
  digits (0.0003 → 0.00035 read "0.0003 → 0.0003");
- ability card texts fill `{s:X}` through the property's `m_strLocTokenOverride` too, `{s:X_scale}`
  from the tier's scaling bonus and `{s:hero_name}` with the owner (`abilities._tokens`: "for
  BuffDurations" in 40-odd upgrade lines);
- `m_bWarnIfNoAffectedAbilities` (an editor check) is technical; the screen flash on taking damage
  (`EFlashType_*` in generic_data's `m_mapDamageFlash`) and where a gun's bullets leave the model
  (`m_vecOriginOffsets*`) are visual, `m_bIsHiddenOverhead` / minimap `vOffset2D` UI, a trooper's
  self-destruct sound names audio — they had read as balance or mechanics;
- an item's Corrupted version (City Never Sleeps: the Broker trades a high-tier item for it — bonuses
  plus random penalties, `m_CorruptedItemInfo`) appearing or going at once is ONE row "Corrupted
  version: Cooldown -4, Base Health +10" and one change for every counter (`render.fold_corrupted`;
  474 NEW rows → 97); a later tweak of a few bonuses stays row by row;
- ability cards leave out zero values with a unit ("+0m") and print a unit once ("+3m", "4m/s" —
  the postfix " m" doubled it on 47 rows).
- a hero page's cards are what the hero binds now (`hero_page.current_cards`: the guns and the four
  ability slots); abilities still in the files but no longer bound (Calico's Nekomata Ward, Catform
  pounce) and the shared movement abilities get no card — their changes stay in the history below.

Five-auditor review of every build and page (2026-10-01, record format 5, enrich 17):
- classification by the value's shape as well as the field's name (`classify._value_kind`): sound events
  ("Ability.Bebop.Hook.ImpactGeo") audio, file paths visual (a `.vcss` HUD style UI), loc keys
  ("#AbilityButtonHint_…") UI, unix times meta; "20m" in a record is a number (`_is_num`), not a mechanic;
  what a value scales with / which stat it feeds (`WIRING_RE`) is a mechanic when it CHANGES; light melee,
  *Effectiveness, ModelScaleGrowth, recoil and Puddle Punch are gameplay, not visual;
- polarity: `_LOWER_FIRST` / `_HIGHER_FIRST` whole-name lists checked before the word lists (post-cast,
  arm time, gravity, respawn health, the enemy's damage taken…); a T1-T3 / Enhanced bonus to a debuff
  stored negative compares magnitudes (`enrich.negative_props`, `neg_base`); "no limit" values (-1, 9999)
  have no direction; the same value written another way (units → metres, 1 → 100%) is no change
  (`semantics.reencoded`, `same`);
- units: engine floats named like lengths are metres, like speeds m/s (`semantics.engine_unit`, `SPEED`;
  `display_raw` never divides a value already in metres);
- labels: an item's upgrade entry is its "Enhanced" version; a coefficient names what it scales with
  ("(boon scaling)", `scale_stat`, `scaled_by`); "(% of base)" for EMultiplyBase;
- records: numbers in lists keep their order (prices per tier, resist per enemy count, spreads);
  a flat bullet-speed curve wins over a field beside it (Haze before 5747);
- owners: real heroes before the templates (hero_base had Infernus' gun); a sub-ability no hero binds
  goes to the hero its id names (`hero_bound_abilities(heroes, abilities)`);
- names: Shrine, Mid-Boss, Mini Turret (`data/overrides/unit_names.json`); helpers of any unit kind;
- tables: units show the Shrine's 2nd phase and the Patron's growth / backdoor regen; items' Stats are
  what the item always gives (no `ConditionallyApplied`), innate Spirit Power counts;
- cards: "+4×Boon" / "×Weapon Damage" for what a coefficient multiplies, m/s speeds, no zero bonuses;
- values carry the unit the tooltip prints (`semantics.prop_unit`: the loc `<prop>_postfix`, also of the
  property's m_strLocTokenOverride; `with_unit`) — "Cooldown 30s → 38s", not "30 → 38" — and labels use
  the override's own label ("Shield Duration", `override_label`; enrich keeps `loc_token` / `unit` on
  the change, MChange carries `unit`) (enrich 18);
- a tier bonus to an enemy debuff written as a negative compares magnitudes even when the base is 0
  (`_ENEMY_DEBUFF`: Enemy Dash Slow −25 → −22 is a nerf);
- labels of nested fields read as words (`semantics.context_label`: `CONTAINER_WORDS` "Projectile ›
  Speed", "Heavy melee › Cooldown On Hit"; `FLAG_FIELDS` "Behaviour", "Can target", "Interrupted by";
  a modifier's script value named by what it changes, "Aura › Bullet Armor Damage Resist") (enrich 20);
- a hero's base stat keeps only a length, speed or time unit (the stat panel's "%" postfix is for
  bonuses: "Crit Bonus Scale 1% → 0.8%" was a multiplier); stamina per second shows as the game's
  stamina cooldown (`describe` → `invert`, `semantics.show`: 0.2 → "5s") (enrich 21). The Hero Stats
  table keeps the owner's sheet layout (Stamina Regen per second).

Hero mechanics audit (2026-10-02, record format 6, enrich 22):
- a dash covers a fixed distance (`EGround/AirDashDistanceInMeters`), so a longer dash duration is a
  NERF (`_LOWER_FIRST` dashduration / airdashtraveltime); the mantle / climb-rope slow on the player
  is better smaller (`_SELF_SLOW`, on the whole path); parry's victim damage taken is better bigger;
- engine floats Valve already writes in metres (`…InMeters`, `…Meters`) or m/s (rope climb speed,
  the dash's drag thresholds) are shown as is (`semantics.METRES`, `MPS`);
- table rows keyed by the number that names them (`flatten.NUMERIC_ID_FIELDS`: an investment step by
  its souls threshold, a purchase bonus by its tier) — a step inserted at 6,400 souls no longer shifts
  every later step; the Vitality investment's two unit switches (% of base health ↔ flat HP, builds
  6044 and 6403) have no direction;
- the bullet-speed curve wins over the field only before 5747 (`flatten(curve_wins=…)`, history passes
  each side's era; `hero_table.bullet_speed` reads the build): Graves / Silver / Apollo carry a
  placeholder curve of 22500;
- the spirit-resist-per-boon key renamed at 6541 (`…TECH_ARMOR_DAMAGE_RESIST` → `…TECH_RESIST`) is an
  alias, and the Hero Stats column reads both; range per boon is metres; heroes in development bound to
  another hero's gun (`hero_table.borrowed_guns`: Infernus' as a stand-in) show no gun numbers;
- base stats: run / sprint speeds in m/s (Valve's postfix says "m" since 2026-01), times in s,
  resists keep "%", multipliers do not; "Headshot Damage Taken ×" over the game's "Crit Reduction";
  powerup labels no longer cut "_PERCENTAGE" ("Cooldown Reductionage"); a heavy melee's turn rate is
  gameplay; a rule for "All heroes" is unreleased only if every hero it touches is.

Audit follow-up (2026-10-02, enrich 25):
- shares the game writes 0..1 and the notes as percents are shown ×100 with "%"
  (`semantics.FRACTION`, `_FRACTION_FIELD`: move speed while shooting / zoomed, damage at falloff
  end, boss / NPC damage scale, instant gold share) — "0.55 → 0.7" reads 55% → 70%;
- an ability property that is a travel speed and carries no unit is engine units per second
  (`semantics.prop_speed`: Zip Speed 693 = 17.6 m/s, toss / leap / reel / return / projectile
  speeds) and so is a flat T1-T3 bonus to one; move speeds, attack speeds, slows, turn / tracking /
  sweep rates, cameras and distances named after a speed are not; a value written "20%" keeps its
  percent whatever the field (`display_raw`);
- a curve's `m_vDomainMins` / `m_vDomainMaxs` read "Domain (min)" / "Domain (max)";
- NPCs bind abilities like heroes (`classify.unit_bound_abilities`): Walker's Stomp / Laser Beam /
  Rocket Barrage, Patron's gun. The catalog keeps `units` on such an ability; it moves UP / DOWN
  like its unit (enrich and `match.change_json` judge it as 'unit') and its history sits on the
  unit's page (`history_table(line_names=False)`: "Rocket Barrage" is also a hero's ability);
- an entity added or removed counts on the patch page when it matters (`match.event_worthy`): the
  player-facing kinds always; another ability when it has a name or an NPC binds it (Splatapult's
  removal; the name a removed ability had comes from the catalog, `match.event_name` — its text
  leaves with it); a rules / pickup entry when its fields are gameplay (the permanent ammo pickup,
  `m_RejuvParams`) — a removed one by its id's category; a hero's melee never (the hero's event);
- an NPC's abilities also count on its row of the unit changes matrix (`dynamics_page._collect`);
- values in a line's proof and in a matrix tile's card go through `render.shown_value` (ids as
  names); a hero in development with no name in any build is `pretty_id` ("Airheart"), never its id;
  `common.ids_to_names` also replaces any snake_case word the catalog knows (a dev hero's
  `fathom_reefdweller_harpoon`); `readable_value` reads a flag list word by word;
- 9999 / 99999 (the game's "no limit") print as ∞ (`render.shown_value`), so 9999 → 99999 is no
  change;
- a list of numbers is a value, never a flag set (`render._flags`: a recoil range "-0.1, 0.1" read
  "+-0.1 +0.1"); a script / modifier value is named by what it changes, its value leaf dropped;
- tooltip texts: a value's own unit yields to the text's ("{s:X} m/s" with "1.2m"), entities are
  unescaped once (`abilities.fill`); a key binding with a form word reads as [Key] (`_KEY_HINT`);
- update-data commits only on top of the main it started from; when main moved meanwhile (or the
  push loses that race) it resets to the new main and regenerates data/ there (up to 3 times),
  never merging or rebasing generated files (run 36896244450 went red so); any other push failure
  fails at once.

Data-quality audit (2026-10-04, record format 7, enrich 29):
- shared abilities: an ability more than half of the real heroes bind (at least 3: jump, dash, mantle, slide,
  sprint, climb rope, zipline, zipline boost, parry, the voting poster) belongs to every hero, so to none
  (`classify.shared_abilities`): no owner, kind `shared` in records, entities.json and abilities.json; units
  do not claim them either. The first real hero in the file (Infernus) had taken them all — 135 of the 295
  rows on his page. They have their own page, heroes/shared.html (`builders/shared_page.py`, linked from the Heroes index toolbar), a row
  "All heroes · movement & shared" in the hero change matrix (`dynamics_page.SHARED_KEY`) and search rows
  (#ab-<id> filters the page); the patch archive lists them as cards of their own.
- one label per field: enrich keeps each build's own words (`label`, `label_src: 'fallback'` when the label is
  the field's name, `unit`, `sign`); `pipeline/labels.py` builds, per (file, entity, path), the label the
  NEWEST build's text gives it, else the last label Valve ever gave it, else the name split into words; the
  newest non-empty unit; the newest sign. The matcher matches note lines against the window's own label
  (`MChange.label`) but writes the canonical one (`MChange.shown`) and re-renders `old_s` / `new_s` from the
  raw values with the canonical unit (`labels.display_unit`: an old bare number takes the unit Valve added
  later — no record holds a bare length of 40+ engine units under a field that gained "m"; a speed's "m" is
  m/s). Build records (the archive's build pages) keep each build's words. Ability cards use the same
  resolver (`abilities._label`), so a card and the newest history row agree, and list a property once per
  section. A loc text that is only a qualifier ("(Normalized)") is no label
  (`semantics._names_something`). When the newest text still labels a field but prints no unit, or another one,
  where older text printed one (Valve dropped or replaced it), the field has no canonical unit: each window prints
  its own text's unit (`labels.resolve` → unit None, `display_unit`), and the row across the switch
  (`labels.unit_switch`, from the per-build unit steps `collect` keeps) prints each side in its own unit, CHANGED
  without a percent (`match.MChange.old_unit`, `unit_switch: true` in the patch JSON; `render.vals_html` then
  does not copy a unit across). A unit only ever added stays one unit for every row, as before.
- enemy slows: a property whose tooltip prefix is "-" (`semantics.prop_sign`: the game prints "-30% Move
  Speed" over a stored 30) is labelled by what it does to the enemy (`semantics.enemy_label`: "Movement
  Slow", "Fire Rate Slow", "Bullet Resist reduction (Heavy)", "Parry Cooldown reduction") and shown as its
  size (`show(..., magnitude=True)`); BUFF / NERF still from the raw value (a smaller slow is a nerf). A slow
  stored −30 in one build and 30 in the next (Card Trick 2026-08-12) is one value.
- sign flips: `cards.is_noop` keeps signs ("−22% → 22%" is a change); a flip that comes with the property's
  provided type flipping (REDUCTION_PERCENT → INCREASE_PERCENT: Riposte, Gloom Bombs) is the same value
  written the other way round (`match.mark_retyped` → `same`).
- units: −1 is never turned into metres (`display_value`); recoil, turn, spin, decay, blend-bias and penalty
  fields are not lengths or speeds; "…MeterPerSecond" is m/s already; an engine float ENDING in a length word
  is a length ("Nearby Enemy Resist Range" 2000 = 50.8 m); an ability property named like a length that no
  build gave a unit is engine units when its numbers pass 20 (`semantics.length_in_units`: "Lift Height
  120 → 200" = 3.05 → 5.08 m); a property is a speed wherever "speed" sits in its name (`speed_prop`:
  "Active Movespeed Penalty 4.5m/s"); a label drops "(m)" / "(s)" when its value carries the unit;
  "Verticall" → "Vertical"; corrupted bonuses carry their property's unit.
- an identifying field spelt with other capitals (Valve's `m_StrPropertyNAme`, Shadow Transformation
  2026-03-06) still keys its list (`flatten._id_case`): the T2 cooldown bonus reads "T2: Cooldown −25s →
  −20s NERF", not "Ability Upgrades #2 › Property Upgrades #2 › Bonus" BUFF.
- names: a weapon-class ability's upgrades are T1-T3 (Venator's ultimate), map keys that are ids read as the
  game's names ("Item Draft Weights › <item name>"), an NPC ability whose only text is its unit's name has
  none (`catalog.drop_unit_names`: the Patron's "Aoe wave", not three "Patron" groups), stand-ins say what
  they are (`common.pretty_id`: "Ability 1", "Weapon (shotgun)").
- values: `render._sentinel` keeps a real −1 — a T1-T3 / Enhanced / Corrupted bonus (".m_strBonus") or a
  value whose other side is another negative number (Sharpshooter's −0.5 → −1 m/s); `cards.merge_renames`
  does not pair a removed and an added bonus of another property AND another unit (Shoulder Charge's T1
  "25% → 2.2"); the hero page's weapon cells show two decimals (Reload 1.06, not 1.0575).
- tracker upkeep commits (a subject without a build number: "cleanup", "Dump exe, dedupe…") are not builds
  (`tracker.is_game_build`, `head_build`): no record (history takes what they moved as the new baseline; the
  next build names the build before it), the catalog and the cards keep the newest game build, and
  update-data names its commit after the newest game build ("tracker Dump" / "tracker Fail" on 2026-10-04,
  `None_92d2d9d0` = the 2025-08-23 "cleanup" with 498 loc rows).

Data-quality audit, part 2 (2026-10-04, enrich 30):
- plumbing by path: `cards._PLUMBING_PATH` drops, in every file, a modifier's mid-boss / effectiveness /
  refresh / time-scale / target-filter / buildup switches, dependent-ability lists, model scale, the Patron's
  observer origin and the deploy checks unless a note named them; `_PROPERTY_WIRING` also drops
  `m_nRequiredUpgradeBits`; a shotgun's pellet offsets never show (`_PELLETS`, labelled "Pellet pattern" in
  the archive); `cards.is_noop` drops an empty block added or removed. Rows are never hidden because of
  where their label came from.
- container words: a container named after its modifier loses the word ("Grab › Duration",
  `semantics._MODIFIER_TAIL`, not on the leaf); `CONTAINER_WORDS` names the Rejuvenator buff, "On target",
  "Build-up", "Stagger"; `UNIT_FIELDS` the invulnerability aura range and the sight range vs heroes;
  `FLAG_FIELDS` "Applies" (m_nEnabledStateMask), "Immune to" (m_nDisabledStateMask), "Aura affects",
  "Item slot", "Activation", "Reduced by CC diminishing returns".
- gameplay flags (`pipeline/flags.py`): a modifier's m_nEnabledStateMask is a mechanic (it was technical); for
  target types, interrupting states, enabled / disabled state masks, attributes, cast behaviours and target
  flags a vocabulary lists the bits a player plays with — words and the side an ADDED bit takes for the owner
  (+1 / -1 / 0: a lockout state has no side, it can be the holder's own or an enemy's debuff). Interrupting
  states count -1 each, target types +1, a disabled-state mask +1 (an immunity). A row shows when a listed bit
  moved (`flags.is_gameplay`; bits that read the same, DASH_DISABLED → DASH_DISABLED_DEBUFF, cancel out),
  with only the listed bits in words ("+ignored by troopers and neutrals", "+neutrals", "+can't be purged");
  quick-cast UI and internal states stay plumbing. Enums read as words ("Item slot: Spirit → Vitality",
  `flags.enum_words`, also `render.readable_value` for EItemSlotType_*). `flags.direction` gives BUFF /
  NERF when every moved bit goes one way; the records carry `flag: true` and `render.tag_of` uses the
  direction even for a first bit added (op add). The matcher links a state mask only by the states that
  moved (`match._STATE_MASK`), never by the modifier's container words. A flag field whose moved bits are all unlisted shows them the engine's
  way (`render.flags_html`; they are Technical rows). A chip's colour is the side it moved the owner to
  (`.flag.good / .bad / .even`), not added / removed. The disabled-state mask has its own nouns
  (`flags.IMMUNITIES`: "Immune to +dash lockouts +disarm +slows"); *_Invalid / NONE enum values are no value
  (`flags.enum_words`); the same bits in another order are no change (`cards.is_noop`); the matrices' hover cards
  read a flag row as its moved bits in words (`dynamics_page._sample_values`, `render.flag_moves`).
- polarity: `semantics.POLARITY_RULES` (path regex → side, each with its note) wins over the name rules —
  ActiveReloadPercent, RecoilRecoverySpeed, MoveSpeedPenaltyPerStack (an enemy slow) +1; SummonFrequency,
  BonusBuffsPerGold, MinimumDamage, Goo Ball's m_DamagePreventionModifier.m_flDuration -1. A hero's own
  base stat compares with its sign (a negative resist is a penalty). A negating word before the lower-is-
  better word counts too ("Reduce Cooldown On Hit"). Offsets, pitch limits, aim bias, damping, friction and
  springs are neutral; a shotgun's scatter scales lower-is-better. `semantics.is_sentinel`: 9999 always,
  -1 only against a non-negative other side; -2 is no sentinel.
- "no limit": `render.shown_value` prints 9999 as "no limit" (was ∞), the same word `render._sentinel` gives
  -1, so `cards.is_noop` sees "9999 → -1" as no change; `_SENTINEL_WORDS` says "default" for a charge delay /
  spin-up / spread-decay -1 and "permanent" for a modifier's duration.
- renames: `cards.merge_renames` also pairs a DEL with a NEW of the same entity and tier when the values
  are equal and the names say the same thing (`cards._alike`: labels with other
  numbers in them are never one field (investment thresholds, "Level N", "value #N"); with the same value, last
  label part ≥ 0.75 alike, one label's words inside the other's, or — for ability properties and T1-T3 bonuses
  only — one property name inside the other ("FlameAuraDPS" / "DPS"; a bare engine leaf such as m_value names
  nothing); with a new value only a respelling (`cards._respelt`: as many words, letters ≥ 0.9 alike: "Picup" →
  "Pickup"); a word more or less ("Damage Taken" → "Damage", "… Max", "Imbued …") or another word in its place
  ("Spirit Damage" → "Base Damage") stays DEL + NEW. A flat number and a percent are one value only at 0 or when
  the bare field's name says percent (`cards._same_value`: Blood Bomb's "Self Damage 30" → "Health Cost 30%" is
  two rows).
- matcher: `match.twin_hits` — a matched line also claims, in the entities it matched, a changed field of
  the line's tier that it names by a word and that moved by its exact numbers ("Ability Range" range AND
  radius multiplier, "damage and debuff resistance" bullet AND spirit resist); `match._aligned_pairs` —
  "from A … B … to C … D …" pairs numbers that have words between them when both sides read alike (not
  'changed from "X" to "Y"' nor "changed from -56s Cooldown to Impact Area Stuns"); `_ITEM_TIER_MOVE` —
  "Moved from T4 to T3" is the item's tier; a fix line's pairs also run reversed ("being 3 instead of 1.5")
  and its status stays "fix"; LABEL_SYNONYMS cooldown ↔ chargeup.
- scenery: `classify.decor_entity` (the city's traffic, glass panes, team colours, minimap offsets, district
  names, timer placement) — no gameplay event in `match._gameplay_entity`, their fields `visual` in enrich.

Data-quality audit, part 3 (2026-10-04, enrich 31):
- shared page (already described above in part 1, but expanded here).

Coverage audit (2026-10-05, owner: "I want to see ALL changes to everything in the game"):
- shared changes on their entities: an edit the files copy into 6+ entities (`diff.SHARED_MIN`) is one
  '@shared' block in a patch, and since this audit it keeps the KEYS of the entities it hit (`target_keys`;
  names are ambiguous: renamed heroes, "Melee"), the status of each target that differs from the block's
  (`target_status`: a note line named only that hero; a hero in development is `unreleased`), and its `scope`
  (`pipeline/shared_groups.py`): 'all' when its targets are `ALL_SHARE` (85%) or more of the entities of their
  kinds that the window could diff field by field, else 'some'. Before, 13,573 hero × row pairs and 278 hero
  patch bands were missing (Haze's Max Health 740 → 730 on 2026-05-22, Abrams' Ground Dash Duration 0.7s → 0.72s on 2026-07-28).
- `scope` on abilities.vdata is measured per FIELD too (`shared_groups.UNION_FILES`, `_field_rules`): the blocks of a
  window on one ability property are counted together, and when their union is a rule for all, each block is 'all'.
  Channel Move Speed went from engine units to m/s on 2025-08-18 for every ability and item at once (491 targets
  50 → no limit, 93 targets 50 → 1.3m, 6 targets 9999 → no limit): three "shared ×491" rows on 268 pages, now one
  link row. Not the heroes' file: there the blocks are base stats by archetype (Max Health 740 → 730 for nine heroes,
  790 → 780 for 26) a hero page shows as its own rows.
- `builders/shared_rows.py` spreads a block over its targets (`spread` / `entities`: each target's own key,
  status, catalog kind / owner / name; `shared_n`, `shared_what`, `shared_all` on the rows) for every entity
  view: the entity history (`entities_pages._history`), the trail squares and "last change" (`trail._index`),
  the change matrices (`dynamics_page._collect`), the home feed (`home_page.update_feed`). A block on some
  entities is an ordinary row with a chip "shared ×9 heroes" (`cards.shared_chip`). A rule for all heroes or
  abilities (`FOLD_FILES`: the level curve, investment and purchase bonuses, every melee attack) folds into ONE
  row "All heroes: N changes" that opens in place (`cards.every_rows`, `details.fam.shr-all`) and is counted
  apart (`shared_rows.is_every`): not in the band's counters, its eye count, the toolbar's "Not in patch notes",
  the matrices, the trail squares or the home icons. Units never fold: a kind of unit is a handful of ids, so a
  block on the five troopers (their 44-row rework of 2026-04-30) is the troopers' own change.

Announced features (hidden-story review 2026-10-05):
- An entity that came or went is "described" when a line of its window names it
  (`match.name_events`, `match_rules.event_phrases` / `names_event`): its name without a tier
  numeral and with the last word singular or plural ("Haunts (new neutral camps): … Barrel
  Mimics" = Barrel Mimic I-III), aliases for entries the files give no name
  (`match_rules.EVENT_ALIASES`: "Tough Crates", "Bell Tower") or that the notes call otherwise
  (`EVENT_NAME_ALIASES`: "Shrooms" = Slum Shroom). The line links the event and is no longer
  unmatched / untracked. Only the event: the new entity's numbers stay hidden.
- Lines that announce a whole feature without numbers cover the changes
  `data/overrides/blanket_lines.json` scopes to them, by field and kind of operation, never a
  whole file (`match.blanket_lines`, each entry with its "why"): 2025-05-08 "All hero stats
  rebalanced" (base stats and per-boon growth), "Adjusted objective health values" (building
  health fields), "Full shop rework, including many new items" (items added / removed only — the
  numbers of items that stayed keep the eye: audit TRUE_HIDDEN); Old Gods "an Enhanced or
  Legendary item" (the Enhanced bonuses that appeared), "Behold the Patrons" (add / remove of
  buildings and troopers only — Patron Health 5625 → 12000 keeps the eye); City Never Sleeps
  The Broker (a Corrupted version that appeared, the corrupted shop / price / penalty table),
  "Buff Containers" (the new permanent buffs and the statues' reward pools), the Street Brawl
  corrupted round. Runs after the unreleased pass.
- `render.fold_enhanced` (with `fold_corrupted` in `render.fold_versions`): an item's Enhanced
  version that appears or goes whole is ONE row "Enhanced version: Max Ammo +10%, …" and one
  change for every counter (on the item page, inside its "Enhanced version" group, "Bonuses").
- Not in patch notes, all patches: 6811 → 6000 (City Never Sleeps 596 → ~400, Old Gods 902 → 433,
  2025-05-08 1107 → 1003). `tools/audit_score.py` prints the eye's precision (TRUE_HIDDEN among
  the audited changes still called hidden: 28% → 32%); `tests/test_audit.py` keeps it ≥ 30%.
  60 verdicts for City Never Sleeps and Old Gods were added (tag `review-2026-10-05`).

Rules for all on an entity page:
- A rule for every hero or ability (`is_every`) is taken out of the band's groups
  (`history_view.split_every`) and shown ONCE per band: one block of link rows after the groups
  (`.hgroup.shr-band`), one row per (Game system, noun) (`cards.every_links`, `every_key`), its
  copies on each of the entity's abilities deduped (`history_view.every_sig`). The banner chip
  "+N for all …", the link rows and the strip tile's card count that one list. A band that holds
  only such rules (`pblock.every-only`) waits in place behind the toolbar's "For all heroes /
  items N" (`data-toggle-class="show-every"`, like "Before release") and gets no strip tile.
- `game_systems.place_all_row` routes a rule by its targets' noun first (a part's `nouns`:
  combat.melee "melee attacks", combat.guns "guns"), then by path; "Every ability & item" takes
  every `m_mapAbilityProperties` rule. Game pages drop rules for all from real entries
  (`game_pages.collect`): they are the part's own group there.

History bands:
- Every band with the entity's own changes stands open and is in the page (Sloppy's history reads
  as one document; 86% of 6,555 bands loaded folded). Bands of work before release and bands of
  rules for all only stay folded and are the only `<template class="hp-t">`s (OPEN_PATCHES /
  EAGER_PATCHES are gone). A history longer than 8 bands gets a year banner
  (`h3.banner.sub.hyear`) where the year changes; filters hide them. Perf (perf_probe):
  nano 9.5k elements p95 16.8 ms, haze 5.8k 16.8, atlas 5.6k 16.7.

Game section (2026-10-05, part 2; owner: "I want to see ALL changes to everything in the game"):
- 2,040 gameplay changes (1,340 not in the notes) were on no hero, item or unit page — the Soul Urn rework of 2026-06-04,
  crates, powerups, the Rejuvenator, soul sharing, the level curve, respawn times and soul rewards (console variables).
  The fourth section, Game, is everything no hero, item or unit page shows (`builders/game_systems.py`, `game_pages.py`,
  `game_rules.py`; config `data/overrides/game_systems.json`).
- Which entries: `entities_pages.page_entities` / `page_keys` are THE pages. The Game takes exactly the rest
  (`game_systems.place_entity(key, e, pages)`): map objects, game rules, effects, loot tables, abilities no hero owns,
  templates. Scenery (`classify.decor_entity`) is no page's.
- Systems: Souls & economy, Respawn, Hero progression, Urn & Unstable Rift, Pickups & powerups, Breakables & crates,
  Troopers & lanes, Neutral camps & Mid-Boss, Shop & item rules, Movement & combat, Modes, Other rules & objects.
  Each has parts (the page's filters). A rule is a regex tried from the start of a subject, systems and parts in config
  order, first match wins; subjects are an entry `file:id#kind`, a row of a rule for every hero / ability `file:@all:path`,
  a console variable `convar:name`. Names: the config's (the files give these entries no text), else the catalog's, else
  `pretty_id` without `modifier_` — never an id; templates say "(template)", loot tables "Loot table: …". Icons: a path
  under icons/ (game files) or `glyph:<site glyph>`; a missing one fails the build (`game_systems.missing_icons`).
- A system's page (`game/<id>.html`) is `history_table` over a composite key list, like a unit family: one group per
  entry in part order; identical rows of several entries merged into one group; a rule for every hero or ability once, as
  its part's own group; a part's console variables as one group "Console variables" (rows labelled by the variable's name).
  A template's change shows only where no heir has the same (path, old, new) in that patch (`game_pages.template_rows`).
  heroes/shared.html is a redirect to game/combat.html (anchors kept).
- Console variables (`game_systems.convar_changes`): a patch's rows per variable, first old → last new; only the
  server's (`gamedll` in flags), named by a part and not a test / display switch (`convar_hide`). Direction from the
  snake_case name (`convar_polarity`): more souls BUFF for the taker, a longer respawn / spawn timer NERF, comeback
  scales / ramps' times UP. Units read in the game's units (`game_systems.convar_unit` / `convar_number` / `convar_value`,
  config `convar_units`: [regex on the name, unit, scale], first match wins): a multiplier / ratio / percent stays a
  number, `_meters` is metres, `fraction` ×100 %, `_pct` %, a radius / range / distance / width / thickness / spacing
  / padding is engine units → m, the move-speed cap and leap / force speeds → m/s, durations / intervals / delays /
  windows / the respawn ramps and named times → s; a bare `_time` is no unit. Game rules shows "55m" for
  `citadel_bounty_aoe_radius` 2165.35, its hover history on the same scale (`data-unit`, scripts.js `hist-tip` appends it).
- Ids in values: `common.ids_to_names` also knows map objects, effects and loot tables (`_game_entry_names`, by
  `game_systems.name_of`) and reads an unknown `modifier_…` as words: Game › Breakables read "Pickup
  spirit_permanent_pickup → small_gold_pickup".
- Game rules (`game/rules.html`, `game_rules.py`): ONE table, a band row per system, every gameplay variable that
  exists today: its value now (its history on hover: the stats tables' `hist-tip`), how many times it moved, the date.
  No level curve or tier prices: the files list those rows only when they change.
- Game changes (`game/changes.html`): `dynamics_page.matrix_html(game_entries(), 'game')`, a row per system;
  `_collect` puts every entry no structure claims (`game_systems.claimed`), a template's change no heir shows, a rule
  for every hero / ability once and the console variables in `game:<system>`; the hover card names each change's
  entry (`table[data-what]`, scripts.js dyn-tip). Glyph systems draw the site glyph in the name cell.
- Home: four tiles (Game: 12 systems, its art the systems' game-file icons); the feed's fourth row "Game" (system
  icons with counts, eye, card). The banner's "N of them in game rules & map objects" links to the Game section.
- Search: every system and every named Game entry.
- Patch archive: the console variables tab lists every variable (noted ones first; `match.slim_extras` keeps them
  all), or "+N more on the build pages".

Name and description changes (`pipeline/entity_texts.py`, `builders/text_rows.py`):
- a loc key that IS an ability's / item's / hero's id is its name, `…_desc` its description, `…_tN_desc` a tier's;
  a window keeps first old → last new per entity and part, only when both sides have words and they read differently
  (markup or a token respelt is no change; a text that comes or goes with its entity is the entity's event).
- `entities_pages._history` files them under `text:<key>`; `history_table` adds them to the entity's group in that band:
  a rename is a row "Name  A → B", a description a fold "Description changed" (T1-T3: "T2 description changed") opening
  on the old and the new text, words that went struck through (`del`), words that came lit (`ins`).
- Never counted (no tag, no eye, no counter, no strip tile); a tag or the eye filter hides them; a group of texts only is
  "Before release" when every other group of its band is. A hero renamed in development carries "was Slork" in its head
  (`text_rows.former_names`). 1,084 such rows over all patches.
- "Icons without per-entity art" table, new row: "Game systems | a game-file icon per system in
  data/overrides/game_systems.json (souls, timer, Drop Soul Urn, the powerup ping icon, the trooper class portrait, a
  lantern neutral, the shop tab, the dash stat icon) or a site glyph (breakables, hero progression, modes, other)".

Matching, third pass (2026-10-02, P12/P13): synonyms are looked up the way `words()` writes words
(`rules.stem`: "radius" is "radiu" — `radius`, `souls`, `charges` synonyms never fired; "collision size"
/ "hitbox" now name a radius, "HP" is health); a subject-less line without numbers is checked for a
sound / interface / map topic before any rule (a fix stays a fix; "visuals" is no topic here: "splash
range much larger than its visuals" is gameplay); the respawn and gun-damage families take a line with a
number only (`NUMBER_FAMILIES`); an alias that IS a name the line uses stays an alias ("Base Guardian");
a subject-less line that names an entity changed in the window (`match.inline_names`: not inside
parentheses, not a name shared by more than 6 entities, a unit with its bound abilities) is that
entity's — its numbers need a word of the field, and failing a hit the whole patch is searched again
(`name_inline`); a misspelt hero prefix finds its hero (`_close_hero`, "Vindcita"); a line naming one
of the hero's abilities links on-topic fields of that ability first ("Siphon Life range…" is not
Seismic Impact's radius); Sinner's Sacrifice is an alias of the vault and its camp.
A line with several number pairs links the best field of EACH pair (`pair_hits`: "Base HP 6725 → 12500
and growth 470 → 200"); a line listing properties before one "by N%" links the best field of each
(`list_hits`: "respawn times, hp, and bounty"), a property without growth words never taking a
per-boon field ("Melee damage and growth"); "growth" is a label PHRASE (`rules.GROWTH_LABEL`: per boon /
per minute / boon or spirit scaling — not "Level 21: gives a boon") and points a hero line at the
hero's own stats; a numeric line that fell back to words links the fields sharing the most of its
words outside parentheses; "light / heavy melee damage … by N%" covers every hero's starting melee
damage (`DELTA_FAMILIES`, hero audit #11). A line with ONE number after "now grants / gives / has /
provides …" is a value that appeared (0 → N), after "no longer grants" one that went away (N → 0)
(`granted_pair`; the largest group of the 769 unmatched numeric lines: "Superior Stamina: Now grants
+75 Health"); a change to N counts too ("Now has a 8s cooldown" while it was 3s), the invented 0 is
never a rounding nor a mismatch (Valve reuses the property: "No longer grants +15% Spirit Lifesteal as
base stat" while the field went 15 → 16). Up to six words may sit between "from A" and "to B".
A patch that changes the number of boons rescales every per-boon value, and its hero lines quote growth
in the OLD scale (`rules.boon_rescale`): 2024-09-26 "Boon count increased from 11 to 14" + "Non-Health
boon bonuses rescaled…" (×11/14, health kept: "Kelvin: Bullet damage growth 1.2 → 0.9" is 0.707 in the
files), 2025-06-17 "total stat levels increased from 20 to 32 (but rescaled…)" (×20/32, all stats). Such
a field carries `MChange.scale`; `steps()` adds the new value in the notes' scale, so pairs and percents
compare like for like — these were "mismatch" lines, the mistake ours, not Valve's. The two patch-wide
lines link the boon levels and the plainly rescaled values (`rules.boon_lines`). A spawn timer says
minutes without the word ("Vaults spawn time/interval 10/5 → 8/4" is 600/300 → 480/240 s): small
numbers on a spawn / interval line with no seconds unit also try ×60. The golden statue alias holds
the containers that carry its timers; "vault(s)" is Sinner's Sacrifice. A typed field without "m_"
(`flCooldownOnBreak` of the shield trackers) is humanized like any field (`_TYPED_FIELD`, enrich 26).
A "mismatch" claims Valve's numbers disagree with the files, so the field must be the one the line
means (`mismatch_field`, review 2026-10-02: 24 of 41 were our wrong links): the line names every word of
the property (`names_whole_property`: "T3 +1 Charge → +2" is not the T3 Charge Delay) by a word of its
own — not a common word nor a word the subject brings ("guardian" → "tier": Tier2 Gold Kill) — or, for
a label of common words only ("Bullet Damage"), by all of them; only the pairs outside parentheses and
with two different numbers are judged ("(0->14%)" is a total; "changed from 0.2s cast delay to 0.2s
post cast time" moves a value). "X instead of Y" is a pair; "movespeed" / "firerate" are two words.
A change hotfixed across a window edge is one line (`late_landings` → `_chain_hit`): the field starts
at the line's A in its window and the same field ends at B later, step by step ("Lucky Shot: Damage
reduced from 125% to 110%" = 125 → 120 in build 5983, 120 → 110 an hour later in the follow-up's
5984). A late landing counts "damage" as a word. A hero's "Base damage …" is its gun's bullet damage
(`_BASE_DAMAGE`). `granted_pair` also reads "now (also) reduces / increases … by N", "now lasts N",
"is now N", and counts neither a tier name ("T3") nor an aside in parentheses as a second number.
Wordy lines (2026-10-03): a flag that came or went names a field by its words (`flag_words`: "No longer
interrupts sliding" = DONT_INTERRUPT_SLIDE_ON_CAST, "Multiple instances stack" = a modifier's
ATTRIBUTE_MULTIPLE; a hero line's flags only of the ability it names, filler words such as "can",
"cast", "use" left out — and then the ability's other mechanics stay described too); a label named
whole by common words links ("Bullet Resistance changed to Spirit Resistance": two words at least, or
one of its own); "requires" / "upgrades from" are components; "Removed from the game" / "is disabled"
is the subject's availability.

Patch notes, second pass (2026-10-01): a post's later patches ("03-10-2026 Patch:", "[ Follow-up … ]")
split off by date and joined per date (`news.dated_chunks`), a copy appended to an old post yields to
the patch's own post; short dated changelogs are notes (`patches.is_patch_notes`); a build of 1,000+
gameplay fields far from a main changelog is an update of its own (`HUGE_BUILD_FIELDS`); unreleased is
judged at the build a change shipped in; a line's percent must move the field the way its verb says
(`verb_sign`, a rate may move a time field the other way); number transforms follow the field
(`value_matches`: metres only for lengths/speeds, ×100 only for fractions, 1/x only for rates) and
`close` is relative only; minutes in a line also match seconds; the name index carries the name at the
build AND the latest one (Sinclair); an alias word inside a longer name the line uses is not an alias
(Veil Walker); a line naming an ability describes only its mechanics, never from a sound / visual line;
post headings ("General Changes ==", all caps) and Steam image placeholders are not lines.
Old Gods, New Blood (2026-01-22) comes from its update page (`data/overrides/update_pages.json`
"oldgods": cards, the hero schedule, "Also in this update"; the Patrons' lore is not republished).

The tracker clone follows upstream with `git reset --hard` (`tracker.sync`): it is a read-only
mirror, and the tracker's own `.gitattributes` (`* text eol=lf`) makes git see binaries such as
`vconsole2.exe` as modified forever, which made the fast-forward merge refuse updates.

## Visual system (design review 2026-10-01, three designer agents, four rounds)

- **Page weight and first paint** (2026-10-05): No inline SVG for icons. Status marks (`common.mark`),
  tag counters (`render.pip`) and category glyphs (`common.visual` without art) are empty spans; styles.css
  draws the shape as a CSS mask on `::before`. All masks come from `pixel_icons.svg_mask`; `tests/test_perf.py`
  and test_entity_page.py keep the CSS in sync with the art. Nano's page 483 → 330 KB, the archive's HTML
  81 → 63 MB. **Fonts never hold the first paint.** One Google Fonts request per page, loaded as `media="print"`
  `data-fonts` and switched on by scripts.js once it has loaded. With the fonts server answering in 2.5 s:
  DCL / first paint 2.7 s before, 35-250 ms after. A change-matrix tile of one tag is a class (`.dsq.s-<tag>`),
  not an inline gradient.
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
- Hero / item / unit pages ARE their history (owner, 2026-10-03: "closer to Sloppy"), in ONE centred
  column (`common.page(cls='entity')` → `<main class="page entity">`, max `--entity-w` 1180px). Head,
  today's values, strip, toolbar and bands share the same left and right edges. Before this, the history
  sat in 1120px pinned left under a 1640px head. Order: head (portrait / icon, name, chips; a hero's key
  stat tiles) → what it is today, OPEN (owner 2026-10-04: nothing folded by default). A hero gets a plain
  `section.now-open` with the weapon panel (all cells), the ability cards and the other stats as panels.
  An item's "Current values" and a unit's "Current stats" are `history_view.now_fold`, always `open`, and
  can still be folded; an item's sections sit side by side as cards. Then History. One function for all
  three (`history_view.history_table`): bands are managed as described in the History bands section above, over ONE panel.
  Each part (base stats, gun, each ability) is an `.hgroup.has-ic`: its icon on a framed plate in a
  column of its own (`cards.ability_plate`, scaled smooth, the ultimate marked with a gold corner diamond:
  `hero_page.ULT_SLOT`, `history_table(ults=)`), then its name and rows. A single-entity page has no
  sub-header. The rows are what the files changed (`cards.entity_rows`) plus the note lines that live in
  the game's code (status `code`). A row reads as a sentence: the label, old → new right after it, the %
  at the right edge, and a dashed ruler to it on hover (the values' own `::after`, no markup). A DEL
  row's old value is struck through. One mark only: the eye on what the notes left out. A unit family's tier table (`table.tier-grid`) is at least 420px
  wide on a desktop and fills the panel below 700px (390px phone: no sideways scroll on any of the 455
  hero, item and unit pages). An item's section cards fill the panel (`auto-fit`); a lone card stops at
  580px, so a label and its value never sit a whole panel apart. The ultimate's plate has the gold corner
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
  (`pblock.all-hidden`; the eye sat on 46% of hero rows); engine vocabulary — flag sets "A | B",
  `PBF_*`, `k_e*`, bone names, pellet `m_vecScatterOffsets` — is plumbing (`cards.is_engine`) unless a
  note line covered the change; ability chips merge namesakes (`data-f-ab="id1 id2"`), removed ones
  fold behind "Removed (N)", a chip without art shows its name; a lazy band carries `data-tags /
  -abs / -areas` so a filter stamps only bands that can match. Matrix tag chips SELECT (as here), not
  hide. Unnamed units (`unit_families.is_named`) sit with the helpers and stay off the home feed. An
  item page splits its "Enhanced: …" rows into an "Enhanced version" group (`history_table(enhanced=
  True)`, parts Base / Enhanced; the item's own group has no header).
- Round 3: a unit's AI wiring is plumbing (`cards._NPC_AI_LABEL`: attack range target, aiming spread,
  ability chances, weak-point count / respawn, sweep, model scale…; "Viewer" labels too); values read as
  said (`render._sentinel`: "-1" → "no limit" except "-1%", empty → "—"; `_same_unit`: "50m → 20m");
  family groups are named by tier only; buildings count as named; Unit Stats shows only named units,
  drops a column that repeats another (Walk = Run), a glyph where there is no art; the history toolbar
  is not sticky (Sloppy's scrolls away); home counters count what the pages show (`update_feed` over
  every patch).
- Patch strip (`history_view.patch_strip`, Sloppy's entity strip): the entity's latest 40 patches as ONE
  row of tiles over the toolbar, oldest → newest with the newest on the RIGHT, as in the change matrices
  and the trail squares (owner 2026-10-05: "новые справа везде"). The row never scrolls: tiles are
  `flex: 0 1 30px` (min 14px) and shrink to fit the column; below 760px only the newest 15 show
  (`nth-last-child`). Tiles are striped by tag (`dynamics_page.stripes`), show the count, and carry the site's eye (a
  CSS mask, `--mask-eye`) when the notes left something out. A tile opens `#p-<patch>`. Hovering it
  shows the hover card (below).
- Hover cards (scripts.js `dyn-tip`, ONE renderer `card()`): a change-matrix cell, an entity page's strip
  tile, an ability card's trail square and its "last change" link, and a home feed icon. Each card shows
  the patch (named ones in gold), counts by tag, "N not in patch notes", and the biggest changes (tag,
  eye, field, old → new). On an entity page they are grouped by ability with its plate. The data is ONE
  JSON blob per page, parsed on the first hover: `script.strip-data` (`history_view.strip_data` /
  `tile_card`: per tile per group the counts, the hidden count, and samples ranked across the patch;
  the strip card lists the top `TILE_SAMPLES` 6, a trail card the ability's own up to 4) and
  `script.feed-data` on the home page (`home_page.chip_card`, 2 per icon). The older bands are
  `<template>`s, so a card never reads the page. The change matrices' blob is parsed on the first hover
  too and shared with `dyn-parts` (`window.__dyn`). Tiles carry `aria-label` and no text tooltip, so two
  tooltips never stack. A card also opens on keyboard focus. A card's "biggest" (`history_view._rank`, also the home feed's
  `chip_card`) is the size of the % and then the tag order. A NEW / REWORK / DEL row without a % counts
  as 100%, so a release card shows what was added and not two small base-stat NERFs. The change
  matrices keep their own order (`dynamics_page._collect`); that is the owner's call.
- Links inside a page (scripts.js `patch-anchor`): a strip tile, a trail square (`trail_html(local=True)`:
  `#p-<patch>` with `data-ab`; mixed buff+nerf patches are striped, not REWORK purple) and an ability
  card's "last change" (`trail.last_counts`, its tag counts) open the band on this page. This works even
  when a filter or "Before release" hid the band or
  only the ability's group (`window.__histReset(dev)`: the group is checked on its own, because the band
  can show through another ability's rows), and even when the address
  already names it. A square scrolls to its ability's group and lights it briefly. On the patch archive
  the squares still link to `patches/<id>.html` with a text tooltip.
- Round 4 (advisor, a player's eye): one wording — "not in patch notes" for the eye (toolbar, banners,
  home), "Before release" for work on a hero before it shipped, "First seen <date>" (`common.first_seen`)
  instead of a build number. Labels split from field names use the game's words
  (`semantics.game_words`: Tech → Spirit, Armor Damage Resist → Resist; `m_vecIntrinsicModifiers` →
  "Passive"); a time field without a tooltip unit gets "s" (`semantics._TIME_FIELD`), a speed Valve
  writes as "20m" reads m/s (`speed_m` → `M_SPEED`, display only: the matcher's transforms are
  unchanged). Long values wrap;
  an entity event row ("Added to the game
  files", path `@add`) has no value cell. The newest update on the home page names its icons; stats
  tables explain their notch. A "changed in the newest update" notch on index cards was tried and
  dropped (owner, 2026-10-03): the newest update marked 1 hero, two weeks would mark 102 items — it
  told nothing apart; the home feed and the search answer "what changed lately".
- Namesakes (`cards.disambiguate`, `history_hints`): two fields under one label each get the words of
  their property name the label lacks; a bare one beside a hinted one gets its skipped words or "base"
  ("T3: Damage · base" / "· heavy melee"), a stat moved to a new name "old field" / "new field", an
  engine field its last path segment. Hints are computed over the entity's whole history, so a row
  reads alike in every patch. A property's wiring (scale-function switches, provided-type flags) is
  plumbing even where the notes spoke (`cards._PROPERTY_WIRING`).
- Home search (`builders/site_search.py`, scripts.js `site-search`): `search.json` = [name, page, what,
  icon] for every hero, its current abilities (`#ab-<id>` opens the hero filtered to it), item and
  named unit, fetched on the first keystroke; names that start with the query first.
- Weight: only the newest `EAGER_PATCHES` (6) bands are in the DOM; older panels are a
  `<template class="hp-t">` stamped when opened, filtered or named by `#p-<patch>` (Nano: 12k → 1.5k
  elements at load).
- Hero page head: every main non-gun stat as a tile (`hero_page.KEY_STATS`: health, regen, resists,
  movement, melee, spirit growth), values centred. Weapon panel (open, first under the head): six
  headline tiles (`hero_page.WEAPON_TOP`: DPS, Max DPS, Bullet dmg, Bullets/s, Ammo, Reload) and every other weapon number in an even grid below (units ride on the number). "Changed lately" is a corner notch.
- Hero page guns and sub-abilities: the ability grid holds the four Signature slots only and skips a card with nothing to read
  (`hero_page.has_content`). The gun is always the weapon block (`hero_page.weapon_block`): with a
  stats row its numbers, without one its name, last change, History link and trail plus "Gun numbers
  come with Hero Stats once the hero is playable". The alt fire (a Weapon_Secondary card) is a slim
  line "Alt fire" in the block (`_gun_links`); its history rows join the gun's group as "Alt fire: …"
  and a row the gun has in the same band is said once (`hero_page.alt_guns`, `fold_alt`).
  A nameless sub-ability no slot binds is named and drawn after the owned ability whose id it extends
  ("Ava · trigger", "Pounce · instant": `hero_page.sub_parents`), its rows the parent repeats in the
  same band go (`drop_parent_rows`), and the parent's toolbar chip holds it (`history_table(chip_of=)`).
  A removed chip whose name a current one has joins that chip's ids. A hero whose owner is another hero
  (`hero_page.borrowed_gun`) carries "No gun of its own yet", without name, last change, History or trail.
- Site shell (add to the Fonts / shell bullets): the site bar is a 3-column grid: brand left,
  Heroes | Items | Units centred, build badge right. On phones it is eye + scrolling tabs. The site shell does not centre wide tables. Centring every
  `.table-fade` gave the change matrices a 20-25px sideways scroll at 1700-1920px, and the first column
  slid under the sticky names. A stats table that should sit in the middle opts in with the item-stats
  track's `.table-fade.center`. Tooltips and cards
  float above the sticky site bar (`--z-tooltip` 200 > `--z-nav` 100). The game's icons are scaled smooth
  (`img.px` is no longer pixelated), because they are 128px paintings
  shown at 20-96px. A switch (`data-toggle-class` checkbox) follows its box, also when the browser restores
  a ticked box on "back". Toggle buttons report `aria-pressed`.
- Patch titles (`common.patch_title_html` / `patch_title_text`): the date once. A named update (City
  Never Sleeps, Matchmaking Update) shows its name in gold (`--gold`, no icon: it shifted the text) +
  the date and a gold banner bar; a dated one ("09-16-2026 Update") shows only its date + "update".
- Dates are never in the pixel fonts: IBM Plex, tabular figures (banners, tooltips, lists, cards).
- Stat history tooltip: one set of columns for every row (date | was | → | now | %), a first value
  sits under "now".
- % pills grade their colour strength by size (`render.pct_grade`, steps 5/15/30/60%; scripts.js
  `pctGrade` mirrors them); the history tooltip shows no pill for a first value or a 0.0% step.
- Item page: current values in a sticky left column beside the history.
- Heroes index (`builders/heroes_grid.py`), like the game's hero grid: one grid of tall portraits in
  the order of the game's sort names (`m_strHeroSortName`: The Doorman under D; no "new players" row —
  owner's call), the name plate in the hero's colour from the game (`m_colorUI` as `--hero` in the
  card's style — the one approved exception to ":root tokens only") and a PRE-RELEASE ribbon; no role,
  complexity or last-patch line (owner's call, 2026-10-01).
- Unit families (`builders/unit_families.py`, owner 2026-10-03: "many identical units, only the tier
  changes"): units sharing a name once the tier numeral is dropped (Slum Shroom I-III, the five Gutter
  Ghouls of each tier, the four Walkers, the Base Guardians) are ONE card on the Units index (tiers and
  "×N" under the name), ONE page (the main member's: not an `alt_` copy, lowest tier, not the boss's
  `weak` copy; the others are redirect stubs `body[data-redirect]` that keep the `#p-` anchor), ONE row
  in Unit changes (the same change on several members counts once) and on the home feed. On the page a
  member is a group named by its tier and what tells it apart ("Tier II · dock creature", "alt weak");
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
  named update), a cell = a square striped in the
  tag colours, each stripe as tall as its share (same counting rule as every counter). Switches: older
  patches (> 1 year, hidden by default; the table opens scrolled to the newest), buff vs nerf (one net
  colour), tag filters, pre-release heroes / removed items and units. Heroes index: pre-release heroes hide behind
  a switch, "Unreleased & hero labs" is folded.
- Hero changes: one tile per cell holds everything a patch did to the hero (stats, weapon, abilities);
  a filter — All / Stats / Weapon / Abilities (`dynamics_page.PARTS`, `part_of`: weapon = gun + melee) —
  redraws every tile from the part counts in the page JSON and narrows the hover card (owner, 10-01:
  a filter, not split tiles). Heroes index cards are only the portrait and the name on a plate in
  the hero's colour (no role, complexity or last-patch line — owner's call).
- Change matrix cells: a bevelled tile, its number of changes in the corner; hovering opens a card drawn by
  scripts.js from the page's `.dyn-data` JSON (who, which patch, counts with the tag icons, the three
  biggest changes, "+N more").
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
- Shared abilities (`builders/shared_page.py`): the abilities every hero has (kind 'shared'): heroes/shared.html (the hero history
  view), the hero matrix's "All heroes · movement & shared" row, search rows.
- Hero Stats: group labels left-aligned (visible at each group's start), a right-edge fade while more
  columns are off-screen (`.table-fade`, removed when scrolled to the end).
- Every stats table (2026-10-03): a click on a group header folds the group to its first column
  (scripts.js `col-groups`); zeros are quieter (`td.zero`); a cell's history drops steps its rounding
  cannot show (`tables_pages._same_shown`: Max DPS 122.925 → 122.9251); `data-hist` is single-quoted
  JSON (`common.json_attr`, no `&quot;`). Boons redraw once per frame and re-rank the heat; the search
  waits for a pause in typing and takes comma-separated names ("haze, abrams").
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
  units in the headers (`.u`), the table centred when narrower than the page (`.table-fade.center`).
  Dashes in the default view: 26% of the cells (was 71-84%), no row without a number. "Souls per point"
  converts every `[data-spp]` value (chips and stat cells) to cost / value; the heat then ranks it
  lower-is-better through `data-hpol` while `data-pol` keeps the stat's own direction for the history
  tooltip. Cost carries `data-hpol="0"` (it only repeats the tier).
- Heatmap (all stats tables, scripts.js `heatmap`): graded by rank — each column's distinct values (by
  size) ranked 0..1, the middle fifth plain, then 4 steps of green / red (`--heat-g1..4`, `--heat-b1..4`);
  an item's stat chip ranks with its column. On by default on Item Stats (`_toolbar(heat_on=True)`), a
  switch elsewhere. The sorted column has a gold header and a faint gold wash (`td.sorted-col`). Values rank with their sign (a drawback is the worst, not the biggest); a table with
  `data-heat-by="tier"` (Item Stats) ranks within each row's tier, except with "Souls per point" on.
- One recount for everything that hides columns (scripts.js `col-groups`, `table.__recount`): a folded
  group, the item filter's empty columns, Details and the stat columns; each group header spans exactly its
  visible columns, a folded group keeps the first column the filter left visible, band rows re-span. `col-groups` refolds every group on each recount (a group just unfolded drops its
  `grp-off`; only folded groups were refolded before, so an unfolded group stayed hidden); a column's cells
  change only when its header's state does (the `statcols` event re-applies to new cells).
- Table and matrix toolbars are not sticky (`.toolbar.tbl-bar`, `.toolbar.dyn-bar`): stuck, they covered
  the table's own sticky header. The legend chip wraps and is shortened on phones (`.lg-tail`).
- Change matrices (scripts.js `dyn-scroll`): the box is as wide as the name column + a whole number of
  patch columns, so the newest end opens with the first column at the sticky names; month labels are
  clipped (a one-patch month's label overflowed and made the box scroll 25px too far); only "Older
  patches" re-scrolls to the end. On phones (≤600px) the name column is the icon only (44px). A resize keeps the place — height-only does nothing, a new width keeps the
  distance from the newest end; only "Older patches" re-scrolls to the end.
- Item Stats extras: closing "Stat columns" while one sorted the rows resets the sort (`table.__resetSort`);
  a "Souls per point" box restored on "back" converts the values at load.
- Tests: `tests/test_browser_tables.py` runs site/scripts.js + styles.css on fixture pages in Chromium
  (Playwright; skipped where it is not installed — CI does not install it): fold / unfold returns the
  column count, signed and per-tier heat, sort reset, souls-per-point restore, matrix resize, tooltip
  step directions. All 7 fail on the previous scripts.js.

## Patch pages: written notes (`builders/written_notes.py`)

An update with notes and changes they left out has the tab "Not in patch notes N" (eye on the tab,
`patches_pages.HIDDEN_TAB`, `data-hidden-tab`): its biggest changes and readable lines of those rows only
(`_key_changes(only_hidden=)`, `_generated_notes(only_hidden=)`); "#hidden" opens it (scripts.js
hidden-hash), while the All changes eye keeps "#changes". An update without notes says "no patch notes"
(home banner too: "N · no patch notes"). "N of them in game rules" opens game/changes.html.

`builders/written_notes.py` writes the tabs "Not in patch notes" (an update with notes: what they left out) and
"From the files" (an update with none). Their lines are exactly the rows the patch's counters count
(`patch_counts.counted_rows`, which `count` now sums: console variables included, one edit over a family or a
Game system once), so a tab's number is what it lists. Valve's sections: Heroes, Items, Units, Game rules & map
objects, Console variables (`section_of`: the page the row is on, as the home icons route it). A line is its tag
badge (`render.tag_of`) and "Subject: what changed": an ability with its hero ("Kelvin · Frozen Shelter"), values
from `render.shown_pair` (sentinels "default" / "no limit", flag moves "+A −B", enum words, units, ranges), two
fields under one label told apart by `cards.disambiguate`, two entities of one name by how their ids differ
(`history_view.id_tail`, as the page's namesake groups). The verb (`written_notes.verb`): positive values by the
numbers; at or below zero by the row's percent (the pill's; a penalty or slow by size, a resist by sign), else by
size; a sign flip, another unit or words "changed". `pipeline.match.sentence` is no longer used for pages.

All changes: a shared edit's card carries an anchor (`<span class="anc" id="c-<id>">`) for each target without a
card of its own, a hero's ability by its hero (`patches_pages.shared_anchor_ids`); `change_anchors` /
`archive.change_anchors(pid)` list every `c-` place.

## Patch notes tab (`builders/notes_view.py`)

Interface, sound and settings get their own tab "Interface & sound" (`notes_view.split_sections`):
whole sections whose title names them (User Interface, Settings, Sandbox, Spectating, Sound…) and,
from general buckets only ("Additional Update Notes", "General"), lines the matcher filed under an
interface/sound/visual topic. They render as a grid of features — the name bold, what it does below
(`interface_table`), no tags. In the notes tab a line "Name: what it does" without a subject shows the
name bold; a line the files cannot back gets a tag only when its wording names a kind (Fixed → FIX,
no longer → DEL, now/added → NEW) — never a CHANGED that tells nothing.


Valve's text is not reproduced as a wall of lines: each section's lines are grouped by subject (hero,
item, ability, unit — consecutive lines, a bare-name heading opens a group) under an icon header with tag
counters; the subject prefix is dropped from the lines; a hero's line shows the icon of the ability it
matched (or names); each line gets the tag of the change it matched (counters when it matched several
kinds); "from A to B" / "by N" numbers are highlighted in the direction's colour; the right column keeps
what the files say.

## Notes vs files (`builders/errata_page.py` → `patches/errata.html`)

Every patch-note line still called "mismatch" after the 2026-10-02 review is Valve's own slip — a wrong
old value, a retune after the notes, two items' numbers swapped (Surge of Power / Spirit Snatch,
2026-05-22). One table, newest first: patch, field (icon, name, label), Valve's line, the numbers it
gives, the numbers in the files (with the tooltip's unit). A third tab of Patches.

A Steam post without text (most hero reveals, Rat King's "Listen up, Crumbums! Your King is here.") is
`news.TITLE_ONLY`: it names an unannounced build of its days but opens no window and is no "own post"
that would drop a forum follow-up of that date (`patches.group`; treating it as a full announcement
moved four hero-release builds out of the follow-up windows whose notes describe them).

## Cosmetics groundwork (`pipeline/cosmetics.py` → `data/cosmetics.json`)

Skin-system work ships in the files long before an announcement (2026-10-02: news of "underwear
textures" for Paige and Victor — `*_basebody` materials since City Never Sleeps, build 6711). The step
reads the tracker's packed-file list (`git log -G` over `pak01_dir.txt`) and the server schema dumps:
base bodies (`models/heroes*/<hero>/…basebody…`), per-hero cosmetic animation graphs
(`hero_cosmetic.vnmgraph+<hero>`), cosmetic sound sets, cosmetic item classes
(`CCitadel_Cosmetic{Item,Ability}_<Name>`; a rename Item → Ability in one build cancels out). Hero
codes resolve by model folder / file (any `models/heroes*`), id word or game name ("calico", "mo_krill").
Build pages list the build's events ("Cosmetics"); a hero with a base body gets the "skin base in files"
chip.

## Icons without per-entity art

| Rows | Source |
|---|---|
| troopers (and the zipline trooper), Guardians, Walkers, Patron, Base Guardians, base turret, Mid Boss, Shrine, Sinner's Sacrifice | the portraits / markers the game's own ping wheel uses (`scripts/ping_wheel_messages.vdata`: "Push Shrine" → npcs/shield_generator, "Sinner's Here" → minimap/neutral_vault), rules in `data/overrides/unit_icons.json` |
| a hero's summon or placed object (Mini Turret, Spectral Wall, Goo Ball, Bounce Pad, Familiar's helpers, Fire Scarabs, Rat King's rats and swarm), the shield escort, the removed rejuvenator / soul pickup units | the art of the ability that makes it, matched by model and class (Mini Turret: McGinnis' turret portrait heroes/engineer_turret); the escort: the minimap's escort marker; removed pickups: their misc.vdata namesakes' art — same file |
| neutral camps without art | their family's art: same id stem (`neutral_lantern_weak` → `_normal`) or same name without the tier ("Gutter Ghoul I" → II) |
| map pickups (powerups, rejuvenator) | `m_strPingIcon` / nested `m_strHudIcon` of `misc.vdata` (`misc:<id>`) |
| Game entries with no art of their own (Soul Urn pickup / carrier / return, Unstable Rift, soul pickups and orbs, souls powerup, crates, neutral camps by tier, Rejuvenator buff, ziplines, Parry, Mantle, Teleporting, Stunned) | the art the game shows for the same thing elsewhere (minimap marker, ping-wheel or HUD icon), rules on `<file>:<id>` in `data/overrides/game_icons.json` → manifest keys `misc:` / `modifier:` / `ability:` (`common.entity_icon` reads `modifier:<id>`), files under `icons/game/` |
| Game tiles | `game_systems.json` `icon`: Breakables = the minimap crate marker, Hero progression = the HUD level-up icon, Modes = Street Brawl's HUD icon, Urn = the Soul Urn's minimap marker (the old art, ability_golden_idol's, is Wraith's Telekinesis the files borrow); their files are game_icons.json's `systems` |
| groups and rules ("All heroes (24)", game rules, console variables, "Other rules & objects", loot tables) and units with no fitting art | site category glyphs (`common.GLYPHS`, pixel SVG, never presented as game art) |

`tools/extract_icons.py`: rule images go through `rule_art` (stored once, PNG → WebP, SVG copied); a marker whose
art fills under 35% of its canvas (`TRIM_BELOW`: minimap markers, 20×24 px of 64×64) is cut to its art and squared
(`trimmed`), portraits keep their framing. A `systems` image the VPK lacks is reported as missing (`game-art:<path>`,
exit 1 unless allow-listed). PREFIXES gained a few single-file prefixes (hud/brawl/icon_brawl, hud/levelup_,
hud/zipline_icon, hud/ledge_climb, hud/teleport_icon). Run from a worktree without `vendor/`:
`CYCLOPEAN_VRF=…/Source2Viewer-CLI.exe CYCLOPEAN_TRACKER=…/GameTracking-Deadlock CYCLOPEAN_PRE_TRACKER=…/Deadlocked`.

## Value printing and display (`builders/render.py`)

`render.shown_pair` is ONE value printer for the rows (`vals_html`), the hover cards (`vals_text`)
and the change matrices' cards (`dynamics_page._sample_values`): enum words → clip → sentinels judged
against the other side's raw value → one unit; flag sets as their moved bits with the side colour.

Corrupted / Enhanced versions (`render._fold_version`): namesakes disambiguated
(`cards.disambiguate`), the penalties a Corrupted version never rolls close the list
("· never rolls: Ability Duration"), by the game's names (`pipeline.abilities.corrupted_penalties` →
abilities.json `penalties`; `render.penalty_words`, also on an unfolded "Excluded Penalties" row); a
corrupted bonus carries its tooltip token, m/s for a speed and the enemy-slow minus (enrich 32).

Change matrices show the eye on patches with changes Valve didn't mention, and their cards list one.
A tile with changes not in the notes has the eye (`.dsq.hid`, `dynamics_page._collect`
`hidden`; the tile's data `[patch, counts, samples, parts|null, hidden]`, a sample's 7th element its eye);
scripts.js matrixCard marks those samples and says the count while unfiltered; redraw keeps the eye then.

Hover cards (strip tile, trail square, home icon, matrix tile) keep one sample slot for a change not in the
notes (`history_view.tile_card`, `home_page.chip_card`, scripts.js `rowsHtml(eyeSlot)`).

Description changes (`text_rows`): tokens are words / marks / spaces compared without case, short equal gaps join
changed stretches (`_marked`); `cosmetic` (same `wording`: case, punctuation, spacing, a key binding's spelling)
reads "Wording fixed"; ≤ 300 characters open (`SHORT_DIFF`); the banner chip "renamed" / "description changed"
(`text_kind`, `.txt-chip`, hidden under a tag / eye filter). Status 'unmatched' has its mark ("?", `MARK_ART['question']`) and the patch page's check line counts it.

## Item page details

Current values: the header chips list only what no section lists (`entities_pages.header_only`);
the section cards flow as flex (no stretched one-row card, a lone card centred, no phone overflow).

Item Stats history is exact: a value Valve only renamed or newly showed no longer reads "added", and the older history before it is back.
What an item's active does is marked "Active" (Spirit Sap's -30 Spirit Power is the target's debuff, not the item's stat). Drawbacks show red in the history.

The cooldown is shown once, in its section; cards no longer stretch. A provided stat is an always-on stat only outside the card's Active section and outside a "triggered"
Passive section (one listing its own timer / stacks: a plain number named …Duration / …Cooldown /
…ChargeUp… / …Stack… / BuildUp…, `_triggered`, read as section 'Conditional'); otherwise it is an effect
(Spirit Sap's -30 Spirit Power is the active's debuff). Effects from the Active section carry `active`
and follow an "Active" tag (`.fx-tag`, `.fx.fx-act`).

## Game pages

A search link to a Game entry is made only when its history shows a row (`game_pages._shows_rows`);
`#ab-<id>` sets no filter when no chip, group or band has the id.

## Labels and units (`pipeline/semantics.py`, enrich 33)

`semantics.boss_field`: a trooper's flat fields against a boss in the m_VS words ("Damage Resist at most vs
Guardian"; T1 Guardian, T2 Walker, T3 Patron, barracks = Base Guardian). `game_words`: "Phase 1", "Distance",
"NPC", "AoE". An aura's container (`m_modifierProvidedByAura`) drops out; container / flag words match any
case; CamelCase keys without m_ read as words.

`_percent_word`: a "Pct / Percent / Percentage" field with no tooltip unit: a trailing word becomes the
value's %, a word inside the label "%"; values never scaled (fractions are `_FRACTION_FIELD` /
`_FRACTION_PROP`), never on a scaling coefficient. A modifier's `*_RESIST` value is % (`_RESIST_VALUE`).

`_TIME_FIELD` takes a qualifier after the time word ("Cooldown On Hit", "Time To Give Up", "… Penalty"),
`_NOT_SECONDS` keeps minutes and lengths out; a plain T1-T3 bonus to a time gets "s" too.
`units_when_bare`: a bare Channel Move Speed is engine units on either side.

`direction`: UP / DOWN carry a signed percent; `SHARED_KINDS` includes 'helper'.

`classify`: looks (`Visual(Scale|Height|SplashRadius)`, `ProjectileModelScale`, `Bob*`, `FakeBullet` …),
sounds (`Vol(ume)?Scale(Min|Max)`, `*ToPitchRemap`), `HUDSnippetName` (ui), `MaxMoveIterationScale` /
`NpcAimingSpread` (technical), `*TimeTest` (meta).

`match.flag_words`: a state's -ing word also reads as its verb ("slide" = SLIDING_DISABLED).

## Hero / unit stats

`hero_page.says_nothing`: a stat at its neutral value (`NEUTRAL`: +range / resists per boon 0, headshot taken
×1) or a pellet / burst detail of a one-pellet / no-burst gun (`NEEDS`) is not drawn unless its history has a
real step (`_real_steps`). Units ride on the numbers everywhere (`_split_unit`). `KEY_STATS` holds stamina
regen, dashes and melee per boon; `NOT_ON_HERO`: crouch speed. Hero Stats: reloads 2 decimals, intervals 3,
the newest build (`unchanged_since` keeps the last build that changed a hero).

`.stat-flow` is a centred flex row of 280px panels; `.table-fade` hugs its table, centred.

## CI

`.github/workflows/build.yml` installs Playwright + Chromium (cached) and runs `pytest -rs`;
`tests/conftest.py` has the one `browser` fixture; with `CI` set a missing browser fails.

## Entity page head and history updates

"patch ↗" (`history_view.patch_href(pid, rel, id, also)`): the notes' card (`#n-`) or the All changes place
(`#c-`) of the page's own id, then of the band's other ids (a family's members); an id with no place on the patch
page links the page itself. A band that holds only rules for all links its Game band (`every_href`) instead.

The rules-for-all button says what those bands hold when the page gives no label (`every_label=None`: "For all
abilities & items" on a unit page; several kinds: "Rules for all").

A row whose eye has words of its own (`cards.hidden_tip`: "shipped silently …") carries `.late` and keeps its eye
in an all-hidden band (styles.css `.pblock.all-hidden .erow:not(.late)`).

Description changes print what the game printed. `pipeline/entity_texts.with_values` gives every name /
description / tier text change that holds "{s:Prop}" tokens a `vals` = `{'old': {token: value}, 'new': {…}}`: the
old text's values are read at the build before the patch window (`match.window_states`: the first build record's
`prev_commit`), the new text's at the window's last build — the same two states the window's merged change rows
compare. `match.text_state` reads that build's abilities.vdata (parsed-file cache, two blobs memoised: neighbouring
windows share a state) and `pipeline.abilities.text_values` gives each part its tokens: 'desc' the properties
(`base_values`: metres keep their m, seconds / percents leave the unit to the text, a property also under its
m_strLocTokenOverride), 't1'..'t3' that tier's bonuses over them (`tier_values`, a zero bonus is none, a scale bonus
also as "<prop>_scale") — the helpers the ability cards use (`card`). Tokens are looked up as written, then without
case; the hero's name and key bindings ("{s:iv_attack}", "{s:ability_key}") are no value. `builders/text_rows.sides`
fills each side (`abilities.fill_values`, the text's unit once: "+{s:AbilityCastRange}m" with "3m" is "+3m"); a token
no build record knows is a neutral gap "…" (`text_rows.GAP`), never "[Ability Cooldown]", and keeps the row folded; a
row whose texts differ only in numbers the patch's own change rows show (`numbers_only`: "30s Cooldown" → "28s" beside
"Cooldown 30s → 28s") stays folded too; two texts that read the same once filled are no row. On the data of
2026-10-05: 519 of 1,084 text changes hold tokens, 513 fill completely (6 have a value no build knows: texts written
before their property existed, 2024-07-04 Mini-bombs).

**Hero / unit stats — alt fire:**

The alt fire (`ESlot_Weapon_Secondary`: Viscous, Shiv, Yamato; Skyrunner is not playable yet) is evaluated on every
build like the gun (`hero_table.evaluate_alt`) over `ALT_COLUMNS`: the gun's columns that read the weapon alone — no
per-boon growth — plus Ammo / Shot (`m_iAmmoConsumedPerShot`, Viscous 5, Yamato 3, Shiv 4). A hero row gets `alt` =
`{weapon, values, history}`, heroes.json `alt_columns`; a build without an alt fire after one reads as removed
(Viscous' five-pellet alt fire went 2024-08-01, the goo ball came 2024-08-30), an alt fire cut from abilities.vdata
is MISSING and bridged like the gun. `hero_page.alt_cells` draws DPS, Bullet dmg, Pellets, Bullets/s, Ammo, Ammo/shot,
Reload, Bullet speed, Range as one compact row under the weapon block's "Alt fire" line (`.wb-alt-cells`: one row on a
desktop, three to a row under 600px), each with its history on hover; a default (one pellet, one ammo a shot) is left
out even if an older alt fire's steps moved it (`at_default`).

**Game pages — the "now" block:**

A system page opens on its values today (from `builders/game_now.py` via `now_block`, displayed with `history_view.now_fold('Current values', …)` between the head and
the history, like a unit's "Current stats"): its entries' numbers, then every console variable it reads. An entry's
number today is the newest value of a field in its history (`entry_values`: the history holds every move; a field
removed since, a switch or a name and work before release are left out), its most recently moved six (`NOW_ROWS`);
entries with the same numbers share a panel (`merged_label`), the six most recently tuned panels are shown
(`NOW_PANELS`). A field never moved since the tracking began is not in data/, so it is not there; a rule for every
hero or ability (the level curve) is no entry's number. Console variables: `game_rules.convar_parts(ledger)` (system →
part → variables; `rules_rows` is its per-system flattening), the ledger read once a build for every "now" block and
the Game rules table; a full-width panel per part with the variables in columns (`.cv-rows`), the value printed like
the Game rules table (`game_rules.value_parts`: game units, history on hover). `game_systems.convar_unit` and
`convar_side` match the config's words as whole words of the name (`_word_match`): "ratio" had matched inside
"du-ratio-n", so every `*_duration` read as a bare number (the Soul Urn's 45s decay "45"; 62 variables, 7 of them on
Game pages; no variable's side changed).

Description rows (`text_rows`): a short text opens unless either side holds a value the game fills in
(the hero's own name and key bindings "{s:iv_attack}" are not).

`now_fold` escapes its summary (plain text).

A template's edit its heirs carry (trooper_base, neutral_base) counts on the heirs only
(`patch_counts.counted_rows`, as `home_page._feed_rows`): City Never Sleeps 360 → 335 not in notes, Rat King's
"in game rules & map objects" 3 → 2.

A hero with no role in the files yet carries `data-role="*"`; scripts.js dyn-rows lets "*" through every role.
hist-tip: the "Overall" percent uses the steps' rule (two negatives by size: `pctOf`).

`pipeline.catalog.dead_namesakes`: shop items of one name, some out of the shop (removed, or disabled in the
files): one beside a namesake in the shop is "(old)"; several "(old, added <date>)", else "(old, tier N)", else
"(old, #n)" — "Toughness (old, added 2025-05-08)" / "(old, added 2024-06-06)", "Extra Large Magazine (old, #1)".

Home: a section of an update whose icons are all out of the notes has ONE eye on its label (`.lu-all`); an
update without notes shows none below its "no patch notes". The Items tile shows six shop items.

Game rules (`game_rules.rules_page`): one centred column (`.rules-col`), a variable search, the table scrolls
with the page under a sticky head, "NEW" for a variable added with no move yet. `game_systems.is_dev`: the
designers' test objects are on no Game page.

Names (`pipeline.catalog.earlier_names`): an ability / item / unit (not a gun) its last build's text does not
name takes the newest name an earlier build's text gave it ("[Deprecated]" stripped, "… Disabled" and
"DEPRICATED" skipped; a name a live entity has gets "(old)"); a remaining stand-in is Title Case for items,
abilities and units (`common.display_name` → `pretty_id(title=True)`), "AoE" spelled so.

Item matrix: shop order (slot, tier, name) and slot / tier filters (`dynamics_page.item_entries`,
`ITEM_SLOTS`, `ITEM_TIERS`; scripts.js `dyn-rows`, `table.dyn tr.f-out`); the hero matrix filters by role
(Hero Stats' types); "Removed N" counts drawn rows only (`entities_pages.drawn_extra`). Matrix samples are
disambiguated like the page's rows.

Values: a number list reads as a range for [min, max] fields ("0–0.15", "±0.4 → none") and as the positions
that moved for equal lists ("#2 500 → 800"; `render.number_lists`, shown kind 'steps').

hist-tip: two negative values compare by size (−0.5 → −1 is +100%), "added" / "removed" instead of blanks.

`builders/weights.py`: (net, volume) of a set of rows (BUFF / NERF by min(|%|, 60)/20, NEW +1, DEL −1, the rest
volume). `net_of(rows)` is THE net mark of what one patch did to one entity: 'buff' / 'nerf' / 'mix' by the weighed
sum (`net_class`), '' when no row takes a side (only reworks, mechanics, plain changes). Every place that says it
reads it: a history band's banner (`history_view._banner`: one quiet `.net-chip` after the counters — "net buff",
"net nerf", "mixed" in the tag colours, `weights.net_chip`; hidden while a filter recounts the band,
`.hblocks.filtering`), the hover card of a strip tile (`strip_data` tile [6]), of a home feed icon (`_feed` card [4];
the icon's underline `.lu.net-*` too, which counted a majority before) and of a change-matrix tile (`_collect` →
`nets`, the cell's data [5]; the tile's "Buff vs nerf" class). The words come with each blob (`nets`:
`weights.NET_WORDS`); scripts.js never re-weighs (it read [net, volume] and copied the thresholds before) — a tag or
part filter in the matrices still falls back to which side has more rows. NEW / DEL rows weigh ±1 whatever they are,
so a band of added console variables reads "net buff"; calibration is still open.

The net mark weighs `weights.weighed_rows`: what a band counts — no rule for every hero / ability (counted apart
everywhere) and no work before release unless the entity itself is in development (the band passes its `in_dev`;
every hero on a matrix is released or pre-release, so its cell weighs released rows only). The band computes its mark
once for its banner and its strip card (`_patch_block` → `_banner(net=…)`); the home feed once for an icon and its
card (`_chip(net=…)`). `dynamics_page._collect` takes a removed ability's owner and kind from the catalog: the patch
record of an ability removed in that patch names neither, so the matrix had dropped its DEL rows from the hero's cell
(Holliday 2026-09-29: 7 DEL on the band, 1 in the cell) — the cells' counts and stripes now include them too.
`tests/test_builders.py::test_band_chip_and_matrix_cell_weigh_the_same_rows` builds one hero's band and matrix cell
from the same fixture (a rule for all, work before release, a removed ability, a sideless patch).

classify: `m_bSpawnOnGround`, `BuffTypeValueUnit` are technical.

Removed items show their last values.

Troopers' alt / super / new-model copies are on the Medic / Melee / Trooper pages.

Buff vs nerf in the change matrices weighs how big each change was.

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
| 8 | `pipeline/match.py:window_changes` | A patch window's builds merged into one change per field (`merge_ops`). |
| 9 | `pipeline/match.py:annotate_line` | One patch-note line ⇄ the data changes: documented / described / mismatch / fix / code … |
| 10 | `pipeline/match.py:build_patch` | Writes `data/patches/<id>.json.gz` (statuses, unreleased heroes, `@shared` groups, counts). |
| 11 | `builders/archive.py:patch` / `gameplay` | The patch archive read once a build and shared read-only by every builder. |
| 12 | `builders/cards.py:gameplay_entities` | What a page lists of a patch: gameplay rows only, repeated variants merged. |
| 13 | `builders/cards.py:player_facing` | THE counting rule (renames merged, tiers / corrupted / levels folded, plumbing and no-ops out), memoised. |
| 14 | `builders/cards.py:entity_rows` / `change_rows` | The rows of one entity in one patch: on its own page / on the archive pages. |
| 15 | `builders/render.py:tag_of`, `vals_html`, `shown_value` | A change's badge (class, word), its old → new cell, a value as the page prints it. |
| 16 | `builders/history_view.py:history_table` | An entity's history: one band per patch, groups per part, the toolbar facts, the patch strip and its hover-card blob. |
| 17 | `builders/hero_page.py:hero_page` / `entities_pages.build_all` | A hero's page (head, weapon, ability cards, history); `build_all` writes every hero, item and unit page. |
| 18 | `builders/dynamics_page.py:_collect` / `matrix_html` | One pass over the archive for the three change matrices (counts per row and patch, part counts, hover samples). |
| 19 | `builders/tables_pages.py:render_table` / `hist_attrs` | Every stats table (groups, sortable columns, heat, lazy columns) and a value's history attributes. |
| 20 | `site/scripts.js` modules `hist-filter`, `dyn-tip`, `hist-tip` | The history toolbar's filters and recounts, the one hover-card renderer, the value-history tooltip. |

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

## Tooltips and Keyboard Access

- **Value histories** (`scripts.js `hist-tip`): values with a history (`[data-hist]`) join the tab order
  (scripts.js sets `tabIndex`; Item Stats' lazily built cells too) and show their history on focus (`aria-describedby`,
  Escape closes). Each step carries its direction from `semantics.direction`; a value's history carries its overall
  direction (`data-odir`), from the game field the column reads. Computed columns have no field: scripts.js judges by
  the column's polarity, with the sign. A table's values are one tab stop (roving tabindex): Tab enters at the value
  visited last (else the first shown one), ←/→ move in reading order, ↑/↓ to the same column in the nearest shown row.
- **Sortable headers**: tab order, `aria-sort` (descending / ascending / none), Enter or Space sorts. Foldable group
  headers: `aria-expanded`, Enter / Space fold.
- **Hover cards** (scripts.js `dyn-tip`): a change-matrix cell, an entity page's strip tile, an ability card's trail
  square and its "last change" link, and a home feed icon. Each card shows the patch (named ones in gold), counts by
  tag, "N not in patch notes", and the biggest changes (tag, eye, field, old → new). A card's value column wraps
  between words (`overflow-wrap: break-word`): a long REWORK list wraps inside the card, a number never splits.
- **Category glyphs** (`common.visual` without art): an empty `<span class="px glyph g-<name>">`; it has no size of
  its own, so every place that shows one sizes it with its `img` (`.card img, .card .glyph` 72px, `.ecard-h .ei`, etc.).

Short `data-tooltip` texts are shown by one floating element from `site/scripts.js` (clamped to the
viewport, flips below when there is no room above, tap to show on touch). Stat history cells use the
separate `.hist-tip`. Hero Stats column headers are short one-line labels; the full label is the
header's tooltip; niche columns live in a hidden "Details" group (`tables_pages.HERO_LAYOUT`).

Field categories that never count as gameplay (so never "hidden"): `technical` (scale-function wiring,
curve spline points), `streetbrawl` (incl. item draft weights), `ui`, `visual`, `audio`, `meta`. State masks are now a mechanic.
Changes copied into many entities (`@shared`, e.g. soul-investment bonuses in every hero) show once as
"All heroes (N)".

Matching rules live in `pipeline/match.py`; every fix to matching gets a test in
`tests/test_pipeline.py`. Rules so far:

- numbers match under display transforms: raw, magnitude, fraction↔percent, units↔metres, rate↔interval (1/x);
- a value written in metres on one side and bare on the other is engine units on the bare side (`semantics.metres_pair`,
  used by `match.change_json` for the numbers and the %): "Channel Move Speed 50 → 1.3m" read −97.4% NERF on 93 abilities;
  it is 1.27 → 1.3 m/s, +2.4%;
- a hero's availability written in another field is no change (`match.mark_availability_moves`): on 2026-09-29
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
| various (2026-03-06) | `m_StrPropertyNAme` — an id field with odd capitals, matched case-insensitively (`flatten._id_case`) |
