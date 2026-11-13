"""The groups of a history band: one per part of the entity (`_groups`), namesakes told apart (`_namesakes`,
`id_tail`), and the rows every hero / item shares (`split_every`, `every_groups`)."""
from __future__ import annotations

import re

from .notes_view import _highlight, text_tag
from .fix_reports import reported_chip
from .model_rows import model_rows
from .text_rows import text_rows


CONVARS_KEY = ':convars'  # a Game system part's console variables (game_pages: 'game:<system>:<part>:convars')


def _drop_prefix(text: str, names: list[str]) -> str:
    """'Abrams: Siphon Life DPS reduced…' under the Siphon Life block -> 'DPS reduced…'."""
    out = text
    changed = True
    while changed:                       # "Abrams: Siphon Life …" carries both, hero first
        changed = False
        for n in sorted((n for n in names if n), key=len, reverse=True):
            m = re.match(rf'\s*{re.escape(n)}\s*(?:[:\-–—]\s*|\s+(?=\S))', out, flags=re.I)
            if m:
                out = out[m.end():]
                changed = True
    out = out.strip()
    return out[:1].upper() + out[1:] if out else text


def _groups(slot: dict, order: dict, meta: dict, names: list[str], hints: dict | None, merge,
            every_href=None) -> list[dict]:
    """The patch's parts in page order: {'keys', 'rows' html, 'changes', 'lines'}; members whose rows are
    the same merge into one group (unit families). `every_href`: system id -> the Game page's band of this patch
    (the link row of a rule for every hero, cards.every_rows)."""
    from .cards import entity_rows, row
    from .render import note_badge
    groups: list[dict] = []
    texts = slot.get('texts', {})
    # a hero page fills "[Hero name]" in its texts with the hero's name
    hero = names[0] if names and order and next(iter(order)).startswith('heroes.vdata:') else None
    models = slot.get('models', {})
    for key in sorted(set(slot['ch']) | set(slot['lines']) | set(texts) | set(models), key=lambda k: order.get(k, 999)):
        nm, _ = meta[key]
        changes = slot['ch'].get(key, [])
        lines = slot['lines'].get(key, [])
        rows = entity_rows(changes, (hints or {}).get(key), every_href)
        for ln in lines:
            text = _drop_prefix(ln['text'], names + [nm])
            # a line whose wording names no kind gets the neutral NOTE (its tag column was blank)
            rows += row(ln['status'], text_tag(text, ln.get('topic')) or note_badge('NOTE'),
                        _highlight(text, 'changed') + reported_chip(slot['row']['id'], ln['text']))
        rows += text_rows(texts.get(key, []), hero, changes)
        rows += model_rows(models.get(key, []))
        if not rows:
            continue
        cv = next((g for g in groups if g['keys'][0].endswith(CONVARS_KEY)), None) if key.endswith(CONVARS_KEY) else None
        if merge and cv is not None and not (lines or cv['lines'] or texts.get(key) or texts.get(cv['keys'][0])):
            # a Game system's console variables are one group per band, whichever part each belongs to: the Souls page
            # read "Console variables" twice in one update (review 2026-10-17, round 4); the group keeps every part's
            # filter (its keys' areas)
            cv['keys'].append(key)
            cv['changes'] = cv['changes'] + changes
            cv['rows'] = entity_rows(cv['changes'], None, every_href)
            continue
        # the same rows on another member: one group, both named (a family, a Game system); on any page the same rows
        # under the same name are one group too (review 2026-10-05: Holliday's "Weapon (shotgun)" twice, Kelvin's
        # "Frozen Shelter" twice with one row each)
        same = next((g for g in groups if g['rows'] == rows and (merge or meta[g['keys'][0]][0] == nm)), None)
        if same:
            same['keys'].append(key)
            if merge:
                # its rows are counted with the group's: an edit they share once, an entity each that came or went
                # (render.same_change: four new sketch pickups are four changes)
                same['changes'] = same['changes'] + changes
            continue
        groups.append({'keys': [key], 'rows': rows, 'changes': changes, 'lines': lines})
    return groups


def _namesakes(groups: list[dict], meta: dict, gone: set[str] | frozenset[str] = frozenset()) -> dict[int, str]:
    """Group index -> its header when an earlier group of the band has the same name and other rows (an ability and
    its trigger, an old and a new version: Kelvin's two "Frozen Shelter", Wrecker's two "Wrecking Ball"; review
    2026-10-05): a removed one is "(old version)", another says how its id differs ("Frozen Shelter · trigger")."""
    by_name: dict[str, list[int]] = {}
    for gi, g in enumerate(groups):
        by_name.setdefault(meta[g['keys'][0]][0], []).append(gi)
    out: dict[int, str] = {}
    for nm, idx in by_name.items():
        if len(idx) < 2:
            continue
        live = [gi for gi in idx if groups[gi]['keys'][0] not in gone]
        for gi in idx:
            if gi not in live:
                out[gi] = f'{nm} (old version)'
        if not live:
            continue
        a = groups[live[0]]['keys'][0].partition(':')[2]
        for gi in live[1:]:
            tail = id_tail(a, groups[gi]['keys'][0].partition(':')[2])
            if tail:
                out[gi] = f'{nm} · {tail}'
    return out


def id_tail(a: str, b: str) -> str:
    """How id `b` differs from its namesake `a`, in words: 'ability_frozen_shelter_trigger' beside
    'ability_frozen_shelter' -> 'trigger'."""
    n = 0
    while n < min(len(a), len(b)) and a[n] == b[n]:
        n += 1
    m = 0
    while m < min(len(a), len(b)) - n and a[-1 - m] == b[-1 - m]:
        m += 1
    return b[n:len(b) - m].strip('_').replace('_', ' ')


def _dev_only(g: dict, in_dev: bool) -> bool:
    """Every counted row of the group is work on a hero still in development (and the page is not that hero's)."""
    from .cards import player_facing
    rows = player_facing(g['changes'])
    return (any(c.get('status') == 'unreleased' for c in rows) and all(c.get('status') == 'unreleased' for c in rows)
            and not g['lines'] and not in_dev)


def every_sig(c: dict) -> tuple:
    """One rule for all, whichever of the entity's abilities carries its copy (shared_rows.spread writes the same
    path, values and noun into every target)."""
    return (c.get('file'), c.get('path'), str(c.get('old_s')), str(c.get('new_s')), c.get('shared_what'))


def split_every(slot: dict, in_dev: bool) -> tuple[dict, list[dict]]:
    """(the band's slot with only the entity's own rows, the rules for every hero / ability it carries — counted as
    the counters count, `player_facing`, released ones unless the page is a hero in development — ONCE each). The
    same rule sat under each of the entity's abilities it touched and the banner counted every copy (Holliday
    2026-01-22: "+9 for all abilities & items" for one rule; review 2026-10-05)."""
    from .cards import player_facing
    from .shared_rows import is_every
    own: dict[str, list[dict]] = {}
    every: dict[tuple, dict] = {}
    for key, ch in slot['ch'].items():
        mine = [c for c in ch if not is_every(c)]
        if mine:
            own[key] = mine
        rules = [c for c in ch if is_every(c)]
        if rules:
            for c in player_facing(rules):
                if in_dev or c.get('status') != 'unreleased':
                    every.setdefault(every_sig(c), c)
    return {**slot, 'ch': own}, list(every.values())


def every_name(rows: list[dict]) -> str:
    """'All heroes' for the rows of a rule for every entity of a kind (shared_rows)."""
    return f'All {rows[0].get("shared_what") or "entities"}' if rows else ''


def every_groups(rows: list[dict]) -> dict[str, list[dict]]:
    """The rows of rules for every entity of a kind, by kind: {'All heroes': rows, 'All melee attacks': rows}."""
    out: dict[str, list[dict]] = {}
    for c in rows:
        out.setdefault(every_name([c]), []).append(c)
    return out
