"""Entity-level diff between two parsed vdata files."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from .classify import category
from .flatten import flatten, fmt

SKIP_TOP = {'generic_data_type', '_include'}


@dataclass
class FieldChange:
    path: str
    op: str           # add | remove | change
    old: object
    new: object
    cat: str          # balance | mechanic | ui | visual | audio

    def to_json(self) -> dict:
        d = asdict(self)
        if self.cat in VALUELESS_CATS:
            # cosmetic/UI values are resource paths and layout blobs: keep only the fact
            d.pop('old')
            d.pop('new')
        else:
            d['old'] = _jsonable(self.old)
            d['new'] = _jsonable(self.new)
        targets = getattr(self, 'targets', None)
        if targets:
            d['targets'] = targets
        return d


@dataclass
class EntityChange:
    file: str
    id: str
    status: str       # added | removed | changed
    changes: list[FieldChange]

    def to_json(self) -> dict:
        return {
            'file': self.file,
            'id': self.id,
            'status': self.status,
            'changes': [c.to_json() for c in self.changes],
        }


def _jsonable(v):
    if v is None or isinstance(v, (bool, str)):
        return v
    if isinstance(v, float):
        unit = getattr(v, 'unit', '')
        num = int(v) if v.is_integer() else round(v, 6)
        return f'{fmt(v)}' if unit else num
    if isinstance(v, tuple):
        return [_jsonable(x) for x in v]
    return v


def _eq(a, b) -> bool:
    if isinstance(a, float) and isinstance(b, float):
        return abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))
    return a == b


def diff_entity(a: dict, b: dict) -> list[FieldChange]:
    fa, fb = flatten(a), flatten(b)
    out = []
    for path in fa.keys() | fb.keys():
        if path in fa and path in fb:
            if not _eq(fa[path], fb[path]):
                out.append(FieldChange(path, 'change', fa[path], fb[path], category(path, fa[path], fb[path])))
        elif path in fb:
            out.append(FieldChange(path, 'add', None, fb[path], category(path, None, fb[path])))
        else:
            out.append(FieldChange(path, 'remove', fa[path], None, category(path, fa[path], None)))
    out.sort(key=lambda c: c.path)
    return out


SHARED_MIN = 6            # identical change in >= this many entities -> shared record
VALUELESS_CATS = {'visual', 'audio', 'ui'}


def collapse_shared(changes: list[EntityChange]) -> list[EntityChange]:
    """Move changes that repeat verbatim across many entities into one record.

    Compiled vdata copies template fields into every hero/ability, so one edit
    to hero_base shows up 60 times. Such changes become a single '@shared'
    entity whose FieldChanges carry `targets` (the affected entity ids).
    """
    sig_targets: dict[tuple, list[str]] = {}
    sig_change: dict[tuple, FieldChange] = {}
    for ec in changes:
        if ec.status != 'changed':
            continue
        for c in ec.changes:
            sig = (c.path, c.op, repr(c.old), repr(c.new))
            sig_targets.setdefault(sig, []).append(ec.id)
            sig_change.setdefault(sig, c)
    shared = {sig for sig, ids in sig_targets.items() if len(ids) >= SHARED_MIN}
    if not shared:
        return changes
    result = []
    for ec in changes:
        if ec.status == 'changed':
            kept = [c for c in ec.changes if (c.path, c.op, repr(c.old), repr(c.new)) not in shared]
            if not kept:
                continue
            ec = EntityChange(ec.file, ec.id, ec.status, kept)
        result.append(ec)
    shared_changes = []
    for sig in sorted(shared):
        c = sig_change[sig]
        fc = FieldChange(c.path, c.op, c.old, c.new, c.cat)
        fc.targets = sorted(sig_targets[sig])   # type: ignore[attr-defined]
        shared_changes.append(fc)
    file = changes[0].file if changes else ''
    result.append(EntityChange(file, '@shared', 'shared', shared_changes))
    return result


def diff_file(name: str, old: dict, new: dict) -> list[EntityChange]:
    old = old or {}
    new = new or {}
    result = []
    for eid in sorted((old.keys() | new.keys()) - SKIP_TOP):
        a, b = old.get(eid), new.get(eid)
        if a is None:
            result.append(EntityChange(name, eid, 'added', diff_entity({}, b if isinstance(b, dict) else {'value': b})))
        elif b is None:
            result.append(EntityChange(name, eid, 'removed', []))
        else:
            if not isinstance(a, dict):
                a = {'value': a}
            if not isinstance(b, dict):
                b = {'value': b}
            ch = diff_entity(a, b)
            if ch:
                result.append(EntityChange(name, eid, 'changed', ch))
    return collapse_shared(result)
