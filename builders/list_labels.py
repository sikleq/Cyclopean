"""Labels of list rows that read as code, put in words where the list says what its items are (concept audit
2026-11-13: 194 odd labels). The pipeline's labels stay as they are in data/; every gameplay row passes here on its
way to a page (`brawl.gameplay_rows`), so a page, a counter and a fold read the same words.

- an item of a list the files call "value" ("value #3 › Lane Name"): by what the list holds ("Lane 3 › Lane Name");
- Street Brawl's per-round lists ("Buy Time #5"): "Buy Time, round 5" (m_StreetBrawl: one value per round);
- a hero's purchase bonus ("Vitality purchase bonus, tier 3: value"): the bonus is the value ("…, tier 3").
Cases with no clear words (a bare "value", "Companion Abilities #1 › Companion") are left alone."""
from __future__ import annotations

import re

# what the items of an entry's "value" list are, by the entry's id
LIST_NOUNS = {'m_LaneInfo': 'Lane', 'm_BreakableSpawnTimeDesc': 'Spawn group', 'm_vecSpiritGroups': 'Group',
              'm_vecArmorGroups': 'Group', 'm_vecWeaponGroups': 'Group'}
ROUND_LISTS = ('m_StreetBrawl',)            # entries whose lists hold one value per round
_VALUE_N = re.compile(r'^value #(\d+)(?= › |$)')
_ROUND_N = re.compile(r'^(?P<head>[^›#]+?) #(?P<n>\d+)$')
_PURCHASE = re.compile(r'^(?P<head>\w+ purchase bonus, tier [\d–-]+): value$')


def fixed_label(key: str, label: str) -> str:
    """The row's label in words (`key`: 'file:entity:path'); the label itself when there is nothing clear to say."""
    if not label:
        return label
    eid = key.split(':', 2)[1] if key.count(':') >= 2 else ''
    m = _VALUE_N.match(label)
    if m and eid in LIST_NOUNS:
        return f'{LIST_NOUNS[eid]} {m.group(1)}' + label[m.end():]
    if eid in ROUND_LISTS:
        m = _ROUND_N.match(label)
        if m:
            return f'{m.group("head")}, round {m.group("n")}'
    m = _PURCHASE.match(label)
    if m:
        return m.group('head')
    return label


def relabel(c: dict) -> dict:
    """`c` with its label in words — a copy when it changes, else `c` itself (`cards.player_facing` memoises on
    identity)."""
    label = str(c.get('label') or '')
    new = fixed_label(str(c.get('key') or ''), label)
    return c if new == label else {**c, 'label': new}
