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


def asset_category(path: str) -> str:
    for prefix, cat in ASSET_CATEGORIES:
        if path.startswith(prefix):
            return cat
    return 'other'


def asset_diff(prev: str, cur: str) -> dict | None:
    out = tracker.git('diff', '-U0', '--no-color', prev, cur, '--', tracker.ASSET_LIST)
    removed: dict[str, str] = {}
    added: dict[str, str] = {}
    for line in out.splitlines():
        m = _ASSET_LINE.match(line)
        if not m:
            continue
        sign, path, crc = m.group(1), m.group(2), m.group(3)
        (added if sign == '+' else removed)[path] = crc
    if not added and not removed:
        return None
    counts: dict[str, dict[str, int]] = defaultdict(lambda: {'added': 0, 'removed': 0, 'modified': 0})
    notable: dict[str, list] = defaultdict(list)
    heroes_touched: dict[str, set] = defaultdict(set)
    for path in added.keys() | removed.keys():
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
    return {
        'counts': dict(sorted(counts.items())),
        'notable': {k: sorted(v, key=lambda x: x[1]) for k, v in notable.items()},
        'hero_models': {k: sorted(v) for k, v in sorted(heroes_touched.items())},
    }


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
