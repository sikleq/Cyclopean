"""Non-vdata change sources per build: asset list, convars, build info.

- game/citadel/pak01_dir.txt lists every packed asset with a CRC, so a diff
  tells which models / maps / particles / sounds / UI files changed even
  when no balance file did (new hero model, map geometry, VFX pass...).
- DumpSource2/convars.txt holds console variables with default values; new or
  changed `citadel_*` convars often reveal mechanics that patch notes skip.
"""
from __future__ import annotations

import re
from collections import defaultdict

from . import tracker

ASSET_CATEGORIES = (
    ('maps/', 'map'),
    ('models/heroes', 'hero_model'),
    ('models/npc', 'npc_model'),
    ('models/', 'model'),
    ('particles/', 'particles'),
    ('soundevents/', 'sound'),
    ('sounds/', 'sound'),
    ('panorama/', 'ui'),
    ('materials/', 'material'),
    ('animgraphs/', 'animation'),
    ('animation/', 'animation'),
    ('scripts/', 'data'),
    ('resource/', 'ui'),
)
NOTABLE_CATS = {'map', 'hero_model', 'npc_model'}
NOTABLE_LIMIT = 60
NOTABLE_EXT = ('.vmdl_c', '.vpk', '.vmap_c', '.vwrld_c')

_ASSET_LINE = re.compile(r'^([+-])(\S+) CRC:(\S+) size:(\d+)')
_HERO_DIR = re.compile(r'models/heroes[^/]*/([^/]+)/')
# a hero model whose file grew or shrank this many times over was rebuilt, not touched up: Doorman's luggage trolley
# went 1.68 MB -> 0.17 MB in build 6815 (2026-10-22), the fix of a cart drawn twice (97,000 -> ~9,000 polygons by the
# community's count; no patch note). The hero's history shows it (builders/model_rows.py)
SIZE_JUMP = 3.0
MODEL_EXT = '.vmdl_c'
# the hero a model folder belongs to: heroes.vdata names each hero's model (and its work-in-progress one); a folder's
# "_v2" is a redo of the same hero (hero_doorman wears doorman_v2/, its trolley sits in doorman/)
_HERO_BLOCK = re.compile(r'^\t(hero_\w+) =')
_HERO_MODEL = re.compile(r'm_str(?:WIP)?ModelName = resource_name:"models/heroes[^/]*/([^/"]+)/')
_REDO = re.compile(r'_v\d+$')
# whose a changed file is: (folder pattern, kind). A build page lists changes per hero / unit ("Nurse: model ~1,
# particles ~11") instead of thousands of paths; files without an owner (shared materials, UI) stay counts only
OWNER_RULES = (
    (re.compile(r'models/heroes[^/]*/([^/]+)/'), 'model'),
    (re.compile(r'models/npc[^/]*/([^/]+)/'), 'model'),
    (re.compile(r'particles/(?:abilities|weapon_fx|heroes)/([^/]+)/'), 'particles'),
    (re.compile(r'sounds/vo/([^/]+)/'), 'voice'),
    (re.compile(r'sounds/(?:abilities|weapons|heroes)/([^/]+)/'), 'sounds'),
    (re.compile(r'animgraphs/animgraph2/hero/([^+/]+)\+([^./]+)\.'), 'animgraph'),   # one shared graph, a copy per hero
)
# a shared graph changed in this many heroes' copies at once is one change (6810: `hero_leans` in all 52 heroes)
SHARED_GRAPH = 8
_ANIM_EXT = ('.vanim_c', '.vnmclip_c', '.vseq_c', '.vagrp_c')
_OPS = ('added', 'removed', 'modified')


def asset_category(path: str) -> str:
    for prefix, cat in ASSET_CATEGORIES:
        if path.startswith(prefix):
            return cat
    return 'other'


_LIST_LINE = re.compile(r'^(\S+) CRC:(\S+) size:(\d+)')


def _asset_changes(prev: str, cur: str) -> tuple[dict[str, tuple], dict[str, tuple]]:
    """(added, removed) asset lines as {path: (crc, size)}. Within one tracker clone git diffs the
    list; across the two clones (predecessor -> main) both lists are compared."""
    if tracker._repo_of(prev) == tracker._repo_of(cur):
        out = tracker.git('diff', '-U0', '--no-color', prev, cur, '--', tracker.ASSET_LIST, repo=tracker._repo_of(cur))
        added: dict[str, tuple] = {}
        removed: dict[str, tuple] = {}
        for line in out.splitlines():
            m = _ASSET_LINE.match(line)
            if m:
                (added if m.group(1) == '+' else removed)[m.group(2)] = (m.group(3), int(m.group(4)))
        return added, removed
    a = {m.group(1): (m.group(2), int(m.group(3)))
         for m in map(_LIST_LINE.match, (tracker.read(prev, tracker.ASSET_LIST) or '').splitlines()) if m}
    b = {m.group(1): (m.group(2), int(m.group(3)))
         for m in map(_LIST_LINE.match, (tracker.read(cur, tracker.ASSET_LIST) or '').splitlines()) if m}
    added = {p: c for p, c in b.items() if a.get(p) != c}
    removed = {p: c for p, c in a.items() if b.get(p) != c}
    return added, removed


def asset_diff(prev: str, cur: str) -> dict | None:
    added, removed = _asset_changes(prev, cur)
    if not added and not removed:
        return None
    counts: dict[str, dict[str, int]] = defaultdict(lambda: {'added': 0, 'removed': 0, 'modified': 0})
    notable: dict[str, list] = defaultdict(list)
    heroes_touched: dict[str, set] = defaultdict(set)
    for path in sorted(added.keys() | removed.keys()):   # in order: the NOTABLE_LIMIT cap took a different 60 each run
        if path in added and path in removed:
            op = 'modified'
        elif path in added:
            op = 'added'
        else:
            op = 'removed'
        cat = asset_category(path)
        counts[cat][op] += 1
        m = _HERO_DIR.match(path)
        if m:
            heroes_touched[m.group(1)].add(op)
        if cat in NOTABLE_CATS and path.endswith(NOTABLE_EXT) and len(notable[cat]) < NOTABLE_LIMIT:
            notable[cat].append([op, path])
    out = {
        'counts': dict(sorted(counts.items())),
        'notable': {k: sorted(v, key=lambda x: x[1]) for k, v in notable.items()},
        'hero_models': {k: sorted(v) for k, v in sorted(heroes_touched.items())},
    }
    owners = hero_owners(cur)
    by_owner =asset_owners({p: _op(p, added, removed) for p in added.keys() | removed.keys()}, owners)
    if by_owner:
        out['owners'] = by_owner
    jumps = size_jumps(added, removed)
    if jumps:
        for j in jumps:
            m = _HERO_DIR.match(j['path'])
            j['hero'] = owners.get(_REDO.sub('', m.group(1))) if m else None
        out['model_sizes'] = jumps
    return out


def hero_owners(commit: str) -> dict[str, str]:
    """model_owners of that build's heroes.vdata (its own function: a test without the tracker replaces it)."""
    return model_owners(tracker.read(commit, tracker.SCRIPTS + 'heroes.vdata') or '')


def _op(path: str, added: dict, removed: dict) -> str:
    return 'modified' if path in added and path in removed else 'added' if path in added else 'removed'


def owner_of(folder: str, owners: dict[str, str]) -> str:
    """A folder's hero (heroes.vdata names the model folder; `haze_wip`, `drifter_out_of_combat`, `doorman_v2`
    are the same hero), else the folder itself."""
    name = _REDO.sub('', folder)
    while True:
        if name in owners:
            return owners[name]
        if '_' not in name:
            return folder
        name = name.rsplit('_', 1)[0]


def asset_owners(ops: dict[str, str], owners: dict[str, str]) -> dict[str, dict[str, list[int]]]:
    """{owner: {kind: [added, removed, modified]}} for the files that belong to a hero or unit folder; a shared
    animation graph changed for many heroes at once sits under '*' as {'graph <name>': counts}."""
    out: dict[str, dict[str, list[int]]] = {}
    graphs: dict[str, list[tuple[str, str]]] = {}
    for path in sorted(ops):
        for rx, kind in OWNER_RULES:
            m = rx.match(path)
            if not m:
                continue
            if kind == 'animgraph':
                graphs.setdefault(m.group(1).removesuffix('.vnmgraph'), []).append((owner_of(m.group(2), owners), ops[path]))
                break
            if kind == 'model' and not path.endswith(MODEL_EXT):
                kind = 'animation' if path.endswith(_ANIM_EXT) else 'model parts'
            _count(out, owner_of(m.group(1), owners), kind, ops[path])
            break
    for graph, hits in graphs.items():
        shared = len({o for o, _ in hits}) >= SHARED_GRAPH
        for owner, op in hits:
            _count(out, '*', f'graph {graph}', op) if shared else _count(out, owner, 'animgraph', op)
    return {k: dict(sorted(v.items())) for k, v in sorted(out.items())}


def _count(out: dict, owner: str, kind: str, op: str) -> None:
    out.setdefault(owner, {}).setdefault(kind, [0, 0, 0])[_OPS.index(op)] += 1


def size_jumps(added: dict[str, tuple], removed: dict[str, tuple]) -> list[dict]:
    """Hero model files whose size moved SIZE_JUMP times or more: [{'path', 'old', 'new'}] (bytes)."""
    out = []
    for path in sorted(added.keys() & removed.keys()):
        if not (path.startswith('models/heroes') and path.endswith(MODEL_EXT)):
            continue
        old, new = removed[path][1], added[path][1]
        if old > 0 and new > 0 and max(old, new) / min(old, new) >= SIZE_JUMP:
            out.append({'path': path, 'old': old, 'new': new})
    return out


def model_owners(heroes_vdata: str) -> dict[str, str]:
    """model folder (without a "_v2") -> the hero whose model lives there; the first hero to name a folder keeps it.
    A hero's code name maps to it too (`nurse` -> hero_nurse): particle and sound folders use it."""
    out: dict[str, str] = {}
    names: dict[str, str] = {}
    hero = None
    for line in heroes_vdata.splitlines():
        m = _HERO_BLOCK.match(line)
        if m:
            hero = m.group(1)
            names.setdefault(hero[len('hero_'):], hero)
            continue
        m = _HERO_MODEL.search(line)
        if m and hero:
            out.setdefault(_REDO.sub('', m.group(1)), hero)
    return {**names, **out}       # a model folder named after another hero's code name stays the model's


_CONVAR_HEAD = re.compile(r'^(\S+) (.*?) \(([^)]*)\)\s*$')


def parse_convars(text: str) -> dict[str, dict]:
    result: dict[str, dict] = {}
    cur = None
    for line in text.splitlines():
        if not line.strip():
            cur = None
            continue
        if line.startswith('\t') and cur:
            desc = line.strip()
            if desc != '<no description>':
                result[cur]['desc'] = (result[cur].get('desc', '') + ' ' + desc).strip()
            continue
        m = _CONVAR_HEAD.match(line)
        if m:
            cur = m.group(1)
            result[cur] = {'value': m.group(2), 'flags': m.group(3)}
    return result


def convar_diff(prev: str, cur: str) -> list[dict]:
    a_txt = tracker.read(prev, tracker.CONVARS) or ''
    b_txt = tracker.read(cur, tracker.CONVARS) or ''
    a, b = parse_convars(a_txt), parse_convars(b_txt)
    out = []
    for name in sorted(a.keys() | b.keys()):
        if not name.startswith(('citadel_', 'dl_', 'deadlock_')):
            continue
        x, y = a.get(name), b.get(name)
        if x == y:
            continue
        if x is None:
            out.append({'name': name, 'op': 'add', 'new': y['value'], 'flags': y['flags'], 'desc': y.get('desc')})
        elif y is None:
            out.append({'name': name, 'op': 'remove', 'old': x['value'], 'flags': x['flags']})
        elif x['value'] != y['value']:
            out.append({'name': name, 'op': 'change', 'old': x['value'], 'new': y['value'], 'flags': y['flags'], 'desc': y.get('desc')})
        elif x.get('desc') != y.get('desc'):
            out.append({'name': name, 'op': 'desc', 'old': x.get('desc'), 'new': y.get('desc'), 'flags': y['flags']})
    return out


def steam_inf(rev: str) -> dict:
    text = tracker.read(rev, tracker.STEAM_INF) or ''
    return dict(line.split('=', 1) for line in text.splitlines() if '=' in line)
