"""Rendering of change records shared by patch, build and entity pages."""
from __future__ import annotations

import re

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


_FLAG_PREFIX = re.compile(r'^(CITADEL_ABILITY_BEHAVIOR_|MODIFIER_STATE_|MODIFIER_VALUE_|EAbility|E[A-Z][a-z]+_|DOTA_)')
LONG_VALUE = 60


def _flags(s) -> list[str] | None:
    """'A | B' bit flags or 'a, b, c' id lists -> items; None for plain values."""
    if not isinstance(s, str):
        return None
    if ' | ' in s:
        return [f.strip() for f in s.split('|') if f.strip()]
    parts = [f.strip() for f in s.split(', ')]
    if len(parts) > 1 and all(p and ' ' not in p for p in parts):
        return parts
    return None


def _short_flag(f: str) -> str:
    return _FLAG_PREFIX.sub('', f).replace('_', ' ').lower()


def flags_html(old_s, new_s) -> str | None:
    """Bit-flag lists ('A | B | C') show only what was added / removed."""
    a, b = _flags(old_s), _flags(new_s)
    if a is None and b is None:
        return None
    a, b = set(a or ([old_s] if old_s else [])), set(b or ([new_s] if new_s else []))
    added = ''.join(f'<span class="flag add">+{esc(_short_flag(f))}</span>' for f in sorted(b - a))
    removed = ''.join(f'<span class="flag rem">−{esc(_short_flag(f))}</span>' for f in sorted(a - b))
    return f'<span class="vals flags">{added}{removed}</span>'


def _clip(s) -> str:
    s = '' if s is None else str(s)
    return s if len(s) <= LONG_VALUE else s[:LONG_VALUE - 1] + '…'


def vals_html(c: dict) -> str:
    op = c.get('op')
    if c.get('cat') in ('visual', 'audio', 'ui'):
        return f'<span class="vals muted">{esc(op)}</span>'
    old_s = c.get('old_s', c.get('old'))
    new_s = c.get('new_s', c.get('new'))
    fl = flags_html(old_s, new_s)
    if fl:
        return fl
    old_s, new_s = _clip(old_s), _clip(new_s)
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
