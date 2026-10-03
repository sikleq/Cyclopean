"""Heroes index laid out like the game's hero grid: one grid of tall portrait cards in the order of
the game's sort names (The Doorman under D). A card is the portrait and the name on a plate in the
hero's own colour from the game (m_colorUI); pre-release heroes carry a ribbon. Nothing else: role,
complexity and last-patch counters were dropped on the owner's call (2026-10-01) — the hero page
and Hero changes hold that."""
from __future__ import annotations

from .common import display_name, esc, hero_icon, icon, slug


def hero_color(c) -> str | None:
    """[r, g, b] or [r, g, b, a] from heroes.vdata m_colorUI -> 'rgb(r g b)'; anything else -> None."""
    if isinstance(c, (list, tuple)) and len(c) >= 3 and all(isinstance(x, (int, float)) for x in c[:3]):
        r, g, b = (max(0, min(255, int(x))) for x in c[:3])
        return f'rgb({r} {g} {b})'
    return None


def _portrait(hid: str, rel: str) -> str | None:
    return icon(f'heroes/card:{hid}', rel) or icon(f'heroes/vertical:{hid}', rel) or hero_icon(hid, rel)


def hero_card(h: dict, row: dict | None, rel: str) -> str:
    row = row or {}
    name = display_name(h)
    href = slug(h['file'], h['id']).split('/', 1)[1]
    src = _portrait(h['id'], rel)
    img = f'<img src="{esc(src)}" alt="" loading="lazy">' if src else '<span class="noimg"></span>'
    pre = h.get('state') == 'EHeroDevState_PreRelease'
    ribbon = '<span class="hg-rib">Pre-release</span>' if pre else ''
    # the hero's colour comes from the game data, so it rides as a custom property, not a :root token
    # (an exception the owner approved on 2026-10-01)
    color = hero_color(row.get('color'))
    style = f' style="--hero: {color}"' if color else ''
    return (f'<a class="hgcard{" pre" if pre else ""}" href="{esc(href)}"{style} data-search="{esc(name.lower())}">'
            f'<span class="hg-pic">{img}</span>{ribbon}<span class="hg-nm">{esc(name)}</span></a>')


def heroes_grid_html(live: list[dict], other: list[dict], rows: dict, rel: str) -> str:
    def key(h: dict) -> str:
        return ((rows.get(h['id']) or {}).get('sort_name') or display_name(h)).lower()
    live = sorted(live, key=key)
    # pre-release heroes (vote candidates) hide behind a switch; unreleased ones fold away
    out = ['<div class="hgrid-cards" id="heroes-grid">'
           + ''.join(hero_card(h, rows.get(h['id']), rel) for h in live) + '</div>']
    if other:
        out.append(f'<details class="fold-group"><summary class="grid-group-title">Unreleased & hero labs '
                   f'<span class="n">{len(other)}</span></summary><div class="hgrid-cards lab">'
                   + ''.join(hero_card(h, rows.get(h['id']), rel) for h in sorted(other, key=key)) + '</div></details>')
    return ''.join(out)


def pre_release_switch(live: list[dict]) -> str:
    n = sum(1 for h in live if h.get('state') == 'EHeroDevState_PreRelease')
    if not n:
        return ''
    return (f'<label class="switch"><input type="checkbox" data-toggle-class="show-pre" data-target="#heroes-grid">'
            f'<span class="track"></span>Pre-release <span class="n">{n}</span></label>')
