"""The home page's search (scripts.js `site-search`): every hero, its current abilities, every item and
named unit by its name today — one row [name, page, what it is, icon] in search.json, loaded on the
first keystroke (advisor round 4, 2026-10-03: finding "what changed on X lately" took an index page
first). An ability opens its hero's page filtered to it (#ab-<id>, scripts.js `hist-filter`)."""
from __future__ import annotations

import json

from .common import display_name, entity_icon, hero_icon, slug

INDEX_FILE = 'search.json'


def search_rows(heroes: list[dict], items: list[dict], units: list[tuple[str, dict]], cards: dict,
                current_cards) -> list[list[str]]:
    """`units`: (family name, its main member) of the named families; `current_cards`: hero_page's."""
    rows: list[list[str]] = []
    for h in heroes:
        name, url = display_name(h), slug(h['file'], h['id'])
        rows.append([name, url, 'Hero', hero_icon(h['id'], '') or ''])
        for c in current_cards(cards, h['id']):
            if c.get('slot') != 'Weapon_Primary' and c.get('name'):
                rows.append([c['name'], f'{url}#ab-{c["id"]}', f'{name} · ability',
                             entity_icon('abilities.vdata', c['id'], 'ability', '') or ''])
    for it in items:
        what = 'Item' if it.get('alive') else 'Item · removed'
        rows.append([display_name(it), slug(it['file'], it['id']), what, entity_icon(it['file'], it['id'], 'item', '') or ''])
    for name, u in units:
        what = 'Unit' if u.get('alive') else 'Unit · removed'
        rows.append([name, slug(u['file'], u['id']), what, entity_icon(u['file'], u['id'], u['kind'], '') or ''])
    # a name the game shows twice (an item and an ability) stays twice: they are different pages
    return sorted(rows, key=lambda r: (r[0].lower(), r[2]))


def search_json(rows: list[list[str]]) -> str:
    return json.dumps(rows, ensure_ascii=False, separators=(',', ':'))


def search_box(rel: str = '') -> str:
    return (f'<div class="site-search"><input type="search" placeholder="Hero, ability, item or unit…" '
            f'aria-label="Find a hero, ability, item or unit" autocomplete="off" '
            f'data-site-search="{rel}{INDEX_FILE}" data-rel="{rel}"><div class="ss-list" hidden></div></div>')
