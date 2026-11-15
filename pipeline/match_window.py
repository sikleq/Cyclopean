"""A patch window's changes: its build records merged into one change per field (`window_changes`, `merge_ops`),
the marks a window puts on them (moves of availability, dud guns, inherited defaults, retyped values), lists
re-keyed by their ids (`rekey_lists`) and the builds before and after the window (`window_states`)."""
from __future__ import annotations

import re
from functools import lru_cache

from . import cache, game_map, jsonio, labels, semantics, tracker
from . import flatten as flatten_mod
from .diff import _eq as diff_eq, _jsonable as jsonable
from . import patches as patches_mod
from . import classify as classify_mod
from .classify import GAMEPLAY_CATS, category, decor_entity
from .patches import Patch
from .match_values import MChange, num


BUILDS = tracker.BUILDS_DIR


def load_record(file_name: str) -> dict:
    return jsonio.load(BUILDS / file_name)


def merge_ops(first: str, then: str) -> str:
    """One field's op across the window's builds. A field added then tuned is still NEW (it was
    shown as '— → 0.75' CHANGED), tuned then removed is DEL ('16.2 → —'); added then removed
    never shipped and becomes a no-op change (old == new == None, dropped below)."""
    if first == 'add':
        return 'change' if then == 'remove' else 'add'
    if first == 'remove':
        return 'change' if then == 'add' else 'remove'
    return 'remove' if then == 'remove' else 'change'


_PROVIDED_TYPE = re.compile(r'^m_mapAbilityProperties\.([^.]+)\.m_eProvidedPropertyType$')


def mark_retyped(changes: list[MChange]) -> None:
    """A property whose provided type flipped in the window (REDUCTION_PERCENT → INCREASE_PERCENT) flips
    the sign of its numbers with it: Riposte's "Melee Resist −22% → 22%" is the same resist written the
    other way round (`retyped` -> change_json 'same'). A sign flip without it stays a change."""
    retyped = {(c.file, c.eid, m.group(1)) for c in changes if c.op == 'change'
               for m in [_PROVIDED_TYPE.match(c.path)] if m}
    if not retyped:
        return
    for c in changes:
        if (c.file, c.eid, semantics.property_name(c.path)) in retyped and not _PROVIDED_TYPE.match(c.path):
            c.retyped = True


_SELECTABLE = 'm_bPlayerSelectable'


_DEV_STATE = 'm_eHeroDevelopmentState'


_IN_DEV = 'm_bInDevelopment'


_TRUTHY = ('true', '1', 'yes')


def mark_availability_moves(changes: list[MChange]) -> None:
    """A hero's availability written in another field, not a change: on 2026-09-29 heroes.vdata dropped
    m_bPlayerSelectable and gained m_eHeroDevelopmentState, so 38 released heroes read "Hero Development State →
    Release" (ON) and 43 "Player Selectable yes → —" in the newest band of their pages, counted as not in the
    patch notes (Haze "seemed to be released on September 29", review 2026-10-05). Both rows of a hero are
    `moved` (change_json 'same': no row, no count) when the old flag and the new state say the same — selectable
    and a released state, or not selectable and a state that is not; a hero that changed availability keeps both."""
    by_hero: dict[str, dict[str, MChange]] = {}
    for c in changes:
        if c.file == 'heroes.vdata' and c.path in (_SELECTABLE, _DEV_STATE, _IN_DEV):
            by_hero.setdefault(c.eid, {})[c.path] = c
    for fields in by_hero.values():
        flag, state, in_dev = fields.get(_SELECTABLE), fields.get(_DEV_STATE), fields.get(_IN_DEV)
        if state and in_dev and state.op == 'change' and str(state.new) in RELEASED_STATES:
            # the old in-development flag turned ON the day Baba and Violet were released ("OFF In Development no →
            # yes" beside "ON Release", data review 2026-10-17): the state says it; the flag's row is part of it
            in_dev.moved = True
        if not flag or not state or flag.op != 'remove' or state.op != 'add':
            continue
        if (str(flag.old).lower() in _TRUTHY) == (str(state.new) in LISTED_STATES):
            flag.moved = state.moved = True


def mark_dud_guns(changes: list[MChange]) -> None:
    """A weapon block that came or went whole on an ability that is no gun, with zero bullet damage, never fired: the
    engine's default gun copied in (Aura of Suffering lost one of 100 fields on 2026-03-06 — spread, recoil, clip 0 —
    which a wrong word link had called described; the audit calls them not gameplay). Its added / removed rows are
    plumbing; a value that changed inside it stays."""
    blocks: dict[str, list[MChange]] = {}
    for c in changes:
        if c.file == 'abilities.vdata' and c.kind != 'weapon' and c.path.startswith('m_mapWeaponInfos.'):
            blocks.setdefault(c.eid, []).append(c)
    for rows in blocks.values():
        dmg = next((c for c in rows if c.path.endswith('.m_flBulletDamage')), None)
        if dmg is None or not ((dmg.op == 'remove' and num(dmg.old) == 0) or (dmg.op == 'add' and num(dmg.new) == 0)):
            continue
        for c in rows:
            if c.op in ('add', 'remove'):
                c.cat = 'technical'


_BASE_LINK = ('_base', '_multibase')


def nameless_part(eid: str, cat: dict[str, dict]) -> bool:
    """A second part of an ability with no name of its own: its id is the parent's plus a part suffix
    (classify._SUB_SUFFIX) and it bears the parent's name or none ('ability_ice_dome_trigger' of Frozen Shelter). A part
    named on its own is an ability of its own (Solomon's 'ability_chessmaster_knightbuff_trigger' is "Move King", Mirage's
    'mirage_teleport' "Traveler")."""
    parent = classify_mod.sub_part_parent(eid)
    pe = cat.get(f'abilities.vdata:{parent}') if parent else None
    if not pe:
        return False
    name = (cat.get(f'abilities.vdata:{eid}') or {}).get('name')
    return not name or name == eid or name == pe.get('name')


def mark_inherited_defaults(changes: list[MChange], cat: dict[str, dict]) -> None:
    """A nameless part of an ability (`nameless_part`: its trigger, cancel, recast) that gets a template in the
    window (`_multibase` / `_base` added) takes the template's defaults: every field it did not have "appears" — Frozen
    Shelter's trigger read "Activation added (instant cast)", "Max Level added (1)", "Charge Delay added (default)",
    "Bullet Velocity added (254m/s)" among City Never Sleeps' hidden changes (review 2026-10-17, round 4). Those added
    rows are plumbing, as the audit calls an explicit default (NOT_GAMEPLAY "explicit 0 default added"); a value that
    changed stays. Only a part: a whole ability or item moving to another template (an item's tier move) is real."""
    linked = {(c.file, c.eid) for c in changes if c.path in _BASE_LINK and c.op == 'add'
              and c.file == 'abilities.vdata' and nameless_part(c.eid, cat)}
    for c in changes:
        if (c.file, c.eid) in linked and c.op == 'add' and c.cat in GAMEPLAY_CATS:
            c.cat = 'technical'


def _window_change(file: str, tid: str, c: dict, ce: dict, builds: list, shared: bool, tok: dict[str, str],
                   canon: dict[str, dict]) -> MChange:
    """A record's field change `c` of entity `tid` as the window's MChange (labels of that build's text)."""
    key = f"{file}:{tid}:{c['path']}"
    d = semantics.describe(c['path'], tok, tid, ce.get('kind', ''), c.get('scaled_by'), c.get('loc_token'),
                           c.get('scale_parts'))
    cn = canon[key] = labels.canonical(key, d)
    shown = cn['label']
    if c.get('scale_parts') and 'scaling' not in shown:
        # a scaling T1-T3 bonus its path does not name (enrich.tier_scaling) says so in ITS window only: one field can
        # be a flat bonus in one build and a scaling one later (Warden's T3 Barrier +150, Fire Scarabs' T3 63 → 1.2)
        shown += semantics.scaling_suffix(c['scale_parts'])
    return MChange(
        file, tid, c['path'], c['op'], c.get('old'), c.get('new'), c['cat'],
        # an NPC's ability (catalog 'units': Walker's Stomp) is judged as its unit: UP / DOWN
        'unit' if ce.get('units') else ce.get('kind', ''), ce.get('owner'), d['label'], d['meters'],
        builds, shared, chain=[c.get('old'), c.get('new')],
        drawback=bool(c.get('drawback')), neg_base=bool(c.get('neg_base')),
        unit=labels.display_unit(d, cn), invert=bool(d.get('invert')),
        speed_m=bool(d.get('speed_m')), shown=shown, sign=cn['sign'], base=c.get('base'))


# lists whose entries carry their own name (a breakable's pickups, a loot table's items, the lanes): one entry
# inserted at #2 shifted every later row — "Primary Pickups #3 › Pickup: Medium → Large", "#4 …" (#12.6 / #41)
LIST_IDS = ('m_sPickup', 'm_strItem', 'm_strLaneName')


_LIST_INDEX = re.compile(r'^(\w+)\[\d+\]\.')


# the files that hold such lists (an ability's T1-T3 list IS positional: never re-read the big abilities.vdata)
LIST_FILES = ('misc.vdata', 'loot_tables.vdata', 'generic_data.vdata')


def keyed_list(entity, name: str) -> dict[str, object] | None:
    """{path: value} of an entity's list `name` keyed by the name its entries carry ("m_vecPrimaryPickups
    {spirit_permanent_pickup}.m_flPickupWeight"), or None when an entry has none or two share one."""
    obj = entity if isinstance(entity, dict) else {'value': entity}
    items = obj.get(name)
    if items is None and entity is not None:
        return {}                                   # the list came or went whole: every entry is new / gone
    if not isinstance(items, list) or not items or not all(isinstance(x, dict) for x in items):
        return None
    for id_field in LIST_IDS:
        ids = [x.get(id_field) for x in items]
        if all(isinstance(i, str) and i for i in ids) and len(set(ids)) == len(ids):
            out = {}
            for x in items:
                flat = flatten_mod.flatten(x)
                if len(flat) > 1:
                    flat.pop(id_field, None)        # the entry's other rows say it came or went; its name is the key
                out.update({f'{name}{{{x[id_field]}}}.{path}': v for path, v in flat.items()})
            return out
    return None


@lru_cache(maxsize=8)
def _state(commit: str, file: str) -> dict:
    """A vdata file as a build left it, parsed once (a shared edit over 23 breakables reads misc.vdata 46 times)."""
    return cache.vdata(commit, tracker.SCRIPTS + file)


def rekey_lists(p: Patch, changes: list[MChange], cat: dict[str, dict], tok: dict[str, str],
                canon: dict[str, dict]) -> list[MChange]:
    """The window's rows of a named-entries list (`LIST_IDS`) by entry instead of by position: the list as the
    window found it and left it (`window_states`), diffed by the entries' names. The build records keep their
    positions (keying them in pipeline/flatten.py needs every record rebuilt: `history --rebuild`, ~25 min)."""
    # a window a hero's release interrupts: its "before" and "after" states hold the release build's edits too — a list
    # that build moved stays by position (its rows are the release's)
    theirs: set[tuple[str, str, str]] = set()
    for row in patches_mod.gap_builds(p):
        for e in load_record(row['file'])['entities']:
            if e['file'] in LIST_FILES:
                theirs |= {(e['file'], e['id'], m.group(1)) for c in e.get('changes', ())
                           for m in [_LIST_INDEX.match(c['path'])] if m}
    lists: dict[tuple[str, str, str], list[MChange]] = {}
    for c in changes:
        m = _LIST_INDEX.match(c.path)
        if m and c.file in LIST_FILES and (c.file, c.eid, m.group(1)) not in theirs:
            lists.setdefault((c.file, c.eid, m.group(1)), []).append(c)
    if not lists:
        return changes
    before, after = window_states(p)
    if not before or not after:
        return changes
    drop: set[int] = set()
    out: list[MChange] = []
    for (file, eid, name), rows in sorted(lists.items()):
        a = keyed_list(_state(before, file).get(eid), name)
        b = keyed_list(_state(after, file).get(eid), name)
        if a is None or b is None:
            continue
        drop |= {id(c) for c in rows}
        builds = sorted({x for c in rows for x in c.builds})
        shared = any(c.shared for c in rows)
        ce = cat.get(f'{file}:{eid}', {})
        for path in sorted(a.keys() | b.keys()):
            old, new = a.get(path), b.get(path)
            if path in a and path in b and diff_eq(old, new):
                continue
            op = 'change' if path in a and path in b else 'add' if path in b else 'remove'
            rec = {'path': path, 'op': op, 'old': jsonable(old), 'new': jsonable(new), 'cat': category(path, old, new)}
            out.append(_window_change(file, eid, rec, ce, list(builds), shared, tok, canon))
    return [c for c in changes if id(c) not in drop] + out


def window_changes(p: Patch, cat: dict[str, dict], tok: dict[str, str]) -> tuple[list[MChange], dict]:
    """Merge the builds of a window. Entities added inside the window are not
    diffed field by field (their whole data is "new"): they become one
    'entity added' change each."""
    merged: dict[str, MChange] = {}
    canon: dict[str, dict] = {}
    extras = {'loc': [], 'convars': [], 'assets': [], 'entities_added': [], 'entities_removed': [],
              'entities_returned': []}
    added_here: set[str] = set()
    for row in p.builds:
        rec = load_record(row['file'])
        for e in rec['entities']:
            targets_default = [e['id']]
            ekey = f"{e['file']}:{e['id']}"
            # a new entry compared with the one it follows (a ranked season against the season before it,
            # diff.previous_season) carries real "was -> now" rows: matched field by field like a returned one
            follows = e['status'] == 'added' and any(c.get('op') == 'change' for c in e['changes'])
            if e['status'] in ('added', 'removed', 'returned'):
                if e['status'] == 'added' and not follows:
                    added_here.add(ekey)
                ce = cat.get(ekey, {})
                extras[f"entities_{e['status']}"].append({
                    'file': e['file'], 'id': e['id'], 'build': rec['build'],
                    'name': event_name(e, ce), 'kind': e.get('kind'), 'owner': e.get('owner'),
                    'units': ce.get('units'), 'gameplay': _gameplay_entity(e)})
                if e['status'] != 'returned' and not follows:
                    continue                  # a returned entity's fields differ from its last version: diffed below
            if ekey in added_here:
                continue
            for c in e['changes']:
                for tid in (c.get('targets') or targets_default):
                    if f"{e['file']}:{tid}" in added_here:
                        continue
                    ce = cat.get(f"{e['file']}:{tid}", {})
                    key = f"{e['file']}:{tid}:{c['path']}"
                    mc = merged.get(key)
                    if mc is None:
                        merged[key] = _window_change(e['file'], tid, c, ce, [rec['build']], bool(c.get('targets')),
                                                     tok, canon)
                    else:
                        mc.new = c.get('new')
                        mc.chain.append(c.get('new'))
                        mc.builds.append(rec['build'])
                        mc.op = merge_ops(mc.op, c['op'])
        extras['loc'].extend(dict(x, build=rec['build']) for x in rec.get('loc') or [])
        extras['convars'].extend(dict(x, build=rec['build']) for x in rec.get('convars') or [])
        if rec.get('assets'):
            extras['assets'].append({'build': rec['build'], **rec['assets']})
    changes = [c for c in merged.values() if not (c.op == 'change' and c.old == c.new)]
    changes = rekey_lists(p, changes, cat, tok, canon)
    for c in changes:
        sw = labels.unit_switch(canon.get(c.key) or {}, c.builds) if c.op == 'change' else None
        if sw:
            era = {'speed_m': c.speed_m}
            c.old_unit, c.unit = (labels.display_unit(era, {'unit': u}) for u in sw)
    mark_retyped(changes)
    mark_availability_moves(changes)
    mark_dud_guns(changes)
    mark_inherited_defaults(changes, cat)
    # console variables take part in matching ("Respawn time … from 35s to 38s"), and so does one a game system
    # names that came with a value ("Unstable Rift spawn interval increased from every 6 minutes to every 7
    # minutes" is citadel_koth_respawn_interval added at 420; coverage finding 8) — not the snapshot that started
    # the tracking (every variable "added"), nor one that also moved in the window (its change row is the match)
    moved_cv = {cv['name'] for cv in extras['convars'] if cv.get('op') == 'change'}
    for cv in extras['convars']:
        new = num(cv.get('new'))
        if cv.get('op') == 'change' and num(cv.get('old')) is not None and new is not None:
            old = cv['old']
        elif (cv.get('op') == 'add' and new is not None and cv['name'] not in moved_cv
              and cv.get('build') != game_map.convar_start() and game_map.convar_system(cv['name'])):
            old = None
        else:
            continue
        label = cv['name'].replace('citadel_', '').replace('_', ' ')
        changes.append(MChange('convars', cv['name'], cv['name'], cv['op'], old, cv['new'], 'balance',
                               'global', None, label, False, [cv['build']]))
    # an entity added and removed within one window never shipped; one removed and back within one
    # window (or back and removed again) is where it started: only its field changes remain
    removed = {f"{x['file']}:{x['id']}" for x in extras['entities_removed']}
    returned = {f"{x['file']}:{x['id']}" for x in extras['entities_returned']}
    both = (added_here | returned) & removed
    for bucket in ('entities_added', 'entities_removed', 'entities_returned'):
        extras[bucket] = [x for x in extras[bucket] if f"{x['file']}:{x['id']}" not in both]
    return changes, extras


def event_name(e: dict, ce: dict) -> str | None:
    """A removed ability loses its text in the build that removes it: the catalog keeps the name it
    had in game (Witching Hour, Pulse Cannon — 29 events lost until review 2026-10-02)."""
    name = e.get('name')
    return ce.get('name') or name if not name or name == e['id'] else name


def _gameplay_entity(e: dict) -> bool:
    if e['file'] in ('misc.vdata', 'generic_data.vdata') and decor_entity(e['id']):
        return False                    # the city's traffic, team colours, minimap offsets (classify)
    if e['status'] == 'removed':        # a removed entity carries no fields: judge its id
        return e['file'] != 'generic_data.vdata' or category(e['id'], None, None) in GAMEPLAY_CATS
    return any(c.get('cat') in GAMEPLAY_CATS for c in e['changes'])


# a hero is in the game from its release; pre-release (in the files, announced, not playable: Nurse Harrow on
# 2026-10-16, due on 10-20) is still work before release — her boon tuning had the eye (data review 2026-10-17)
RELEASED_STATES = ('EHeroDevState_Release',)


# the states a hero is listed in (the old m_bPlayerSelectable said the same: `mark_availability_moves`)
LISTED_STATES = ('EHeroDevState_Release', 'EHeroDevState_PreRelease')


def gap_text_states(p: Patch):
    """For a window a hero's release interrupts: row -> (commit before its first build, commit of its last build) for
    a text change whose entity a release build in the gap also changed, else None. The window's edges hold that
    build's edits too: Violet's Homing Brush T1 (text of 6796) read its values after Nurse Harrow's release (6801) in
    the 10-14 window (2026-11-15). None when the window has no gap."""
    gap = patches_mod.gap_builds(p)
    if not gap:
        return None
    touched = {f"{e['file']}:{e['id']}" for row in gap for e in load_record(row['file'])['entities']}
    files = {b['build']: b['file'] for b in p.builds}

    def own(row: dict) -> tuple[str | None, str | None] | None:
        builds = [files[b] for b in sorted(row.get('builds') or ()) if b in files]
        if row.get('ent') not in touched or not builds:
            return None
        return load_record(builds[0]).get('prev_commit'), load_record(builds[-1]).get('commit')
    return own


def window_states(p: Patch) -> tuple[str | None, str | None]:
    """(commit before the window's first build, commit of its last build): the game as a window found it and left
    it — the old and new sides of its merged changes."""
    if not p.builds:
        return None, None
    return load_record(p.builds[0]['file']).get('prev_commit'), load_record(p.builds[-1]['file']).get('commit')
