"""Name and description changes of the abilities, items and heroes a page shows (coverage audit 2026-10-05,
finding 7: 938 such text changes were only in the patch archive's "Text & tooltips" tab, cut at 400 a patch).

A localization key names an entity when it IS the entity's id (lower-case, as the game reads keys): its name
("ability_sleep_dagger", "upgrade_self_bubble", "hero_slork"), its description ("…_desc") or an upgrade tier's
("…_t2_desc"). A patch window keeps one row per entity and part: the first old text → the last new one. Kept only
when both sides have words and they read differently — a token respelt or a colour span moved is no change to a
reader, and a text that appears with the entity (or leaves with it) is the entity's own "Added / Removed" event.
Quips, lore, notes and labels are not kept (the audit: "quests and lore not shown")."""
from __future__ import annotations

import html
import re

TEXT_FILES = ('abilities.vdata', 'heroes.vdata')
# 'ability_x' (name), 'ability_x_desc', 'ability_x_t2_desc' (an upgrade tier's text)
_KEY = re.compile(r'^(?P<base>[a-z0-9_]+?)(?:_t(?P<tier>[1-3]))?(?P<desc>_desc)?$')
_TAGS = re.compile(r'<[^>]+>')
_SPACE = re.compile(r'\s+')


def words(s: str | None) -> str:
    """What a reader sees of a text: no markup, entities decoded, spaces collapsed."""
    return _SPACE.sub(' ', html.unescape(_TAGS.sub(' ', s or ''))).strip()


def key_part(key: str, ids: dict[str, str]) -> tuple[str, str] | None:
    """(entity key, part) a localization key names: part 'name', 'desc' or 't1'..'t3'; None for any other key.
    `ids`: lower-case entity id -> entity key ('abilities.vdata:ability_x')."""
    m = _KEY.match(key.lower())
    if not m:
        return None
    ent = ids.get(m.group('base'))
    if not ent:
        return None
    tier, desc = m.group('tier'), bool(m.group('desc'))
    if tier:
        return (ent, f't{tier}') if desc else None          # 'ability_x_t1' alone is a tier's label
    if ent.startswith('heroes.vdata:'):
        return (ent, 'name') if not desc else None          # a hero's "desc" is its lore blurb
    return ent, 'desc' if desc else 'name'


def entity_texts(loc_rows: list[dict], cat: dict[str, dict]) -> list[dict]:
    """[{ent, part, old, new, builds}] of one patch window's localization rows (each with its 'build'), in
    build order; see the module doc for what is kept."""
    ids = {e['id'].lower(): k for k, e in cat.items() if e.get('file') in TEXT_FILES}
    merged: dict[tuple[str, str], dict] = {}
    for x in loc_rows:
        hit = key_part(str(x.get('key') or ''), ids)
        if not hit:
            continue
        row = merged.get(hit)
        if row is None:
            merged[hit] = {'ent': hit[0], 'part': hit[1], 'old': x.get('old'), 'new': x.get('new'),
                           'builds': [x.get('build')]}
        else:
            row['new'] = x.get('new')
            row['builds'].append(x.get('build'))
    out = []
    for row in merged.values():
        a, b = words(row['old']), words(row['new'])
        if a and b and a != b:
            row['builds'] = sorted({n for n in row['builds'] if n is not None})
            out.append(row)
    return out
