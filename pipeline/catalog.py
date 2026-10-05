"""Catalog of every entity that ever existed in the tracked vdata files.

For each entity: file, kind, owner hero (for abilities/weapons) or the NPCs
that bind it (`units`: Walker's Stomp, Patron's gun), first and
last build seen, whether it still exists, and its display name taken from the
localization of the last build it existed in (so removed items keep the name
they had in game).

    python -m pipeline.catalog   ->  data/entities.json
"""
from __future__ import annotations

import json
import re
import time

from . import cache, loc, tracker
from .classify import (ability_kind, hero_bound_abilities, shared_abilities, unit_bound_abilities, unit_is_helper,
                       unit_kind)

OUT = tracker.ROOT / 'data' / 'entities.json'
FILES = ('heroes.vdata', 'abilities.vdata', 'npc_units.vdata', 'misc.vdata', 'modifiers.vdata', 'generic_data.vdata')


def _kind(file: str, eid: str, data: dict, owners: dict, shared: set[str] = frozenset()) -> str:
    if file == 'heroes.vdata':
        return 'hero'
    if file == 'abilities.vdata':
        return ability_kind(eid, data, owners, shared)
    if file == 'npc_units.vdata':
        kind = unit_kind(eid, data)
        # any kind: the Hideout's cat is "neutral" by its id, a zipline container "trooper"
        return 'helper' if unit_is_helper(eid, data) else kind
    if file == 'modifiers.vdata':
        return 'modifier'
    return 'global'


def build() -> dict:
    t0 = time.time()
    ents: dict[str, dict] = {}
    last_blobs: dict[str, str | None] = {}
    current: dict[str, set[str]] = {}         # ids in the latest version of each file
    heroes: dict = {}
    abilities_now: dict = {}
    units_now: dict = {}
    by_units: dict[str, set[str]] = {}       # ability -> every NPC that ever bound it (Walker's Stomp)
    head = tracker.head_build()
    upkeep_files: set[str] = set()
    for b in tracker.builds():
        if not tracker.is_game_build(b):
            # tracker upkeep: no build number to date an entity with; a file it touched is read
            # with the next build
            upkeep_files |= set(b.files)
            continue
        touched = [f for f in FILES if tracker.SCRIPTS + f in b.files or tracker.SCRIPTS + f in upkeep_files]
        upkeep_files = set()
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
        if 'abilities.vdata' in snap:
            abilities_now = snap['abilities.vdata'][1]
        if 'npc_units.vdata' in snap:
            units_now = snap['npc_units.vdata'][1]
        owners = hero_bound_abilities(heroes, abilities_now)
        shared = shared_abilities(heroes)
        for aid, uids in unit_bound_abilities(units_now, owners, shared).items():
            by_units.setdefault(aid, set()).update(uids)
        ability_slots = {}
        for h in heroes.values():
            if isinstance(h, dict):
                for slot, aid in (h.get('m_mapBoundAbilities') or {}).items():
                    if isinstance(aid, str):
                        ability_slots.setdefault(aid, slot.replace('ESlot_', ''))
        for f, (_, data) in snap.items():
            current[f] = {k for k, v in data.items() if isinstance(v, dict)}
            for eid, val in data.items():
                if not isinstance(val, dict) or eid in ('generic_data_type', '_include'):
                    continue
                key = f'{f}:{eid}'
                e = ents.get(key)
                if e is None:
                    e = ents[key] = {'file': f, 'id': eid, 'first': [b.build, b.date[:10]], 'owner': None}
                e['last'] = [b.build, b.date[:10], b.commit]
                e['kind'] = _kind(f, eid, val, owners, shared)
                if eid in owners:
                    e['owner'] = owners[eid]
                elif eid in shared:
                    e['owner'] = None          # every hero's (jump, dash…): its last state wins
                    by_units.pop(eid, None)
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
        # alive = still in the latest version of its file. Not "seen in the head build": a build
        # that leaves abilities.vdata alone (6728) killed every item on the site (2026-10-01)
        e['alive'] = e['id'] in current.get(e['file'], set())
        if e['file'] == 'abilities.vdata' and e['id'] in by_units and not e.get('owner'):
            e['units'] = sorted(by_units[e['id']])
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
    # (not a gun: its text is its hero's, so an old variant would take the hero's gun name today)
    earlier_names([e for e in ents.values() if e['file'] in ('abilities.vdata', 'npc_units.vdata')
                   and (e.get('name') or e['id']) == e['id'] and e.get('kind') != 'weapon'
                   and not e['id'].startswith('citadel_weapon_')], ents.values())
    drop_unit_names(ents.values())
    data = {'build': head.build, 'entities': sorted(ents.values(), key=lambda e: (e['file'], e['id']))}
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f"{len(ents)} entities, {time.time() - t0:.0f}s -> {OUT}")
    return data


_DEPRECATED = re.compile(r'^\s*\[deprecated\]\s*|\s*-\s*deprecated\s*$', re.I)


def name_in(tok: dict[str, str], e: dict) -> str | None:
    """The entity's name in one build's text, without Valve's "[Deprecated]" marks; None when it has none there
    ("DEPRICATED" is no name)."""
    if e['file'] == 'npc_units.vdata':
        name = loc.unit_name(tok, e['id'], {'m_sLocUnitName': e.get('loc_key', '')})
    else:
        name = loc.plain(loc.entity_name(tok, e['id'], e.get('owner')))
    name = _DEPRECATED.sub('', name or '').strip()
    # "Bullet Resilience Disabled": Valve marking a dead entry, not its name — an older build has it
    if (not name or name == e['id'] or 'deprecated' in name.lower() or 'depricated' in name.lower()
            or re.search(r'\bdisabled$', name, re.I)):
        return None
    return name


def earlier_names(missing: list[dict], everyone=()) -> None:
    """An entity whose last build's text has no name for it gets the newest name an earlier build gave it (a removed
    item's key left the text before the item did: "Ablative coat", "Aoe silence" were EMP Grenade… on 57 item pages,
    review 2026-10-05). The text of each distinct state of the english files is read once, newest first. A
    patch page keeps its own build's name (rule 4); this is the catalog's fallback. A found item / ability name another
    entity has too (the live "Toughness") is marked "(old)" on the removed one (`everyone`: all entities); a unit's
    joins its namesakes' family."""
    want = {e['id']: e for e in missing}
    if not want:
        return
    found = _scan_names(want)
    taken: dict[tuple[str, str], int] = {}
    for e in everyone:
        if e.get('name'):
            taken[(e['file'], e['name'])] = taken.get((e['file'], e['name']), 0) + 1
    for e in found:
        # (a unit joins its living namesakes' family instead: unit_families)
        if e['file'] == 'abilities.vdata' and taken.get((e['file'], e['name']), 0) > 1 and not e.get('alive'):
            e['name'] += ' (old)'


def _scan_names(want: dict[str, dict]) -> list[dict]:
    found = []
    seen: set[tuple] = set()
    for b in reversed(tracker.builds()):
        if not want:
            break
        state = tuple(sorted(loc.english_files(b.commit).values()))
        if not state or state in seen:
            continue
        seen.add(state)
        tok = loc.tokens(b.commit)
        for eid, e in list(want.items()):
            name = name_in(tok, e)
            if name:
                e['name'] = name
                found.append(e)
                del want[eid]
    return found


def drop_unit_names(ents) -> None:
    """An NPC's ability whose only text is its unit's name (the kill feed's "Patron" on three of the
    Patron's abilities: one page, three groups named "Patron") has no name of its own: it keeps its
    id, and the pages name it by its id words ("Aoe wave", `common.pretty_id`)."""
    ents = list(ents)
    unit_names = {e['id']: (e.get('name') or '').lower() for e in ents if e['file'] == 'npc_units.vdata'}
    for e in ents:
        if e['file'] == 'abilities.vdata' and e.get('units') and e.get('name') and \
                e['name'].lower() in {unit_names.get(u) for u in e['units']}:
            e['name'] = e['id']


def load() -> dict[str, dict]:
    data = json.loads(OUT.read_text(encoding='utf-8'))
    return {f"{e['file']}:{e['id']}": e for e in data['entities']}


if __name__ == '__main__':
    build()
