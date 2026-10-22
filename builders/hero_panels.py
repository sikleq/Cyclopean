"""The hero page's stats as the game's own panels (owner 2026-10-22: "like the game's", in place of the stat tiles):
Weapon / Vitality / Spirit Stats — the hero card of the shop (panorama citadel_hero_stats_{weapon,armor,tech}_panel)
— and the Boon Rewards card. What each panel lists, in what order and under which name is the game's
(pipeline/hero_panels.py); a value a Hero Stats column holds keeps that column's history on hover, like the tiles did.

The look follows the game's stylesheets (citadel_hero_stats_panels_shared.css): the category paper behind each panel,
a two-column grid of dark tiles, a stat at its neutral value at half opacity (.isZeroValue), a stat that grows with
Spirit Power in a spirit frame with its "× scale" badge (citadel_stat_scaling_label.css), the gun's picture,
tags, DPS and falloff range in the weapon panel's head."""
from __future__ import annotations

from functools import lru_cache

from .common import esc, icon, load_json

# the game prints these to a set precision (Warden: "17.3 Bullet Damage" for 17.34, "290m/s", "66 DPS"); the rest
# with two decimals at most, trailing zeros dropped ("3.81", "4.5s", "2")
DIGITS = {'EBulletDamage': 1, 'EBulletSpeed': 0, 'EMaxHealth': 0, 'EWeaponDPS': 0, 'EClipSize': 0, 'EStamina': 0}
PANEL_CLASS = {'weapon': 'w', 'vitality': 'v', 'spirit': 's'}
BOONS_COL = {'key': 'boons', 'label': 'Boons', 'digits': 0, 'pol': 1}


@lru_cache(maxsize=1)
def _labels() -> dict:
    return load_json('tables/heroes.json').get('panel_labels') or {}


def text(key: str) -> str:
    return (_labels().get('text') or {}).get(key) or ''


def stat_label(stat: str) -> str:
    from pipeline.hero_panels import loc_key
    return (_labels().get('stats') or {}).get(stat) or loc_key(stat).removeprefix('StatDesc_')


def _num(v: float, stat: str) -> str:
    from pipeline.hero_panels import PERCENT
    from .tables_pages import _fmt
    digits = 0 if stat in PERCENT else DIGITS.get(stat, 2)
    return _fmt(round(v, 6), digits)


def _unit(stat: str) -> str:
    from pipeline.hero_panels import PERCENT, UNIT
    u = '%' if stat in PERCENT else UNIT.get(stat, '')
    return f'<span class="u">{esc(u)}</span>' if u else ''


def _scale_badge(row: dict, stat: str, rel: str) -> str:
    """The game's "× 0.008" under a spirit arrow: what one Spirit Power adds to the stat (m_mapScalingStats)."""
    s = (row.get('scaling') or {}).get(stat)
    if not s:
        return ''
    return (f'<span class="gp-sc"><img src="{rel}icons/shop/scale_spirit.webp" alt="" loading="lazy">'
            f'<span>× {esc(f"{s:g}")}</span></span>')


def value_of(row: dict, stat: str) -> float | None:
    from pipeline.hero_panels import COLUMN
    if stat in COLUMN:
        v = (row.get('values') or {}).get(COLUMN[stat])
        return 0.0 if v is None and stat.endswith('DamageReduction') else v   # no base resist: the game's 0%
    return (row.get('panel_values') or {}).get(stat)


def tile(row: dict, stat: str, cols: dict[str, dict], name: str, rel: str) -> str:
    """One stat: "17.3 Bullet Damage", at half opacity at its neutral value, framed when it grows with Spirit Power;
    a stat a Hero Stats column holds carries that column's history (the tile it replaces did)."""
    from pipeline.hero_panels import COLUMN
    from .hero_page import _hist_attrs
    v = value_of(row, stat)
    if v is None:
        return ''
    cls, attrs = ['gp-tile'], ''
    if v == 0:
        cls.append('zero')
    col = cols.get(COLUMN.get(stat, ''))
    if col:
        hcls, attrs = _hist_attrs(row, col, name)
        cls += [c for c in hcls.split() if c != 'spirit']
    if (row.get('scaling') or {}).get(stat):
        cls.append('spirit')
    return (f'<div class="{" ".join(cls)}"{attrs}><span class="v">{_num(v, stat)}{_unit(stat)}</span>'
            f'<span class="l">{esc(stat_label(stat))}</span>{_scale_badge(row, stat, rel)}</div>')


def _grid(row: dict, stats: list[str], cols: dict, name: str, rel: str, extra: str = '') -> str:
    tiles = ''.join(tile(row, s, cols, name, rel) for s in stats)
    return f'<div class="gp-grid{extra}">{tiles}</div>' if tiles else ''


def _attrs(row: dict) -> str:
    names = _labels().get('attrs') or {}
    chips = [f'<span class="gp-attr">{esc(names.get(a) or a.rsplit("_", 1)[-1])}</span>'
             for a in (row.get('gun') or {}).get('attrs') or []]
    return f'<div class="gp-attrs">{"".join(chips)}</div>' if chips else ''


def _falloff(row: dict, cols: dict, name: str) -> str:
    from .hero_page import _hist_attrs
    vals = row.get('values') or {}
    parts = []
    for k in ('falloff_start', 'falloff_end'):
        v, c = vals.get(k), cols.get(k)
        if v is None or not c:
            return ''
        hcls, attrs = _hist_attrs(row, c, name)
        # whole metres, like the game's "18m → 47m" (Viscous' 19.99 is its "20m")
        parts.append(f'<b class="{hcls}"{attrs}>{_num(v, "EWeaponDPS")}<span class="u">m</span></b>')
    return (f'<div class="gp-fall"><span class="gp-fall-l">{esc(text("CitadelHeroStats_Weapon_Falloff"))}</span>'
            f'<span class="gp-fall-v">{parts[0]}<span class="gp-arrow">→</span>{parts[1]}</span></div>')


def _dps(row: dict, cols: dict, name: str) -> str:
    from .hero_page import _hist_attrs
    v, c = (row.get('values') or {}).get('dps'), cols.get('dps')
    if v is None or not c:
        return ''
    hcls, attrs = _hist_attrs(row, c, name)
    return (f'<div class="gp-dps {hcls}"{attrs}><b>{_num(v, "EWeaponDPS")}</b>'
            f'<span>{esc(stat_label("EWeaponDPS"))}</span></div>')


def weapon_panel(row: dict, cols: dict, name: str, rel: str, gun_name: str, links: str, alt: str) -> str:
    p = (row.get('panels') or {}).get('weapon') or {}
    image = (row.get('gun') or {}).get('image')
    pic = (f'<img class="gp-gun" src="{rel}icons/guns/{esc(image)}.webp" alt="" loading="lazy">' if image else '')
    head = (f'<div class="gp-head">{pic}<div class="gp-id"><div class="gp-t">{esc(text("CitadelHeroStats_Weapon"))}</div>'
            f'{gun_name}{links}{_attrs(row)}</div>{_dps(row, cols, name)}{_falloff(row, cols, name)}</div>')
    return (f'<section class="gpanel w" id="weapon">{head}'
            f'<div class="gp-body">{_grid(row, p.get("stats") or [], cols, name, rel)}{alt}</div>'
            f'{_grid(row, p.get("other") or [], cols, name, rel, " other")}</section>')


def vitality_panel(row: dict, cols: dict, name: str, rel: str) -> str:
    p = (row.get('panels') or {}).get('vitality') or {}
    return (f'<section class="gpanel v"><div class="gp-body"><div class="gp-t">{esc(text("CitadelHeroStats_Vitality"))}'
            f'</div>{_grid(row, p.get("stats") or [], cols, name, rel)}</div>'
            f'{_grid(row, p.get("other") or [], cols, name, rel, " other")}</section>')


def impact_rows(row: dict, cards: list[dict], rel: str) -> list[str]:
    """Spirit Power Impact (CitadelModifiedAbilities): what Spirit Power raises — the gun's stats that scale with it,
    then every ability property that does (Warden: Bullets per sec, Fire Rate, Damage 60, Barrier 125, Damage 110,
    DPS 70), with its icon and today's value."""
    from pipeline.hero_panels import LOC
    from .hero_page import prop_src
    out = []
    for stat in row.get('scaling') or {}:
        v = value_of(row, stat)
        if v is None:
            continue
        src = icon(f'StatDesc:{LOC.get(stat, stat[1:])}', rel)
        out.append((src, stat_label(stat), f'{_num(v, stat)}{_unit(stat)}'))
    for c in sorted(cards, key=lambda c: c.get('slot') or ''):
        if not str(c.get('slot') or '').startswith('Signature_'):
            continue
        for p in (c.get('header') or []) + (c.get('important') or []) + (c.get('basic') or []):
            if p.get('scale') and not p.get('scale_by'):
                out.append((prop_src(p.get('css'), rel), p['label'], esc(p['value'])))
    rows = []
    for src, label, val in out:
        pic = f'<img src="{esc(src)}" alt="" loading="lazy">' if src else '<span></span>'
        rows.append(f'<div class="gp-imp">{pic}<span class="l">{esc(label)}</span><span class="v">{val}</span></div>')
    return rows


def spirit_panel(row: dict, cols: dict, name: str, rel: str, cards: list[dict]) -> str:
    p = (row.get('panels') or {}).get('spirit') or {}
    imp = impact_rows(row, cards, rel)
    sp = (f'<div class="gp-spirit"><div class="gp-sp-l"><div class="gp-t">{esc(text("CitadelHeroStats_SpiritPower_Impact"))}'
          f'</div><div class="gp-sp-n"><b>0</b> {esc(text("StatDesc_TechPower"))}</div>'
          f'<p>{esc(text("CitadelHeroStats_SpiritPower_Desc"))}</p></div>'
          f'<div class="gp-imps">{"".join(imp)}</div></div>') if imp else ''
    return (f'<section class="gpanel s"><div class="gp-body"><div class="gp-t">{esc(text("CitadelHeroStats_Spirit"))}'
            f'</div>{_grid(row, p.get("stats") or [], cols, name, rel)}</div>{sp}</section>')


def boon_card(row: dict, cols: dict, name: str, rel: str) -> str:
    """Boon Rewards: what one boon adds to this hero (m_mapStandardLevelUpUpgrades, the gains that are not 0) and
    the boon its stat rewards stop at — that build's boon count, with its history (Haze 11 in 2024-08, 35 today)."""
    from pipeline.hero_panels import BOON_ROWS
    from .hero_page import _hist_attrs, _stat_icon
    from .tables_pages import _fmt
    vals = row.get('values') or {}
    gains = []
    for _, label_key, key in BOON_ROWS:
        v, c = vals.get(key), cols.get(key)
        if not v or not c:
            continue
        hcls, attrs = _hist_attrs(row, c, name)
        unit = 'm' if key == 'range_lvl' else '%' if key.endswith('resist_lvl') else ''
        gains.append(f'<div class="gb-gain {hcls}"{attrs}>{_stat_icon(key, rel)}'
                     f'<b>+{_fmt(v, 2)}{esc(unit)}</b><span>{esc(text(label_key))}</span></div>')
    n = vals.get('boons')
    hcls, attrs = _hist_attrs(row, BOONS_COL, name)
    most = text('Citadel_Player_Level_Stat_RewardsMax').replace('{#}', f'<b class="{hcls}"{attrs}>{n}</b>') if n else ''
    sub = text('Citadel_Player_Level_RewardsSubhead').replace('{s:hero_name}', esc(name))
    return (f'<section class="gboons"><div class="gb-top"><div class="gb-t">{esc(text("Citadel_Player_Level_RewardsTitle"))}'
            f'</div><div class="gb-sub">{sub}</div><div class="gb-ap">{esc(text("Citadel_Player_Level_AP_Rewards"))}'
            f'</div><div class="gb-note">{esc(text("Citadel_Player_Level_AP_Rewards_UnlockNote"))}</div></div>'
            f'<div class="gb-stats"><div class="gb-t2">{esc(text("Citadel_Player_Level_Stat_Rewards"))}</div>'
            f'<div class="gb-sub">{most}</div><div class="gb-gains">{"".join(gains)}</div></div></section>')


def panels(row: dict, cols: list[dict], name: str, rel: str, cards: list[dict], gun_name: str, links: str,
           alt: str) -> str:
    by_key = {c['key']: c for c in cols}
    return (f'<div class="gpanels">{weapon_panel(row, by_key, name, rel, gun_name, links, alt)}'
            f'{vitality_panel(row, by_key, name, rel)}{spirit_panel(row, by_key, name, rel, cards)}</div>'
            f'{boon_card(row, by_key, name, rel)}')
