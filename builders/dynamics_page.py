"""Hero / item changes as a matrix (Sloppy's "Hero Dynamics"): one row per hero or item, one column per
patch, each cell a square striped in the colours of what the patch did (buff, nerf, new, removed…),
the stripes as tall as their share. Switches: older patches, buff-vs-nerf (one net colour per cell),
tag filters, pre-release heroes / removed items; a search over the rows."""
from __future__ import annotations

import json
from datetime import date, timedelta
from functools import lru_cache

from .common import entity_icon, esc, hero_icon, load_json, patch_name, patch_title_text, pretty_id
from .pixel_icons import tag_svg
from .render import TAG_ORDER, TAG_WORDS, counts_text, tag_of

OLD_DAYS = 365            # columns older than this hide behind "Older patches"
MATRIX_TAGS = ('new', 'rework', 'buff', 'nerf', 'del', 'up', 'down', 'mech', 'on', 'off', 'changed')


SAMPLES = 3              # the tooltip lists a cell's biggest changes, this many


def _sample(e: dict, c: dict) -> tuple:
    """(what, field, old, new, tag, |%|) for the tooltip: the entity's display name, never an id."""
    name = e.get('name') if e.get('name') and e.get('name') != e.get('id') else pretty_id(e['id'], e.get('owner'))
    if e['file'] == 'heroes.vdata':
        name = 'Base stats'
    return (name, c.get('label') or '', str(c.get('old_s') or ''), str(c.get('new_s') or ''), tag_of(c)[0],
            abs(c['pct']) if isinstance(c.get('pct'), (int, float)) else 0)


@lru_cache(maxsize=1)
def _cells() -> tuple[list[dict], dict[str, dict[str, dict[str, int]]]]:
    """(patch rows oldest first, {row key: {patch id: {tag: count}}}). A hero's row counts its own
    stats and every ability it owns; an item's row is the item. Same counting rule as everywhere."""
    rows, cells, _ = _cells_and_samples()
    return rows, cells


@lru_cache(maxsize=1)
def _cells_and_samples() -> tuple[list[dict], dict, dict]:
    from .cards import gameplay_entities, player_facing
    rows = sorted(load_json('patches/index.json'), key=lambda r: r['date'])
    out: dict[str, dict[str, dict[str, int]]] = {}
    samples: dict[str, dict[str, list[tuple]]] = {}
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
            cell = out.setdefault(key, {}).setdefault(r['id'], {})
            sm = samples.setdefault(key, {}).setdefault(r['id'], [])
            for c in player_facing(e['changes']):
                t = tag_of(c)[0]
                cell[t] = cell.get(t, 0) + 1
                sm.append(_sample(e, c))
    for per in samples.values():
        for pid, lst in per.items():
            # biggest moves first, then the tag order (new, rework, buff, nerf, ...)
            per[pid] = [list(x[:5]) for x in sorted(lst, key=lambda x: (-x[5], TAG_ORDER.get(x[4], 9)))[:SAMPLES]]
    return rows, out, samples


def _net(counts: dict[str, int]) -> str:
    good = counts.get('buff', 0) + counts.get('new', 0) + counts.get('on', 0)
    bad = counts.get('nerf', 0) + counts.get('del', 0) + counts.get('off', 0)
    return 'net-buff' if good > bad else 'net-nerf' if bad > good else 'net-mix'


def _cell(pid: str, prow: dict, counts: dict[str, int] | None, href: str, old: bool, k: int | None = None) -> str:
    cls = 'dc old' if old else 'dc'
    if not counts:
        return f'<td class="{cls}"></td>'
    stripes = ''.join(f'<span class="st t-{t}" style="flex:{n}"></span>'
                      for t, n in sorted(counts.items(), key=lambda kv: TAG_ORDER.get(kv[0], 9)))
    total = sum(counts.values())
    # the hover card is drawn by scripts.js from the page's .dyn-data (who, which patch, counts with
    # their icons, the biggest changes); aria-label keeps a plain-text version
    tip = f'{patch_title_text(prow)}: {counts_text(counts)}'
    data_k = f' data-k="{k}"' if k is not None else ''
    return (f'<td class="{cls}"><a class="dsq {_net(counts)}" href="{esc(href)}"{data_k} aria-label="{esc(tip)}">'
            f'{stripes}<span class="dn">{total}</span></a></td>')


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
    rows, cells, samples = _cells_and_samples()
    cutoff = (date.fromisoformat(rows[-1]['date'][:10]) - timedelta(days=OLD_DAYS)).isoformat() if rows else ''
    pidx = {r['id']: i for i, r in enumerate(rows)}
    tips: list = []
    body = []
    for key, name, ic, href, extra in entries:
        mine = cells.get(key, {})
        if not mine:
            continue
        img = f'<img src="{esc(ic)}" alt="" loading="lazy">' if ic else ''
        anchor = f'#c-{key.split(":", 1)[1]}' if kind == 'hero' else ''
        parts = []
        for r in rows:
            counts = mine.get(r['id'])
            k = None
            if counts:
                k = len(tips)
                tips.append([len(body), pidx[r['id']], counts, samples.get(key, {}).get(r['id'], [])])
            parts.append(_cell(r['id'], r, counts, f'../patches/{r["id"]}.html{anchor}', r['date'] < cutoff, k))
        tds = ''.join(parts)
        body.append(f'<tr class="{esc(extra)}" data-search="{esc(name.lower())}" data-name="{esc(name)}" '
                    f'data-icon="{esc(ic or "")}"><td class="name"><a href="{esc(href)}">{img}{esc(name)}</a></td>{tds}</tr>')
    data = {'patches': [[r['date'][:10], patch_title_text(r), bool(patch_name(r['title']))] for r in rows],
            'cells': tips, 'icons': {t: tag_svg(t) for t in MATRIX_TAGS}, 'words': TAG_WORDS}
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
    return (f'<div class="toolbar dyn-bar"><input type="search" placeholder="Search…" data-search-target="{target} tbody tr">'
            f'<span class="sep"></span>'
            f'<label class="switch"><input type="checkbox" data-toggle-class="show-old" data-target="{target}">'
            f'<span class="track"></span>Older patches</label>'
            f'<label class="switch"><input type="checkbox" data-toggle-class="bvn" data-target="{target}">'
            f'<span class="track"></span>Buff vs nerf</label>{rows_switch}'
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
