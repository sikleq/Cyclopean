"""Items index = the game's shop. This module sorts the items the way the shop does — on sale (tiers 1-4),
Street Brawl's draft-only T5, no longer sold — and hands them to builders/game_shop.py, which draws the
tabs, the three category catalogs and All Items."""
from __future__ import annotations

SHOP_TIERS = (1, 2, 3, 4)


def _used_in(items: list[dict], cards: dict) -> dict[str, list[str]]:
    """id -> the items it is a component of (the shop lights those up on hover)."""
    out: dict[str, list[str]] = {}
    for e in items:
        for comp in ((cards.get(e['id']) or {}).get('item') or {}).get('components') or []:
            out.setdefault(comp, []).append(e['id'])
    return out


def shop_html(items: list[dict], cards: dict, rel: str) -> tuple[str, str]:
    """(page html, tooltips json)."""
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
    from .game_shop import game_shop_html
    return game_shop_html(shop, brawl, gone, cards, rel, _used_in(shop + brawl, cards), tier, slot)
