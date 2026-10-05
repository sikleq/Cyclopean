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
    from .game_systems import is_template
    from .shared_rows import catalog, entities as spread_all
    if pages is None:
        pages = page_set()
    cat = catalog()
    heirs = {(x['file'], c.get('path'), str(c.get('old_s')), str(c.get('new_s')))
             for x in spread_all(ents) if not is_template(x) for c in x['changes']
             if not str(c.get('path') or '').startswith('@')}
    out = []
    for e in ents:
        if (e.get('id') != '@shared' and e.get('key') not in pages
                and is_template({**e, **cat.get(e.get('key'), {})})):
            kept = [c for c in e['changes']
                    if (e['file'], c.get('path'), str(c.get('old_s')), str(c.get('new_s'))) not in heirs]
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
    from .cards import gameplay_entities, player_facing
    from .game_systems import place_all_row
    from .shared_rows import spread
    if pages is None:
        pages = page_set()
    out: list[tuple[dict | None, dict, bool]] = []
    once: set[tuple] = set()
    for e in drop_inherited(gameplay_entities(p['entities']), pages):
        rows = player_facing(e['changes'])
        if not rows:
            continue
        group, on_page = _counted_as(e, pages)
        on_page = on_page and any(x['key'] in pages for x in spread(e))
        for c in rows:
            if group is not None:
                # one edit over a unit family's members or a Game system's entries counts once, as their pages, the
                # change matrices and the home icons count it (Walker's four ids, twelve breakable props)
                g = f'game:{place_all_row(e["file"], c)[0]}' if group == ALL_ROWS else group
                sig = (g, c.get('label'), c.get('old_s'), c.get('new_s'))
                if sig in once:
                    continue
                once.add(sig)
            out.append((e, c, on_page))
    # the console variables a game reads: the Game pages and the home icons show them, so they count (2026-09-16:
    # the banner said 8 off the pages, the Game icons 12; review 2026-10-05)
    from .game_systems import convar_changes, convar_start
    convars = (p.get('extras') or {}).get('convars') or []
    for c in player_facing(convar_changes(convars, convar_start())) if convars else ():
        out.append((None, c, False))
    return out


def count(p: dict, pages: frozenset[str] | set[str] | None = None) -> dict[str, int]:
    """{'changes': n, '<status>': n per status, 'not_in_notes': n, 'hidden_on_pages': n} of one patch. `pages`: the
    keys the hero, item and unit pages show (`page_set`)."""
    from .render import not_in_notes
    out: Counter = Counter()
    for _, c, on_page in counted_rows(p, pages):
        out['changes'] += 1
        out[c.get('status', 'hidden')] += 1
        out['not_in_notes'] += not_in_notes(c)
        out['hidden_on_pages'] += bool(on_page and not_in_notes(c))
    return {'changes': 0, 'hidden': 0, 'not_in_notes': 0, 'hidden_on_pages': 0, **out}


@lru_cache(maxsize=None)
def for_id(pid: str) -> dict[str, int]:
    """`count` of a patch by its id (read once per build: the patch pages, the list and the home page share it;
    the record from the build's shared archive, builders/archive.py)."""
    from . import archive
    return count(archive.patch(pid))


def off_pages(counts: dict[str, int]) -> int:
    """How many of the changes not in the notes no hero, item or unit page shows (game rules, map objects)."""
    return counts.get('not_in_notes', 0) - counts.get('hidden_on_pages', 0)
