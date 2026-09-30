"""Add human-readable fields to build records (in place).

History records are raw diffs. This pass adds, using the localization and
hero data OF THAT SAME BUILD:
  entity: name, kind, owner, owner_name
  change: label, old_s, new_s, dir, pct, grad
so the site builder never needs the tracker clone (CI builds from data/).

    python -m pipeline.enrich [--all]
"""
from __future__ import annotations

import argparse
import re

from . import cache, jsonio, loc, semantics, tracker
from .classify import ability_kind, category, hero_bound_abilities, unit_kind
from .diff import VALUELESS_CATS
from .history import OUT as BUILDS
from .history import reindex

ENRICH_VERSION = 3


def _num(v):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = re.match(r'^\s*([-+]?\d*\.?\d+)\s*[a-z%]*\s*$', str(v), re.I)
    return float(m.group(1)) if m else None


def _display(v, meters):
    n = _num(v)
    return semantics.display_value(n if n is not None else v, meters)


def enrich_record(rec: dict) -> dict:
    commit = rec['commit']
    tok = loc.tokens(commit)
    heroes = cache.vdata(commit, tracker.SCRIPTS + 'heroes.vdata')
    abilities = cache.vdata(commit, tracker.SCRIPTS + 'abilities.vdata')
    units = cache.vdata(commit, tracker.SCRIPTS + 'npc_units.vdata')
    prev_abilities = None
    owners = hero_bound_abilities(heroes)
    for e in rec['entities']:
        f, eid = e['file'], e['id']
        if f == 'heroes.vdata':
            e['kind'] = 'hero'
            e['name'] = loc.plain(loc.hero_name(tok, eid)) if eid != '@shared' else 'All heroes'
        elif f == 'abilities.vdata':
            data = abilities.get(eid)
            if data is None:   # removed entity: classify from the previous build
                if prev_abilities is None:
                    prev_abilities = cache.vdata(rec['prev_commit'], tracker.SCRIPTS + 'abilities.vdata')
                data = prev_abilities.get(eid, {})
            e['kind'] = ability_kind(eid, data, owners) if eid != '@shared' else 'shared'
            e['name'] = loc.plain(loc.entity_name(tok, eid)) if eid != '@shared' else 'Many abilities & items'
        elif f == 'npc_units.vdata':
            data = units.get(eid, {})
            e['kind'] = unit_kind(eid, data) if eid != '@shared' else 'shared'
            key = str(data.get('m_sLocUnitName', '')).lstrip('#').lower()
            e['name'] = loc.plain(tok.get(key)) or eid if eid != '@shared' else 'Many units'
        else:
            e['kind'] = 'modifier' if f == 'modifiers.vdata' else 'global'
            e['name'] = eid if eid != '@shared' else f'Many entries ({f})'
        if eid in owners:
            e['owner'] = owners[eid]
            e['owner_name'] = loc.plain(loc.hero_name(tok, owners[eid]))
        for c in e['changes']:
            # classification rules evolve: re-derive the category, but never move a
            # change whose values were dropped (cosmetic) into a category that shows values
            has_vals = 'old' in c or 'new' in c
            cat = category(c['path'], c.get('old'), c.get('new'))
            if has_vals or cat in VALUELESS_CATS:
                c['cat'] = cat
            d = semantics.describe(c['path'], tok, eid, e['kind'])
            c['label'] = d['label']
            if 'old' in c or 'new' in c:
                c['old_s'] = _display(c.get('old'), d['meters'])
                c['new_s'] = _display(c.get('new'), d['meters'])
                dirn, pct = semantics.direction(c['path'], _num(c.get('old')), _num(c.get('new')), e['kind'])
                c['dir'] = dirn
                c['pct'] = None if pct is None else round(pct, 1)
                c['grad'] = semantics.gradient(pct)
    rec['enriched'] = ENRICH_VERSION
    return rec


def run(all_records: bool = False) -> None:
    n = 0
    for p in sorted(BUILDS.glob('*_*.json.gz')):
        rec = jsonio.load(p)
        if not all_records and rec.get('enriched') == ENRICH_VERSION:
            continue
        if not rec['entities']:
            rec['enriched'] = ENRICH_VERSION
        else:
            enrich_record(rec)
        jsonio.dump(p, rec)
        n += 1
    reindex()
    print(f'enriched {n} build records')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--all', action='store_true')
    run(ap.parse_args().all)
