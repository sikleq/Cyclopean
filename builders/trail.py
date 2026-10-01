"""The strip of history squares next to an entity (Sloppy's item cards have it): the last
N patches up to the one on screen, a square per patch, filled when the entity changed
there, coloured by what the change mostly was."""
from __future__ import annotations

from functools import lru_cache

from .cards import player_facing
from .common import esc, load_json
from .render import tag_of

GAMEPLAY = ('balance', 'mechanic', 'availability')
TRAIL_LEN = 12
TAG_WORD = {'buff': 'buff', 'nerf': 'nerf', 'rework': 'buffs and nerfs', 'new': 'added', 'del': 'removed',
            'mech': 'mechanic change', 'changed': 'changed', 'on': 'enabled', 'off': 'disabled'}


def dominant(changes: list[dict]) -> str:
    kinds = [tag_of(c)[0] for c in changes]
    if 'buff' in kinds and 'nerf' in kinds:
        return 'rework'
    for k in ('rework', 'buff', 'nerf', 'new', 'del', 'off', 'on', 'mech'):
        if k in kinds:
            return k
    return 'changed'


@lru_cache(maxsize=1)
def _index() -> tuple[list[dict], dict[str, dict[str, str]]]:
    """(patches oldest first, {entity key: {patch id: dominant tag}})"""
    rows = sorted(load_json('patches/index.json'), key=lambda r: r['date'])
    by_ent: dict[str, dict[str, str]] = {}
    for r in rows:
        p = load_json(f'patches/{r["id"]}.json.gz')
        for e in p['entities']:
            ch = player_facing([c for c in e['changes'] if c['cat'] in GAMEPLAY])
            if ch and e.get('id') != '@shared':
                by_ent.setdefault(e['key'], {})[r['id']] = dominant(ch)
    return rows, by_ent


def last_change(key: str) -> tuple[dict, str] | None:
    """(patch index row, dominant tag) of the newest patch that changed the entity."""
    rows, by_ent = _index()
    hits = by_ent.get(key) or {}
    for r in reversed(rows):
        if r['id'] in hits:
            return r, hits[r['id']]
    return None


@lru_cache(maxsize=1)
def patch_stats() -> dict[str, dict]:
    """patch id -> {'tags': {tag class: count}, 'heroes': [hero ids, most changed first]}."""
    out: dict[str, dict] = {}
    for r in load_json('patches/index.json'):
        p = load_json(f'patches/{r["id"]}.json.gz')
        tags: dict[str, int] = {}
        heroes: dict[str, int] = {}
        for e in p['entities']:
            owner = e['id'] if e['file'] == 'heroes.vdata' and e['id'] != '@shared' else e.get('owner')
            for c in player_facing([c for c in e['changes'] if c['cat'] in GAMEPLAY]):
                cls = tag_of(c)[0]
                tags[cls] = tags.get(cls, 0) + 1
                if owner and owner != 'hero_base':
                    heroes[owner] = heroes.get(owner, 0) + 1
        out[r['id']] = {'tags': tags, 'heroes': sorted(heroes, key=lambda h: (-heroes[h], h))}
    return out


@lru_cache(maxsize=1)
def _hero_changes() -> dict[str, tuple[dict, list[dict]]]:
    """hero id -> (newest patch row that touched the hero or one of its abilities, its changes)."""
    out: dict[str, tuple[dict, list[dict]]] = {}
    for r in sorted(load_json('patches/index.json'), key=lambda r: r['date'], reverse=True):
        p = load_json(f'patches/{r["id"]}.json.gz')
        found: dict[str, list[dict]] = {}
        for e in p['entities']:
            owner = e['id'] if e['file'] == 'heroes.vdata' and e['id'] != '@shared' else e.get('owner')
            if owner and owner not in out:
                found.setdefault(owner, []).extend(player_facing([c for c in e['changes'] if c['cat'] in GAMEPLAY]))
        for hid, ch in found.items():
            if ch:
                out[hid] = (r, ch)
    return out


def hero_last(hid: str) -> tuple[dict, list[dict]] | None:
    """The hero's newest patch (its own stats or any of its abilities) and what changed there."""
    return _hero_changes().get(hid)


def trail_html(key: str, current: str | None = None, rel: str = '../', n: int = TRAIL_LEN) -> str:
    """Squares for the last n patches ending at `current` (or the newest); empty when the
    entity never changed in that span."""
    rows, by_ent = _index()
    hits = by_ent.get(key)
    if not hits:
        return ''
    ids = [r['id'] for r in rows]
    end = ids.index(current) + 1 if current in ids else len(ids)
    span = rows[max(0, end - n):end]
    if not any(r['id'] in hits for r in span):
        return ''
    cells = []
    for r in span:
        tag = hits.get(r['id'])
        cur = ' cur' if r['id'] == current else ''
        if tag:
            tip = f'{r["title"]} · {TAG_WORD.get(tag, tag)}'
            cells.append(f'<a class="sq t-{tag}{cur}" href="{rel}patches/{esc(r["id"])}.html" '
                         f'data-tooltip="{esc(tip)}"></a>')
        else:
            cells.append(f'<span class="sq{cur}"></span>')
    return '<span class="trail">' + ''.join(cells) + '</span>'
