"""Hero / item changes as a matrix (Sloppy's "Hero Dynamics"): one row per hero or item, one column per
patch, each cell a tile striped in the colours of what the patch did (buff, nerf, new, removed…),
each stripe as tall as its share.

A hero's tile is split in three: base stats | weapon (gun and melee) | abilities, each part with its
own stripes, so a glance tells WHAT changed, not only how much (owner, 2026-10-01). The ▸ before a
hero opens one sub-row per part: base stats, the weapon, every ability with its icon.
Switches: older patches, buff-vs-nerf (one net colour per cell), tag filters, pre-release heroes /
removed items; a search over the rows; a hover card per cell (scripts.js, from the page's JSON)."""
from __future__ import annotations

import json
from datetime import date, timedelta
from functools import lru_cache

from .common import entity_icon, esc, hero_icon, load_json, patch_name, patch_title_text, pretty_id
from .pixel_icons import tag_svg
from .render import TAG_ORDER, TAG_WORDS, counts_text, tag_of

OLD_DAYS = 365            # columns older than this hide behind "Older patches"
MATRIX_TAGS = ('new', 'rework', 'buff', 'nerf', 'del', 'up', 'down', 'mech', 'on', 'off', 'changed')
SAMPLES = 2               # the hover card lists this many biggest changes per part
PARTS = (('stats', 'Base stats'), ('weapon', 'Weapon'), ('abil', 'Abilities'))
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
    subs       {row key: {sub key: {'name', 'part', 'file', 'id', 'kind', 'owner', 'cells': {pid: {tag: n}}}}}
    samples    {row or sub key: {pid: [[what, field, old, new, tag, part], ...]}}"""
    from .cards import gameplay_entities, player_facing
    rows = sorted(load_json('patches/index.json'), key=lambda r: r['date'])
    cells: dict = {}
    parts: dict = {}
    subs: dict = {}
    raw: dict = {}
    for r in rows:
        p = load_json(f'patches/{r["id"]}.json.gz')
        for e in gameplay_entities(p['entities']):
            if e.get('id') == '@shared':
                continue
            if e['file'] == 'heroes.vdata':
                key = f'hero:{e["id"]}'
            elif e.get('owner'):
                key = f'hero:{e["owner"]}'
            elif e.get('kind') == 'item':
                key = f'item:{e["id"]}'
            else:
                continue
            part = part_of(e)
            sub_key = f'{e["file"]}:{e["id"]}'
            sub = subs.setdefault(key, {}).setdefault(sub_key, {
                'name': _display(e), 'part': part, 'file': e['file'], 'id': e['id'], 'kind': e.get('kind', ''),
                'owner': e.get('owner'), 'cells': {}})
            cell = cells.setdefault(key, {}).setdefault(r['id'], {})
            pcell = parts.setdefault(key, {}).setdefault(r['id'], {}).setdefault(part, {})
            scell = sub['cells'].setdefault(r['id'], {})
            for c in player_facing(e['changes']):
                t = tag_of(c)[0]
                for d in (cell, pcell, scell):
                    d[t] = d.get(t, 0) + 1
                s = (_display(e), c.get('label') or '', str(c.get('old_s') or ''), str(c.get('new_s') or ''), t, part,
                     abs(c['pct']) if isinstance(c.get('pct'), (int, float)) else 0)
                raw.setdefault(key, {}).setdefault(r['id'], []).append(s)
                raw.setdefault(sub_key, {}).setdefault(r['id'], []).append(s)
    samples: dict = {}
    for k, per in raw.items():
        for pid, lst in per.items():
            ranked = sorted(lst, key=lambda x: (-x[6], TAG_ORDER.get(x[4], 9)))
            picked, seen = [], {}
            for x in ranked:                      # the biggest per part, the parts in their order
                if seen.get(x[5], 0) < SAMPLES:
                    seen[x[5]] = seen.get(x[5], 0) + 1
                    picked.append(list(x[:6]))
            order = {p: i for i, (p, _) in enumerate(PARTS)}
            samples.setdefault(k, {})[pid] = sorted(picked, key=lambda x: order.get(x[5], 9))
    return {'rows': rows, 'cells': cells, 'parts': parts, 'subs': subs, 'samples': samples}


def _net(counts: dict[str, int]) -> str:
    good = counts.get('buff', 0) + counts.get('new', 0) + counts.get('on', 0)
    bad = counts.get('nerf', 0) + counts.get('del', 0) + counts.get('off', 0)
    return 'net-buff' if good > bad else 'net-nerf' if bad > good else 'net-mix'


def _stripes(counts: dict[str, int]) -> str:
    return ''.join(f'<span class="st t-{t}" style="flex:{n}"></span>'
                   for t, n in sorted(counts.items(), key=lambda kv: TAG_ORDER.get(kv[0], 9)))


def _cell(prow: dict, counts: dict[str, int] | None, href: str, old: bool, k: int | None,
          split: dict | None = None) -> str:
    cls = 'dc old' if old else 'dc'
    if not counts:
        return f'<td class="{cls}"></td>'
    total = sum(counts.values())
    if split is not None:
        # stats | weapon | abilities: each third striped by its own changes, empty when untouched
        inner = ''.join(f'<span class="seg s-{p}{"" if split.get(p) else " empty"}">{_stripes(split.get(p, {}))}</span>'
                        for p, _ in PARTS)
        tile = 'dsq split'
    else:
        inner, tile = _stripes(counts), 'dsq'
    tip = f'{patch_title_text(prow)}: {counts_text(counts)}'
    data_k = f' data-k="{k}"' if k is not None else ''
    return (f'<td class="{cls}"><a class="{tile} {_net(counts)}" href="{esc(href)}"{data_k} aria-label="{esc(tip)}">'
            f'{inner}<span class="dn">{total}</span></a></td>')


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
    return f'<thead><tr class="cats"><th class="name"></th>{top}</tr><tr class="cols"><th class="name">{esc(label)}</th>{sub}</tr></thead>'


def _sub_order(sub: dict) -> tuple:
    order = {p: i for i, (p, _) in enumerate(PARTS)}
    return order.get(sub['part'], 9), sub['name'].lower()


def matrix_html(entries: list[tuple[str, str, str | None, str, str]], kind: str, rel: str = '../') -> str:
    """entries: (row key, display name, icon url, page href, extra row class)."""
    d = _collect()
    rows, cells, parts, subs, samples = d['rows'], d['cells'], d['parts'], d['subs'], d['samples']
    cutoff = (date.fromisoformat(rows[-1]['date'][:10]) - timedelta(days=OLD_DAYS)).isoformat() if rows else ''
    pidx = {r['id']: i for i, r in enumerate(rows)}
    tips: list = []
    body: list[str] = []

    def tds(key: str, mine: dict, anchor: str, split_of: dict | None) -> str:
        out = []
        for r in rows:
            counts = mine.get(r['id'])
            k = None
            if counts:
                k = len(tips)
                tips.append([pidx[r['id']], counts, samples.get(key, {}).get(r['id'], [])])
            split = (split_of or {}).get(r['id'], {}) if split_of is not None else None
            out.append(_cell(r, counts, f'../patches/{r["id"]}.html{anchor}', r['date'] < cutoff, k, split))
        return ''.join(out)

    for key, name, ic, href, extra in entries:
        mine = cells.get(key, {})
        if not mine:
            continue
        img = f'<img src="{esc(ic)}" alt="" loading="lazy">' if ic else ''
        anchor = f'#c-{key.split(":", 1)[1]}' if kind == 'hero' else ''
        rid = key.split(':', 1)[1]
        is_hero = kind == 'hero'
        toggle = (f'<button class="dyn-open" data-open="{esc(rid)}" aria-label="Show stats, weapon and abilities">'
                  f'▸</button>' if is_hero else '')
        body.append(f'<tr class="{esc(extra)}" data-search="{esc(name.lower())}" data-name="{esc(name)}" '
                    f'data-icon="{esc(ic or "")}"><td class="name"><span class="nm-wrap">{toggle}<a href="{esc(href)}">{img}{esc(name)}</a></span></td>'
                    f'{tds(key, mine, anchor, parts.get(key, {}) if is_hero else None)}</tr>')
        if not is_hero:
            continue
        for sub_key, sub in sorted(subs.get(key, {}).items(), key=lambda kv: _sub_order(kv[1])):
            if not sub['cells']:
                continue
            sic = (hero_icon(sub['id'], rel) if sub['file'] == 'heroes.vdata'
                   else entity_icon(sub['file'], sub['id'], sub['kind'], rel, sub['name'], sub['owner']))
            simg = f'<img src="{esc(sic)}" alt="" loading="lazy">' if sic else ''
            label = dict(PARTS)[sub['part']] if sub['part'] == 'stats' else sub['name']
            body.append(f'<tr class="sub p-{sub["part"]} {esc(extra)}" data-parent="{esc(rid)}" '
                        f'data-search="{esc(name.lower())} {esc(label.lower())}" data-name="{esc(name)} · {esc(label)}" '
                        f'data-icon="{esc(sic or "")}"><td class="name"><span class="sub-l">{simg}{esc(label)}</span></td>'
                        f'{tds(sub_key, sub["cells"], anchor, None)}</tr>')
    data = {'patches': [[r['date'][:10], patch_title_text(r), bool(patch_name(r['title']))] for r in rows],
            'cells': tips, 'icons': {t: tag_svg(t) for t in MATRIX_TAGS}, 'words': TAG_WORDS,
            'parts': dict(PARTS)}
    # JSON inside a script element: "</" would end it early
    blob = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    return (f'<div class="table-fade"><div class="table-scroll"><table class="dyn" id="dyn-{kind}">{_head(rows, cutoff, kind.title())}'
            f'<tbody>{"".join(body)}</tbody></table></div></div>'
            f'<script type="application/json" class="dyn-data" data-for="dyn-{kind}">{blob}</script>')


def toolbar(kind: str, n_hidden_rows: int, hidden_label: str) -> str:
    target = f'#dyn-{kind}'
    tags = ''.join(f'<button class="tag {t}" data-toggle-class="hide-{t}" data-target="{target}">{t.upper()}</button>'
                   for t in ('buff', 'nerf', 'new', 'del', 'rework', 'mech', 'up', 'down'))
    rows_switch = (f'<label class="switch"><input type="checkbox" data-toggle-class="show-extra" data-target="{target}">'
                   f'<span class="track"></span>{esc(hidden_label)} <span class="n">{n_hidden_rows}</span></label>'
                   if n_hidden_rows else '')
    # how to read a hero's tile: the three parts, and "open all" for their rows
    legend = ''
    if kind == 'hero':
        legend = ('<span class="sep"></span><span class="dyn-legend"><span class="dsq split demo">'
                  '<span class="seg s-stats"><span class="st t-buff"></span></span>'
                  '<span class="seg s-weapon"><span class="st t-nerf"></span></span>'
                  '<span class="seg s-abil"><span class="st t-new"></span></span></span>'
                  '<span>stats · weapon · abilities</span></span>'
                  f'<label class="switch"><input type="checkbox" data-toggle-class="open-all" data-target="{target}">'
                  '<span class="track"></span>Split rows</label>')
    return (f'<div class="toolbar dyn-bar"><input type="search" placeholder="Search…" data-search-target="{target} tbody tr:not(.sub)">'
            f'<span class="sep"></span>'
            f'<label class="switch"><input type="checkbox" data-toggle-class="show-old" data-target="{target}">'
            f'<span class="track"></span>Older patches</label>'
            f'<label class="switch"><input type="checkbox" data-toggle-class="bvn" data-target="{target}">'
            f'<span class="track"></span>Buff vs nerf</label>{rows_switch}{legend}'
            f'<span class="sep"></span><span class="dyn-tags">{tags}</span></div>')


def hero_entries(heroes: list[dict], rel: str) -> list[tuple]:
    out = []
    for h in sorted(heroes, key=lambda h: (h.get('name') or h['id']).lower()):
        pre = h.get('state') != 'EHeroDevState_Release'
        out.append((f'hero:{h["id"]}', h.get('name') or h['id'], hero_icon(h['id'], rel), f'{h["id"]}.html',
                    'extra' if pre else ''))
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
