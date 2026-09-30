"""Hero page: portrait + key stats, stat tables with history, ability cards
(the in-game tooltip rebuilt from data), and the full history as one table."""
from __future__ import annotations

import json

from .common import entity_icon, esc, hero_icon, icon, img, mark, page
from .render import sort_changes, tag_html, vals_html

SLOT_ORDER = ('Weapon_Primary', 'Weapon_Secondary', 'Signature_1', 'Signature_2', 'Signature_3', 'Signature_4')
SLOT_LABEL = {'Weapon_Primary': 'Weapon', 'Weapon_Secondary': 'Alt weapon', 'Signature_1': 'Ability 1',
              'Signature_2': 'Ability 2', 'Signature_3': 'Ability 3', 'Signature_4': 'Ultimate'}
KEY_STATS = ('hp', 'hp_lvl', 'hp_regen', 'dps', 'bullet_dmg', 'clip', 'move', 'sprint', 'stamina', 'spirit_lvl')
LINE_STATUSES = ('documented', 'rounded', 'described', 'mismatch', 'fix')
GAMEPLAY = ('balance', 'mechanic', 'availability')


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


def key_stats(row: dict, cols: list[dict], name: str) -> str:
    by_key = {c['key']: c for c in cols}
    out = []
    for k in KEY_STATS:
        c = by_key.get(k)
        if not c or row['values'].get(k) is None:
            continue
        cls, attrs = _hist_attrs(row, c, name)
        out.append(f'<div class="keystat {cls}"{attrs}><div class="v">{_fmt(row["values"][k], c["digits"])}</div>'
                   f'<div class="l">{esc(c["label"])}</div></div>')
    return '<div class="keystats">' + ''.join(out) + '</div>'


def stat_tables(row: dict, cols: list[dict], name: str) -> str:
    groups: dict[str, list[dict]] = {}
    for c in cols:
        groups.setdefault(c['group'], []).append(c)
    parts = []
    for g, cs in groups.items():
        rows = []
        for c in cs:
            v = row['values'].get(c['key'])
            if v is None:
                continue
            cls, attrs = _hist_attrs(row, c, name)
            rows.append(f'<tr><td>{esc(c["label"])}</td><td class="v {cls}"{attrs}>{_fmt(v, c["digits"])}</td></tr>')
        if rows:
            parts.append(f'<table class="kvt px-frame"><caption>{esc(g)}</caption>{"".join(rows)}</table>')
    return '<div class="stat-tables">' + ''.join(parts) + '</div>'


WEAPON_CARD = ('bullet_dmg', 'pellets', 'bps', 'dps', 'clip', 'reload', 'bullet_speed', 'falloff_start',
               'falloff_end', 'headshot')


def weapon_rows(row: dict, cols: list[dict]) -> list[dict]:
    """The gun has no tooltip block in the data: show its stats from the hero table."""
    by_key = {c['key']: c for c in cols}
    out = []
    for k in WEAPON_CARD:
        v = row['values'].get(k)
        if v is None or k not in by_key:
            continue
        out.append({'label': by_key[k]['label'], 'value': _fmt(v, by_key[k]['digits']), 'scale': None})
    return out


def _prop_rows(rows: list[dict]) -> str:
    out = []
    for r in rows:
        scale = f'<span class="scale">+{r["scale"]:g}×Spirit</span>' if r.get('scale') else ''
        out.append(f'<tr><td>{esc(r["label"])}</td><td class="v">{esc(r["value"])}{scale}</td></tr>')
    return ''.join(out)


def ability_card(c: dict, rel: str, slot_label: str = '') -> str:
    ic = entity_icon('abilities.vdata', c['id'], c['kind'], rel)
    hdr = ''.join(f'<span class="chip">{esc(h["label"])} {esc(h["value"])}</span>' for h in c.get('header', []))
    rows = _prop_rows(c.get('important', []) + c.get('basic', []))
    table = f'<table class="kvt">{rows}</table>' if rows else ''
    desc = f'<div class="ac-desc">{esc(c["desc"])}</div>' if c.get('desc') else ''
    tiers = ''.join(
        f'<div class="tier"><span class="tn">T{t["tier"]}</span><span class="tt">'
        f'{esc(t["text"] or ", ".join(b["label"] + " " + b["value"] for b in t["bonuses"]))}</span></div>'
        for t in c.get('tiers', []))
    return (f'<div class="ability-card px-frame" id="{esc(c["id"])}"><div class="ac-head">{img(ic, "", "px")}'
            f'<div><div class="ac-name">{esc(c["name"])}</div><div class="ac-sub">{esc(slot_label)}</div></div></div>'
            f'{"<div class=ac-hdr>" + hdr + "</div>" if hdr else ""}{desc}{table}'
            f'{"<div class=tiers>" + tiers + "</div>" if tiers else ""}</div>')


def history_table(keys: list[tuple[str, str, str | None]], names: list[str], by_ent, by_subject, rel: str) -> str:
    """keys: [(entity key, display name, icon url)]; one table, grouped by patch, newest first."""
    per_patch: dict[str, dict] = {}
    for key, nm, ic in keys:
        for row, ch in by_ent.get(key, []):
            slot = per_patch.setdefault(row['id'], {'row': row, 'ents': [], 'lines': []})
            slot['ents'].append((nm, ic, ch))
    for n in names:
        for row, ln in by_subject.get(n.lower(), []):
            slot = per_patch.setdefault(row['id'], {'row': row, 'ents': [], 'lines': []})
            if ln not in slot['lines']:
                slot['lines'].append(ln)
    if not per_patch:
        return '<p class="muted">No recorded changes.</p>'
    trs = []
    for pid in sorted(per_patch, key=lambda k: per_patch[k]['row']['date'], reverse=True):
        slot = per_patch[pid]
        row = slot['row']
        n_hidden = sum(1 for _, _, ch in slot['ents'] for c in ch if c.get('status') == 'hidden')
        hid = f'<span class="chip">{mark("hidden")}{n_hidden} hidden</span>' if n_hidden else ''
        trs.append(f'<tr class="ph"><td colspan="5"><a class="t" href="{rel}patches/{esc(pid)}.html">{esc(row["title"])}</a>'
                   f'<span class="d">{esc(row["date"])}</span> {hid}</td></tr>')
        for ln in slot['lines']:
            st = ln['status']
            m = mark(st) if st in LINE_STATUSES else ''
            trs.append(f'<tr class="nl st-{esc(st)}"><td class="st">{m}</td><td colspan="4">{esc(ln["text"])}</td></tr>')
        for nm, ic, ch in slot['ents']:
            for c in sort_changes(ch):
                st = c.get('status', 'hidden')
                icon_html = f'<img class="px" src="{esc(ic)}" alt="">' if ic else ''
                trs.append(f'<tr class="ch st-{esc(st)}"><td class="st">{mark(st)}</td><td class="sc">{icon_html}{esc(nm)}</td>'
                           f'<td class="tg">{tag_html(c)}</td><td>{esc(c.get("label"))}</td><td class="ov">{vals_html(c)}</td></tr>')
    return f'<table class="hist">{"".join(trs)}</table>'


def hero_page(h: dict, cards: dict, table_row: dict | None, cols: list[dict], ents_by_id: dict,
              by_ent, by_subject) -> str:
    rel = '../'
    hid = h['id']
    name = h.get('name') or hid
    portrait = icon(f'heroes/card:{hid}', rel) or icon(f'heroes/vertical:{hid}', rel) or hero_icon(hid, rel)
    mine = [c for c in cards.values() if c.get('owner') == hid]
    mine.sort(key=lambda c: SLOT_ORDER.index(c['slot']) if c.get('slot') in SLOT_ORDER else 99)
    state = '<span class="chip">pre-release</span>' if h.get('state') == 'EHeroDevState_PreRelease' else ''
    gone = '' if h.get('alive') else '<span class="tag del">REMOVED</span>'
    chips = [state, gone]
    if table_row:
        if table_row.get('type'):
            chips.append(f'<span class="chip">{esc(table_row["type"].rsplit("_", 1)[-1])}</span>')
        if table_row.get('weapon_name'):
            chips.append(f'<span class="chip">Weapon: {esc(table_row["weapon_name"])}</span>')
    head = (f'<div class="hero-head"><div><img class="portrait px-frame" src="{esc(portrait or "")}" alt="{esc(name)}"></div><div>'
            f'<div class="crumbs"><a href="index.html">Heroes</a> / {esc(name)}</div><h1>{esc(name)}</h1>'
            f'<div class="meta">First seen: build {h["first"][0]} ({esc(h["first"][1])}) · <code>{esc(hid)}</code></div>'
            f'<div class="chips">{"".join(chips)}</div>'
            f'{key_stats(table_row, cols, name) if table_row else ""}</div></div>')
    stats = (f'<h2>Stats</h2>{stat_tables(table_row, cols, name)}' if table_row else '')
    abil = ''
    if mine:
        cards_html = []
        for c in mine:
            if c.get('kind') == 'weapon' and table_row and c.get('slot') == 'Weapon_Primary' \
                    and not (c.get('important') or c.get('basic')):
                c = {**c, 'important': weapon_rows(table_row, cols)}
            cards_html.append(ability_card(c, rel, SLOT_LABEL.get(c.get('slot', ''), c.get('slot', ''))))
        abil = '<h2>Abilities</h2><div class="ability-grid">' + ''.join(cards_html) + '</div>'
    keys = [(f'heroes.vdata:{hid}', name, hero_icon(hid, rel))]
    for e in sorted((e for e in ents_by_id.values() if e.get('owner') == hid), key=lambda e: e.get('name') or ''):
        keys.append((f'abilities.vdata:{e["id"]}', e.get('name') or e['id'],
                     entity_icon('abilities.vdata', e['id'], e.get('kind', ''), rel)))
    hist = history_table(keys, [name], by_ent, by_subject, rel)
    body = (head + stats + abil +
            '<h2>History</h2><div class="toolbar"><button class="px-btn" data-toggle-class="only-hidden" '
            'data-target="#history">Only hidden</button></div>'
            f'<div id="history">{hist}</div>')
    return page(name, body, rel, 'heroes', description=f'Deadlock {name}: stats, abilities and every change')
