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
    jumps = size_jumps(added, removed)
    if jumps:
        owners = model_owners(tracker.read(cur, tracker.SCRIPTS + 'heroes.vdata') or '')
        for j in jumps:
            m = _HERO_DIR.match(j['path'])
            j['hero'] = owners.get(_REDO.sub('', m.group(1))) if m else None
        out['model_sizes'] = jumps
    return out


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
    """model folder (without a "_v2") -> the hero whose model lives there; the first hero to name a folder keeps it."""
    out: dict[str, str] = {}
    hero = None
    for line in heroes_vdata.splitlines():
        m = _HERO_BLOCK.match(line)
        if m:
            hero = m.group(1)
            continue
        m = _HERO_MODEL.search(line)
        if m and hero:
            out.setdefault(_REDO.sub('', m.group(1)), hero)
    return out


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
