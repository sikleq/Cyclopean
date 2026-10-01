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

from .common import entity_icon, esc, hero_icon, load_json, patch_name, patch_title_text, pretty_id
from .pixel_icons import tag_svg
from .render import TAG_ORDER, TAG_WORDS, counts_text, tag_of

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
    cells: dict = {}
    parts: dict = {}
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
            elif e['file'] == 'npc_units.vdata':
                key = f'unit:{e["id"]}'
            else:
                continue
            part = part_of(e)
            cell = cells.setdefault(key, {}).setdefault(r['id'], {})
            pcell = parts.setdefault(key, {}).setdefault(r['id'], {}).setdefault(part, {})
            for c in player_facing(e['changes']):
                t = tag_of(c)[0]
                for d in (cell, pcell):
                    d[t] = d.get(t, 0) + 1
                s = (_display(e), c.get('label') or '', str(c.get('old_s') or ''), str(c.get('new_s') or ''), t, part,
                     abs(c['pct']) if isinstance(c.get('pct'), (int, float)) else 0)
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


def _stripes(counts: dict[str, int]) -> str:
    return ''.join(f'<span class="st t-{t}" style="flex:{n}"></span>'
                   for t, n in sorted(counts.items(), key=lambda kv: TAG_ORDER.get(kv[0], 9)))


def _cell(prow: dict, counts: dict[str, int] | None, href: str, old: bool, k: int | None) -> str:
    cls = 'dc old' if old else 'dc'
    if not counts:
        return f'<td class="{cls}"></td>'
    total = sum(counts.values())
    tip = f'{patch_title_text(prow)}: {counts_text(counts)}'
    data_k = f' data-k="{k}"' if k is not None else ''
    return (f'<td class="{cls}"><a class="dsq {_net(counts)}" href="{esc(href)}"{data_k} aria-label="{esc(tip)}">'
            f'{_stripes(counts)}<span class="dn">{total}</span></a></td>')


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


def matrix_html(entries: list[tuple[str, str, str | None, str, str]], kind: str) -> str:
    """entries: (row key, display name, icon url, page href, extra row class)."""
    d = _collect()
    rows, cells, parts, samples = d['rows'], d['cells'], d['parts'], d['samples']
    cutoff = (date.fromisoformat(rows[-1]['date'][:10]) - timedelta(days=OLD_DAYS)).isoformat() if rows else ''
    pidx = {r['id']: i for i, r in enumerate(rows)}
    tips: list = []
    body: list[str] = []

    def tds(key: str, mine: dict, anchor: str, part_of_cell: dict | None) -> str:
        out = []
        for r in rows:
            counts = mine.get(r['id'])
            k = None
            if counts:
                k = len(tips)
                entry = [pidx[r['id']], counts, samples.get(key, {}).get(r['id'], [])]
                if part_of_cell is not None:
                    entry.append(part_of_cell.get(r['id'], {}))     # {part: {tag: n}} for the filter
                tips.append(entry)
            out.append(_cell(r, counts, f'../patches/{r["id"]}.html{anchor}', r['date'] < cutoff, k))
        return ''.join(out)

    for key, name, ic, href, extra in entries:
        mine = cells.get(key, {})
        if not mine:
            continue
        img = f'<img src="{esc(ic)}" alt="" loading="lazy">' if ic else ''
        anchor = f'#c-{key.split(":", 1)[1]}' if kind == 'hero' else ''
        body.append(f'<tr class="{esc(extra)}" data-search="{esc(name.lower())}" data-name="{esc(name)}" '
                    f'data-icon="{esc(ic or "")}"><td class="name"><a href="{esc(href)}">{img}{esc(name)}</a></td>'
                    f'{tds(key, mine, anchor, parts.get(key, {}) if kind == "hero" else None)}</tr>')
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
    out = []
    for h in sorted(heroes, key=lambda h: (h.get('name') or h['id']).lower()):
        pre = h.get('state') != 'EHeroDevState_Release'
        out.append((f'hero:{h["id"]}', h.get('name') or h['id'], hero_icon(h['id'], rel), f'{h["id"]}.html',
                    'extra' if pre else ''))
    return out


def unit_entries(units: list[dict], groups: tuple[tuple[str, str], ...], rel: str) -> list[tuple]:
    """Units in the order of the Units index (buildings, troopers, neutrals, others); removed ones hide."""
    from .common import slug
    order = {k: i for i, (k, _) in enumerate(groups)}
    out = []
    for u in sorted(units, key=lambda u: (order.get(u.get('kind'), len(order)), (u.get('name') or u['id']).lower())):
        name = u['name'] if u.get('name') and u['name'] != u['id'] else pretty_id(u['id'])
        hidden = not u.get('alive') or u.get('kind') == 'helper'      # removed, or Hideout / bots / effects
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
