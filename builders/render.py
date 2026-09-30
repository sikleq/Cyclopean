"""Rendering of change records shared by patch, build and entity pages."""
from __future__ import annotations

from .common import esc, mark

TAG_ORDER = {'new': 0, 'rework': 1, 'buff': 2, 'nerf': 3, 'del': 4, 'changed': 6}
KIND_LABEL = {
    'hero': 'Hero', 'ability': 'Ability', 'weapon': 'Weapon', 'melee': 'Melee', 'item': 'Item',
    'ability_other': 'Ability', 'trooper': 'Trooper', 'building': 'Building', 'neutral': 'Neutral',
    'unit': 'Unit', 'modifier': 'Modifier', 'global': 'Game rules',
}


def tag_of(c: dict) -> tuple[str, str]:
    """(css class, badge text) for one change dict (from data/patches or build pages)."""
    op, cat = c.get('op'), c.get('cat')
    if cat == 'availability':
        new = str(c.get('new')).lower()
        if new in ('true', '1'):
            return 'del', 'DISABLED'
        if new in ('false', '0', 'ehherodevstate_release', 'eherodevstate_release'):
            return 'new', 'ENABLED'
        return 'changed', 'STATE'
    if op == 'add':
        return 'new', 'NEW'
    if op == 'remove':
        return 'del', 'DEL'
    d = c.get('dir')
    pct = c.get('pct')
    if d in ('buff', 'nerf'):
        txt = 'BUFF' if d == 'buff' else 'NERF'
        if pct is not None:
            txt += f' {abs(pct):.0f}%' if abs(pct) >= 1 else ''
        return d, txt
    return 'changed', 'MECH' if cat == 'mechanic' else 'CHANGED'


def tag_html(c: dict) -> str:
    cls, txt = tag_of(c)
    g = c.get('grad', 5)
    return f'<span class="tag {cls}" data-g="{g}">{esc(txt)}</span>'


def sort_changes(changes: list[dict]) -> list[dict]:
    return sorted(changes, key=lambda c: (TAG_ORDER.get(tag_of(c)[0], 7), c.get('label', '')))


def vals_html(c: dict) -> str:
    op = c.get('op')
    if c.get('cat') in ('visual', 'audio', 'ui'):
        return f'<span class="vals muted">{esc(op)}</span>'
    old_s = c.get('old_s', c.get('old'))
    new_s = c.get('new_s', c.get('new'))
    if op == 'add':
        return f'<span class="vals"><span class="new">{esc(new_s)}</span></span>'
    if op == 'remove':
        return f'<span class="vals"><span class="old">{esc(old_s)}</span></span>'
    d = c.get('dir', 'changed')
    pct = c.get('pct')
    pct_s = f'<span class="pct dir-{d}">{pct:+.1f}%</span>' if isinstance(pct, (int, float)) else ''
    return (f'<span class="vals"><span class="old">{esc(old_s)}</span><span class="arrow">→</span>'
            f'<span class="new dir-{d}">{esc(new_s)}</span>{pct_s}</span>')


def change_li(c: dict, show_status: bool = True, show_builds: bool = False) -> str:
    st = c.get('status', 'hidden')
    status = mark(st) if show_status else ''
    builds = ''
    if show_builds and c.get('builds'):
        builds = f'<span class="bld">{esc(", ".join(str(b) for b in c["builds"]))}</span>'
    return (f'<li class="st-{esc(st)} cat-{esc(c.get("cat", ""))}">{status}{tag_html(c)}'
            f'<span class="lbl">{esc(c.get("label"))}</span>{vals_html(c)}{builds}</li>')
