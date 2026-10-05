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


_VALUE = re.compile(r'\{s:(\w+)\}')
# the hero's own name and a key binding ("{s:iv_attack}", "{s:ability_key}") are no value of the ability:
# builders/text_rows fills the one, draws the other as a key
HERO_TOKEN = re.compile(r'^hero_?name$', re.I)
BINDING_TOKEN = re.compile(r'^(?:(?:iv|in|key)_|ability_key$)', re.I)


def not_a_value(name: str) -> bool:
    return bool(HERO_TOKEN.match(name) or BINDING_TOKEN.match(name))
VALUE_PARTS = ('desc', 't1', 't2', 't3')


def value_tokens(text: str | None) -> list[str]:
    """The values a text has the game fill in ("{s:AbilityCooldown}"), in order, once each."""
    return list(dict.fromkeys(n for n in _VALUE.findall(str(text or '')) if not not_a_value(n)))


def _side_values(text: str | None, part_values: dict[str, str] | None) -> dict[str, str]:
    """{token: value} of the tokens a text uses that the build knows (a token is looked up as written, then
    without case — the game reads keys without case)."""
    if not part_values:
        return {}
    lower = {k.lower(): v for k, v in part_values.items()}
    out = {}
    for n in value_tokens(text):
        v = part_values.get(n, lower.get(n.lower()))
        if v is not None:
            out[n] = v
    return out


def with_values(rows: list[dict], before, after) -> list[dict]:
    """The rows with `vals` = {'old': {token: value}, 'new': {…}}: what the game filled into the old text at the
    window's start and into the new text at its end (Haze's Sleep Dagger T2 2026-07-28 read "[Ability Cooldown]s
    Cooldown → +[Sleep Duration]s Sleep Duration"; review 2026-10-05: ~550 such rows). `before` / `after`: entity key
    -> {part: {token: value}} of that state (pipeline.abilities.text_values), None when it is not known. A row
    without value tokens is unchanged; a token neither build knows stays out (the page writes a neutral gap)."""
    out = []
    for row in rows:
        if row.get('part') not in VALUE_PARTS or not (value_tokens(row.get('old')) or value_tokens(row.get('new'))):
            out.append(row)
            continue
        vals = {}
        for side, state in (('old', before), ('new', after)):
            got = _side_values(row.get(side), ((state or {}).get(row['ent']) or {}).get(row['part']))
            if got:
                vals[side] = got
        out.append({**row, 'vals': vals} if vals else row)
    return out


def needed(rows: list[dict]) -> set[str]:
    """Entity keys whose texts in `rows` hold values the game fills in (the states `with_values` needs)."""
    return {r['ent'] for r in rows if r.get('part') in VALUE_PARTS
            and (value_tokens(r.get('old')) or value_tokens(r.get('new')))}


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
