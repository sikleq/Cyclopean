"""Build pages: every tracked game build and exactly what its files changed."""
from __future__ import annotations

import json

from . import build_tech
from .common import (COSMETIC_KINDS, build_label, build_pages, cosmetics, esc, load_json, names_by_id, plural, page,
                     patch_title_text, pretty_id, slug, write)
from .cards import facing_scope
from .evidence import build_rows_scope, commit_url, diff_url, row_key, source_of
from .patches_pages import _changes_table, _loc_li, convar_li

ENTITY_LIMIT = 400          # cards shown open on a build page; the rest of a huge build (a new hero) folded


def _patch_of_build() -> dict[str, dict]:
    """{build record file name: patch index row}."""
    from . import archive
    out = {}
    for row in archive.index():
        for b in archive.patch(row['id'])['builds']:
            out[b['file']] = row
    return out


def _row_label(r: dict, stems: dict) -> str:
    """'Build 6404'; the second commit of one build number 'Build 6404 (#2)' (they read as duplicates)."""
    stem = stems.get(r['file'], '')
    nth = stem.rsplit('-', 1)[1] if r['build'] is not None and '-' in stem else ''
    return build_label(r['build']) + (f' (#{nth})' if nth else '')


HERO_KINDS = ('base body', 'cosmetic animation')     # their subjects are heroes; a sound set ('hero_poster') is not


def _cosmetic_subject(s: str, kind: str, rel: str) -> str:
    """A hero links to its page; a sound set or a code class reads as words."""
    if kind in HERO_KINDS and s.startswith('hero_'):
        return f'<a href="{rel}{slug("heroes.vdata", s)}">{esc(names_by_id().get(s) or pretty_id(s))}</a>'
    return esc(s.replace('_', ' '))


def cosmetics_section(build: int | None, rel: str) -> str:
    """Skin-system groundwork this build added or removed (pipeline/cosmetics.py)."""
    evs = [e for e in cosmetics()['events'] if e['build'] == build and build is not None]
    if not evs:
        return ''
    def by_name(e):              # heroes alphabetically by the name shown, not by internal id (hero_astro = Holliday)
        return sorted(e['subjects'], key=lambda s: (names_by_id().get(s) or pretty_id(s)).lower())
    rows = ''.join(f'<li><span class="lbl">{esc(COSMETIC_KINDS.get(e["kind"], e["kind"]))} · {esc(e["op"])}</span>'
                   # a list of names wraps (40 heroes on one line made build 6790's page 2646px wide at 1440)
                   f'<span class="vals wrap">{", ".join(_cosmetic_subject(s, e["kind"], rel) for s in by_name(e))}</span></li>'
                   for e in evs)
    return (f'<details class="collapsible section px-frame" open><summary>Cosmetics<span class="chip">{len(evs)}</span>'
            f'</summary><ul class="change-list">{rows}</ul></details>')


# an entity that came, came back or went is ONE row of its patch, under this path (pipeline: 'Added to the game files')
EVENT_PATH = {'added': '@add', 'returned': '@return', 'removed': '@remove'}


def _status(statuses: dict[str, str], e: dict, c: dict) -> str:
    """A build row's status in its patch (`notes_of`) when the notes left it out (render.NOT_IN_NOTES: the eye), else
    'raw' (quiet, as on an entity page: a mark on every row grew 5554's page 0.5 MB). A shared block's row by its
    targets' statuses — ONE for all of them, else quiet (build 5136: its blocks' targets were described, their
    'file:@shared:path' key hidden in another block) —, then by its own key; a new entity's field by the entity's one
    row; a change the patch does not hold (moved and moved back inside its window) is quiet."""
    from .render import NOT_IN_NOTES
    path, ev = c.get('path'), EVENT_PATH.get(e.get('status'))
    got = {statuses[k] for t in c.get('targets') or () for k in [row_key(e['file'], t, path)] if k in statuses}
    if not got:
        own = [row_key(e['file'], e['id'], path)] + ([row_key(e['file'], e['id'], ev)] if ev else [])
        got = next(({statuses[k]} for k in own if k in statuses), set())
    status = next(iter(got)) if len(got) == 1 else 'raw'
    return status if status in NOT_IN_NOTES else 'raw'


def page_entities(rec: dict, statuses: dict[str, str] | None = None) -> list[dict]:
    """The record's entities as the build page lists them (in the record's order, before ENTITY_LIMIT): their
    gameplay rows, an entity that came, went or came back as one event row. The eye on an entity page links into
    this list (evidence.build_anchors / build_rows), so both read it from here. Each row carries `src`, the record's
    own row (evidence.source_of: its anchor and source block), and its status in the patch (`statuses`: notes_of)."""
    from .cards import gameplay_rows, writes_rows
    ents = []
    for e in rec['entities']:
        def st(c: dict) -> str:
            return _status(statuses, e, c) if statuses else c.get('status', 'raw')
        g = [{**c, 'status': st(c), 'src': (e['file'], e['id'], c['path'], c.get('op'), c.get('old'), c.get('new'))}
             if c.get('path') else {**c, 'status': st(c)}
             for c in gameplay_rows(e['changes'])]
        if g or e['status'] in ('added', 'removed', 'returned'):
            # the event row has its path ('@remove'…, as in a patch record): without one `cards.is_noop` read "Removed
            # from game data" with no value as an empty removal and dropped it — 199 cards on 40 build pages were a
            # name over nothing (5315's Riptide, Scald; concept audit 2026-11-13)
            if e['status'] == 'added' and not g:
                g = [{'op': 'add', 'cat': 'mechanic', 'label': 'Added to game data', 'new_s': '', 'path': '@add'}]
            if e['status'] == 'returned':
                g = [{'op': 'add', 'cat': 'mechanic', 'label': 'Back in game data', 'new_s': '', 'path': '@return'}] + g
            if e['status'] == 'removed':
                g = [{'op': 'remove', 'cat': 'mechanic', 'label': 'Removed from game data', 'old_s': '',
                      'path': '@remove'}]
            g = [c if 'status' in c else {**c, 'status': st(c)} for c in g]
            # a card is never a name over nothing: rows that are all no-ops are no card (`cards.writes_rows`)
            if writes_rows(g, added=e['status'] == 'added'):
                ents.append({**e, 'changes': g})
    return ents


def shown_keys(ents: list[dict]):
    """The keys of the rows a build page writes with their source (cards.listed_rows: a row folded from several has
    none), one per row: two '@shared' blocks with one path give one key twice."""
    from .cards import listed_rows
    for e in ents:
        for c in listed_rows(e['changes'], added=e.get('status') == 'added'):
            raw = source_of(c)
            if raw:
                yield row_key(raw[0], raw[1], raw[2])


def unique_keys(ents: list[dict]) -> tuple[set[str], set[str]]:
    """(the keys a build page writes once — its row anchors, what an entity page's eye may land on: evidence.build_rows
    —, the keys it writes more than once — rows with a source and no anchor)."""
    from collections import Counter
    n = Counter(shown_keys(ents))
    return {k for k, v in n.items() if v == 1}, {k for k, v in n.items() if v > 1}


def notes_of(pid: str, build: int) -> dict[str, str]:
    """{row key: its status in `pid`} for the rows `build` carries (`_status` keeps the ones not in the notes). A shared
    edit's row is under its block's key and each target's; a key two rows give two statuses (two '@shared' blocks with
    one path) is left out."""
    from . import archive
    try:
        p = archive.patch(pid)
    except (OSError, KeyError):
        return {}
    seen: dict[str, set[str]] = {}
    for e in p.get('entities') or ():
        for c in e.get('changes') or ():
            if build not in (c.get('builds') or ()) or not c.get('path') or not c.get('key'):
                continue
            keys = [c['key']]
            if e['id'] == '@shared':
                keys += [row_key(e['file'], '@shared', c['path'])] + [f'{k}:{c["path"]}' for k in e.get('target_keys') or ()]
            for k in keys:
                seen.setdefault(k, set()).add(c.get('status', ''))
    return {k: next(iter(s)) for k, s in seen.items() if len(s) == 1}


def data_files(rec: dict) -> list[str]:
    """The data files whose entries this build changed, in the record's order."""
    return list(dict.fromkeys(e['file'] for e in rec.get('entities') or () if e.get('file')))


def split_limit(ents: list[dict]) -> tuple[list[dict], list[dict]]:
    """(the cards shown open, the rest folded under "More entities") of a build page: the first ENTITY_LIMIT, and a
    hero's later abilities with them (one card a hero: two would share its `c-<hero>` anchor)."""
    if len(ents) <= ENTITY_LIMIT:
        return ents, []
    head = ents[:ENTITY_LIMIT]

    def owner(e: dict) -> str | None:
        return e['id'] if e['file'] == 'heroes.vdata' and e['id'] != '@shared' else e.get('owner')
    heroes = {owner(e) for e in head} - {None}
    first = head + [e for e in ents[ENTITY_LIMIT:] if owner(e) in heroes]
    return first, [e for e in ents[ENTITY_LIMIT:] if owner(e) not in heroes]


OTHER_WORDS = {'technical': 'technical', 'visual': 'visual', 'audio': 'audio', 'ui': 'interface', 'meta': 'meta',
               'streetbrawl': 'Street Brawl'}
OTHER_CHARS = 160           # a long value (a particle path, a list of ids) is cut on the page


def other_rows(rec: dict) -> list[tuple[dict, dict]]:
    """(entity, row) of every data field the build moved that is no gameplay row (`cards.is_gameplay`): engine
    plumbing, looks, sounds, interface, test flags, Street Brawl's draft weights. A build that moved only these said
    "0 gameplay fields" and "Cosmetic fields changed: visual 1" (74 builds; concept audit 2026-11-13)."""
    from .cards import is_gameplay
    # an entity that came or went is its one event row (its every field is no news: a new hero's ~200)
    return [(e, c) for e in rec.get('entities') or () if e.get('status') not in ('added', 'removed')
            for c in e.get('changes') or () if not is_gameplay(c) and c.get('path')]


def _cut(v) -> str:
    s = '' if v is None else str(v)
    return s if len(s) <= OTHER_CHARS else s[:OTHER_CHARS] + '…'


def other_section(rows: list[tuple[dict, dict]]) -> str:
    """The "Other data fields" fold: each row as entity › label, its kind and old → new (names, never ids)."""
    from .patches_pages import _display_name
    items = []
    for e, c in rows:
        old, new = c.get('old_s', c.get('old')), c.get('new_s', c.get('new'))
        old = None if old in ('', '—') else old
        new = None if new in ('', '—') else new
        vals = (f'<span class="old">{esc(_cut(old))}</span><span class="arrow">→</span><span class="new">{esc(_cut(new))}</span>'
                if old is not None and new is not None else
                f'<span class="new">{esc(_cut(new))}</span>' if new is not None else
                f'<span class="old">{esc(_cut(old))}</span>' if old is not None else '')
        op = {'add': 'new', 'remove': 'removed'}.get(str(c.get('op')), '')
        items.append(f'<li><span class="chip">{esc(OTHER_WORDS.get(c.get("cat"), c.get("cat")))}</span>'
                     f'<span class="lbl">{esc(_display_name(e))} › {esc(c.get("label") or "")}'
                     f'{" " + op if op else ""}</span><span class="vals wrap">{vals}</span></li>')
    return (f'<details class="collapsible section px-frame"><summary>Other data fields<span class="chip">{len(rows)}'
            f'</span></summary><ul class="change-list">{"".join(items)}</ul></details>')


def convar_statuses(pid: str | None, build) -> dict[tuple[str, str], str]:
    """{(variable, op): its status in the update} of the console variables `build` moved (the patch's extras.convars,
    the rows the patch and Game pages mark)."""
    from . import archive
    if not pid or build is None:
        return {}
    try:
        cvs = (archive.patch(pid).get('extras') or {}).get('convars') or []
    except (OSError, KeyError):
        return {}
    return {(cv.get('name'), cv.get('op')): cv.get('status') for cv in cvs if cv.get('build') == build and cv.get('status')}


def build_page(rec: dict, patch: dict | None, prev_b, next_b) -> str:
    rel = '../'
    # each row with its status in the update it belongs to (the eye on what the notes left out) and its source
    statuses = notes_of(patch['id'], rec['build']) if patch and rec.get('build') is not None else {}
    ents = page_entities(rec, statuses)
    diff = ({f: diff_url(rec.get('build'), rec['commit'], f) for f in data_files(rec)} if rec.get('commit') else {})
    # the proof of every row: the tracker's own commit of this build (evidence.commit_url) and its diff of each data
    # file (a row's "file diff ↗" names one of these: `df-<file>`, scripts.js build-src)
    commit = (f' · <a href="{esc(commit_url(rec.get("build"), rec["commit"]))}" rel="noopener">tracker commit ↗</a>'
              if rec.get('commit') else '')
    if diff:
        commit += ' · file diffs: ' + ' '.join(f'<a id="df-{esc(f)}" href="{esc(u)}" rel="noopener">{esc(f)} ↗</a>'
                                               for f, u in diff.items())
    head = [f'<div class="crumbs"><a href="index.html">Builds</a> / {esc(build_label(rec["build"]))}</div>',
            f'<h1>{esc(build_label(rec["build"]))}</h1>',
            f'<div class="page-head"><div class="meta">Tracked {esc(rec["date"][:16].replace("T", " "))} UTC'
            f'{" · game build date " + esc(rec["version_date"]) if rec.get("version_date") else ""}'
            f'{" · part of <a href=" + chr(34) + rel + "patches/" + esc(patch["id"]) + ".html" + chr(34) + ">" + esc(patch_title_text(patch)) + "</a>" if patch else ""}'
            f'{commit}</div></div>']
    boxes = [
        ('', len(ents), 'entities with gameplay changes'),
        ('', sum(len(e['changes']) for e in ents), 'gameplay fields'),
        ('', len(rec.get('loc') or []), 'text changes'),
        ('', len(rec.get('convars') or []), 'console variables'),
    ]
    head.append('<div class="stat-strip">' + ''.join(
        f'<div class="stat-box px-frame"><div class="n">{n}</div><div class="l">{esc(l)}</div></div>' for _, n, l in boxes) + '</div>')
    body = head
    body.append('<div class="toolbar"><input type="search" placeholder="Hero, item…" data-search-target="#build-body tr[data-search]"></div>')
    body.append('<div id="build-body">')
    if ents:
        body.append('<section class="section"><h2>Gameplay data</h2>')
        # every row: its source and, its key written once, its anchor (evidence.row_source). Every entity is on the
        # page: past ENTITY_LIMIT the rest is folded, not cut (a new hero's build had "N more entities not shown")
        first, more = split_limit(ents)
        with build_rows_scope(diff, unique_keys(ents)[1]):
            body.append(_changes_table(first, rel))
            if more:
                body.append(f'<details class="collapsible section px-frame"><summary>More entities'
                            f'<span class="chip">{len(more)}</span></summary>{_changes_table(more, rel)}</details>')
        body.append('</section>')
    other = other_rows(rec)
    if other:
        body.append(other_section(other))
    if rec.get('loc'):
        # every text change, folded (they were cut at 500)
        rows = ''.join(_loc_li(x) for x in rec['loc'])
        body.append(f'<details class="collapsible section px-frame"><summary>Text changes<span class="chip">{len(rec["loc"])}</span></summary>'
                    f'<ul class="change-list">{rows}</ul></details>')
    if rec.get('convars'):
        # every variable, folded (cut at 400), with its status in the update — the eye where the notes left it out,
        # as the patch and Game pages mark it (2,124 rows had none)
        cv_status = convar_statuses(patch['id'] if patch else None, rec.get('build'))
        rows = ''.join(convar_li({**x, 'status': cv_status.get((x.get('name'), x.get('op')), x.get('status'))})
                       for x in rec['convars'])
        body.append(f'<details class="collapsible section px-frame"><summary>Console variables<span class="chip">{len(rec["convars"])}</span></summary>'
                    f'<ul class="change-list">{rows}</ul></details>')
    cos = cosmetics_section(rec.get('build'), rel)
    if cos:
        body.append(cos)
    body.append(build_tech.files_section(rec.get('assets'), rel))
    body.append(build_tech.protobuf_section(rec.get('protobuf'), rec.get('build'), rec.get('commit')))
    body.append(build_tech.strings_section(rec.get('strings'), rec.get('build'), rec.get('commit')))
    body.append(build_tech.dll_section(rec.get('build')))
    body.append('</div>')
    nav = []
    if prev_b:
        nav.append(f'<a class="px-btn" href="{esc(prev_b)}.html">← {esc(prev_b)}</a>')
    # any build in one step (owner 2026-11-13: "I can only press back"): the list loads from builds/list.json on first
    # use (scripts.js build-pick), so 900 pages do not carry 900 options each
    nav.append(f'<select class="build-pick" data-list="{LIST_JSON}" aria-label="Go to build">'
               f'<option selected>{esc(build_label(rec["build"]))}</option></select>')
    if next_b:
        nav.append(f'<a class="px-btn" href="{esc(next_b)}.html">{esc(next_b)} →</a>')
    body.append('<div class="flex build-nav">' + ''.join(nav) + '</div>')
    return page(build_label(rec['build']), ''.join(body), rel, 'builds', cls='column')     # its cards: one column


def code_only_rows(index: list[dict]) -> list[dict]:
    """Index rows of the builds that changed only code: the tracker's commit holds a version bump, so no record, but
    the binaries' functions changed (6828: 11 in server.dll; 48 builds had no page, 2026-11-01). Each page is its
    number, which no record has."""
    known = {r['build'] for r in index}
    return [{'build': int(b), 'commit': None, 'date': d['seen'], 'file': f'code-{b}', 'entities': []}
            for b, d in build_tech.dll_changes().items()
            if int(b) not in known and d.get('seen') and any(s['changed'] for s in d['dlls'].values())]


def index_page(index: list[dict], patch_of: dict[str, dict], stems: dict[str, str] | None = None) -> str:
    stems = stems or build_pages()
    rows = []
    for r in reversed(index):
        f = r.get('fields', {})
        gp = f.get('balance', 0) + f.get('mechanic', 0) + f.get('availability', 0)
        code = sum(s['changed'] for s in (build_tech.dll_changes().get(str(r['build'])) or {}).get('dlls', {}).values())
        # a build whose only changes are files, protocol, strings or code is listed too (6810 was missing)
        if not (gp or r.get('loc') or r.get('convars') or r.get('added') or r.get('removed') or r.get('protobuf')
                or r.get('strings') or code or any(r.get('assets', {}).values())):
            continue
        patch = patch_of.get(r['file'])
        ptxt = f'<small>{esc(patch_title_text(patch))}</small>' if patch else ''
        chips = []
        if gp:
            chips.append(f'<span class="chip">{gp} gameplay</span>')
        if r.get('added'):
            chips.append(f'<span class="chip">+{r["added"]} new</span>')
        if r.get('removed'):
            chips.append(f'<span class="chip">−{r["removed"]} removed</span>')
        if r.get('loc'):
            chips.append(f'<span class="chip">{r["loc"]} text</span>')
        if r.get('convars'):
            chips.append(f'<span class="chip">{plural(r["convars"], "cvar")}</span>')
        if r.get('protobuf'):
            chips.append(f'<span class="chip">{r["protobuf"]} protobuf</span>')
        if code:
            chips.append(f'<span class="chip">{plural(code, "function")}</span>')
        rows.append(f'<li data-search="{r["build"]} {esc(r["date"][:10])}"><span class="date">{esc(r["date"][:10])}</span>'
                    f'<span><a class="ttl" href="{esc(stems[r["file"]])}.html">{esc(_row_label(r, stems))}</a>{ptxt}</span>'
                    f'<span class="nums">{"".join(chips)}</span></li>')
    body = ('<h1>Builds</h1>'
            '<div class="toolbar"><input type="search" placeholder="Build number or date…" data-search-target=".timeline > li"></div>'
            f'<ul class="timeline px-frame">{"".join(rows)}</ul>')
    return page('Builds', body, '../', 'builds')


def build_all() -> int:
    index = load_json('builds/index.json')
    patch_of = _patch_of_build()
    code_only = code_only_rows(index)
    stems = {**build_pages(), **{r['file']: str(r['build']) for r in code_only}}
    rows = sorted(index + code_only, key=lambda r: r['date'])
    pages = [stems[r['file']] for r in rows]
    n = 0
    for i, r in enumerate(rows):
        rec = r if r['file'].startswith('code-') else load_json(f'builds/{r["file"]}')
        prev_b = pages[i - 1] if i > 0 else None
        next_b = pages[i + 1] if i + 1 < len(pages) else None
        with facing_scope():                 # a record is read once: its rows leave the memo with the page
            write(f'builds/{pages[i]}.html', build_page(rec, patch_of.get(r['file']), prev_b, next_b))
        n += 1
    write('builds/index.html', index_page(rows, patch_of, stems))
    write(f'builds/{LIST_JSON}', json.dumps(pick_list(rows, stems, patch_of), ensure_ascii=False, separators=(',', ':')))
    return n


LIST_JSON = 'list.json'


def pick_list(rows: list[dict], stems: dict[str, str], patch_of: dict[str, dict]) -> list[list[str]]:
    """The build picker's options, newest first: [page stem, label] ('6861, 2026-11-11: Ranked - Beta Season 2'; no
    separator dots, owner 2026-10-29)."""
    out = []
    for r in reversed(rows):
        patch = patch_of.get(r['file'])
        label = f'{stems[r["file"]]}, {r["date"][:10]}' + (f': {patch["title"]}' if patch and patch.get('title') else '')
        out.append([stems[r['file']], label])
    return out
