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
from .classify import ability_kind, category, hero_bound_abilities, unit_bound_abilities, unit_kind
from .diff import VALUELESS_CATS
from .history import OUT as BUILDS
from .history import reindex

ENRICH_VERSION = 26       # 26: typed fields without m_ named; 25: tier speeds m/s; 24: modifier values; 23: shares %


def _num(v):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = re.match(r'^\s*([-+]?\d*\.?\d+)\s*[a-z%]*\s*$', str(v), re.I)
    return float(m.group(1)) if m else None


def _display(v, meters):
    return semantics.display_raw(v, meters)


def drawbacks(data: dict | None) -> set[str]:
    """Properties the game marks as the holder's downside (m_bIsNegativeAttribute: drawn red)."""
    props = (data or {}).get('m_mapAbilityProperties') or {}
    return {p for p, d in props.items()
            if isinstance(d, dict) and str(d.get('m_bIsNegativeAttribute')).lower() in ('true', '1')}


def loc_tokens_of(data: dict | None) -> dict[str, str]:
    """{property: m_strLocTokenOverride} — the name the tooltip text and label use."""
    props = (data or {}).get('m_mapAbilityProperties') or {}
    return {p: str(d['m_strLocTokenOverride']) for p, d in props.items()
            if isinstance(d, dict) and d.get('m_strLocTokenOverride')}


def negative_props(data: dict | None) -> set[str]:
    """Properties whose base value is below zero: debuffs written as negatives (-50 dash slow)."""
    props = (data or {}).get('m_mapAbilityProperties') or {}
    out = set()
    for p, d in props.items():
        v = _num(d.get('m_strValue')) if isinstance(d, dict) else None
        if v is not None and v < 0:
            out.add(p)
    return out


def enrich_record(rec: dict) -> dict:
    commit = rec['commit']
    tok = loc.tokens(commit)
    heroes = cache.vdata(commit, tracker.SCRIPTS + 'heroes.vdata')
    abilities = cache.vdata(commit, tracker.SCRIPTS + 'abilities.vdata')
    units = cache.vdata(commit, tracker.SCRIPTS + 'npc_units.vdata')
    prev_abilities = None
    owners = hero_bound_abilities(heroes, abilities)
    npc_bound = unit_bound_abilities(units, owners)
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
            e['name'] = (loc.plain(loc.entity_name(tok, eid, owners.get(eid))) if eid != '@shared'
                         else 'Many abilities & items')
        elif f == 'npc_units.vdata':
            data = units.get(eid, {})
            e['kind'] = unit_kind(eid, data) if eid != '@shared' else 'shared'
            e['name'] = loc.unit_name(tok, eid, data) if eid != '@shared' else 'Many units'
        else:
            e['kind'] = 'modifier' if f == 'modifiers.vdata' else 'global'
            e['name'] = eid if eid != '@shared' else f'Many entries ({f})'
        if eid in owners:
            e['owner'] = owners[eid]
            e['owner_name'] = loc.plain(loc.hero_name(tok, owners[eid]))
        downsides = drawbacks(data) if f == 'abilities.vdata' and eid != '@shared' else set()
        below_zero = negative_props(data) if f == 'abilities.vdata' and eid != '@shared' else set()
        tokens = loc_tokens_of(data) if f == 'abilities.vdata' and eid != '@shared' else {}
        # an NPC's ability (Walker's Stomp) moves like its unit: UP / DOWN, not a player's BUFF / NERF
        side = 'unit' if f == 'abilities.vdata' and eid in npc_bound else e['kind']
        for c in e['changes']:
            # classification rules evolve: re-derive the category, but never move a
            # change whose values were dropped (cosmetic) into a category that shows values
            has_vals = 'old' in c or 'new' in c
            cat = category(c['path'], c.get('old'), c.get('new'))
            if has_vals or cat in VALUELESS_CATS:
                c['cat'] = cat
            # what the property's coefficient multiplies (boons, melee damage…): kept on the change so
            # match.window_changes labels it the same way (140 rows all said "spirit scaling")
            scaled = (semantics.scale_stat(data, semantics.property_name(c['path']))
                      if f == 'abilities.vdata' and eid != '@shared' and 'Scale' in c['path'] else None)
            if scaled and scaled != 'ETechPower':
                c['scaled_by'] = scaled
            token = tokens.get(semantics.property_name(c['path'])) if tokens else None
            if token:
                c['loc_token'] = token          # the tooltip's own name for the property
            d = semantics.describe(c['path'], tok, eid, e['kind'], c.get('scaled_by'), token)
            c['label'] = d['label']
            if d.get('unit'):
                c['unit'] = d['unit']
            if 'old' in c or 'new' in c:
                c['old_s'] = semantics.show(c.get('old'), d['meters'], d.get('unit', ''), d.get('invert', False))
                c['new_s'] = semantics.show(c.get('new'), d['meters'], d.get('unit', ''), d.get('invert', False))
                # the property itself, not a T1-T3 bonus to it (a bigger bonus there shrinks the downside)
                worse = c['path'].startswith('m_mapAbilityProperties.') and semantics.property_name(c['path']) in downsides
                if worse:
                    c['drawback'] = True        # match.change_json re-judges the window total with it
                # a T1-T3 / Enhanced bonus to a property whose value is negative (a debuff)
                neg = '.m_vecPropertyUpgrades' in c['path'] and semantics.property_name(c['path']) in below_zero
                if neg:
                    c['neg_base'] = True
                dirn, pct = semantics.direction(c['path'], _num(c.get('old')), _num(c.get('new')), side, worse, neg)
                c['dir'] = dirn
                c['pct'] = None if pct is None else round(pct, 1)
                c['grad'] = semantics.gradient(pct)
                if semantics.reencoded(c.get('old'), c.get('new'), c['path']):
                    c['same'] = True            # the same value written another way: cards.is_noop drops it
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
