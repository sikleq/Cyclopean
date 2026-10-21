# TODO — deferred owner tasks

Start only on the owner's word. Order: by date written. Done items: strike through with date and commit.

## Ideas from deadlog.io (written 2026-10-19, not started)

deadlog.io (studied 2026-10-19, owner asked "analyse, don't continue"): a Deadlock changelog of Valve's patch-note
TEXT only (no hidden/datamined changes, no current stats, no units, no tables/matrices); labels buff/nerf/mixed/
rework/QoL/fix/note from wording; data from Steam announcements, icons hotlinked from deadlock-api CDN; SvelteKit +
static JSON on Cloudflare; lags (missed 10-14 and 10-16 on 10-19). Shots/text: session scratchpad deadlog/.

Ideas ranked for Cyclopean (none started): 1 search in change TEXT (incl. hidden) with entity chips + URL (M);
2 value timeline for every number, not only ~25 key stats (M); 3 revert marker "reverts 2025-05-08" exact from files
(S-M); 4 entity-page tag/ability filters in URL + counts on tag badges (S); 5 per-line permalinks, short hash not id
(S); 6 sticky year→patch jump rail in History (S-M); 7 home feed filtered by a picked hero (M); 8 top 1-2 lines on home
update cards (S); 9 "changes · updates · last changed" + "most changed / most hidden" sort on index tiles (S);
10 finer Game anchors (ziplines, jump pads, shrines…) (M); 11 mechanic chip on general note lines → /game/x (S);
12 per-update social preview image at build (M); 13 mobile touches (S). Missing data: patch author + post time
(Valve's posts), Matchmaking as a notes-only system, a MIXED tag for one line both buff and nerf.
Keep Cyclopean's edge: files-based values, hidden changes, value-polarity direction, units, matrices.

## Track silent edits of patch-note posts (written 2026-10-19, not started)

PLAN, not started (2026-10-19; came from another session at the owner's request). Do only when
the owner says.

Idea (seen on datavpk.com, Dota 2, Monitor → News "edited"): Valve silently edits patch-note posts after release —
Cyclopean could mark an edited post and show what changed in its text.

How (checked 2026-10-19 by that session):
- Steam events feed for Deadlock: https://store.steampowered.com/events/ajaxgetpartnereventspageable/?clan_accountid=0&appid=1422450&offset=0&count=100&l=english
- Each event: `announcement_body.posttime` (published) vs `announcement_body.updatetime` (last text edit) —
  different = edited (Dota example: "7.41f Gameplay Patch" posted 15.09 18:44 UTC, fixed 18:55).
- `rtime32_last_modified` is useless for this: it changes daily on every post (Deadlock too).
- To show WHAT changed: store `announcement_body.body` per version and diff against the next one.

**Why:** fits the site's core (what Valve said vs. what changed); notes are already fetched from Steam News
(docs/data-sources.md). **How to apply:** when asked, add to the notes fetch (pipeline) + a mark on the patch
page; live checks stay separate from deploy (AGENTS.md rule 9).

## Owner answers of 2026-10-21 (to the questions below; all done in 250f7cb, not pushed yet)

Q14 was no break: release_pass described the hero's stats on purpose (option A); now its numbers are hidden.
Q11: 33 units still have no art in pak01_dir.txt (two found: Nurse leech, Nano rollermine).

| # | Answer |
|---|---|
| 2 | Rework strip tiles like Sloppy: wider dynamic cells, colour at rest, main info on hover |
| 3 | A (no names). Restyle the "All / Not in patch notes" switch: it stands out from the design |
| 4 | Remove the big home wordmark and hub H1s; logo only in the site header like Sloppy ("sikleq \| dota.vpk"), section names only in the header. Logo will be redrawn later |
| 5 | B (one height). Also restyle the cooldown / cast time / duration / date labels: font or look is off |
| 6 | A; check every hero stat is in the key stats |
| 7 | B (smaller); maybe in a circle or square |
| 8 | B: every table stretched to full width (rule for all tables) |
| 9 | Show mm.dd; the year as a divider |
| 10 | A for now |
| 11 | "?" placeholder when there is surely no icon/portrait, and for WIP / unreleased units |
| 12 | Same placeholder for items; unreleased items not in the shop, or in their own "unreleased" category |
| 13 | B: Violet's sketches on Violet's page |
| 14 | B: release post covers the kit, stats are hidden; the site shows A (Nurse, Deadman Danny): find the break |
| 15 | A (no page) |
| 16 | A: keep the path; exception recorded in project memory, not AGENTS.md |
| 17 | B: covered by "Full shop rework"; update the audit reference |

## Owner questions from the visual pass of 2026-10-17 (written 2026-10-20, answered 2026-10-21 above)

The site is live as described in "now"; an answer only changes it if it picks the other option. Ask the owner
these at the start of work; Q1 (delete worktrees) is answered and done (2026-10-19).

| # | Question | Now (A) | Other option (B) |
|---|---|---|---|
| 2 | Hidden mark on strip / matrix tiles | orange top edge, stripes whole | the eye glyph on the tile (eats part of the stripes) |
| 3 | Names under the home feed icons | none on any update (hover / first tap names it) | names on every update (a big update twice as tall on a phone) |
| 4 | Big home wordmark and hub H1 ("Heroes" under the "Heroes" tab) | kept | smaller on a phone, or removed |
| 5 | Ability cards | each ends at its last tier (ragged bottoms) | one height, space inside short cards |
| 6 | Health tile in hero key stats | wider so rows are whole and columns align | equal tiles, a hole at the end |
| 7 | Trooper role marks (game build-browser tags) | large, top-right corner (42%) | smaller |
| 8 | Tables on wide screens | left-aligned (Game rules leaves ~1000px empty at 1920) | stretched to full width |
| 9 | Short month label in matrices | "Dec" | "12" |
| 10 | Head chip "skins in the works" | shown | removed |
| 11 | Units with no game art (Overseer, Hideout toys, weak points) | site glyph on their own pages | hide their cards |
| 12 | Items with no art ever (Stabilizing Tripod) | glyph | fold into "+N" like units |
| 13 | Violet's sketch pickups | Game → Pickups "Violet's sketches" | on Violet's page (needs non-ability owner support) |
| 14 | Hero release window | kit = announced by the release post, other rows "not in patch notes" | — confirm |
| 15 | A page "every hidden change, newest first" | not made (patch-centric); matrices have the "Not in patch notes" switch instead | make the page |
| 16 | Raw game names in the proof on build pages (file › entry › field path) | shown inside each row's source block | AGENTS.md forbids ids on pages: allow as an exception, or hide them |
| 17 | 2025-05-08 shop rework: item slot / tier / cost moves | hidden (the audit reference says so; covering them drops "real hidden kept" 93% → 89%) | announced by "Full shop rework" |

Smaller owner questions from the tracks (decide only if asked): body text stays 14px (15px wrapped 8% more on
phones); Walker / Patron get no II / III numerals; Rat King's three rats share one icon; a matrix sideways scroll
with Older patches on costs p95 ~40 ms on a 4x slower CPU (sticky month labels); Hero Stats box shorter on desktop
(613px) to keep the header in view; footer wraps to 4 lines at 390px.

## Leftovers from 2026-10-17 (not started)

- Restorative Shot "Can target +allied heroes" (build 6790: target types gained CITADEL_UNIT_TARGET_HERO_FRIENDLY and
  `m_bProcOnFriendlyBulletHits = true`): reads raw on the site; word it plainly (e.g. "now also procs on allied
  heroes"). Recheck after Nurse Harrow's release (announced for 2026-10-20) whose kit may explain ally hits.
- Merge identical changes across many abilities into one row ("+can't be purged on 23 abilities") — no existing fold
  does it (each row has its own modifier label).
- Pair related console variables into one plain line (souls ticks: period 3s → 2s with pulses 3 → 2 = same income,
  more often).
- Release windows: a window takes the nearest announcement post within 2 days without checking it names the hero;
  a hero added directly as Release gets no window; texts in a window a release interrupts read the states around
  the gap.
- Three Baba lines of 10-14 stay unmatched (code changes; Baba's files moved, so not marked "code").
