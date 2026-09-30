"""Hero, item and unit pages + their index grids."""
from __future__ import annotations

from collections import defaultdict

from .common import entity_icon, esc, hero_icon, img, load_json, page, pretty_id, slug, write
from .hero_page import hero_page, history_table, stat_tables
from .render import KIND_LABEL

GAMEPLAY = ('balance', 'mechanic', 'availability')
UNIT_GROUPS = (('building', 'Buildings & objectives'), ('trooper', 'Troopers'), ('neutral', 'Neutrals'),
               ('unit', 'Other units'))
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
        if info.get('cost'):
            chips.append(f'<span class="chip">{info["cost"]} souls</span>')
    head = (f'<div class="crumbs"><a href="index.html">Items</a> / {esc(name)}</div>'
            f'<div class="page-head">{img(ic, "", "head-icon px px-frame")}<div><h1>{esc(name)}{gone}{disabled}</h1>'
            f'<div class="chips">{"".join(chips)}</div>'
            f'<div class="meta">First seen: build {it["first"][0]} ({esc(it["first"][1])})</div></div></div>')
    sections = ''
    if card:
        blocks = []
        for s in card.get('sections', []):
            rows = ''.join(f'<tr><td>{esc(r["label"])}</td><td class="v">{esc(r["value"])}'
                           f'{"<span class=scale>+" + format(r["scale"], "g") + "×Spirit</span>" if r.get("scale") else ""}</td></tr>'
                           for r in s['props'])
            desc = f'<div class="ac-desc">{esc(s["desc"])}</div>' if s.get('desc') else ''
            blocks.append(f'<div class="ability-card px-frame"><div class="ac-head"><div class="ac-name">{esc(s["type"])}</div></div>'
                          f'{desc}<table class="kvt">{rows}</table></div>')
        hdr = ''
        if card.get('header'):
            hdr = '<div class="chips item-hdr">' + ''.join(
                f'<span class="chip">{esc(h["label"])} {esc(h["value"])}</span>' for h in card['header']) + '</div>'
        sections = ('<h2>Current values</h2>' + hdr + '<div class="ability-grid">' + ''.join(blocks) + '</div>'
                    if blocks or hdr else '')
    hist = history_table([(f'abilities.vdata:{it["id"]}', name, ic)], [name], by_ent, by_subject, rel)
    body = head + sections + '<h2>History</h2>' + hist
    return page(name, body, rel, 'items')


def unit_page(u: dict, trow: dict | None, cols: list[dict], by_ent, by_subject) -> str:
    rel = '../'
    name = u['name'] if u.get('name') and u['name'] != u['id'] else pretty_id(u['id'])
    ic = entity_icon(u['file'], u['id'], u['kind'], rel)
    gone = '' if u.get('alive') else ' <span class="tag del">REMOVED</span>'
    head = (f'<div class="crumbs"><a href="index.html">Units</a> / {esc(name)}</div>'
            f'<div class="page-head">{img(ic, "", "head-icon px px-frame")}<div><h1>{esc(name)}{gone}</h1>'
            f'<div class="chips"><span class="chip">{esc(KIND_LABEL.get(u["kind"], u["kind"]))}</span></div>'
            f'<div class="meta">First seen: build {u["first"][0]} ({esc(u["first"][1])})</div></div></div>')
    stats = ''
    if trow:
        stats = '<h2>Stats</h2>' + stat_tables(trow, cols, name, rel)
    hist = history_table([(f'npc_units.vdata:{u["id"]}', name, ic)], [name], by_ent, by_subject, rel)
    return page(name, head + stats + '<h2>History</h2>' + hist, rel, 'units')


def _card(e: dict, rel_icon: str | None, sub: str = '') -> str:
    href = slug(e['file'], e['id']).split('/', 1)[1]
    cls = 'card px-frame' + ('' if e.get('alive') else ' gone')
    name = e['name'] if e.get('name') and e['name'] != e['id'] else pretty_id(e['id'], e.get('owner'))
    return (f'<a class="{cls}" href="{esc(href)}" data-search="{esc(name.lower())} {esc(e["id"])}">'
            f'{img(rel_icon, "", "px")}<span class="nm">{esc(name)}</span>'
            f'<span class="sub">{esc(sub)}</span></a>')


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
    grid = ''.join(_card(h, hero_icon(h['id'], rel), 'pre-release' if h.get('state') == 'EHeroDevState_PreRelease' else '')
                   for h in live)
    grid2 = ''.join(_card(h, hero_icon(h['id'], rel), 'unreleased') for h in other)
    body = ('<h1>Heroes</h1><div class="toolbar"><input type="search" placeholder="Hero…" data-search-target=".card"></div>'
            f'<div class="grid heroes">{grid}</div>'
            + (f'<div class="grid-group-title">Unreleased & hero labs</div><div class="grid heroes">{grid2}</div>' if grid2 else ''))
    write('heroes/index.html', page('Heroes', body, rel, 'heroes'))

    items = [e for e in ents.values() if e['file'] == 'abilities.vdata' and e['kind'] == 'item'
             and e['id'].startswith('upgrade_') and not e.get('template')
             and (e.get('tier') or f"abilities.vdata:{e['id']}" in by_ent)]
    for it in items:
        write(slug(it['file'], it['id']), item_page(it, cards.get(it['id']), by_ent, by_subject))
        counts['items'] += 1
    groups = []
    for slot, title in SLOT_NAMES.items():
        sel = sorted((i for i in items if i.get('slot') == slot and i.get('alive') and not i.get('disabled')),
                     key=lambda i: (i.get('tier', ''), i.get('name') or ''))
        if sel:
            groups.append(f'<div class="grid-group-title">{esc(title)}</div><div class="grid items">'
                          + ''.join(_card(i, entity_icon(i['file'], i['id'], 'item', rel), i.get('tier', '').replace('EModTier_', 'T'))
                                    for i in sel) + '</div>')
    gone = sorted((i for i in items if not i.get('alive') or i.get('disabled')), key=lambda i: i.get('name') or '')
    if gone:
        groups.append('<div class="grid-group-title">Removed or disabled</div><div class="grid items">'
                      + ''.join(_card(i, entity_icon(i['file'], i['id'], 'item', rel), 'gone') for i in gone) + '</div>')
    body = ('<h1>Items</h1><div class="toolbar"><input type="search" placeholder="Item…" data-search-target=".card"></div>'
            + ''.join(groups))
    write('items/index.html', page('Items', body, rel, 'items'))

    units = [e for e in ents.values() if e['file'] == 'npc_units.vdata' and not e.get('template')]
    for u in units:
        write(slug(u['file'], u['id']), unit_page(u, urow.get(u['id']), units_t['columns'], by_ent, by_subject))
        counts['units'] += 1
    groups = []
    for kind, title in UNIT_GROUPS:
        sel = sorted((u for u in units if u['kind'] == kind), key=lambda u: (not u.get('alive'), u.get('name') or ''))
        if sel:
            groups.append(f'<div class="grid-group-title">{esc(title)}</div><div class="grid units">'
                          + ''.join(_card(u, entity_icon(u['file'], u['id'], kind, rel), '' if u.get('alive') else 'removed')
                                    for u in sel) + '</div>')
    body = ('<h1>Units</h1><div class="toolbar"><input type="search" placeholder="Unit…" data-search-target=".card"></div>'
            + ''.join(groups))
    write('units/index.html', page('Units', body, rel, 'units'))
    return counts
