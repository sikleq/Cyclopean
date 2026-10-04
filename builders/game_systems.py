"""The Game section's map: which system and part an entry, a rule for every hero / ability or a console variable
belongs to (data/overrides/game_systems.json), what it is called and its icon; console variables as history rows.

The site's fourth section (coverage audit 2026-10-05, owner: "I want to see ALL changes to everything in the game")
is everything that is not one hero, item or unit: the Soul Urn, crates, powerups, the Rejuvenator, soul sharing, the
level curve, respawn times. An entry is the Game's when no hero, item or unit page claims it (`claimed`): a hero's
abilities and gun are the hero's, a shop item is its own, an NPC and the abilities it binds are the unit's; the rest
— map objects (misc.vdata), game rules (generic_data.vdata), effects (modifiers.vdata), loot tables, abilities no
hero owns (Drop Soul Urn, jump, dash), templates (trooper_base) — is placed by the config's regexes, first match
wins, and what none names falls to 'other' (nothing is lost)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from .common import ICONS, icon_manifest, load_json, pretty_id, visual

CONFIG = 'overrides/game_systems.json'
CONVAR_PREFIX = 'convars:'          # by_ent key of a console variable's rows ('convars:citadel_koth_warning_time')
ALL_PREFIX = 'game:all:'            # by_ent key of a patch's rules for every hero / ability ('game:all:heroes.vdata')
SECTION = 'game'
# files whose entries can be a page's: everything else is the Game's whatever its id
PAGE_FILES = ('heroes.vdata', 'abilities.vdata', 'npc_units.vdata')


@dataclass(frozen=True)
class Part:
    id: str
    name: str
    rules: tuple[re.Pattern, ...]


@dataclass(frozen=True)
class System:
    id: str
    name: str
    icon: str
    subjects: tuple[str, ...]
    parts: tuple[Part, ...]

    @property
    def href(self) -> str:
        return f'{self.id}.html'


@lru_cache(maxsize=1)
def _config() -> dict:
    return load_json(CONFIG)


@lru_cache(maxsize=1)
def systems() -> tuple[System, ...]:
    out = []
    for s in _config()['systems']:
        parts = tuple(Part(p['id'], p['name'], tuple(re.compile(rx) for rx in p.get('match', ())))
                      for p in s['parts'])
        out.append(System(s['id'], s['name'], s.get('icon', ''), tuple(s.get('subjects', ())), parts))
    return tuple(out)


def shown() -> tuple[System, ...]:
    """The systems in the order the pages list them (the config's 'display'; `systems` is the regexes' order)."""
    order = {sid: i for i, sid in enumerate(_config().get('display', ()))}
    return tuple(sorted(systems(), key=lambda s: order.get(s.id, len(order))))


def system(sid: str) -> System:
    return next(s for s in systems() if s.id == sid)


def part_name(sid: str, pid: str) -> str:
    return next((p.name for p in system(sid).parts if p.id == pid), '')


def place(subject: str) -> tuple[str, str] | None:
    """(system id, part id) of a subject — 'file:id#kind', 'file:@all:path' or 'convar:name' — or None."""
    for s in systems():
        for p in s.parts:
            if any(rx.match(subject) for rx in p.rules):
                return s.id, p.id
    return None


def entity_subject(key: str, kind: str | None) -> str:
    return f'{key}#{kind or ""}'


def is_template(e: dict) -> bool:
    """An engine template (trooper_base, hero_base, the breakables' prop base): no player meets it, its heirs do."""
    return bool(e.get('template')) or str(e.get('id', '')).endswith('_base')


def claimed(e: dict) -> bool:
    """A hero, item or unit page shows this entry (catalog row or patch entity): a hero and its abilities and gun,
    a shop item ('upgrade_*'), an NPC and the abilities it binds. Templates never."""
    file, eid = e.get('file'), str(e.get('id', ''))
    if file not in PAGE_FILES or is_template(e):
        return False
    if file in ('heroes.vdata', 'npc_units.vdata'):
        return True
    return bool(e.get('owner')) or bool(e.get('units')) or (e.get('kind') == 'item' and eid.startswith('upgrade_'))


def is_decor(e: dict) -> bool:
    """The city's traffic, glass panes, team and outline colours (classify.decor_entity): scenery, no page's. A
    shared edit spread over the breakable props lands on the cars too."""
    from pipeline.classify import decor_entity
    return e.get('file') in DECOR_FILES and decor_entity(str(e.get('id', '')))


DECOR_FILES = ('misc.vdata', 'generic_data.vdata')


def place_entity(key: str, e: dict, pages: set[str] | frozenset[str] | None = None) -> tuple[str, str] | None:
    """The Game's (system, part) of an entry no page claims; None for a claimed one or scenery. `pages`: the keys
    the hero, item and unit pages show (entities_pages.page_keys) — where the pages are built, the Game takes exactly
    the rest; without it, what the files say (`claimed`: the change matrices, the home feed)."""
    if (key in pages if pages is not None else claimed(e)) or is_decor(e):
        return None
    return place(entity_subject(key, e.get('kind'))) or ('other', 'rest')


def place_all_row(file: str, c: dict) -> tuple[str, str]:
    """A row of a rule for every hero or ability (the level curve, every melee's heavy attack, every item's slot
    cost): its system and part by its path."""
    return place(f'{file}:@all:{c.get("path") or ""}') or ('other', 'rest')


# ---- names and icons --------------------------------------------------------------------------------------------

def name_of(key: str, e: dict | None = None) -> str:
    """The site's name of a Game entry: the config's (the files give these no text), else the game's own name,
    else a readable stand-in — never the id. A template says so."""
    named = _config().get('names', {}).get(key)
    if named:
        return named
    file, _, eid = key.partition(':')
    e = e or {'file': file, 'id': eid}
    # an effect's id says it is one ("modifier_citadel_idol_return" read "Modifier citadel idol return")
    nm = e.get('name')
    name = nm if nm and nm != eid else pretty_id(eid.removeprefix('modifier_'), e.get('owner'))
    if file == 'loot_tables.vdata':          # "all_items" is a crate's loot table, not every item
        name = f'Loot table: {name}'
    return f'{name} (template)' if is_template(e) and 'template' not in name.lower() else name


def icon_url(sys_: System, rel: str) -> str | None:
    """A system's icon from the game files (icons/…); None for a site glyph ('glyph:…')."""
    if sys_.icon.startswith('glyph:'):
        return None
    return f'{rel}icons/{sys_.icon}'


def icon_html(sys_: System, rel: str, cls: str = 'px') -> str:
    glyph = sys_.icon.removeprefix('glyph:') if sys_.icon.startswith('glyph:') else 'rules'
    return visual(icon_url(sys_, rel), glyph, cls)


def missing_icons() -> list[str]:
    """Config icons that are not in icons/ (AGENTS rule 8: a missing icon is an error, never a silent stand-in)."""
    known = set(icon_manifest().values())
    return [s.icon for s in systems() if not s.icon.startswith('glyph:')
            and s.icon not in known and not (ICONS / s.icon).exists()]


# ---- console variables ------------------------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _hide() -> re.Pattern:
    return re.compile(_config().get('convar_hide') or r'$^')


@lru_cache(maxsize=1)
def _polarity() -> tuple[tuple[re.Pattern, int], ...]:
    return tuple((re.compile(rx), side) for rx, side in _config().get('convar_polarity', ()))


def convar_place(cv: dict) -> tuple[str, str] | None:
    """(system, part) of a console variable a player's game reads: the server's ('gamedll'), named by a part,
    not a test or display switch; None stays in the patch archive only."""
    name = str(cv.get('name') or '')
    if 'gamedll' not in str(cv.get('flags') or '').split() or _hide().search(name):
        return None
    return place(f'convar:{name}')


def convar_side(name: str) -> int:
    for rx, side in _polarity():
        if rx.search(name):
            return side
    return 0


def _num(v) -> float | None:
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def convar_change(name: str, op: str, old, new, status: str, builds: list) -> dict:
    """One console variable's change in a patch as a history row (the shape of data/patches changes): its name as
    the label (console variable names are the one id a page shows, AGENTS), BUFF / NERF by its side for the taker,
    else UP / DOWN."""
    a, b = _num(old), _num(new)
    side = convar_side(name)
    dirn, pct = 'changed', None
    if op == 'change' and a is not None and b is not None and a != b:
        dirn = ('buff' if (b > a) == (side > 0) else 'nerf') if side else ('up' if b > a else 'down')
        pct = round((b - a) / abs(a) * 100, 1) if a else None
    return {'key': f'{CONVAR_PREFIX}{name}:{name}', 'file': 'convars', 'id': name, 'path': name, 'op': op,
            'cat': 'balance', 'label': name, 'old_s': '' if old is None else str(old),
            'new_s': '' if new is None else str(new), 'dir': dirn, 'pct': pct, 'status': status or 'hidden',
            'builds': builds, 'convar': True}


def convar_changes(rows: list[dict], start_build: int | None) -> list[dict]:
    """A patch's console variables (extras.convars) as history rows, one per variable: its value before the
    window's first build → after its last (added = no value before, removed = none after). The snapshot that starts
    the tracking (`start_build`, 6395: 1,365 entries) and description-only edits are no change."""
    first: dict[str, dict] = {}
    last: dict[str, dict] = {}
    for cv in sorted(rows, key=lambda x: x.get('build') or 0):
        if cv.get('build') == start_build or cv.get('op') == 'desc' or not convar_place(cv):
            continue
        first.setdefault(cv['name'], cv)
        last[cv['name']] = cv
    out = []
    for name, a in first.items():
        b = last[name]
        old = None if a['op'] == 'add' else a.get('old')
        new = None if b['op'] == 'remove' else b.get('new')
        if old is None and new is None or old is not None and new is not None and str(old) == str(new):
            continue
        op = 'add' if old is None else 'remove' if new is None else 'change'
        builds = sorted({cv.get('build') for cv in rows if cv.get('name') == name and cv.get('build')})
        out.append(convar_change(name, op, old, new, a.get('status') or b.get('status'), builds))
    return out


@lru_cache(maxsize=1)
def convar_start() -> int | None:
    """The first build with console variables (6395, 2026-03-10: the tracker began dumping them): a snapshot of all
    1,365 of them, not changes."""
    return next((b['build'] for b in load_json('builds/index.json') if b.get('convars')), None)


def merged_label(names: list[str]) -> str:
    """The header of entries whose rows are identical in a patch (one edit spread over twelve breakables)."""
    names = list(dict.fromkeys(names))
    if len(names) <= 3:
        return ' · '.join(names)
    return f'{names[0]}, {names[1]} + {len(names) - 2} more'
