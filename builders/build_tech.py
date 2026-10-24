"""The build page's technical sections: which hero's files changed, network / game-coordinator messages
(protobuf), text strings of the game's binaries, and functions of client.dll / server.dll.

Owner (2026-10-24): only what tells something. No full path lists (thousands of files a build, as on datavpk.com),
no steam.inf or manifests: files are counted per hero or unit, paths are written only for maps.
"""
from __future__ import annotations

from functools import lru_cache

from .common import DATA, esc, load_json, names_by_id, pretty_id, slug
from .evidence import path_diff_url

PROTO_PREFIX = 'Protobufs/'
STRING_PATHS = {'client': 'game/citadel/bin/win64/client_strings.txt',
                'server': 'game/citadel/bin/win64/server_strings.txt',
                'host': 'game/citadel/bin/win64/host_strings.txt',
                'engine2': 'game/bin/win64/engine2_strings.txt'}
KIND_ORDER = ('model', 'model parts', 'animation', 'animgraph', 'particles', 'sounds', 'voice')
KIND_WORDS = {'animgraph': 'animation graph', 'voice': 'voice lines'}
PROTO_OPS = {'added': 'new', 'removed': 'removed', 'changed': 'changed'}
STRING_CHARS = 160          # a long description string is cut on the page


def counts(t: list[int]) -> str:
    """[added, removed, modified] -> '+2 −1 ~9' (zeros left out)."""
    return ' '.join(f'{s}{n}' for s, n in zip(('+', '−', '~'), t) if n)


def _section(title: str, n: int, inner: str, open_: bool = False) -> str:
    return (f'<details class="collapsible section px-frame"{" open" if open_ else ""}><summary>{esc(title)}'
            f'<span class="chip">{n}</span></summary>{inner}</details>')


def _owner(owner: str, rel: str) -> str:
    if owner.startswith('hero_') and owner in names_by_id():
        return f'<a href="{rel}{slug("heroes.vdata", owner)}">{esc(names_by_id()[owner])}</a>'
    return esc(pretty_id(owner))


def files_section(assets: dict | None, rel: str) -> str:
    """Changed files per hero / unit; a shared animation graph changed for all heroes is one row; maps by path;
    the category totals as one line."""
    if not assets:
        return ''
    owners = dict(assets.get('owners') or {})
    shared = owners.pop('*', {})
    names = names_by_id()

    def key(o: str) -> tuple:
        return (not o.startswith('hero_'), (names.get(o) or pretty_id(o)).lower())
    rows = []
    for graph, t in sorted(shared.items()):
        rows.append(f'<li><span class="lbl">All heroes</span><span class="vals wrap">'
                    f'{esc(graph.removeprefix("graph ").replace("_", " "))} animation graph {counts(t)}</span></li>')
    for o in sorted(owners, key=key):
        kinds = owners[o]
        parts = [f'{esc(KIND_WORDS.get(k, k))} {counts(kinds[k])}'
                 for k in sorted(kinds, key=lambda k: KIND_ORDER.index(k) if k in KIND_ORDER else 99)]
        rows.append(f'<li><span class="lbl">{_owner(o, rel)}</span><span class="vals wrap">{" · ".join(parts)}</span></li>')
    for op, path in (assets.get('notable') or {}).get('map', ()):
        rows.append(f'<li><span class="lbl"><code>{esc(path)}</code></span><span class="vals">map {esc(op)}</span></li>')
    total = assets.get('counts') or {}
    line = ', '.join(f'{esc(cat.replace("_", " "))} {counts([t["added"], t["removed"], t["modified"]])}'
                     for cat, t in total.items())
    n = sum(sum(t.values()) for t in total.values())
    return _section('Game files', n, (f'<ul class="change-list">{"".join(rows)}</ul>' if rows else '')
                    + (f'<p class="muted">All files: {line}.</p>' if line else ''), open_=bool(rows))


def protobuf_section(rows: list[dict] | None, build, commit: str | None) -> str:
    """Messages of the game's network and game-coordinator protocol: fields and enum values added, removed,
    changed; a whole message added or removed is one row."""
    if not rows:
        return ''
    items = []
    for r in rows:
        where = esc(r['scope'])
        if commit:
            where = (f'<a href="{esc(path_diff_url(build, commit, PROTO_PREFIX + r["file"]))}" rel="noopener">'
                     f'{where}</a>')
        if 'item' not in r:
            what = f'message {PROTO_OPS[r["op"]]}'
        elif r['op'] == 'changed':
            what = f'<code>{esc(r["old"])}</code> → <code>{esc(r["new"])}</code>'
        else:
            what = f'{PROTO_OPS[r["op"]]}: <code>{esc(r.get("new") or r.get("old"))}</code>'
        items.append(f'<li><span class="lbl">{where}</span><span class="vals wrap">{what}</span></li>')
    return _section('Protobuf messages', len(rows), f'<ul class="change-list">{"".join(items)}</ul>', open_=True)


def strings_section(mods: dict | None, build, commit: str | None) -> str:
    """Text strings that appeared in or left each game binary (the first and most telling of each side)."""
    if not mods:
        return ''
    items = []
    total = 0
    for mod, d in mods.items():
        name = f'{mod}.dll'
        if commit and mod in STRING_PATHS:
            name = f'<a href="{esc(path_diff_url(build, commit, STRING_PATHS[mod]))}" rel="noopener">{name}</a>'
        n_mod = d['n_added'] + d['n_removed']
        total += n_mod
        items.append(_head(name, f'+{d["n_added"]} −{d["n_removed"]}'))
        for side, word in (('added', 'new'), ('removed', 'removed')):
            items += [_line(f'<code>{esc(s[:STRING_CHARS])}</code>', word) for s in d[side]]
        more = n_mod - len(d['added']) - len(d['removed'])
        if more:
            items.append(_line(f'<span class="muted">and {more} more</span>', ''))
    return _section('Strings in the binaries', total, f'<ul class="change-list">{"".join(items)}</ul>')


def _head(lbl: str, vals: str) -> str:
    """A binary's own row above its list."""
    return f'<li><span class="lbl"><b>{lbl}</b></span><span class="vals">{esc(vals)}</span></li>'


def _line(lbl: str, vals: str) -> str:
    """One string or function: left, one per row (a comma run right-aligned read as a wall, 2026-10-24)."""
    return f'<li><span class="lbl">{lbl}</span><span class="vals">{esc(vals)}</span></li>'


@lru_cache(maxsize=None)
def dll_changes() -> dict:
    """data/dll_changes.json (tools/import_dll_summary.py); {} before the first import."""
    return load_json('dll_changes.json') if (DATA / 'dll_changes.json').exists() else {}


def dll_section(build) -> str:
    """Functions of client.dll / server.dll whose code changed, by the name their strings or class give them."""
    d = dll_changes().get(str(build)) if build is not None else None
    if not d:
        return ''
    items = []
    for mod, s in d['dlls'].items():
        # only functions whose code changed: "added / removed" are mostly the same functions moved to another
        # address by the linker (6810's client.dll: +1473 −1473), not new code
        if not s['changed']:
            continue
        items.append(_head(f'{esc(mod)}.dll', f'{s["changed"]} changed'))
        items += [_line(f'<code>{esc(f["name"])}</code>', '') for f in s['functions']]
        if s.get('unnamed'):
            items.append(_line(f'<span class="muted">and {s["unnamed"]} without a name</span>', ''))
    if d.get('other'):
        items.append(_head('Other binaries changed', ', '.join(m + '.dll' for m in d['other'])))
    n = sum(s['changed'] for s in d['dlls'].values())
    return _section('Code of the binaries', n, f'<ul class="change-list">{"".join(items)}</ul>') if items else ''
