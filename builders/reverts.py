"""A row that puts a field back: "reverts 2026-06-30" (idea from deadlog.io, owner 2026-11-01). Exact, from the files: the
field's previous move in the archive went old → new, this one goes new → old, in another update. A note's wording plays
no part. 645 of the archive's 11,571 moves are one."""
from __future__ import annotations

from collections import defaultdict
from functools import lru_cache

from . import archive

CATS = ('balance', 'mechanic')


def _row_id(c: dict) -> tuple:
    return c.get('key'), str(c.get('old_s')), str(c.get('new_s')), tuple(c.get('builds') or ())


def reverted(moves: list[tuple[str, dict]]) -> dict[tuple, str]:
    """{row id: date of the move it undoes} of [(update date, row)] in date order."""
    last: dict[str, tuple[str, dict]] = {}
    out = {}
    for date, c in moves:
        prev = last.get(c['key'])
        if prev and prev[0] != date and str(prev[1].get('old_s')) == str(c.get('new_s')) \
                and str(prev[1].get('new_s')) == str(c.get('old_s')):
            out[_row_id(c)] = prev[0]
        last[c['key']] = (date, c)
    return out


@lru_cache(maxsize=1)
def _index() -> dict[tuple, str]:
    moves = defaultdict(list)
    for row in archive.index():
        for e in archive.patch(row['id']).get('entities') or ():
            moves[row['date'][:10]] += [c for c in e['changes']
                                        if c.get('op') == 'change' and c.get('cat') in CATS and c.get('key')]
    return reverted([(d, c) for d in sorted(moves) for c in moves[d]])


def revert_date(c: dict) -> str | None:
    return _index().get(_row_id(c)) if c.get('op') == 'change' else None
