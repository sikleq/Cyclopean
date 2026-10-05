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
    from .entities_pages import GAMEPLAY, page_entities, page_keys
    from .shared_rows import entities as spread_all, is_every
    ents = {f"{e['file']}:{e['id']}": e for e in load_json('entities.json')['entities']}
    mine: set[str] = set()          # entities_pages.changed over its _history
    for row in load_json('patches/index.json'):
        for e in spread_all(load_json(f'patches/{row["id"]}.json.gz')['entities']):
            if any(c['cat'] in GAMEPLAY and not is_every(c) for c in e['changes']):
                mine.add(e['key'])
    trow = {r['id']: r for r in load_json('tables/heroes.json')['heroes']}
    heroes, items, units = page_entities(ents, mine, trow)
    return frozenset(page_keys(ents, heroes, items, units))


def count(p: dict, pages: frozenset[str] | set[str] | None = None) -> dict[str, int]:
    """{'changes': n, '<status>': n per status, 'not_in_notes': n, 'hidden_on_pages': n} of one patch. `pages`: the
    keys the hero, item and unit pages show (`page_set`)."""
    from .cards import gameplay_entities, player_facing
    from .render import not_in_notes
    from .shared_rows import spread
    if pages is None:
        pages = page_set()
    out: Counter = Counter()
    for e in gameplay_entities(p['entities']):
        rows = player_facing(e['changes'])
        if not rows:
            continue
        on_page = any(x['key'] in pages for x in spread(e))
        for c in rows:
            out['changes'] += 1
            out[c.get('status', 'hidden')] += 1
            out['not_in_notes'] += not_in_notes(c)
            out['hidden_on_pages'] += bool(on_page and not_in_notes(c))
    return {'changes': 0, 'hidden': 0, 'not_in_notes': 0, 'hidden_on_pages': 0, **out}


@lru_cache(maxsize=None)
def for_id(pid: str) -> dict[str, int]:
    """`count` of a patch by its id (read once per build: the patch pages, the list and the home page share it)."""
    return count(load_json(f'patches/{pid}.json.gz'))


def off_pages(counts: dict[str, int]) -> int:
    """How many of the changes not in the notes no hero, item or unit page shows (game rules, map objects)."""
    return counts.get('not_in_notes', 0) - counts.get('hidden_on_pages', 0)
