# Pages

What each kind of page shows and how it is built. Split out of `architecture.md` on 2026-11-13; see it for the pipeline overview.

## Patch pages: written notes (`builders/written_notes.py`)

An update with notes and changes they left out has the tab "Not in patch notes N" (eye on the tab,
`patches_pages.HIDDEN_TAB`, `data-hidden-tab`): its biggest changes and readable lines of those rows only
(`_key_changes(only_hidden=)`, `_generated_notes(only_hidden=)`); "#hidden" opens it (scripts.js
hidden-hash), while the All changes eye keeps "#changes". An update with no changelog and no hero release says "no patch notes"
(home banner too: "N changes · no patch notes"; the patch list counts such an update by all its changes).
"N of them in game rules" opens game/changes.html. The band chips read "N not in patch notes", "all N not in patch
notes" or "no patch notes" (`history_view`); scripts.js `hist-filter` keeps "no patch notes" under a filter. The
notes check under the tiles (`patches_pages._audit_line`) reads "N not in patch notes", "N changes · no patch notes"
(a hero's release: "N released with the hero" and "M other changes not in patch notes"), "notes we couldn't match", "N on heroes in development"
(a count of changes), and singular "bug fix" / "note disagrees with the files".

`patches_pages` names the tabs "Not in patch notes" (an update with notes; its heading "What the patch notes left
out") and "Notes from the files" (an update with no changelog, a hero's release included; its heading "Patch notes written from the files").
`builders/written_notes.py` writes their lines (`notes_html`). Their lines are exactly the rows the patch's counters
count (`patch_counts.counted_rows`, which `count` now sums: console variables included, one edit over a family or a
Game system once), so a tab's number is what it lists. Valve's sections: Heroes, Items, Units, Game rules & map
objects, Console variables (`section_of`: the page the row is on, as the home icons route it). A line is its tag
badge (`render.tag_of`) and "Subject: what changed": an ability with its hero ("Kelvin · Frozen Shelter"), values
from `render.shown_pair` (sentinels "default" / "no limit", flag moves "+A −B", enum words, units, ranges), two
fields under one label told apart by `cards.disambiguate`, two entities of one name by how their ids differ
(`history_groups.id_tail`, as the page's namesake groups). The verb (`written_notes.verb`): positive values by the
numbers; at or below zero by the row's percent (the pill's; a penalty or slow by size, a resist by sign), else by
size; a sign flip, another unit or words "changed". `pipeline.match_passes.sentence` is no longer used for pages.

All changes: a shared edit's card carries an anchor (`<span class="anc" id="c-<id>">`) for each target without a
card of its own, a hero's ability by its hero (`patches_pages.shared_anchor_ids`); `change_anchors` /
`archive.change_anchors(pid)` list every `c-` place.

A patch page and a build page are one centred column like an entity page (`common.page(cls='column')`, `.page.column`
= `--entity-w` + gutters); their cards (`.ecards`) stand one under another (two CSS columns of cards of any height left
black holes, review 2026-10-17). Below 760px the sticky tab bar (`.tabs.toolbar`) is one row that scrolls sideways
(scripts.js `tabs` scrolls the open tab into sight). The patch list (`patches_pages._index_row`, `.ix`): above 1100px
five columns; 761–1100px date | title | faces over counts | notes (`grid-area`); ≤760px faces, counts and notes stack
under the title.

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

A notes row (`cards.row`) for a line no change was found for (status `unmatched`) has no mark (`ROW_MARKS` leaves it
out); the summary's audit line still counts it. `notes_view._pair` prints a described line's values as
`render.vals_text` does: an added value alone, a removed one as "<value> removed". At ≤600px a card row
(`.ecard .erow`) is a flow-root: the status mark and the tag float left, their negative bottom margin keeping them no
taller than the first line, so the text takes the full width below them, and the values sit under the text. The patch
switcher by the title always shows both steps, "◀ Older" and "Newer ▶" (`span.step.off` where there is none). The tabs
(`.tabs .px-btn`) are inline-flex on the baseline, with the eye centred at 14px.

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
Build pages list the build's events ("Cosmetics"); a hero with a base body gets the head chip "skins in the works"
(`hero_page.SKIN_CHIP`).

## Item page details

Current values: the header chips list only what no section lists (`entities_pages.header_only`); the sections are
groups of the one "today" component (see Hero / unit stats), and those header values sit on the section
`header_host` picks (`.chips.vg-hdr`).

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

System icons: Shop & item rules takes the game's shopping-cart icon and Other rules & objects its rule-book icon
(`icon_cart.svg` and `icon_book.svg` under `panorama/images/icons/`, listed under 'systems' in
`data/overrides/game_icons.json`; the site keeps them as `icons/game/`); no system uses a site glyph any more. `.card
img` sits on the glyph tile (`--bg-panel-3`, 5px inset); flat SVG marks on Game cards get a 13px inset
(`.game-card img[src$=".svg"]`).

The Game change matrix (`table.dyn[data-what]`, built for the Game kind by `dynamics_page`) draws each system icon
whole: `object-fit: contain` on `td.name img` (the Souls icon, 35x67, was cropped to a swirl). The `.dt-head img` of
a hover card is `contain` as well.

## Completeness audit (2026-11-13): what was in data/ and on no page

- **THE gameplay rule of every builder** is `cards.is_gameplay` / `cards.gameplay_rows` (`builders/brawl.py`): the
  gameplay categories plus Street Brawl's own rules. `gameplay_entities`, the entity histories, `patch_counts.page_set`,
  the trail squares, the value eyes and the build pages all read it (seven hand copies of `c['cat'] in GAMEPLAY`).
- **Street Brawl** (category `streetbrawl`, classify.py): the mode's item draft rounds, tier buckets and backdoor
  protection against players are gameplay rows in words (`brawl.rule_label`: "Round 1 draft: 3 rare items (weight)",
  "Draft of tier 3 items: Good bucket (weight)"); the 2026-09-29 re-keying of the rounds reads one label on both sides,
  so it is no change. The heroes' item draft weights (`m_mapItemDraftWeights`, 971 rows) never reach a hero page: a
  patch's weights are ONE row (`brawl.draft_row`, key `brawl:draft_weights:@drafts`) of Game › Modes ("Item draft
  weights: 18 heroes, 140 items"), its lines (hero or heroes › item: old → new) in a fold inside the row
  (`brawl.drafts_html`, `details.drafts`, not `.erow`: scripts.js counts the row once), one change for every counter —
  the band, the Game index card, the matrix (`dynamics_page`), the home icon (`home_page._feed_rows`) and the patch's
  count (`patch_counts._placed_rows`, as a Game row like the console variables). Placed by the config's subject
  `brawl:draft_weights` (part modes.brawl).
- **No card is a name over nothing** (`cards.writes_rows`, `patches_pages.shown_entities`): a build page's event row
  has its path (`@add` / `@return` / `@remove`, as in a patch record) — without one `is_noop` read "Removed from game
  data" with no value as an empty removal (199 empty cards on 40 build pages); an entity whose rows are all no-ops has
  no card and no `c-<id>` anchor (`change_anchors`; 50 on patch pages, 22 on build-6801).
- **Build pages**: every entity, text change and console variable is on the page — past `ENTITY_LIMIT` the entities
  fold under "More entities" (`builds_pages.split_limit` keeps a hero's abilities in its one card), texts and variables
  were cut at 500 / 400; a variable carries its status in the update (`convar_statuses`: the eye, as on the patch and
  Game pages); "Other data fields" (`other_rows` / `other_section`) lists the non-gameplay rows (technical, looks,
  sounds, interface, meta, the draft weights) of entities that did not come or go — 74 builds said only "0 gameplay
  fields"; binary strings with no word of 4+ letters are not listed and a build whose listed strings are all such
  bytes has no strings section (`build_tech.is_word_string`; 133 builds showed only ".l/gwk").
- **A new entity** (`builders/arrivals.py`, applied by `archive.patch`, so every page and counter reads it): its
  `@add` row carries `came_with`, the key numbers of the build that added it (`cards.ADDED_KEY` first, at most 8,
  `game_now._ADDED_NOISE` out; printed by `render.shown_pair` as a list), and a field a later build of the same window
  moved is its own row (first old → last new, its builds, status hidden unless the arrival is work before release or
  an update with no notes). The matcher folds those builds into the arrival (`match_window.merge_ops`), so Eternal Gift's
  Respawn Time −90% → −70% (6135) was on no page.
- **A neutral's attacks** are effects its entry names (`m_vNeutralAbilities`, `m_sNeutralMelee`):
  `classify.unit_bound_modifiers` → the catalog's `units` on those modifiers.vdata entries → `page_keys`, the unit
  page's groups (`entities_pages.unit_attack_name`), `home_page.page_route`, the unit matrix. Data: from the next
  catalog run.
- **Folds over nothing**: `cards.entity_rows` folds an arrival's many fields under "Added to the game" only when some
  are key fields and none is a console variable (2026-06-30's 13 new Urn variables, Nox Nostra's 15 new tier bonuses
  on build-6801 were heads over nothing).
- **List labels** (`builders/list_labels.py`, in `gameplay_rows`): "value #3 › Lane Name" → "Lane 3 › Lane Name" (by
  `LIST_NOUNS`), Street Brawl's per-round lists "Buy Time #5" → "Buy Time, round 5", "Vitality purchase bonus, tier 3:
  value" → "…, tier 3".
- Console variables placed (`data/overrides/game_systems.json`, `_why_convars_2026_11_13`); the footer links Builds.

## Hero / unit stats

`hero_page.says_nothing`: a stat at its neutral value (`NEUTRAL`: +range / resists per boon 0, headshot taken
×1) or a pellet / burst detail of a one-pellet / no-burst gun (`NEEDS`) is not drawn unless its history has a
real step (`_real_steps`). Units ride on the numbers everywhere (`_split_unit`). `NOT_ON_HERO`: crouch speed. Hero Stats: reloads 2 decimals, intervals 3,
the newest build (`unchanged_since` keeps the last build that changed a hero).

The values of today are ONE component, `builders/now_values.py` (`Row`, `group`, `flow`): a unit's single-tier stats
(`hero_page.stat_tables`), a hero's stats when it has none of the game's panels (`hero_page.more_stats`), an item's sections (`entities_pages.item_page`
→ `hero_page.prop_values`) and a Game system's entries (`game_now.now_block`). `flow` is `.stat-flow`, CSS columns
(`columns: 330px auto`, 24px gap, a rule between). A `group` is `section.stat-panel`: an `h3` (none for an item's
untitled section, class `untitled`), an optional `.vg-top` (an item section's header chips `.chips.vg-hdr` and its text
`.vg-desc`), then `.sc-row`s (`.k` label, `.v` value at the column's right edge; `p-<css>` colours an item's value as
the game does). A group stays whole (`break-inside: avoid`); a group of more than `LONG_GROUP` (8) rows (`.long`) and a
lone group may break, and a lone group's heading and top span the columns (`:only-child`, a structural pseudo, no
`:has()`). In a group every row has an icon slot (`.si`, empty where the game has no icon) or none does. A hero's other
stats get the component's own ground (`.now-open > .stat-flow`). A Game system's console variables stay a panel after
the groups (`.now-flow > .stat-panel.now-cv`), their rows in their own columns (`.cv-rows`, the same 24px gap). The
tiered unit table (`table.kvt.tier-grid`) is unchanged. Every table box hugs its table at the page's left edge
(no auto margins; `.table-fade.center` and `render_table(center=)` are gone), under its title, bar and band.

## Entity page head and history updates

"patch ↗" (`history_view.patch_href(pid, rel, id, also)`): the notes' card (`#n-`) or the All changes place
(`#c-`) of the page's own id, then of the band's other ids (a family's members); an id with no place on the patch
page links the page itself. A band that holds only rules for all links its Game band (`every_href`) instead.

The rules-for-all button says what those bands hold when the page gives no label (`every_label=None`: "For all
abilities & items" on a unit page; several kinds: "Rules for all").

The "Removed" chips of a hero page (`hero_page.removed_parts`) are the hero's abilities that are gone from the files, or
were bound in a slot once and are not today. An ability that no slot ever bound but that is still in the files is today's
kit, so it is not listed as removed (Move King, Move Piece). `hero_page.every_history_fold` is `history_folds` for every
hero; the home feed uses it, so a hero's icon counts what its history band counts.

`builders/evidence.py`: the eye on a history row names the build(s) whose game files carry the change and opens that
build's page at the row itself (`builds/<n>.html#r-<hash>`: `row_anchor(key)` = 'r-' + the first 12 hex of the sha1 of
'file:id:path'; a shared edit's block in the build record is 'file:@shared:path'), else at the entity's card (`#c-<id>`:
a hero's ability lands on its hero's card; a folded row — REWORK, a re-keyed field, a family head — or a row the
build page writes without an anchor), else on the page itself (a shared edit with no row of its own there).
`patch_builds(builds, rel, pid)` (a ContextVar, set by `history_view._patch_block` around a band) gives
`row_evidence(c)` → (words, href, late): "Not in patch notes — in the game files of build 6444 (2026-04-10) · click to
open that build"; a window with no changelog and no hero release (its rows are `unannounced`): "No patch notes for this update — …"; several builds by name (at most 3 in
the data), more as "6 builds, A (…) to B (…)". A build is dated by the game build's own date (`game_date(file)`: the
record's `version_date`, "Oct 14 2026 20:01:37" → 2026-10-14), not by the tracker's UTC commit time. A change came
after the patch (`late`: "Not in patch notes — came in build 6444 (2026-04-10), after the patch") only when its build
is newer than the notes' own build and carries nothing the notes announced: `notes_window(pid)` → (the build an
announced change came in most often, the earliest of a tie; every build of an announced change — all its builds, not
only its first; the notes' date); in a window where the notes matched nothing, a game build dated after the notes.
Until 2026-10-17 it was "any build but the window's first" — 4,727 claims, about 1,400 now: Deadman Danny's 10-14
rows sat in 6785, the notes' own build, while the window's first, 6782, carried nothing. Not the FIRST announced build
either: 2026-01-30's 6198 carried 2 of its 140 announced changes a day early. The `.late` row keeps its full eye in an
all-hidden band. A build number the tracker committed twice keeps its last commit (the first of such pairs holds no
gameplay rows). `band_evidence(rows, anchor)` gives the band's chip its words and build.

`common.mark(status, tip, href)`: with `href` the mark is `<a class="mark hidden">` in the tab order (until 2026-10-17
a row's eye was `tabindex="-1"` and the keyboard reached no row's proof), its words written once as its `aria-label`
(an empty `data-tooltip`; scripts.js `tooltip` reads the label). The band's "N not in patch notes" chip is ONE link
(`history_view._eye_chip`: `<a class="chip eye-chip">`, the words as its `data-tooltip`, "N not in patch notes —
words" as its name, renamed when a filter recounts it: scripts.js hist-filter `named`); without a build to open it is
a span with the plain eye. In a band the notes never mentioned (`.all-hidden`) every row keeps a dimmed eye (opacity
.7: a link icon keeps 3:1 on the row; .45 read 2.6:1), full on hover / focus. A family head's eye sits in a
`<summary>`: words only, no link (`row_evidence(..., link=False)`), its rows' eyes link. Touch (`(hover: none)`): the
first tap shows the words ("tap again to open"), the second follows, for `a.mark[href]` and `a.eye-chip[href]`; a
hidden tip disarms. On a touch screen the tooltip ignores mouseout / focusout — a tap's compatibility events hid the
words and disarmed the link between its two taps on CI's Linux Chromium (2026-10-06); a tap elsewhere hides them.
styles.css lights a linked eye on hover.

A fragment is written only when the build page has that place. `evidence._facts(file)` reads each build record once
→ (`build_anchors`: the cards, `patches_pages.own_anchors(builds_pages.page_entities(rec)[:ENTITY_LIMIT])`;
`build_rows`: the row anchors, `builds_pages.unique_keys` — a key the page writes twice, two '@shared' blocks with one
path and other values (41 rows in 15 builds), has none, so an eye cannot open the wrong block; `game_date`). Folded
rows carry their sources' builds and entity (`render.folded_source`: a REWORK tier swap, a Corrupted / Enhanced
version, `row_rules.merge_renames`, a family head). On 2026-10-17: about 8,700 eye links and chips on hero / item / unit /
Game pages, ~6,200 of the ~6,900 row eyes on their row, 0 to a missing id.

Build pages (`builds_pages.build_page`): `notes_of(pid, build)` → {row key: its status in the build's update} for the
rows the build carries (a shared block under its block key and each target's; a key two rows give two statuses is
left out). `page_entities(rec, statuses)` gives every row its status when the notes left it out (`_status`, NOT_IN_NOTES:
the eye; a shared block by its targets' statuses — one for all, else quiet —, then its own key; a new entity's field by
the entity's one `@add` row), else 'raw' (quiet, as on an entity page: a mark on every row grew 5554's page 0.5 MB),
and a `src` = (file, id, path, op, old, new). While the cards are written (`evidence.build_rows_scope(diff, dupes)`),
`cards.change_row` asks `evidence.row_source(c)`: a row whose `src` still is its own (`source_of`: its path, op and
the very old / new objects — a row folded from several has none) becomes `<details class="src" id="r-…"><summary>
{row}</summary><div class="src-b">…</div></details>` (no id for a key the page writes twice): file › entity › path
(internal ids on purpose: the proof), the raw old → new (JSON, cut at 160 characters), "file diff ↗"
(`href="#df-<file>"`; scripts.js `build-src` gives it the head's URL when it opens) and, by the row's status, "This
update's notes: no line mentions this" / "No patch notes for this update". The head links the tracker's commit
(`evidence.commit_url`: builds before 5044 come from Lifeismana/Deadlocked, the rest from
SteamTracking/GameTracking-Deadlock — checked against both clones for all 622 builds) and each data file's diff once
(`evidence.diff_url`: the commit URL + '#diff-' + the sha256 of 'game/citadel/pak01_dir/scripts/<file>'; GitHub may
not render every file of a commit with thousands of asset changes, the link then opens the commit). A new entity's
rows under "All fields" get no source (`change_row(c, source=False)`: 5554's page would be 4.2 MB, it is 2.8).
`cards._layout` is the one plan of `change_rows` and `listed_rows` (the rows written with a source: what
`builds_pages.shown_keys` counts); tests/test_eye_to_proof.py holds the written ids to `build_rows` for four builds.
scripts.js `build-src`: `#r-…` in the address (load or hashchange) opens that row's source and every fold around it
and scrolls it under the site bar and the sticky search (`details.src { scroll-margin-top }`); `:target` lights it
(`--eye-14`). A REWORK row's "more ▾" inside such a summary opens the list, not the source (rework-lines).

Described rows keep Valve's line as the quiet "Patch notes" note under the group (`valve_notes`); documented rows
need none. The patch archive's All changes rows keep the plain eye (2,598 hidden rows on City Never Sleeps' page).

Description changes print what the game printed. `pipeline/entity_texts.with_values` gives every name /
description / tier text change that holds "{s:Prop}" tokens a `vals` = `{'old': {token: value}, 'new': {…}}`: the
old text's values are read at the build before the patch window (`match_window.window_states`: the first build record's
`prev_commit`), the new text's at the window's last build — the same two states the window's merged change rows
compare. `match_passes.text_state` reads that build's abilities.vdata (parsed-file cache, two blobs memoised: neighbouring
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
(`patch_counts.counted_rows`, as `home_page._feed_rows`): City Never Sleeps 360 → 335 not in patch notes, Rat King's
"in game rules & map objects" 3 → 2.

A hero with no role in the files yet carries `data-role="*"`; scripts.js dyn-rows lets "*" through every role.
hist-tip: the "Overall" percent uses the steps' rule (two negatives by size: `pctOf`).

`pipeline.catalog.dead_namesakes`: shop items of one name, some out of the shop (removed, or disabled in the
files): one beside a namesake in the shop is "(old)"; several "(old, added <date>)", else "(old, tier N)", else
"(old, #n)" — "Toughness (old, added 2025-05-08)" / "(old, added 2024-06-06)", "Extra Large Magazine (old, #1)".

Home: a section whose icons are all out of the notes carries the chip `span.chip.lu-all` (see Home above); an
update with no changelog and no hero release shows no chip. The Items tile shows six shop items.

Game rules (`game_rules.rules_page`): one column at the page's left edge (`.rules-col`, under the title and tabs), a
variable search, the table scrolls with the page under a sticky head, "NEW" for a variable added with no move yet. A
name breaks after its underscores only (`common.wbr_ids`, `overflow-wrap: normal` at ≤ 700px). At ≤ 700px the Changes
column (`.cn`) hides and its count rides under the date (`td.lc .lc-n`: "3 changes" / NEW).
`game_systems.is_dev`: the designers' test objects are on no Game page.

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
`tests/test_dynamics_page.py::test_band_chip_and_matrix_cell_weigh_the_same_rows` builds one hero's band and matrix cell
from the same fixture (a rule for all, work before release, a removed ability, a sideless patch).
The matrix also drops the repeats a hero page drops (2026-10-06, the last 5 of 4,476 cells): `hero_page.history_folds`
maps an alt fire to its gun and a nameless sub-ability to its parent, and `_collect` removes their rows the gun /
parent already has in the patch (`hero_page.repeats_dropped`, the `_sig` of fold_alt / drop_parent_rows). And it
reads one entity's records in a patch (its own and each shared block it is in) as ONE list, as the page's group does:
a shared "Corrupted: Bonus Health" folds into the item's Corrupted version (Veil Walker 2026-09-29 was a second NEW);
Game entries stay apart. Band chip and cell now agree on every cell of all four matrices;
`test_matrix_cell_drops_the_repeats_the_page_drops_and_reads_an_entity_as_one_list` keeps it.

A patch page's "Biggest changes" (`patches_pages`, `table.hist.big`) stacks each row into two lines under 700px —
name and tag, then label and old → new — instead of a table 235px wider than a 390px phone.

A banner (`.banner`, `.banner .bc`) wraps its chips under the title when there are many: Astro's band of 21 changes,
its net chip, the eye and three "+N for all …" chips ran 67px past a 1440px window (2026-10-06). A patch page's note
cards (`.ecards`, one column since 2026-10-17) load their icons at `load` like the matrices' row icons (scripts.js `dyn-icons`): each
icon arriving mid-scroll re-balanced the columns of up to ~2,000 elements — patches/2024-10-10.html spent 1.4 s in 14
layouts while scrolling (p95 83 ms), now 0 layouts (p95 16.8 ms). In `data/overrides/game_systems.json` the combat
rules name every zipline modifier (`modifier_zipline_\w*`): the bare prefix before `#` matched only an id that ended
there, and the Zip Line speed bonus fell to Other with its note line unmatched.

classify: `m_bSpawnOnGround`, `BuffTypeValueUnit` are technical.

Removed items show their last values.

Troopers' alt / super / new-model copies are on the Medic / Melee / Trooper pages.

Buff vs nerf in the change matrices weighs how big each change was.

Visual pass 2026-10-17 (entity track). The "today" panels are one component, `builders/now_values.py` (see Hero /
unit stats). `entities_pages.header_host(sections)` picks the section that carries the header values no section lists
(`header_only`): the Active section, else the Passive, else the first non-Innate, else the first. Its `.chips.vg-hdr`
row sits above its text and rows; an item without sections keeps the left-aligned `.chips.item-hdr` row.

Hero head: a `.hero-head` grid. The portrait is column 1 over three rows (110px under 980px, where it takes row 1 and
the name stays beside it; 88px under 420px). `.hh-id` (name, chips, "First seen") and the patch strip (`.head-strip`) are column 2; under 980px the strip takes
the whole width below the name. Ability cards: the grid is `align-items: start`; `.ac-hdr .chip` is 15px. Weapon block:
one column — `.wb-id` is the header row (kicker, name, last change, History, trail), then the game's panels
(`hero_panels.panels`).

Trail (`trail.trail_html`): on the entity's own page (`local=True`) a trail with fewer than `TRAIL_MIN_LOCAL` (2)
changes in its span is not drawn; an empty slot (`span.sq`) is a 2px dot; a hidden square is a 3px eye-coloured top
edge. Tiles (strip `.ps-tile`, matrix `.dsq`): hidden = `border-top: 4px solid var(--eye)` (the stripes keep their
proportions below it; no `::before/::after` plate), the count `.dn` on a `--shadow` plate, 9px under 760px. The
strip's own tiles (2026-11-13): a 3px eye top, the count centred at rest, the tags' bar as `::before`.
`patch_strip.month_cues(dates)` gives a strip tile its `data-m`: "Oct" under a month's first tile, "2026" under a
year's first (labels at least `CUE_GAP` 2 tiles apart; a year's label wins over the month before it).
`.ps-tile[data-m]::after` draws it in the strip's bottom padding (`.patch-strip` padding 10px 8px 21px); the tile's
aria-label and hover card carry the whole date.

History bands: `.hblocks .banner .bc > .chip / .net-chip / .pnotes` share one spec (600 11px UI font, 20px, 0 7px
padding, outline and ink from `--c`), "patch ↗" is a chip too; under 700px `.bc` takes its own line, left. The %
follows the new value (`.pct` no longer pushed right; the hover ruler and `.pct-pad` slot are gone on entity pages). A
year banner gets `every-only` / `dev-only` / `ed-only` when all its bands wait behind "For all …" / "Before release"
(`history_view.band_kind`, `year_class`); styles.css hides it while the switch is off.

Phones (≤600px, `.hblocks`): `.hgroup.has-ic` is a 38px + 1fr grid with `.hg-b { display: contents }` — the icon sits in
the sub-head's row, the rows span the width; an `.erow` is a flex-wrap row with the eye and the tag absolutely placed at
its left (label from 26px + `--tag-w` + 8px), the label and a short value on one line, a long value under the label.
`common.wbr_ids` puts `<wbr>` after each `_` of an underscored name of 14+ characters (`WBR_MIN`) in a change row's label
(`cards.change_row`) and a console variable in the "now" panel (`game_now`). Folds (`details.txt`, `details.fam`) show
their +/− before the words (`::before`). scripts.js `rework-lines`: a REWORK row whose two-line clamp cut its list gets
`.clamped` (measured after load, a band's toggle and a resize; reads, then writes) and a "more ▾" / "less ▴" line; a tap
on the values toggles it.

Visual pass 2026-10-17, round 2 (entity track). The head's key stats and the weapon's number grid of that pass gave way
to the game's panels (owner 2026-10-22) and were removed on 2026-11-13. An alt fire's tile (`.wcell`) keeps the icon's
corner slot: `_stat_icon` writes an empty `.si` where the game has no StatDesc icon (radius, spread, gravity, lifetime).

The patch strip is in the head: `history_view.head_strip(told)` gives `.head-strip` = `.hs-l` "Patches" + the strip (and
the hover cards' blob); with one patch (`told['strip_tiles']` is false, set by `history_table` with `facts_out`) only
the blob comes. A hero's strip is a grid item of `.hero-head` (column 2, under `.hh-id`). An item's, a unit's and a
Game system's is the last child of `.page-head`: `flex-wrap` puts it on a row of its own at the name's edge
(`margin-left: 96px + 2 × --px + 18px`; on a phone at the icon's edge), and the name block keeps `flex: 1 1 0` beside
the icon. Game system pages pass `facts_out` as well.

`.head-strip` is a grid: `.hs-l` ("Patches") | the strip, and `.hs-l` has `margin-bottom: 13px` to sit level with the
tiles. A strip with any orange top is followed by `div.hs-key` (`dynamics_page.cap_key()`: a 12px tile with the
eye-coloured top and "some changes not in patch notes") in the grid's second column, under the tiles from their left
edge.

A history band's title is `common.band_title_html(row)`: `.pdate` first (700 18px UI font, tabular figures), then
`.pname` (gold, pixel caps) or `.pkind` "Update", then `.pfu` for a follow-up, so the dates line up from band to band.
`.hblocks .pblock > .banner` is a `--patina` `color-mix` gradient, and a named update's banner takes `--gold`.
`patch_title_html` (patch pages, home, indexes) is unchanged. The rule-for-all link row (`cards.every_links`) reads
"N changes for all <what>" with "see <Game system> ›" and its tag counts.

Hover cards: `table.dt-rows td.dt-tg + td.dt-field` has `min-width: 10em` (strip, trail and home cards), so
"Min Sleep Time" keeps one line; the change matrix's card has no tag column and is unchanged.

`history_groups._groups` (merge mode = Game system pages): every `…:convars` key of a band with no lines or texts of its
own joins ONE group (its areas are all its keys' parts). `written_notes.with_owner`: a removed ability's line takes the
catalog's owner for its subject (the record and the pages' routing are unchanged).
