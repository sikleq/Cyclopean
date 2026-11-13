"""The rules that turn a patch's change rows into the rows a player reads: renamed and moved fields merged
(`merge_renames`), engine plumbing (`is_engine`) and no-ops (`is_noop`) out, levels combined (`combine_levels`),
repeated variants merged (`gameplay_entities`) and THE counting rule (`player_facing`, memoised)."""
from __future__ import annotations

import difflib
import re
from contextlib import contextmanager

from pipeline import flags as flag_rules
from pipeline.semantics import TIER_PREFIX, UNITS_PER_METER

from .brawl import gameplay_rows
from .render import HIDDEN_LIKE, _sentinel, fold_tier_swaps, fold_versions, folded_source, shown_value


# engine plumbing that reached a gameplay category: '{}' blocks, ENUM_CONSTANTS, ETypeNames
_ENGINE_VALUE = re.compile(r'^\{\}$|^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$|^E[A-Z][a-zA-Z]+(?:_[A-Za-z]+)*$')


# "Viewer Souls Class › 0 weak_to_viewer": how a neutral's souls show to spectators (2026-10-03)
_ENGINE_LABEL = re.compile(r'\b(scaling stats|roster|layout|background|css|panel|particle|viewer)\b', re.I)


def merge_renames(changes: list[dict]) -> list[dict]:
    """A field re-keyed between builds arrives as DEL + NEW with the same label ('Hit Speed
    80' removed, 'Hit Speed 78.74' added): one CHANGED row 80 -> 78.74. Also under a label that only
    names it more or less precisely (`_renamed_add`)."""
    adds = {}
    for c in changes:
        if c.get('op') == 'add':
            adds.setdefault(_rename_key(c.get('label')), []).append(c)
    if not adds:
        return _merge_moves(list(changes))
    added = [a for g in adds.values() for a in g]
    out, used = [], set()
    for c in changes:
        pool = adds.get(_rename_key(c.get('label'))) if c.get('op') == 'remove' else None
        # another property with another unit is a replaced bonus, not a re-key: Shoulder Charge's T1 lost
        # "+25% weapon damage" and gained a flat "+2.2" — one row "25% → 2.2" read as a −91% nerf
        # (Sloppy reference audit 2026-10-04)
        pool = [a for a in pool or ()
                if _prop_of(a) == _prop_of(c) or _unit_of(a.get('new_s')) == _unit_of(c.get('old_s'))]
        a = pool[0] if pool else _renamed_add(c, added, used) if c.get('op') == 'remove' else None
        if a is not None:
            adds[_rename_key(a.get('label'))].remove(a)
            used.add(id(a))
            merged = _moved(c, a)
            if merged is not None:
                out.append(merged)
            continue
        out.append(c)
    return _merge_moves([c for c in out if id(c) not in used])


def _moved(gone: dict, came: dict) -> dict | None:
    """One CHANGED row for a value that left one field (`gone`, its old value) and arrived in another (`came`, its
    new value) — None when it is the same value (a re-key, a length now in metres, a share now a percent)."""
    x, y = _num(gone.get('old_s', gone.get('old'))), _num(came.get('new_s', came.get('new')))
    if _same_shown(gone.get('old_s'), came.get('new_s')) or _same_value(gone.get('old_s'), came.get('new_s'), gone, came) \
            or (x is not None and y is not None and (x == y or abs(x / UNITS_PER_METER - y) < 0.01)):
        return None
    # the builds both halves shipped in ride along (render.folded_source): the eye's link opens the right build
    merged = {**came, **folded_source([gone, came]), 'op': 'change', 'old_s': gone.get('old_s'), 'old': gone.get('old'),
              'status': min((came.get('status', 'hidden'), gone.get('status', 'hidden')),
                            key=lambda s: s not in HIDDEN_LIKE)}
    if x is not None and y is not None:
        # the NEW row carried dir='changed': judge the pair like any other change — a unit's or a game object's as
        # UP / DOWN, as its other rows (#43.4: a re-keyed trooper field read BUFF on a unit page)
        from pipeline.semantics import direction, gradient
        d, pct = direction(str(came.get('path', '')), x, y, 'unit' if _unit_side(gone, came) else '')
        merged.update(dir=d, pct=pct, grad=gradient(pct))
    return merged


# files whose entries enrich judges with no owner side (semantics.SHARED_KINDS: units, map objects, game rules); an
# effect (modifiers.vdata) keeps BUFF / NERF there
_UNIT_FILES = ('npc_units.vdata', 'misc.vdata', 'generic_data.vdata', 'loot_tables.vdata')


def _unit_side(*rows: dict) -> bool:
    """The rows are a unit's or a game object's (no owner side): by their file, or a sibling row judged UP / DOWN
    (an NPC's ability)."""
    return any(str(r.get('key') or '').split(':', 1)[0] in _UNIT_FILES or r.get('dir') in ('up', 'down') for r in rows)


_ZERO = re.compile(r'^\s*[-+]?0(?:\.0+)?\s*(?:m/s|m|s|%)?\s*$')


def _leaves(c: dict) -> bool:
    return c.get('op') == 'remove' or (c.get('op') == 'change' and bool(_ZERO.match(str(c.get('new_s') or ''))))


def _arrives(c: dict) -> bool:
    return c.get('op') == 'add' or (c.get('op') == 'change' and bool(_ZERO.match(str(c.get('old_s') or ''))))


def _entity_of(c: dict) -> str:
    return ':'.join(str(c.get('key') or '').split(':', 2)[:2])


def _merge_moves(rows: list[dict]) -> list[dict]:
    """A stat that moved to another field of the same name, one side through 0: Thermal Detonator's "Spirit Power"
    left TechPower (7 → 0) for SpiritPower (— → 8), Headshot Booster's "Cooldown" left HeadShotCooldown (5s → —)
    for AbilityCooldown (0s → 7s) — two rows "· old field / · new field" (#12.8; 15 pairs over all patches). One
    CHANGED row 7 → 8 (none when the value is the same). Only one leaving and one arriving row under the label, in
    one unit, never a T1-T3 / Enhanced bonus (a bonus moved to another property is a tier swap, `fold_tier_swaps`)."""
    by: dict[str, tuple[list[dict], list[dict]]] = {}
    for c in rows:
        label = _rename_key(c.get('label'))
        if not label or TIER_PREFIX.match(label):
            continue
        gone, came = by.setdefault(label, ([], []))
        if _leaves(c) and not _arrives(c):
            gone.append(c)
        elif _arrives(c) and not _leaves(c):
            came.append(c)
    pairs: dict[int, dict | None] = {}
    for gone, came in by.values():
        if len(gone) != 1 or len(came) != 1:
            continue
        g, a = gone[0], came[0]
        if g.get('path') == a.get('path') or 'change' not in (g.get('op'), a.get('op')):
            continue                # remove + add is merge_renames' own; this is a field set to / from 0
        if not _entity_of(g) or _entity_of(g) != _entity_of(a):
            continue                # rows of two entities (or with no key: a build page's card) are never one stat
        if _unit_of(g.get('old_s')) != _unit_of(a.get('new_s')) and not _same_value(g.get('old_s'), a.get('new_s'), g, a):
            continue
        pairs[id(g)] = None
        pairs[id(a)] = _moved(g, a)
    if not pairs:
        return rows
    out = (pairs.get(id(c), c) for c in rows)
    return [c for c in out if c is not None]


def _rename_key(label) -> str:
    """'Pickup Radius' and 'Pickup Radius › Base' are one field moved into a sub-block."""
    return str(label or '').removesuffix(' › Base')


_LABEL_WORD = re.compile(r'[a-z0-9]+')


_LABEL_DIGITS = re.compile(r'\d+')


_LETTERS = re.compile(r'[^a-z]+')


RENAME_RATIO = 0.75         # name likeness of a re-key with the same value ("Interupt" -> "Interrupt": 0.97)


RENAME_RATIO_CHANGED = 0.9  # … and of one whose value moved too: only a respelling (`_respelt`)


# a property name that is a real property (an ability property or a T1-T3 bonus of one): one name inside
# the other is the same property ("FlameAuraDPS" / "DPS"); a bare engine leaf (m_value, m_flValue,
# eScaleStat) names nothing and matched unrelated stats (data-quality review 2026-10-04)
_PROP_PATH = re.compile(r'm_mapAbilityProperties\.|m_vecPropertyUpgrades\{')


def _words(label: str) -> set[str]:
    """A label's words, singular, without 'modifier' (a container's name for itself)."""
    ws = {w[:-1] if len(w) > 3 and w.endswith('s') else w for w in _LABEL_WORD.findall(label.lower())}
    return ws - {'modifier'}


def _last_seg(label: str) -> str:
    return label.rsplit('›', 1)[-1].strip().lower()


def _same_shown(a, b) -> bool:
    a, b = str(a or '').strip(), str(b or '').strip()
    return bool(a) and a not in ('—',) and a == b


def _alike(r: dict, a: dict, ratio: float) -> float:
    """How surely an added field is a removed one renamed (0 = not): its label names it more or less
    precisely ("Grab › Follow Damping Factor" → "Grab › Damping Factor", "Projectile › Vertical Aim Bias"
    → "Vertical Aim Bias", "Zip Speed" → "Zip Speed Inner"), is the same words respelt ("Interupt
    Cooldown", "Slow Resist" → "Slow Resistance") or its field name holds the other's (FlameAuraDPS →
    DPS: "DPS" → "Damage Per Second"). Not another stat of the same kind ("Spirit Resist" → "Bullet
    Resist", "Sprint Speed" → "Move Speed": real swaps, data-quality audit 2026-10-04)."""
    lr, la = str(r.get('label') or ''), str(a.get('label') or '')
    hr, ha = TIER_PREFIX.match(lr), TIER_PREFIX.match(la)
    if (hr.group(1) if hr else '') != (ha.group(1) if ha else ''):
        return 0.0                          # a T1 bonus is not a T2 one
    lr, la = lr[hr.end():] if hr else lr, la[ha.end():] if ha else la
    if _LABEL_DIGITS.findall(lr) != _LABEL_DIGITS.findall(la):
        return 0.0                          # "at 9,600 souls" is not "at 6,400 souls", "#1" not "#5"
    if ratio > RENAME_RATIO:
        return _respelt(lr, la)
    sm = difflib.SequenceMatcher(None, _last_seg(lr), _last_seg(la))
    if sm.real_quick_ratio() >= ratio and sm.quick_ratio() >= ratio:       # cheap upper bounds first
        best = sm.ratio()
        if best >= ratio:
            return best
    wr, wa = _words(lr), _words(la)
    if wr and wa and (wr <= wa or wa <= wr):
        return 0.7
    if _PROP_PATH.search(str(r.get('path') or '')) and _PROP_PATH.search(str(a.get('path') or '')):
        pr, pa = _prop_of(r).lower(), _prop_of(a).lower()
        if min(len(pr), len(pa)) >= 3 and (pr in pa or pa in pr):
            return 0.6
    return 0.0


def _respelt(lr: str, la: str) -> float:
    """How surely two labels are one name respelt ("Interupt Cooldown" → "Interrupt Cooldown"): as many
    words and the letters ≥ RENAME_RATIO_CHANGED alike. A word more or less is another field ("Damage
    Taken (spirit scaling)" → "Damage (spirit scaling)", "Wall Turn Ratio" → "… Max", "Horizontal
    Speed" → "… Speed X"), and so is another word in its place ("Spirit Damage" → "Base Damage"):
    paired with a new value they invented a BUFF / NERF with a made-up percent (review 2026-10-04)."""
    if len(_LABEL_WORD.findall(lr.lower())) != len(_LABEL_WORD.findall(la.lower())):
        return 0.0
    a, b = _LETTERS.sub('', lr.lower()), _LETTERS.sub('', la.lower())
    if not a or not b:
        return 0.0
    sm = difflib.SequenceMatcher(None, a, b)
    if sm.real_quick_ratio() < RENAME_RATIO_CHANGED or sm.quick_ratio() < RENAME_RATIO_CHANGED:
        return 0.0
    s = sm.ratio()
    return s if s >= RENAME_RATIO_CHANGED else 0.0


def _renamed_add(r: dict, added: list[dict], used: set[int]) -> dict | None:
    """The NEW row of the same entity that is this DEL row's field renamed: the same value under an alike
    name (`_alike`), or a respelt name with a new value (one CHANGED row). 73 such pairs read DEL + NEW,
    ~12 of them as a tier REWORK ("T2 upgrade: DPS 40 → Damage Per Second 40"; data-quality audit
    2026-10-04)."""
    ent = ':'.join(str(r.get('key') or '').split(':', 2)[:2])
    if not ent:
        return None                         # a build page's card mixes an entity's parts: no key, no guess
    best, score = None, 0.0
    for a in added:
        if id(a) in used or not str(a.get('key') or '').startswith(ent + ':'):
            continue
        x, y = _num(r.get('old_s')), _num(a.get('new_s'))
        same = _same_value(r.get('old_s'), a.get('new_s'), r, a)
        if not same and (_unit_of(r.get('old_s')) != _unit_of(a.get('new_s')) or x is None or y is None):
            continue
        s = _alike(r, a, RENAME_RATIO if same else RENAME_RATIO_CHANGED)
        if s > score:
            best, score = a, s
    return best


_PCT_NAME = re.compile(r'percent|pct', re.I)


def _same_value(old_s, new_s, r: dict, a: dict) -> bool:
    """A removed and an added value that are one value: shown alike, or one number in units that agree.
    A bare number and a percent are one only when the bare field's name says percent (Inhibitor's
    "…Damage Penalty Percent -35" → "Damage Penalty -35%"), or at 0: Blood Bomb's flat "Self Damage
    30" → "Health Cost 30%" (SelfDamagePct) is another cost, it read as no change (review 2026-10-04)."""
    if _same_shown(old_s, new_s):
        return True
    x, y = _num(old_s), _num(new_s)
    if x is None or y is None:
        return False
    ur, ua = _unit_of(old_s), _unit_of(new_s)
    if x != y and {ur, ua} == {'', '%'}:
        # a share written as a fraction in one field and as a percent in its "…Pct" successor: Mo & Krill's
        # "Non Player Resource Scale 0.35" → "35%" (NonPlayerResourceScalePct) is one value
        frac, pct, row = (x, y, a) if ua == '%' else (y, x, r)
        return 0 < abs(frac) <= 1 and abs(frac * 100 - pct) < 1e-6 and bool(_PCT_NAME.search(_prop_of(row)))
    if x != y:
        return False
    if x == 0 or ur == ua or '%' not in (ur, ua):
        return True
    return bool(_PCT_NAME.search(_prop_of(r if ur != '%' else a)))


_NUM = re.compile(r'^\s*([-+]?\d*\.?\d+)\s*(m|s|%)?\s*$')


_UNIT_OF = re.compile(r'^\s*[-+−]?\d*\.?\d+\s*(m/s|m|s|%)?\s*$')


def _unit_of(v) -> str | None:
    """'25%' -> '%', '2.2' -> '', 'yes' -> None (not a number)."""
    m = _UNIT_OF.match(str(v)) if v is not None else None
    return (m.group(1) or '') if m else None


def _num(v) -> float | None:
    m = _NUM.match(str(v)) if v is not None else None
    return float(m.group(1)) if m else None


# the engine's own vocabulary in a value: flag sets "A | B", projectile flags PBF_*, k_e* enums, bone
# names (advisor, 2026-10-03: 452 "Behaviour" rows, 97 pellet offsets, Walker's weak-point joints)
_ENGINE_TOKENS = re.compile(r'^[A-Z][A-Z0-9_]+(?:\s*\|\s*[A-Z][A-Z0-9_]+)+$|\bPBF_\w+|\bk_e[A-Z]\w+|\bjoint_\w+')


_ENGINE_PATH = re.compile(r'm_vecWeakPoints\{[^}]*\}\.m_strName')


# a shotgun's pellet offsets, one "x, y" row per pellet: unreadable even when a note describes the new
# pattern (37 "Scatter Offsets[n]" rows stayed as "described", audit 2026-10-04) — the line says it
_PELLETS = re.compile(r'm_vecScatterOffsets')


# a property's own wiring: its scale function's switches (not the coefficient m_flStatScale), how its
# value is typed and registered ("Cooldown · Function Disabled", "Spirit Lifesteal · Automatically Deduce
# Provided Property Type From Name" — 2026-10-03, the namesake audit). Never what a note line talks
# about, even on a property the notes changed.
_PROPERTY_WIRING = re.compile(r'\.m_subclassScaleFunction(?!\.m_flStatScale)(?:\.|$)'
                              r'|\.m_(?:bAutomaticallyDeduceProvidedPropertyTypeFromName|eProvidedPropertyType|'
                              # which upgrade bits a property waits for: "Weapon Damage Per Kill · Required
                              # Upgrade Bits — → —" on Assassinate, Borrowed Decree, Combo (2026-09-29)
                              r'eStatsUsageFlags|nRequiredUpgradeBits)$')


# a unit's AI wiring (advisor round 3, 2026-10-03: a new Gutter Ghoul's page was mostly these); its
# health, damage, range, speed, bounty, resists and abilities stay
_NPC_AI_LABEL = re.compile(r'^(?:Attack Range Target|Non Move Attack Duration|Cap Simultan|Face Enemy While Idle|'
                           r'Npc Aiming Spread|Weak Point (?:Count|Respawn Time)|Ability Chance\s*\d|Sweep|Model Scale|'
                           r'Jump Up Base Cost|Track Out Of Combat|Melee Attack Points)', re.I)


NOTED = ('documented', 'described', 'rounded', 'mismatch')


# fields that only wire a modifier or a model, in any file (data-quality audit 2026-10-04: "Passive › Is For
# Mid Boss", "Buildup Affected By Effectiveness", "Dependent Abilities › ability ice dome trigger", "Model
# Scale", the Patron's "Observer Origin"); what the notes talked about stays
_PLUMBING_PATH = re.compile(
    r'\.m_b(?:IsForMidBoss|KeepMaximumDurationOnRefresh|DurationAffectedByEffectiveness|DurationCanBeTimeScaled|'
    r'BuildupAffectedByEffectiveness|IsBuildup|RequiresTargetFilter|EndCreatedSequenceOnRemove|'
    r'RemoveProvidedModifierOnAuraRemoval|NetworkValuesForStatsPreview)$'
    r'|^m_mapDependentAbilities\.|(?:^|\.)m_fl(?:Preview)?ModelScale$|Observer(?:Origin|Pitch)$|^m_deploymentInfo\.m_b'
    # which property a regen reads, and a property block's wait for an upgrade (review 2026-10-05: "Ability
    # Properties Block #1 › Ability Properties BonusBulletSpeedPercent › Requires Ability Upgrade yes → —")
    r'|m_strRegenAbilityPropertyName$|AbilityPropertiesBlock.*\.m_bRequiresAbilityUpgrade$')


def is_engine(c: dict) -> bool:
    if c.get('cat') == 'availability':      # "Pre Release", "Disabled": never plumbing
        return False
    path = str(c.get('path') or '')
    if flag_rules.is_flag_field(path):
        # a bit set / enum / switch: shown when a bit a player plays with moved ("Can target: + neutrals",
        # "Item slot: Spirit → Vitality"), plumbing when only quick-cast UI or internal states did
        return not flag_rules.is_gameplay(path, c.get('old_s'), c.get('new_s'))
    vals = [str(c.get(k) or '').strip() for k in ('old_s', 'new_s')]
    vals = [v for v in vals if v and v != '—']
    if bool(vals) and all(_ENGINE_VALUE.match(v) for v in vals) or bool(_ENGINE_LABEL.search(str(c.get('label')))):
        return True
    if _PROPERTY_WIRING.search(path) or _PELLETS.search(path):
        return True
    # what the notes talked about stays, however it is spelled in the files ("No longer interrupts sliding")
    if c.get('status') in NOTED:
        return False
    if _PLUMBING_PATH.search(path):
        return True
    if str(c.get('file') or c.get('key') or '').startswith('npc_units.vdata') and _NPC_AI_LABEL.match(str(c.get('label') or '')):
        return True
    return bool(_ENGINE_PATH.search(str(c.get('path') or ''))) or (
        bool(vals) and any(_ENGINE_TOKENS.search(v) for v in vals))


def merge_variants(ents: list[dict]) -> list[dict]:
    """One object kept under several ids (Walker: alt_npc_boss_tier2, npc_boss_tier2, their _weak
    copies; two crate ids) gets the same edit in each: one card 'Walker · 4 variants' (audit
    2026-10-01: a third of CHANGED rows were such repeats). Heroes and unnamed ids never merge."""
    groups: dict[tuple, list[dict]] = {}
    order: list[tuple] = []
    for e in ents:
        name = e.get('name')
        if e['file'] == 'heroes.vdata' or e.get('id') == '@shared' or not name or name == e.get('id'):
            key: tuple = ('solo', id(e))
        else:
            key = (e['file'], name, frozenset((c.get('path'), c.get('op'), str(c.get('old_s')), str(c.get('new_s')))
                                              for c in e['changes']))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(e)
    out = []
    for key in order:
        g = groups[key]
        out.append(g[0] if len(g) == 1 else {**g[0], 'variants': [x['id'] for x in g]})
    return out


def gameplay_entities(entities: list[dict]) -> list[dict]:
    """A patch's entities as players read them: gameplay rows only, repeated variants merged.
    Every page that lists or counts a patch's changes starts here (one rule, same numbers)."""
    out = []
    for e in entities:
        ch = gameplay_rows(e['changes'])
        if ch:
            out.append({**e, 'changes': ch})
    return merge_variants(out)


_FACING: dict[tuple[int, ...], tuple[list[dict], list[dict]]] = {}


FACING_CACHE_MAX = 100_000      # entries before the memo starts over (a build makes ~25k)


def player_facing(changes: list[dict]) -> list[dict]:
    """The rows a player reads, which is what EVERY counter counts (home summary, patches index,
    heroes index, card headers, history bands): renames merged, replaced tiers folded into one
    REWORK, engine plumbing out. Folding works per entity (a hero card mixes its abilities).

    Memoised on the identity of the change dicts: the same patch's rows went through it 9 times a build
    (95k calls on 10k inputs, python audit 2026-10-04). The memo keeps the inputs alive, so an id is never
    reused while its entry exists; the change dicts are never written into after they are read (the patch
    archive is shared, builders/archive.py). A caller gets its own list."""
    key = tuple(map(id, changes))
    hit = _FACING.get(key)
    if hit is None:
        if len(_FACING) >= FACING_CACHE_MAX:
            _FACING.clear()
        hit = _FACING[key] = (list(changes), _player_facing(changes))
    return list(hit[1])


@contextmanager
def facing_scope():
    """A memo of its own for rows read once (a build page's record): they do not outlive the page, and the
    archive's entries stay."""
    global _FACING
    saved, _FACING = _FACING, {}
    try:
        yield
    finally:
        _FACING = saved


def _player_facing(changes: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for c in changes:
        groups.setdefault(':'.join(str(c.get('key') or '').split(':', 2)[:2]), []).append(c)
    return [c for g in groups.values() for c in combine_levels(fold_tier_swaps(fold_versions(merge_renames(g))))
            if not is_engine(c) and not is_noop(c)]


_ZERO_RE = re.compile(r'^[+-]?0(?:\.0+)?\s*(?:m|s|%|m/s|x|u)?$')


# signs are kept: "−22% → 22%" is a change (11 sign flips were dropped from every page and counter,
# python audit 2026-10-04); a flip that is only the value written the other way round arrives with
# 'same' from the pipeline (match.mark_retyped)
_NOT_WORD = re.compile(r'[^a-z0-9.+\-]')


def _same(a: str, b: str) -> bool:
    """Equal up to case, spaces and underscores: 'Head Ignore Obscure Blockers' is
    'Head_IgnoreObscureBlockers' (one enum spelled two ways across builds). Not up to the sign."""
    a, b = a.replace('−', '-'), b.replace('−', '-')
    return a == b or _NOT_WORD.sub('', a.lower()) == _NOT_WORD.sub('', b.lower())


def is_noop(c: dict) -> bool:
    """'1.5 → 1.5': the shown values are equal (a re-keyed or re-typed field), nothing to read.
    A field added or removed with a zero / "no" value changes nothing either: the patch window's
    final value decides (Sleep Dagger's "Explosion Radius 0" NEW in City Never Sleeps was a field
    tuned to 0 within the window)."""
    op = c.get('op')
    if c.get('same'):
        return True        # the same value written another way (units -> metres, 1 -> 100%)
    if c.get('drafts'):
        return False       # a patch's Street Brawl draft weights: one row whose values are its fold (brawl.draft_row)
    if op == 'change':
        # compared as the page prints them: "ELOSCheck_Bounds → Bounds" or an id and its name
        # read "Bounds → Bounds" (28 MECH rows, audit 2026-10-01); 9999 and -1 are one "no limit"
        a, b = shown_value(c.get('old_s')), shown_value(c.get('new_s'))
        if '|' in str(c.get('old_s')) and '|' in str(c.get('new_s')) and \
                flag_rules.bits(c.get('old_s')) == flag_rules.bits(c.get('new_s')):
            return True    # the same bits in another order: Goo Ball's "Behaviour" read as an empty row
        return _same(_sentinel(a, c, b), _sentinel(b, c, a))
    if op in ('add', 'remove') and not str(c.get('path') or '').startswith('@'):
        v = str(c.get('new_s' if op == 'add' else 'old_s') or '').strip().lower()
        # nothing to read either: an empty block added or removed ("Targeting rules — → —", 68 rows)
        return bool(_ZERO_RE.match(v)) or v in ('no', 'false', '', '—')
    return False


_LEVEL_ROW = re.compile(r'^Level (\d+): (.+)$')


_LEVEL_WORDS = {'souls needed': '{} souls', 'gives a boon': 'boon', 'ability points': '{} ability point',
                'ability unlocks': 'unlocks an ability'}


def combine_levels(rows: list[dict]) -> list[dict]:
    """A whole level added or removed ('Level 35: souls needed / gives a boon / ability points',
    three NEW rows) is one row: 'Level 35 added · 47000 souls · boon · 1 ability point'."""
    by_level: dict[tuple, list[dict]] = {}
    for c in rows:
        m = _LEVEL_ROW.match(str(c.get('label', '')))
        if m and c.get('op') in ('add', 'remove'):
            by_level.setdefault((m.group(1), c['op']), []).append(c)
    whole = {k: g for k, g in by_level.items() if len(g) >= 2}
    if not whole:
        return rows
    out, done = [], set()
    for c in rows:
        m = _LEVEL_ROW.match(str(c.get('label', '')))
        key = (m.group(1), c.get('op')) if m else None
        if key not in whole:
            out.append(c)
            continue
        if key in done:
            continue
        done.add(key)
        parts = []
        for x in whole[key]:
            what = _LEVEL_ROW.match(x['label']).group(2)
            val = x.get('new_s') if key[1] == 'add' else x.get('old_s')
            if str(val).lower() in ('no', 'false', '0'):
                continue
            fmt = _LEVEL_WORDS.get(what)
            parts.append(fmt.format(val) if fmt else f'{what} {val}')
        side = 'new_s' if key[1] == 'add' else 'old_s'
        out.append({**whole[key][0], 'label': f'Level {key[0]} {"added" if key[1] == "add" else "removed"}',
                    side: ' · '.join(parts), 'path': f'level:{key[0]}'})
    return out


_PROP_KEY = re.compile(r'(?:m_mapAbilityProperties\.|PropertyUpgrades\{)(\w+)')


_FIELD_PREFIX = re.compile(r'^(?:m_)?(?:fl|n|i|b|str|e|vec|map|un|s|v|h|ar|bits|sz)?(?=[A-Z])')


def _prop_of(c: dict) -> str:
    """The property a row is about; an engine field names itself by its last segment (a weapon's spread
    struct: three rows under "Shoot Spread Penalty Per Shot Normalization")."""
    path = str(c.get('path') or '')
    m = _PROP_KEY.search(path)
    return m.group(1) if m else _FIELD_PREFIX.sub('', re.sub(r'[\[{].*$', '', path.rsplit('.', 1)[-1]))
