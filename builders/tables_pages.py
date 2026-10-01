"""Stats tables (heroes, units & buildings): current value in every cell,
hover a cell with a dot for its full change history."""
from __future__ import annotations

import json
from typing import Callable

from .common import entity_icon, esc, hero_icon, load_json, page, write

UNIT_KIND_LABEL = {'building': 'Building', 'trooper': 'Trooper', 'neutral': 'Neutral'}

# Hero table layout: the group header gives the context, so column headers stay one
# short line ("+/boon" under Vitality); the full label is the header's tooltip.
# Niche numbers (spread, gravity, collision…) sit in "Details", hidden until asked for.
# Compared with the user's sheet (docs/reference/hero-stats-sheet.md): its core columns
# are all here; the sheet's derived ones (per-level tables) live on the hero pages.
DETAILS = 'Details'
HERO_LAYOUT = (
    ('Weapon', (('dps', 'DPS'), ('dps_max', 'Max DPS'), ('bullet_dmg', 'Bullet'), ('bullet_dmg_lvl', '+/boon'),
                ('bullet_dmg_max', 'Max bullet'), ('pellets', 'Pellets'), ('bps', 'Shots/s'), ('clip', 'Ammo'),
                ('reload', 'Reload'), ('reload_full', 'Full reload'), ('headshot', 'Headshot'),
                ('bullet_speed', 'Speed'), ('falloff_start', 'Falloff'), ('falloff_end', 'Falloff end'))),
    ('Melee', (('light_melee', 'Light'), ('melee_lvl', '+/boon'), ('heavy_melee', 'Heavy'))),
    ('Vitality', (('hp', 'HP'), ('hp_lvl', '+/boon'), ('hp_regen', 'Regen'), ('bullet_resist', 'Bullet res'),
                  ('bullet_resist_lvl', '+/boon'), ('spirit_resist', 'Spirit res'), ('spirit_resist_lvl', '+/boon'),
                  ('headshot_taken', 'HS taken'))),
    ('Mobility', (('move', 'Move'), ('sprint', 'Sprint'), ('stamina', 'Stamina'), ('stamina_regen', 'Stam. regen'),
                  ('crouch', 'Crouch'), ('ground_dash', 'Dash'), ('air_dash', 'Air dash'))),
    ('Spirit', (('spirit_lvl', '+/boon'),)),
    (DETAILS, (('cycle', 'Interval'), ('full_clip', 'Clip time'), ('burst', 'Burst'), ('burst_cycle', 'Burst gap'),
               ('bullet_radius', 'Radius'), ('spread', 'Spread'), ('pellet_spread', 'Pellet spread'),
               ('gravity', 'Gravity'), ('lifetime', 'Lifetime'), ('range', 'Range'), ('range_lvl', 'Range/boon'),
               ('collision_r', 'Coll. radius'), ('collision_h', 'Coll. height'))),
)


def laid_out(cols: list[dict], layout) -> list[dict]:
    """Columns in display order with their display group and short header; a column the
    layout does not know yet (new in the data) is never dropped: it goes to Details."""
    by_key = {c['key']: c for c in cols}
    out, seen = [], set()
    for group, entries in layout:
        for key, short in entries:
            if key in by_key:
                out.append({**by_key[key], 'group': group, 'short': short})
                seen.add(key)
    out += [{**c, 'group': DETAILS} for c in cols if c['key'] not in seen]
    return sorted(out, key=lambda c: c['group'] == DETAILS)        # stable: Details last


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

    def gcls(group: str) -> str:
        return ' g-details' if group == DETAILS else ''
    cat_row = '<tr class="cats"><th class="name"></th>' + ''.join(
        f'<th colspan="{n}" class="cat{gcls(g)}">{esc(g)}</th>' for g, n in groups) + '</tr>'

    def head(c: dict) -> str:
        short = c.get('short')
        tip = f' data-tooltip="{esc(c["label"])}"' if short and short != c['label'] else ''
        cls = ('grp-start' if c['key'] in first_of_group else '') + gcls(c['group'])
        return f'<th data-col="{esc(c["key"])}" class="{cls.strip()}"{tip}>{esc(short or c["label"])}</th>'
    col_row = (f'<tr class="cols"><th class="name" data-col="name">{esc(name_title)}</th>'
               + ''.join(head(c) for c in cols) + '</tr>')
    body = []
    for r in rows:
        cells = [name_cell(r)]
        for c in cols:
            v = r['values'].get(c['key'])
            hist = r['history'].get(c['key'])
            cls = ['grp-start'] if c['key'] in first_of_group else []
            if c['group'] == DETAILS:
                cls.append('g-details')
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


def _toolbar(placeholder: str, legend_spirit: bool, details: bool = False) -> str:
    spirit = '<span class="chip legend-spirit">scales with Spirit</span>' if legend_spirit else ''
    more = ('<button class="px-btn" data-toggle-class="show-details" data-target=".table-scroll">Details</button>'
            if details else '')
    return ('<div class="toolbar">'
            f'<input type="search" placeholder="{esc(placeholder)}" data-search-target="table.stats tbody tr">'
            f'<span class="sep"></span><button class="px-btn" data-heatmap>Heatmap</button>{more}'
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

    table = render_table(laid_out(t['columns'], HERO_LAYOUT), t['heroes'], name_cell, 'Hero',
                         lambda r, c: ['spirit'] if c['key'] in r.get('spirit_scaled', []) else [])
    body = '<h1>Hero Stats</h1>' + tabs('heroes') + _toolbar('Hero…', True, details=True) + table
    return page('Hero Stats', body, rel, 'tables', build=t['build'],
                description='Deadlock hero stats with the full history of every value', wide=True)


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
                description='Deadlock troopers, guardians, walkers, patron and neutrals with the history of every value', wide=True)


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
                description='Deadlock shop items with the history of every value', wide=True)


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
