"""Catalog of every entity that ever existed in the tracked vdata files.

For each entity: file, kind, owner hero (for abilities/weapons), first and
last build seen, whether it still exists, and its display name taken from the
localization of the last build it existed in (so removed items keep the name
they had in game).

    python -m pipeline.catalog   ->  data/entities.json
"""
from __future__ import annotations

import json
import time

from . import cache, loc, tracker
from .classify import ability_kind, hero_bound_abilities, unit_kind

OUT = tracker.ROOT / 'data' / 'entities.json'
FILES = ('heroes.vdata', 'abilities.vdata', 'npc_units.vdata', 'misc.vdata', 'modifiers.vdata', 'generic_data.vdata')


def _kind(file: str, eid: str, data: dict, owners: dict) -> str:
    if file == 'heroes.vdata':
        return 'hero'
    if file == 'abilities.vdata':
        return ability_kind(eid, data, owners)
    if file == 'npc_units.vdata':
        return unit_kind(eid, data)
    if file == 'modifiers.vdata':
        return 'modifier'
    return 'global'


def build() -> dict:
    t0 = time.time()
    ents: dict[str, dict] = {}
    last_blobs: dict[str, str | None] = {}
    heroes: dict = {}
    head = tracker.builds()[-1]
    for b in tracker.builds():
        touched = [f for f in FILES if tracker.SCRIPTS + f in b.files]
        if not touched and last_blobs:
            continue
        snap = {}
        for f in FILES:
            blob = tracker.blob_id(b.commit, tracker.SCRIPTS + f)
            if blob != last_blobs.get(f) or f == 'heroes.vdata':
                snap[f] = (blob, cache.vdata_blob(blob) if blob else {})
            last_blobs[f] = blob
        if 'heroes.vdata' in snap:
            heroes = snap['heroes.vdata'][1]
        owners = hero_bound_abilities(heroes)
        ability_slots = {}
        for h in heroes.values():
            if isinstance(h, dict):
                for slot, aid in (h.get('m_mapBoundAbilities') or {}).items():
                    if isinstance(aid, str):
                        ability_slots.setdefault(aid, slot.replace('ESlot_', ''))
        for f, (_, data) in snap.items():
            for eid, val in data.items():
                if not isinstance(val, dict) or eid in ('generic_data_type', '_include'):
                    continue
                key = f'{f}:{eid}'
                e = ents.get(key)
                if e is None:
                    e = ents[key] = {'file': f, 'id': eid, 'first': [b.build, b.date[:10]], 'owner': None}
                e['last'] = [b.build, b.date[:10], b.commit]
                e['kind'] = _kind(f, eid, val, owners)
                if eid in owners:
                    e['owner'] = owners[eid]
                if eid in ability_slots:
                    e['ability_slot'] = ability_slots[eid]     # Signature_4 = ultimate
                if val.get('_not_pickable'):
                    e['template'] = True
                if val.get('m_sLocUnitName'):
                    e['loc_key'] = str(val['m_sLocUnitName']).lstrip('#').lower()
                if f == 'heroes.vdata':
                    e['state'] = str(val.get('m_eHeroDevelopmentState') or ('disabled' if val.get('m_bDisabled') else ''))
                if f == 'abilities.vdata' and e['kind'] == 'item':
                    e['tier'] = str(val.get('m_iItemTier') or '')
                    e['slot'] = str(val.get('m_eItemSlotType') or '')
                    e['disabled'] = str(val.get('m_bDisabled')).lower() in ('true', '1')
    # names from the last build each entity existed in
    by_commit: dict[str, list[dict]] = {}
    for e in ents.values():
        e['alive'] = e['last'][2] == head.commit or e['last'][0] == head.build
        by_commit.setdefault(e['last'][2], []).append(e)
    for commit, group in by_commit.items():
        tok = loc.tokens(commit)
        for e in group:
            if e['file'] == 'heroes.vdata':
                e['name'] = loc.hero_name(tok, e['id'])
            elif e['file'] == 'npc_units.vdata':
                e['name'] = loc.unit_name(tok, e['id'], {'m_sLocUnitName': e.get('loc_key', '')})
            else:
                e['name'] = loc.entity_name(tok, e['id'], e.get('owner'))
    for e in ents.values():
        e['last'] = e['last'][:2]
    data = {'build': head.build, 'entities': sorted(ents.values(), key=lambda e: (e['file'], e['id']))}
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f"{len(ents)} entities, {time.time() - t0:.0f}s -> {OUT}")
    return data


def load() -> dict[str, dict]:
    data = json.loads(OUT.read_text(encoding='utf-8'))
    return {f"{e['file']}:{e['id']}": e for e in data['entities']}


if __name__ == '__main__':
    build()
