"""The abilities every hero has (jump, dash, slide, mantle, climb rope, zipline, parry): no hero owns them since the
data-quality audit of 2026-10-04 (`classify.shared_abilities`, kind 'shared'). They had a page of their own under
Heroes (heroes/shared.html); since the Game section (coverage audit 2026-10-05) they are its "Movement & combat"
system (builders/game_pages.py), and the old address points there, keeping a #p-<patch> or #ab-<id> anchor."""
from __future__ import annotations

from .common import display_name, esc, pretty_id

HREF = 'shared.html'                    # the old page, under heroes/: now a redirect
GAME_SYSTEM = 'combat'                  # game_systems: "Movement & combat"
TITLE = 'Movement & combat'


def shared_entities(ents: list[dict]) -> list[dict]:
    """The shared abilities that ever existed, by name."""
    sel = [e for e in ents if e['file'] == 'abilities.vdata' and e.get('kind') == 'shared' and not e.get('template')]
    return sorted(sel, key=lambda e: name_of(e).lower())


def name_of(e: dict) -> str:
    nm = display_name(e)
    return nm if nm != e['id'] else pretty_id(e['id'])


def has_history(abils: list[dict], by_ent: dict) -> bool:
    return any(by_ent.get(f'abilities.vdata:{e["id"]}') for e in abils)


def game_href(rel: str = '../') -> str:
    return f'{rel}game/{GAME_SYSTEM}.html'


def redirect() -> str:
    """heroes/shared.html: the Game section's Movement & combat page now (entities_pages.redirect_page)."""
    from .entities_pages import redirect_page
    return redirect_page(game_href(), TITLE)


def index_link() -> str:
    """Their way in from the Heroes index (a button in its toolbar)."""
    return f'<span class="sep"></span><a class="px-btn" href="{esc(game_href())}">{esc(TITLE)}</a>'
