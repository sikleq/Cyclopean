"""Patch pages: official notes annotated with the data, plus hidden changes."""
from __future__ import annotations

import re
from functools import lru_cache

from .common import build_href, esc, ids_to_names, load_json, mark, names_by_id, page, pretty_id, write

GAMEPLAY = ('balance', 'mechanic', 'availability')
FILES_TAB_MIN = 100     # hidden changes before a notes patch also gets the "From the files" tab


def _counts_html(p: dict) -> str:
    c = p.get('counts', {})
    lc = p.get('line_counts', {})
    if not p.get('sections'):
        boxes = [('hidden', c.get('unannounced', 0), 'changes in the files — no official numbers published')]
        if c.get('documented'):     # notes of an earlier patch that only landed in these builds
            boxes.append(('documented', c['documented'], 'announced in earlier patch notes'))
    else:
        boxes = [
            ('documented', c.get('documented', 0), 'changes with exact numbers in the notes'),
            ('described', c.get('described', 0), 'changes covered by a general line'),
            ('hidden', c.get('hidden', 0), 'changes missing from the notes'),
            ('mismatch', lc.get('mismatch', 0), 'note lines that disagree with the files'),
            ('fix', lc.get('fix', 0), 'bug fixes listed'),
        ]
        if c.get('unreleased'):
            boxes.insert(3, ('unreleased', c['unreleased'], 'changes to heroes still in development'))
    return '<div class="stat-strip">' + ''.join(
        f'<div class="stat-box px-frame {cls}"><div class="n">{n}</div><div class="l">{esc(lbl)}</div></div>'
        for cls, n, lbl in boxes) + '</div>'


def _notes_table(p: dict, change_by_key: dict) -> str:
    rows = []
    for s in p['sections']:
        rows.append(f'<tr class="sec"><td colspan="3">{esc(s["title"])}</td></tr>')
        rows.extend(_note_row(ln, change_by_key) for ln in s['lines'])
    return f'<table class="notes">{"".join(rows)}</table>'


TOPIC_LABEL = {'link': 'forum link', 'sound': 'sound', 'visual': 'visuals', 'interface': 'interface',
               'map': 'map', 'bots': 'bots', 'performance': 'performance'}


def _note_row(ln: dict, change_by_key: dict) -> str:
    """status | the official line | what the game files say."""
    st = ln['status']
    if st == 'heading':
        return f'<tr class="sub"><td></td><td colspan="2">{esc(ln["text"])}</td></tr>'
    m = mark(st) if st in ('documented', 'rounded', 'described', 'mismatch', 'fix', 'untracked', 'nodata',
                           'repeated') else ''
    files = ''
    if st == 'repeated':
        files = f'also in <a href="{esc(ln["see"]["patch"])}.html">{esc(ln["see"]["title"])}</a>'
    elif st == 'untracked':
        files = f'<span class="topic">{esc(TOPIC_LABEL.get(ln.get("topic"), ln.get("topic") or ""))}</span>'
    if st in ('mismatch', 'rounded') and ln.get('data'):
        files = f'<span class="v">{esc(ln["data"][0])}</span><span class="arrow">→</span><span class="v">{esc(ln["data"][1])}</span>'
        files = ('files: ' if st == 'mismatch' else 'exact: ') + files
    elif st == 'documented' and ln.get('late'):
        # the value changed in a later build than the notes (a follow-up days after)
        late = ln['late']
        blds = ', '.join(str(b) for b in late.get('builds', []))
        files = (f'landed later: build {esc(blds)} · <a href="{esc(late["patch"])}.html">{esc(late["title"])}</a>')
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


@lru_cache(maxsize=1)
def hero_names() -> dict[str, str]:
    """hero id -> display name from the entity catalog (heroes that did not change themselves)."""
    return {e['id']: e.get('name') or e['id'] for e in load_json('entities.json')['entities']
            if e['file'] == 'heroes.vdata'}


@lru_cache(maxsize=1)
def catalog_names() -> dict[str, str]:
    """entity key -> the latest known name: an ability localized only after the patch
    still shows a name, not its internal id."""
    return {f"{e['file']}:{e['id']}": e['name'] for e in load_json('entities.json')['entities']
            if e.get('name') and e['name'] != e['id']}


def _display_name(e: dict) -> str:
    """Name at the patch's build; else the latest known name; else a readable stand-in, never the id."""
    name = e.get('name') or e['id']
    if name != e['id']:
        return name
    return catalog_names().get(f"{e['file']}:{e['id']}") or pretty_id(e['id'], e.get('owner'))


def _changes_table(ents: list[dict], rel: str) -> str:
    """All gameplay changes: one table, grouped by hero (with its abilities), then items, units, rules."""
    from .common import entity_icon, glyph_for, hero_icon, visual
    from .render import HIDDEN_LIKE, change_row, entity_rows, fold_tier_swaps, sort_changes
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
    names = hero_names()

    def hero_label(hid: str) -> str:
        if hid == 'hero_base':
            return 'Common abilities (all heroes)'
        return (heroes.get(hid, {}).get('name') or names.get(hid)
                or next((x.get('owner_name') for x in by_owner[hid] if x.get('owner_name')), hid))

    for hid in sorted(by_owner, key=lambda h: hero_label(h).lower()):
        hname = hero_label(hid)
        groups.append((hname, hero_icon(hid, rel), by_owner[hid], 'heroes' if hid == 'hero_base' else 'hero'))
    for e in rest:
        groups.append((_display_name(e), entity_icon(e['file'], e['id'], e.get('kind', ''), rel, e.get('name'),
                                                     e.get('owner')), [e], glyph_for(e['file'], e['id'], e.get('kind', ''))))
    trs = []
    for gname, gicon, members, gglyph in groups:
        all_ch = [c for e in members for c in e['changes']]
        n_h = sum(1 for c in all_ch if c.get('status') == 'hidden')
        n_dev = sum(1 for c in all_ch if c.get('status') == 'unreleased')
        icon_html = visual(gicon, gglyph, 'px gi')
        chips = f' <span class="chip">{mark("hidden")}{n_h}</span>' if n_h else ''
        if n_dev:
            chips += f' <span class="chip dev">{mark("unreleased")}{n_dev} in development</span>'
        search = gname.lower()
        dev = ' dev' if n_dev else ''
        dev += ' has-hidden' if any(c.get('status', 'hidden') in HIDDEN_LIKE for c in all_ch) else ''
        trs.append(f'<tr class="ph{dev}" data-search="{esc(search)}"><td colspan="4"><span class="t">{icon_html}'
                   f'{esc(gname)}</span>{chips}</td></tr>')
        solo = len(members) == 1 and members[0].get('kind') not in ('ability', 'weapon', 'melee')
        for e in members:
            if solo:          # an item / unit group: its header already names it
                trs.extend(change_row(c, '', search) for c in sort_changes(fold_tier_swaps(e['changes'])))
                continue
            scope = _display_name(e)
            if e['file'] == 'heroes.vdata' and e['id'] != '@shared':
                scope = 'Base stats'
            if e.get('targets'):
                scope += f' ({len(e["targets"])})'
            ic = entity_icon(e['file'], e['id'], e.get('kind', ''), rel, e.get('name'), e.get('owner'))
            trs.extend(entity_rows(scope, ic, e['changes'], search, glyph=glyph_for(e['file'], e['id'], e.get('kind', ''))))
    return f'<table class="hist grouped">{"".join(trs)}</table>'


def _key_changes(p: dict, rel: str) -> str:
    rows = p.get('key_changes') or []
    if not rows:
        return ''
    from .render import key_change_rows
    trs = key_change_rows(rows, rel, hero_names())
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
    lis = ''.join(f'<li>{esc(ids_to_names(s))}</li>' for s in lines[:1500])
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
            c['ent_name'] = _display_name(e)
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
        c = p.get('counts', {})
        # notes that say little about a big update (City Never Sleeps: 11 interface lines,
        # 1,400+ gameplay changes): the files' own summary sits next to the official text
        if c.get('hidden', 0) >= FILES_TAB_MIN and c.get('hidden', 0) > 3 * (c.get('documented', 0) + c.get('described', 0)):
            # 'generated', not 'files': the asset tab "Game files" already uses id="files"
            tabs.append(('generated', 'From the files', sum(len(e['changes']) for e in gameplay),
                         _key_changes(p, rel) + _generated_notes({**p, 'entities': gameplay})))
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


_KEY_HINT = re.compile(r"\{g:citadel_binding:'([^']*)'\}")


def _plain(s) -> str:
    """Loc text for display: no markup; key-binding tokens as [Attack]."""
    t = re.sub(r'<[^>]+>', '', str(s or ''))
    return _KEY_HINT.sub(r' [\1] ', t)[:400]


_LOC_SUFFIX = re.compile(r'^(?P<base>.+?)(?P<suf>(?:_t(?P<tier>[1-3]))?_(?P<kind>desc|quip|header|lore|name|label|'
                         r'tooltip|note)|_t(?P<tier2>[1-3])|:n)?$')
_LOC_KIND = {'desc': 'description', 'quip': 'quip', 'header': 'header', 'lore': 'lore', 'name': 'name',
             'label': 'label', 'tooltip': 'tooltip', 'note': 'note'}


def loc_key_label(key: str) -> str:
    """'ability_afterburn_t1_desc' -> 'Afterburn · T1 description'; unknown keys are
    humanised ('citadel_commend_toast_seconds' -> 'commend toast seconds'). The raw key
    stays available as the chip's tooltip."""
    m = _LOC_SUFFIX.match(key.lower())
    base, tier = m.group('base'), m.group('tier') or m.group('tier2')
    part = ' '.join(p for p in (f'T{tier}' if tier else '', _LOC_KIND.get(m.group('kind') or '', '')) if p)
    if m.group('suf') == ':n':
        part = 'name'
    names = names_by_id()
    name, extra = names.get(base), []
    while not name and '_' in base:       # 'ability_afterburn_burn' -> 'Afterburn' + 'burn'
        base, _, tail = base.rpartition('_')
        extra.insert(0, tail)
        name = names.get(base)
    if not name:
        return re.sub(r'^(citadel_|ability_|modifier_|upgrade_)+', '', key.lower()).replace('_', ' ').replace(':', ' ')
    part = ' '.join(extra + ([part] if part else []))
    return f'{name} · {part}' if part else name


def _loc_li(x: dict) -> str:
    key = f'<span class="chip" data-tooltip="{esc(x["key"])}">{esc(loc_key_label(x["key"]))}</span>'
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
