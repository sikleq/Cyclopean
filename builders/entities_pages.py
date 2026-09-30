"""Hero, item and unit pages + their index grids.

Each page shows the entity's full change history, patch by patch (newest
first): the official note lines about it and every change in the files,
with hidden ones marked.
"""
from __future__ import annotations

from collections import defaultdict

from .common import (entity_icon, esc, hero_icon, icon, img, load_json, mark, page, slug, write)
from .render import KIND_LABEL, change_li, sort_changes

GAMEPLAY = ('balance', 'mechanic', 'availability')
UNIT_GROUPS = (('building', 'Buildings & objectives'), ('trooper', 'Troopers'), ('neutral', 'Neutrals'),
               ('unit', 'Other units'))
SLOT_NAMES = {'EItemSlotType_WeaponMod': 'Weapon', 'EItemSlotType_Armor': 'Vitality', 'EItemSlotType_Tech': 'Spirit'}


def _history() -> tuple[dict, dict, list]:
    """entity key -> [(patch row, changes)], subject name -> [(patch row, lines)], patch rows."""
    index = load_json('patches/index.json')
    by_ent: dict[str, list] = defaultdict(list)
    by_subject: dict[str, list] = defaultdict(list)
    for row in index:
        p = load_json(f'patches/{row["id"]}.json.gz')
        for e in p['entities']:
            ch = [c for c in e['changes'] if c['cat'] in GAMEPLAY]
            if ch:
                by_ent[e['key']].append((row, ch))
        for s in p['sections']:
            for ln in s['lines']:
                if ln.get('subject'):
                    by_subject[ln['subject'].strip().lower()].append((row, ln))
    return by_ent, by_subject, index


def _timeline(keys: list[tuple[str, str]], names: list[str], by_ent, by_subject, rel: str) -> str:
    """keys: [(entity key, display name)] shown together (hero + abilities)."""
    per_patch: dict[str, dict] = {}
    for key, nm in keys:
        for row, ch in by_ent.get(key, []):
            slot = per_patch.setdefault(row['id'], {'row': row, 'ents': [], 'lines': []})
            slot['ents'].append((key, nm, ch))
    for n in names:
        for row, ln in by_subject.get(n.lower(), []):
            slot = per_patch.setdefault(row['id'], {'row': row, 'ents': [], 'lines': []})
            if ln not in slot['lines']:
                slot['lines'].append(ln)
    if not per_patch:
        return '<p class="muted">No recorded changes.</p>'
    out = []
    for pid in sorted(per_patch, key=lambda k: per_patch[k]['row']['date'], reverse=True):
        slot = per_patch[pid]
        row = slot['row']
        hidden = sum(1 for _, _, ch in slot['ents'] for c in ch if c.get('status') == 'hidden')
        hid_chip = f'<span class="chip">{mark("hidden")}{hidden} hidden</span>' if hidden else ''
        out.append(f'<section class="section px-frame"><h3 class="section-title">'
                   f'<a href="{rel}patches/{esc(pid)}.html">{esc(row["title"])}</a>'
                   f'<span class="dimmer">{esc(row["date"])}</span>{hid_chip}</h3>')
        if slot['lines']:
            out.append('<ul class="note-lines">' + ''.join(
                f'<li class="st-{esc(ln["status"])}">{mark(ln["status"]) if ln["status"] in ("documented", "rounded", "described", "mismatch", "fix") else "<span class=mark></span>"}'
                f'<span class="txt">{esc(ln["text"])}</span></li>' for ln in slot['lines']) + '</ul>')
        for key, nm, ch in slot['ents']:
            if len(keys) > 1:
                out.append(f'<div class="entity-sub-head">{esc(nm)}</div>')
            out.append('<ul class="change-list">' + ''.join(change_li(c) for c in sort_changes(ch)) + '</ul>')
        out.append('</section>')
    return ''.join(out)


def hero_page(h: dict, ents: dict, table_row: dict | None, table_cols: list, by_ent, by_subject) -> str:
    rel = '../'
    hid = h['id']
    card = (icon(f'heroes/card:{hid}', rel) or icon(f'heroes/vertical:{hid}', rel) or hero_icon(hid, rel))
    abilities = sorted((e for e in ents.values() if e.get('owner') == hid and e['kind'] in ('ability', 'weapon', 'melee')
                        and e.get('alive')), key=lambda e: (e['kind'] != 'weapon', e.get('name') or ''))
    pills = ''.join(
        f'<span class="ability-pill">{img(entity_icon(a["file"], a["id"], a["kind"], rel), "", "px")}'
        f'<span>{esc(a.get("name") or a["id"])}<br><span class="dimmer">{esc(KIND_LABEL.get(a["kind"], ""))}</span></span></span>'
        for a in abilities if a['kind'] != 'melee')
    stats = ''
    if table_row:
        vals = table_row['values']
        picks = [c for c in table_cols if c['key'] in ('hp', 'hp_lvl', 'hp_regen', 'move', 'sprint', 'stamina', 'dps',
                                                          'bullet_dmg', 'clip', 'reload', 'bps', 'light_melee', 'heavy_melee',
                                                          'spirit_lvl', 'bullet_resist', 'spirit_resist')]
        stats = '<dl class="kv">' + ''.join(
            f'<dt>{esc(c["label"])}</dt><dd>{_fmt(vals.get(c["key"]), c["digits"])}</dd>' for c in picks) + '</dl>'
    state = ' <span class="chip">pre-release</span>' if h.get('state') == 'EHeroDevState_PreRelease' else ''
    gone = '' if h.get('alive') else ' <span class="tag del">REMOVED</span>'
    banner = (f'<div class="hero-banner"><div>{img(card, h.get("name", ""), "card-art px-frame")}</div><div>'
              f'<h1>{esc(h.get("name"))}{state}{gone}</h1>'
              f'<div class="meta muted">First seen: build {h["first"][0]} ({esc(h["first"][1])}) · internal id <code>{esc(hid)}</code></div>'
              f'<h3>Abilities</h3><div class="abilities">{pills or "<span class=muted>—</span>"}</div>'
              f'<h3>Current stats</h3>{stats or "<p class=muted>Not in the stats table.</p>"}'
              f'<p><a href="{rel}tables/heroes.html">Full stats table →</a></p></div></div>')
    keys = [(f'heroes.vdata:{hid}', h.get('name'))] + [(f'abilities.vdata:{a["id"]}', a.get('name') or a['id'])
                                                        for a in sorted((e for e in ents.values() if e.get('owner') == hid),
                                                                        key=lambda e: e.get('name') or '')]
    body = (f'<div class="crumbs"><a href="index.html">Heroes</a> / {esc(h.get("name"))}</div>' + banner +
            '<h2>History</h2>' + _timeline(keys, [h.get('name') or ''], by_ent, by_subject, rel))
    return page(h.get('name') or hid, body, rel, 'heroes', description=f'Deadlock {h.get("name")}: every change, including hidden ones')


def _fmt(v, digits) -> str:
    if v is None:
        return '<span class="dash">—</span>'
    s = f'{v:.{max(digits, 0)}f}'
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return s


def item_page(it: dict, by_ent, by_subject) -> str:
    rel = '../'
    ic = entity_icon(it['file'], it['id'], it['kind'], rel)
    gone = '' if it.get('alive') else ' <span class="tag del">REMOVED</span>'
    disabled = ' <span class="chip">not in shop</span>' if it.get('disabled') else ''
    tier = it.get('tier', '').replace('EModTier_', 'Tier ')
    slot_name = SLOT_NAMES.get(it.get('slot', ''), '')
    head = (f'<div class="page-head">{img(ic, "", "head-icon px px-frame")}<div><h1>{esc(it.get("name"))}{gone}{disabled}</h1>'
            f'<div class="meta">{esc(slot_name)} · {esc(tier)} · first seen build {it["first"][0]} ({esc(it["first"][1])})'
            f' · <code>{esc(it["id"])}</code></div></div></div>')
    body = (f'<div class="crumbs"><a href="index.html">Items</a> / {esc(it.get("name"))}</div>' + head + '<h2>History</h2>' +
            _timeline([(f'abilities.vdata:{it["id"]}', it.get('name'))], [it.get('name') or ''], by_ent, by_subject, rel))
    return page(it.get('name') or it['id'], body, rel, 'items')


def unit_page(u: dict, by_ent, by_subject) -> str:
    rel = '../'
    ic = entity_icon(u['file'], u['id'], u['kind'], rel)
    gone = '' if u.get('alive') else ' <span class="tag del">REMOVED</span>'
    head = (f'<div class="page-head">{img(ic, "", "head-icon px px-frame")}<div><h1>{esc(u.get("name"))}{gone}</h1>'
            f'<div class="meta">{esc(KIND_LABEL.get(u["kind"], u["kind"]))} · first seen build {u["first"][0]} ({esc(u["first"][1])})'
            f' · <code>{esc(u["id"])}</code></div></div></div>')
    body = (f'<div class="crumbs"><a href="index.html">Units</a> / {esc(u.get("name"))}</div>' + head + '<h2>History</h2>' +
            _timeline([(f'npc_units.vdata:{u["id"]}', u.get('name'))], [u.get('name') or ''], by_ent, by_subject, rel))
    return page(u.get('name') or u['id'], body, rel, 'units')


def _card(e: dict, rel_icon: str | None, sub: str = '') -> str:
    href = slug(e['file'], e['id']).split('/', 1)[1]
    cls = 'card px-frame' + ('' if e.get('alive') else ' gone')
    return (f'<a class="{cls}" href="{esc(href)}" data-search="{esc((e.get("name") or "").lower())} {esc(e["id"])}">'
            f'{img(rel_icon, "", "px")}<span class="nm">{esc(e.get("name") or e["id"])}</span>'
            f'<span class="sub">{esc(sub)}</span></a>')


def build_all() -> dict[str, int]:
    data = load_json('entities.json')
    ents = {f"{e['file']}:{e['id']}": e for e in data['entities']}
    by_ent, by_subject, _ = _history()
    table = load_json('tables/heroes.json')
    trow = {r['id']: r for r in table['heroes']}
    rel = '../'
    counts = {'heroes': 0, 'items': 0, 'units': 0}

    heroes = [e for e in ents.values() if e['file'] == 'heroes.vdata' and not e.get('template')
              and (e.get('state') in ('EHeroDevState_Release', 'EHeroDevState_PreRelease') or e['id'] in trow
                   or f"heroes.vdata:{e['id']}" in by_ent)]
    by_id = {e['id']: e for e in ents.values() if e['file'] == 'abilities.vdata'}
    for h in heroes:
        write(slug(h['file'], h['id']), hero_page(h, by_id, trow.get(h['id']), table['columns'], by_ent, by_subject))
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
        write(slug(it['file'], it['id']), item_page(it, by_ent, by_subject))
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
        write(slug(u['file'], u['id']), unit_page(u, by_ent, by_subject))
        counts['units'] += 1
    groups = []
    for kind, title in UNIT_GROUPS:
        sel = sorted((u for u in units if u['kind'] == kind), key=lambda u: (not u.get('alive'), u.get('name') or ''))
        if sel:
            groups.append(f'<div class="grid-group-title">{esc(title)}</div><div class="grid units">'
                          + ''.join(_card(u, entity_icon(u['file'], u['id'], kind, rel), u['id']) for u in sel) + '</div>')
    body = ('<h1>Units</h1><div class="toolbar"><input type="search" placeholder="Unit…" data-search-target=".card"></div>'
            + ''.join(groups))
    write('units/index.html', page('Units', body, rel, 'units'))
    return counts
