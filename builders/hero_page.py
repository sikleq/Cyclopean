"""Hero page: portrait + key stats, the weapon block, ability cards (the in-game
tooltip rebuilt from data), the remaining stats as compact panels, and the full
history grouped by patch and by ability."""
from __future__ import annotations

import json
import re

from .common import entity_icon, esc, glyph_for, hero_icon, icon, img, mark, page, pretty_id
from .render import HIDDEN_LIKE, entity_rows

SLOT_ORDER = ('Weapon_Primary', 'Weapon_Secondary', 'Signature_1', 'Signature_2', 'Signature_3', 'Signature_4')
SLOT_LABEL = {'Weapon_Primary': 'Weapon', 'Weapon_Secondary': 'Alt weapon', 'Signature_1': 'Ability 1',
              'Signature_2': 'Ability 2', 'Signature_3': 'Ability 3', 'Signature_4': 'Ultimate'}
# the head strip: survivability and movement; gun numbers live in the weapon block right below
KEY_STATS = ('hp', 'hp_lvl', 'hp_regen', 'bullet_resist', 'spirit_resist', 'move', 'sprint', 'stamina', 'spirit_lvl')
WEAPON_GROUP = 'Damage'
LINE_STATUSES = ('documented', 'rounded', 'described', 'mismatch', 'fix')
# in-game stat icons (icons/stats/StatDesc) for the stat cells
STAT_ICON = {
    'dps': 'DPS', 'dps_max': 'DPS', 'bullet_dmg': 'BulletDamage', 'bullet_dmg_lvl': 'BulletDamage',
    'bullet_dmg_max': 'BulletDamage', 'clip': 'ClipSizeBonus', 'full_clip': 'ClipSizeBonus',
    'reload': 'ReloadTime', 'reload_full': 'ReloadTime', 'headshot': 'CritDamageBonusScale',
    'cycle': 'FireRate', 'bps': 'RoundsPerSecond', 'burst_cycle': 'FireRate', 'bullet_speed': 'BulletSpeed',
    'range': 'WeaponRange', 'falloff_start': 'WeaponRange', 'falloff_end': 'WeaponRange', 'range_lvl': 'WeaponRange',
    'light_melee': 'LightMeleeDamage', 'heavy_melee': 'HeavyMeleeDamage', 'melee_lvl': 'MeleeDamage',
    'hp': 'MaxHealth', 'hp_lvl': 'MaxHealth', 'hp_regen': 'BaseHealthRegen',
    'bullet_resist': 'BulletArmorDamageReduction', 'bullet_resist_lvl': 'BulletArmorDamageReduction',
    'spirit_resist': 'TechArmorDamageReduction', 'spirit_resist_lvl': 'TechArmorDamageReduction',
    'headshot_taken': 'CritDamageReceivedScale', 'move': 'RunSpeed', 'sprint': 'SprintSpeed',
    'stamina': 'Stamina', 'stamina_regen': 'StaminaRegenPerSecond', 'ground_dash': 'DashSpeedInMeters',
    'air_dash': 'DashSpeedInMeters', 'spirit_lvl': 'TechPower',
}


def _fmt(v, digits) -> str:
    if v is None:
        return '<span class="dash">—</span>'
    s = f'{v:.{max(digits, 0)}f}'
    return s.rstrip('0').rstrip('.') if '.' in s else s


def _hist_attrs(row: dict, col: dict, name: str) -> tuple[str, str]:
    hist = row['history'].get(col['key'])
    cls = []
    if col['key'] in row.get('spirit_scaled', []):
        cls.append('spirit')
    attrs = f' data-pol="{col["pol"]}" data-digits="{col["digits"]}"'
    if hist:
        cls.append('has-hist')
        attrs += (f' data-hist="{esc(json.dumps(hist, separators=(",", ":")))}"'
                  f' data-title="{esc(name)} · {esc(col["label"])}"')
    return ' '.join(cls), attrs


def _stat_icon(key: str, rel: str) -> str:
    src = icon(f'StatDesc:{STAT_ICON[key]}', rel) if key in STAT_ICON else None
    return f'<img class="si" src="{esc(src)}" alt="" loading="lazy">' if src else '<span class="si"></span>'


def key_stats(row: dict, cols: list[dict], name: str, rel: str = '../') -> str:
    by_key = {c['key']: c for c in cols}
    out = []
    for k in KEY_STATS:
        c = by_key.get(k)
        v = row['values'].get(k)
        if not c or v is None or (v == 0 and k.endswith('_resist')):     # base resists are 0 for most heroes
            continue
        cls, attrs = _hist_attrs(row, c, name)
        out.append(f'<div class="keystat {cls}"{attrs}>{_stat_icon(k, rel)}<div class="v">{_fmt(row["values"][k], c["digits"])}</div>'
                   f'<div class="l">{esc(c["label"])}</div></div>')
    return '<div class="keystats">' + ''.join(out) + '</div>'


def _cells(row: dict, cs: list[dict], name: str, rel: str) -> str:
    out = []
    for c in cs:
        v = row['values'].get(c['key'])
        if v is None:
            continue
        cls, attrs = _hist_attrs(row, c, name)
        out.append(f'<div class="sc-row"><span class="k">{_stat_icon(c["key"], rel)}{esc(c["label"])}</span>'
                   f'<span class="v {cls}"{attrs}>{_fmt(v, c["digits"])}</span></div>')
    return ''.join(out)


def stat_tables(row: dict, cols: list[dict], name: str, rel: str = '../', skip: tuple[str, ...] = ()) -> str:
    """Stat groups as compact panels that flow in columns (no tall-block gaps)."""
    groups: dict[str, list[dict]] = {}
    for c in cols:
        if c['group'] not in skip:
            groups.setdefault(c['group'], []).append(c)
    parts = []
    for g, cs in groups.items():
        body = _cells(row, cs, name, rel)
        if body:
            parts.append(f'<section class="stat-panel"><h3>{esc(g)}</h3>{body}</section>')
    return '<div class="stat-flow">' + ''.join(parts) + '</div>' if parts else ''


def weapon_block(card: dict | None, row: dict, cols: list[dict], name: str, rel: str) -> str:
    """The gun is not an ability: its own block, first, with every Damage-group number."""
    wcols = [c for c in cols if c['group'] == WEAPON_GROUP]
    cells = []
    for c in wcols:
        v = row['values'].get(c['key'])
        if v is None:
            continue
        cls, attrs = _hist_attrs(row, c, name)
        cells.append(f'<div class="wcell {cls}"{attrs}>{_stat_icon(c["key"], rel)}<span class="v">{_fmt(v, c["digits"])}</span>'
                     f'<span class="l">{esc(c["label"])}</span></div>')
    wname = (card or {}).get('name') or row.get('weapon_name') or ''
    # heroes in development often have no localized gun name yet: never show the internal id
    name_html = (f'<div class="wb-name">{esc(wname)}</div>' if wname and not wname.startswith('citadel_weapon_')
                 else '<div class="wb-name unnamed">No in-game name yet</div>')
    wid = (card or {}).get('id') or row.get('weapon')
    ic = entity_icon('abilities.vdata', wid, 'weapon', rel) if wid else None
    desc = f'<div class="wb-desc">{esc(card["desc"])}</div>' if card and card.get('desc') else ''
    return (f'<section class="weapon-block px-frame" id="weapon"><div class="wb-id">{img(ic, "", "px", "abilities")}'
            f'<div><div class="wb-kicker">Weapon</div>{name_html}{desc}</div></div>'
            f'<div class="wb-cells">{"".join(cells)}</div></section>')


def prop_icon(css: str | None, rel: str) -> str:
    """The property's icon from the in-game tooltip (m_strCSSClass -> icons/stats/prop)."""
    src = icon(f'prop:{css}', rel) if css else None
    return f'<img class="pi" src="{esc(src)}" alt="" loading="lazy">' if src else '<span class="pi"></span>'


def prop_rows(rows: list[dict], rel: str) -> str:
    out = []
    for r in rows:
        scale = f'<span class="scale">+{r["scale"]:g}×Spirit</span>' if r.get('scale') else ''
        css = r.get('css') or ''
        out.append(f'<tr class="p-{esc(css)}"><td>{prop_icon(css, rel)}{esc(r["label"])}</td>'
                   f'<td class="v">{esc(r["value"])}{scale}</td></tr>')
    return ''.join(out)


def ability_card(c: dict, rel: str, slot_label: str = '') -> str:
    ic = entity_icon('abilities.vdata', c['id'], c['kind'], rel, c.get('name'), c.get('owner'))
    hdr = ''.join(f'<span class="chip p-{esc(h.get("css") or "")}">{prop_icon(h.get("css"), rel)}'
                  f'{esc(h["label"])} <b>{esc(h["value"])}</b></span>' for h in c.get('header', []))
    rows = prop_rows(c.get('important', []) + c.get('basic', []), rel)
    table = f'<table class="kvt">{rows}</table>' if rows else ''
    desc = f'<div class="ac-desc">{esc(c["desc"])}</div>' if c.get('desc') else ''
    tiers = ''.join(
        f'<div class="tier"><span class="tn">T{t["tier"]}</span><span class="tt">'
        f'{esc(t["text"] or ", ".join(b["label"] + " " + b["value"] for b in t["bonuses"]))}</span></div>'
        for t in c.get('tiers', []))
    name = c['name'] if c.get('name') and c['name'] != c['id'] else pretty_id(c['id'], c.get('owner'))
    return (f'<div class="ability-card px-frame" id="{esc(c["id"])}"><div class="ac-head">{img(ic, "", "px", "abilities")}'
            f'<div><div class="ac-name">{esc(name)}</div><div class="ac-sub">{esc(slot_label)}</div></div></div>'
            f'{"<div class=ac-hdr>" + hdr + "</div>" if hdr else ""}{desc}{table}'
            f'{"<div class=tiers>" + tiers + "</div>" if tiers else ""}</div>')


def _strip_subject(text: str, names: list[str]) -> str:
    """'Abrams: Melee damage per boon increased by 10%' -> 'Melee damage per boon …' on
    Abrams' own page: the subject is the page."""
    alts = '|'.join(re.escape(n) for n in names if n)
    if not alts:
        return text
    out = re.sub(rf'^\s*(?:{alts})\s*[:\-–—]\s*', '', text, flags=re.I)
    return out[:1].upper() + out[1:] if out else text


def history_table(keys: list[tuple[str, str, str | None]], names: list[str], by_ent, by_subject, rel: str) -> str:
    """keys: [(entity key, display name, icon url)] in display order; one table, grouped
    by patch (newest first), then by entity: a header per ability, its changes below."""
    order = {k: i for i, (k, _, _) in enumerate(keys)}
    per_patch: dict[str, dict] = {}
    for key, nm, ic in keys:
        for row, ch in by_ent.get(key, []):
            slot = per_patch.setdefault(row['id'], {'row': row, 'ents': {}, 'lines': []})
            ent = slot['ents'].setdefault(key, (nm, ic, []))
            ent[2].extend(ch)
    for n in names:
        for row, ln in by_subject.get(n.lower(), []):
            slot = per_patch.setdefault(row['id'], {'row': row, 'ents': {}, 'lines': []})
            if ln not in slot['lines']:
                slot['lines'].append(ln)
    if not per_patch:
        return '<p class="muted">No recorded changes.</p>'
    trs = []
    for pid in sorted(per_patch, key=lambda k: per_patch[k]['row']['date'], reverse=True):
        slot = per_patch[pid]
        row = slot['row']
        all_ch = [c for _, _, ch in slot['ents'].values() for c in ch]
        n_hidden = sum(1 for c in all_ch if c.get('status') == 'hidden')
        n_dev = sum(1 for c in all_ch if c.get('status') == 'unreleased')
        chips = ''
        if n_hidden:
            chips += f' <span class="chip">{mark("hidden")}{n_hidden} hidden</span>'
        if n_dev:
            chips += f' <span class="chip dev">{mark("unreleased")}{n_dev} in development</span>'
        dev = ' dev' if n_dev else ''
        dev += ' has-hidden' if any(c.get('status', 'hidden') in HIDDEN_LIKE for c in all_ch) else ''
        trs.append(f'<tr class="ph{dev}"><td colspan="4"><a class="t" href="{rel}patches/{esc(pid)}.html">{esc(row["title"])}</a>'
                   f'<span class="d">{esc(row["date"])}</span>{chips}</td></tr>')
        for ln in slot['lines']:
            st = ln['status']
            m = mark(st) if st in LINE_STATUSES else ''
            trs.append(f'<tr class="nl st-{esc(st)}"><td class="st">{m}</td><td colspan="3">'
                       f'{esc(_strip_subject(ln["text"], names))}</td></tr>')
        for key in sorted(slot['ents'], key=lambda k: order[k]):
            nm, ic, ch = slot['ents'][key]
            file, _, eid = key.partition(':')
            trs.extend(entity_rows(nm, ic, ch, glyph=glyph_for(file, eid)))
    return f'<table class="hist grouped">{"".join(trs)}</table>'


def _owned_keys(hid: str, name: str, mine: list[dict], ents_by_id: dict, rel: str) -> list[tuple]:
    """History entities in page order: base stats, weapon, abilities by slot, the rest by name."""
    keys = [(f'heroes.vdata:{hid}', 'Base stats', hero_icon(hid, rel))]
    slot_of = {c['id']: c.get('slot') for c in mine}
    owned = [e for e in ents_by_id.values() if e.get('owner') == hid]

    def rank(e: dict) -> tuple:
        s = slot_of.get(e['id'])
        return (SLOT_ORDER.index(s) if s in SLOT_ORDER else len(SLOT_ORDER), e.get('name') or '')
    for e in sorted(owned, key=rank):
        nm = e.get('name') or e['id']
        if nm == e['id']:
            nm = pretty_id(e['id'], hid)
        keys.append((f'abilities.vdata:{e["id"]}', nm,
                     entity_icon('abilities.vdata', e['id'], e.get('kind', ''), rel, nm, hid)))
    return keys


def hero_page(h: dict, cards: dict, table_row: dict | None, cols: list[dict], ents_by_id: dict,
              by_ent, by_subject) -> str:
    rel = '../'
    hid = h['id']
    name = h.get('name') or hid
    portrait = icon(f'heroes/card:{hid}', rel) or icon(f'heroes/vertical:{hid}', rel) or hero_icon(hid, rel)
    mine = [c for c in cards.values() if c.get('owner') == hid]
    mine.sort(key=lambda c: SLOT_ORDER.index(c['slot']) if c.get('slot') in SLOT_ORDER else 99)
    chips = []
    state = h.get('state')
    if not h.get('alive'):
        chips.append('<span class="tag del">REMOVED</span>')
    elif state == 'EHeroDevState_PreRelease':
        chips.append('<span class="chip">pre-release</span>')
    elif state != 'EHeroDevState_Release':
        chips.append(f'<span class="chip dev">{mark("unreleased")}in development</span>')
    if table_row and table_row.get('type'):
        chips.append(f'<span class="chip">{esc(table_row["type"].rsplit("_", 1)[-1])}</span>')
    head = (f'<div class="hero-head"><div><img class="portrait px-frame" src="{esc(portrait or "")}" alt="{esc(name)}"></div><div>'
            f'<div class="crumbs"><a href="index.html">Heroes</a> / {esc(name)}</div><h1>{esc(name)}</h1>'
            f'<div class="meta">First seen: build {h["first"][0]} ({esc(h["first"][1])})</div>'
            f'<div class="chips">{"".join(chips)}</div>'
            f'{key_stats(table_row, cols, name, rel) if table_row else ""}</div></div>')
    weapon_card = next((c for c in mine if c.get('slot') == 'Weapon_Primary'), None)
    weapon = weapon_block(weapon_card, table_row, cols, name, rel) if table_row else ''
    # without a stats row there is no weapon block: the gun stays an ordinary card
    abil_cards = [ability_card(c, rel, SLOT_LABEL.get(c.get('slot', ''), c.get('slot', '')))
                  for c in mine if c.get('slot') != 'Weapon_Primary' or not table_row]
    abil = ('<h2>Abilities</h2><div class="ability-grid">' + ''.join(abil_cards) + '</div>') if abil_cards else ''
    stats = ''
    if table_row:
        panels = stat_tables(table_row, cols, name, rel, skip=(WEAPON_GROUP,))
        stats = f'<h2>Stats</h2>{panels}' if panels else ''
    keys = _owned_keys(hid, name, mine, ents_by_id, rel)
    hist = history_table(keys, [name], by_ent, by_subject, rel)
    body = (head + weapon + abil + stats +
            '<h2>History</h2><div class="toolbar"><button class="px-btn" data-toggle-class="only-hidden" '
            'data-target="#history">Only hidden</button></div>'
            f'<div id="history">{hist}</div>')
    return page(name, body, rel, 'heroes', description=f'Deadlock {name}: stats, abilities and every change')
