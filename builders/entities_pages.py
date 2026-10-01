"""Hero, item and unit pages + their index grids."""
from __future__ import annotations

from collections import defaultdict

from .common import entity_icon, esc, glyph_for, hero_icon, img, load_json, page, pretty_id, slug, write
from .hero_page import hero_page, history_heading, history_table, prop_icon, prop_rows, stat_tables
from .render import KIND_LABEL

GAMEPLAY = ('balance', 'mechanic', 'availability')
UNIT_GROUPS = (('building', 'Buildings & objectives'), ('trooper', 'Troopers'), ('neutral', 'Neutrals'),
               ('unit', 'Other units'), ('helper', 'Hideout, bots & effects'))
SLOT_NAMES = {'EItemSlotType_WeaponMod': 'Weapon', 'EItemSlotType_Armor': 'Vitality', 'EItemSlotType_Tech': 'Spirit'}


def _history() -> tuple[dict, dict]:
    """entity key -> [(patch row, changes)], note subject -> [(patch row, line)]."""
    by_ent: dict[str, list] = defaultdict(list)
    by_subject: dict[str, list] = defaultdict(list)
    for row in load_json('patches/index.json'):
        p = load_json(f'patches/{row["id"]}.json.gz')
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
    name = it['name'] if it.get('name') and it['name'] != it['id'] else pretty_id(it['id'])
    ic = entity_icon(it['file'], it['id'], it['kind'], rel)
    gone = '' if it.get('alive') else ' <span class="tag del">REMOVED</span>'
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
            chips.append(f'<span class="chip">{info["cost"]} souls</span>')
    head = (f'<div class="crumbs"><a href="index.html">Items</a> / {esc(name)}</div>'
            f'<div class="page-head">{img(ic, "", "head-icon px px-frame", "abilities")}<div><h1>{esc(name)}{gone}{disabled}</h1>'
            f'<div class="chips">{"".join(chips)}</div>'
            f'<div class="meta">First seen: build {it["first"][0]} ({esc(it["first"][1])})</div></div></div>')
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
        sections = ('<h2>Current values</h2>' + hdr + ''.join(blocks)) if blocks or hdr else ''
    hist = history_table([(f'abilities.vdata:{it["id"]}', name, ic)], [name], by_ent, by_subject, rel)
    history = history_heading() + f'<div id="history">{hist}</div>'
    # current values beside the history (design review: the values sat above a screen of empty space)
    body = head + (f'<div class="item-layout"><aside class="item-now">{sections}</aside><div>{history}</div></div>'
                   if sections else history)
    return page(name, body, rel, 'items')


def unit_page(u: dict, trow: dict | None, cols: list[dict], by_ent, by_subject) -> str:
    rel = '../'
    name = u['name'] if u.get('name') and u['name'] != u['id'] else pretty_id(u['id'])
    ic = entity_icon(u['file'], u['id'], u['kind'], rel)
    gone = '' if u.get('alive') else ' <span class="tag del">REMOVED</span>'
    head = (f'<div class="crumbs"><a href="index.html">Units</a> / {esc(name)}</div>'
            f'<div class="page-head">{img(ic, "", "head-icon px px-frame", "units")}<div><h1>{esc(name)}{gone}</h1>'
            f'<div class="chips"><span class="chip">{esc(KIND_LABEL.get(u["kind"], u["kind"]))}</span></div>'
            f'<div class="meta">First seen: build {u["first"][0]} ({esc(u["first"][1])})</div></div></div>')
    stats = ''
    if trow:
        stats = '<h2>Stats</h2>' + stat_tables(trow, cols, name, rel)
    hist = history_table([(f'npc_units.vdata:{u["id"]}', name, ic)], [name], by_ent, by_subject, rel)
    return page(name, head + stats + history_heading() + f'<div id="history">{hist}</div>', rel, 'units')


_VARIANT_STOP = {'npc', 'neutral', 'citadel'}


def unit_variants(units: list[dict]) -> dict[str, str]:
    """Units that share a name (4 Walkers, 5 "Gutter Ghoul I") get what tells them apart: the words
    of their id the namesakes do not share ('alt weak', 'amber', 'dock creature', 'model 2')."""
    by_name: dict[str, list[dict]] = defaultdict(list)
    for u in units:
        if u.get('alive'):
            by_name[u.get('name') or u['id']].append(u)
    out = {}
    for group in by_name.values():
        if len(group) < 2:
            continue
        toks = {u['id']: u['id'].split('_') for u in group}
        common = set.intersection(*(set(t) for t in toks.values()))
        for uid, t in toks.items():
            rest = [w for w in t if w not in common and w not in _VARIANT_STOP]
            out[uid] = ' '.join(f'model {int(w)}' if w.isdigit() else w for w in rest)
    return out


SUB_TABS = {'heroes': (('index', 'Heroes'), ('changes', 'Hero changes')),
            'items': (('index', 'Items'), ('changes', 'Item changes')),
            'units': (('index', 'Units'), ('changes', 'Unit changes'))}


def sub_tabs(section: str, active: str) -> str:
    """The grid and its change matrix (Sloppy's Materials / Dynamics pair)."""
    return '<div class="flex table-tabs">' + ''.join(
        f'<a class="px-btn{" on" if k == active else ""}" href="{k}.html">{esc(lbl)}</a>'
        for k, lbl in SUB_TABS[section]) + '</div>'


def _card(e: dict, rel_icon: str | None, sub: str = '', foot: str = '') -> str:
    href = slug(e['file'], e['id']).split('/', 1)[1]
    cls = 'card px-frame' + ('' if e.get('alive') else ' gone')
    name = e['name'] if e.get('name') and e['name'] != e['id'] else pretty_id(e['id'], e.get('owner'))
    return (f'<a class="{cls}" href="{esc(href)}" data-search="{esc(name.lower())} {esc(e["id"])}">'
            f'{img(rel_icon, "", "px", glyph_for(e["file"], e["id"]))}<span class="nm">{esc(name)}</span>'
            f'<span class="sub">{esc(sub)}</span>{foot}</a>')


def build_all() -> dict[str, int]:
    data = load_json('entities.json')
    ents = {f"{e['file']}:{e['id']}": e for e in data['entities']}
    by_ent, by_subject = _history()
    table = load_json('tables/heroes.json')
    trow = {r['id']: r for r in table['heroes']}
    units_t = load_json('tables/units.json')
    urow = {r['id']: r for r in units_t['units']}
    cards = load_json('abilities.json')['abilities']
    rel = '../'
    counts = {'heroes': 0, 'items': 0, 'units': 0}

    heroes = [e for e in ents.values() if e['file'] == 'heroes.vdata' and not e.get('template')
              and (e.get('state') in ('EHeroDevState_Release', 'EHeroDevState_PreRelease') or e['id'] in trow
                   or f"heroes.vdata:{e['id']}" in by_ent)]
    by_id = {e['id']: e for e in ents.values() if e['file'] == 'abilities.vdata'}
    for h in heroes:
        write(slug(h['file'], h['id']), hero_page(h, cards, trow.get(h['id']), table['columns'], by_id, by_ent, by_subject))
        counts['heroes'] += 1
    live = sorted((h for h in heroes if h.get('state') in ('EHeroDevState_Release', 'EHeroDevState_PreRelease')),
                  key=lambda h: h.get('name') or '')
    other = sorted((h for h in heroes if h not in live), key=lambda h: h.get('name') or '')
    from .dynamics_page import hero_entries, matrix_html, toolbar
    from .heroes_grid import heroes_grid_html, pre_release_switch
    body = ('<h1>Heroes</h1>' + sub_tabs('heroes', 'index') +
            '<div class="toolbar"><input type="search" placeholder="Hero…" data-search-target=".hgcard">'
            f'<span class="sep"></span>{pre_release_switch(live)}</div>'
            + heroes_grid_html(live, other, trow, rel))
    write('heroes/index.html', page('Heroes', body, rel, 'heroes'))
    n_pre = sum(1 for h in live if h.get('state') != 'EHeroDevState_Release')
    dyn = matrix_html(hero_entries(live, rel), 'hero')
    write('heroes/changes.html', page('Hero changes', '<h1>Hero changes</h1>' + sub_tabs('heroes', 'changes')
                                      + toolbar('hero', n_pre, 'Pre-release') + dyn, rel, 'heroes', wide=True))

    items = [e for e in ents.values() if e['file'] == 'abilities.vdata' and e['kind'] == 'item'
             and e['id'].startswith('upgrade_') and not e.get('template')
             and (e.get('tier') or f"abilities.vdata:{e['id']}" in by_ent)]
    for it in items:
        write(slug(it['file'], it['id']), item_page(it, cards.get(it['id']), by_ent, by_subject))
        counts['items'] += 1
    # laid out like the game's shop: tiers x Weapon / Spirit / Vitality (builders/shop_page.py)
    from .dynamics_page import item_entries
    from .shop_page import shop_html
    body = ('<h1>Items</h1>' + sub_tabs('items', 'index') +
            '<div class="toolbar"><input type="search" placeholder="Item…" data-search-target=".icard"></div>'
            + shop_html(items, cards, rel))
    entries = item_entries(items, cards, rel)
    n_gone = sum(1 for e in entries if e[4])
    write('items/changes.html', page('Item changes', '<h1>Item changes</h1>' + sub_tabs('items', 'changes')
                                     + toolbar('item', n_gone, 'Removed') + matrix_html(entries, 'item'),
                                     rel, 'items', wide=True))
    write('items/index.html', page('Items', body, rel, 'items'))

    units = [e for e in ents.values() if e['file'] == 'npc_units.vdata' and not e.get('template')]
    for u in units:
        write(slug(u['file'], u['id']), unit_page(u, urow.get(u['id']), units_t['columns'], by_ent, by_subject))
        counts['units'] += 1
    groups = []
    variants = unit_variants(units)
    for kind, title in UNIT_GROUPS:
        sel = sorted((u for u in units if u['kind'] == kind), key=lambda u: (not u.get('alive'), u.get('name') or ''))
        if sel:
            # the Hideout's toys, the bots' brain, effect-only entries: behind their own switch
            wrap = ' class="helper-group"' if kind == 'helper' else ''
            groups.append(f'<div{wrap}><div class="grid-group-title">{esc(title)}</div><div class="grid units">'
                          + ''.join(_card(u, entity_icon(u['file'], u['id'], kind, rel),
                                          variants.get(u['id'], '') if u.get('alive') else 'removed')
                                    for u in sel) + '</div></div>')
    n_gone = sum(1 for u in units if not u.get('alive'))
    n_helpers = sum(1 for u in units if u['kind'] == 'helper')
    gone_switch = ''.join(
        f'<label class="switch"><input type="checkbox" data-toggle-class="{cls}" data-target="#units-grid">'
        f'<span class="track"></span>{label} <span class="n">{n}</span></label>'
        for cls, label, n in (('show-gone', 'Removed', n_gone), ('show-helpers', 'Hideout, bots & effects', n_helpers)) if n)
    gone_switch = f'<span class="sep"></span>{gone_switch}' if gone_switch else ''
    body = ('<h1>Units</h1>' + sub_tabs('units', 'index')
            + f'<div class="toolbar"><input type="search" placeholder="Unit…" data-search-target=".card">{gone_switch}</div>'
            + f'<div id="units-grid">{"".join(groups)}</div>')
    write('units/index.html', page('Units', body, rel, 'units'))
    from .dynamics_page import unit_entries
    entries = unit_entries(units, UNIT_GROUPS, rel)
    n_gone = sum(1 for e in entries if e[4])
    write('units/changes.html', page('Unit changes', '<h1>Unit changes</h1>' + sub_tabs('units', 'changes')
                                     + toolbar('unit', n_gone, 'Removed & helpers') + matrix_html(entries, 'unit'),
                                     rel, 'units', wide=True))
    return counts
