"""Items index laid out like the game's shop. This module draws the "All Items" tab: one row per tier
with its price tag on the left, three columns Weapon → Spirit → Vitality (the game's order everywhere),
item cards with ACTIVE / IMBUE labels; hovering a card lights up its components and what it upgrades
into, the rest dims (the game does the same). Street Brawl's T5 draft items and removed items follow
below. The tabs and the three category catalogs are builders/game_shop.py."""
from __future__ import annotations

from .common import entity_icon, esc, icon, pretty_id, slug
from .render import pip

# (slot in the data, the shop's name, css key, icon of the category in the game's HUD)
SHOP_COLUMNS = (('WeaponMod', 'Weapon', 'w', 'courage'), ('Tech', 'Spirit', 's', 'spirit'),
                ('Armor', 'Vitality', 'v', 'fortitude'))
SHOP_TIERS = (1, 2, 3, 4)
TALLY = {1: 'I', 2: 'II', 3: 'III', 4: 'IIII', 5: 'V'}


def _name(e: dict) -> str:
    return e['name'] if e.get('name') and e['name'] != e['id'] else pretty_id(e['id'])


def _cat_icon(key: str, rel: str) -> str:
    src = icon(f'prop:{key}', rel)
    return f'<img class="cat-i" src="{esc(src)}" alt="" loading="lazy">' if src else ''


def item_card(e: dict, card: dict | None, rel: str, cat: str, tier: int, used_in: list[str]) -> str:
    from .trail import last_change
    info = (card or {}).get('item') or {}
    name = _name(e)
    href = slug(e['file'], e['id']).split('/', 1)[1]
    active = info.get('activation') == 'Active'
    tags = ''
    if active:
        tags += '<span class="it-act">Active</span>'
    if info.get('imbue'):
        tags += '<span class="it-imb">Imbue</span>'
    last = last_change(f"{e['file']}:{e['id']}")
    foot = f'<span class="it-last">{pip(last[1])}<span class="d">{esc(last[0]["date"][5:])}</span></span>' if last else ''
    ic = entity_icon(e['file'], e['id'], 'item', rel)
    img = f'<img src="{esc(ic)}" alt="" loading="lazy">' if ic else '<span class="noimg"></span>'
    comp = ' '.join(info.get('components') or [])
    cls = f'icard {cat} t{tier}' + (' act' if active else '')
    return (f'<a class="{cls}" href="{esc(href)}" data-id="{esc(e["id"])}" data-comp="{esc(comp)}" '
            f'data-up="{esc(" ".join(used_in))}" data-search="{esc(name.lower())}">'
            f'<span class="it-ic">{img}</span>{tags}<span class="it-nm">{esc(name)}</span>{foot}</a>')


def _used_in(items: list[dict], cards: dict) -> dict[str, list[str]]:
    """id -> the items it is a component of (the shop lights those up on hover)."""
    out: dict[str, list[str]] = {}
    for e in items:
        for comp in ((cards.get(e['id']) or {}).get('item') or {}).get('components') or []:
            out.setdefault(comp, []).append(e['id'])
    return out


def shop_html(items: list[dict], cards: dict, rel: str) -> str:
    def info(e: dict) -> dict:
        return (cards.get(e['id']) or {}).get('item') or {}

    def tier(e: dict) -> int:
        t = str(info(e).get('tier') or e.get('tier') or '').replace('EModTier_', '')
        return int(t) if t.isdigit() else 0

    def slot(e: dict) -> str:
        return info(e).get('slot') or str(e.get('slot') or '').replace('EItemSlotType_', '')

    live = [e for e in items if e.get('alive') and not e.get('disabled') and not info(e).get('disabled')]
    brawl = [e for e in live if info(e).get('street_brawl') or tier(e) == 5]
    shop = [e for e in live if e not in brawl and tier(e) in SHOP_TIERS]
    gone = [e for e in items if e not in shop and e not in brawl]
    used_in = _used_in(shop + brawl, cards)
    price = {tier(e): info(e).get('cost') for e in shop if info(e).get('cost')}

    def cells(group: list[dict], t: int) -> str:
        out = []
        for slot_key, label, cat, _ in SHOP_COLUMNS:
            sel = sorted((e for e in group if slot(e) == slot_key and (tier(e) == t or t == 0)), key=_name)
            out.append(f'<div class="cell {cat}" data-label="{label}">' + ''.join(
                item_card(e, cards.get(e['id']), rel, cat, tier(e) or 5, used_in.get(e['id'], [])) for e in sel)
                + '</div>')
        return ''.join(out)

    head = '<div class="shop-head"><span></span>' + ''.join(
        f'<div class="cat-h {cat}">{_cat_icon(ik, rel)}<span>{name}</span>'
        f'<small>{sum(1 for e in shop if slot(e) == sk)}</small></div>'
        for sk, name, cat, ik in SHOP_COLUMNS) + '</div>'
    souls = _cat_icon('souls', rel)
    rows = ''.join(
        f'<div class="shop-row t{t}"><div class="tier-tag"><span class="tally">{TALLY[t]}</span>'
        f'<span class="price">{souls}{price.get(t, "")}</span></div>{cells(shop, t)}</div>'
        for t in SHOP_TIERS)
    # one category alone is its own tab now (builders/game_shop.py): no filter buttons here
    out = [f'<section class="shop px-frame">{head}{rows}</section>']
    if brawl:
        out.append('<div class="grid-group-title">Street Brawl legendaries <small>T5 · draft only</small></div>'
                   f'<section class="shop brawl px-frame">{head}<div class="shop-row t5">'
                   f'<div class="tier-tag"><span class="tally">V</span></div>{cells(brawl, 0)}</div></section>')
    if gone:
        out.append('<div class="grid-group-title">Removed or disabled</div><div class="gone-grid">' + ''.join(
            item_card(e, cards.get(e['id']), rel, next((c for s, _, c, _ in SHOP_COLUMNS if s == slot(e)), 'w'),
                      tier(e) or 1, []) for e in sorted(gone, key=_name)) + '</div>')
    from .game_shop import game_shop_html
    return game_shop_html(shop, cards, rel, used_in, tier, slot, ''.join(out))
