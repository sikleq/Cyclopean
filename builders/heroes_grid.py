"""Heroes index laid out like the game's hero grid: one grid of tall portrait cards in the order of
the game's sort names (The Doorman under D), the name plate in the hero's own colour from the game
(m_colorUI), the role as text (the game has no role icons) and complexity as marks; pre-release
heroes carry a ribbon. Under each card: what the hero's newest patch did to it."""
from __future__ import annotations

from .common import esc, hero_icon, icon, slug

COMPLEXITY_MAX = 3


def hero_color(c) -> str | None:
    """[r, g, b] or [r, g, b, a] from heroes.vdata m_colorUI -> 'rgb(r g b)'; anything else -> None."""
    if isinstance(c, (list, tuple)) and len(c) >= 3 and all(isinstance(x, (int, float)) for x in c[:3]):
        r, g, b = (max(0, min(255, int(x))) for x in c[:3])
        return f'rgb({r} {g} {b})'
    return None


def _portrait(hid: str, rel: str) -> str | None:
    return icon(f'heroes/card:{hid}', rel) or icon(f'heroes/vertical:{hid}', rel) or hero_icon(hid, rel)


def hero_card(h: dict, row: dict | None, rel: str, foot: str) -> str:
    row = row or {}
    name = h.get('name') or h['id']
    href = slug(h['file'], h['id']).split('/', 1)[1]
    src = _portrait(h['id'], rel)
    img = f'<img src="{esc(src)}" alt="" loading="lazy">' if src else '<span class="noimg"></span>'
    pre = h.get('state') == 'EHeroDevState_PreRelease'
    ribbon = '<span class="hg-rib">Pre-release</span>' if pre else ''
    role = str(row.get('type') or '').rsplit('_', 1)[-1]
    cx = row.get('complexity')
    marks = ''
    if isinstance(cx, int) and cx > 0:
        marks = ('<span class="hg-cx" data-tooltip="Complexity ' + str(cx) + '">'
                 + ''.join(f'<i class="{"on" if i < cx else ""}"></i>' for i in range(max(cx, COMPLEXITY_MAX))) + '</span>')
    meta = f'<span class="hg-meta"><span class="hg-role">{esc(role) or "&nbsp;"}</span>{marks}</span>'
    # the hero's colour comes from the game data, so it rides as a custom property, not a :root token
    # (an exception the owner approved on 2026-10-01)
    color = hero_color(row.get('color'))
    style = f' style="--hero: {color}"' if color else ''
    return (f'<a class="hgcard px-frame{" pre" if pre else ""}" href="{esc(href)}"{style} data-search="{esc(name.lower())}">'
            f'<span class="hg-pic">{img}{ribbon}</span><span class="hg-nm">{esc(name)}</span>{meta}{foot}</a>')


def heroes_grid_html(live: list[dict], other: list[dict], rows: dict, rel: str, foot_of) -> str:
    def key(h: dict) -> str:
        return ((rows.get(h['id']) or {}).get('sort_name') or h.get('name') or h['id']).lower()
    live = sorted(live, key=key)
    out = ['<div class="hgrid-cards">'
           + ''.join(hero_card(h, rows.get(h['id']), rel, foot_of(h['id'])) for h in live) + '</div>']
    if other:
        out.append('<div class="grid-group-title">Unreleased & hero labs</div><div class="hgrid-cards lab">'
                   + ''.join(hero_card(h, rows.get(h['id']), rel, '') for h in sorted(other, key=key)) + '</div>')
    return ''.join(out)
