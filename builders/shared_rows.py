"""'@shared' blocks on the pages of the entities they changed (coverage audit 2026-10-05; owner: "I want to see ALL
changes to everything in the game").

A patch keeps one edit copied into many entities as ONE block with the keys of the entities it hit
(`pipeline/shared_groups.py`: `target_keys`, `scope`, per-target `target_status`). Every hero / item / unit view
spreads it back over those entities here — the entity pages' history, the ability cards' trail squares, the change
matrices, the home feed — so Haze's band of 2026-05-22 has its Max Health 740 → 730 and Abrams' band of 2026-07-28
its Ground Dash Duration 0.7s → 0.72s. They were on no hero page: the blocks kept only the targets' names.

A block on some of them (`scope` 'some': nine heroes' Max Health) is an ordinary row of each, with a chip "shared
×9 heroes". A block on (almost) every entity of its kinds ('all': the level curve, the investment bonuses, every
melee attack, every item's slot cost) is a rule for all: on each hero or item it is ONE link row per Game system
"All heroes: N changes · Hero progression ›" (cards.every_rows; its rows are on the Game page) and is counted apart
from the entity's own changes (`is_every`), so 35 level-curve rows do not drown the hero's own patch nor fill every
hero's cell of the change matrix. Units never fold (`FOLD_FILES`)."""
from __future__ import annotations

import re
from collections import Counter
from functools import lru_cache

from .common import load_json

# what a target is, by its catalog kind (the chip "shared ×9 heroes", the fold "All melee attacks: 5 changes")
KIND_NOUN = {'hero': 'heroes', 'item': 'items', 'melee': 'melee attacks', 'weapon': 'guns', 'ability': 'abilities',
             'ability_other': 'abilities', 'shared': 'abilities', 'neutral': 'neutrals', 'trooper': 'troopers',
             'building': 'buildings', 'unit': 'units', 'helper': 'units', 'modifier': 'modifiers',
             'global': 'map objects'}
FILE_NOUN = {'heroes.vdata': 'heroes', 'abilities.vdata': 'abilities', 'npc_units.vdata': 'units',
             'misc.vdata': 'map objects', 'modifiers.vdata': 'modifiers'}
# where a rule for all folds: the heroes' file (level curve, investment and purchase bonuses) and the abilities'
# (every melee attack, every gun, every item's slot cost). Not the units': a kind of unit is a handful of ids — a
# block on the five troopers IS how the troopers changed (44 rows on 2026-04-30), shown and counted as theirs
FOLD_FILES = ('heroes.vdata', 'abilities.vdata')


@lru_cache(maxsize=1)
def catalog() -> dict[str, dict]:
    """entity key -> its catalog row (kind, owner, name, template)."""
    return {f"{e['file']}:{e['id']}": e for e in load_json('entities.json')['entities']}


def noun(file: str, keys: list[str], cat: dict[str, dict]) -> str:
    """What the targets are: 'heroes', 'items', 'melee attacks', 'abilities & items', 'neutrals'… — by the kinds
    that hold KIND_SHARE of them (one sub-ability among 276 items is still "All items")."""
    from pipeline.shared_groups import KIND_SHARE
    kinds = Counter(cat[k].get('kind') for k in keys if k in cat and not cat[k].get('template'))
    nouns = {KIND_NOUN.get(kd, '') for kd, n in kinds.items() if n >= KIND_SHARE * sum(kinds.values())} - {''}
    if len(nouns) == 1:
        return nouns.pop()
    if file == 'abilities.vdata' and 'items' in nouns:
        return 'abilities & items'
    return FILE_NOUN.get(file, 'entries')


def block_name(e: dict, cat: dict[str, dict] | None = None) -> str:
    """The patch archive's name of an '@shared' block: "All heroes (61)" for a rule for all of a kind, "10 heroes"
    for some — every block read "All heroes (N)", nine heroes' Max Health too (coverage audit 2026-10-05)."""
    cat = catalog() if cat is None else cat
    real = [k for k in e.get('target_keys') or [] if k in cat and not cat[k].get('template')]
    if not real:
        return str(e.get('name') or 'Many entries')
    what = noun(e['file'], real, cat)
    return f'All {what} ({len(real)})' if e.get('scope') == 'all' else f'{len(real)} {what}'


def is_every(c: dict) -> bool:
    """A row of a rule for (almost) every entity of its kinds: folded and counted apart on an entity's views."""
    return bool(c.get('shared_all'))


SIDELESS = ('trooper', 'building', 'neutral', 'unit', 'global', 'helper')     # pipeline.semantics.SHARED_KINDS
_NUM = re.compile(r'^\s*([-+]?(?:\d+\.?\d*|\.\d+))')


def _unit_direction(c: dict) -> dict:
    """{dir, pct, grad} of a row judged for a unit (semantics.direction with the 'unit' side), from its shown values;
    {} when they are not numbers."""
    from pipeline import semantics
    a, b = (_NUM.match(str(c.get(f) or '')) for f in ('old_s', 'new_s'))
    if not a or not b:
        return {}
    dirn, pct = semantics.direction(str(c.get('path') or ''), float(a.group(1)), float(b.group(1)), 'unit')
    return {'dir': dirn, 'pct': None if pct is None else round(pct, 1), 'grad': semantics.gradient(pct)}


def spread(e: dict, cat: dict[str, dict] | None = None) -> list[dict]:
    """A patch entity as the entities its rows belong to: [e] itself, or for an '@shared' block one entity per
    target (kind / owner / name from the catalog; templates such as hero_base have no page and are left out), its
    rows that target's — the target's key and status, `shared_n` / `shared_what` / `shared_all` set. A block written
    before `target_keys` existed spreads nowhere (it stays in the patch archive only, as before)."""
    if e.get('id') != '@shared':
        return [e]
    keys = e.get('target_keys') or []
    if not keys:
        return []
    cat = catalog() if cat is None else cat
    real = [k for k in keys if k in cat and not cat[k].get('template')]
    every = e.get('scope') == 'all' and e['file'] in FOLD_FILES
    what = noun(e['file'], real, cat)
    out = []
    for k in real:
        ce = cat[k]
        file, _, eid = k.partition(':')
        # a unit's copy reads which way the number went (UP / DOWN), as its own rows do: one block over a hero's
        # ability and the Medic trooper's heal judged them both BUFF / NERF (review 2026-10-05)
        unit_side = ce.get('kind') in SIDELESS or bool(ce.get('units'))
        rows = []
        for c in e['changes']:
            row = {f: v for f, v in c.items() if f != 'target_status'}
            row.update(key=f'{k}:{c.get("path")}', id=eid, file=file,
                       status=(c.get('target_status') or {}).get(k, c.get('status')),
                       shared_n=len(real), shared_what=what, shared_all=every)
            if unit_side and row.get('dir') in ('buff', 'nerf'):
                row.update(_unit_direction(row))
            rows.append(row)
        out.append({'key': k, 'file': file, 'id': eid, 'kind': ce.get('kind'), 'owner': ce.get('owner'),
                    'name': ce.get('name') or eid, 'changes': rows})
    return out


def entities(ents: list[dict], cat: dict[str, dict] | None = None) -> list[dict]:
    """A patch's entities with every '@shared' block spread over its targets (`spread`)."""
    return [x for e in ents for x in spread(e, cat)]


def own(changes: list[dict]) -> list[dict]:
    """The rows that are the entity's own or shared with some others — not a rule for all (`is_every`)."""
    return [c for c in changes if not is_every(c)]
