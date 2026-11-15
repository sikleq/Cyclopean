"""Every number of a Game system's entries as the newest build has them, for the files where the history alone falls
short.

The "Current values" panel of a Game system reads an entry's numbers from its history (builders/game_now.py), so a
field that never moved since the tracking began is not there: Ranked's Season 1 showed no "Wins to Play Ranked 60"
nor "Placement Matches 8" — copied from default_ranked when the file came, never changed (todo 2026-11-13, done
2026-11-15). For the files in `FILES` this writes every gameplay number of each entry at the tracker's head.

    python -m pipeline.now_entries   ->  data/tables/now_entries.json
"""
from __future__ import annotations

import json

from . import cache, loc, semantics, tracker
from .classify import category
from .field_labels import describe
from .flatten import flatten

OUT = tracker.ROOT / 'data' / 'tables' / 'now_entries.json'
FILES = ('ranked_seasons.vdata',)
GAMEPLAY = ('balance', 'mechanic')


def _number(v) -> float | list[float] | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, (list, tuple)) and v and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v):
        return list(v)
    return None


def entry_rows(eid: str, entry: dict, tok: dict[str, str]) -> list[list[str]]:
    """[[label, value]] of an entry's gameplay numbers in the file's order; switches, names and ids are left out."""
    rows = []
    for path, v in flatten(entry).items():
        n = _number(v)
        if n is None or category(path, None, v) not in GAMEPLAY:
            continue
        rows.append([describe(path, tok, eid)['label'], semantics.display_value(n, False)])
    return rows


def snapshot(commit: str) -> dict[str, list[list[str]]]:
    """entity key -> its rows (`entry_rows`) at `commit`; templates (`_not_pickable`) are no entries."""
    tok = loc.tokens(commit)
    out: dict[str, list[list[str]]] = {}
    for file in FILES:
        data = cache.vdata(commit, tracker.SCRIPTS + file) or {}
        for eid, e in data.items():
            if isinstance(e, dict) and not e.get('_not_pickable'):
                rows = entry_rows(eid, e, tok)
                if rows:
                    out[f'{file}:{eid}'] = rows
    if not out:
        raise RuntimeError(f'no entries with numbers in {FILES} at {commit[:8]}')
    return out


def build() -> dict:
    head = tracker.git('rev-parse', 'HEAD').strip()
    out = snapshot(head)
    tmp = OUT.with_suffix('.tmp')
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
    tmp.replace(OUT)
    print(f'{len(out)} entries -> {OUT}')
    return out


if __name__ == '__main__':
    build()
