"""Hero page: portrait + key stats, the weapon block, ability cards (the in-game
tooltip rebuilt from data), the remaining stats as compact panels, and the full
history grouped by patch and by ability."""
from __future__ import annotations

from functools import lru_cache
import re

from .common import cosmetics, display_name, entity_icon, esc, first_seen, hero_icon, icon, img, load_json, mark, page
from .history_view import history_table
from .render import tag_badge
from .tables_pages import _fmt, hist_attrs

SLOT_ORDER = ('Weapon_Primary', 'Weapon_Secondary', 'Signature_1', 'Signature_2', 'Signature_3', 'Signature_4')
SLOT_LABEL = {'Weapon_Primary': 'Weapon', 'Weapon_Secondary': 'Alt weapon', 'Signature_1': 'Ability 1',
              'Signature_2': 'Ability 2', 'Signature_3': 'Ability 3', 'Signature_4': 'Ultimate'}
ULT_SLOT = 'Signature_4'    # its icon carries the ultimate's corner mark (cards.ability_plate)
# the head strip: every main non-gun stat (survival, movement, melee, spirit growth); the rest of
# the stats are open panels under the abilities, the gun's in the weapon block (user, 10-01; open 10-04)
KEY_STATS = ('hp', 'hp_lvl', 'hp_regen', 'bullet_resist', 'spirit_resist', 'move', 'sprint', 'stamina',
             'stamina_regen', 'ground_dash', 'air_dash', 'light_melee', 'heavy_melee', 'melee_lvl', 'spirit_lvl')
# the same for every hero (Crouch Speed 4.75 on all 44): no hero's own number; its one step is in the history
NOT_ON_HERO = ('crouch',)
WEAPON_GROUP = 'Damage'
# the six numbers a player compares first: one row of equal tiles with one-line labels
WEAPON_TOP = {'dps': 'DPS', 'dps_max': 'Max DPS', 'bullet_dmg': 'Bullet dmg', 'bps': 'Bullets/s',
              'clip': 'Ammo', 'reload': 'Reload'}
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


@lru_cache(maxsize=1)
def _recent_cutoff() -> str:
    """Values changed after this date get the corner dot (the rest: history on hover only)."""
    from .tables_pages import _recent_cutoff as cutoff
    return cutoff(load_json('tables/heroes.json').get('date'))


def _hist_attrs(row: dict, col: dict, name: str) -> tuple[str, str]:
    """The Hero Stats cell's history on the hero page's own tiles — the same helper as the table
    (tables_pages.hist_attrs), so steps the column's rounding cannot show drop here too (they had drifted:
    8 such steps sat on hero heads, python audit 2026-10-04); directed like the table's (tables_pages.directed)."""
    cls = ['spirit'] if col['key'] in row.get('spirit_scaled', []) else []
    hcls, hattrs = hist_attrs(row['history'].get(col['key']), col['digits'], f'{name} · {col["label"]}',
                              _recent_cutoff(), (row.get('odir') or {}).get(col['key']))
    return ' '.join(cls + hcls), f' data-pol="{col["pol"]}" data-digits="{col["digits"]}"' + hattrs


def _real_steps(row: dict, key: str, digits: int) -> list:
    """The steps of a stat's history a reader sees: a value that changed (not the field's first appearance, null →
    value, and not a step its rounding hides)."""
    out = []
    for h in row.get('history', {}).get(key) or ():
        if h[2] is None:
            continue
        if _fmt(h[2], digits) != _fmt(h[3], digits):
            out.append(h)
    return out


# a stat at its neutral value says nothing (review 2026-10-05: "+Range / boon 0m" on 38 of 39 heroes,
# "+Bullet Resist / boon 0", "Headshot Taken × 1" on 42): hidden unless it ever moved
NEUTRAL = {'range_lvl': 0, 'bullet_resist_lvl': 0, 'spirit_resist_lvl': 0, 'headshot_taken': 1}
# …and a gun's pellet / burst details when it fires one pellet / one bullet a burst
NEEDS = {'pellet_spread': ('pellets', 1), 'pellets': ('pellets', 1), 'burst': ('burst', 1),
         'burst_cycle': ('burst', 1)}


def says_nothing(row: dict, c: dict) -> bool:
    """A stat tile or row that would only print a default (`NEUTRAL`, `NEEDS`) with no real step in its history."""
    k = c['key']
    vals = row.get('values') or {}
    if k in NEUTRAL:
        v = vals.get(k)
        dead = v is not None and float(v) == NEUTRAL[k]
    elif k in NEEDS:
        base, one = NEEDS[k]
        v = vals.get(base)
        dead = v is not None and float(v) == one
    else:
        return False
    return dead and not _real_steps(row, k, c.get('digits', 2))


def _stat_icon(key: str, rel: str) -> str:
    src = icon(f'StatDesc:{STAT_ICON[key]}', rel) if key in STAT_ICON else None
    return f'<img class="si" src="{esc(src)}" alt="" loading="lazy">' if src else '<span class="si"></span>'


def key_stats(row: dict, cols: list[dict], name: str, rel: str = '../') -> str:
    by_key = {c['key']: c for c in cols}
    out = []
    for k in KEY_STATS:
        c = by_key.get(k)
        v = row['values'].get(k)
        if not c or v is None or (v == 0 and k.endswith('_resist')) or says_nothing(row, c):
            continue                                     # base resists are 0 for most heroes
        cls, attrs = _hist_attrs(row, c, name)
        label, unit = _split_unit(c['label'])
        out.append(f'<div class="keystat {cls}"{attrs}>{_stat_icon(k, rel)}<div class="v">{_fmt(row["values"][k], c["digits"])}'
                   f'{_unit_html(unit)}</div><div class="l">{esc(label)}</div></div>')
    return '<div class="keystats">' + ''.join(out) + '</div>'


def more_stats(row: dict, cols: list[dict], name: str, rel: str) -> str:
    """Secondary stats (per-boon growth of resists, dashes, collision…) as open panels below the abilities
    (owner 2026-10-04: nothing folded by default — they sat two clicks deep)."""
    panels = stat_tables(row, cols, name, rel, skip=(WEAPON_GROUP,), skip_keys=KEY_STATS + NOT_ON_HERO)
    if not panels:
        return ''
    return f'<h2>Stats</h2>{panels}'


def _cells(row: dict, cs: list[dict], name: str, rel: str) -> str:
    out = []
    for c in cs:
        v = row['values'].get(c['key'])
        if v is None or says_nothing(row, c):
            continue
        cls, attrs = _hist_attrs(row, c, name)
        label, unit = _split_unit(c['label'])           # "Ground Dash 0.72 s", not "Ground Dash (s) 0.72"
        out.append(f'<div class="sc-row"><span class="k">{_stat_icon(c["key"], rel)}{esc(label)}</span>'
                   f'<span class="v {cls}"{attrs}>{_fmt(v, c["digits"])}{_unit_html(unit)}</span></div>')
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


def weapon_block(card: dict | None, row: dict | None, cols: list[dict], name: str, rel: str,
                 alt: dict | None = None) -> str:
    """The gun is not an ability: its own block, first, with every Damage-group number. `alt`: the gun's alt fire
    (a Weapon_Secondary card: the files give it no text) as a slim line in the block — what changed it lately, its
    trail, its history (its rows are in the gun's group: hero_page.fold_alt). Without a stats row (a hero in
    development) the block is the gun's name and that line, never an empty ability card."""
    wcols = [c for c in cols if c['group'] == WEAPON_GROUP] if row else []
    top_order = list(WEAPON_TOP)
    top, rest = [], []
    for c in sorted(wcols, key=lambda c: top_order.index(c['key']) if c['key'] in WEAPON_TOP else len(top_order)):
        v = row['values'].get(c['key'])
        if v is None or says_nothing(row, c):
            continue
        cls, attrs = _hist_attrs(row, c, name)
        is_top = c['key'] in WEAPON_TOP
        # the unit rides on the number for every tile ("RELOAD S" beside "Full Reload 3.88 s")
        label, unit = (WEAPON_TOP[c['key']], _split_unit(c['label'])[1]) if is_top else _split_unit(c['label'])
        # two decimals at most, like the game's panel: "Reload 1.0575" was a sum no screen prints (external
        # audit 2026-10-04); the full value stays in the cell's history
        cell = (f'<div class="wcell{" top" if is_top else ""} {cls}"{attrs}>{_stat_icon(c["key"], rel)}'
                f'<span class="v">{_fmt(v, min(c["digits"], WEAPON_DIGITS))}{_unit_html(unit)}</span>'
                f'<span class="l">{esc(label)}</span></div>')
        (top if is_top else rest).append(cell)
    wname = (card or {}).get('name') or (row or {}).get('weapon_name') or ''
    # heroes in development often have no localized gun name yet: never show the internal id
    name_html = (f'<div class="wb-name">{esc(wname)}</div>' if wname and not wname.startswith('citadel_weapon_')
                 else '<div class="wb-name unnamed">No in-game name yet</div>')
    wid = (card or {}).get('id') or (row or {}).get('weapon')
    ic = entity_icon('abilities.vdata', wid, 'weapon', rel) if wid else None
    desc = f'<div class="wb-desc">{esc(card["desc"])}</div>' if card and card.get('desc') else ''
    links = _gun_links(wid, wid, rel) if wid else ''
    lines = ''
    if alt:
        lines += (f'<div class="wb-alt"><span class="wb-alt-l">Alt fire</span>'
                  f'{_gun_links(alt["id"], wid or alt["id"], rel)}</div>')
    if top or rest:
        nums = f'<div class="wb-top">{"".join(top)}</div>{_more_weapon(rest)}'
    else:
        # Hero Stats lists playable heroes only (hero_table.PLAYABLE_STATES; a borrowed stand-in gun is no gun)
        nums = '<div class="wb-none">Gun numbers come with Hero Stats once the hero is playable</div>'
    return (f'<section class="weapon-block px-frame" id="weapon"><div class="wb-id">{img(ic, "", "px", "abilities")}'
            f'<div><div class="wb-kicker">Weapon</div>{name_html}{links}{desc}</div></div>'
            f'<div class="wb-nums">{nums}{lines}</div></section>')


def _gun_links(aid: str, group: str, rel: str) -> str:
    """A gun's (or its alt fire's) last change, trail squares and "History" — the ability card's head line.
    `group`: the gun whose history group holds the rows (an alt fire's are in its gun's)."""
    from .trail import trail_html
    return (f'<div class="wb-links">{last_change(aid, group)}<a class="ac-hist" href="#ab-{esc(group)}">History</a>'
            f'{trail_html("abilities.vdata:" + aid, None, rel, local=True)}</div>')


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
    # a tier with neither text nor bonuses is not drawn: 97 bare "T1 / T2 / T3" lines sat on the cards of
    # heroes still in development (python audit 2026-10-04)
    tiers = ''.join(
        f'<div class="tier"><span class="tn">T{t["tier"]}</span><span class="tt">'
        f'{esc(t["text"] or ", ".join(b["label"] + " " + b["value"] for b in t["bonuses"]))}</span></div>'
        for t in c.get('tiers', []) if t.get('text') or t.get('bonuses'))
    name = display_name(c)
    from .cards import ability_plate
    from .trail import trail_html
    last_html = last_change(c['id'])
    plate = ability_plate(ic, 'abilities', c.get('slot') == ULT_SLOT)
    key = 'abilities.vdata:' + c['id']
    return (f'<div class="ability-card px-frame" id="{esc(c["id"])}"><div class="ac-head">{plate}'
            f'<div class="ac-id"><div class="ac-name">{esc(name)}</div><div class="ac-sub">{esc(slot_label)}{last_html}'
            f'<a class="ac-hist" href="#ab-{esc(c["id"])}">History</a></div>'
            f'{trail_html(key, None, rel, local=True)}</div></div>'
            f'{"<div class=ac-hdr>" + hdr + "</div>" if hdr else ""}{desc}{table}'
            f'{"<div class=tiers>" + tiers + "</div>" if tiers else ""}</div>')


def last_change(aid: str, ab: str | None = None) -> str:
    """What happened to an ability or gun lately: the last patch that touched it, its tag counters and date — it
    opens that patch's band in the history below, not the patch archive (owner 2026-10-04). `ab`: the history group
    it lands in (an alt fire's rows are in its gun's group)."""
    from .render import TAG_ORDER, pip
    from .trail import last_counts
    last = last_counts(f'abilities.vdata:{aid}')
    if not last:
        return ''
    prow, counts = last
    pips = ''.join(pip(t, n) for t, n in sorted(counts.items(), key=lambda kv: TAG_ORDER.get(kv[0], 9)))
    return (f'<a class="ac-last" href="#p-{esc(prow["id"])}" data-p="{esc(prow["id"])}" '
            f'data-ab="{esc(ab or aid)}"><span class="tsum">{pips}</span> {esc(prow["date"])}</a>')


def has_content(c: dict) -> bool:
    """A card with something to read: text, header values, property rows or a tier (an alt fire and a gun in
    development are bare: Viscous' "Alt weapon" was a 579 px empty card that pushed Goo Ball to a row of its own)."""
    return bool(c.get('desc') or c.get('header') or c.get('important') or c.get('basic')
                or any(t.get('text') or t.get('bonuses') for t in c.get('tiers', [])))


def _owned_keys(hid: str, mine: list[dict], ents_by_id: dict, rel: str, skip: set[str] = frozenset(),
                parents: dict[str, str] | None = None) -> list[tuple]:
    """History entities in page order: base stats, weapon, abilities by slot, the rest by name. `skip`: ids whose
    rows sit in another group (an alt fire's are its gun's); `parents`: a nameless sub-ability -> the ability it
    belongs to ("Ava · trigger" with Ava's icon, not "Catform trigger")."""
    keys = [(f'heroes.vdata:{hid}', 'Base stats', hero_icon(hid, rel))]
    slot_of = {c['id']: c.get('slot') for c in mine}
    owned = [e for e in ents_by_id.values() if e.get('owner') == hid and e['id'] not in skip]
    parents = parents or {}

    def rank(e: dict) -> tuple:
        s = slot_of.get(e['id'])
        return (SLOT_ORDER.index(s) if s in SLOT_ORDER else len(SLOT_ORDER), e.get('name') or '')
    for e in sorted(owned, key=rank):
        par = ents_by_id.get(parents.get(e['id'], ''))
        if par:
            nm = f'{display_name(par)} · {e["id"][len(par["id"]) + 1:].replace("_", " ")}'
            ic = entity_icon('abilities.vdata', par['id'], par.get('kind', ''), rel, display_name(par), hid)
        else:
            nm = display_name(e)                 # its owner is this hero
            ic = entity_icon('abilities.vdata', e['id'], e.get('kind', ''), rel, nm, hid)
        keys.append((f'abilities.vdata:{e["id"]}', nm, ic))
    return keys


_ALT_GUN = re.compile(r'^citadel_weapon_.+(?:_alt|_set_?2)$')


def alt_guns(hid: str, gun: str | None, ents_by_id: dict) -> list[str]:
    """The hero's alt fire guns (citadel_weapon_viscous_set_2, the removed …_alt): the files give them no name, and
    their history repeated the gun's (Viscous 2024-07-18 "Ammo 20 → 21" twice)."""
    return sorted(e['id'] for e in ents_by_id.values()
                  if e.get('owner') == hid and e['id'] != gun and _ALT_GUN.match(e['id']))


def sub_parents(hid: str, mine: list[dict], ents_by_id: dict) -> dict[str, str]:
    """A nameless sub-ability no slot binds -> the owned ability whose id it extends (ability_nano_pounce_instant ->
    …_pounce, …_catform_trigger -> …_catform): Calico's history showed "Pounce instant", "Catform trigger"."""
    slotted = {c['id'] for c in mine}
    owned = {e['id']: e for e in ents_by_id.values() if e.get('owner') == hid and e.get('kind') != 'weapon'}
    out = {}
    for eid, e in owned.items():
        if eid in slotted or (e.get('name') and e['name'] != eid):
            continue
        cands = [p for p in owned if p != eid and eid.startswith(p + '_') and owned[p].get('name')
                 and owned[p]['name'] != p]
        if cands:
            out[eid] = max(cands, key=len)
    return out


def _sig(c: dict) -> tuple:
    return (str(c.get('label')), str(c.get('old_s')), str(c.get('new_s')))


def fold_alt(by_ent: dict, gun: str, alts: list[str]) -> dict:
    """by_ent with the alt fire's rows in its gun's group, "Alt fire: …" — a row the gun has in the same band with
    the same label and values is said once. Returns a new mapping; `by_ent` is shared and stays as it is."""
    gk = f'abilities.vdata:{gun}'
    bands = {row['id']: (row, list(ch)) for row, ch in by_ent.get(gk, [])}
    for a in alts:
        for row, ch in by_ent.get(f'abilities.vdata:{a}', []):
            row_, have = bands.setdefault(row['id'], (row, []))
            seen = {_sig(c) for c in have}
            have += [{**c, 'label': f'Alt fire: {c.get("label")}'} for c in ch if _sig(c) not in seen]
    out = {**by_ent, gk: sorted(bands.values(), key=lambda rc: rc[0]['date'])}
    for a in alts:
        out.pop(f'abilities.vdata:{a}', None)
    return out


def drop_parent_rows(by_ent: dict, parents: dict[str, str]) -> dict:
    """A sub-ability's row its parent shows in the same band with the same label and values goes (Calico's "Pounce"
    and "Pounce · instant" both read "Movement Slow 30% → 24%" on 2026-09-16)."""
    out = dict(by_ent)
    for child, par in parents.items():
        ck, pk = f'abilities.vdata:{child}', f'abilities.vdata:{par}'
        mine = {row['id']: {_sig(c) for c in ch} for row, ch in by_ent.get(pk, [])}
        rows = [(row, kept) for row, ch in by_ent.get(ck, [])
                for kept in [[c for c in ch if _sig(c) not in mine.get(row['id'], ())]] if kept]
        out[ck] = rows
    return out


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
    weapon_card = next((c for c in mine if c.get('slot') == 'Weapon_Primary'), None)
    alt_card = next((c for c in mine if c.get('slot') == 'Weapon_Secondary'), None)
    gun = (weapon_card or {}).get('id') or (table_row or {}).get('weapon')
    alts = alt_guns(hid, gun, ents_by_id) if gun else []
    # the guns are the weapon block (with a stats row its numbers, else its name): the ability grid holds the four
    # ability slots only, so the ultimate never sits alone on a second row (Viscous' empty "Alt weapon" card)
    weapon = (weapon_block(weapon_card, table_row, cols, name, rel, alt_card if alt_card and alt_card['id'] in alts
                           else None) if weapon_card or table_row else '')
    abil_cards = [ability_card(c, rel, SLOT_LABEL.get(c.get('slot', ''), c.get('slot', '')))
                  for c in mine if str(c.get('slot', '')).startswith('Signature_') and has_content(c)]
    abil = ('<h2>Abilities</h2><div class="ability-grid">' + ''.join(abil_cards) + '</div>') if abil_cards else ''
    # the page is the history (owner, 2026-10-03), and what the hero is today stands open above it — the gun,
    # the abilities, every stat; nothing folded (owner 2026-10-04: it hid three levels deep)
    now = weapon + abil + (more_stats(table_row, cols, name, rel) if table_row else '')
    parents = sub_parents(hid, mine, ents_by_id)
    keys = _owned_keys(hid, mine, ents_by_id, rel, skip=set(alts) if gun else set(), parents=parents)
    hist_ents = drop_parent_rows(fold_alt(by_ent, gun, alts) if gun and alts else by_ent, parents)
    ults = frozenset(f'abilities.vdata:{c["id"]}' for c in mine if c.get('slot') == ULT_SLOT)
    from .dynamics_page import part_of
    areas = {f'heroes.vdata:{hid}': 'stats'}
    areas |= {f'abilities.vdata:{e["id"]}': part_of(e) for e in ents_by_id.values() if e.get('owner') == hid}
    gone = {f'abilities.vdata:{e["id"]}' for e in ents_by_id.values() if e.get('owner') == hid
            and e['id'] not in {c['id'] for c in mine}}
    chip_of = {f'abilities.vdata:{c}': f'abilities.vdata:{p}' for c, p in parents.items()}
    told: dict = {}
    hist = history_table(keys, [name], hist_ents, by_subject, rel, areas=areas, gone=gone,
                         in_dev=state not in ('EHeroDevState_Release', 'EHeroDevState_PreRelease'), ults=ults,
                         every_label='For all heroes', chip_of=chip_of, facts_out=told)
    from .history_view import head_strip, hidden_link
    chips.append(hidden_link(told.get('hidden', 0)))
    head = (f'<div class="crumbs"><a href="index.html">Heroes</a> / {esc(name)}</div>'
            f'<div class="hero-head"><div><img class="portrait px-frame" src="{esc(portrait or "")}" alt="{esc(name)}"></div><div>'
            f'<h1>{esc(name)}</h1><div class="chips">{"".join(chips)}</div>'
            f'{first_seen(h["first"])}'
            f'{key_stats(table_row, cols, name, rel) if table_row else ""}'
            f'</div></div>')
    # the patch strip right under the head: the first screen shows what changed (History sat at y=1365-2096)
    body = head + head_strip(told) + (f'<section class="now-open">{now}</section>' if now else '') + hist
    return page(name, body, rel, 'heroes', description=f'Deadlock {name}: every change to its stats and abilities',
                cls='entity')
