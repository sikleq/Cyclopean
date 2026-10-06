"""Flag and enum fields a player plays with: which bits are gameplay, how they read, which way they go.

The engine's bit sets and enums were all dropped from the pages as plumbing (1,295 rows) and a modifier's
state mask was filed as technical (external-sites audit 0, coverage audit 5, 2026-10-04). Among them:
Hex-Lined Snap Trap became "ignored by NPC targeting" (a BUFF on deadlock-tracker), Grapple Arm learnt to
grab neutrals, Diviner's Kevlar moved from the Spirit to the Vitality shop, Borrowed Decree's curse became
unpurgeable, Air Drop's grab started to wear off on a target grabbed again. A bit listed here is such a
fact: (words, side when ADDED for the owner: +1 better, -1 worse, 0 no side — a disabling state on a
modifier can be the owner's own lockout or the enemy's debuff). A change whose bits are all unlisted
(quick-cast UI, preview radius, lag compensation, internal states) stays plumbing.

Polarity of numbers lives in semantics.py; this module is the same idea for bits.
"""
from __future__ import annotations

import re

from .semantics import SHOP_SLOT

_LEAF = re.compile(r'[\[{].*$')

# --- modifier states (MODIFIER_STATE_*): what holding the modifier means
STATES = {
    'INVULNERABLE': ('invulnerable', 1), 'UNKILLABLE': ('cannot die', 1), 'UNSTOPPABLE': ('unstoppable', 1),
    'STATUS_IMMUNE': ('immune to debuffs', 1), 'SLOW_IMMUNE': ('immune to slows', 1),
    'KNOCKDOWN_IMMUNE': ('immune to knockdowns', 1),
    'IGNORED_BY_NPC_TARGETING': ('ignored by troopers and neutrals', 1),
    'TECH_UNTARGETABLE': ('untargetable by spirit abilities', 1), 'IGNORE_BULLETS': ('immune to bullets', 1),
    'IGNORE_MELEE': ('immune to melee', 1), 'UNLIMITED_AIR_DASHES': ('unlimited air dashes', 1),
    # a lockout: the holder's own (while channelling, carrying the Urn) or an enemy's (a debuff)
    'DISARMED': ('disarmed', 0), 'SILENCED': ('silenced', 0), 'MUTED': ('items muted', 0),
    'SILENCE_MOVEMENT_ABILITES': ('movement abilities silenced', 0), 'STUNNED': ('stunned', 0),
    'IMMOBILIZED': ('rooted', 0), 'SLOWED': ('slowed', 0), 'IS_ASLEEP': ('asleep', 0), 'CHAINED': ('chained', 0),
    'GLITCHED': ('glitched', 0), 'COMMAND_RESTRICTED': ('controls locked', 0),
    'DASH_DISABLED': ('no dashing', 0), 'DASH_DISABLED_DEBUFF': ('no dashing', 0), 'JUMP_DISABLED': ('no jumping', 0),
    'AIR_JUMPS_DISABLED': ('no air jumps', 0), 'DUCKING_DISABLED': ('no crouching', 0),
    'MELEE_DISABLED': ('no melee', 0), 'MELEE_DISABLED_DEBUFF': ('no melee', 0),
    'ZIPLINE_DISABLED': ('no ziplines', 0), 'SLIDING_DISABLED': ('no sliding', 0),
    'MANTLE_DISABLED': ('no mantling', 0), 'TELEPORTER_DISABLED': ('no teleporters', 0),
    'MOVEMENT_ABILITY_RESTRICTED': ('movement abilities restricted', 0),
    'MOVEMENT_ABILITY_ACTIVATION_RESTRICTED': ('movement abilities restricted', 0),
    'PULLDOWN_TO_GROUND': ('pulled to the ground', 0), 'OUT_OF_GAME': ('out of the game', 0),
    'VISIBLE_TO_ENEMY': ('revealed to enemies', 0),
}
# --- the same states in a modifier's DISABLED mask: what the holder cannot be put into while it lasts. Nouns,
# under "Immune to": "Immune to +no dashing +disarmed" read as a double negative on Abrams, Yamato, Warden
# and Mirage (review 2026-10-04); an added one is always an immunity (FIELDS gives the side)
IMMUNITIES = {
    'SLOWED': 'slows', 'SILENCED': 'silence', 'SILENCE_MOVEMENT_ABILITES': 'movement silences',
    'MUTED': 'item mutes', 'DISARMED': 'disarm', 'GLITCHED': 'glitch', 'STUNNED': 'stuns', 'IMMOBILIZED': 'roots',
    'IS_ASLEEP': 'sleep', 'CHAINED': 'chains', 'COMMAND_RESTRICTED': 'control locks',
    'DASH_DISABLED': 'dash lockouts', 'DASH_DISABLED_DEBUFF': 'dash lockouts', 'JUMP_DISABLED': 'jump lockouts',
    'AIR_JUMPS_DISABLED': 'air-jump lockouts', 'DUCKING_DISABLED': 'crouch lockouts',
    'MELEE_DISABLED': 'melee lockouts', 'MELEE_DISABLED_DEBUFF': 'melee lockouts',
    'ZIPLINE_DISABLED': 'zipline lockouts', 'SLIDING_DISABLED': 'slide lockouts', 'MANTLE_DISABLED': 'mantle lockouts',
    'TELEPORTER_DISABLED': 'teleporter lockouts', 'MOVEMENT_ABILITY_RESTRICTED': 'movement restrictions',
    'MOVEMENT_ABILITY_ACTIVATION_RESTRICTED': 'movement restrictions', 'PULLDOWN_TO_GROUND': 'pull-downs',
}
# --- a modifier's rules (MODIFIER_ATTRIBUTE_*); MULTIPLE / PERMANENT are bookkeeping
ATTRIBUTES = {'CANNOT_BE_PURGED': ("can't be purged", 1), 'IGNORE_INVULNERABLE': ('ignores invulnerability', 1)}
# --- how an ability casts (CITADEL_ABILITY_BEHAVIOR_*); quick-cast UI, previews, camera, lag compensation
# and the deploy / projectile wiring are left out
BEHAVIOURS = {
    'DONT_INTERRUPT_SLIDE_ON_CAST': ("doesn't interrupt a slide", 1),
    'DONT_INTERRUPT_MELEE_ON_CAST': ("doesn't interrupt melee", 1),
    'INTERRUPT_MELEE_ON_CAST': ('interrupts your melee', -1),
    'CASTABLE_WHILE_BUSY': ('castable during other actions', 1),
    'CAN_CAST_ON_ZIPLINE': ('castable on ziplines', 1),
    'DONT_BREAK_INVISIBILITY': ("doesn't break invisibility", 1),
    'CANNOT_CANCEL_DURING_CHANNEL': ("channel can't be cancelled", -1),
    'CAN_CANCEL_DURING_CAST_DELAY': ('cancellable during the cast delay', 1),
    'DONT_TRIGGER_SPELL_BLOCK': ("doesn't trigger spell block", 1),
    'PROJECTILE_PASS_THROUGH_WORLD': ('passes through walls', 1),
    'ALLOW_SELF_CAST': ('self-cast', 1), 'ALLOW_ALT_CAST': ('alt-cast', 1),
    'CHANNELLED': ('channelled', 0), 'MOVEMENT': ('movement ability', 0),
}
TARGET_FLAGS = {'PENETRATE_INVULNERABLE': ('pierces invulnerability', 1),
                'ALLOW_SMALL_DEPLOYABLES': ('hits small deployables', 1)}

# field leaf -> (vocabulary, how an added bit counts: 'own' its own side, +1 / -1 every bit, 0 none)
FIELDS = {
    'm_nAbilityTargetTypes': ('target', 1),             # more kinds of target: better
    'm_iAuraSearchType': ('target', 0),                 # whom an aura touches: no side
    'm_bitsInterruptingStates': ('state', -1),          # interrupted by more states: worse
    'm_nEnabledStateMask': ('state', 'own'),
    'm_nDisabledStateMask': ('immunity', 1),            # states blocked while it lasts: an immunity
    'm_nAttributes': ('attribute', 'own'),
    'm_AbilityBehaviorsBits': ('behaviour', 'own'), 'm_nAbilityBehaviors': ('behaviour', 'own'),
    'm_nAbilityTargetFlags': ('targetflag', 'own'),
}
_PREFIX = {'state': 'MODIFIER_STATE_', 'immunity': 'MODIFIER_STATE_', 'attribute': 'MODIFIER_ATTRIBUTE_',
           'behaviour': 'CITADEL_ABILITY_BEHAVIOR_', 'target': 'CITADEL_UNIT_TARGET_',
           'targetflag': 'CITADEL_UNIT_TARGET_FLAG_'}
_VOCAB = {'state': STATES, 'immunity': {k: (w, 1) for k, w in IMMUNITIES.items()}, 'attribute': ATTRIBUTES,
          'behaviour': BEHAVIOURS, 'targetflag': TARGET_FLAGS}

# single-value enums: field leaf -> value pattern, words of its capture
ENUMS = {
    'm_eItemSlotType': re.compile(r'^EItemSlotType_(\w+)$'),
    'm_eAbilityActivation': re.compile(r'^CITADEL_ABILITY_ACTIVATION_(\w+)$'),
    'm_eAbilityTargetingShape': re.compile(r'^CITADEL_ABILITY_TARGETING_SHAPE_(\w+)$'),
    'm_eAbilityTargetingLocation': re.compile(r'^CITADEL_ABILITY_TARGETING_LOCATION_(\w+)$'),
}
# booleans: leaf -> side when it becomes true
BOOLS = {'m_bDurationReducibleByCrowdControlDiminish': -1}   # the owner's crowd control wears off sooner

_PLURAL = {'HERO': 'heroes', 'BOSS': 'bosses', 'TROPHY': 'trophies', 'ALL': 'everything', 'GOLD_ORBS': 'soul orbs',
           'ABILLITY_TRIGGER': 'ability triggers', 'BREAKABLE_PROP': 'breakable props'}

# CITADEL_UNIT_TARGET_TYPE as the game defines it (DumpSource2/schemas/client/CITADEL_UNIT_TARGET_TYPE.h): one bit a
# kind of unit on one side, the rest are unions. A set is compared bit by bit, so "ALL_ENEMY → HERO_FRIENDLY |
# HERO_ENEMY | TROOPER_ENEMY | … | CREEP_ENEMY" (Life Drain, 2024-10-11) is "+allied heroes", not "−all enemies"
# and nine "+…" chips (#22)
TARGET_BITS = {'HERO_FRIENDLY': 1, 'TROOPER_FRIENDLY': 2, 'BOSS_FRIENDLY': 4, 'BUILDING_FRIENDLY': 8,
               'PROP_FRIENDLY': 16, 'MINION_FRIENDLY': 32, 'GOLD_ORBS_FRIENDLY': 64, 'TROPHY_FRIENDLY': 128,
               'HERO_ENEMY': 256, 'TROOPER_ENEMY': 512, 'BOSS_ENEMY': 1024, 'BUILDING_ENEMY': 2048,
               'PROP_ENEMY': 4096, 'MINION_ENEMY': 8192, 'GOLD_ORBS_ENEMY': 16384, 'TROPHY_ENEMY': 32768,
               'NEUTRAL': 65536, 'ZIPLINE': 131072, 'BREAKABLE_PROP': 262144, 'ABILITY_TRIGGER': 524288}
# unions, widest first: a group of bits that moved together is said by its name
TARGET_UNIONS = (('ALL', 81727), ('ALL_ENEMY', 81664), ('CREEP', 67078), ('CREEP_ENEMY', 67072),
                 ('ALL_FRIENDLY', 63), ('GOLD_ORBS', 16448), ('TROPHY', 32896), ('MINION', 8224), ('PROP', 4112),
                 ('BUILDING', 2056), ('BOSS', 1028), ('TROOPER', 514), ('HERO', 257), ('CREEP_FRIENDLY', 6))
_TARGET_VALUE = {**TARGET_BITS, **dict(TARGET_UNIONS), 'DYNAMIC_PROP': 262144}
_TARGET_PREFIX = 'CITADEL_UNIT_TARGET_'


def target_bits(names: set[str]) -> set[str]:
    """A target set as single bits ('ALL_ENEMY' -> HERO_ENEMY, TROOPER_ENEMY, … NEUTRAL); a name the game's list does
    not hold (Valve's old 'ABILLITY_TRIGGER') stays as it is."""
    out = set()
    for n in names:
        v = _TARGET_VALUE.get(n.removeprefix(_TARGET_PREFIX)) if n.startswith(_TARGET_PREFIX) else None
        if v is None:
            out.add(n)
            continue
        out |= {_TARGET_PREFIX + b for b, x in TARGET_BITS.items() if v & x}
    return out


def target_groups(bits_: set[str]) -> set[str]:
    """Single bits that moved, a union's worth of them said by the union's name ("+all enemies")."""
    left = set(bits_)
    out = set()
    for name, v in TARGET_UNIONS:
        members = {_TARGET_PREFIX + b for b, x in TARGET_BITS.items() if v & x}
        if members <= left:
            out.add(_TARGET_PREFIX + name)
            left -= members
    return out | left


def leaf(path: str) -> str:
    return _LEAF.sub('', str(path or '').rsplit('.', 1)[-1])


def field(path: str) -> tuple[str, object] | None:
    return FIELDS.get(leaf(path))


def bits(v) -> set[str]:
    """'A | B' (or one bit) -> {'A', 'B'}; an absent side is no bits."""
    if v is None or isinstance(v, bool):
        return set()
    s = str(v).strip()
    if s in ('', '—'):
        return set()
    return {p.strip() for p in s.split('|') if p.strip()}


def _target_words(name: str) -> str:
    side = ''
    for suffix, word in (('_ENEMY', 'enemy '), ('_FRIENDLY', 'allied ')):
        if name.endswith(suffix) and name != 'ALL' + suffix:
            name, side = name[:-len(suffix)], word
    if name in ('ALL_ENEMY', 'ALL_FRIENDLY'):
        return 'all enemies' if name == 'ALL_ENEMY' else 'all allies'
    noun = _PLURAL.get(name) or name.lower().replace('_', ' ') + 's'
    return side + noun


def bit_words(kind: str, bit: str) -> tuple[str, int] | None:
    """(words, side when added) of a listed bit, None for an unlisted one."""
    name = bit.removeprefix(_PREFIX[kind])
    if kind == 'target':
        return (_target_words(name), 1) if bit.startswith(_PREFIX[kind]) and 'FLAG_' not in bit else None
    return _VOCAB[kind].get(name)


def diff(path: str, old, new) -> tuple[list[tuple[str, int]], list[tuple[str, int]]] | None:
    """(added, removed) listed bits of a flag field as (words, side for the owner); None when the path is
    not a flag field. Unlisted bits are left out."""
    f = field(path)
    if not f:
        return None
    kind, how = f
    a, b = bits(old), bits(new)
    if kind == 'target':
        a, b = target_bits(a), target_bits(b)

    def listed(names: set[str]) -> list[tuple[str, int]]:
        out = []
        for n in sorted(names):
            w = bit_words(kind, n)
            if w and all(w[0] != x for x, _ in out):
                out.append((w[0], w[1] if how == 'own' else int(how)))
        return out
    if kind == 'target':
        added, removed = listed(target_groups(b - a)), listed(target_groups(a - b))
    else:
        added, removed = listed(b - a), listed(a - b)
    # a bit renamed to one that reads the same (DASH_DISABLED -> DASH_DISABLED_DEBUFF) is no change
    same = {w for w, _ in added} & {w for w, _ in removed}
    return [x for x in added if x[0] not in same], [x for x in removed if x[0] not in same]


def enum_words(path: str, v) -> str | None:
    """'EItemSlotType_Tech' -> 'Spirit', 'CITADEL_ABILITY_ACTIVATION_INSTANT_CAST' -> 'instant cast'."""
    rx = ENUMS.get(leaf(path))
    m = rx.match(str(v)) if rx and v is not None else None
    if not m or _NO_VALUE.match(m.group(1)):
        return None           # EItemSlotType_Invalid: no slot, not a shop ("DEL Item slot invalid" on Viper)
    return SHOP_SLOT.get(m.group(1)) or m.group(1).replace('_', ' ').lower()


_NO_VALUE = re.compile(r'^(?:invalid|none|null|unset|count)$', re.I)


def enum_none(path: str, v) -> bool:
    """The enum's "no value" (CITADEL_ABILITY_TARGETING_LOCATION_NONE): a page prints "—", not the engine words
    ("unit → Ability Targeting Location None", review 2026-10-05)."""
    rx = ENUMS.get(leaf(path))
    m = rx.match(str(v)) if rx and v is not None else None
    return bool(m and _NO_VALUE.match(m.group(1)))


def _truthy(v) -> bool:
    return str(v).strip().lower() in ('true', '1', 'yes')


def is_gameplay(path: str, old, new) -> bool:
    """A flag / enum / boolean change a player plays with (a listed bit moved, a listed enum changed)."""
    d = diff(path, old, new)
    if d is not None:
        return bool(d[0] or d[1])
    lf = leaf(path)
    if lf in ENUMS:
        return enum_words(path, old) is not None or enum_words(path, new) is not None
    return lf in BOOLS


def is_flag_field(path: str) -> bool:
    lf = leaf(path)
    return lf in FIELDS or lf in ENUMS or lf in BOOLS


def direction(path: str, old, new) -> str | None:
    """'buff' / 'nerf' when every listed bit that moved goes one way for the owner, 'changed' when they
    disagree or have no side; None for a field that is not a flag field."""
    lf = leaf(path)
    if lf in BOOLS:
        a, b = _truthy(old), _truthy(new)
        if a == b:
            return 'changed'
        good = (b if BOOLS[lf] > 0 else a)
        return 'buff' if good else 'nerf'
    d = diff(path, old, new)
    if d is None:
        return None
    sides = {s for _, s in d[0]} | {-s for _, s in d[1]}
    sides.discard(0)
    if len(sides) == 1:
        return 'buff' if sides.pop() > 0 else 'nerf'
    return 'changed'
