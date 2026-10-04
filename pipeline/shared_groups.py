"""A patch's '@shared' records: one edit copied into many entities (`pipeline/diff.py` SHARED_MIN) is ONE block
in the patch archive, not N.

Each block keeps the KEYS of the entities it hit (`target_keys`), not only their names: names are ambiguous
(renamed heroes, "Melee", raw ids), and with names only no hero, item or unit page could show the change —
13,573 hero × row pairs and 278 hero patch bands were on no hero page (coverage audit 2026-10-05: Haze's
Max Health 740 → 730 on 2026-05-22, the dash times of eleven heroes on 2026-07-28). The builders spread a
block over its targets (`builders/shared_rows.py`).

`scope` says whether the block covers (almost) every entity of its kind that was in the game files then
('all': the level curve, the investment bonuses, every item's slot cost) or some of them ('some': nine heroes'
Max Health). A target whose status differs from the block's (a note line named only that hero) is listed in
the change's `target_status`."""
from __future__ import annotations

ALL_SHARE = 0.85     # a block on at least this share of the live entities of its kinds is a rule for all of them
KIND_SHARE = 0.1     # … counting the kinds that hold at least this share of its targets
# the more noted status wins; among equals, a dev hero's 'unreleased' yields: a rule for all heroes is
# "unreleased" only if every hero it touches is (a dev hero listed first had made 41 "All heroes" rows
# unreleased, audit 2026-10-01)
STATUS_RANK = {'hidden': 0, 'unannounced': 0, 'unreleased': 0, 'described': 1, 'documented': 2}


def merged_status(cur: str, new: str) -> str:
    if STATUS_RANK[new] > STATUS_RANK[cur] or (cur == 'unreleased' and new != 'unreleased'
                                               and STATUS_RANK[new] == STATUS_RANK[cur]):
        return new
    return cur


class SharedGroups:
    """Collects a window's shared changes by signature (file, path, old, new), then makes the '@shared' entities."""

    def __init__(self) -> None:
        self._groups: dict[tuple, dict] = {}

    def __contains__(self, sig: tuple) -> bool:
        return sig in self._groups

    def add(self, sig: tuple, change: dict | None, name: str, key: str, status: str) -> None:
        """`change`: the first target's change JSON (made once per signature, None after); `key`: the target
        entity's key; `status`: that target's own status."""
        grp = self._groups.get(sig)
        if grp is None:
            if change is None:
                raise ValueError(f'the first target of {sig} brings the change')
            grp = self._groups[sig] = {'change': change, 'names': [], 'status': {}}
        grp['names'].append(name)
        grp['status'][key] = status
        grp['change']['status'] = merged_status(grp['change']['status'], status)

    def __bool__(self) -> bool:
        return bool(self._groups)

    def entities(self, cat: dict[str, dict], window: tuple[tuple, tuple] | None, labels: dict[str, str]) -> list[dict]:
        """The '@shared' entities: one per file and set of targets, its changes the blocks hitting exactly that
        set. `cat`: the entity catalog (kinds, first / last seen); `window`: its first and last build (who was
        in the files, `window_of`); `labels`: file -> the archive's name for a block ("All heroes")."""
        out: dict[tuple, dict] = {}
        used: set[str] = set()
        for (file, *_), grp in self._groups.items():
            keys = tuple(sorted(grp['status']))
            ent = out.get((file, keys))
            if ent is None:
                names = sorted(set(grp['names']))
                base = key = f"@shared:{file}:{len(names)}:{','.join(names[:3])}"
                n = 1
                while key in used:            # another set of targets under the same first names
                    n += 1
                    key = f'{base}#{n}'
                used.add(key)
                ent = out[(file, keys)] = {
                    'key': key, 'file': file, 'id': '@shared', 'kind': 'shared', 'owner': None,
                    'name': f"{labels.get(file, 'Many entries')} ({len(names)})", 'targets': names,
                    'target_keys': list(keys), 'scope': scope(file, keys, cat, window), 'changes': []}
            change = grp['change']
            odd = {k: s for k, s in grp['status'].items() if s != change['status']}
            if odd:
                change['target_status'] = odd
            ent['changes'].append(change)
        return list(out.values())


def _seen(e: dict, end: str) -> tuple:
    """(build, date) of an entity's first or last sighting; build None when the record has no number."""
    v = e.get(end) or [None, '']
    return (v[0] if isinstance(v[0], int) else None, str(v[1] or '')[:10])


def _before(a: tuple, b: tuple, strict: bool) -> bool:
    """a before b: by build number when both have one, else by date (a date has no order inside a day)."""
    if a[0] is not None and b[0] is not None:
        return a[0] < b[0] if strict else a[0] <= b[0]
    return a[1] <= b[1]


def live_keys(file: str, kinds: set[str], cat: dict[str, dict], window: tuple[tuple, tuple]) -> list[str]:
    """Entities of the file and kinds the window could diff field by field: in the files before its first build
    and still there at its last (an entity added or removed inside the window is an event, never a target),
    templates out. `window`: ((first build, date), (last build, date))."""
    start, end = window
    out = []
    for k, e in cat.items():
        if e.get('file') != file or e.get('kind') not in kinds or e.get('template'):
            continue
        if _before(_seen(e, 'first'), start, strict=True) and _before(end, _seen(e, 'last'), strict=False):
            out.append(k)
    return out


def scope(file: str, keys: tuple[str, ...], cat: dict[str, dict], window: tuple[tuple, tuple] | None) -> str:
    """'all' when the targets are ALL_SHARE or more of the entities of their kinds the window could diff. Only
    the kinds that hold KIND_SHARE of the targets count: one sub-ability among 256 items ("Shop Version",
    City Never Sleeps) put every sub-ability in the files under the measure."""
    kinds: dict[str, int] = {}
    for k in keys:
        if k in cat and not cat[k].get('template'):
            kinds[cat[k].get('kind')] = kinds.get(cat[k].get('kind'), 0) + 1
    main = {kd for kd, n in kinds.items() if n >= KIND_SHARE * sum(kinds.values())}
    if not main or not window:
        return 'some'
    live = live_keys(file, main, cat, window)
    hits = sum(1 for k in keys if k in cat and cat[k].get('kind') in main and not cat[k].get('template'))
    return 'all' if live and hits >= ALL_SHARE * len(live) else 'some'


def window_of(builds: list[dict]) -> tuple[tuple, tuple] | None:
    """((first build, date), (last build, date)) of a patch window's builds."""
    if not builds:
        return None
    builds = sorted(builds, key=lambda b: str(b.get('date') or ''))
    ends = []
    for b in (builds[0], builds[-1]):
        ends.append((b.get('build') if isinstance(b.get('build'), int) else None, str(b.get('date') or '')[:10]))
    return ends[0], ends[1]
