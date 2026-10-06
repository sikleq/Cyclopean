"""The Game section's map as the matcher reads it: which game system an entry or a console variable belongs to
(data/overrides/game_systems.json, the same regexes builders/game_systems.py places pages with) and the words the
patch notes use for a system ('subjects': "Jump Pad", "Zip Line", "Urn", "Bounty").

A note line names a system far more often than one of its entries: "Jump Pad stun window increased from 0.6s to
0.9s" is modifier_citadel_catapult_damage_watcher's Duration, "Trooper bounty split ratios updated from 1/0.65/… to
1/0.54/…" is generic_data's m_flTrooperKillGoldShareFrac — entries the files give no name, so no line could reach
them and they kept the eye (coverage finding 8). `system_pools` gives each subject phrase the entries of its system
that no hero, item or unit page claims (`claimed`), plus the console variables the system's parts name."""
from __future__ import annotations

import json
import re
from functools import lru_cache

from . import tracker

CONFIG = tracker.ROOT / 'data' / 'overrides' / 'game_systems.json'
# files whose entries can be a page's: everything else is the Game's whatever its id
PAGE_FILES = ('heroes.vdata', 'abilities.vdata', 'npc_units.vdata')


@lru_cache(maxsize=1)
def _config() -> dict:
    try:
        return json.loads(CONFIG.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {'systems': []}


@lru_cache(maxsize=1)
def _rules() -> tuple[tuple[str, str, tuple[re.Pattern, ...]], ...]:
    """(system id, part id, regexes) in the config's order: the first match wins."""
    return tuple((s['id'], p['id'], tuple(re.compile(rx) for rx in p.get('match', ())))
                 for s in _config()['systems'] for p in s['parts'])


def place(subject: str) -> tuple[str, str] | None:
    """(system id, part id) of a subject — 'file:id#kind', 'file:@all:path' or 'convar:name' — or None."""
    for sid, pid, rxs in _rules():
        if any(rx.match(subject) for rx in rxs):
            return sid, pid
    return None


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


@lru_cache(maxsize=1)
def subject_phrases() -> tuple[tuple[str, str], ...]:
    """(phrase, system id) of every system's note words, lower case, longest first: "jump pad" before "jump"."""
    out = {(w.strip().lower(), s['id']) for s in _config()['systems'] for w in s.get('subjects', ()) if w.strip()}
    return tuple(sorted(out, key=lambda x: (-len(x[0]), x[0], x[1])))


def phrases_in(text: str) -> list[tuple[str, str]]:
    """The (phrase, system id) a line names as whole words, a longer phrase hiding the ones inside it ("Soul Urn"
    is the Urn's, not "Souls & economy"'s); a trailing "s" / "es" counts ("Jump Pads")."""
    low = text.lower()
    found: list[tuple[str, str]] = []
    for phrase, sid in subject_phrases():
        if any(phrase in longer and phrase != longer for longer, _ in found):
            continue
        if re.search(rf'\b{re.escape(phrase)}(?:s|es)?\b', low):
            found.append((phrase, sid))
    return found


def system_entries(cat: dict[str, dict]) -> dict[str, frozenset[str]]:
    """system id -> the catalog keys placed in it that no page claims (a hero's own fields stay the hero's: the
    progression part takes every hero, and "Level 3 …" would have reached all of them)."""
    out: dict[str, set[str]] = {}
    for key, e in cat.items():
        if claimed(e):
            continue
        hit = place(f'{key}#{e.get("kind") or ""}')
        if hit:
            out.setdefault(hit[0], set()).add(key)
    return {sid: frozenset(keys) for sid, keys in out.items()}


def convar_system(name: str) -> str | None:
    hit = place(f'convar:{name}')
    return hit[0] if hit else None
