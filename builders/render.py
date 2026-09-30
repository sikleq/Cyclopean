"""Rendering of change records shared by patch, build and entity pages."""
from __future__ import annotations

from .common import entity_icon, esc, img, mark, slug

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


def entity_block(ent: dict, rel: str, children: list[dict] | None = None, show_builds: bool = False) -> str:
    """One entity (hero/item/unit) with its changes and optional child entities (abilities, weapon)."""
    changes = sort_changes(ent.get('changes', []))
    has_hidden = any(c.get('status') == 'hidden' for c in changes) or any(
        c.get('status') == 'hidden' for ch in (children or []) for c in ch.get('changes', []))
    href = slug(ent['file'], ent['id'])
    name = esc(ent.get('name') or ent['id'])
    name_html = f'<a href="{rel}{href}">{name}</a>' if href else name
    ic = entity_icon(ent['file'], ent['id'], ent.get('kind', ''), rel)
    kind = KIND_LABEL.get(ent.get('kind') or '', ent.get('kind') or '')
    parts = [f'<div class="entity-block px-frame{" has-hidden" if has_hidden else ""}" data-search="{name.lower()}">',
             f'<div class="entity-head">{img(ic, "", "px")}<span class="nm">{name_html}</span>'
             f'<span class="chip kind">{esc(kind)}</span></div>']
    if changes:
        parts.append('<ul class="change-list">' + ''.join(change_li(c, show_builds=show_builds) for c in changes) + '</ul>')
    for ch in children or []:
        cic = entity_icon(ch['file'], ch['id'], ch.get('kind', ''), rel)
        ck = KIND_LABEL.get(ch.get('kind') or '', '')
        parts.append(f'<div class="entity-sub"><div class="entity-sub-head">{img(cic, "", "px")}'
                     f'{esc(ch.get("name") or ch["id"])}<span class="chip">{esc(ck)}</span></div>'
                     '<ul class="change-list">' + ''.join(change_li(c, show_builds=show_builds)
                                                         for c in sort_changes(ch.get('changes', []))) + '</ul></div>')
    parts.append('</div>')
    return ''.join(parts)


def group_by_owner(entities: list[dict]) -> list[tuple[dict, list[dict]]]:
    """Nest ability/weapon entities under their hero; others stand alone."""
    heroes = {e['id']: e for e in entities if e.get('file') == 'heroes.vdata'}
    children: dict[str, list[dict]] = {}
    standalone = []
    for e in entities:
        if e.get('file') == 'heroes.vdata':
            continue
        owner = e.get('owner')
        if owner and e.get('kind') in ('ability', 'weapon', 'melee'):
            children.setdefault(owner, []).append(e)
            if owner not in heroes:
                heroes[owner] = {'file': 'heroes.vdata', 'id': owner, 'kind': 'hero', 'name': e.get('owner_name') or owner,
                                 'changes': []}
        else:
            standalone.append(e)
    out = [(h, sorted(children.get(hid, []), key=lambda x: x.get('name') or '')) for hid, h in heroes.items()]
    out.sort(key=lambda x: (x[0].get('name') or '').lower())
    out += [(e, []) for e in standalone]
    return out
