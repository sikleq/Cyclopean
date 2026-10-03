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

Tag look: the tag's own pixel icon + word, coloured on a tint of the tag colour with a 2px bar and
notched corners; the tint grows with the size of the change (`data-g`). Counters (▲3-style) are the
same icons + a number (`render.pip`). Icons are 10×10 ASCII grids in `builders/pixel_icons.py`, never
font glyphs (fallback fonts drew ⟳ as "C"); how to draw and review them: `.claude/skills/pixel-icons`.

**One counting rule.** Every counter on every page (home summary, patches index, heroes index, card
headers, ability sub-headers, history bands, the 12-patch strip) counts `cards.player_facing(changes)`:
renamed fields merged, swapped upgrade tiers folded into one REWORK (per entity, never across abilities),
engine plumbing (`cards.is_engine`, the "Technical" fold) left out. A patch that only touched plumbing is
not the hero's "last change" and does not take one of the three open history bands.

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

Polarity notes: an interval between an effect's ticks (`HealInterval`, `TickInterval`, `DamageInterval`…)
is lower-is-better — Infest Heal Interval 3 → 2 is a BUFF. A property the game marks as the holder's own
downside (`m_bIsNegativeAttribute`, drawn red in the tooltip; `enrich.drawbacks`, the change carries
`drawback`) grows as a NERF whatever its name says (Golden Goose Egg's damage penalty −10% → −15%).

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
- Hero / item / unit pages ARE their history (owner, 2026-10-03: "closer to Sloppy"): head (portrait /
  icon, name, chips; a hero's key stat tiles) → "Current …" folded in one line (all stats, the weapon
  panel, ability cards; an item's values; a unit's stat tables) → History. One function for all three
  (`history_view.history_table`): one band per patch, newest first (latest 3 open), over ONE panel — a
  sub-header per part (base stats, gun, each ability; none on a single-entity page) and its rows: what
  the files changed (`cards.entity_rows`: tag, field, old → new; no "Technical" fold, a new entity is
  its NEW head + key fields) plus the note lines that live in the game's code (status `code`). Bug
  fixes, sound / look lines, engine plumbing and unmatched lines stay in data/ and the patch archive.
  One mark only: the eye on what the notes left out.
- The history toolbar (`history_view.toolbar`, scripts.js `hist-filter`): the tags present (multi-
  select), "Only hidden" (CSS on build-time `has-hidden` classes), the parts Stats / Weapon /
  Abilities, the abilities as icons (current ones in slot order, removed ones grey after a divider),
  "In development" (work on a hero before release: rows `st-unreleased`, groups / bands `dev-only`;
  shown by default only while the hero itself is in development). A patch with a match opens; a band
  left empty folds away.
- Weight: only the newest `EAGER_PATCHES` (6) bands are in the DOM; older panels are a
  `<template class="hp-t">` stamped when opened, filtered or named by `#p-<patch>` (Nano: 12k → 1.5k
  elements at load).
- Hero page head: every main non-gun stat as a tile (`hero_page.KEY_STATS`: health, regen, resists,
  movement, melee, spirit growth), values centred. Weapon panel (under "Current …"): six headline
  tiles (`hero_page.WEAPON_TOP`: DPS, Max DPS, Bullet dmg, Bullets/s, Ammo, Reload), the rest under
  "All weapon stats" (units ride on the number). "Changed lately" is a corner notch.
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
  only the columns that differ: range, speed) + the others (Mid-Boss, Sinner's Sacrifice); rows with no
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
- Navigation (2026-10-03, owner: "closer to Sloppy"): the bar is Heroes | Items | Units; each section has
  the same three sub-tabs (`common.SECTION_TABS`): its index, its stats table (Hero / Item / Unit Stats)
  and its change matrix. Patches, builds, the calendar and Notes vs files are still built but off the
  bar: the footer's "Patch archive" and the date banners lead there. A matrix tile and the home feed open
  the entity's own page at that patch (`#p-<patch id>` on every history block; scripts.js opens it).
- Home (`builders/home_page.py`): the three sections as tiles, then "Latest changes" — for each of the
  last 4 updates with gameplay changes, the heroes, items and units it touched as icons (count, net
  buff / nerf edge, the eye when something was hidden) linking to that page at that update
  (`home_page.update_feed`: a hero's abilities count on the hero; '@shared', templates, helpers and
  unreleased work are left out).
- Hero Stats: group labels left-aligned (visible at each group's start), a right-edge fade while more
  columns are off-screen (`.table-fade`, removed when scrolled to the end).
- Item Stats (`tables_pages.items_table`, 2026-10-03, Sloppy's Mana Items): ONE table of the shop
  (Weapon → Spirit → Vitality, by tier), a "Builds" column (component icons → what it builds into),
  chips by category / tier / Active · Passive · Imbue (rows carry `data-cat / data-tier / data-kind`),
  columns no shown row fills hide and the group headers re-span (scripts.js `item-filter`, also after a
  search), "Souls per point" turns each Stats cell into cost / value (lower is better, heat re-ranks via
  `window.__reheat`).

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
