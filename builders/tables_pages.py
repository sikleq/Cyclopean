"""Stats tables (heroes, units & buildings): current value in every cell,
hover a cell with a dot for its full change history."""
from __future__ import annotations

import json
from typing import Callable

from .common import entity_icon, esc, hero_icon, load_json, page, write

UNIT_KIND_LABEL = {'building': 'Building', 'trooper': 'Trooper', 'neutral': 'Neutral'}


def _fmt(v, digits: int) -> str:
    if v is None:
        return '<span class="dash">—</span>'
    s = f'{v:.{max(digits, 0)}f}'
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return s


def render_table(cols: list[dict], rows: list[dict], name_cell: Callable[[dict], str], name_title: str,
                 extra_cls: Callable[[dict, dict], list[str]] | None = None) -> str:
    groups: list[list] = []
    for c in cols:
        if groups and groups[-1][0] == c['group']:
            groups[-1][1] += 1
        else:
            groups.append([c['group'], 1])
    first_of_group = {cols[sum(n for _, n in groups[:i])]['key'] for i in range(len(groups))}
    cat_row = '<tr class="cats"><th class="name"></th>' + ''.join(
        f'<th colspan="{n}">{esc(g)}</th>' for g, n in groups) + '</tr>'
    col_row = f'<tr class="cols"><th class="name" data-col="name">{esc(name_title)}</th>' + ''.join(
        f'<th data-col="{esc(c["key"])}" class="{"grp-start" if c["key"] in first_of_group else ""}">'
        f'{esc(c["label"])}</th>' for c in cols) + '</tr>'
    body = []
    for r in rows:
        cells = [name_cell(r)]
        for c in cols:
            v = r['values'].get(c['key'])
            hist = r['history'].get(c['key'])
            cls = ['grp-start'] if c['key'] in first_of_group else []
            if extra_cls:
                cls += extra_cls(r, c)
            attrs = f' data-col="{c["key"]}" data-sort="{"" if v is None else v}" data-pol="{c["pol"]}" data-digits="{c["digits"]}"'
            if hist:
                cls.append('has-hist')
                attrs += (f' data-hist="{esc(json.dumps(hist, separators=(",", ":")))}"'
                          f' data-title="{esc(r["name"])} · {esc(c["label"])}"')
            cells.append(f'<td class="{" ".join(cls)}"{attrs}>{_fmt(v, c["digits"])}</td>')
        body.append(f'<tr data-search="{esc(r["name"].lower())}">' + ''.join(cells) + '</tr>')
    return (f'<div class="table-scroll"><table class="stats"><thead>{cat_row}{col_row}</thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def _toolbar(placeholder: str, legend_spirit: bool) -> str:
    spirit = '<span class="chip legend-spirit">scales with Spirit</span>' if legend_spirit else ''
    return ('<div class="toolbar">'
            f'<input type="search" placeholder="{esc(placeholder)}" data-search-target="table.stats tbody tr">'
            '<span class="sep"></span><button class="px-btn" data-heatmap>Heatmap</button>'
            f'<span class="sep"></span><span class="chip legend-hist">has history</span>{spirit}</div>')


def heroes_table() -> str:
    rel = '../'
    t = load_json('tables/heroes.json')

    def name_cell(h):
        ic = hero_icon(h['id'], rel)
        pre = '<span class="pre">PRE</span>' if h['state'] == 'prerelease' else ''
        img_html = f'<img class="px" src="{esc(ic)}" alt="" loading="lazy">' if ic else ''
        return (f'<td class="name" data-col="name" data-sort="{esc(h["name"])}"><a href="{rel}heroes/'
                f'{esc(h["id"].removeprefix("hero_"))}.html">{img_html}{esc(h["name"])}{pre}</a></td>')

    table = render_table(t['columns'], t['heroes'], name_cell, 'Hero',
                         lambda r, c: ['spirit'] if c['key'] in r.get('spirit_scaled', []) else [])
    body = '<h1>Hero Stats</h1>' + tabs('heroes') + _toolbar('Hero…', True) + table
    return page('Hero Stats', body, rel, 'tables', build=t['build'],
                description='Deadlock hero stats with the full history of every value')


def units_table() -> str:
    rel = '../'
    t = load_json('tables/units.json')

    def name_cell(u):
        ic = entity_icon('npc_units.vdata', u['id'], u['kind'], rel)
        img_html = f'<img class="px" src="{esc(ic)}" alt="" loading="lazy">' if ic else ''
        kind = UNIT_KIND_LABEL.get(u['kind'], u['kind'])
        return (f'<td class="name" data-col="name" data-sort="{esc(u["name"])}"><a href="{rel}units/{esc(u["id"])}.html">'
                f'{img_html}{esc(u["name"])}<span class="pre">{esc(kind)}</span></a></td>')

    table = render_table(t['columns'], t['units'], name_cell, 'Unit')
    body = '<h1>Units & Buildings</h1>' + tabs('units') + _toolbar('Unit…', False) + table
    return page('Units & Buildings', body, rel, 'tables', build=t['build'],
                description='Deadlock troopers, guardians, walkers, patron and neutrals with the history of every value')


def items_table() -> str:
    rel = '../'
    t = load_json('tables/items.json')

    def name_cell(it):
        ic = entity_icon('abilities.vdata', it['id'], 'item', rel)
        img_html = f'<img class="px" src="{esc(ic)}" alt="" loading="lazy">' if ic else ''
        return (f'<td class="name" data-col="name" data-sort="{esc(it["name"])}"><a href="{rel}items/'
                f'{esc(it["id"].removeprefix("upgrade_"))}.html">{img_html}{esc(it["name"])}'
                f'<span class="pre">{esc(it["slot"])} · {esc(it["activation"])}</span></a></td>')

    table = render_table(t['columns'], t['items'], name_cell, 'Item')
    body = '<h1>Items</h1>' + tabs('items') + _toolbar('Item…', False) + table
    return page('Item Stats', body, rel, 'tables', build=t['build'],
                description='Deadlock shop items with the history of every value')


def tabs(active: str) -> str:
    items = (('heroes', 'Heroes', 'heroes.html'), ('units', 'Units & Buildings', 'units.html'),
             ('items', 'Items', 'items.html'))
    return '<div class="flex table-tabs">' + ''.join(
        f'<a class="px-btn{" on" if k == active else ""}" href="{href}">{esc(lbl)}</a>' for k, lbl, href in items) + '</div>'


def build_all() -> int:
    write('tables/heroes.html', heroes_table())
    write('tables/units.html', units_table())
    write('tables/items.html', items_table())
    return 3
