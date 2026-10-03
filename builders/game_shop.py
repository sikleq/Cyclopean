"""The Items page as the game's shop: tabs on the left (All Items, Weapon, Spirit, Vitality), and each
category a catalog page drawn like the game's — Fairfax / MPS / Curiosity Catalog art from the VPK
(tools/extract_shop_assets.py), four tier boxes where the game puts them, paper cards per category and
tier, round cards for active items, the price on the tape. Hovering a card dims the others, lights up
what it builds from and into, shows the item's tooltip and plays the category's hover sound.

Geometry is the game's own, in its design pixels (the catalog is 1120 x 960):
panorama/styles/citadel_shop_mods_filtered.css (tier rows) and citadel_shop_mod_view.css (cards);
see docs/shop.md. The page scales it with the width; narrow screens stack the tiers."""
from __future__ import annotations

from .common import entity_icon, esc, icon, pretty_id, slug
from .hero_page import prop_rows

BOARD = (1120, 960)
CARD_W, CARD_H, CARD_GAP = 76, 114, 3          # CitadelShopMod: 76 x 114, margin 3 -> pitch 82 x 120
PITCH_X, PITCH_Y = CARD_W + 2 * CARD_GAP, CARD_H + 2 * CARD_GAP
# (css key, slot in the data, tab name, tab icon art, tab click sound ui_shop_panel_<x>), game order
CATEGORIES = (('w', 'WeaponMod', 'Weapon', 'weapon', 'weapon'), ('s', 'Tech', 'Spirit', 'spirit', 'magic'),
              ('v', 'Armor', 'Vitality', 'vitality', 'vitality'))
HOVER_SOUNDS = {'w': 11, 's': 11, 'v': 10}      # ui_shop_mod_hover_<cat>_01..NN
# tier row (x, y, width) per category: .ShowingXOnly .tierRow.EModTier_N
ROWS = {
    'w': {1: (44, 120, 500), 2: (510, 10, 540), 3: (44, 480, 600), 4: (674, 480, 400)},
    's': {1: (44, 120, 500), 2: (510, 10, 540), 3: (44, 480, 500), 4: (510, 480, 560)},
    'v': {1: (44, 120, 500), 2: (510, 10, 540), 3: (44, 480, 500), 4: (510, 480, 550)},
}
SHIFTED = (2, 4)            # .ShowingXOnly .tierRow.EModTier_2, .EModTier_4 { margin-left: 20px }
ROW_PAD_X, ROW_PAD_Y = 22, 65    # row origin -> first card's margin box (padding, cost label above)
# the price sits on the black tape painted into each page's art (centre, design px)
PRICE_AT = {1: (75, 166), 2: (576, 38), 3: (94, 508), 4: (595, 502)}
PRICE_AT_WEAPON_T4 = (776, 503)
PRICE_SIZE = {1: 24, 2: 26, 3: 28, 4: 28}       # CostLabel font-size per tier
PRICES = {1: 800, 2: 1600, 3: 3200, 4: 6400}    # generic_data m_nItemPricePerTier
# the game's fonts (VALVEOracle for names, VALVEPulp for prices) are not in the VPK: close free ones
FONTS = 'https://fonts.googleapis.com/css2?family=Archivo+Narrow:wght@600;700&family=Fredoka:wght@600&display=swap'


def tier_box(cat: str, tier: int) -> tuple[int, int, int]:
    """Where a tier's cards go on its page: (left, top, cards per row), design px of the margin box."""
    x, y, w = ROWS[cat][tier]
    left = x + (20 if tier in SHIFTED else 0) + ROW_PAD_X
    return left, y + ROW_PAD_Y, (w - 22) // PITCH_X


def price_at(cat: str, tier: int) -> tuple[int, int]:
    return PRICE_AT_WEAPON_T4 if (cat, tier) == ('w', 4) else PRICE_AT[tier]


def _name(e: dict) -> str:
    return e['name'] if e.get('name') and e['name'] != e['id'] else pretty_id(e['id'])


def card_html(e: dict, card: dict | None, rel: str, used_in: list[str], n: int) -> str:
    """One card. `n`: its place in the tier (the game picks the torn-edge icon mask by it)."""
    info = (card or {}).get('item') or {}
    name = _name(e)
    href = slug(e['file'], e['id']).split('/', 1)[1]
    active = info.get('activation') == 'Active'
    src = entity_icon(e['file'], e['id'], 'item', rel)
    img = f'<img src="{esc(src)}" alt="" loading="lazy">' if src else ''
    cls = 'gcard' + (' act' if active else f' m{n % 3 + 1}') + (' imb' if info.get('imbue') else '')
    imbue = '<span class="gc-imb">Imbue</span>' if info.get('imbue') else ''
    return (f'<a class="{cls}" href="{esc(href)}" data-id="{esc(e["id"])}" '
            f'data-comp="{esc(" ".join(info.get("components") or []))}" data-up="{esc(" ".join(used_in))}" '
            f'data-search="{esc(name.lower())}"><span class="gc-ic">{img}</span>{imbue}'
            f'<span class="gc-nm">{esc(name)}</span></a>')


def _section_rows(card: dict, rel: str) -> str:
    out = []
    stats = (card.get('important') or []) + (card.get('basic') or [])
    if stats:
        out.append(f'<table class="kvt gt-stats">{prop_rows(stats, rel)}</table>')
    for s in card.get('sections') or []:
        kind = s.get('type') or 'Passive'
        cd = next((p['value'] for p in s.get('props', []) if p.get('prop') == 'AbilityCooldown'), '')
        props = [p for p in s.get('props', []) if p.get('prop') != 'AbilityCooldown']
        head = (f'<div class="gt-bar {esc(kind.lower())}"><span>{esc(kind)}</span>'
                + (f'<span class="gt-cd">{esc(cd)}</span>' if cd else '') + '</div>')
        desc = f'<p class="gt-desc">{esc(s["desc"])}</p>' if s.get('desc') else ''
        rows = f'<table class="kvt">{prop_rows(props, rel)}</table>' if props else ''
        out.append(f'<div class="gt-sec">{head}{desc}{rows}</div>')
    return ''.join(out)


def tooltip_html(e: dict, card: dict | None, cat: str, rel: str, names: dict[str, str]) -> str:
    """The item tooltip (citadel_tooltip_mod_details): header strip of the category with the name and
    the price, innate stats, the Active / Passive sections, what it builds from and into."""
    card = card or {}
    info = card.get('item') or {}
    cost = info.get('cost')
    souls = icon('prop:souls', rel)
    price = (f'<span class="gt-cost"><img src="{esc(souls)}" alt="">{esc(cost)}</span>' if cost and souls
             else f'<span class="gt-cost">{esc(cost)}</span>' if cost else '')
    body = _section_rows(card, rel)
    links = []
    for label, ids in (('Upgrades from', info.get('components') or []), ('Upgrades to', e.get('_up') or [])):
        named = [names[i] for i in ids if i in names]
        if named:
            links.append(f'<div class="gt-comp"><b>{label}</b> {esc(", ".join(named))}</div>')
    return (f'<template id="gt-{esc(e["id"])}"><div class="gtip {cat}"><div class="gt-head">'
            f'<span class="gt-name">{esc(_name(e))}</span>{price}</div>'
            f'<div class="gt-body">{body}{"".join(links)}</div></div></template>')


def tabs_html(rel: str) -> str:
    def tab(key: str, img: str, label: str, panel: str) -> str:
        return (f'<button class="gs-tab {key}" data-gs="{key}" data-panel="{panel}" data-tooltip="{label}" '
                f'aria-label="{label}"><img src="{rel}icons/shop/tab_{img}.webp" alt=""></button>')
    # All Items plays the starred click, like the game's Builds / Popular / All Items tabs
    tabs = [tab('all', 'all', 'All Items', 'starred')] + [tab(k, art, f'{nm} Items', panel)
                                                         for k, _, nm, art, panel in CATEGORIES]
    sound = ('<button class="gs-sound on" data-tooltip="Shop sounds" aria-label="Shop sounds" aria-pressed="true">'
             '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2 6h3l4-3v10l-4-3H2z"/>'
             '<path class="w" d="M11 5.5c1 .8 1 4.2 0 5M12.8 4c1.9 1.6 1.9 6.4 0 8"/></svg></button>')
    return f'<nav class="gs-tabs">{"".join(tabs)}{sound}</nav>'


def catalog_page(cat: str, shop: list[dict], cards: dict, rel: str, used_in: dict[str, list[str]],
                 tier_of, slot_of) -> str:
    slot = next(c[1] for c in CATEGORIES if c[0] == cat)
    boxes = []
    for t in (1, 2, 3, 4):
        group = sorted((e for e in shop if slot_of(e) == slot and tier_of(e) == t), key=_name)
        left, top, per = tier_box(cat, t)
        px, py = price_at(cat, t)
        boxes.append(
            f'<span class="gs-price t{t}" style="--x:{px};--y:{py};--fs:{PRICE_SIZE[t]}">{PRICES[t]}</span>'
            f'<div class="gs-tier t{t}" data-tier="Tier {t}" style="--x:{left};--y:{top};--n:{per}">' + ''.join(
                card_html(e, cards.get(e['id']), rel, used_in.get(e['id'], []), i) for i, e in enumerate(group))
            + '</div>')
    return (f'<section class="gs-page {cat}" data-page="{cat}" hidden>'
            f'<div class="gs-board">{"".join(boxes)}</div></section>')


def game_shop_html(shop: list[dict], cards: dict, rel: str, used_in: dict[str, list[str]], tier_of, slot_of,
                   all_items: str) -> str:
    """The whole shop: tabs + three catalog pages + the All Items page (`all_items`, shop_page.py)."""
    names = {e['id']: _name(e) for e in shop}
    tips = []
    for e in shop:
        cat = next((c[0] for c in CATEGORIES if c[1] == slot_of(e)), 'w')
        tips.append(tooltip_html({**e, '_up': used_in.get(e['id'], [])}, cards.get(e['id']), cat, rel, names))
    pages = ''.join(catalog_page(c[0], shop, cards, rel, used_in, tier_of, slot_of) for c in CATEGORIES)
    sounds = ' '.join(f'{k}:{n}' for k, n in HOVER_SOUNDS.items())
    # pages start hidden and the script opens one; without the script they all show
    noscript = '<noscript><style>.gs-page[hidden] { display: block; }</style></noscript>'
    return (f'{noscript}<div class="gshop" data-sfx="{rel}sounds/shop/" data-hover="{sounds}">{tabs_html(rel)}'
            f'<div class="gs-pages">{pages}<section class="gs-page all" data-page="all" hidden>{all_items}</section>'
            f'</div></div><div class="gs-tips" hidden>{"".join(tips)}</div>')
