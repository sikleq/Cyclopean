"""A new entity's patch row says what it came with, and the edits made to it later in the same window stay rows
(concept audit 2026-11-13).

The matcher folds an entity added in a patch window into ONE row, "Added to the game files" (path '@add'), and with it
the builds after its arrival inside the window (match.merge_ops): Spirit Snatch came in 5375 with Spirit Power Reduction
−30 and 5390 made it −26, yet its page said only "Added to the game files" — 1,433 such rows had no number, 77 later
edits (39 not in the notes) were on no page. The build records hold both, so the archive completes the patch record
when it is read (`archive.patch`), and every page, counter and matrix reads the same rows:

- `came_with` on the '@add' row: the key numbers of the build that added it ("Spirit Damage 50, Duration 16s"), the
  rule a new entity's card follows (cards.ADDED_KEY first, then its other numbers; game_now._ADDED_NOISE left out);
- a row per field a later build of the window moved (first old → last new), its builds those builds, its status the
  arrival's when that is work before release or an update with no notes, else hidden: the notes announce the new
  thing, never its tuning before release."""
from __future__ import annotations

from functools import lru_cache

from .common import load_json

CAME_WITH_MAX = 8          # numbers the arrival row prints
# only a new entity: one back in the files is diffed against its last version over the whole window already
ARRIVAL_PATHS = ('@add',)
KEEP_STATUS = ('unreleased', 'unannounced')


@lru_cache(maxsize=64)
def _record(file: str) -> dict | None:
    try:
        return load_json(f'builds/{file}')
    except (OSError, ValueError):
        return None


def _rows_of(file: str, key: str) -> list[dict] | None:
    """The record's rows of entity `key` ('file:id'), None when the record or the entity is not there."""
    rec = _record(file)
    if rec is None:
        return None
    f, _, eid = key.partition(':')
    for e in rec.get('entities') or ():
        if e.get('file') == f and e.get('id') == eid:
            return e.get('changes') or []
    return None


def came_with(rows: list[dict]) -> str:
    """'Spirit Damage 50, Duration 16s, …' — the numbers a new entity's record row set gives it: the key fields first
    (cards.ADDED_KEY: an item's or ability's values, a hero's base stats, a unit's health), then its other balance
    numbers, its own before the blocks it nests."""
    from .brawl import is_gameplay
    from .cards import ADDED_KEY
    from .game_now import _ADDED_NOISE
    nums = [c for c in rows if c.get('op') == 'add' and is_gameplay(c) and c.get('cat') == 'balance'
            and any(ch.isdigit() for ch in str(c.get('new_s') or ''))
            and not str(c.get('new_s')).startswith(('-1', '−1')) and not _ADDED_NOISE.search(str(c.get('label') or ''))]
    nums.sort(key=lambda c: (not ADDED_KEY.search(str(c.get('path') or '')), '{' in str(c.get('path') or '')))
    seen, out = set(), []
    for c in nums:
        label = str(c.get('label') or '')
        if label in seen:
            continue
        seen.add(label)
        out.append(f'{label} {c.get("new_s")}')
        if len(out) == CAME_WITH_MAX:
            break
    return ', '.join(out)


def _num(v) -> float | None:
    try:
        return float(str(v).replace('−', '-').rstrip('%sm/'))
    except (TypeError, ValueError):
        return None


def later_rows(key: str, after: int, builds: list[dict], status: str, known: set[str]) -> list[dict]:
    """The rows of the fields entity `key` moved in the window's builds after `after` (its arrival): first old → last
    new per path, a field moved back where it was is none; `known`: paths the patch already has for it."""
    from .brawl import gameplay_rows
    moves: dict[str, list[tuple[int, dict]]] = {}
    for b in builds:
        if b.get('build') is None or b['build'] <= after:
            continue
        rows = _rows_of(b['file'], key)
        for c in gameplay_rows(rows or []):
            path = str(c.get('path') or '')
            if path and not path.startswith('@') and path not in known:
                moves.setdefault(path, []).append((b['build'], c))
    out = []
    for path, got in moves.items():
        first, last = got[0][1], got[-1][1]
        old_s = None if first.get('op') == 'add' else first.get('old_s')
        new_s = None if last.get('op') == 'remove' else last.get('new_s')
        if old_s is None and new_s is None or str(old_s) == str(new_s):
            continue
        op = 'add' if old_s is None else 'remove' if new_s is None else 'change'
        row = {**last, 'key': f'{key}:{path}', 'op': op, 'old': None if op == 'add' else first.get('old'),
               'old_s': '—' if old_s is None else old_s, 'new_s': '—' if new_s is None else new_s,
               'builds': [b for b, _ in got], 'status': status if status in KEEP_STATUS else 'hidden', 'late_add': True}
        if len(got) > 1 and op == 'change':
            a, b = _num(old_s), _num(new_s)
            row['pct'] = round((b - a) / abs(a) * 100, 1) if a and b is not None else None
        out.append(row)
    return out


def complete(p: dict) -> dict:
    """The patch record with its arrivals completed (`came_with`, `later_rows`); the same object when it has none.
    Never writes into `p` (the archive is shared): changed entities are copies."""
    builds = sorted((b for b in p.get('builds') or () if b.get('file')), key=lambda b: b.get('build') or 0)
    if not builds:
        return p
    out, changed = [], False
    for e in p.get('entities') or ():
        arrival = next((c for c in e.get('changes') or () if c.get('path') in ARRIVAL_PATHS), None)
        if arrival is None or e.get('id') == '@shared':
            out.append(e)
            continue
        key = f"{e['file']}:{e['id']}"
        at = min(arrival.get('builds') or [builds[0]['build']])
        file_at = next((b['file'] for b in builds if b.get('build') == at), None)
        rows = list(e['changes'])
        text = came_with(_rows_of(file_at, key) or []) if file_at else ''
        if text:
            rows[rows.index(arrival)] = {**arrival, 'came_with': text}
        known = {str(c.get('path')) for c in e['changes']}
        rows += later_rows(key, at, builds, str(arrival.get('status') or ''), known)
        if text or len(rows) != len(e['changes']):
            changed = True
            out.append({**e, 'changes': rows})
        else:
            out.append(e)
    return {**p, 'entities': out} if changed else p
