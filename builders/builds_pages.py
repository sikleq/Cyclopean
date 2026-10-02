"""Build pages: every tracked game build and exactly what its files changed."""
from __future__ import annotations

from .common import (COSMETIC_KINDS, build_label, build_pages, cosmetics, esc, load_json, names_by_id, plural, page,
                     patch_title_text, pretty_id, slug, write)
from .patches_pages import _changes_table, _loc_li, convar_li

GAMEPLAY = ('balance', 'mechanic', 'availability')
COSMETIC = ('visual', 'audio', 'ui', 'meta')
ENTITY_LIMIT = 400          # huge builds (new heroes) are truncated with a note


def _patch_of_build() -> dict[str, dict]:
    """{build record file name: patch index row}."""
    out = {}
    for row in load_json('patches/index.json'):
        p = load_json(f'patches/{row["id"]}.json.gz')
        for b in p['builds']:
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
                   f'<span class="vals">{", ".join(_cosmetic_subject(s, e["kind"], rel) for s in by_name(e))}</span></li>'
                   for e in evs)
    return (f'<details class="collapsible section px-frame" open><summary>Cosmetics<span class="chip">{len(evs)}</span>'
            f'</summary><ul class="change-list">{rows}</ul></details>')


def build_page(rec: dict, patch: dict | None, prev_b, next_b) -> str:
    rel = '../'
    ents = []
    cosmetic: dict[str, int] = {}
    for e in rec['entities']:
        g = [c for c in e['changes'] if c['cat'] in GAMEPLAY]
        for c in e['changes']:
            if c['cat'] in COSMETIC:
                cosmetic[c['cat']] = cosmetic.get(c['cat'], 0) + 1
        for c in g:
            c.setdefault('status', 'raw')
        if g or e['status'] in ('added', 'removed', 'returned'):
            if e['status'] == 'added' and not g:
                g = [{'op': 'add', 'cat': 'mechanic', 'label': 'Added to game data', 'new_s': '', 'status': 'raw'}]
            if e['status'] == 'returned':
                g = [{'op': 'add', 'cat': 'mechanic', 'label': 'Back in game data', 'new_s': '', 'status': 'raw'}] + g
            if e['status'] == 'removed':
                g = [{'op': 'remove', 'cat': 'mechanic', 'label': 'Removed from game data', 'old_s': '', 'status': 'raw'}]
            ents.append({**e, 'changes': g})
    head = [f'<div class="crumbs"><a href="index.html">Builds</a> / {esc(build_label(rec["build"]))}</div>',
            f'<h1>{esc(build_label(rec["build"]))}</h1>',
            f'<div class="page-head"><div class="meta">Tracked {esc(rec["date"][:16].replace("T", " "))} UTC'
            f'{" · game build date " + esc(rec["version_date"]) if rec.get("version_date") else ""}'
            f'{" · part of <a href=" + chr(34) + rel + "patches/" + esc(patch["id"]) + ".html" + chr(34) + ">" + esc(patch_title_text(patch)) + "</a>" if patch else ""}'
            f'</div></div>']
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
        body.append(_changes_table(ents[:ENTITY_LIMIT], rel))
        if len(ents) > ENTITY_LIMIT:
            body.append(f'<p class="muted">{len(ents) - ENTITY_LIMIT} more entities not shown.</p>')
        body.append('</section>')
    if cosmetic:
        body.append('<p class="muted">Cosmetic fields changed: ' + ', '.join(f'{k} {v}' for k, v in sorted(cosmetic.items())) + '.</p>')
    if rec.get('loc'):
        rows = ''.join(_loc_li(x) for x in rec['loc'][:500])
        body.append(f'<details class="collapsible section px-frame"><summary>Text changes<span class="chip">{len(rec["loc"])}</span></summary>'
                    f'<ul class="change-list">{rows}</ul></details>')
    if rec.get('convars'):
        rows = ''.join(convar_li(x) for x in rec['convars'][:400])
        body.append(f'<details class="collapsible section px-frame"><summary>Console variables<span class="chip">{len(rec["convars"])}</span></summary>'
                    f'<ul class="change-list">{rows}</ul></details>')
    cos = cosmetics_section(rec.get('build'), rel)
    if cos:
        body.append(cos)
    if rec.get('assets'):
        a = rec['assets']
        rows = ''.join(f'<li><span class="lbl">{esc(cat)}</span><span class="vals">+{t["added"]} / −{t["removed"]} / ~{t["modified"]}</span></li>'
                       for cat, t in a.get('counts', {}).items())
        hm = ''
        if a.get('hero_models'):
            hm = '<p class="muted">Hero model folders: ' + esc(', '.join(f'{k} ({"/".join(v)})' for k, v in a['hero_models'].items())) + '</p>'
        body.append(f'<details class="collapsible section px-frame"><summary>Game files<span class="chip">{sum(sum(t.values()) for t in a.get("counts", {}).values())}</span></summary>'
                    f'<ul class="change-list">{rows}</ul>{hm}</details>')
    body.append('</div>')
    nav = []
    if prev_b:
        nav.append(f'<a class="px-btn" href="{prev_b}.html">← {prev_b}</a>')
    if next_b:
        nav.append(f'<a class="px-btn" href="{next_b}.html">{next_b} →</a>')
    body.append('<div class="flex">' + ''.join(nav) + '</div>')
    return page(build_label(rec['build']), ''.join(body), rel, 'builds')


def index_page(index: list[dict], patch_of: dict[str, dict]) -> str:
    stems = build_pages()
    rows = []
    for r in reversed(index):
        f = r.get('fields', {})
        gp = f.get('balance', 0) + f.get('mechanic', 0) + f.get('availability', 0)
        if not (gp or r.get('loc') or r.get('convars') or r.get('added') or r.get('removed')):
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
        rows.append(f'<li data-search="{r["build"]} {esc(r["date"][:10])}"><span class="date">{esc(r["date"][:10])}</span>'
                    f'<span><a class="ttl" href="{stems[r["file"]]}.html">{esc(_row_label(r, stems))}</a>{ptxt}</span>'
                    f'<span class="nums">{"".join(chips)}</span></li>')
    body = ('<h1>Builds</h1>'
            '<div class="toolbar"><input type="search" placeholder="Build number or date…" data-search-target=".timeline > li"></div>'
            f'<ul class="timeline px-frame">{"".join(rows)}</ul>')
    return page('Builds', body, '../', 'builds')


def build_all() -> int:
    index = load_json('builds/index.json')
    patch_of = _patch_of_build()
    stems = build_pages()
    pages = [stems[r['file']] for r in index]
    n = 0
    for i, r in enumerate(index):
        rec = load_json(f'builds/{r["file"]}')
        prev_b = pages[i - 1] if i > 0 else None
        next_b = pages[i + 1] if i + 1 < len(pages) else None
        write(f'builds/{pages[i]}.html', build_page(rec, patch_of.get(r['file']), prev_b, next_b))
        n += 1
    write('builds/index.html', index_page(index, patch_of))
    return n
