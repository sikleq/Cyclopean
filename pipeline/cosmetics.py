"""Cosmetics groundwork in the game files: what a skin system needs, build by build.

Valve ships cosmetics work long before it is announced (2026-10-02: news of "underwear textures"
for Paige and Victor — the files had them since City Never Sleeps, build 6711). Read from the
tracker's packed-file list and schema dumps, never from the client:
  base body           models/heroes*/<hero>/…basebody…   the body a skin is put on
  cosmetic animation  animgraphs/…/hero_cosmetic.vnmgraph+<hero>
  cosmetic sounds     sounds/cosmetics/<set>/
  cosmetic code       DumpSource2/schemas/server/CCitadel_Cosmetic{Item,Ability}_<Name>.h

    python -m pipeline.cosmetics   ->  data/cosmetics.json
"""
from __future__ import annotations

import json
import re

from . import cache, loc, tracker

OUT = tracker.ROOT / 'data' / 'cosmetics.json'
SCHEMAS = 'DumpSource2/schemas/server/'

ASSET_KINDS = (
    ('base body', re.compile(r'^models/heroes(?:_wip)?/([^/]+)/\S*basebody', re.I)),
    ('cosmetic animation', re.compile(r'^animgraphs/animgraph2/hero/hero_cosmetic\.vnmgraph\+([a-z0-9_]+)\.vnmgraph_c$')),
    ('cosmetic sounds', re.compile(r'^sounds/cosmetics/([^/]+)/')),
)
_PICK = '|'.join(('basebody', 'hero_cosmetic', 'sounds/cosmetics/'))
_DIFF_LINE = re.compile(r'^([+-])(\S+) CRC:')
_SCHEMA = re.compile(r'^CCitadel_Cosmetic(?:Item|Ability)_([A-Za-z]+?)(?:_VData)?\.h$')
_COMMIT = '\x01'


_MODEL = re.compile(r'models/heroes[a-z_]*/([a-z0-9_]+)/(?:[a-z0-9_]+/)*([a-z0-9_]+)\.vmdl')


def hero_codes(heroes: dict, names: dict[str, str] | None = None) -> dict[str, str]:
    """model folder / model file / id word / game name -> hero id: 'bookworm' (Paige's folder),
    'archer' (Grey Talon's, under heroes_staging), 'mo_krill' (the name the cosmetic graphs use)."""
    out: dict[str, str] = {}
    for hid, h in heroes.items():
        if not hid.startswith('hero_') or not isinstance(h, dict):
            continue
        out.setdefault(hid[5:], hid)
        m = _MODEL.search(str(h.get('m_strModelName') or ''))
        if m:
            out.setdefault(m.group(1), hid)
            out.setdefault(m.group(2), hid)
        name = (names or {}).get(hid)
        if name:
            out.setdefault(re.sub(r'[^a-z0-9]+', '_', name.lower().replace('&', '')).strip('_'), hid)
    return out


def subject_of(code: str, codes: dict[str, str]) -> str:
    """'priest_crossbow' -> hero_priest; an unknown code stays itself."""
    parts = code.split('_')
    for n in range(len(parts), 0, -1):
        hid = codes.get('_'.join(parts[:n]))
        if hid:
            return hid
    return code


def _commits() -> dict[str, tracker.Build]:
    return {b.commit: b for b in tracker.builds() if b.repo == 'main'}


def asset_events(codes: dict[str, str], by_commit: dict[str, tracker.Build]) -> list[dict]:
    out = tracker.git('log', '--reverse', '-G', _PICK, '-p', '-U0', '--no-color', f'--format={_COMMIT}%H',
                      '--', tracker.ASSET_LIST)
    events = []
    for chunk in out.split(_COMMIT)[1:]:
        commit, _, body = chunk.partition('\n')
        b = by_commit.get(commit.strip())
        if b is None:
            continue
        seen: dict[str, dict[str, int]] = {}         # path -> {+: n, -: n}
        for line in body.splitlines():
            m = _DIFF_LINE.match(line)
            if m:
                seen.setdefault(m.group(2), {}).setdefault(m.group(1), 0)
                seen[m.group(2)][m.group(1)] += 1
        groups: dict[tuple[str, str], dict] = {}
        for path, ops in seen.items():
            op = 'modified' if '+' in ops and '-' in ops else 'added' if '+' in ops else 'removed'
            for kind, rx in ASSET_KINDS:
                km = rx.match(path)
                if km:
                    who = km.group(1) if kind == 'cosmetic sounds' else subject_of(km.group(1), codes)
                    g = groups.setdefault((kind, op), {'subjects': set(), 'files': 0})
                    g['subjects'].add(who)
                    g['files'] += 1
                    break
        for (kind, op), g in sorted(groups.items()):
            events.append({'build': b.build, 'date': b.date[:10], 'commit': b.commit[:8], 'kind': kind, 'op': op,
                           'subjects': sorted(g['subjects']), 'files': g['files']})
    return events


def schema_events(by_commit: dict[str, tracker.Build]) -> list[dict]:
    out = tracker.git('log', '--reverse', '--diff-filter=AD', '--name-status', f'--format={_COMMIT}%H',
                      '--', SCHEMAS + '*Cosmetic*')
    events = []
    for chunk in out.split(_COMMIT)[1:]:
        commit, _, body = chunk.partition('\n')
        b = by_commit.get(commit.strip())
        if b is None:
            continue
        names: dict[str, set[str]] = {}
        for line in body.splitlines():
            st, _, path = line.partition('\t')
            m = _SCHEMA.match(path.rsplit('/', 1)[-1]) if path else None
            if m:
                names.setdefault('added' if st == 'A' else 'removed', set()).add(m.group(1))
        # a class renamed Item -> Ability in one build is the same feature: added and removed cancel
        both = names.get('added', set()) & names.get('removed', set())
        for op in ('added', 'removed'):
            left = sorted(names.get(op, set()) - both)
            if left:
                events.append({'build': b.build, 'date': b.date[:10], 'commit': b.commit[:8], 'kind': 'cosmetic code',
                               'op': op, 'subjects': left, 'files': len(left)})
    return events


def build() -> dict:
    head = tracker.git('rev-parse', 'HEAD').strip()
    heroes = cache.vdata(head, tracker.SCRIPTS + 'heroes.vdata')
    tok = loc.tokens(head)
    codes = hero_codes(heroes, {hid: loc.plain(loc.hero_name(tok, hid)) for hid in heroes if hid.startswith('hero_')})
    by_commit = _commits()
    events = sorted(asset_events(codes, by_commit) + schema_events(by_commit),
                    key=lambda e: (e['date'], e['build'] or 0, e['kind'], e['op']))
    # what each hero has in the files now: kinds added and not removed since
    now: dict[str, set[str]] = {}
    for e in events:
        if e['kind'] in ('base body', 'cosmetic animation'):
            for s in e['subjects']:
                (now.setdefault(s, set()).add if e['op'] != 'removed' else now.setdefault(s, set()).discard)(e['kind'])
    data = {'events': events, 'heroes': {h: sorted(k) for h, k in sorted(now.items()) if k}}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    print(f"{len(events)} cosmetics events -> {OUT}")
    return data


if __name__ == '__main__':
    build()
