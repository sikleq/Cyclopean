"""The abilities every hero has (jump, dash, slide, mantle, climb rope, zipline, parry): no hero owns them
since the data-quality audit of 2026-10-04 (`classify.shared_abilities`, kind 'shared'), so they left
Infernus' page — and, until this page, every page but the patch archive (review 2026-10-04: 135 rows of
movement changes no menu reached). One history page under Heroes (heroes/shared.html, the same history
view as a hero's), a row "All heroes" in the hero change matrix and their names in the site search."""
from __future__ import annotations

from .common import display_name, entity_icon, esc, page, pretty_id
from .dynamics_page import SHARED_KEY as MATRIX_KEY     # a shared ability's changes count on this row

HREF = 'shared.html'                    # under heroes/
TITLE = 'Movement & shared abilities'
MATRIX_NAME = 'All heroes · movement & shared'
_OWN = 'shared:@all'                    # history_table's "own" entity: none, so every ability gets a chip


def shared_entities(ents: list[dict]) -> list[dict]:
    """The shared abilities that ever existed, by name."""
    sel = [e for e in ents if e['file'] == 'abilities.vdata' and e.get('kind') == 'shared' and not e.get('template')]
    return sorted(sel, key=lambda e: name_of(e).lower())


def name_of(e: dict) -> str:
    nm = display_name(e)
    return nm if nm != e['id'] else pretty_id(e['id'])


def _keys(abils: list[dict], rel: str) -> list[tuple[str, str, str | None]]:
    return [(f'abilities.vdata:{e["id"]}', name_of(e), entity_icon('abilities.vdata', e['id'], 'shared', rel))
            for e in abils]


def has_history(abils: list[dict], by_ent: dict) -> bool:
    return any(by_ent.get(f'abilities.vdata:{e["id"]}') for e in abils)


def shared_page(abils: list[dict], by_ent, by_subject) -> str:
    from .history_view import history_table
    rel = '../'
    keys = _keys(abils, rel)
    head = (f'<div class="crumbs"><a href="index.html">Heroes</a> / {esc(TITLE)}</div>'
            f'<div class="page-head"><div><h1>{esc(TITLE)}</h1></div></div>')
    hist = history_table([(_OWN, 'All heroes', None)] + keys, [], by_ent, by_subject, rel)
    return page(TITLE, head + hist, rel, 'heroes',
                description='Deadlock: every change to the movement and parry every hero has')


def matrix_entry() -> tuple[str, str, str | None, str, str]:
    """The hero matrix's row for them (dynamics_page.matrix_html entries)."""
    return (MATRIX_KEY, MATRIX_NAME, None, HREF, '')


def index_link() -> str:
    """Their way in from the Heroes index (a button in its toolbar)."""
    return f'<span class="sep"></span><a class="px-btn" href="{HREF}">{esc(TITLE)}</a>'


def search_rows(abils: list[dict], by_ent: dict) -> list[list[str]]:
    """site_search rows of the ones with a history: an ability opens the page filtered to it (#ab-<id>)."""
    return [[name_of(e), f'heroes/{HREF}#ab-{e["id"]}', 'All heroes · ability',
             entity_icon('abilities.vdata', e['id'], 'shared', '') or ''] for e in abils
            if by_ent.get(f'abilities.vdata:{e["id"]}')]
