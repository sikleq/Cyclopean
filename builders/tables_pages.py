"""Stats tables (heroes, units & buildings): current value in every cell,
hover a cell with a dot for its full change history."""
from __future__ import annotations

from typing import Callable

from .common import entity_icon, esc, hero_icon, json_attr, load_json, page, pretty_id, section_tabs, write


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


def _same_shown(a, b, digits: int) -> bool:
    """Two values the column prints the same (numbers at its digits; anything else as text)."""
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return _fmt(a, digits) == _fmt(b, digits)
    return a == b


RECENT_DAYS = 45      # the corner dot marks values changed this recently; older history is on hover only


def _recent_cutoff(as_of: str | None) -> str:
    from datetime import date, timedelta
    if not as_of:
        return '9999'
    return (date.fromisoformat(as_of[:10]) - timedelta(days=RECENT_DAYS)).isoformat()


def non_empty(cols: list[dict], rows: list[dict]) -> list[dict]:
    """Columns with at least one value in these rows (a category's table drops the others)."""
    return [c for c in cols if any(r['values'].get(c['key']) is not None for r in rows)]


def hist_attrs(hist: list | None, digits: int, title: str, cutoff: str) -> tuple[list[str], str]:
    """(classes, attributes) of a value with a change history: the hover table's data, a corner notch
    when it changed lately. A step the column's rounding cannot show is not a change to a reader (Max
    DPS 122.925 -> 122.9251 sat in Abrams' history, 2026-10-03)."""
    hist = [h for h in hist or [] if not _same_shown(h[2], h[3], digits)]
    if not hist:
        return [], ''
    cls = ['has-hist'] + (['recent'] if str(hist[-1][1])[:10] >= cutoff else [])
    return cls, json_attr('data-hist', hist) + f' data-title="{esc(title)}"'


def _head_label(c: dict, rel: str) -> str:
    """The header's text; an item column also shows the game's property icon and its unit
    ("Weapon Damage %", "Cooldown s"), so the cells can stay plain numbers."""
    from .hero_page import prop_icon
    pic = prop_icon(c['css'], rel) if c.get('css') else ''
    unit = f' <span class="u">{esc(c["unit"])}</span>' if c.get('unit') else ''
    return f'{pic}{esc(c.get("short") or c["label"])}{unit}'


def render_table(cols: list[dict], rows: list[dict], name_cell: Callable[[dict], str], name_title: str,
                 extra_cls: Callable[[dict, dict], list[str]] | None = None, as_of: str | None = None,
                 row_cls: Callable[[dict], str] | None = None, table_id: str = '',
                 section_of: Callable[[dict], str | tuple[str, str]] | None = None,
                 cell_attrs: Callable[[dict, dict], str] | None = None,
                 row_attrs: Callable[[dict], str] | None = None,
                 cells_by_key: dict[str, Callable[[dict, dict, str], str]] | None = None,
                 group_cls: dict[str, str] | None = None, rel: str = '../', center: bool = False) -> str:
    """`cells_by_key`: a column whose cell is not one number (items: the stats as chips, the effects,
    what an item builds from and into) — builder(row, column, cutoff) -> '<td…>'. A column's own `cls`
    goes on its header and cells, a group's (`group_cls`) on its group header; a `lazy` column has no
    cells (scripts.js builds them). `section_of` -> a band row before each new section: its label, or
    (label, row attributes). `center`: the box sits in the middle of the page when narrower."""
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
    group_cls = group_cls or {}

    def gcls(group: str) -> str:
        return (' g-details' if group == DETAILS else '') + (f' {group_cls[group]}' if group_cls.get(group) else '')
    cat_row = ('<tr class="cats"><th class="name"></th>' + ''.join(
        f'<th colspan="{n}" class="cat{gcls(g)}" data-group="{esc(g)}">{esc(g)}</th>' for g, n in groups) + '</tr>')

    def cell_cls(c: dict) -> list[str]:
        return ((['grp-start'] if c['key'] in first_of_group else []) + (['g-details'] if c['group'] == DETAILS else [])
                + (['g-odd'] if c['group'] in odd_groups else []) + ([c['cls']] if c.get('cls') else []))

    def head(c: dict) -> str:
        short = c.get('short')
        tip = f' data-tooltip="{esc(c["label"])}"' if short and short != c['label'] else ''
        parts = (['grp-start'] if c['key'] in first_of_group else []) + gcls(c['group']).split()
        cls = ' '.join(dict.fromkeys(parts + ([c['cls']] if c.get('cls') else [])))
        nosort = ' data-nosort' if c.get('nosort') else ''
        # a lazy column has no cells in the page: scripts.js builds them from the row's chips on demand
        lazy = f' data-cell-cls="{" ".join(cell_cls(c))}"' if c.get('lazy') else ''
        return (f'<th data-col="{esc(c["key"])}" data-group="{esc(c["group"])}" class="{cls}"{tip}{nosort}{lazy}>'
                f'{_head_label(c, rel)}</th>')
    col_row = (f'<tr class="cols"><th class="name" data-col="name">{esc(name_title)}</th>'
               + ''.join(head(c) for c in cols) + '</tr>')
    body: list[str] = []
    last_section: list[str | None] = [None]
    cells_by_key = cells_by_key or {}
    for r in rows:
        cells = [name_cell(r)]
        for c in cols:
            if c.get('lazy'):
                continue
            if c['key'] in cells_by_key:
                cells.append(cells_by_key[c['key']](r, c, cutoff))
                continue
            v = r['values'].get(c['key'])
            cls = cell_cls(c)
            if extra_cls:
                cls += extra_cls(r, c)
            attrs = f' data-col="{c["key"]}" data-sort="{"" if v is None else v}" data-pol="{c["pol"]}" data-digits="{c["digits"]}"'
            if cell_attrs:
                attrs += cell_attrs(r, c)
            tint = COLUMN_TINT.get(c['key'])
            if tint:
                cls.append(tint)
            if v == 0 and isinstance(v, (int, float)):
                cls.append('zero')                  # a zero reads quieter than a number (Sloppy's regen 0)
            hcls, hattrs = hist_attrs(r['history'].get(c['key']), c['digits'], f'{r["name"]} · {c["label"]}', cutoff)
            cls += hcls
            attrs += hattrs
            cells.append(f'<td class="{" ".join(cls)}"{attrs}>{_fmt(v, c["digits"])}</td>')
        if section_of:
            sec = section_of(r)
            label, sattrs = sec if isinstance(sec, tuple) else (sec, '')
            if label != last_section[0]:
                last_section[0] = label
                body.append(f'<tr class="sec"{sattrs}><td class="name">{label}</td>'
                            f'<td class="sec-fill" colspan="{len(cols)}"></td></tr>')
        rc = f' class="{row_cls(r)}"' if row_cls and row_cls(r) else ''
        ra = row_attrs(r) if row_attrs else ''
        body.append(f'<tr{rc}{ra} data-search="{esc(r["name"].lower())}">' + ''.join(cells) + '</tr>')
    # the fade on the right edge says "more columns this way" until the table is scrolled to its end
    tid = f' id="{esc(table_id)}"' if table_id else ''
    fade = 'table-fade center' if center else 'table-fade'
    return (f'<div class="{fade}"><div class="table-scroll"><table class="stats"{tid}><thead>{cat_row}{col_row}</thead>'
            f'<tbody>{"".join(body)}</tbody></table></div></div>')


def _toolbar(placeholder: str, details: bool = False, extra: str = '', heat_on: bool = False) -> str:
    more = ('<button class="px-btn" data-toggle-class="show-details" data-target=".table-scroll">Details</button>'
            if details else '')
    # the corner notch explained once, at the end of the bar (advisor round 4: "recent" had no legend);
    # on a phone only its first half, and it wraps (the 489px chip scrolled the page sideways)
    legend = (f'<span class="chip legend-hist">changed in the last {RECENT_DAYS} days'
              f'<span class="lg-tail"> · hover a value for its history</span></span>')
    checked = ' checked' if heat_on else ''
    # not sticky: stuck, it covered the table's own sticky header (a third of a phone screen)
    return ('<div class="toolbar tbl-bar">'
            f'<input type="search" placeholder="{esc(placeholder)}" data-search-target="table.stats tbody tr:not(.sec)">'
            f'<span class="sep"></span><label class="switch"><input type="checkbox" data-heatmap{checked}>'
            f'<span class="track"></span>Heatmap</label>{more}{extra}<span class="sep"></span>{legend}</div>')


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
    body = ('<h1>Hero Stats</h1>' + section_tabs('heroes', 'stats') + _toolbar('Hero…', details=True, extra=switch + boons + role_btns)
            + table)
    return page('Hero Stats', body, rel, 'heroes', build=t['build'],
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


def has_stats(u: dict) -> bool:
    """A row worth a line: a value besides a 1-HP placeholder (the Bug, the zipline container)."""
    vals = {k: v for k, v in u['values'].items() if v is not None}
    return bool(vals) and vals != {'hp': 1.0} and not (set(vals) == {'hp'} and vals['hp'] <= 1)


def neutral_groups(rows: list[dict], cols: list[dict], title: str) -> list[tuple[str, str, list[dict]]]:
    """Neutral camps (owner, 2026-10-03: "many identical units, only the tier changes"): every family's
    tier I / II / III shares health, damage and bounty — one TIER table holds what all families share,
    one FAMILY table a row per family with only what differs (speed, range, fire interval); the rest
    (Mid-Boss, Sinner's Sacrifice) as before."""
    from .unit_families import family_name, tier_of
    tiered = [u for u in rows if tier_of(u)]
    other = [u for u in rows if not tier_of(u)]
    by_tier: dict[str, list[dict]] = {}
    for u in tiered:
        by_tier.setdefault(tier_of(u), []).append(u)
    shared = [c['key'] for c in cols
              if all(len({u['values'].get(c['key']) for u in us}) == 1 for us in by_tier.values())
              and any(us[0]['values'].get(c['key']) is not None for us in by_tier.values())]
    tier_rows = [{**us[0], 'name': f'Tier {t}', 'tier_row': True,
                  'values': {k: us[0]['values'].get(k) for k in shared},
                  'history': {k: v for k, v in (us[0].get('history') or {}).items() if k in shared}}
                 for t, us in sorted(by_tier.items(), key=lambda kv: len(kv[0]))]
    families: dict[str, list[dict]] = {}
    for u in tiered:
        families.setdefault(family_name(u), []).append(u)
    # what differs between families: one column, or one per tier where a family's tiers differ too
    # (Gutter Ghoul runs 3.81 / 3.05 / 2.03 — the table showed tier I's 3.81 for all, advisor 10-03)
    tiers = sorted(by_tier, key=len)

    def varies_by_tier(key: str) -> bool:
        for fam in families.values():
            per: dict[str, object] = {}
            for u in fam:
                per.setdefault(tier_of(u), u['values'].get(key))
            if len(set(per.values())) > 1:
                return True
        return False
    fam_cols = []
    kept: list[str] = []
    for c in cols:
        if c['key'] in shared or not any(u['values'].get(c['key']) is not None for u in tiered):
            continue
        # a column that repeats an earlier one in every unit says nothing new (Walk = Run on all neutrals)
        if any(all(u['values'].get(c['key']) == u['values'].get(k) for u in tiered) for k in kept):
            continue
        kept.append(c['key'])
        if varies_by_tier(c['key']):
            fam_cols += [{**c, 'key': f'{c["key"]}@{t}', 'label': f'{c["label"]} {t}',
                          'short': f'{c.get("short") or c["label"]} {t}'} for t in tiers]
        else:
            fam_cols.append(c)
    fam_rows = []
    for name, us in sorted(families.items()):
        by_t = {}
        for u in sorted(us, key=lambda u: u['id']):
            by_t.setdefault(tier_of(u), u)
        values, history = {}, {}
        for c in fam_cols:
            base, _, t = c['key'].partition('@')
            src = by_t.get(t) if t else by_t.get(tiers[0])
            if src:
                values[c['key']] = src['values'].get(base)
                if (src.get('history') or {}).get(base):
                    history[c['key']] = src['history'][base]
        first = by_t.get(tiers[0]) or us[0]
        fam_rows.append({**first, 'name': name, 'values': values, 'history': history})
    out = []
    if tier_rows:
        out.append(('neutral', f'{esc(title)} · tiers', tier_rows))
    if fam_rows:
        out.append(('neutral', f'{esc(title)} · families', merge_copies(fam_rows), fam_cols))
    if other:
        out.append(('neutral', f'{esc(title)} · others', merge_copies(sorted(other, key=lambda u: unit_label(u).lower()))))
    return out


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
    """One banner + table per group, each with only the columns its rows fill; a group may bring its own
    columns as a 4th element (the neutral families' per-tier speeds)."""
    out = []
    for group in groups:
        key, title, rows = group[:3]
        own_cols = group[3] if len(group) > 3 else cols
        if not rows:
            continue
        out.append(f'<div class="banner sub tbl-sec {esc(key)}"><span class="bt">{title}</span>'
                   f'<span class="bc">{len(rows)}</span></div>'
                   + render_table(non_empty(own_cols, rows), rows, name_cell, name_title, as_of=as_of,
                                  section_of=section_of))
    return ''.join(out)


def units_table() -> str:
    rel = '../'
    t = load_json('tables/units.json')

    from .unit_families import is_named, main_of
    ents = [e for e in load_json('entities.json')['entities'] if e['file'] == 'npc_units.vdata' and not e.get('template')]
    main = main_of(ents)

    def name_cell(u):
        from .common import glyph_for, visual
        ic = entity_icon('npc_units.vdata', u['id'], u['kind'], rel)
        # no art: the unit glyph, so every row has its mark (Shrine, Overseer had none, round 3)
        img_html = visual(ic, glyph_for('npc_units.vdata', u['id']), 'px')
        copies = f'<span class="copies">×{u["copies"]}</span>' if u.get('copies') else ''
        label = unit_label(u)
        if u.get('tier_row'):                  # a row of the tier template: no page of its own
            return f'<td class="name" data-col="name" data-sort="{esc(label)}"><span>{img_html}{esc(label)}</span></td>'
        page_id = main.get(u['id'], u['id'])   # the unit family's page
        return (f'<td class="name" data-col="name" data-sort="{esc(label)}"><a href="{rel}units/{esc(page_id)}.html">'
                f'{img_html}{esc(label)}{copies}</a></td>')

    groups = []
    for kind, title in UNIT_SECTIONS:
        # what the Units index shows: named units (unit_families.is_named) with a stat besides a placeholder
        rows = [u for u in t['units'] if (u['kind'] if u['kind'] in dict(UNIT_SECTIONS) else 'unit') == kind
                and has_stats(u) and is_named(u)]
        if kind == 'neutral':
            groups += neutral_groups(rows, t['columns'], title)
            continue
        groups.append((kind, esc(title), merge_copies(sorted(rows, key=lambda u: unit_label(u).lower()))))
    body = ('<h1>Unit Stats</h1>' + section_tabs('units', 'stats') + _toolbar('Unit…')
            + _section_tables(groups, t['columns'], name_cell, 'Unit', t.get('date')))
    return page('Unit Stats', body, rel, 'units', build=t['build'],
                description='Deadlock troopers, guardians, walkers, patron and neutrals with the history of every value', wide=True)


ITEM_SECTIONS = (('Weapon', 'w', 'courage'), ('Spirit', 's', 'spirit'), ('Vitality', 'v', 'fortitude'))
# stat families (pipeline.item_table.family) -> the class that colours their numbers
FAMILY_CSS = {'Weapon': 'f-w', 'Spirit': 'f-s', 'Vitality': 'f-v', 'Movement': 'f-m', 'Utility': 'f-u'}
STATS_COL = {'key': 'stats', 'label': 'Always on', 'group': 'Stats', 'cls': 'sumc', 'nosort': True, 'pol': 0, 'digits': 0}
EFFECT_COL = {'key': 'effect', 'label': 'Passive · Active', 'group': 'Effect', 'cls': 'fxc', 'nosort': True, 'pol': 0,
              'digits': 0}
# what an item is built from → what it builds into: last, after what the item does
BUILDS_COL = {'key': 'builds', 'label': 'From → into', 'group': 'Builds', 'cls': 'xcol', 'nosort': True, 'pol': 0,
              'digits': 0}


def item_columns(cols: list[dict]) -> list[dict]:
    """Item Stats in display order: Shop | Stats — the always-on stats as chips in one cell, or (the
    "Stat columns" switch) one sortable column per stat by family | Effect | Utility (cooldown, duration).
    Folded into one cell the stats leave few dashes: 156 items give ~2 of 25 stats each, so a column
    per stat is ~90% empty (owner complaint 6, 2026-10-04)."""
    shop = [c for c in cols if c['group'] == 'Shop']
    # the per-stat cells are not in the page (~3.5k cells, 90% dashes): scripts.js stat-cols builds them
    # from the chips the first time the columns open
    stats = [{**c, 'cls': 'stc', 'lazy': True} for c in cols if c.get('stat')]
    rest = [c for c in cols if c['group'] not in ('Shop',) and not c.get('stat')]
    return shop + [STATS_COL] + stats + [EFFECT_COL] + rest + [BUILDS_COL]


def _chip(cls: str, value: str, label: str, css: str | None, attrs: str, rel: str) -> str:
    """One number as the game's tooltip shows it: the property's icon, the value, its label."""
    from .hero_page import prop_icon
    return f'<span class="{cls}"{attrs}>{prop_icon(css, rel)}<b>{esc(value)}</b> <i>{esc(label)}</i></span>'


def stats_cell(row: dict, stat_cols: list[dict], cutoff: str, rel: str = '../') -> str:
    """The row's always-on stats as chips (value as the game prints it + label), each with its own
    history; a chip carries its column's key and value, so the heatmap ranks it with that column and a
    click opens the columns sorted by it."""
    chips, gone = [], []
    for c in stat_cols:
        v = row['values'].get(c['key'])
        hcls, hattrs = hist_attrs(row['history'].get(c['key']), c['digits'], f'{row["name"]} · {c["label"]}', cutoff)
        if v is None:
            # a stat the item no longer gives keeps its history for the column view (an empty marker)
            if hattrs:
                gone.append(f'<span class="sc gone {" ".join(hcls)}" data-col="{esc(c["key"])}" data-pol="{c["pol"]}" '
                            f'data-digits="{c["digits"]}"{hattrs}></span>')
            continue
        cls = ' '.join(['sc', FAMILY_CSS.get(c['group'], 'f-u')] + hcls)
        attrs = (f' data-col="{esc(c["key"])}" data-sort="{v}" data-pol="{c["pol"]}" data-digits="{c["digits"]}"'
                 f' data-spp{hattrs}')
        shown = (row.get('shown') or {}).get(c['key']) or _fmt(v, c['digits'])
        chips.append(_chip(cls, shown, c['label'], c.get('css'), attrs, rel))
    inner = (f'<div class="chips">{"".join(chips)}</div>' if chips else '<span class="dash">—</span>') + ''.join(gone)
    return f'<td class="sumc grp-start" data-col="stats" data-sort="{len(chips) or ""}" data-pol="0">{inner}</td>'


def effects_cell(row: dict, cutoff: str, rel: str = '../') -> str:
    """Every other number on the item's card (Headshot Booster's +45 Head Shot Bonus Damage), labelled,
    with units, each with its own history."""
    chips = []
    for e in row.get('effects') or []:
        hcls, hattrs = hist_attrs(row['history'].get(e['key']), e['digits'], f'{row["name"]} · {e["label"]}', cutoff)
        attrs = f' data-pol="{e["pol"]}" data-digits="{e["digits"]}"{hattrs}'
        chips.append(_chip(' '.join(['fx'] + hcls), e['value'], e['label'], e.get('css'), attrs, rel))
    inner = f'<div class="chips">{"".join(chips)}</div>' if chips else '<span class="dash">—</span>'
    return f'<td class="fxc grp-start" data-col="effect" data-sort="{len(chips) or ""}" data-pol="0">{inner}</td>'


def tier_starts(rows: list[dict]) -> set[str]:
    """Ids of the first row of each tier inside each category (a divider line above it)."""
    out, last = set(), None
    for r in rows:
        key = (r.get('slot'), r['values'].get('tier'))
        if key != last:
            out.add(r['id'])
            last = key
    return out


def items_table() -> str:
    from .common import icon
    rel = '../'
    t = load_json('tables/items.json')
    cards = load_json('abilities.json')['abilities']

    def name_cell(it):
        ic = entity_icon('abilities.vdata', it['id'], 'item', rel)
        # the shop's art, smooth and framed (pixelated 22px icons read as noise, 2026-10-04)
        img_html = f'<img class="ti" src="{esc(ic)}" alt="" loading="lazy">' if ic else '<span class="ti"></span>'
        act = '<span class="it-act">Active</span>' if it.get('activation') == 'Active' else ''
        return (f'<td class="name" data-col="name" data-sort="{esc(it["name"])}"><a href="{rel}items/'
                f'{esc(it["id"].removeprefix("upgrade_"))}.html">{img_html}<span class="nm">{esc(it["name"])}</span>{act}</a></td>')

    def in_shop(it) -> bool:
        info = (cards.get(it['id']) or {}).get('item') or {}
        return not info.get('street_brawl') and not info.get('disabled') and (it['values'].get('tier') or 0) <= 4

    # ONE table of the shop (owner, 2026-10-03; Sloppy's Mana Items): Weapon → Spirit → Vitality, each by
    # tier; chips filter by category, tier and kind, the columns no shown row fills hide (scripts.js
    # item-filter), "Souls per point" turns each stat into what one point of it costs
    order = {slot: i for i, (slot, _, _) in enumerate(ITEM_SECTIONS)}
    cat_of = {slot: css for slot, css, _ in ITEM_SECTIONS}
    rows = sorted((it for it in t['items'] if in_shop(it)),
                  key=lambda it: (order.get(it.get('slot'), 9), it['values'].get('tier') or 9, it['name'].lower()))
    names = {it['id']: it['name'] for it in t['items']}
    into: dict[str, list[str]] = {}
    for it in rows:
        for comp in ((cards.get(it['id']) or {}).get('item') or {}).get('components') or []:
            into.setdefault(comp, []).append(it['id'])

    def mini(iid: str) -> str:
        ic = entity_icon('abilities.vdata', iid, 'item', rel)
        nm = names.get(iid) or pretty_id(iid)
        img = f'<img src="{esc(ic)}" alt="" loading="lazy">' if ic else ''
        return (f'<a class="bmini" href="{rel}items/{esc(iid.removeprefix("upgrade_"))}.html" data-tooltip="{esc(nm)}" '
                f'aria-label="{esc(nm)}">{img}</a>')

    def builds(it: dict, c: dict | None = None, cutoff: str = '') -> str:
        comps = ((cards.get(it['id']) or {}).get('item') or {}).get('components') or []
        ups = into.get(it['id'], [])
        if not comps and not ups:
            return '<td class="xcol grp-start" data-col="builds" data-pol="0"><span class="dash">—</span></td>'
        arrow = '<span class="barrow">→</span>' if comps and ups else ''
        return (f'<td class="xcol grp-start" data-col="builds" data-sort="{len(comps) + len(ups)}" data-pol="0">'
                f'{"".join(mini(c) for c in comps)}{arrow}{"".join(mini(u) for u in ups)}</td>')

    def row_attrs(it: dict) -> str:
        info = (cards.get(it['id']) or {}).get('item') or {}
        kind = 'imbue' if info.get('imbue') else (it.get('activation') or 'passive').lower()
        return (f' data-cat="{cat_of.get(it.get("slot"), "")}" data-tier="{it["values"].get("tier") or ""}"'
                f' data-kind="{esc(kind)}" data-cost="{it["values"].get("cost") or ""}"')

    def cat_icon(ik: str) -> str:
        src = icon(f'prop:{ik}', rel)
        return f'<img class="cat-i" src="{esc(src)}" alt="">' if src else ''
    chips = ('<span class="it-filter">'
             + ''.join(f'<button class="px-btn" data-f="cat" data-v="{css}">{cat_icon(ik)}{esc(slot)}</button>'
                       for slot, css, ik in ITEM_SECTIONS)
             + '</span><span class="sep"></span><span class="it-filter">'
             + ''.join(f'<button class="px-btn" data-f="tier" data-v="{n}">Tier {r}</button>'
                       for n, r in ((1, 'I'), (2, 'II'), (3, 'III'), (4, 'IV')))
             + '</span><span class="sep"></span><span class="it-filter">'
             + ''.join(f'<button class="px-btn" data-f="kind" data-v="{k}">{lbl}</button>'
                       for k, lbl in (('active', 'Active'), ('passive', 'Passive'), ('imbue', 'Imbue')))
             + '</span><span class="sep"></span><label class="switch"><input type="checkbox" data-stat-cols '
               'data-toggle-class="cols-open" data-target="#items-table"><span class="track"></span>Stat columns</label>'
               '<label class="switch"><input type="checkbox" data-souls-per>'
               '<span class="track"></span>Souls per point</label>')
    # a band row per category (Weapon → Spirit → Vitality) and a divider at each new tier; both stand
    # aside while the table is sorted by a column (scripts.js table-sort)
    n_in = {slot: sum(1 for r in rows if r.get('slot') == slot) for slot, _, _ in ITEM_SECTIONS}
    icon_of = {slot: ik for slot, _, ik in ITEM_SECTIONS}

    def band(it: dict) -> tuple[str, str]:
        slot = it.get('slot') or ''
        label = (f'<span class="band">{cat_icon(icon_of.get(slot, ""))}{esc(slot)}'
                 f'<span class="bn">{n_in.get(slot, 0)}</span></span>')
        return label, f' data-cat="{cat_of.get(slot, "")}"'

    def cell_attrs(r: dict, c: dict) -> str:
        if c.get('stat'):
            return ' data-spp'
        # the price follows the tier: shading it only repeated the tier bands (all 800s green)
        return ' data-hpol="0"' if c['key'] == 'cost' else ''
    starts = tier_starts(rows)
    cols = item_columns(non_empty(t['columns'], rows))
    stat_cols = [c for c in cols if c.get('stat')]
    group_cls = {c['group']: 'stc' for c in stat_cols}
    group_cls.update({c['group']: '' for c in cols if not c.get('stat') and c['group'] in group_cls})
    group_cls['Stats'] = 'sumc'
    group_cls['Builds'] = 'xcol'
    table = render_table(cols, rows, name_cell, 'Item', as_of=t.get('date'),
                         row_attrs=row_attrs, table_id='items-table',
                         row_cls=lambda it: 'tier-start' if it['id'] in starts else '', section_of=band,
                         cell_attrs=cell_attrs,
                         cells_by_key={'stats': lambda r, c, cut: stats_cell(r, stat_cols, cut, rel),
                                       'effect': lambda r, c, cut: effects_cell(r, cut, rel), 'builds': builds},
                         group_cls=group_cls, rel=rel, center=True)
    body = ('<h1>Item Stats</h1>' + section_tabs('items', 'stats')
            + _toolbar('Item…', extra='<span class="sep"></span>' + chips, heat_on=True) + table)
    return page('Item Stats', body, rel, 'items', build=t['build'],
                description='Deadlock shop items with the history of every value', wide=True)


def build_all() -> int:
    write('tables/heroes.html', heroes_table())
    write('tables/units.html', units_table())
    write('tables/items.html', items_table())
    return 3
