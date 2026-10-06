"""The eye in a value's history (review 2026-10-06, #44): Hero / Unit / Item Stats, a hero page's stat tiles and the
Game rules table show a value's steps on hover (scripts.js `hist-tip`); a step the patch notes left out carries a
sixth element 1 and the tip draws the eye on it, as the entity pages' rows do.

A step is [build, date, old, new, direction?]. The build's patch window holds what the files changed in it, each
change with its status and the builds that moved it (`builds`). The step's own row is the field the column reads
(its `path`), else the row of that build that moved the same numbers (an item's provided stat, Item Stats has no
paths): the eye when it is not in the notes; a column with a field but no row of its own gets none. A computed column
(DPS, reload) has no such row: the eye only when every counted row of its entities in that build was left out — a DPS
step a documented bullet-damage change explains keeps none (never an eye too many).
A console variable's step is its own record of that build (`extras.convars`: name, build, status)."""
from __future__ import annotations

import re
from functools import lru_cache

from . import archive

HIDDEN = 1                  # the step's sixth element


@lru_cache(maxsize=1)
def _rows_by_build() -> dict[tuple[str, int], tuple[dict, ...]]:
    """(entity key, build) -> the gameplay rows that build moved, over every patch (one edit over many entities
    spread to each: shared_rows), engine plumbing and no-ops left out as every counter leaves them."""
    from .cards import GAMEPLAY, is_engine, is_noop
    from .shared_rows import entities as spread_all
    out: dict[tuple[str, int], list[dict]] = {}
    for r in archive.index():
        for e in spread_all(archive.patch(r['id'])['entities']):
            for c in e['changes']:
                if c.get('cat') not in GAMEPLAY or is_engine(c) or is_noop(c):
                    continue
                for b in c.get('builds') or ():
                    out.setdefault((e['key'], b), []).append(c)
    return {k: tuple(v) for k, v in out.items()}


@lru_cache(maxsize=1)
def _convars_by_build() -> dict[tuple[str, int], str]:
    """(console variable, build) -> the status of its change there."""
    out: dict[tuple[str, int], str] = {}
    for r in archive.index():
        for cv in (archive.patch(r['id']).get('extras') or {}).get('convars') or ():
            if cv.get('build') is not None and cv.get('name'):
                out[(cv['name'], cv['build'])] = cv.get('status') or ''
    return out


def _leaf(path: str) -> str:
    return str(path or '').rsplit('.', 1)[-1]


_NUM = re.compile(r'^\s*([-+−]?(?:\d+\.?\d*|\.\d+))')


def _num(s) -> float | None:
    m = _NUM.match(str(s if s is not None else ''))
    return float(m.group(1).replace('−', '-')) if m else None


def _same(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= 1e-3 + 1e-3 * abs(a)


def _moves(c: dict, old, new) -> bool:
    """The row moved the value as the step did: its printed numbers are the step's (an added / removed row has only
    the side it holds)."""
    o = None if c.get('op') == 'add' else _num(c.get('old_s'))
    n = None if c.get('op') == 'remove' else _num(c.get('new_s'))
    if o is None and n is None:
        return False
    num = lambda v: v if isinstance(v, (int, float)) and not isinstance(v, bool) else None   # noqa: E731
    return _same(o, num(old)) and _same(n, num(new))


def step_hidden(keys: tuple[str, ...] | list[str], build, path: str | None = None, old=None, new=None) -> bool:
    """Was the step of `build` (old → new) over these entities left out of the notes? `path`: the field the column
    reads. The step's own row is the field's, else the one that moved the same numbers. Without one, a column with a
    field gets no eye (the build's other rows say nothing about it: 63 Hero Stats steps at a hero's release took one
    from unrelated rows, review 2026-10-06); a computed column (no field) gets the eye only when nothing the entities
    changed in that build was in the notes."""
    from .render import not_in_notes
    if not isinstance(build, int):
        return False
    idx = _rows_by_build()
    rows = [c for k in keys for c in idx.get((k, build), ())]
    if not rows:
        return False
    mine = [c for c in rows if _leaf(c.get('path')) == _leaf(path)] if path else []
    mine = mine or [c for c in rows if _moves(c, old, new)]
    if mine:
        return any(not_in_notes(c) for c in mine)
    return not path and all(not_in_notes(c) for c in rows)


def _marked(steps: list, hidden) -> list:
    """The steps with the hidden ones' sixth element set (a step without a direction gets null in the fifth)."""
    out = []
    for h in steps:
        if hidden(h):
            out.append([*h[:4], h[4] if len(h) > 4 else None, HIDDEN])
        else:
            out.append(h)
    return out


def mark_row(row: dict, keys: list[str], paths: dict[str, str] | None = None) -> dict:
    """A stats row (`history`: column -> steps) with its hidden steps marked; `keys`: the entities its values come
    from (a hero and its gun), `paths`: column -> the field it reads."""
    paths = paths or {}
    keys = tuple(k for k in keys if k)
    hist = {col: _marked(steps or [], lambda h, col=col: step_hidden(keys, h[0], paths.get(col), h[2], h[3]))
            for col, steps in (row.get('history') or {}).items()}
    return {**row, 'history': hist}


def mark_convar(name: str, steps: list) -> list:
    """A console variable's steps with the ones its patch's notes left out marked."""
    from .render import NOT_IN_NOTES
    idx = _convars_by_build()
    return _marked(steps, lambda h: idx.get((name, h[0])) in NOT_IN_NOTES)
