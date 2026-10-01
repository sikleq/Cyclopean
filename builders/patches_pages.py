"""Patch pages: official notes annotated with the data, plus hidden changes."""
from __future__ import annotations

import re
from functools import lru_cache

from .notes_view import notes_table
from .common import build_href, esc, ids_to_names, load_json, mark, names_by_id, page, pretty_id, write

GAMEPLAY = ('balance', 'mechanic', 'availability')
FILES_TAB_MIN = 100     # hidden changes before a notes patch also gets the "From the files" tab


SUMMARY_TAGS = (('buff', 'Buffs'), ('nerf', 'Nerfs'), ('new', 'New'), ('del', 'Removed'), ('rework', 'Reworks'),
                ('other', 'Other'))


def _summary(p: dict, gameplay: list[dict], rel: str, link_base: str = '') -> str:
    """The patch's first screen: how big and which way (tag counters + bar), who was hit
    (hero portraits with up/down counts), then one thin line of the notes check."""
    from .common import hero_icon
    from .render import tag_of
    counts = {k: 0 for k, _ in SUMMARY_TAGS}
    per_hero: dict[str, list[int]] = {}
    for e in gameplay:
        owner = e['id'] if e['file'] == 'heroes.vdata' and e['id'] != '@shared' else e.get('owner')
        for c in e['changes']:
            cls = tag_of(c)[0]
            counts[cls if cls in counts else 'other'] += 1
            if owner and owner != 'hero_base':
                ud = per_hero.setdefault(owner, [0, 0])
                if cls == 'buff':
                    ud[0] += 1
                elif cls == 'nerf':
                    ud[1] += 1
    total = sum(counts.values()) or 1
    tiles = ''.join(f'<div class="sum-tile t-{k}"><span class="n">{counts[k]}</span><span class="l">{esc(lbl)}</span></div>'
                    for k, lbl in SUMMARY_TAGS if counts[k])
    bar = ''.join(f'<span class="b-{k}" style="width:{counts[k] / total * 100:.2f}%"></span>' for k, _ in SUMMARY_TAGS
                  if counts[k])
    names = hero_names()
    live = released_heroes()
    heroes = sorted(per_hero, key=lambda h: (-(sum(per_hero[h])), names.get(h, h)))
    # heroes still in development (placeholder art) do not crowd the strip: one counter for them
    in_dev = [h for h in heroes if h not in live]
    strip = ''.join(
        f'<a class="hchip" href="{esc(link_base)}#c-{esc(h)}" data-tooltip="{esc(names.get(h, h))}">'
        f'<img class="px" src="{esc(hero_icon(h, rel) or "")}" alt="{esc(names.get(h, h))}" loading="lazy">'
        f'<span class="hc">{"<span class=up>▲" + str(per_hero[h][0]) + "</span>" if per_hero[h][0] else ""}'
        f'{"<span class=dn>▼" + str(per_hero[h][1]) + "</span>" if per_hero[h][1] else ""}</span></a>'
        for h in heroes if h in live and hero_icon(h, rel))
    if in_dev:
        strip += f'<span class="chip dev hdev">{mark("unreleased")}+{len(in_dev)} in development</span>'
    c = p.get('counts', {})
    lc = p.get('line_counts', {})
    if p.get('sections'):
        audit = [('documented', c.get('documented', 0), 'exact in the notes'),
                 ('described', c.get('described', 0), 'covered by a general line'),
                 ('hidden', c.get('hidden', 0), 'not in the notes'),
                 ('mismatch', lc.get('mismatch', 0), 'notes disagree with the files'),
                 ('fix', lc.get('fix', 0), 'bug fixes')]
        if c.get('unreleased'):
            audit.insert(3, ('unreleased', c['unreleased'], 'heroes in development'))
    else:
        audit = [('hidden', c.get('unannounced', 0), 'changes, no official notes')]
        if c.get('documented'):
            audit.append(('documented', c['documented'], 'announced in earlier notes'))
    audit_html = ''.join(f'<span class="au au-{k}">{mark(k)}<b>{n}</b> {esc(lbl)}</span>' for k, n, lbl in audit if n)
    return (f'<section class="summary px-frame"><div class="sum-tiles">{tiles}</div><div class="sum-bar">{bar}</div>'
            f'{"<div class=sum-heroes>" + strip + "</div>" if strip else ""}'
            f'<div class="sum-audit">{audit_html}</div></section>')


@lru_cache(maxsize=1)
def hero_names() -> dict[str, str]:
    """hero id -> display name from the entity catalog (heroes that did not change themselves)."""
    return {e['id']: e.get('name') or e['id'] for e in load_json('entities.json')['entities']
            if e['file'] == 'heroes.vdata'}


@lru_cache(maxsize=1)
def released_heroes() -> set[str]:
    """Heroes a player can pick today (release or pre-release, still in the files)."""
    return {e['id'] for e in load_json('entities.json')['entities']
            if e['file'] == 'heroes.vdata' and e.get('alive')
            and e.get('state') in ('EHeroDevState_Release', 'EHeroDevState_PreRelease')}


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


def _changes_table(ents: list[dict], rel: str, pid: str | None = None) -> str:
    """All gameplay changes as entity cards: one card per hero (its abilities as
    sub-headers), then one per item, unit and rule; each with its history strip."""
    from .cards import card, card_head, change_rows, is_hidden, sub_head
    from .common import entity_icon, glyph_for, hero_icon
    from .render import KIND_LABEL
    from .trail import trail_html
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
    names = hero_names()

    def hero_label(hid: str) -> str:
        if hid == 'hero_base':
            return 'Common abilities (all heroes)'
        return (heroes.get(hid, {}).get('name') or names.get(hid)
                or next((x.get('owner_name') for x in by_owner[hid] if x.get('owner_name')), hid))

    out = []
    for hid in sorted(by_owner, key=lambda h: hero_label(h).lower()):
        members = by_owner[hid]
        all_ch = [c for e in members for c in e['changes']]
        hname = hero_label(hid)
        body = []
        for e in members:
            if e['file'] == 'heroes.vdata':
                scope, ic, glyph = 'Base stats', hero_icon(hid, rel), 'hero'
            else:
                scope = _display_name(e)
                ic = entity_icon(e['file'], e['id'], e.get('kind', ''), rel, e.get('name'), e.get('owner'))
                glyph = glyph_for(e['file'], e['id'], e.get('kind', ''))
            body.append(sub_head(scope, ic, glyph, e['changes'], is_hidden(e['changes'])))
            body.append(change_rows(e['changes']))
        head = card_head(hname, hero_icon(hid, rel), 'heroes' if hid == 'hero_base' else 'hero', all_ch,
                         trail=trail_html(f'heroes.vdata:{hid}', pid, rel))
        out.append(card(head, ''.join(body), hidden=is_hidden(all_ch),
                        dev=any(c.get('status') == 'unreleased' for c in all_ch),
                        search=hname.lower(), anchor=f'c-{hid}'))
    for e in rest:
        name = _display_name(e)
        if e.get('targets'):
            name += f' ({len(e["targets"])})' if f'({len(e["targets"])})' not in name else ''
        ic = entity_icon(e['file'], e['id'], e.get('kind', ''), rel, e.get('name'), e.get('owner'))
        head = card_head(name, ic, glyph_for(e['file'], e['id'], e.get('kind', '')), e['changes'],
                         trail=trail_html(f"{e['file']}:{e['id']}", pid, rel))
        out.append(card(head, change_rows(e['changes']), hidden=is_hidden(e['changes']), search=name.lower(),
                        rows=len(e['changes'])))
    return '<div class="ecards">' + ''.join(out) + '</div>'


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
    # patch switcher next to the title (players step through patches)
    step = ''
    if prev:
        step += f'<a class="step" href="{esc(prev["id"])}.html" data-tooltip="{esc(prev["title"])}">◀</a>'
    if nxt:
        step += f'<a class="step" href="{esc(nxt["id"])}.html" data-tooltip="{esc(nxt["title"])}">▶</a>'
    parts = [f'<div class="crumbs"><a href="index.html">Patches</a> / {esc(p["date"])}</div>',
             f'<div class="ptitle"><h1>{esc(p["title"])}</h1><span class="steps">{step}</span></div>']
    builds = ', '.join(f'<a href="{build_href(b["file"], rel)}">{b["build"]}</a>' for b in p['builds'][:30])
    link_text = 'official notes' if p.get('source') != 'announcement' else 'official announcement'
    src = f' · <a href="{esc(p["url"])}" rel="noopener">{link_text}</a>' if p.get('url') else ''
    parts.append(f'<div class="meta muted">{esc(p["date"])}{src} · builds: {builds or "—"}</div>')

    gameplay = []
    for e in p['entities']:
        ch = [c for c in e['changes'] if c['cat'] in GAMEPLAY]
        if ch:
            gameplay.append({**e, 'changes': ch})
    names = {e['id']: e.get('name') for e in p['entities'] if e['file'] == 'heroes.vdata'}
    for e in gameplay:
        if e.get('owner'):
            e['owner_name'] = names.get(e['owner'])
    parts.append(_summary(p, gameplay, rel))
    ex = p.get('extras', {})
    tabs = []
    if p['sections']:
        tabs.append(('notes', 'Patch notes', sum(len(s['lines']) for s in p['sections']), notes_table(p, change_by_key, rel)))
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
                     'data-search-target="#changes .ecard[data-search]"></div>' + _changes_table(gameplay, rel, p['id']))
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


MONTHS = ('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
          'November', 'December')
INDEX_HEROES = 6


def _index_row(p: dict, stats: dict, rel: str, follow: bool) -> str:
    from .common import hero_icon
    c, lc = p['counts'], p['line_counts']
    st = stats.get(p['id'], {'tags': {}, 'heroes': []})
    t = st['tags']
    # four fixed cells (empty when zero) so the counts line up from row to row
    dirs = ''.join(f'<span class="ix-{k}">{sym + str(t[k]) if t.get(k) else ""}</span>'
                   for k, sym in (('buff', '▲'), ('nerf', '▼'), ('new', '✦'), ('del', '✕')))
    names = hero_names()
    faces = ''.join(f'<img class="px" src="{esc(hero_icon(h, rel) or "")}" alt="" loading="lazy" '
                    f'data-tooltip="{esc(names.get(h, h))}">' for h in st['heroes'][:INDEX_HEROES] if hero_icon(h, rel))
    if p.get('has_notes'):
        audit = (f'<span class="au">{mark("documented")}<b>{c.get("documented", 0)}</b></span>'
                 f'<span class="au au-hidden">{mark("hidden")}<b>{c.get("hidden", 0)}</b></span>')
        if p['line_counts'].get('mismatch'):
            audit += f'<span class="au au-mismatch">{mark("mismatch")}<b>{lc["mismatch"]}</b></span>'
    else:
        audit = f'<span class="au au-hidden">{mark("hidden")}<b>{c.get("unannounced", 0)}</b> no notes</span>'
    title = p['title'].split(' · follow-up ')[-1] if follow else p['title']
    title = f'follow-up {title}' if follow else title
    return (f'<a class="ix{" fu" if follow else ""}" href="{esc(p["id"])}.html">'
            f'<span class="ixd">{esc(p["date"])}</span>'
            f'<span class="ixt"><span class="t">{esc(title)}</span><span class="b">{p["builds"]} builds</span></span>'
            f'<span class="ixs">{dirs}</span><span class="ixh">{faces}</span>'
            f'<span class="ixa">{audit}{_bar(c)}</span></a>')


def index_page(index: list[dict]) -> str:
    """Patches by month; a follow-up sits under its parent; each row says which way the
    patch went and who it hit."""
    from .trail import patch_stats
    stats = patch_stats()
    rel = '../'
    # a thread's follow-ups stay with their parent (06-30 Update and its 07-01..07-28 follow-ups),
    # families newest first, the month taken from the parent
    families: dict[str, list[dict]] = {}
    for p in index:
        families.setdefault(p['title'].split(' · follow-up ')[0], []).append(p)
    ordered = []
    for fam in families.values():
        parent = next((p for p in fam if ' · follow-up ' not in p['title']), fam[0])
        follows = sorted((p for p in fam if p is not parent), key=lambda p: p['date'], reverse=True)
        ordered.append((parent, follows))
    ordered.sort(key=lambda pf: pf[0]['date'], reverse=True)
    month_n: dict[str, int] = {}
    for parent, _ in ordered:
        month_n[parent['date'][:7]] = month_n.get(parent['date'][:7], 0) + 1
    out, month = [], None
    for parent, follows in ordered:
        m = parent['date'][:7]
        if m != month:
            month = m
            n = month_n[m]
            out.append(f'<div class="banner sub"><span class="bt">{MONTHS[int(m[5:7]) - 1]} {m[:4]}</span>'
                       f'<span class="bc">{n} update{"s" if n != 1 else ""}</span></div>')
        out.append(_index_row(parent, stats, rel, False))
        out.extend(_index_row(f, stats, rel, True) for f in follows)
    body = f'<h1>Patches</h1><div class="ixlist">{"".join(out)}</div>'
    return page('Patches', body, rel, 'patches')


def build_all() -> int:
    index = load_json('patches/index.json')
    for i, row in enumerate(index):
        p = load_json(f'patches/{row["id"]}.json.gz')
        prev = index[i - 1] if i > 0 else None
        nxt = index[i + 1] if i + 1 < len(index) else None
        write(f'patches/{row["id"]}.html', patch_page(p, prev, nxt))
    write('patches/index.html', index_page(index))
    return len(index)
