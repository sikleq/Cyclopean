"""Patch pages: official notes annotated with the data, plus hidden changes."""
from __future__ import annotations

import re

from .common import build_href, esc, load_json, mark, page, write
from .render import entity_block, group_by_owner

GAMEPLAY = ('balance', 'mechanic', 'availability')


def _counts_html(p: dict) -> str:
    c = p.get('counts', {})
    lc = p.get('line_counts', {})
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


def _bar(c: dict) -> str:
    total = sum(c.get(k, 0) for k in ('documented', 'described', 'hidden')) or 1
    seg = ''.join(f'<span class="{cls}" style="width:{c.get(k, 0) / total * 100:.1f}%"></span>'
                  for k, cls in (('documented', 'b-doc'), ('described', 'b-des'), ('hidden', 'b-hid')))
    return f'<div class="bar">{seg}</div>'


def _line_html(ln: dict, change_by_key: dict) -> str:
    st = ln['status']
    status = st if st in ('documented', 'rounded', 'described', 'mismatch', 'fix') else ''
    m = mark(status) if status else '<span class="mark"></span>'
    data = ''
    if st in ('mismatch', 'rounded') and ln.get('data'):
        data = (f'<span class="data">Game files: <span class="v">{esc(ln["data"][0])}</span>'
                f'<span class="arrow">→</span><span class="v">{esc(ln["data"][1])}</span></span>')
    elif st == 'documented' and ln.get('changes'):
        c = change_by_key.get(ln['changes'][0])
        if c:
            data = (f'<span class="data">{esc(c["label"])}: <span class="v">{esc(c["old_s"])}</span>'
                    f'<span class="arrow">→</span><span class="v">{esc(c["new_s"])}</span></span>')
    elif st == 'described' and len(ln.get('changes', [])) > 1:
        items = [change_by_key.get(k) for k in ln['changes'][:40]]
        chips = ''.join(
            f'<span class="chip">{esc(c.get("ent_name", ""))} · {esc(c["label"])}: '
            f'{esc(c["old_s"])}→{esc(c["new_s"])}</span> ' for c in items if c)
        more = len(ln['changes']) - 40
        more_s = f' <span class="muted">+{more} more</span>' if more > 0 else ''
        data = f'<details class="data"><summary>Exact values in the files ({len(ln["changes"])})</summary>{chips}{more_s}</details>'
    return f'<li class="st-{esc(st)}">{m}<span class="txt">{esc(ln["text"])}{data}</span></li>'


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
    src = f' · <a href="{esc(p["url"])}" rel="noopener">official notes</a>' if p.get('url') else ''
    parts.append(f'<div class="page-head"><div class="meta">{esc(p["date"])}{src} · builds: {builds or "—"}</div></div>')
    parts.append(_counts_html(p))
    parts.append('<div class="toolbar">'
                 '<button class="px-btn" data-toggle-class="filter-hidden-only" data-target="#patch-body">Only hidden</button>'
                 '<span class="sep"></span>'
                 '<input type="search" placeholder="Filter heroes, items…" data-search-target="#patch-body .entity-block">'
                 '</div>')
    parts.append('<div id="patch-body">')
    if p['sections']:
        parts.append('<section class="section px-frame"><h2>Patch notes</h2>')
        for s in p['sections']:
            parts.append(f'<h3>{esc(s["title"])}</h3><ul class="note-lines">')
            parts.extend(_line_html(ln, change_by_key) for ln in s['lines'])
            parts.append('</ul>')
        parts.append('</section>')

    gameplay = []
    for e in p['entities']:
        ch = [c for c in e['changes'] if c['cat'] in GAMEPLAY]
        if ch:
            gameplay.append({**e, 'changes': ch})
    hidden_n = sum(1 for e in gameplay for c in e['changes'] if c['status'] == 'hidden')
    parts.append(f'<section class="section"><h2 class="section-title">All gameplay changes in the files '
                 f'<span class="chip">{hidden_n} hidden</span></h2>')
    names = {e['id']: e.get('name') for e in p['entities'] if e['file'] == 'heroes.vdata'}
    for e in gameplay:
        if e.get('owner'):
            e['owner_name'] = names.get(e['owner'])
    for ent, children in group_by_owner(gameplay):
        parts.append(entity_block(ent, rel, children, show_builds=len(p['builds']) > 1))
    parts.append('</section>')

    parts.append(_extras_html(p, rel))
    parts.append('</div>')
    nav = []
    if prev:
        nav.append(f'<a class="px-btn" href="{esc(prev["id"])}.html">← {esc(prev["title"])}</a>')
    if nxt:
        nav.append(f'<a class="px-btn" href="{esc(nxt["id"])}.html">{esc(nxt["title"])} →</a>')
    parts.append('<div class="flex">' + ''.join(nav) + '</div>')
    return page(p['title'], ''.join(parts), rel, 'patches',
                description=f'Deadlock {p["title"]}: official notes vs game files')


def _extras_html(p: dict, rel: str) -> str:
    ex = p.get('extras', {})
    out = []
    loc_rows = ex.get('loc', [])
    if loc_rows:
        more = ex.get('loc_total', len(loc_rows)) - len(loc_rows)
        more_s = f'<p class="muted">+{more} more on the build pages.</p>' if more > 0 else ''
        rows = ''.join(_loc_li(x) for x in loc_rows)
        out.append(f'<details class="collapsible section px-frame"><summary>Text & tooltip changes'
                   f'<span class="chip">{ex.get("loc_total", len(loc_rows))}</span></summary>'
                   f'<ul class="change-list">{rows}</ul>{more_s}</details>')
    cv = ex.get('convars', [])
    if cv:
        rows = ''.join(convar_li(x) for x in cv)
        out.append(f'<details class="collapsible section px-frame"><summary>Console variables'
                   f'<span class="chip">{ex.get("convars_total", len(cv))}</span></summary>'
                   f'<ul class="change-list">{rows}</ul></details>')
    assets = ex.get('assets') or {}
    totals = assets.get('counts', {})
    if totals:
        heroes = assets.get('hero_models', [])
        rows = ''.join(f'<li><span class="lbl">{esc(cat)}</span><span class="vals">+{t["added"]} / −{t["removed"]} / ~{t["modified"]}</span></li>'
                       for cat, t in sorted(totals.items()))
        hm = f'<p class="muted">Hero model folders touched: {esc(", ".join(heroes))}</p>' if heroes else ''
        out.append(f'<details class="collapsible section px-frame"><summary>Game files (models, VFX, sounds, UI)'
                   f'<span class="chip">{sum(sum(t.values()) for t in totals.values())}</span></summary>'
                   f'<ul class="change-list">{rows}</ul>{hm}</details>')
    visual = sum(1 for e in p['entities'] for c in e['changes'] if c['cat'] in ('visual', 'audio', 'ui', 'meta'))
    if visual:
        out.append(f'<p class="muted">Also changed in data: {visual} visual / audio / UI fields (see build pages).</p>')
    return ''.join(out)


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
