# Matching and tags

How patch-note lines meet the files: statuses and tags. Split out of `architecture.md` on 2026-11-13; see it for the pipeline overview.

## Change statuses (patch pages)

| Status | Meaning |
|---|---|
| documented | a note line has the same old → new numbers as the files |
| described | a note line talks about it without exact numbers (e.g. "All slows reduced by ~20%") |
| hidden | nothing in the notes covers it — the eye marker; in a hero's release window: what its announcement left out |
| mismatch (line) | the line names a property of the entity but the files say other numbers |
| fix (line) | a bug-fix line ("Fixed …") — usually no data change; where a report of it is known it says "was first reported 18 days before" (`builders/fix_reports.py`), with no link; a line with a subject is also a row of that entity's page (`history_view.TEXT_STATUSES`), not counted by the band |
| rounded (line) | the notes round a value (0.54 → "0.5"); exact values shown |
| unannounced | a window with no changelog and no hero release (build-6169, "Rem Enters The City That Never Sleeps"): nothing can be "hidden"; the page shows
  the biggest changes and patch notes written from the files |
| unreleased | a change to a hero still in development at that build — flask mark, violet rows; kept in "Only hidden" |
| heading (line) | a bare entity name ("Sinclair") heading the lines below it: those lines get it as their subject |
| untracked (line) | sound / visuals / interface / map / bots / performance / forum links: not in the diffed vdata, so not a matcher failure (`match_rules.untracked_topic`; a line with numbers is never untracked) |
| nodata (line) | the patch predates every tracker (May 2024): nothing to compare with |
| repeated (line) | an edited Steam post carries a line that a later patch's notes have and match (the 2026-03-06 post holds 03-21 lines): points to that patch |
| code (line) | the line is about a hero / ability / item whose gameplay files did not move in the window nor within `LATE_DAYS` after it ("Vyper: Sliding uphill now allows for lateral movement"): the change lives in the game's code, which is not compared (`match_passes.code_lines`, last pass). Not for lines with numbers (more likely our miss) — those stay unmatched; a quiet line about sounds or looks becomes untracked instead |
| unmatched (line) | should be in the data but no change was found — a real matcher gap |

## Tags (badges)

Chosen from what the data contains (all patches, 2026-10-01): NEW 20k, DEL 11k, NERF 5.2k, BUFF 4k,
CHANGED 2.5k, MECH 0.9k, availability 92. The badge never repeats the percentage (the value cell has it).

| Tag | When |
|---|---|
| NEW / DEL | field or entity added / removed |
| BUFF / NERF | numeric change, direction by the polarity of the PROPERTY's own name (`field_units.property_name`, not its container: "Cost" in `m_MapModCostBonuses` flipped 110 investment bonuses); "Reduction / Refund / Decay" after a lower-is-better word turns it around (Cooldown Reduction); lower-is-better values compare with their sign (an enemy healing penalty −65 → −70 is stronger) |
| UP / DOWN | numeric change on an object both teams have (troopers, guardians, walkers, camps, pickups, game rules): the number went up / down, no better/worse — except `semantics.PLAYER_SIDE` (camp bounty, powerup strength, shorter respawn / spawn timers), which are BUFF / NERF for whoever takes them |
| REWORK | an upgrade tier whose bonuses were removed and added in one patch (`render.fold_tier_swaps`) |
| MECH | mechanic field (behaviour flags, dependencies) without a direction |
| CHANGED | value without a known direction |
| ON / OFF | availability: `Disabled`/`In Development` truthy = OFF, `Player Selectable`/release state = ON; a "Disabled On Heroes" list that grew = OFF, shrank = ON |

On hero and patch pages changes are grouped: patch or hero → one header per ability (icon, name, tag
counters) → its rows without the name repeated. Abilities re-created under a new id borrow the icon of
their namesake with the same owner (`common.entity_icon`).

Tag look (`render.tag_badge`, the only badge markup, used by all builders): the word in the UI font
(600 11px uppercase, `--fs-xs`), one width for every tag (`--tag-w`, 80px: CHANGED fits with padding 4px 5px 3px
7px and .02em spacing — at 8px / 6px and .03em it measured 82.6px and stood out of its column, 2026-10-17; a phone's
row grid takes the column from `--tag-w` too, and hover cards use the same 11px tags), a muted tint of the tag
colour with a 2px bar on the left, and one fill. The size of a change is shown by the % next to it, never
by the badge. The % is coloured text whose ink strength follows `data-g`, not a second box. There is no
clip-path, because it cut the focus and "chosen" rings. The tag's pixel icon is the badge's CSS
`::before`: a mask per tag (`pixel_icons.tag_mask`, written into styles.css as `.tag.<t> { --ti: … }`),
drawn in the badge's own colour. `tests/test_entity_page.py` keeps the CSS in sync with `TAG_ART`. Counters
(`render.pip`) draw the badge's mask (`.pip.<tag>::before`). A chosen filter tag is `aria-pressed="true"`,
never the class `on`, because `.tag.on` is the ON tag's green.

**One counting rule.** Every counter on every page (home summary, patches index, heroes index, card
headers, ability sub-headers, history bands, the 12-patch strip) counts `row_rules.player_facing(changes)`:
renamed fields merged, swapped upgrade tiers folded into one REWORK (per entity, never across abilities),
engine plumbing (`row_rules.is_engine`, the "Technical" fold) left out. A patch that only touched plumbing is
not the hero's "last change" and does not take one of the three open history bands. `row_rules.player_facing`
is memoised on the identity of the change dicts; it ran 96k times on ~23k inputs.

**One count of "not in patch notes".** "Not in patch notes" — the eye — is ONE status set everywhere
(`render.NOT_IN_NOTES` = hidden and unannounced; `not_in_notes(c)`): what Valve did not write down, including every
change of an update with no changelog and no hero release (before this rule, Rat King's build 6736 lost its eye and
dropped out of the eye filter when only hidden counted). Such a band's eye chip reads "no patch notes"; a hero's
release is checked against its post (`common.checks_notes`), so its band reads "N not in patch notes". ONE icon too:
`unannounced` draws the eye
(`STATUS_MARK['unannounced'] = ('eye', 'No patch notes for this update — …')`, `.mark.unannounced { --mk:
var(--mask-eye) }` in the eye's colour; its document glyph sat beside the eyes of every other update, 2026-10-17).
Work on a hero still in development
(unreleased, "Before release") is not it. A patch's numbers come from ONE function (`builders/patch_counts.py`,
`for_id(pid)`): `not_in_notes` (the eye's number everywhere), the per-status counts, and `hidden_on_pages` — those of
them a hero, item or unit page shows by THE pages' keys (`patch_counts.page_set` = `entities_pages.page_entities` /
`page_keys` over the keys with changes of their own), so "N of them in game rules & map objects" is exactly what the
Game section shows.

The home icons route rows by THE pages (`home_page.page_route` over `patch_counts.page_set`, the catalog's
owner / units, unit families via `patch_counts.unit_main`), not by the patch record's name: unnamed units
(Neutral bug, Medic Trooper) are on the home page.

`game_systems.heir_sig(file, c)` / `heir_sigs(entities)`: THE rule for a template's inherited rows — (file, path, old,
new) of the heirs' rows, never an entity's own coming and going (`@add` / `@remove`). Used by
`patch_counts.drop_inherited`, `home_page._feed_rows`, `game_pages._heir_sigs` / `template_rows` and
`dynamics_page._collect` (four hand copies had drifted: 2026-06-30's pickup template removal was in the count and on
no Breakables icon, page or cell).

`patch_counts._placed_rows`: every counted row with where it is shown — PAGE, GAME or ARCHIVE (no hero / item / unit
page and no Game system: a designers' test object) — and on how many home icons a page row sits (`_icons`: an
'@shared' block's distinct page routes and the Game systems of its targets no page shows). `count` adds
`hidden_archive` and `hidden_shared`; `off_pages` = not in patch notes − on pages − archive-only, so
"N of them in game rules & map objects" is what the Game icons carry.

An '@shared' block on map objects of several Game systems counts once in each, with the status of its first entry
there (`_by_system`; template targets yield to the others; a block whose only placed entry is a template keeps its rows
in that system) — as those systems' pages and icons show it (City Never Sleeps: the powerup spawner's hidden copy was
on the Pickups icon while the count took the block's "described" once, in Breakables).

The home banner says what makes the icons add up to another number: "S of them on several icons" (an edit shared by
several heroes or units counts once in the banner and on each of their icons) and "K only in the patch archive"
(links the patch page). City Never Sleeps: 353 not in patch notes, 114 of them in game rules (= the Game icons), 5 of them
on several icons (the icons carry 9 more copies). The four updates on the home page: banner = icons + those copies.

**The eye everywhere a change is shown:**

Trail squares: `trail._index` → (patches, tag counts, hidden counts); a square with changes the notes left out gets
`.hid` and ", N not in patch notes" in its label (72 of 356 squares on hero pages); styles.css draws
`pixel_icons.EYE_SMALL` (a 10-grid eye, 1:1 at 10px, `--mask-eye-sm`) on a dark plate, the tag colour left as a bar
above and below.

Value histories (`builders/stat_eyes.py`): a step `[build, date, old, new, dir]` the notes left out carries a sixth
element 1 (`null` as the fifth when it had no direction); `hist-tip` draws the eye after its %. The step's row is the
field the column reads (`paths`, matched by the path's last segment), else the row of that build that moved the same
numbers (Item Stats has no paths). A column with a field but no such row gets no eye; a computed column (DPS, reload)
gets it only when nothing its entities changed in that build was in the notes. Applied by `heroes_data` (Hero Stats,
the hero pages' tiles, the alt fire's own gun), Unit Stats, Item Stats (`mark_row`) and Game rules (`mark_convar`, the
patch's `extras.convars` status). Steps with the eye: Hero Stats 705 of 3,561, Item Stats 733 of 2,663, Unit Stats 56
of 110, Game rules 70 of 96.

Game index cards: "N not in patch notes" with the eye under the date (`game_pages._stats` → (changes, last, hidden), the
same rows and dedupe as the count).

**What a page lists** starts at `row_rules.gameplay_entities` (gameplay rows only; one object kept under
several ids with the same edit — Walker's `alt_`/`_weak` copies, two crate ids — merges into one
"Walker · 4 variants" card, `row_rules.merge_variants`). Inside a card, 4+ rows of one family (labels equal
but for a number: "Level 19…36: souls needed", "Vitality investment, step N") fold into one summary row
with the % range (`cards.family_rows`).

**Labels for structures the game never labels** (`field_labels.plain_label`): level table ("Level 22: souls
needed / gives a boon / ability points"), investment bonuses ("Vitality investment, step 5: bonus"), the
hero's kit ("Kit: Ability 3"), powerups ("Powerup: Fire Rate (early game)"), the pellet pattern, walker
stages ("Health (empowered, stage 1)"), weak points. `humanize` drops `m_` and Hungarian prefixes even
before a lower-case letter, keeps plural acronyms (NPCs) and turns "In Seconds" into "(s)". Values:
`render.readable_value` turns engine enums into words (`EHeroDevState_PreRelease` → "Pre Release").
Not gameplay (`pipeline/classify.py`): vote stickers, AG2 names, rich presence, HUD/name offsets, unit
name keys, trooper hit-react clips → visual/ui; collision hulls, soul-orb flight physics, NPC sight → technical.

A field added then tuned within one patch window is NEW, tuned then removed is DEL (`match_window.merge_ops`);
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
- a field added or removed with a 0 / "no" value changes nothing (`row_rules.is_noop`; a field tuned to 0
  inside a window kept its first category and showed "Explosion Radius 0 · NEW");
- a field that appears with the value Valve says it was raised to takes the notes' old value
  (`match._old_from_notes`: "Headshot stack count increased from +2 to +3" while the files only gained
  `HeadshotStacks = 3` is a BUFF 2 → 3, not a NEW);
- a tier's scaling bonus names what it scales with (`field_labels.scaling_suffix`: "(weapon damage
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
  (`display_values.reencoded`, `same`);
- units: engine floats named like lengths are metres, like speeds m/s (`field_units.engine_unit`, `SPEED`;
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
- values carry the unit the tooltip prints (`field_labels.prop_unit`: the loc `<prop>_postfix`, also of the
  property's m_strLocTokenOverride; `with_unit`) — "Cooldown 30s → 38s", not "30 → 38" — and labels use
  the override's own label ("Shield Duration", `override_label`; enrich keeps `loc_token` / `unit` on
  the change, MChange carries `unit`) (enrich 18);
- a tier bonus to an enemy debuff written as a negative compares magnitudes even when the base is 0
  (`_ENEMY_DEBUFF`: Enemy Dash Slow −25 → −22 is a nerf);
- labels of nested fields read as words (`field_labels.context_label`: `CONTAINER_WORDS` "Projectile ›
  Speed", "Heavy melee › Cooldown On Hit"; `FLAG_FIELDS` "Behaviour", "Can target", "Interrupted by";
  a modifier's script value named by what it changes, "Aura › Bullet Armor Damage Resist") (enrich 20);
- a hero's base stat keeps only a length, speed or time unit (the stat panel's "%" postfix is for
  bonuses: "Crit Bonus Scale 1% → 0.8%" was a multiplier); stamina per second shows as the game's
  stamina cooldown (`describe` → `invert`, `display_values.show`: 0.2 → "5s") (enrich 21). The Hero Stats
  table keeps the owner's sheet layout (Stamina Regen per second).

Hero mechanics audit (2026-10-02, record format 6, enrich 22):
- a dash covers a fixed distance (`EGround/AirDashDistanceInMeters`), so a longer dash duration is a
  NERF (`_LOWER_FIRST` dashduration / airdashtraveltime); the mantle / climb-rope slow on the player
  is better smaller (`_SELF_SLOW`, on the whole path); parry's victim damage taken is better bigger;
- engine floats Valve already writes in metres (`…InMeters`, `…Meters`) or m/s (rope climb speed,
  the dash's drag thresholds) are shown as is (`field_units.METRES`, `MPS`);
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
  (`field_units.FRACTION`, `_FRACTION_FIELD`: move speed while shooting / zoomed, damage at falloff
  end, boss / NPC damage scale, instant gold share) — "0.55 → 0.7" reads 55% → 70%;
- an ability property that is a travel speed and carries no unit is engine units per second
  (`field_units.prop_speed`: Zip Speed 693 = 17.6 m/s, toss / leap / reel / return / projectile
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
  removal; the name a removed ability had comes from the catalog, `match_window.event_name` — its text
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
  rows on his page. They have their own page, heroes/shared.html (`builders/shared_page.py`, linked from the Heroes index toolbar), a row for
  them in the hero change matrix and search rows
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
  (`field_labels._names_something`). When the newest text still labels a field but prints no unit, or another one,
  where older text printed one (Valve dropped or replaced it), the field has no canonical unit: each window prints
  its own text's unit (`labels.resolve` → unit None, `display_unit`), and the row across the switch
  (`labels.unit_switch`, from the per-build unit steps `collect` keeps) prints each side in its own unit, CHANGED
  without a percent (`match_values.MChange.old_unit`, `unit_switch: true` in the patch JSON; `render.vals_html` then
  does not copy a unit across). A unit only ever added stays one unit for every row, as before.
- enemy slows: a property whose tooltip prefix is "-" (`field_labels.prop_sign`: the game prints "-30% Move
  Speed" over a stored 30) is labelled by what it does to the enemy (`field_labels.enemy_label`: "Movement
  Slow", "Fire Rate Slow", "Bullet Resist reduction (Heavy)", "Parry Cooldown reduction") and shown as its
  size (`show(..., magnitude=True)`); BUFF / NERF still from the raw value (a smaller slow is a nerf). A slow
  stored −30 in one build and 30 in the next (Card Trick 2026-08-12) is one value.
- sign flips: `row_rules.is_noop` keeps signs ("−22% → 22%" is a change); a flip that comes with the property's
  provided type flipping (REDUCTION_PERCENT → INCREASE_PERCENT: Riposte, Gloom Bombs) is the same value
  written the other way round (`match_window.mark_retyped` → `same`).
- units: −1 is never turned into metres (`display_value`); recoil, turn, spin, decay, blend-bias and penalty
  fields are not lengths or speeds; "…MeterPerSecond" is m/s already; an engine float ENDING in a length word
  is a length ("Nearby Enemy Resist Range" 2000 = 50.8 m); an ability property named like a length that no
  build gave a unit is engine units when its numbers pass 20 (`field_units.length_in_units`: "Lift Height
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
  value whose other side is another negative number (Sharpshooter's −0.5 → −1 m/s); `row_rules.merge_renames`
  does not pair a removed and an added bonus of another property AND another unit (Shoulder Charge's T1
  "25% → 2.2"); the hero page's weapon cells show two decimals (Reload 1.06, not 1.0575).
- tracker upkeep commits (a subject without a build number: "cleanup", "Dump exe, dedupe…") are not builds
  (`tracker.is_game_build`, `head_build`): no record (history takes what they moved as the new baseline; the
  next build names the build before it), the catalog and the cards keep the newest game build, and
  update-data names its commit after the newest game build ("tracker Dump" / "tracker Fail" on 2026-10-04,
  `None_92d2d9d0` = the 2025-08-23 "cleanup" with 498 loc rows).

Data-quality audit, part 2 (2026-10-04, enrich 30):
- plumbing by path: `row_rules._PLUMBING_PATH` drops, in every file, a modifier's mid-boss / effectiveness /
  refresh / time-scale / target-filter / buildup switches, dependent-ability lists, model scale, the Patron's
  observer origin and the deploy checks unless a note named them; `_PROPERTY_WIRING` also drops
  `m_nRequiredUpgradeBits`; a shotgun's pellet offsets never show (`_PELLETS`, labelled "Pellet pattern" in
  the archive); `row_rules.is_noop` drops an empty block added or removed. Rows are never hidden because of
  where their label came from.
- container words: a container named after its modifier loses the word ("Grab › Duration",
  `field_labels._MODIFIER_TAIL`, not on the leaf); `CONTAINER_WORDS` names the Rejuvenator buff, "On target",
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
  way (`render.shown_pair`; they are Technical rows). A chip's colour is the side it moved the owner to
  (`.flag.good / .bad / .even`), not added / removed. The disabled-state mask has its own nouns
  (`flags.IMMUNITIES`: "Immune to +dash lockouts +disarm +slows"); *_Invalid / NONE enum values are no value
  (`flags.enum_words`); the same bits in another order are no change (`row_rules.is_noop`); the matrices' hover cards
  read a flag row as its moved bits in words (`dynamics_page._sample_values` -> `render.vals_text`).
- polarity: `semantics.POLARITY_RULES` (path regex → side, each with its note) wins over the name rules —
  ActiveReloadPercent, RecoilRecoverySpeed, MoveSpeedPenaltyPerStack (an enemy slow) +1; SummonFrequency,
  BonusBuffsPerGold, MinimumDamage, Goo Ball's m_DamagePreventionModifier.m_flDuration -1. A hero's own
  base stat compares with its sign (a negative resist is a penalty). A negating word before the lower-is-
  better word counts too ("Reduce Cooldown On Hit"). Offsets, pitch limits, aim bias, damping, friction and
  springs are neutral; a shotgun's scatter scales lower-is-better. `display_values.is_sentinel`: 9999 always,
  -1 only against a non-negative other side; -2 is no sentinel.
- "no limit": `render.shown_value` prints 9999 as "no limit" (was ∞), the same word `render._sentinel` gives
  -1, so `row_rules.is_noop` sees "9999 → -1" as no change; `_SENTINEL_WORDS` says "default" for a charge delay /
  spin-up / spread-decay -1 and "permanent" for a modifier's duration.
- renames: `row_rules.merge_renames` also pairs a DEL with a NEW of the same entity and tier when the values
  are equal and the names say the same thing (`row_rules._alike`: labels with other
  numbers in them are never one field (investment thresholds, "Level N", "value #N"); with the same value, last
  label part ≥ 0.75 alike, one label's words inside the other's, or — for ability properties and T1-T3 bonuses
  only — one property name inside the other ("FlameAuraDPS" / "DPS"; a bare engine leaf such as m_value names
  nothing); with a new value only a respelling (`row_rules._respelt`: as many words, letters ≥ 0.9 alike: "Picup" →
  "Pickup"); a word more or less ("Damage Taken" → "Damage", "… Max", "Imbued …") or another word in its place
  ("Spirit Damage" → "Base Damage") stays DEL + NEW. A flat number and a percent are one value only at 0 or when
  the bare field's name says percent (`row_rules._same_value`: Blood Bomb's "Self Damage 30" → "Health Cost 30%" is
  two rows).
- "described another way" (owner 2026-10-30, the Halloween 2026 update: 136 hidden, 88 after; whole archive 8,139 →
  7,840): a line that tells a rework in words claims the fields of that entity that came or went in the window
  (`match.post_pass`; one with a number of its own only on a "no longer / removed" line — "Baba's Brew - No longer
  has an initial brew time" is its three Lock Times; a new number stays hidden: Walker's 30% trooper factor); a tier
  line "T3 no longer has …" what that tier lost; a sub-heading line inside a post ("Street Brawl:", `match._SUBHEAD`)
  heads the lines below it, so that mode's lines answer with its Street Brawl numbers; "N% faster / slower" is a
  speed by that percent; a name that is also an alias brings the alias's entries ("Mid-Boss" + its Rejuvenator,
  `m_RejuvParams`, spelt "Rejuvinator" in the files); a DPS field is damage ("Haunts … Damage output increased by
  10%"). Audit: coverage 86 → 87%, real hidden kept 92 → 91%. Round 2 (same day, every version): a percent over
  many values ("all abilities", "every", "~8%": `match._LOOSE_PCT`) accepts round values Valve put on a step of 5
  (`match._rounded_to_five`; a line about one property stays exact — "Neutral bounty +5%" is not a trooper's 65 → 70),
  and such a line takes every field that moved by it and names its property, tiers too (Mo & Krill's Combo 40 → 35);
  "the old T2 … in the base" takes the base's fields that came from nothing (`match._OLD_TIER`); a words line naming an
  ability takes the field whose value is the line's one number, in its unit and the line's tier (none: the base) —
  "previously launched at least 45° upward" is Guided Owl's Arrow Initial Pitch -45 → 89. Archive 7,851 → 7,714 hidden,
  1,570 → 1,538 unmatched lines; 2025-07-04's "~8%" alone 206 → 105.
- matcher: `match.twin_hits` — a matched line also claims, in the entities it matched, a changed field of
  the line's tier that it names by a word and that moved by its exact numbers ("Ability Range" range AND
  radius multiplier, "damage and debuff resistance" bullet AND spirit resist); `match_values._aligned_pairs` —
  "from A … B … to C … D …" pairs numbers that have words between them when both sides read alike (not
  'changed from "X" to "Y"' nor "changed from -56s Cooldown to Impact Area Stuns"); `_ITEM_TIER_MOVE` —
  "Moved from T4 to T3" is the item's tier; a fix line's pairs also run reversed ("being 3 instead of 1.5")
  and its status stays "fix"; LABEL_SYNONYMS cooldown ↔ chargeup.
- scenery: `classify.decor_entity` (the city's traffic, glass panes, team colours, minimap offsets, district
  names, timer placement) — no gameplay event in `match_window._gameplay_entity`, their fields `visual` in enrich.

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
  (`history_groups.split_every`) and shown ONCE per band: one block of link rows after the groups
  (`.hgroup.shr-band`), one row per (Game system, noun) (`cards.every_links`, `every_key`), its
  copies on each of the entity's abilities deduped (`history_groups.every_sig`). The banner chip
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
- 2,040 gameplay changes (1,340 not in patch notes) were on no hero, item or unit page — the Soul Urn rework of 2026-06-04,
  crates, powerups, the Rejuvenator, soul sharing, the level curve, respawn times and soul rewards (console variables).
  The fourth section, Game, is everything no hero, item or unit page shows (`builders/game_systems.py`, `game_pages.py`,
  `game_rules.py`; config `data/overrides/game_systems.json`).
- Which entries: `entities_pages.page_entities` / `page_keys` are THE pages. The Game takes exactly the rest
  (`game_systems.place_entity(key, e, pages)`): map objects, game rules, effects, loot tables, abilities no hero owns,
  templates. Scenery (`classify.decor_entity`) is no page's.
- Systems: Souls & economy, Respawn, Hero progression, Urn & Unstable Rift, Pickups & powerups, Breakables & crates,
  Troopers & lanes, Neutral camps & Mid-Boss, Shop & item rules, Movement & combat, Modes, Ranked, Seasonal events, Other
  rules & objects. Ranked (2026-11-13): `scripts/ranked_seasons.vdata` (in `tracker.VDATA_FILES` since then; its build
  records were remade), a season per entry: points per match, rank-up XP, shields, hero unlock, calibration cap, dates;
  icon the hideout's rank-protection shield. Seasonal events (2026-10-30) is first in precedence: Halloween's cauldrons, troll, candy, masks, pumpkins
  and `citadel_halloween_*` variables, Winter's snowball and presents — otherwise a cauldron reads as a crate and the
  candy every hero carries as a hero move. Its dates come from `pipeline/events.py` (events.vdata → data/events.json).
  An entry that never moved shows the numbers it came with, read from the build record (`game_now.added_values`). A
  row that undoes the field's previous move in another update carries "reverts <date>" (`builders/reverts.py`). Each has parts (the page's filters). A rule is a regex tried from the start of a subject, systems and parts in config
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
- Patch archive: the console variables tab lists every variable (noted ones first; `match_passes.slim_extras` keeps them
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

Fuller build pages (`builders/build_tech.py`; owner 2026-10-24: "only what tells something", no datavpk-style path
dumps, no steam.inf / manifests). Record format 8 (`pipeline/history.py`) adds:
- `assets.owners` — {hero or unit: {kind: [added, removed, modified]}} (`extras.asset_owners`, `OWNER_RULES`: model,
  model parts, animation, particles, sounds, voice lines, animation graph). A folder's hero by heroes.vdata (model
  folder, or code name: `nurse` → hero_nurse; `_v2`, `_wip`, `_out_of_combat` stripped). A shared animation graph
  changed in `SHARED_GRAPH` (8) or more heroes' copies at once is one row under `'*'` (6810: `hero_leans`, 51 heroes).
  Files without an owner (shared materials, UI) stay in `assets.counts`; map paths are written (`assets.notable.map`).
- `assets.files` — {category: [[op, path], ...]} for a category that changed at most `extras.FEW_FILES` (25) files
  (owner 2026-11-13: build 6861's page said "ui ~1" and nothing more); the page lists those paths, except a hero's or
  unit's (its own row). Added to the older records in place (counts checked against the record's own).
- A build page's picker (`select.build-pick`) opens any build: its options come from `builds/list.json`
  (`builds_pages.pick_list`, newest first) on first use (scripts.js `build-pick`).
- `protobuf` — rows {file, scope, op, item, old, new}: each .proto read into {Message.Nested: {field or enum value:
  definition}}, so a moved or re-spaced line is no change; a whole message added / removed is one row; cap 300.
- `strings` — {client|server|host|engine2: {added, removed (60 each), n_added, n_removed}}. Dropped: lines with
  dump escapes, under 6 characters, byte runs (8+ repeats), the engine's build date; a leading length byte (`?`, `:`,
  `@`) is cut; MSVC type names spelled out (`.?AV?$CModifierFactory@VCCitadel_Modifier_X@@…` →
  `CModifierFactory<CCitadel_Modifier_X>`). Engine tools (resourcecompiler, vconsole2, Qt…) are not read.
- Functions of client/server.dll come from outside the tracker: `data/dll_changes.json`, written by hand with
  `python tools/import_dll_summary.py <summary.json>` from the per-build DLL diff summary (no code, addresses or
  paths; two Steam builds under one tracker build merged; type names spelled out). CI cannot refresh it. The page
  shows only functions whose code changed: "added / removed" are mostly functions the linker moved (6810's client.dll:
  +1473 −1473). Strings and functions are one per row, left (a comma run read as a wall). A build that changed only
  code has no record (the tracker's commit is a version bump): `builds_pages.code_only_rows` makes its page and list
  row from the summary, dated by the Steam build's `seen`; stems of the records do not move.
- Page stems (`common.build_pages`): a strings / protocol-only record (`common.tech_only_files`) is numbered after
  the records of its build number with game data or files, and the eye (`evidence.patch_builds`) never opens it — no
  page that existed before moved (6785's notes build is still 6785.html).
The builds list shows a build whose only changes are files, protocol, strings or code (6810 was missing).

A hero's model rebuilt (`pipeline/extras.size_jumps`, `builders/model_rows.py`; owner 2026-10-23):
- the asset diff keeps each file's size; a `models/heroes*/*.vmdl_c` whose size moved `SIZE_JUMP` (3) times or more is
  in the build record's `assets.model_sizes` with its hero (`extras.model_owners`: the folder heroes.vdata names for the
  hero's model or WIP model, "_v2" off — hero_doorman wears doorman_v2/, its trolley sits in doorman/). All records were rebuilt
  on 2026-10-23 (they had not been since 2026-10-17's classifier changes: 35 builds' new entities lost sound / look /
  plumbing rows and gained melee attack rows).
- `match_passes.slim_extras` gives the patch `extras.models`; `entities_pages._history` files them under `model:<key>`;
  `history_table` adds a row "Model luggagetrolley: file size  1.68 MB → 168 KB · 10× smaller" to the hero's group,
  a MODEL badge and the eye (no patch note says it), one row for a model and its "_friendly" copy.
- Never counted (scripts.js `countRows` skips `.model-row`). First case: Doorman's luggage trolley, build 6815
  (2026-10-22), a cart drawn twice (97,000 → ~9,000 polygons by the community's count).
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

## Patch windows

`pipeline/patches.py`: window of a changelog = `[date − 3 h, next start)`. Builds usually land
17–26 h after the title date but sometimes before it; builds within `[start − 12 h, start + 30 h]`
are re-assigned to whichever neighbouring changelog they document better. Posts without a change
list (hero reveals, events) never open a window; a big build (≥150 gameplay fields) with no changelog
within 3 days becomes its own patch, named after an announcement within 2 days if there is one.

**Hero releases.** `history.released_heroes(rec)` (index row key `released`): the heroes whose `m_eHeroDevelopmentState`
turns `EHeroDevState_Release` in that build. `patches.release_windows`: such a build with an announcement post (any
non-changelog post, title-only included) within `ANNOUNCEMENT_GAP` is a window of its own (`Patch.release` = the heroes,
id `build-<n>`, title and link = the post), unless a changelog is dated the build's own UTC day (then those notes are the
release's, as on 01-17-2025). The window takes the builds of `[release, release + RELEASE_TAIL)` (6 h: the release-day
hotfixes) that move fewer than `HOTFIX_MAX_FIELDS` (20) gameplay fields; a bigger one is the notes' balance build. The
latest release owns a tail build (`release_of` in `group()`). Every other build is placed among the non-release windows,
so a notes window "resumes" after a release that interrupts it (10-14's window = 6782 + 6785; Danny's 6779 and Violet's
6790 are their own). `group()` returns the windows in the order their first builds shipped; `ambiguous_builds` and
`absorb_late_windows` skip release windows.

Statuses in a release window: the rows start as `unannounced`, then `match.release_pass` sets the hero's state row to
`documented` and its kit to `described`. The kit (`match.release_kit`) is the hero, what it owns, the entries whose id
carries its code (`citadel_artist_strokeblocker`, `pickup_artist_drawing_*`) and the units named like one of its
abilities. Everything else — other heroes' tuning, edits shared by many entities, its console variables — is `hidden`:
the announcement is the window's notes and those rows are what it left out. Only a window with no changelog and no hero
release keeps `unannounced`. Builders ask `common.checks_notes(row)` (index row: `has_notes` or `release`): the home
feed's icons / banner, the patch list's audit + bar and the patch page's check line treat a release like an update with
notes; the patch page's "From the files" list of a release leads every line with its mark
(`written_notes.notes_html(marks=…)`, `patches_pages.RELEASE_MARKS`: the kit's tilde says "Released with the hero"). Its
check line reads "N released with the hero" and "M other changes not in patch notes", and adds `unreleased`
("on heroes in development") so the buckets sum to the changes. `match.mark_unreleased` runs in every window,
also one without notes. `RELEASED_STATES` is Release only: a PreRelease hero is `unreleased` (`LISTED_STATES` keeps both
for `mark_availability_moves`). The in-development flag that flips together with a release is marked `moved` and folded
into the state row. A window that a release interrupts has a gap (`patches.gap_builds`): its before and after states
include the gap builds' edits, so `match_window.rekey_lists` keys only the lists those builds did not move. Text rows' values in
such a window still read those states; that is a known limit.
