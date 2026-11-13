# Values and labels

How a field gets its words, its unit and its printed value. Split out of `architecture.md` on 2026-11-13; see it for the pipeline overview.

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
A tile with changes not in patch notes has the eye (`.dsq.hid`, `dynamics_page._collect`
`hidden`; the tile's data `[patch, counts, samples, parts|null, hidden, net]`, plus `_hidden_tail` for a cell
partly out of the notes, see "Not in patch notes" above; a sample's 7th element its eye);
scripts.js matrixCard marks those samples and says the count (under "Not in patch notes", of those rows only);
redraw keeps the eye then.

Hover cards (strip tile, trail square, home icon, matrix tile) keep one sample slot for a change not in the
notes (`patch_strip.tile_card`, `home_page.chip_card`, scripts.js `rowsHtml(eyeSlot)`).

Description changes (`text_rows`): tokens are words / marks / spaces compared without case, short equal gaps join
changed stretches (`_marked`); `cosmetic` (same `wording`: case, punctuation, spacing, a key binding's spelling)
reads "Wording fixed"; ≤ 300 characters open (`SHORT_DIFF`); the banner chip "renamed" / "description changed"
(`text_kind`, `.txt-chip`, hidden under a tag / eye filter). Status 'unmatched' has its mark ("?", `MARK_ART['question']`) and the patch page's check line counts it.

`render.bool_move`: a yes / no field whose label reads as what holds (`_PREDICATE`: Can / Is / Has / Should / Uses /
Requires / Ignores / Applies / Reduced …) prints "now" / "no longer" (('steps', …) in shown_pair: rows, hover
cards, matrices, written notes "Can Proc From Items: no longer"); an added "no" or a label naming a thing keeps
"yes → no".

`row_rules.merge_renames` → `_merge_moves`: a stat that moved to another field of the same label with one side through 0
(TechPower 7 → 0 + SpiritPower — → 8; HeadShotCooldown 5s → — + AbilityCooldown 0s → 7s) is ONE changed row 7 → 8
(no row when the value is the same), only one leaving and one arriving row under the label, one unit, never a T1-T3 /
Enhanced bonus. `_same_value` takes a fraction and its "…Pct" successor's percent as one value (0.35 → 35%). A merged
row of a unit or a game object is judged UP / DOWN (`_unit_side`, #43.4).

Unit Stats: Bullet Resist, Spirit Resist (Vitality) and Sight Range (m) (Attack) columns (`pipeline/unit_table.COLUMNS`): a
unit's own resists are its always-on modifier's script values (bullet armor / bullet damage reduction; spirit /
ability damage reduction) whatever the modifier is called — a column path segment "name{key}" picks a list entry by
its _my_subclass_name / modifier value, "{*}" any entry (`_walk`). Guardian 10%, Base Guardian 20%, Walker 35%,
Mid-Boss 15%, neutrals 50-60% / 45-55%; Sight Range = m_flSightRangePlayers (troopers 25 m, Guardian 34 m).

## Labels and units (`pipeline/semantics.py`, enrich 33)

`field_label_tables.boss_field`: a trooper's flat fields against a boss in the m_VS words ("Damage Resist at most vs
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

`match_lines.flag_words`: a state's -ing word also reads as its verb ("slide" = SLIDING_DISABLED).

Speeds in m/s (#13): an ability property ending in Speed / Velocity + Max / Min is a travel speed (`_PROP_SPEED`;
Rain of Arrows' "Air Speed Max 150 → 161.42" = the notes' 3.8 → 4.1 m/s; "Fall" / "AirSpeed" left the not-travel
list), and `speed_prop` reads "1m" there as m/s; `_NOT_A_LENGTH` takes "Turn" and "Lerp" as CamelCase words only
("KillerPlane", "ReturnSpeed" were caught inside), so the soul orbs' Killer Plane speeds and the hook's Return Speed
are m/s; "…movespeed" is a speed; a modifier's speed value (MODIFIER_VALUE_SPRINT_SPEED_BONUS, …_MOVEMENT_SPEED_MAX;
not a percent, slow, attack, fire rate) is m/s (`fallback_unit`); a growing value's part (m_flBase, m_flMaxValue,
m_flMinValue, m_flPerMinuteAfterStart; `scaled_parent`) is in its field's unit — "Pickup Radius › Base 85" = 2.16 m,
"Pickup Expiration Duration › Base 30s".

A trooper's m_VS*.m_flDamageResist prints % like the flat …DamageResistPct field it replaced.

`flags.target_bits` / `target_groups`: a target set (m_nAbilityTargetTypes, m_iAuraSearchType) is compared as the
game's single bits (CITADEL_UNIT_TARGET_TYPE from DumpSource2), the bits that moved said by the widest union they
fill: Life Drain's "all enemies → allied heroes + the nine enemy kinds" is "+allied heroes".

A Notification modifier's attributes (Proc / Interrupt Notification › Attributes) have no side (`flags._NOTIFICATION`).

A Walker weak point (`m_vecWeakPoints{key}`) is named by `field_labels.WEAK_POINT_NAMES` (head, canister, rear / front
left / right leg; another key reads as its words without "joint"): "Rear left leg weak point › Max Health"
(`m_nMaxHealth`; `m_nHealth` is "Health"). The committed records were written with "Weak point (joint_rear_left):
health" / "Weak Points joint rear left › …": `common.load_json` rewrites the labels of `patches/` and `builds/` records on
load (`readable_labels` → `field_labels.readable_label`, idempotent) until the data is regenerated.

- `classify.VISUAL_RE`: `(?<!_)Light(?!ning|Melee|Attack)`. A light melee attack (`m_LightAttackData`,
  `EAttackType_Light`, `EBabaBenchMeleeAttack_Light`) is gameplay. Build records 4330 and 6785 were regenerated
  (`history`), because a visual change keeps no values.
- `classify.STREET_BRAWL_VALUE` rows are balance; item draft weights stay in the `streetbrawl` category.
- `field_units._NOT_A_LENGTH` / `_PROP_NOT_LENGTH`: `Power$` and `Exponent` are no lengths (enrich 39).
- `classify.is_template_entry`: `_not_pickable` is a template unless a hero binds the entry in a slot. The catalog keeps
  the newest state of an entry (it does not stick); `abilities.build` gives such an ability its card.
- `classify`: `PingTarget*` ui; `m_eDisableShopFilters`, `m_BossWeaponName` technical. Enrich 40.
- `field_labels.context_label`: a modifier's `m_nAttributes` reads "<modifier> effect" (a name ending in Modifier /
  Effect says it once; top level: "Effect").
- `field_labels._GAME_WORDS`: Gold → Souls (Gold Orb → Soul Orb, Gold Kill → Kill Souls, Per Gold → Per Soul) in labels
  the game never wrote; `PLAIN_FIELDS` for an ability's unlabelled own fields (Danny's rocket jump).
- `enrich.tier_scaling` → `scale_parts` (a removed bonus: read in the build before) → `field_labels.describe(
  scale_parts=…)` and `match_window._window_change`: a T1-T3 bonus (`.m_strBonus`) keyed by its property alone (no namesake in
  its tier, `flatten._list_key`) whose `m_eUpgradeType` is a scaling reads "(spirit scaling)" like the card. The suffix is decided per window
  (`_window_change` appends it to the canonical label of `pipeline.labels` when that label lacks it), so one field can be
  flat in one build and a scaling later (Warden's T3 Barrier).
- `item_table.track` iterates its keys sorted and `values` keep column order: two data runs gave 11 items different
  histories (a set's order picked a renamed predecessor).

## Known schema drift (handled by aliases in `pipeline/flatten.py`)

| Build | Change |
|---|---|
| 5201 (2024-09) | `m_nAbilityBehaviors` → `m_AbilityBehaviorsBits` |
| 6468 (2026-04-30) | trooper flat DPS/resist fields → `m_VS*{…}` blocks (real restructure, not aliased) |
| 6711 (2026-09-29) | `m_WeaponInfo` → `m_mapWeaponInfos.primary` |
| various (2026-03-06) | `m_StrPropertyNAme` — an id field with odd capitals, matched case-insensitively (`flatten._id_case`) |
