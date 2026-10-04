"""Hero, item and unit pages + their index grids."""
from __future__ import annotations

from collections import defaultdict

from .common import display_name, entity_icon, esc, first_seen, glyph_for, img, load_json, page, slug, write
from .cards import GAMEPLAY
from .hero_page import hero_page, history_table, prop_icon, prop_rows, stat_tables
from .history_view import now_fold
from .render import KIND_LABEL, tag_badge

UNIT_GROUPS = (('building', 'Buildings & objectives'), ('trooper', 'Troopers'), ('neutral', 'Neutrals'),
               ('unit', 'Other units'), ('helper', 'Unnamed, hideout, bots & effects'))
SLOT_NAMES = {'EItemSlotType_WeaponMod': 'Weapon', 'EItemSlotType_Armor': 'Vitality', 'EItemSlotType_Tech': 'Spirit'}


def _history() -> tuple[dict, dict]:
    """entity key -> [(patch row, changes)], note subject -> [(patch row, line)]."""
    from . import archive
    by_ent: dict[str, list] = defaultdict(list)
    by_subject: dict[str, list] = defaultdict(list)
    for row in archive.index():
        p = archive.patch(row['id'])
        for e in p['entities']:
            ch = [c for c in e['changes'] if c['cat'] in GAMEPLAY]
            if ch and e.get('id') != '@shared':
                by_ent[e['key']].append((row, ch))
        for s in p['sections']:
            for ln in s['lines']:
                # a heading is a bare name, a repeated line lives on its later patch
                if ln.get('subject') and ln['status'] not in ('heading', 'repeated'):
                    by_subject[ln['subject'].strip().lower()].append((row, ln))
    return by_ent, by_subject


def item_page(it: dict, card: dict | None, by_ent, by_subject) -> str:
    rel = '../'
    name = display_name(it)
    ic = entity_icon(it['file'], it['id'], it['kind'], rel)
    gone = '' if it.get('alive') else ' ' + tag_badge('del', 'REMOVED')
    disabled = ' <span class="chip">not in shop</span>' if it.get('disabled') else ''
    info = card.get('item') if card else None
    chips = []
    if info:
        chips += [f'<span class="chip">{esc(SLOT_NAMES.get("EItemSlotType_" + info["slot"], info["slot"]))}</span>',
                  f'<span class="chip">Tier {esc(info["tier"])}</span>',
                  f'<span class="chip">{esc(info["activation"])}</span>']
        if info.get('street_brawl'):
            # T5 is Street Brawl's draft only; its "price" 9999 is a placeholder, not souls
            chips.append('<span class="chip">Street Brawl only</span>')
        elif info.get('cost'):
            chips.append(f'<span class="chip">{esc(info["cost"])} souls</span>')
    head = (f'<div class="crumbs"><a href="index.html">Items</a> / {esc(name)}</div>'
            f'<div class="page-head">{img(ic, "", "head-icon px px-frame", "abilities")}<div><h1>{esc(name)}{gone}{disabled}</h1>'
            f'<div class="chips">{"".join(chips)}</div>'
            f'{first_seen(it["first"])}</div></div>')
    sections = ''
    if card:
        blocks = []
        for s in card.get('sections', []):
            rows = prop_rows(s['props'], rel)
            desc = f'<div class="ac-desc">{esc(s["desc"])}</div>' if s.get('desc') else ''
            blocks.append(f'<div class="ability-card px-frame"><div class="ac-head"><div class="ac-name">{esc(s["type"])}</div></div>'
                          f'{desc}<table class="kvt">{rows}</table></div>')
        hdr = ''
        if card.get('header'):
            hdr = '<div class="chips item-hdr">' + ''.join(
                f'<span class="chip p-{esc(h.get("css") or "")}">{prop_icon(h.get("css"), rel)}{esc(h["label"])} '
                f'<b>{esc(h["value"])}</b></span>' for h in card['header']) + '</div>'
        # the sections side by side as cards, not full-width tables (a label and its value sat 1300px apart)
        grid = f'<div class="ability-grid item-secs">{"".join(blocks)}</div>' if blocks else ''
        sections = (hdr + grid) if blocks or hdr else ''
    history = history_table([(f'abilities.vdata:{it["id"]}', name, ic)], [name], by_ent, by_subject, rel,
                            enhanced=True)
    # the page is the history (owner, 2026-10-03); what the item does today sits open above it (owner
    # 2026-10-04: nothing folded by default)
    return page(name, head + now_fold('Current values', sections) + history, rel, 'items', cls='entity')


UNIT_AREAS = (('stats', 'Stats'), ('t1', 'Tier I'), ('t2', 'Tier II'), ('t3', 'Tier III'), ('abil', 'Abilities'))


def unit_page(members: list[dict], urow: dict, cols: list[dict], by_ent, by_subject, bound: dict) -> str:
    """A unit FAMILY's page (unit_families): Slum Shroom I-III, the four Walkers — one head, today's stats
    per tier (open), one history where each member is a group (identical ones merged)."""
    from .unit_families import TIER_RANK, family_name, member_label, merged_label, tier_of
    rel = '../'
    u = members[0]
    name = family_name(u)
    ic = entity_icon(u['file'], u['id'], u['kind'], rel)
    gone = '' if any(m.get('alive') for m in members) else ' ' + tag_badge('del', 'REMOVED')
    tiers = list(dict.fromkeys(tier_of(m) for m in members if tier_of(m)))
    chips = [f'<span class="chip">{esc(KIND_LABEL.get(u["kind"], u["kind"]))}</span>']
    if tiers:
        chips.append(f'<span class="chip">Tier {" · ".join(tiers)}</span>')
    copies = len(members) // max(len(tiers), 1)
    if copies > 1:
        chips.append(f'<span class="chip">{copies} variants</span>')
    head = (f'<div class="crumbs"><a href="index.html">Units</a> / {esc(name)}</div>'
            f'<div class="page-head">{img(ic, "", "head-icon px px-frame", "units")}<div><h1>{esc(name)}{gone}</h1>'
            f'<div class="chips">{"".join(chips)}</div>'
            f'{first_seen(u["first"])}</div></div>')
    # today's stats above the history: a tiered family as ONE table, a stat per row, a tier per column
    # (three stacked panels repeated every label, advisor 10-03); others as before
    by_tier: dict[str, dict] = {}
    for m in members:
        if urow.get(m['id']) and tier_of(m) not in by_tier:
            by_tier[tier_of(m)] = urow[m['id']]
    if len(by_tier) > 1:
        from .tables_pages import _fmt
        tiers_sorted = sorted(by_tier, key=lambda t: TIER_RANK.get(t, 0))
        body_rows, seen = [], []
        for c in cols:
            vals = [by_tier[t]['values'].get(c['key']) for t in tiers_sorted]
            # a row that repeats an earlier one in every tier says nothing new (Walk = Run, as Unit Stats)
            if all(v is None for v in vals) or vals in seen:
                continue
            seen.append(vals)
            body_rows.append(f'<tr><td>{esc(c["label"])}</td>' + ''.join(f'<td class="v">{_fmt(v, c["digits"])}</td>'
                                                                       for v in vals) + '</tr>')
        head_row = '<tr><th></th>' + ''.join(f'<th>Tier {esc(t)}</th>' for t in tiers_sorted) + '</tr>'
        stats_html = f'<table class="kvt tier-grid"><thead>{head_row}</thead><tbody>{"".join(body_rows)}</tbody></table>'
    else:
        row = next((urow.get(m['id']) for m in members if urow.get(m['id'])), None)
        stats_html = stat_tables(row, cols, name, rel) if row else ''
    # the members, then their own abilities and guns (B10: Walker's 120 ability rows were on no unit
    # page); ability names don't pull note lines in — "Rocket Barrage" is also a hero's
    keys = [(f'npc_units.vdata:{m["id"]}', member_label(m, members) if len(members) > 1 else name,
             entity_icon(m['file'], m['id'], m['kind'], rel)) for m in members]
    areas = {k: (f't{TIER_RANK[tier_of(m)]}' if tier_of(m) in TIER_RANK and TIER_RANK[tier_of(m)] <= 3 else 'stats')
             for (k, _, _), m in zip(keys, members)}
    abilities = {a['id']: a for m in members for a in bound.get(m['id'], [])}
    own = [(f'abilities.vdata:{a["id"]}', display_name(a), entity_icon(a['file'], a['id'], a['kind'], rel))
           for a in sorted(abilities.values(), key=lambda a: (a['kind'] == 'weapon', display_name(a)))]
    hist = history_table(keys + own, [name] + [display_name(m) for m in members], by_ent, by_subject, rel,
                         line_names=False, areas=areas, area_labels=UNIT_AREAS,
                         merge=lambda labels: merged_label(labels, len(members)))
    return page(name, head + now_fold('Current stats', stats_html) + hist, rel, 'units', cls='entity')


def redirect_page(target: str, name: str) -> str:
    """A member of a unit family points to the family's page (scripts.js keeps the #p-<patch> anchor;
    the refresh is the fallback without scripts)."""
    from .common import asset_version
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>{esc(name)} · Cyclopean</title>'
            f'<meta http-equiv="refresh" content="1; url={esc(target)}"><link rel="canonical" href="{esc(target)}">'
            f'</head><body data-redirect="{esc(target)}"><p><a href="{esc(target)}">{esc(name)}</a></p>'
            f'<script src="../scripts.js?v={asset_version()}"></script></body></html>')


def sub_tabs(section: str, active: str) -> str:
    """The index, its stats table and its change matrix (common.SECTION_TABS)."""
    from .common import section_tabs
    return section_tabs(section, active)


def _card(e: dict, rel_icon: str | None, sub: str = '', foot: str = '') -> str:
    href = slug(e['file'], e['id']).split('/', 1)[1]
    cls = 'card px-frame' + ('' if e.get('alive') else ' gone')
    name = display_name(e)
    return (f'<a class="{cls}" href="{esc(href)}" data-search="{esc(name.lower())} {esc(e["id"])}">'
            f'{img(rel_icon, "", "px", glyph_for(e["file"], e["id"]))}<span class="nm">{esc(name)}</span>'
            f'<span class="sub">{esc(sub)}</span>{foot}</a>')


def build_all() -> dict[str, int]:
    """Every hero, item and unit page, the three indexes, the change matrices and the home search's list.
    One step per section (python audit 2026-10-04: one 126-line function)."""
    ctx = _context()
    live, shared, has_shared, n_heroes = _build_heroes(ctx)
    items = _build_items(ctx)
    units, fams, named, n_units = _build_units(ctx)
    from .hero_page import current_cards
    from .site_search import INDEX_FILE, search_json, search_rows
    from . import shared_page
    found = search_rows(live, items, named, ctx['cards'], current_cards)
    if has_shared:          # jump, dash, parry… open their own page (shared_page)
        found = sorted(found + shared_page.search_rows(shared, ctx['by_ent']), key=lambda r: (r[0].lower(), r[2]))
    write(INDEX_FILE, search_json(found))
    from .dynamics_page import matrix_html, toolbar, unit_entries
    rel = ctx['rel']
    entries = unit_entries(units, UNIT_GROUPS, rel)
    n_gone = sum(1 for e in entries if e[4])
    write('units/changes.html', page('Unit changes', '<h1>Unit changes</h1>' + sub_tabs('units', 'changes')
                                     + toolbar('unit', n_gone, 'Removed & helpers') + matrix_html(entries, 'unit'),
                                     rel, 'units', wide=True))
    return {'heroes': n_heroes, 'items': len(items), 'units': n_units}


def _context() -> dict:
    """What every section reads: the catalog, the history by entity and by note subject, the tables, the cards."""
    data = load_json('entities.json')
    ents = {f"{e['file']}:{e['id']}": e for e in data['entities']}
    by_ent, by_subject = _history()
    return {'ents': ents, 'by_ent': by_ent, 'by_subject': by_subject, 'heroes_t': load_json('tables/heroes.json'),
            'units_t': load_json('tables/units.json'), 'cards': load_json('abilities.json')['abilities'], 'rel': '../',
            'by_id': {e['id']: e for e in ents.values() if e['file'] == 'abilities.vdata'}}


def _build_heroes(ctx: dict) -> tuple[list[dict], list[dict], bool, int]:
    """Hero pages, the shared abilities' page, the Heroes index and the hero matrix. Returns (the heroes a
    player can pick, the shared abilities, whether they have a history, pages written)."""
    ents, by_ent, by_subject, rel = ctx['ents'], ctx['by_ent'], ctx['by_subject'], ctx['rel']
    table = ctx['heroes_t']
    trow = {r['id']: r for r in table['heroes']}
    heroes = [e for e in ents.values() if e['file'] == 'heroes.vdata' and not e.get('template')
              and (e.get('state') in ('EHeroDevState_Release', 'EHeroDevState_PreRelease') or e['id'] in trow
                   or f"heroes.vdata:{e['id']}" in by_ent)]
    for h in heroes:
        write(slug(h['file'], h['id']), hero_page(h, ctx['cards'], trow.get(h['id']), table['columns'], ctx['by_id'],
                                                  by_ent, by_subject))
    live = sorted((h for h in heroes if h.get('state') in ('EHeroDevState_Release', 'EHeroDevState_PreRelease')),
                  key=lambda h: h.get('name') or '')
    other = sorted((h for h in heroes if h not in live), key=lambda h: h.get('name') or '')
    from .dynamics_page import hero_entries, matrix_html, toolbar
    from .heroes_grid import heroes_grid_html, pre_release_switch
    from . import shared_page
    shared = shared_page.shared_entities(list(ents.values()))
    has_shared = shared_page.has_history(shared, by_ent)
    if has_shared:
        write(f'heroes/{shared_page.HREF}', shared_page.shared_page(shared, by_ent, by_subject))
    body = ('<h1>Heroes</h1>' + sub_tabs('heroes', 'index') +
            '<div class="toolbar"><input type="search" placeholder="Hero…" data-search-target=".hgcard">'
            f'<span class="sep"></span>{pre_release_switch(live)}{shared_page.index_link() if has_shared else ""}</div>'
            + heroes_grid_html(live, other, trow, rel))
    write('heroes/index.html', page('Heroes', body, rel, 'heroes'))
    n_pre = sum(1 for h in live if h.get('state') != 'EHeroDevState_Release')
    dyn = matrix_html(hero_entries(live, rel) + ([shared_page.matrix_entry()] if has_shared else []), 'hero')
    write('heroes/changes.html', page('Hero changes', '<h1>Hero changes</h1>' + sub_tabs('heroes', 'changes')
                                      + toolbar('hero', n_pre, 'Pre-release') + dyn, rel, 'heroes', wide=True))
    return live, shared, has_shared, len(heroes)


def _build_items(ctx: dict) -> list[dict]:
    """Item pages, the shop (Items index) with its tooltips, the item matrix. Returns the items."""
    ents, by_ent, cards, rel = ctx['ents'], ctx['by_ent'], ctx['cards'], ctx['rel']
    items = [e for e in ents.values() if e['file'] == 'abilities.vdata' and e['kind'] == 'item'
             and e['id'].startswith('upgrade_') and not e.get('template')
             and (e.get('tier') or f"abilities.vdata:{e['id']}" in by_ent)]
    for it in items:
        write(slug(it['file'], it['id']), item_page(it, cards.get(it['id']), by_ent, ctx['by_subject']))
    # laid out like the game's shop: tiers x Weapon / Spirit / Vitality (builders/shop_page.py)
    from .dynamics_page import item_entries, matrix_html, toolbar
    from .shop_page import shop_html
    shop, tips = shop_html(items, cards, rel)
    write('items/shop-tips.json', tips)          # the tooltips, loaded on the first hover
    body = ('<h1>Items</h1>' + sub_tabs('items', 'index') +
            '<div class="toolbar"><input type="search" placeholder="Item…" data-search-target=".gcard"></div>' + shop)
    entries = item_entries(items, cards, rel)
    n_gone = sum(1 for e in entries if e[4])
    write('items/changes.html', page('Item changes', '<h1>Item changes</h1>' + sub_tabs('items', 'changes')
                                     + toolbar('item', n_gone, 'Removed') + matrix_html(entries, 'item'),
                                     rel, 'items', wide=True))
    from .game_shop import FONTS as SHOP_FONTS
    write('items/index.html', page('Items', body, rel, 'items', fonts=SHOP_FONTS))
    return items


def _unit_group(ms: list[dict]) -> str:
    """A family's group on the Units index; an unnamed unit the code spawns sits with the helpers
    (unit_families.is_named)."""
    from .unit_families import is_named
    return ms[0]['kind'] if is_named(ms[0]) else 'helper'


def _build_units(ctx: dict) -> tuple[list[dict], dict, list[tuple], int]:
    """One page per unit family (the other members point to it) and the Units index. Returns (the units, the
    families, the named ones for the search, pages written)."""
    ents, rel = ctx['ents'], ctx['rel']
    units_t = ctx['units_t']
    urow = {r['id']: r for r in units_t['units']}
    units = [e for e in ents.values() if e['file'] == 'npc_units.vdata' and not e.get('template')]
    bound = defaultdict(list)                  # unit id -> the abilities it binds (Walker's Stomp…)
    for e in ctx['by_id'].values():
        for uid in e.get('units') or ():
            bound[uid].append(e)
    from .unit_families import families
    fams = families(units)
    for name, members in fams.items():
        main = members[0]
        page_path = slug(main['file'], main['id'])
        write(page_path, unit_page(members, urow, units_t['columns'], ctx['by_ent'], ctx['by_subject'], bound))
        for m in members[1:]:
            write(slug(m['file'], m['id']), redirect_page(page_path.split('/', 1)[1], name))
    write('units/index.html', page('Units', _units_index(fams, rel), rel, 'units'))
    named = [(n, ms[0]) for n, ms in fams.items() if _unit_group(ms) != 'helper']
    return units, fams, named, len(fams)


def _units_index(fams: dict, rel: str) -> str:
    """The Units index body: a card per family by group, the Removed and helpers switches."""
    from .unit_families import tier_of
    groups = []
    for kind, title in UNIT_GROUPS:
        sel = sorted(((n, ms) for n, ms in fams.items() if _unit_group(ms) == kind),
                     key=lambda kv: (not kv[1][0].get('alive'), kv[0]))
        if not sel:
            continue
        cards_html = []
        for n, ms in sel:
            tiers = list(dict.fromkeys(tier_of(m) for m in ms if tier_of(m)))
            copies = len(ms) // max(len(tiers), 1)
            sub = ('removed' if not ms[0].get('alive') else
                   ' · '.join(([' '.join(tiers)] if tiers else []) + ([f'×{copies}'] if copies > 1 else [])))
            cards_html.append(_card({**ms[0], 'name': n}, entity_icon(ms[0]['file'], ms[0]['id'], kind, rel), sub))
        # the Hideout's toys, the bots' brain, effect-only entries: behind their own switch
        wrap = ' class="helper-group"' if kind == 'helper' else ''
        groups.append(f'<div{wrap}><div class="grid-group-title">{esc(title)}</div><div class="grid units">'
                      + ''.join(cards_html) + '</div></div>')
    # the two switches count apart (round 3: "Removed 39" and "Unnamed & helpers 65" overlapped)
    n_gone = sum(1 for ms in fams.values() if not ms[0].get('alive') and _unit_group(ms) != 'helper')
    n_helpers = sum(1 for ms in fams.values() if _unit_group(ms) == 'helper')
    # every removed unit so far is an unnamed one: the helpers' switch says so (round 4: "where are the
    # removed units?" — no Removed switch, they hid behind "Unnamed & helpers")
    n_gone_helpers = sum(1 for ms in fams.values() if not ms[0].get('alive') and _unit_group(ms) == 'helper')
    helpers_label = 'Unnamed, removed & helpers' if n_gone_helpers and not n_gone else 'Unnamed & helpers'
    gone_switch = ''.join(
        f'<label class="switch"><input type="checkbox" data-toggle-class="{cls}" data-target="#units-grid">'
        f'<span class="track"></span>{label} <span class="n">{n}</span></label>'
        for cls, label, n in (('show-gone', 'Removed', n_gone), ('show-helpers', helpers_label, n_helpers)) if n)
    gone_switch = f'<span class="sep"></span>{gone_switch}' if gone_switch else ''
    return ('<h1>Units</h1>' + sub_tabs('units', 'index')
            + f'<div class="toolbar"><input type="search" placeholder="Unit…" data-search-target=".card">{gone_switch}</div>'
            + f'<div id="units-grid">{"".join(groups)}</div>')
