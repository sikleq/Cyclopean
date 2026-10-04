"""ONE count per patch of its changes and of those not in its patch notes, for every place that shows one: the home
feed's update banners and the home totals, the patch page's check line, its "All changes" tab and its "Not in patch
notes" filter, the patch list (coverage audit 2026-10-05: City Never Sleeps read 1232 on its page and in the list —
the matcher's raw field counts —, 620 under "Only hidden" and 212 on the home page — rows on hero / item / unit pages
only).

Counted is what the patch archive's "All changes" lists, the whole update: its gameplay rows as a player reads them
(`cards.gameplay_entities` → `cards.player_facing`: plumbing out, renamed fields merged, variants of one object
merged), an edit shared by many entities once. "Not in patch notes" is `render.NOT_IN_NOTES` (status hidden), the
same rule an entity page's bands, strip tiles and eye filter use; work on heroes still in development (unreleased)
and an update with no notes at all (unannounced) are counted apart. `hidden_on_pages`: those of the hidden ones a
hero, item or unit page shows (`home_page.page_of`; a shared edit when one of its targets has a page) — the rest are
game rules and map objects only the archive lists."""
from __future__ import annotations

from collections import Counter
from functools import lru_cache

from .common import load_json


@lru_cache(maxsize=1)
def _pages() -> tuple[frozenset[str], dict[str, str]]:
    """(template keys, unit id -> its family's page id): what `home_page.page_of` needs."""
    from .unit_families import families
    ents = load_json('entities.json')['entities']
    templates = frozenset(f"{e['file']}:{e['id']}" for e in ents if e.get('template'))
    fams = families([e for e in ents if e['file'] == 'npc_units.vdata' and not e.get('template')])
    return templates, {m['id']: ms[0]['id'] for ms in fams.values() for m in ms}


def count(p: dict, templates: frozenset[str] | None = None, unit_main: dict[str, str] | None = None
          ) -> dict[str, int]:
    """{'changes': n, '<status>': n per status, 'hidden_on_pages': n} of one patch."""
    from .cards import gameplay_entities, player_facing
    from .home_page import page_of
    from .render import not_in_notes
    from .shared_rows import spread
    if templates is None or unit_main is None:
        templates, unit_main = _pages()
    out: Counter = Counter()
    for e in gameplay_entities(p['entities']):
        rows = player_facing(e['changes'])
        if not rows:
            continue
        on_page = any(page_of(x, templates, unit_main) for x in spread(e))
        for c in rows:
            out['changes'] += 1
            out[c.get('status', 'hidden')] += 1
            out['hidden_on_pages'] += bool(on_page and not_in_notes(c))
    return {'changes': 0, 'hidden': 0, 'hidden_on_pages': 0, **out}


@lru_cache(maxsize=None)
def for_id(pid: str) -> dict[str, int]:
    """`count` of a patch by its id (read once per build: the patch pages, the list and the home page share it)."""
    return count(load_json(f'patches/{pid}.json.gz'))


def off_pages(counts: dict[str, int]) -> int:
    """How many of the changes not in the notes no hero, item or unit page shows (game rules, map objects)."""
    return counts.get('hidden', 0) - counts.get('hidden_on_pages', 0)
