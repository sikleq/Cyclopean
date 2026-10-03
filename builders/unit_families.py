"""Units that are one thing to a player (owner, 2026-10-03): "Slum Shroom I / II / III", the five Gutter
Ghouls of each tier, the four Walkers (alt, weak), the three Base Guardians (amber, sapphire). A family is
the units sharing a name once the tier numeral is dropped; it gets ONE card, ONE page (its main member's,
the others redirect there), ONE row in the change matrix. On the page each member is a group named by its
tier and what tells it apart; members whose changes in a patch are identical show as one group."""
from __future__ import annotations

import re
from collections import defaultdict

from .common import display_name

_TIER = re.compile(r'\s+(I{1,3}|IV|V)$')
TIER_RANK = {'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5}
_STOP = {'npc', 'neutral', 'citadel'}


def family_name(u: dict) -> str:
    """'Slum Shroom II' -> 'Slum Shroom'; a unit without a localized name is its own family."""
    return _TIER.sub('', display_name(u))


def tier_of(u: dict) -> str:
    m = _TIER.search(display_name(u))
    return m.group(1) if m else ''


def _variant_words(members: list[dict]) -> dict[str, str]:
    """What tells namesakes apart: the words of their id the others don't all share ('alt weak',
    'amber', 'dock creature'); tier words (weak / normal / strong) are the tier's, not the variant's."""
    toks = {u['id']: [w for w in u['id'].split('_') if w not in _STOP] for u in members}
    common = set.intersection(*(set(t) for t in toks.values())) if toks else set()
    tiers = {u['id']: tier_of(u) for u in members}
    out = {}
    for uid, t in toks.items():
        words = [w for w in t if w not in common and not (tiers[uid] and w in ('weak', 'normal', 'strong'))]
        out[uid] = ' '.join(f'model {int(w)}' if w.isdigit() else w for w in words)
    return out


def families(units: list[dict]) -> dict[str, list[dict]]:
    """family name -> members, the main one first: not an 'alt_' copy, the lowest tier, not a 'weak'
    copy of a boss (Walker before Walker weak), then by id. Removed units join their living namesakes."""
    by_name: dict[str, list[dict]] = defaultdict(list)
    for u in units:
        by_name[family_name(u)].append(u)

    def rank(u: dict) -> tuple:
        words = u['id'].split('_')
        return (not u.get('alive'), u['id'].startswith('alt_'), TIER_RANK.get(tier_of(u), 0),
                'weak' in words and not tier_of(u), u['id'])
    return {name: sorted(ms, key=rank) for name, ms in by_name.items()}


def member_label(u: dict, members: list[dict]) -> str:
    """'Tier II · dock creature', 'Tier I', 'alt weak' — or the family name for the main one alone."""
    words = _variant_words(members).get(u['id'], '') if len(members) > 1 else ''
    tier = tier_of(u)
    parts = ([f'Tier {tier}'] if tier else []) + ([words] if words else [])
    return ' · '.join(parts) or family_name(u)


def merged_label(labels: list[str], total: int = 0) -> str:
    """The header of members whose rows are identical in a patch: their common tier ('Tier I' for the five
    Gutter Ghouls I), 'All tiers' across tiers, 'All variants' when every member of `total` is in it
    (the four Walkers), else the labels themselves."""
    tiers = {lb.split(' · ')[0] for lb in labels}
    if len(tiers) == 1 and next(iter(tiers)).startswith('Tier '):
        return next(iter(tiers))
    if all(t.startswith('Tier ') for t in tiers):
        return 'All tiers'
    if total and len(labels) >= total:
        return 'All variants'
    return ' · '.join(dict.fromkeys(labels))


def main_of(units: list[dict]) -> dict[str, str]:
    """unit id -> its family's main unit id (its page)."""
    return {u['id']: ms[0]['id'] for ms in families(units).values() for u in ms}
