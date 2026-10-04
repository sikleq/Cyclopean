"""Hero page: portrait + key stats, the weapon block, ability cards (the in-game
tooltip rebuilt from data), the remaining stats as compact panels, and the full
history grouped by patch and by ability."""
from __future__ import annotations

from functools import lru_cache
import re

from .common import (cosmetics, display_name, entity_icon, esc, first_seen, glyph_for, hero_icon, icon, img, json_attr,
                     load_json, mark, page, pretty_id)
from .history_view import history_table, now_fold  # noqa: F401  (re-exported for entities_pages)
from .render import tag_badge

SLOT_ORDER = ('Weapon_Primary', 'Weapon_Secondary', 'Signature_1', 'Signature_2', 'Signature_3', 'Signature_4')
SLOT_LABEL = {'Weapon_Primary': 'Weapon', 'Weapon_Secondary': 'Alt weapon', 'Signature_1': 'Ability 1',
              'Signature_2': 'Ability 2', 'Signature_3': 'Ability 3', 'Signature_4': 'Ultimate'}
ULT_SLOT = 'Signature_4'    # its icon carries the ultimate's corner mark (cards.ability_plate)
# the head strip: every main non-gun stat (survival, movement, melee, spirit growth); the rest of
# the stats are open panels under the abilities, the gun's in the weapon block (user, 10-01; open 10-04)
KEY_STATS = ('hp', 'hp_lvl', 'hp_regen', 'bullet_resist', 'spirit_resist', 'move', 'sprint', 'stamina',
             'light_melee', 'heavy_melee', 'spirit_lvl')
WEAPON_GROUP = 'Damage'
# the six numbers a player compares first: one row of equal tiles with one-line labels
WEAPON_TOP = {'dps': 'DPS', 'dps_max': 'Max DPS', 'bullet_dmg': 'Bullet dmg', 'bps': 'Bullets/s',
              'clip': 'Ammo', 'reload': 'Reload s'}
WEAPON_DIGITS = 2
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


@lru_cache(maxsize=1)
def _recent_cutoff() -> str:
    """Values changed after this date get the corner dot (the rest: history on hover only)."""
    from .tables_pages import _recent_cutoff as cutoff
    return cutoff(load_json('tables/heroes.json').get('date'))


def _hist_attrs(row: dict, col: dict, name: str) -> tuple[str, str]:
    hist = row['history'].get(col['key'])
    cls = []
    if col['key'] in row.get('spirit_scaled', []):
        cls.append('spirit')
    attrs = f' data-pol="{col["pol"]}" data-digits="{col["digits"]}"'
    if hist:
        cls.append('has-hist')
        if str(hist[-1][1])[:10] >= _recent_cutoff():
            cls.append('recent')
        attrs += json_attr('data-hist', hist) + f' data-title="{esc(name)} · {esc(col["label"])}"'
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


def more_stats(row: dict, cols: list[dict], name: str, rel: str) -> str:
    """Secondary stats (per-boon growth of resists, dashes, collision…) as open panels below the abilities
    (owner 2026-10-04: nothing folded by default — they sat two clicks deep)."""
    panels = stat_tables(row, cols, name, rel, skip=(WEAPON_GROUP,), skip_keys=KEY_STATS)
    if not panels:
        return ''
    return f'<h2>Stats</h2>{panels}'


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


def stat_tables(row: dict, cols: list[dict], name: str, rel: str = '../', skip: tuple[str, ...] = (),
                skip_keys: tuple[str, ...] = ()) -> str:
    """Stat groups as compact panels that flow in columns (no tall-block gaps); skip_keys are
    already on screen (the head strip) and are not repeated."""
    groups: dict[str, list[dict]] = {}
    for c in cols:
        if c['group'] not in skip and c['key'] not in skip_keys:
            groups.setdefault(c['group'], []).append(c)
    parts = []
    for g, cs in groups.items():
        body = _cells(row, cs, name, rel)
        if body:
            parts.append(f'<section class="stat-panel"><h3>{esc(g)}</h3>{body}</section>')
    return '<div class="stat-flow">' + ''.join(parts) + '</div>' if parts else ''


_UNIT = re.compile(r'^(.*?)\s*\(([^()]+)\)$')


def _split_unit(label: str) -> tuple[str, str]:
    """'Bullet Speed (m/s)' -> ('Bullet Speed', 'm/s'): in a narrow weapon cell the unit rides
    on the number, so the label fits one line."""
    m = _UNIT.match(label)
    return (m.group(1), m.group(2)) if m else (label, '')


def _unit_html(unit: str) -> str:
    return f'<span class="u">{esc(unit)}</span>' if unit else ''


def weapon_block(card: dict | None, row: dict, cols: list[dict], name: str, rel: str) -> str:
    """The gun is not an ability: its own block, first, with every Damage-group number."""
    wcols = [c for c in cols if c['group'] == WEAPON_GROUP]
    top_order = list(WEAPON_TOP)
    top, rest = [], []
    for c in sorted(wcols, key=lambda c: top_order.index(c['key']) if c['key'] in WEAPON_TOP else len(top_order)):
        v = row['values'].get(c['key'])
        if v is None:
            continue
        cls, attrs = _hist_attrs(row, c, name)
        is_top = c['key'] in WEAPON_TOP
        label, unit = (WEAPON_TOP[c['key']], '') if is_top else _split_unit(c['label'])
        # two decimals at most, like the game's panel: "Reload 1.0575" was a sum no screen prints (external
        # audit 2026-10-04); the full value stays in the cell's history
        cell = (f'<div class="wcell{" top" if is_top else ""} {cls}"{attrs}>{_stat_icon(c["key"], rel)}'
                f'<span class="v">{_fmt(v, min(c["digits"], WEAPON_DIGITS))}{_unit_html(unit)}</span>'
                f'<span class="l">{esc(label)}</span></div>')
        (top if is_top else rest).append(cell)
    wname = (card or {}).get('name') or row.get('weapon_name') or ''
    # heroes in development often have no localized gun name yet: never show the internal id
    name_html = (f'<div class="wb-name">{esc(wname)}</div>' if wname and not wname.startswith('citadel_weapon_')
                 else '<div class="wb-name unnamed">No in-game name yet</div>')
    wid = (card or {}).get('id') or row.get('weapon')
    ic = entity_icon('abilities.vdata', wid, 'weapon', rel) if wid else None
    desc = f'<div class="wb-desc">{esc(card["desc"])}</div>' if card and card.get('desc') else ''
    return (f'<section class="weapon-block px-frame" id="weapon"><div class="wb-id">{img(ic, "", "px", "abilities")}'
            f'<div><div class="wb-kicker">Weapon</div>{name_html}{desc}</div></div>'
            f'<div class="wb-nums"><div class="wb-top">{"".join(top)}</div>'
            f'{_more_weapon(rest)}</div></section>')


def _more_weapon(cells: list[str]) -> str:
    """Every other weapon number in an even grid under the six headline tiles — shown, not folded."""
    return f'<div class="wb-cells">{"".join(cells)}</div>' if cells else ''


def prop_icon(css: str | None, rel: str) -> str:
    """The property's icon from the in-game tooltip (m_strCSSClass -> icons/stats/prop)."""
    src = icon(f'prop:{css}', rel) if css else None
    return f'<img class="pi" src="{esc(src)}" alt="" loading="lazy">' if src else '<span class="pi"></span>'


def prop_rows(rows: list[dict], rel: str) -> str:
    out = []
    for r in rows:
        # "+0.5×Spirit", "−0.186×Spirit" (not "+-"), "+4×Boon" for what the coefficient really multiplies
        scale = (f'<span class="scale">{"+" if r["scale"] >= 0 else "−"}{abs(round(r["scale"], 4)):g}'
                 f'×{esc(r.get("scale_by") or "Spirit")}</span>' if r.get('scale') else '')
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
    # what happened to it lately: the last patch that touched it, and its 12-patch strip — both open that
    # patch's band in the history below, not the patch archive (owner 2026-10-04)
    from .cards import ability_plate
    from .render import TAG_ORDER, pip
    from .trail import last_counts, trail_html
    key = f'abilities.vdata:{c["id"]}'
    last = last_counts(key)
    last_html = ''
    if last:
        prow, counts = last
        pips = ''.join(pip(t, n) for t, n in sorted(counts.items(), key=lambda kv: TAG_ORDER.get(kv[0], 9)))
        last_html = (f'<a class="ac-last" href="#p-{esc(prow["id"])}" data-p="{esc(prow["id"])}" '
                     f'data-ab="{esc(c["id"])}"><span class="tsum">{pips}</span> {esc(prow["date"])}</a>')
    plate = ability_plate(ic, 'abilities', c.get('slot') == ULT_SLOT)
    return (f'<div class="ability-card px-frame" id="{esc(c["id"])}"><div class="ac-head">{plate}'
            f'<div class="ac-id"><div class="ac-name">{esc(name)}</div><div class="ac-sub">{esc(slot_label)}{last_html}'
            f'<a class="ac-hist" href="#ab-{esc(c["id"])}">History</a></div>'
            f'{trail_html(key, None, rel, local=True)}</div></div>'
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


def current_cards(cards: dict, hid: str) -> list[dict]:
    """The hero's cards as the game shows them: the guns and the four abilities its build binds now.
    Abilities it no longer binds stay in the files (Calico's Nekomata Ward, Catform pounce) and keep
    their history below, but get no card (user, 2026-10-03); so do the shared movement abilities."""
    mine = [c for c in cards.values() if c.get('owner') == hid and c.get('slot') in SLOT_ORDER]
    return sorted(mine, key=lambda c: SLOT_ORDER.index(c['slot']))


def hero_page(h: dict, cards: dict, table_row: dict | None, cols: list[dict], ents_by_id: dict,
              by_ent, by_subject) -> str:
    rel = '../'
    hid = h['id']
    name = display_name(h)
    portrait = icon(f'heroes/card:{hid}', rel) or icon(f'heroes/vertical:{hid}', rel) or hero_icon(hid, rel)
    mine = current_cards(cards, hid)
    chips = []
    state = h.get('state')
    if not h.get('alive'):
        chips.append(tag_badge('del', 'REMOVED'))
    elif state == 'EHeroDevState_PreRelease':
        chips.append('<span class="chip">pre-release</span>')
    elif state != 'EHeroDevState_Release':
        chips.append(f'<span class="chip dev">{mark("unreleased")}in development</span>')
    if table_row and table_row.get('type'):
        chips.append(f'<span class="chip">{esc(table_row["type"].rsplit("_", 1)[-1])}</span>')
    if 'base body' in cosmetics()['heroes'].get(hid, ()):
        # the body a skin is put on is in the files (pipeline/cosmetics.py): skins are being made
        chips.append('<span class="chip">skin base in files</span>')
    from .text_rows import former_names
    was = former_names(by_ent, f'heroes.vdata:{hid}', name)
    if was:          # renamed in development (Slork → Fathom): the names its history uses
        chips.append(f'<span class="chip">was {esc(" · ".join(was))}</span>')
    # the same head as an item's or a unit's: crumbs above, then name, chips, "First seen" (advisor 10-03)
    head = (f'<div class="crumbs"><a href="index.html">Heroes</a> / {esc(name)}</div>'
            f'<div class="hero-head"><div><img class="portrait px-frame" src="{esc(portrait or "")}" alt="{esc(name)}"></div><div>'
            f'<h1>{esc(name)}</h1><div class="chips">{"".join(chips)}</div>'
            f'{first_seen(h["first"])}'
            f'{key_stats(table_row, cols, name, rel) if table_row else ""}'
            f'</div></div>')
    weapon_card = next((c for c in mine if c.get('slot') == 'Weapon_Primary'), None)
    weapon = weapon_block(weapon_card, table_row, cols, name, rel) if table_row else ''
    # without a stats row there is no weapon block: the gun stays an ordinary card
    abil_cards = [ability_card(c, rel, SLOT_LABEL.get(c.get('slot', ''), c.get('slot', '')))
                  for c in mine if c.get('slot') != 'Weapon_Primary' or not table_row]
    abil = ('<h2>Abilities</h2><div class="ability-grid">' + ''.join(abil_cards) + '</div>') if abil_cards else ''
    # the page is the history (owner, 2026-10-03), and what the hero is today stands open above it — the gun,
    # the abilities, every stat; nothing folded (owner 2026-10-04: it hid three levels deep)
    now = weapon + abil + (more_stats(table_row, cols, name, rel) if table_row else '')
    keys = _owned_keys(hid, name, mine, ents_by_id, rel)
    ults = frozenset(f'abilities.vdata:{c["id"]}' for c in mine if c.get('slot') == ULT_SLOT)
    from .dynamics_page import part_of
    areas = {f'heroes.vdata:{hid}': 'stats'}
    areas |= {f'abilities.vdata:{e["id"]}': part_of(e) for e in ents_by_id.values() if e.get('owner') == hid}
    gone = {f'abilities.vdata:{e["id"]}' for e in ents_by_id.values() if e.get('owner') == hid
            and e['id'] not in {c['id'] for c in mine}}
    hist = history_table(keys, [name], by_ent, by_subject, rel, areas=areas, gone=gone,
                         in_dev=state not in ('EHeroDevState_Release', 'EHeroDevState_PreRelease'), ults=ults)
    body = head + (f'<section class="now-open">{now}</section>' if now else '') + hist
    return page(name, body, rel, 'heroes', description=f'Deadlock {name}: every change to its stats and abilities',
                cls='entity')
