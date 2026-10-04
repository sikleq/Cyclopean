"""One label, one unit and one sign per field across its whole history.

enrich labels every build record with the localization OF THAT BUILD, and the matcher every patch
with the patch's: one field showed under two or three names ("Regen Incoming Damage Percent" →
"Damage regenerated" → "Damage Regenerated") or switched between a bare number and a unit
("20 → 18" next to "17% → 16%") on 244 fields of 135 entities (audit 2026-10-04). The page shows
each field the way the game names it NOW:

  label — the newest build's label from the game's text; a field the newest text no longer labels
          keeps the last label Valve ever gave it; never the field's name split into words
          (`semantics.humanize`) while a real label was known. Same rule as entity names.
  unit  — the newest non-empty unit (a field that gained "%" shows it in its old rows too).
  sign  — the newest tooltip prefix: "-" makes an enemy slow read "Movement Slow 30%"
          (`semantics.enemy_label`) instead of the hero's own "Move Speed 30%".

Build records keep each build's own words (`label`, `label_src`, `unit`, `sign`): this module
reads them, the newest build's localization, and returns the map the matcher writes patches with
(data/patches carry the canonical label and values re-rendered from the raw ones) and the ability
cards use (`pipeline.abilities`), so a card and the newest history row agree.
"""
from __future__ import annotations

import subprocess
from functools import lru_cache

from . import jsonio, loc, semantics, tracker

BUILDS = tracker.ROOT / 'data' / 'builds'


def field_key(file: str, eid: str, path: str) -> str:
    return f'{file}:{eid}:{path}'


def collect(records) -> dict[str, dict]:
    """What the build records say of each field, oldest first so the newest wins: the newest label,
    the newest label from the game's text, the newest non-empty unit, the newest sign, and what
    describe() needs to label it again (the entity's kind, the property's loc token, its scale stat)."""
    seen: dict[str, dict] = {}
    for rec in records:
        for e in rec.get('entities', ()):
            for c in e.get('changes', ()):
                path = c.get('path')
                if not path or 'label' not in c:
                    continue
                ids = [e['id']] + [t for t in (c.get('targets') or ()) if t != e['id']]
                for eid in ids:
                    s = seen.setdefault(field_key(e['file'], eid, path), {})
                    s['label'] = c['label']
                    s['kind'] = e.get('kind') or ''
                    s['token'] = c.get('loc_token')
                    s['scaled_by'] = c.get('scaled_by')
                    if c.get('label_src') != 'fallback':
                        s['loc_label'] = c['label']
                    if c.get('unit'):
                        s['unit'] = c['unit']
                    if 'sign' in c:
                        s['sign'] = c['sign']
    return seen


def resolve(path: str, head: dict, seen: dict | None) -> dict:
    """{label, unit, sign, src} of one field from its newest-build description (`head`, describe()
    with the newest localization) and what the records said (`seen`, from collect())."""
    seen = seen or {}
    if head.get('src') != 'fallback':
        label, src = head['label'], head.get('src', 'curated')
    elif seen.get('loc_label'):
        label, src = seen['loc_label'], 'loc'
    else:
        label, src = head['label'], 'fallback'
    unit = head.get('unit') or seen.get('unit') or ''
    sign = head['sign'] if head.get('sign') is not None else seen.get('sign') or ''
    if sign == '-' and src == 'loc':
        label = semantics.enemy_label(label, semantics.property_name(path))
    return {'label': label, 'unit': unit, 'sign': sign, 'src': src}


def build(records, tok: dict[str, str], kinds: dict[str, str] | None = None) -> dict[str, dict]:
    """field key -> {label, unit, sign, src} for every field the records ever changed. `kinds`:
    entity key -> kind (the catalog's), else the newest record's."""
    out = {}
    for key, s in collect(records).items():
        file, eid, path = key.split(':', 2)
        kind = (kinds or {}).get(f'{file}:{eid}') or s.get('kind', '')
        head = semantics.describe(path, tok, eid, kind, s.get('scaled_by'), s.get('token'))
        out[key] = resolve(path, head, s)
    return out


def _records():
    index = jsonio.load(BUILDS / 'index.json') if (BUILDS / 'index.json').exists() else []
    for row in index:
        p = BUILDS / row['file']
        if p.exists():
            yield jsonio.load(p)


@lru_cache(maxsize=1)
def field_map() -> dict[str, dict]:
    """The canonical map over data/builds and the newest game build's localization (needs the tracker;
    without one — a unit test — every field keeps its own build's description)."""
    from . import catalog
    try:
        head = tracker.head_build()
        tok = loc.tokens(head.commit)
    except (OSError, IndexError, subprocess.CalledProcessError) as e:
        print('WARN: no tracker for the label map, fields keep their own build\'s words:', e)
        return {}
    try:
        kinds = {k: e.get('kind', '') for k, e in catalog.load().items()}
    except FileNotFoundError:
        kinds = {}
    return build(_records(), tok, kinds)


def display_unit(era: dict, cn: dict) -> str:
    """The unit printed after a window's values: the field's canonical one. Old bare numbers under a
    unit Valve added later are in that unit (Power Slash's "Slash Radius 50 → 45" of 2024 is the 50m
    the tooltip prints; the 2024 move speeds 7 → 6.5 are m/s) — no build record holds a bare length
    of 40+ engine units under a field that gained "m" (checked 2026-10-04). A speed's "m" is m/s."""
    unit = cn.get('unit') or ''
    return 'm/s' if unit == 'm' and era.get('speed_m') else unit


def canonical(key: str, era: dict, fmap: dict[str, dict] | None = None) -> dict:
    """The field's canonical {label, unit, sign, src}; a field no record changed (one only a '@shared'
    rule moved, a test's) takes its own build's description, signed the same way."""
    hit = (fmap if fmap is not None else field_map()).get(key)
    if hit:
        return hit
    return resolve(key.split(':', 2)[2], era, None)
