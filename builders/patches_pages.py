"""Patch pages: official notes annotated with the data, plus hidden changes."""
from __future__ import annotations

import re

from .common import build_href, esc, load_json, mark, page, write

GAMEPLAY = ('balance', 'mechanic', 'availability')


def _counts_html(p: dict) -> str:
    c = p.get('counts', {})
    lc = p.get('line_counts', {})
    if not p.get('sections'):
        boxes = [('hidden', c.get('unannounced', 0), 'changes in the files — no official numbers published')]
    else:
        boxes = [
            ('documented', c.get('documented', 0), 'changes with exact numbers in the notes'),
            ('described', c.get('described', 0), 'changes covered by a general line'),
            ('hidden', c.get('hidden', 0), 'changes missing from the notes'),
            ('mismatch', lc.get('mismatch', 0), 'note lines that disagree with the files'),
            ('fix', lc.get('fix', 0), 'bug fixes listed'),
        ]
    return '<div class="stat-strip">' + ''.join(
        f'<div class="stat-box px-frame {cls}"><div class="n">{n}</div><div class="l">{esc(lbl)}</div></div>'
        for cls, n, lbl in boxes) + '</div>'


def _notes_table(p: dict, change_by_key: dict) -> str:
    rows = []
    for s in p['sections']:
        rows.append(f'<tr class="sec"><td colspan="3">{esc(s["title"])}</td></tr>')
        rows.extend(_note_row(ln, change_by_key) for ln in s['lines'])
    return f'<table class="notes">{"".join(rows)}</table>'


def _note_row(ln: dict, change_by_key: dict) -> str:
    """status | the official line | what the game files say."""
    st = ln['status']
    m = mark(st) if st in ('documented', 'rounded', 'described', 'mismatch', 'fix') else ''
    files = ''
    if st in ('mismatch', 'rounded') and ln.get('data'):
        files = f'<span class="v">{esc(ln["data"][0])}</span><span class="arrow">→</span><span class="v">{esc(ln["data"][1])}</span>'
        files = ('files: ' if st == 'mismatch' else 'exact: ') + files
    elif st == 'documented' and ln.get('changes'):
        c = change_by_key.get(ln['changes'][0])
        if c:
            files = (f'{esc(c.get("ent_name", ""))} · {esc(c["label"])}: <span class="v">{esc(c["old_s"])}</span>'
                     f'<span class="arrow">→</span><span class="v">{esc(c["new_s"])}</span>')
    elif st == 'described' and ln.get('changes'):
        items = [change_by_key.get(k) for k in ln['changes'][:60]]
        lis = ''.join(f'<li>{esc(c.get("ent_name", ""))} · {esc(c["label"])}: {esc(c["old_s"])} → {esc(c["new_s"])}</li>'
                      for c in items if c)
        more = len(ln['changes']) - 60
        files = (f'<details><summary>{len(ln["changes"])} exact values</summary><ul>{lis}</ul>'
                 f'{"<span class=muted>+" + str(more) + " more</span>" if more > 0 else ""}</details>')
    return f'<tr class="st-{esc(st)}"><td class="st">{m}</td><td>{esc(ln["text"])}</td><td class="fv">{files}</td></tr>'


def _changes_table(ents: list[dict], rel: str) -> str:
    """All gameplay changes: one table, grouped by hero (with its abilities), then items, units, rules."""
    from .common import entity_icon, hero_icon
    from .render import sort_changes, tag_html, vals_html
    heroes = {e['id']: e for e in ents if e['file'] == 'heroes.vdata' and e['id'] != '@shared'}
    by_owner: dict[str, list] = {}
    rest = []
    for e in ents:
        if e['file'] == 'heroes.vdata' and e['id'] != '@shared':
            by_owner.setdefault(e['id'], []).insert(0, e)
        elif e.get('owner') and e.get('kind') in ('ability', 'weapon', 'melee'):
            by_owner.setdefault(e['owner'], []).append(e)
        else:
            rest.append(e)
    order_rest = {'shared': 0, 'item': 1, 'building': 2, 'trooper': 3, 'neutral': 4, 'unit': 5}
    rest.sort(key=lambda e: (order_rest.get(e.get('kind'), 9), e.get('name') or ''))
    groups = []
    for hid in sorted(by_owner, key=lambda h: (heroes.get(h, {}).get('name') or h).lower()):
        hname = heroes.get(hid, {}).get('name') or next((x.get('owner_name') for x in by_owner[hid] if x.get('owner_name')), hid)
        groups.append((hname, hero_icon(hid, rel), by_owner[hid]))
    for e in rest:
        groups.append((e.get('name') or e['id'], entity_icon(e['file'], e['id'], e.get('kind', ''), rel), [e]))
    trs = []
    for gname, gicon, members in groups:
        n_h = sum(1 for e in members for c in e['changes'] if c.get('status') == 'hidden')
        icon_html = f'<img class="px gi" src="{esc(gicon)}" alt="">' if gicon else ''
        hid_chip = f' <span class="chip">{mark("hidden")}{n_h}</span>' if n_h else ''
        trs.append(f'<tr class="ph" data-search="{esc(gname.lower())}"><td colspan="5"><span class="t">{icon_html}{esc(gname)}</span>{hid_chip}</td></tr>')
        for e in members:
            scope = e.get('name') or e['id']
            if e.get('targets'):
                scope += f' ({len(e["targets"])})'
            for c in sort_changes(e['changes']):
                st = c.get('status', 'hidden')
                trs.append(f'<tr class="ch st-{esc(st)}" data-search="{esc(gname.lower())}"><td class="st">{mark(st)}</td>'
                           f'<td class="sc">{esc(scope)}</td><td class="tg">{tag_html(c)}</td>'
                           f'<td>{esc(c.get("label"))}</td><td class="ov">{vals_html(c)}</td></tr>')
    return f'<table class="hist">{"".join(trs)}</table>'


def _key_changes(p: dict, rel: str) -> str:
    rows = p.get('key_changes') or []
    if not rows:
        return ''
    from .render import tag_html, vals_html
    trs = ''.join(f'<tr class="ch"><td class="sc">{esc(r["name"])}</td><td class="tg">{tag_html(r["change"])}</td>'
                  f'<td>{esc(r["change"]["label"])}</td><td class="ov">{vals_html(r["change"])}</td></tr>' for r in rows)
    return f'<h2>Biggest changes</h2><table class="hist px-frame">{trs}</table>'


def _generated_notes(p: dict) -> str:
    """Valve-style notes written from the files for updates without official numbers."""
    lines = []
    for e in p['entities']:
        for c in e['changes']:
            if c['cat'] in GAMEPLAY and c.get('sentence'):
                lines.append(c['sentence'])
    if not lines:
        return ''
    lis = ''.join(f'<li>{esc(s)}</li>' for s in lines[:1500])
    more = f'<p class="muted">+{len(lines) - 1500} more lines.</p>' if len(lines) > 1500 else ''
    return (f'<h2>Patch notes written from the files</h2><p class="muted">Valve published no numbers for this update; '
            f'every line below is read from the game files.</p><ul class="gen-notes cols-2">{lis}</ul>{more}')


def _bar(c: dict) -> str:
    total = sum(c.get(k, 0) for k in ('documented', 'described', 'hidden')) or 1
    seg = ''.join(f'<span class="{cls}" style="width:{c.get(k, 0) / total * 100:.1f}%"></span>'
                  for k, cls in (('documented', 'b-doc'), ('described', 'b-des'), ('hidden', 'b-hid')))
    return f'<div class="bar">{seg}</div>'


def patch_page(p: dict, prev: dict | None, nxt: dict | None) -> str:
    rel = '../'
    change_by_key = {}
    for e in p['entities']:
        for c in e['changes']:
            c['ent_name'] = e.get('name')
            change_by_key[c['key']] = c
    parts = [f'<div class="crumbs"><a href="index.html">Patches</a> / {esc(p["date"])}</div>',
             f'<h1>{esc(p["title"])}</h1>']
    builds = ', '.join(f'<a href="{build_href(b["file"], rel)}">{b["build"]}</a>' for b in p['builds'][:30])
    link_text = 'official notes' if p.get('source') != 'announcement' else 'official announcement'
    src = f' · <a href="{esc(p["url"])}" rel="noopener">{link_text}</a>' if p.get('url') else ''
    parts.append(f'<div class="meta muted">{esc(p["date"])}{src} · builds: {builds or "—"}</div>')
    parts.append(_counts_html(p))

    gameplay = []
    for e in p['entities']:
        ch = [c for c in e['changes'] if c['cat'] in GAMEPLAY]
        if ch:
            gameplay.append({**e, 'changes': ch})
    names = {e['id']: e.get('name') for e in p['entities'] if e['file'] == 'heroes.vdata'}
    for e in gameplay:
        if e.get('owner'):
            e['owner_name'] = names.get(e['owner'])
    ex = p.get('extras', {})
    tabs = []
    if p['sections']:
        tabs.append(('notes', 'Patch notes', sum(len(s['lines']) for s in p['sections']), _notes_table(p, change_by_key)))
    else:
        tabs.append(('notes', 'From the files', sum(len(e['changes']) for e in gameplay),
                     _key_changes(p, rel) + _generated_notes({**p, 'entities': gameplay})))
    changes_panel = ('<div class="toolbar"><button class="px-btn" data-toggle-class="only-hidden" data-target="#changes">'
                     'Only hidden</button><span class="sep"></span><input type="search" placeholder="Hero, item…" '
                     'data-search-target="#changes tr[data-search]"></div>' + _changes_table(gameplay, rel))
    tabs.append(('changes', 'All changes', sum(len(e['changes']) for e in gameplay), changes_panel))
    extra_parts = _extras_parts(p, rel)
    for key, label, count, html in extra_parts:
        tabs.append((key, label, count, html))
    parts.append('<div class="tabs toolbar">' + ''.join(
        f'<button class="px-btn{" on" if i == 0 else ""}" data-tab="{k}">{esc(lbl)}<span class="count">{n}</span></button>'
        for i, (k, lbl, n, _) in enumerate(tabs)) + '</div>')
    for i, (k, _, _, html) in enumerate(tabs):
        parts.append(f'<div class="tab-panel{" on" if i == 0 else ""}" id="{k}">{html}</div>')
    nav = []
    if prev:
        nav.append(f'<a class="px-btn" href="{esc(prev["id"])}.html">← {esc(prev["title"])}</a>')
    if nxt:
        nav.append(f'<a class="px-btn" href="{esc(nxt["id"])}.html">{esc(nxt["title"])} →</a>')
    parts.append('<div class="flex">' + ''.join(nav) + '</div>')
    return page(p['title'], ''.join(parts), rel, 'patches',
                description=f'Deadlock {p["title"]}: official notes vs game files')


def _extras_parts(p: dict, rel: str) -> list[tuple[str, str, int, str]]:
    """Secondary tabs: text/tooltips, console variables, packed game files."""
    ex = p.get('extras', {})
    out = []
    loc_rows = ex.get('loc', [])
    if loc_rows:
        more = ex.get('loc_total', len(loc_rows)) - len(loc_rows)
        more_s = f'<p class="muted">+{more} more on the build pages.</p>' if more > 0 else ''
        out.append(('text', 'Text & tooltips', ex.get('loc_total', len(loc_rows)),
                    f'<ul class="change-list px-frame">{"".join(_loc_li(x) for x in loc_rows)}</ul>{more_s}'))
    cv = ex.get('convars', [])
    if cv:
        out.append(('console', 'Console variables', ex.get('convars_total', len(cv)),
                    f'<ul class="change-list px-frame">{"".join(convar_li(x) for x in cv)}</ul>'))
    assets = ex.get('assets') or {}
    totals = assets.get('counts', {})
    if totals:
        heroes = assets.get('hero_models', [])
        rows = ''.join(f'<tr><td>{esc(cat)}</td><td class="v">+{t["added"]}</td><td class="v">−{t["removed"]}</td>'
                       f'<td class="v">~{t["modified"]}</td></tr>' for cat, t in sorted(totals.items()))
        hm = f'<p class="muted">Hero model folders touched: {esc(", ".join(heroes))}</p>' if heroes else ''
        other = sum(1 for e in p['entities'] for c in e['changes'] if c['cat'] in ('visual', 'audio', 'ui', 'meta', 'technical'))
        other_s = f'<p class="muted">Also {other} visual / audio / UI / technical data fields (see the build pages).</p>' if other else ''
        out.append(('files', 'Game files', sum(sum(t.values()) for t in totals.values()),
                    f'<table class="kvt px-frame"><caption>Packed files: added / removed / modified</caption>{rows}</table>{hm}{other_s}'))
    return out


def _plain(s) -> str:
    return re.sub(r'<[^>]+>', '', str(s or ''))[:400]


def _loc_li(x: dict) -> str:
    key = f'<span class="chip">{esc(x["key"])}</span>'
    old, new = x.get('old'), x.get('new')
    if old and new:
        body = (f'<span class="old">{esc(_plain(old))}</span><span class="arrow">→</span>'
                f'<span class="new">{esc(_plain(new))}</span>')
    elif new:
        body = f'<span class="tag new">NEW</span> {esc(_plain(new))}'
    else:
        body = f'<span class="tag del">DEL</span> <span class="old">{esc(_plain(old))}</span>'
    return f'<li>{key}<span class="lbl">{body}</span></li>'


def convar_li(x: dict) -> str:
    desc = f' — {esc(x["desc"])}' if x.get('desc') else ''
    old, new = x.get('old'), x.get('new')
    if old is not None and new is not None:
        vals = f'<span class="old">{esc(old)}</span><span class="arrow">→</span><span class="new">{esc(new)}</span>'
    else:
        vals = f'<span class="new">{esc(new if new is not None else old)}</span>'
    st = x.get('status')
    m = mark(st) if st in ('documented', 'hidden') else ''
    return (f'<li class="st-{esc(st or "")}">{m}<span class="chip">{esc(x["op"])}</span><span class="lbl"><code>{esc(x["name"])}</code>{desc}</span>'
            f'<span class="vals">{vals}</span></li>')


def index_page(index: list[dict]) -> str:
    rows = []
    for p in reversed(index):
        c = p['counts']
        rows.append(
            f'<li><span class="date">{esc(p["date"])}</span>'
            f'<span><a class="ttl" href="{esc(p["id"])}.html">{esc(p["title"])}</a>'
            f'<small>{p["builds"]} builds</small>{_bar(c)}</span>'
            f'<span class="nums"><span class="chip">{mark("documented")}{c.get("documented", 0)}</span>'
            f'<span class="chip">{mark("hidden")}{c.get("hidden", 0)}</span>'
            f'<span class="chip">{mark("mismatch")}{p["line_counts"].get("mismatch", 0)}</span></span></li>')
    body = f'<h1>Patches</h1><ul class="timeline px-frame">{"".join(rows)}</ul>'
    return page('Patches', body, '../', 'patches')


def build_all() -> int:
    index = load_json('patches/index.json')
    for i, row in enumerate(index):
        p = load_json(f'patches/{row["id"]}.json.gz')
        prev = index[i - 1] if i > 0 else None
        nxt = index[i + 1] if i + 1 < len(index) else None
        write(f'patches/{row["id"]}.html', patch_page(p, prev, nxt))
    write('patches/index.html', index_page(index))
    return len(index)
