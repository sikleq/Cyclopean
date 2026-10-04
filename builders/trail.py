"""The strip of history squares next to an entity (Sloppy's item cards have it): the last
N patches up to the one on screen, a square per patch, filled when the entity changed
there, striped in the colours of what changed (one colour when it was one kind)."""
from __future__ import annotations

from functools import lru_cache

from . import archive
from .cards import GAMEPLAY, player_facing
from .common import esc, patch_title_text
from .render import counts_text, tag_of

TRAIL_LEN = 12


def dominant_of(counts: dict[str, int]) -> str:
    """The tag that colours a one-colour mark (the shop card's "Last change" pip)."""
    if counts.get('buff') and counts.get('nerf'):
        return 'rework'
    for k in ('rework', 'buff', 'nerf', 'new', 'del', 'off', 'on', 'mech'):
        if counts.get(k):
            return k
    return 'changed'


@lru_cache(maxsize=1)
def _index() -> tuple[list[dict], dict[str, dict[str, dict[str, int]]]]:
    """(patches oldest first, {entity key: {patch id: {tag: count}}})"""
    rows = list(archive.by_date())
    by_ent: dict[str, dict[str, dict[str, int]]] = {}
    for r in rows:
        for e in archive.patch(r['id'])['entities']:
            ch = player_facing([c for c in e['changes'] if c['cat'] in GAMEPLAY])
            if ch and e.get('id') != '@shared':
                counts = by_ent.setdefault(e['key'], {}).setdefault(r['id'], {})
                for c in ch:
                    counts[tag_of(c)[0]] = counts.get(tag_of(c)[0], 0) + 1
    return rows, by_ent


def last_counts(key: str) -> tuple[dict, dict[str, int]] | None:
    """(patch index row, {tag: count}) of the newest patch that changed the entity."""
    rows, by_ent = _index()
    hits = by_ent.get(key) or {}
    for r in reversed(rows):
        if r['id'] in hits:
            return r, hits[r['id']]
    return None


def last_change(key: str) -> tuple[dict, str] | None:
    """(patch index row, dominant tag) of the newest patch that changed the entity."""
    last = last_counts(key)
    return (last[0], dominant_of(last[1])) if last else None


@lru_cache(maxsize=1)
def patch_stats() -> dict[str, dict]:
    """patch id -> {'tags': {tag class: count}, 'heroes': [hero ids, most changed first]}."""
    out: dict[str, dict] = {}
    for r in archive.index():
        tags: dict[str, int] = {}
        heroes: dict[str, int] = {}
        for e in archive.gameplay(r['id']):
            owner = e['id'] if e['file'] == 'heroes.vdata' and e['id'] != '@shared' else e.get('owner')
            for c in player_facing(e['changes']):        # gameplay rows already
                cls = tag_of(c)[0]
                tags[cls] = tags.get(cls, 0) + 1
                if owner and owner != 'hero_base':
                    heroes[owner] = heroes.get(owner, 0) + 1
        out[r['id']] = {'tags': tags, 'heroes': sorted(heroes, key=lambda h: (-heroes[h], h))}
    return out


@lru_cache(maxsize=1)
def _positions() -> dict[str, int]:
    return {r['id']: i for i, r in enumerate(_index()[0])}


@lru_cache(maxsize=None)          # a patch page asks for the same strip in its notes and in All changes
def trail_html(key: str, current: str | None = None, rel: str = '../', n: int = TRAIL_LEN, local: bool = False) -> str:
    """Squares for the last n patches ending at `current` (or the newest); empty when the
    entity never changed in that span. A patch that both buffed and nerfed is striped, not REWORK purple
    (REWORK means a replaced tier). `local`: the square is on the entity's own page — it opens that patch's
    band below (#p-<patch>) and shows the band's hover card (scripts.js, the page's strip data) instead of
    linking to the patch archive (owner 2026-10-04)."""
    from .dynamics_page import stripes
    rows, by_ent = _index()
    hits = by_ent.get(key)
    if not hits:
        return ''
    end = _positions().get(current, len(rows) - 1) + 1 if current else len(rows)
    span = rows[max(0, end - n):end]
    if not any(r['id'] in hits for r in span):
        return ''
    eid = key.partition(':')[2]
    cells = []
    for r in span:
        counts = hits.get(r['id'])
        cur = ' cur' if r['id'] == current else ''
        if not counts:
            cells.append(f'<span class="sq{cur}"></span>')
            continue
        pid = esc(r['id'])
        text = esc(f'{patch_title_text(r)} · {counts_text(counts)}')
        style = f' style="background:{stripes(counts)}"' if len(counts) > 1 else ''
        cls = f'sq t-{dominant_of(counts)}{cur}'
        if local:
            cells.append(f'<a class="{cls}" href="#p-{pid}" data-p="{pid}" data-ab="{esc(eid)}" '
                         f'aria-label="{text}"{style}></a>')
        else:
            cells.append(f'<a class="{cls}" href="{rel}patches/{pid}.html" data-tooltip="{text}"{style}></a>')
    return '<span class="trail">' + ''.join(cells) + '</span>'
