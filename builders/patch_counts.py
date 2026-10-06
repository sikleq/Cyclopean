"""ONE count per patch of its changes and of those not in its patch notes, for every place that shows one: the home
feed's update banners and the home totals, the patch page's check line, its "All changes" tab and its "Not in patch
notes" filter, the patch list (coverage audit 2026-10-05: City Never Sleeps read 1232 on its page and in the list —
the matcher's raw field counts —, 620 under "Only hidden" and 212 on the home page — rows on hero / item / unit pages
only).

Counted is what the patch archive's "All changes" lists, the whole update: its gameplay rows as a player reads them
(`cards.gameplay_entities` → `cards.player_facing`: plumbing out, renamed fields merged, variants of one object
merged), an edit shared by many entities once. `not_in_notes` is `render.NOT_IN_NOTES` (hidden, and an update with
no notes at all: unannounced), the same rule an entity page's bands, strip tiles and eye filter use; work on heroes
still in development (unreleased) is counted apart. `hidden_on_pages`: those of them a hero, item or unit page shows
— THE pages (`entities_pages.page_entities` / `page_keys`, `page_set`; a shared edit when one of its targets has a
page). The rest is exactly what the Game section shows (`game_systems.place_entity` with the same keys): it read
`home_page.page_of`, which gives no page to a helper unit or a unit's own ability, so those were "in game rules &
map objects" while their rows were on unit pages (review 2026-10-05)."""
from __future__ import annotations

from collections import Counter
from functools import lru_cache

from .common import load_json


@lru_cache(maxsize=1)
def page_set() -> frozenset[str]:
    """The entity keys a hero, item or unit page shows — the same set the entities step builds its pages from
    (`entities_pages.page_entities` over the keys with changes of their own in any patch)."""
    from . import archive
    from .cards import GAMEPLAY
    from .entities_pages import page_entities, page_keys
    from .shared_rows import entities as spread_all, is_every
    ents = {f"{e['file']}:{e['id']}": e for e in load_json('entities.json')['entities']}
    mine: set[str] = set()          # entities_pages.changed over its _history
    for row in archive.index():
        for e in spread_all(archive.patch(row['id'])['entities']):
            if any(c['cat'] in GAMEPLAY and not is_every(c) for c in e['changes']):
                mine.add(e['key'])
    trow = {r['id']: r for r in load_json('tables/heroes.json')['heroes']}
    heroes, items, units = page_entities(ents, mine, trow)
    return frozenset(page_keys(ents, heroes, items, units))


ALL_ROWS = '@all'          # _counted_as: a rule for every hero / ability, grouped row by row


@lru_cache(maxsize=1)
def unit_main() -> dict[str, str]:
    """A unit id -> the id of its family's page (unit_families: the five Gutter Ghouls I are one page)."""
    from .unit_families import families
    ents = load_json('entities.json')['entities']
    fams = families([e for e in ents if e['file'] == 'npc_units.vdata' and not e.get('template')])
    return {m['id']: ms[0]['id'] for ms in fams.values() for m in ms}


def _counted_as(e: dict, pages: frozenset[str] | set[str]) -> tuple[str | None, bool]:
    """(the group inside which one edit counts once, whether a hero / item / unit page shows the rows) of a patch
    entity — as the home icons route it (home_page.page_route / _feed_rows): a unit family's page, a Game system; a
    rule for every hero or ability is its Game system's (on a hero page it is a link row, no row of its own)."""
    from .game_systems import place_entity
    from .home_page import page_route
    from .shared_rows import FOLD_FILES, catalog
    if e.get('id') == '@shared':
        if e.get('scope') == 'all' and e['file'] in FOLD_FILES:
            return ALL_ROWS, False                   # each row its own system's (place_all_row)
        targets = e.get('target_keys') or []
        if any(k in pages for k in targets):
            return None, True
        # one edit over map objects no page shows (sixteen breakables): their Game system's
        cat = catalog()
        for k in targets:
            hit = place_entity(k, {**cat.get(k, {}), 'file': k.partition(':')[0], 'id': k.partition(':')[2]})
            if hit:
                return f'game:{hit[0]}', False
        return None, False
    info = {**e, **catalog().get(e['key'], {})}
    where = page_route(e['key'], info, pages, unit_main())
    if where:
        return (where[0] if where[1] == 'units' else None), True
    hit = place_entity(e['key'], info)
    return (f'game:{hit[0]}' if hit else None), False


def drop_inherited(ents: list[dict], pages: frozenset[str] | set[str] | None = None) -> list[dict]:
    """A patch's gameplay entities without a template's edits its heirs carry (trooper_base's "Max Range vs Shrine" is
    on the Medic, Melee and Rifle Troopers): theirs, as the home icons route them (home_page._feed_rows: a template no
    page shows; an entity's own coming and going stays). The count and the patch page's All changes start here (review
    2026-10-05: City Never Sleeps' banner counted 15 such rows twice, Rat King's said 3 off the pages over two Game
    icons of one change each). Copies; an emptied template drops out. `pages`: `page_set`."""
    from .game_systems import heir_sig, heir_sigs, is_template
    from .shared_rows import catalog, entities as spread_all
    if pages is None:
        pages = page_set()
    cat = catalog()
    heirs = heir_sigs(spread_all(ents))
    out = []
    for e in ents:
        if (e.get('id') != '@shared' and e.get('key') not in pages
                and is_template({**e, **cat.get(e.get('key'), {})})):
            kept = [c for c in e['changes'] if heir_sig(e['file'], c) not in heirs]
            if len(kept) != len(e['changes']):
                if kept:
                    out.append({**e, 'changes': kept})
                continue
        out.append(e)
    return out


def counted_rows(p: dict, pages: frozenset[str] | set[str] | None = None) -> list[tuple[dict | None, dict, bool]]:
    """THE rows `count` counts, in the patch archive's order, as (entity, row, whether a hero / item / unit page
    shows it); a console variable's row has no entity. The patch page's written notes ("Not in patch notes", "From
    the files") list exactly these, so a tab says the number it lists (review 2026-10-05: City Never Sleeps' tab
    said 360 over 353 lines — the console variables were counted, not listed)."""
    return [(e, c, place == PAGE) for e, c, place, _ in _placed_rows(p, pages)]


PAGE, GAME, ARCHIVE = 'page', 'game', 'archive'     # where a counted row is shown besides the patch archive


def _placed_rows(p: dict, pages: frozenset[str] | set[str] | None = None):
    """`counted_rows` with where each row is shown — PAGE (a hero / item / unit page), GAME (a Game system's page and
    its home icon) or ARCHIVE (the patch archive only: a designers' test object no Game page lists) — and on how many
    home icons a PAGE row sits (one edit over several heroes or units: on each of theirs, once in the count)."""
    from .cards import gameplay_entities, player_facing
    from .game_systems import place_all_row
    from .shared_rows import spread
    if pages is None:
        pages = page_set()
    once: set[tuple] = set()
    for e in drop_inherited(gameplay_entities(p['entities']), pages):
        rows = player_facing(e['changes'])
        if not rows:
            continue
        group, on_page = _counted_as(e, pages)
        on_page = on_page and any(x['key'] in pages for x in spread(e))
        if e.get('id') == '@shared' and not on_page and group not in (None, ALL_ROWS):
            # one edit over map objects of several Game systems counts once in each, with the status of its first
            # entry there — as those systems' pages and home icons show it (City Never Sleeps: the powerup spawner's
            # copy, hidden, sat on the Pickups icon while the count took the block's "described" once, in Breakables)
            yield from _by_system(e, once, group)
            continue
        icons = _icons(e, pages) if on_page else 0
        for c in rows:
            if group is not None:
                # one edit over a unit family's members or a Game system's entries counts once, as their pages, the
                # change matrices and the home icons count it (Walker's four ids, twelve breakable props)
                g = f'game:{place_all_row(e["file"], c)[0]}' if group == ALL_ROWS else group
                sig = (g, c.get('label'), c.get('old_s'), c.get('new_s'))
                if sig in once:
                    continue
                once.add(sig)
            yield e, c, PAGE if on_page else GAME if group is not None else ARCHIVE, icons
    # the console variables a game reads: the Game pages and the home icons show them, so they count (2026-09-16:
    # the banner said 8 off the pages, the Game icons 12; review 2026-10-05)
    from .game_systems import convar_changes, convar_start
    convars = (p.get('extras') or {}).get('convars') or []
    for c in player_facing(convar_changes(convars, convar_start())) if convars else ():
        yield None, c, GAME, 0


def _by_system(e: dict, once: set[tuple], group: str):
    """An '@shared' block on map objects: its rows once per Game system its entries are in (the first entry's copy:
    its own status, `shared_rows.spread`); the first system keeps the block as the row's entity (the archive's name
    of what it covers), another names its entry. `group`: the block's system by `_counted_as` — its rows go there
    when none of its entries but a template has a system (they were dropped then; review 2026-10-06)."""
    from .cards import player_facing
    from .game_systems import is_template, place_entity
    from .shared_rows import catalog, spread
    cat = catalog()
    first = None
    targets = spread(e)
    # a template among them (citadel_punchable_powerup_base) is its heirs' — the block's other targets carry the edit
    heirs = [x for x in targets if not is_template({**x, **cat.get(x['key'], {})})]
    placed = []
    for x in heirs or targets:
        hit = place_entity(x['key'], {**x, **cat.get(x['key'], {})})
        if hit:
            placed.append((f'game:{hit[0]}', x, player_facing(x['changes'])))
    for g, x, rows in placed or [(group, e, player_facing(e['changes']))]:
        first = first or g
        for c in rows:
            sig = (g, c.get('label'), c.get('old_s'), c.get('new_s'))
            if sig not in once:
                once.add(sig)
                yield (e if g == first else x), c, GAME, 0


def _icons(e: dict, pages: frozenset[str] | set[str]) -> int:
    """On how many home icons an entity's rows sit: one, or for an '@shared' block the pages of its targets (a unit
    family's members are one page, a hero's abilities the hero's) and the Game systems of the targets no page shows
    (one edit over 15 heroes' abilities and an ability no hero owns: 15 hero icons and Other rules & objects)."""
    if e.get('id') != '@shared':
        return 1
    from .game_systems import place_entity
    from .home_page import page_route
    from .shared_rows import catalog, spread
    cat = catalog()
    icons = set()
    for x in spread(e):
        info = {**x, **cat.get(x['key'], {})}
        where = page_route(x['key'], info, pages, unit_main())
        hit = None if where else place_entity(x['key'], info)
        if where or hit:
            icons.add(where[0] if where else f'game:{hit[0]}')
    return len(icons)


def count(p: dict, pages: frozenset[str] | set[str] | None = None) -> dict[str, int]:
    """{'changes': n, '<status>': n per status, 'not_in_notes': n, 'hidden_on_pages': n, 'hidden_archive': n,
    'hidden_shared': n} of one patch. `pages`: the keys the hero, item and unit pages show (`page_set`).
    `hidden_archive`: not in the notes and on no page but the patch archive's (no Game system lists it);
    `hidden_shared`: not in the notes and on several home icons (an edit shared by several heroes or units counts once
    here and on each of their icons — the home banner says how many, review 2026-10-06 #16)."""
    from .render import not_in_notes
    out: Counter = Counter()
    for _, c, place, icons in _placed_rows(p, pages):
        out['changes'] += 1
        out[c.get('status', 'hidden')] += 1
        hid = not_in_notes(c)
        out['not_in_notes'] += hid
        out['hidden_on_pages'] += bool(place == PAGE and hid)
        out['hidden_archive'] += bool(place == ARCHIVE and hid)
        out['hidden_shared'] += bool(icons > 1 and hid)
    return {'changes': 0, 'hidden': 0, 'not_in_notes': 0, 'hidden_on_pages': 0, 'hidden_archive': 0,
            'hidden_shared': 0, **out}


@lru_cache(maxsize=None)
def for_id(pid: str) -> dict[str, int]:
    """`count` of a patch by its id (read once per build: the patch pages, the list and the home page share it;
    the record from the build's shared archive, builders/archive.py)."""
    from . import archive
    return count(archive.patch(pid))


def off_pages(counts: dict[str, int]) -> int:
    """How many of the changes not in the notes the Game section shows (game rules, map objects): no hero, item or
    unit page does, and the patch archive is not the only place that lists them."""
    return counts.get('not_in_notes', 0) - counts.get('hidden_on_pages', 0) - counts.get('hidden_archive', 0)
