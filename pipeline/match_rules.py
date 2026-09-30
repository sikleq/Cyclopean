"""Matching rules learned from the audit of 'hidden' changes.

tests/fixtures/audit_verdicts.jsonl holds ~1000 judged changes; each rule
here closes one recurring miss (see docs/architecture.md, "Matching rules").
Score the effect with `python tools/audit_score.py`.
"""
from __future__ import annotations

import re

# ---- 4. words the notes use for units / objectives / rules that have internal ids ----
# note word -> [(file, entity id)]
ALIASES: dict[str, list[tuple[str, str]]] = {}


def _alias(words: tuple[str, ...], keys: list[tuple[str, str]]) -> None:
    for w in words:
        ALIASES[w] = keys


_alias(('guardian', 'guardians'), [('npc_units.vdata', 'npc_boss_tier1'), ('npc_units.vdata', 'alt_npc_boss_tier1'),
                                    ('generic_data.vdata', 'm_ObjectiveParams')])
_alias(('walker', 'walkers'), [('npc_units.vdata', 'npc_boss_tier2'), ('npc_units.vdata', 'alt_npc_boss_tier2'),
                                ('npc_units.vdata', 'npc_boss_tier2_weak'), ('npc_units.vdata', 'alt_npc_boss_tier2_weak'),
                                ('generic_data.vdata', 'm_ObjectiveParams'),
                                ('abilities.vdata', 'citadel_ability_tier2boss_stomp'),
                                ('abilities.vdata', 'citadel_ability_tier2boss_laser_beam'),
                                ('abilities.vdata', 'citadel_ability_tier2boss_rocket_barrage')])
_alias(('patron', 'patrons'), [('npc_units.vdata', 'npc_boss_tier3'), ('npc_units.vdata', 'alt_npc_boss_tier3')])
_alias(('base guardian', 'base guardians'), [('npc_units.vdata', 'npc_barrack_boss'),
                                              ('npc_units.vdata', 'npc_barrack_boss_amber'),
                                              ('npc_units.vdata', 'npc_barrack_boss_sapphire')])
_alias(('shrine', 'shrines'), [('npc_units.vdata', 'destroyable_building'), ('generic_data.vdata', 'm_ObjectiveParams')])
_alias(('mid boss', 'midboss', 'mid-boss'), [('npc_units.vdata', 'npc_super_neutral')])
_alias(('trooper', 'troopers'), [('npc_units.vdata', 'trooper_normal'), ('npc_units.vdata', 'trooper_medic'),
                                  ('npc_units.vdata', 'trooper_melee')])
_alias(('rejuvenator', 'rejuv'), [('generic_data.vdata', 'm_RejuvParams'), ('misc.vdata', 'citadel_item_pickup_rejuv'),
                                  ('npc_units.vdata', 'citadel_item_pickup_rejuv')])
_alias(('soul urn', 'urn'), [('generic_data.vdata', 'm_IdolParams'), ('abilities.vdata', 'ability_golden_idol'),
                              ('misc.vdata', 'citadel_idol_cashin'), ('misc.vdata', 'citadel_item_pickup_idol'),
                              ('misc.vdata', 'xp_orb_idol_dropoff')])
_alias(('neutral', 'neutrals', 'camps', 'jungle'), [('npc_units.vdata', 'neutral_trooper_weak'),
                                                    ('npc_units.vdata', 'neutral_trooper_normal'),
                                                    ('npc_units.vdata', 'neutral_trooper_strong'),
                                                    ('misc.vdata', 'neutral_camp_weak'),
                                                    ('misc.vdata', 'neutral_camp_medium'),
                                                    ('misc.vdata', 'neutral_camp_strong')])
_alias(('golden statue', 'golden statues', 'statue', 'statues'),
       [('misc.vdata', f'{kind}_permanent_pickup{lv}') for kind in ('hp', 'cd', 'ammo', 'bulletresist', 'techresist',
                                                                    'spirit', 'weapon', 'firerate', 'movespeed')
        for lv in ('', '_lv2', '_lv3')])
_alias(('dash', 'dashes'), [('abilities.vdata', 'citadel_ability_dash')])
_alias(('jump', 'dash jump'), [('abilities.vdata', 'citadel_ability_jump')])
_alias(('slide', 'sliding'), [('abilities.vdata', 'citadel_ability_slide')])
_alias(('melee', 'parry'), [('abilities.vdata', 'citadel_ability_melee_parry')])


def alias_keys(text: str) -> set[str]:
    low = text.lower()
    out = set()
    for word, keys in ALIASES.items():
        if re.search(rf'\b{re.escape(word)}\b', low):
            out |= {f'{f}:{i}' for f, i in keys} | {f'{f}:{i}_herotest' for f, i in keys}
    return out


def name_variants(name: str) -> set[str]:
    """'The Doorman' / 'Doorman', 'Mo & Krill' / 'Mo and Krill'."""
    n = name.strip().lower()
    out = {n, n.replace('&', 'and'), n.replace(' and ', ' & ')}
    if n.startswith('the '):
        out.add(n[4:])
    return {x for x in out if x}


# ---- 5. label synonyms: words the notes use for a property ----
LABEL_SYNONYMS = {
    'resist': {'armor', 'resistance'}, 'armor': {'resist'}, 'radius': {'range', 'aoe', 'area'},
    'range': {'radius'}, 'multiplier': {'range'}, 'chargeup': {'cooldown'}, 'cooldown': {'cd'},
    'shock': {'chain'}, 'lifesteal': {'heal', 'healing'}, 'heal': {'healing', 'lifesteal'},
    'duration': {'time'}, 'charges': {'charge'}, 'barrier': {'shield'}, 'speed': {'velocity'},
    'velocity': {'speed'}, 'souls': {'bounty', 'gold'}, 'gold': {'souls', 'bounty'},
}


def expand_label_words(ws: set[str]) -> set[str]:
    out = set(ws)
    for w in ws:
        out |= LABEL_SYNONYMS.get(w, set())
    return out


# ---- 1. global lines: "All ultimates' cooldowns increased by 15%" ----
GROUND_DASH = re.compile(r'GroundDash', re.I)
PROP_FAMILIES: tuple[tuple[re.Pattern, re.Pattern, bool], ...] = (
    # (line pattern, field path pattern, needs "all/global/every")
    (re.compile(r'dash slows?|ground dash'), GROUND_DASH, True),
    (re.compile(r'\bslows?\b'), re.compile(r'Slow', re.I), True),
    (re.compile(r'health per boon|hp per boon'), re.compile(r'BASE_HEALTH_FROM_LEVEL'), False),
    # "Base gun damage and gun damage growth increased by 10%" is global without saying "all"
    (re.compile(r'\b(gun|weapon|bullet) damage\b'), re.compile(r'm_flBulletDamage|BULLET_DAMAGE_FROM_LEVEL'), False),
    (re.compile(r'\b(spirit|ability|ap) damage\b'), re.compile(r'Damage|DPS', re.I), True),
    (re.compile(r'\bcooldowns?\b'), re.compile(r'Cooldown(?!BetweenCharge)|ChargeUpTime', re.I), True),
    (re.compile(r'\bdurations?\b'), re.compile(r'Duration', re.I), True),
    (re.compile(r'investment'), re.compile(r'm_MapModCostBonuses'), False),
    (re.compile(r'\b(boon|level)s? at\b|\bextra (boon|level)\b|\blevels? (at|to)\b'), re.compile(r'm_mapLevelInfo'), False),
    (re.compile(r'\bbount(y|ies)\b'), re.compile(r'Gold|Bounty|Reward|Souls', re.I), True),
    (re.compile(r'respawn'), re.compile(r'spawn_time|Respawn', re.I), False),
)
SCOPES: tuple[tuple[re.Pattern, object], ...] = (
    # scope(entity, change) -> bool; the first matching pattern wins.
    # "AP upgrades" are the ability-point tier upgrades (T1-T3), not shop items.
    (re.compile(r'\bap\b.{0,20}\bupgrades?\b|\babilit(y|ies) upgrades?\b|\btier upgrades?\b'),
     lambda e, c: 'm_vecAbilityUpgrades' in c.path),
    (re.compile(r'\bultimates?\b'), lambda e, c: e.get('ability_slot') == 'Signature_4'),
    (re.compile(r'\b(items?|upgrades?)\b'), lambda e, c: e.get('kind') == 'item'),
    (re.compile(r'\babilit(y|ies)\b'), lambda e, c: e.get('kind') == 'ability'),
    (re.compile(r'\bheroes\b'), lambda e, c: e.get('kind') in ('hero', 'ability', 'weapon')),
)
_PCT = re.compile(r'(increased|reduced|decreased|lowered|raised|by)\D{0,12}?~?(\d+(?:\.\d+)?)\s*%', re.I)
_GLOBAL = re.compile(r'\b(all|every|global(ly)?|across the board)\b', re.I)


_ROUNDING = re.compile(r'nearest (multiple of )?(\d+(?:\.\d+)?)', re.I)


def ratio_ok(old, new, pct: float, sign: int, num, unit: float = 1.0) -> bool:
    o, n = num(old), num(new)
    if o in (None, 0) or n is None:
        return False
    r = abs(n) / abs(o)
    targets = [1 + pct / 100, 1 - pct / 100] if sign == 0 else [1 + sign * pct / 100]
    # "~20%" and rounded values: 3.5 points, or half a rounding unit ("nearest multiple of 5")
    tol = max(0.035, (unit / 2 + 0.01) / abs(o))
    return any(abs(r - t) <= tol for t in targets)


def global_line(text: str, changes: list, cat: dict, num) -> list | None:
    """Changes covered by a global line, or None when the line is not global."""
    low = text.lower()
    for line_re, path_re, needs_global in PROP_FAMILIES:
        if not line_re.search(low):
            continue
        if needs_global and not _GLOBAL.search(low):
            return None
        scope = next((f for rx, f in SCOPES if rx.search(low)), None)
        m = _PCT.search(low)
        pct = float(m.group(2)) if m else None
        verb = m.group(1).lower() if m else ''
        sign = 1 if verb in ('increased', 'raised') else -1 if verb in ('reduced', 'decreased', 'lowered') else 0
        rm = _ROUNDING.search(low)
        unit = float(rm.group(2)) if rm else 1.0
        out = []
        for c in changes:
            if c.cat != 'balance' or not path_re.search(c.path):
                continue
            if path_re.pattern == 'Slow' and GROUND_DASH.search(c.path):
                continue
            if scope is not None and not scope(cat.get(f'{c.file}:{c.eid}', {}), c):
                continue
            if pct is not None and not any(ratio_ok(o, n, pct, sign, num, unit) for o, n in c.steps()):
                continue
            out.append(c)
        return out or None
    return None


# ---- 2. components: "Now builds from Sprint Boots" ----
COMPONENT_RE = re.compile(r'builds? (from|into)|no longer builds|component', re.I)
AFFECTS_UPGRADES_RE = re.compile(r'affects? (its )?upgrades', re.I)

# ---- 7. one line = one feature = many fields ----
_CAMEL = re.compile(r'^m_[a-z]*((?:[A-Z][a-z0-9]+){1,3})')


def cluster_root(path: str) -> str:
    """Fields that belong to one feature: same top-level block, or for top-level
    scalars the same leading words (m_flParryCancelAirGlideDuration -> ParryCancelAir)."""
    first = path.split('.', 1)[0]
    if first == 'm_mapAbilityProperties':
        return '.'.join(path.split('.')[:2])
    if '.' in path or '{' in first or '[' in first:
        return re.sub(r'[\[{].*$', '', first)
    m = _CAMEL.match(path)
    return m.group(1) if m else path
