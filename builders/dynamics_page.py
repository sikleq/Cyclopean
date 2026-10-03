"""Hero / item / unit changes as a matrix (Sloppy's "Hero Dynamics"): one row per hero, item or unit, one column per
patch, each cell a tile striped in the colours of what the patch did (buff, nerf, new, removed…),
each stripe as tall as its share.

A hero's tile holds everything the patch did to the hero — stats, weapon and abilities in one cell;
a filter (All / Stats / Weapon / Abilities) narrows every tile to one part (owner, 2026-10-01: one
cell, a filter, no split tiles). Switches: older patches, buff-vs-nerf (one net colour per cell), tag filters, pre-release heroes /
removed items; a search over the rows; a hover card per cell (scripts.js, from the page's JSON)."""
from __future__ import annotations

import json
from datetime import date, timedelta
from functools import lru_cache

from .common import display_name, entity_icon, esc, hero_icon, load_json, patch_name, patch_title_text, pretty_id
from .pixel_icons import tag_svg
from .render import TAG_ORDER, TAG_WORD_ONE, TAG_WORDS, shown_value, tag_of

OLD_DAYS = 365            # columns older than this hide behind "Older patches"
MATRIX_TAGS = ('new', 'rework', 'buff', 'nerf', 'del', 'up', 'down', 'mech', 'on', 'off', 'changed')
SAMPLES = 2               # the hover card lists this many biggest changes per part of a hero
SAMPLES_ONE = 3           # … and of an item or unit (one part: the row itself)
PARTS = (('stats', 'Stats'), ('weapon', 'Weapon'), ('abil', 'Abilities'))
WEAPON_KINDS = ('weapon', 'melee')


def part_of(e: dict) -> str:
    if e['file'] == 'heroes.vdata':
        return 'stats'
    return 'weapon' if e.get('kind') in WEAPON_KINDS else 'abil'


def _display(e: dict) -> str:
    if e['file'] == 'heroes.vdata':
        return 'Base stats'
    return e['name'] if e.get('name') and e['name'] != e['id'] else pretty_id(e['id'], e.get('owner'))


@lru_cache(maxsize=1)
def _cells() -> tuple[list[dict], dict[str, dict[str, dict[str, int]]]]:
    """(patch rows oldest first, {row key: {patch id: {tag: count}}}). A hero's row counts its own
    stats and every ability it owns; an item's row is the item. Same counting rule as everywhere."""
    d = _collect()
    return d['rows'], d['cells']


@lru_cache(maxsize=1)
def _collect() -> dict:
    """Everything the matrices draw, in one pass over the patches:
    rows       patch index rows, oldest first
    cells      {row key: {pid: {tag: n}}}
    parts      {row key: {pid: {part: {tag: n}}}}           (heroes: stats / weapon / abil)
    samples    {row key: {pid: [[what, field, old, new, tag, part], ...]}}"""
    from .cards import gameplay_entities, player_facing
    rows = sorted(load_json('patches/index.json'), key=lambda r: r['date'])
    ents = load_json('entities.json')['entities']
    # an NPC's own abilities count on its row (Walker's Stomp), as they do on its page
    npc = {e['id']: e['units'] for e in ents if e.get('units')}
    # a unit counts on its family's row; the same change on several members (five Gutter Ghouls, four
    # Walkers) counts once (unit_families)
    from .unit_families import main_of
    fam = main_of([e for e in ents if e['file'] == 'npc_units.vdata' and not e.get('template')])
    cells: dict = {}
    parts: dict = {}
    raw: dict = {}
    once: set = set()
    for r in rows:
        p = load_json(f'patches/{r["id"]}.json.gz')
        for e in gameplay_entities(p['entities']):
            if e.get('id') == '@shared':
                continue
            if e['file'] == 'heroes.vdata':
                keys = [f'hero:{e["id"]}']
            elif e.get('owner'):
                keys = [f'hero:{e["owner"]}']
            elif e.get('kind') == 'item':
                keys = [f'item:{e["id"]}']
            elif e['file'] == 'npc_units.vdata':
                keys = [f'unit:{fam.get(e["id"], e["id"])}']
            elif e['file'] == 'abilities.vdata' and e['id'] in npc:
                keys = list(dict.fromkeys(f'unit:{fam.get(u, u)}' for u in npc[e['id']]))
            else:
                continue
            part = part_of(e)
            for key in keys:
                cell = cells.setdefault(key, {}).setdefault(r['id'], {})
                pcell = parts.setdefault(key, {}).setdefault(r['id'], {}).setdefault(part, {})
                for c in player_facing(e['changes']):
                    if key.startswith('unit:'):
                        sig = (key, r['id'], e['file'] == 'abilities.vdata' and e['id'], c.get('label'),
                               c.get('old_s'), c.get('new_s'))
                        if sig in once:
                            continue
                        once.add(sig)
                    t = tag_of(c)[0]
                    for d in (cell, pcell):
                        d[t] = d.get(t, 0) + 1
                    s = (_display(e), c.get('label') or '', shown_value(c.get('old_s')), shown_value(c.get('new_s')),
                         t, part, abs(c['pct']) if isinstance(c.get('pct'), (int, float)) else 0)
                    raw.setdefault(key, {}).setdefault(r['id'], []).append(s)
    samples: dict = {}
    for k, per in raw.items():
        for pid, lst in per.items():
            ranked = sorted(lst, key=lambda x: (-x[6], TAG_ORDER.get(x[4], 9)))
            picked, seen = [], {}
            limit = SAMPLES if k.startswith('hero:') else SAMPLES_ONE
            for x in ranked:                      # the biggest per part, the parts in their order
                if seen.get(x[5], 0) < limit:
                    seen[x[5]] = seen.get(x[5], 0) + 1
                    picked.append(list(x[:6]))
            order = {p: i for i, (p, _) in enumerate(PARTS)}
            samples.setdefault(k, {})[pid] = sorted(picked, key=lambda x: order.get(x[5], 9))
    return {'rows': rows, 'cells': cells, 'parts': parts, 'samples': samples}


def _net(counts: dict[str, int]) -> str:
    good = counts.get('buff', 0) + counts.get('new', 0) + counts.get('on', 0)
    bad = counts.get('nerf', 0) + counts.get('del', 0) + counts.get('off', 0)
    return 'net-buff' if good > bad else 'net-nerf' if bad > good else 'net-mix'


STRIPE_MIN = 0.12        # a stripe never thinner than this share of the tile (one buff among 30 rows)
STRIPE_COLOUR = {'up': 'changed', 'down': 'changed'}


def stripes(counts: dict[str, int]) -> str:
    """The tile's stripes as ONE gradient (scripts.js draws the same after a filter): a span per tag cost
    ~10k nodes on the item matrix (2026-10-03)."""
    tags = sorted((t for t in counts if counts[t]), key=lambda t: TAG_ORDER.get(t, 9))
    if not tags:
        return ''
    total = sum(counts[t] for t in tags)
    shares = [max(counts[t] / total, STRIPE_MIN) for t in tags]
    norm = sum(shares)
    stops, acc = [], 0.0
    for t, s in zip(tags, shares):
        a, acc = acc, acc + s / norm * 100
        stops.append(f'var(--tag-{STRIPE_COLOUR.get(t, t)}) {a:.3g}% {acc:.3g}%')
    return f'linear-gradient({",".join(stops)})'


def _cell(counts: dict[str, int], href: str, k: int | None, old: bool) -> str:
    data_k = f' data-k="{k}"' if k is not None else ''
    return (f'<td{" class=old" if old else ""}><a class="dsq {_net(counts)}" href="{esc(href)}"{data_k} '
            f'style="background:{stripes(counts)}"><span class="dn">{sum(counts.values())}</span></a></td>')


def _gap(n: int, old: bool) -> str:
    """A run of empty patch cells is ONE cell (the column lines are its background): the item matrix had
    29k cells, 27k of them empty (2026-10-03). A run never crosses into the old columns, which hide."""
    span = f' colspan={n}' if n > 1 else ''
    cls = ' class=old' if old else ''
    return f'<td{cls}{span}></td>'


def _head(rows: list[dict], cutoff: str, label: str) -> str:
    months: list[tuple[str, int, bool]] = []
    for r in rows:
        m, old = r['date'][:7], r['date'] < cutoff
        if months and months[-1][0] == m:
            months[-1] = (m, months[-1][1] + 1, months[-1][2] and old)
        else:
            months.append((m, 1, old))
    top = ''.join(f'<th class="dm{" old" if old else ""}" colspan="{n}">{esc(m)}</th>' for m, n, old in months)
    sub = ''.join(f'<th class="dd{" old" if r["date"] < cutoff else ""}{" named" if patch_name(r["title"]) else ""}">'
                  f'<a href="../patches/{esc(r["id"])}.html" data-tooltip="{esc(patch_title_text(r))}">{esc(r["date"][8:])}</a></th>'
                  for r in rows)
    # fixed layout takes the widths from these: the name, then 30px per patch (0 for an old one while
    # the old patches are hidden) — the automatic layout of ~5k cells with colspans took 0.5 s per toggle
    cols = '<col class="nm">' + ''.join('<col class="old">' if r['date'] < cutoff else '<col>' for r in rows)
    return (f'<colgroup>{cols}</colgroup><thead><tr class="cats"><th class="name"></th>{top}</tr>'
            f'<tr class="cols"><th class="name">{esc(label)}</th>{sub}</tr></thead>')


def matrix_html(entries: list[tuple[str, str, str | None, str, str]], kind: str) -> str:
    """entries: (row key, display name, icon url, page href, extra row class)."""
    d = _collect()
    rows, cells, parts, samples = d['rows'], d['cells'], d['parts'], d['samples']
    cutoff = (date.fromisoformat(rows[-1]['date'][:10]) - timedelta(days=OLD_DAYS)).isoformat() if rows else ''
    pidx = {r['id']: i for i, r in enumerate(rows)}
    tips: list = []
    body: list[str] = []

    def tds(key: str, mine: dict, href: str, part_of_cell: dict | None) -> str:
        out, run, run_old = [], 0, True
        for r in rows:
            counts = mine.get(r['id'])
            old = r['date'] < cutoff
            if run and (counts or old != run_old):
                out.append(_gap(run, run_old))
                run = 0
            if not counts:
                run, run_old = run + 1, old
                continue
            entry = [pidx[r['id']], counts, samples.get(key, {}).get(r['id'], [])]
            if part_of_cell is not None:
                entry.append(part_of_cell.get(r['id'], {}))     # {part: {tag: n}} for the filter
            tips.append(entry)
            # the row's own page at that patch (patch pages are off the bar since 2026-10-03)
            out.append(_cell(counts, f'{href}#p-{r["id"]}', len(tips) - 1, old))
        if run:
            out.append(_gap(run, run_old))
        return ''.join(out)

    for key, name, ic, href, extra in entries:
        mine = cells.get(key, {})
        if not mine:
            continue
        img = f'<img src="{esc(ic)}" alt="" loading="lazy">' if ic else ''
        body.append(f'<tr class="{esc(extra)}" data-search="{esc(name.lower())}" data-name="{esc(name)}" '
                    f'data-icon="{esc(ic or "")}"><td class="name"><a href="{esc(href)}">{img}{esc(name)}</a></td>'
                    f'{tds(key, mine, href, parts.get(key, {}) if kind == "hero" else None)}</tr>')
    data = {'patches': [[r['date'][:10], patch_title_text(r), bool(patch_name(r['title']))] for r in rows],
            'cells': tips, 'icons': {t: tag_svg(t) for t in MATRIX_TAGS}, 'words': TAG_WORDS, 'word1': TAG_WORD_ONE,
            'parts': dict(PARTS)}
    # JSON inside a script element: "</" would end it early
    blob = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    n_old = sum(1 for r in rows if r['date'] < cutoff)
    return (f'<div class="table-fade"><div class="table-scroll"><table class="dyn" id="dyn-{kind}" '
            f'style="--n-all:{len(rows)};--n-new:{len(rows) - n_old}">{_head(rows, cutoff, kind.title())}'
            f'<tbody>{"".join(body)}</tbody></table></div></div>'
            f'<script type="application/json" class="dyn-data" data-for="dyn-{kind}">{blob}</script>')


def toolbar(kind: str, n_hidden_rows: int, hidden_label: str) -> str:
    target = f'#dyn-{kind}'
    # a tag chip SELECTS (only these tags), the same as on a hero / item / unit page (advisor 10-03: here
    # "on" used to hide the tag)
    tags = ''.join(f'<button class="tag {t}" data-dyn-tag="{t}" data-target="{target}">{t.upper()}</button>'
                   for t in ('buff', 'nerf', 'new', 'del', 'rework', 'mech', 'up', 'down'))
    rows_switch = (f'<label class="switch"><input type="checkbox" data-toggle-class="show-extra" data-target="{target}">'
                   f'<span class="track"></span>{esc(hidden_label)} <span class="n">{n_hidden_rows}</span></label>'
                   if n_hidden_rows else '')
    # which part of a hero the tiles show: everything, or only its stats / weapon / abilities
    parts_filter = ''
    if kind == 'hero':
        parts_filter = ('<span class="sep"></span><span class="dyn-parts">' + ''.join(
            f'<button class="px-btn{" on" if p == "all" else ""}" data-part="{p}" data-target="{target}">{esc(lbl)}</button>'
            for p, lbl in (('all', 'All'),) + PARTS) + '</span>')
    return (f'<div class="toolbar dyn-bar"><input type="search" placeholder="Search…" data-search-target="{target} tbody tr">'
            f'<span class="sep"></span>'
            f'<label class="switch"><input type="checkbox" data-toggle-class="show-old" data-target="{target}">'
            f'<span class="track"></span>Older patches</label>'
            f'<label class="switch"><input type="checkbox" data-toggle-class="bvn" data-target="{target}">'
            f'<span class="track"></span>Buff vs nerf</label>{rows_switch}{parts_filter}'
            f'<span class="sep"></span><span class="dyn-tags">{tags}</span></div>')


def hero_entries(heroes: list[dict], rel: str) -> list[tuple]:
    from .common import slug
    out = []
    for h in sorted(heroes, key=lambda h: display_name(h).lower()):
        pre = h.get('state') != 'EHeroDevState_Release'
        # the page is heroes/atlas.html, not hero_atlas.html (every name link was a 404)
        out.append((f'hero:{h["id"]}', display_name(h), hero_icon(h['id'], rel),
                    slug(h['file'], h['id']).split('/', 1)[1], 'extra' if pre else ''))
    return out


def unit_entries(units: list[dict], groups: tuple[tuple[str, str], ...], rel: str) -> list[tuple]:
    """A row per unit FAMILY (unit_families: Slum Shroom I-III, the four Walkers) in the order of the Units
    index (buildings, troopers, neutrals, others); removed ones and helpers hide."""
    from .common import slug
    from .unit_families import families, is_named
    order = {k: i for i, (k, _) in enumerate(groups)}
    out = []
    fams = sorted(families(units).items(),
                  key=lambda kv: (order.get(kv[1][0].get('kind'), len(order)), kv[0].lower()))
    for name, members in fams:
        u = members[0]
        # removed, Hideout / bots / effects, or unnamed (the code's own spawns)
        hidden = not u.get('alive') or u.get('kind') == 'helper' or not is_named(u)
        out.append((f'unit:{u["id"]}', name, entity_icon(u['file'], u['id'], u.get('kind') or 'unit', rel),
                    slug(u['file'], u['id']).split('/', 1)[1], 'extra' if hidden else ''))
    return out


def item_entries(items: list[dict], cards: dict, rel: str) -> list[tuple]:
    from .common import slug
    out = []
    for it in sorted(items, key=lambda e: (e.get('name') or e['id']).lower()):
        info = (cards.get(it['id']) or {}).get('item') or {}
        gone = not it.get('alive') or it.get('disabled') or info.get('disabled')
        name = it['name'] if it.get('name') and it['name'] != it['id'] else pretty_id(it['id'])
        out.append((f'item:{it["id"]}', name, entity_icon(it['file'], it['id'], 'item', rel),
                    slug(it['file'], it['id']).split('/', 1)[1], 'extra' if gone else ''))
    return out
