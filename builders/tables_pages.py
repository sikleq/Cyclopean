"""Stats tables (heroes, units & buildings): current value in every cell,
hover a cell with a dot for its full change history."""
from __future__ import annotations

import json
from typing import Callable

from .common import entity_icon, esc, hero_icon, load_json, page, write


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


RECENT_DAYS = 45      # the corner dot marks values changed this recently; older history is on hover only


def _recent_cutoff(as_of: str | None) -> str:
    from datetime import date, timedelta
    if not as_of:
        return '9999'
    return (date.fromisoformat(as_of[:10]) - timedelta(days=RECENT_DAYS)).isoformat()


def non_empty(cols: list[dict], rows: list[dict]) -> list[dict]:
    """Columns with at least one value in these rows (a category's table drops the others)."""
    return [c for c in cols if any(r['values'].get(c['key']) is not None for r in rows)]


def render_table(cols: list[dict], rows: list[dict], name_cell: Callable[[dict], str], name_title: str,
                 extra_cls: Callable[[dict, dict], list[str]] | None = None, as_of: str | None = None,
                 row_cls: Callable[[dict], str] | None = None, table_id: str = '',
                 section_of: Callable[[dict], str] | None = None,
                 cell_attrs: Callable[[dict, dict], str] | None = None,
                 row_attrs: Callable[[dict], str] | None = None) -> str:
    cutoff = _recent_cutoff(as_of)
    groups: list[list] = []
    for c in cols:
        if groups and groups[-1][0] == c['group']:
            groups[-1][1] += 1
        else:
            groups.append([c['group'], 1])
    first_of_group = {cols[sum(n for _, n in groups[:i])]['key'] for i in range(len(groups))}
    # every other column group gets a faint tint so the eye keeps its place in 46 columns
    odd_groups = {g for i, (g, _) in enumerate(groups) if i % 2}

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
    body: list[str] = []
    last_section: list[str | None] = [None]
    for r in rows:
        cells = [name_cell(r)]
        for c in cols:
            v = r['values'].get(c['key'])
            hist = r['history'].get(c['key'])
            cls = ['grp-start'] if c['key'] in first_of_group else []
            if c['group'] == DETAILS:
                cls.append('g-details')
            if c['group'] in odd_groups:
                cls.append('g-odd')
            if extra_cls:
                cls += extra_cls(r, c)
            attrs = f' data-col="{c["key"]}" data-sort="{"" if v is None else v}" data-pol="{c["pol"]}" data-digits="{c["digits"]}"'
            if cell_attrs:
                attrs += cell_attrs(r, c)
            tint = COLUMN_TINT.get(c['key'])
            if tint:
                cls.append(tint)
            if hist:
                cls.append('has-hist')
                if str(hist[-1][1])[:10] >= cutoff:
                    cls.append('recent')
                attrs += (f' data-hist="{esc(json.dumps(hist, separators=(",", ":")))}"'
                          f' data-title="{esc(r["name"])} · {esc(c["label"])}"')
            cells.append(f'<td class="{" ".join(cls)}"{attrs}>{_fmt(v, c["digits"])}</td>')
        if section_of:
            sec = section_of(r)
            if sec != last_section[0]:
                last_section[0] = sec
                body.append(f'<tr class="sec"><td class="name">{sec}</td><td colspan="{len(cols)}"></td></tr>')
        rc = f' class="{row_cls(r)}"' if row_cls and row_cls(r) else ''
        ra = row_attrs(r) if row_attrs else ''
        body.append(f'<tr{rc}{ra} data-search="{esc(r["name"].lower())}">' + ''.join(cells) + '</tr>')
    # the fade on the right edge says "more columns this way" until the table is scrolled to its end
    tid = f' id="{esc(table_id)}"' if table_id else ''
    return (f'<div class="table-fade"><div class="table-scroll"><table class="stats"{tid}><thead>{cat_row}{col_row}</thead>'
            f'<tbody>{"".join(body)}</tbody></table></div></div>')


def _toolbar(placeholder: str, details: bool = False, extra: str = '') -> str:
    more = ('<button class="px-btn" data-toggle-class="show-details" data-target=".table-scroll">Details</button>'
            if details else '')
    return ('<div class="toolbar">'
            f'<input type="search" placeholder="{esc(placeholder)}" data-search-target="table.stats tbody tr:not(.sec)">'
            f'<span class="sep"></span><label class="switch"><input type="checkbox" data-heatmap>'
            f'<span class="track"></span>Heatmap</label>{more}{extra}</div>')


MAX_BOONS = 35            # levels 2-36 each give a boon (heroes.vdata m_mapLevelInfo)
# a column's value at N boons = base + N x its per-boon column (DPS grows with the bullet's damage)
BOON_PER = {'hp': 'hp_lvl', 'bullet_dmg': 'bullet_dmg_lvl', 'light_melee': 'melee_lvl', 'heavy_melee': 'melee_lvl',
            'bullet_resist': 'bullet_resist_lvl', 'spirit_resist': 'spirit_resist_lvl'}
# numbers tinted by what they are, as Sloppy tints HP green and mana blue
COLUMN_TINT = {'hp': 'tint-vit', 'hp_lvl': 'tint-vit', 'hp_regen': 'tint-vit', 'dps': 'tint-wpn', 'dps_max': 'tint-wpn',
               'bullet_dmg': 'tint-wpn', 'bullet_dmg_lvl': 'tint-wpn', 'bullet_dmg_max': 'tint-wpn',
               'spirit_lvl': 'tint-spi', 'spirit': 'tint-spi'}


def boon_attrs(r: dict, c: dict) -> str:
    vals = r['values']
    key = c['key']
    if key in BOON_PER and vals.get(key) is not None and vals.get(BOON_PER[key]):
        return f' data-per="{vals[BOON_PER[key]]}"'
    if key == 'dps' and vals.get('dps') and vals.get('bullet_dmg') and vals.get('bullet_dmg_lvl'):
        return f' data-per="{vals["dps"] * vals["bullet_dmg_lvl"] / vals["bullet_dmg"]:.6g}"'
    return ''


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
                         lambda r, c: ['spirit'] if c['key'] in r.get('spirit_scaled', []) else [], as_of=t.get('date'),
                         row_cls=lambda h: 'pre' if h['state'] == 'prerelease' else '', table_id='hero-stats',
                         cell_attrs=boon_attrs,
                         row_attrs=lambda h: f' data-role="{esc(str(h.get("type") or "").rsplit("_", 1)[-1].lower())}"')
    n_pre = sum(1 for h in t['heroes'] if h['state'] == 'prerelease')
    # pre-release heroes (vote candidates, template stats) hide until asked for, as on the heroes page
    switch = (f'<span class="sep"></span><label class="switch"><input type="checkbox" data-toggle-class="show-pre" '
              f'data-target="#hero-stats"><span class="track"></span>Pre-release <span class="n">{n_pre}</span></label>'
              if n_pre else '')
    roles = sorted({str(h.get('type') or '').rsplit('_', 1)[-1] for h in t['heroes'] if h.get('type')})
    # Sloppy's LVL box: the table at N boons; and its Melee/Ranged buttons, here the game's roles
    boons = (f'<span class="sep"></span><label class="boons">Boons <input type="number" min="0" max="{MAX_BOONS}" '
             f'value="0" data-boons="#hero-stats"></label>')
    role_btns = '<span class="sep"></span>' + ''.join(
        f'<button class="px-btn" data-role-filter="{esc(r.lower())}" data-target="#hero-stats">{esc(r)}</button>' for r in roles)
    body = ('<h1>Hero Stats</h1>' + tabs('heroes') + _toolbar('Hero…', details=True, extra=switch + boons + role_btns)
            + table)
    return page('Hero Stats', body, rel, 'tables', build=t['build'],
                description='Deadlock hero stats with the full history of every value', wide=True)


UNIT_SECTIONS = (('building', 'Buildings & objectives'), ('trooper', 'Troopers'), ('neutral', 'Neutral camps'),
                 ('unit', 'Other units'))
_UNIT_ID_PREFIX = ('npc_', 'neutral_')


def unit_label(u: dict) -> str:
    """The game's name; a unit the game never names reads as words, never as its raw id."""
    if u['name'] != u['id']:
        return u['name']
    words = u['id']
    for pre in _UNIT_ID_PREFIX:
        words = words.removeprefix(pre)
    return words.replace('_', ' ').strip().title()


def merge_copies(rows: list[dict]) -> list[dict]:
    """One unit kept under several ids with the same numbers (Walker x4, Guardian x2) is one row x N."""
    seen: dict[tuple, dict] = {}
    out = []
    for r in rows:
        key = (unit_label(r), tuple(sorted((k, v) for k, v in r['values'].items())))
        if key in seen:
            seen[key]['copies'] = seen[key].get('copies', 1) + 1
            continue
        r = {**r}
        seen[key] = r
        out.append(r)
    return out


def _section_tables(groups: list[tuple[str, str, list[dict]]], cols: list[dict], name_cell, name_title: str,
                    as_of: str | None, section_of=None) -> str:
    """One banner + table per group, each with only the columns its rows fill."""
    out = []
    for key, title, rows in groups:
        if not rows:
            continue
        out.append(f'<div class="banner sub tbl-sec {esc(key)}"><span class="bt">{title}</span>'
                   f'<span class="bc">{len(rows)}</span></div>'
                   + render_table(non_empty(cols, rows), rows, name_cell, name_title, as_of=as_of,
                                  section_of=section_of))
    return ''.join(out)


def units_table() -> str:
    rel = '../'
    t = load_json('tables/units.json')

    def name_cell(u):
        ic = entity_icon('npc_units.vdata', u['id'], u['kind'], rel)
        img_html = f'<img class="px" src="{esc(ic)}" alt="" loading="lazy">' if ic else ''
        copies = f'<span class="copies">×{u["copies"]}</span>' if u.get('copies') else ''
        label = unit_label(u)
        return (f'<td class="name" data-col="name" data-sort="{esc(label)}"><a href="{rel}units/{esc(u["id"])}.html">'
                f'{img_html}{esc(label)}{copies}</a></td>')

    groups = []
    for kind, title in UNIT_SECTIONS:
        rows = [u for u in t['units'] if (u['kind'] if u['kind'] in dict(UNIT_SECTIONS) else 'unit') == kind]
        groups.append((kind, esc(title), merge_copies(sorted(rows, key=lambda u: unit_label(u).lower()))))
    body = ('<h1>Units & Buildings</h1>' + tabs('units') + _toolbar('Unit…')
            + _section_tables(groups, t['columns'], name_cell, 'Unit', t.get('date')))
    return page('Units & Buildings', body, rel, 'tables', build=t['build'],
                description='Deadlock troopers, guardians, walkers, patron and neutrals with the history of every value', wide=True)


ITEM_SECTIONS = (('Weapon', 'w', 'courage'), ('Spirit', 's', 'spirit'), ('Vitality', 'v', 'fortitude'))


def items_table() -> str:
    from .common import icon
    rel = '../'
    t = load_json('tables/items.json')
    cards = load_json('abilities.json')['abilities']

    def name_cell(it):
        ic = entity_icon('abilities.vdata', it['id'], 'item', rel)
        img_html = f'<img class="px" src="{esc(ic)}" alt="" loading="lazy">' if ic else ''
        act = '<span class="it-act">Active</span>' if it.get('activation') == 'Active' else ''
        return (f'<td class="name" data-col="name" data-sort="{esc(it["name"])}"><a href="{rel}items/'
                f'{esc(it["id"].removeprefix("upgrade_"))}.html">{img_html}{esc(it["name"])}{act}</a></td>')

    def in_shop(it) -> bool:
        info = (cards.get(it['id']) or {}).get('item') or {}
        return not info.get('street_brawl') and not info.get('disabled') and (it['values'].get('tier') or 0) <= 4

    # the game's shop: Weapon, Spirit, Vitality, each by tier (game order), only the columns it fills
    groups = []
    for slot, css, ik in ITEM_SECTIONS:
        rows = sorted((it for it in t['items'] if it.get('slot') == slot and in_shop(it)),
                      key=lambda it: (it['values'].get('tier') or 9, it['name'].lower()))
        src = icon(f'prop:{ik}', rel)
        title = (f'<img class="cat-i" src="{esc(src)}" alt="">' if src else '') + esc(slot)
        groups.append((css, title, rows))
    body = ('<h1>Items</h1>' + tabs('items') + _toolbar('Item…')
            + _section_tables(groups, t['columns'], name_cell, 'Item', t.get('date'),
                              section_of=lambda it: f'Tier {it["values"].get("tier")} · {_fmt(it["values"].get("cost"), 0)} souls'))
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
