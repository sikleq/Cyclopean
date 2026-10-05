"""Entity cards: the one component every change list uses (patch notes, all changes,
build pages, hero / item / unit history). A card = framed 48px icon, name, subtitle,
tag counters and the strip of history squares; inside it optional ability sub-headers
and rows on a fixed grid: status | tag | text | old -> new."""
from __future__ import annotations

import difflib
import re
from contextlib import contextmanager

from pipeline import flags as flag_rules

from .common import esc, mark, plural, visual
from .render import (HIDDEN_LIKE, NOT_IN_NOTES, _sentinel, fold_tier_swaps, fold_versions, not_in_notes, shown_value,
                     sort_changes, tag_badge, tag_html, tag_of, tag_summary, vals_html)
from .shared_rows import is_every

# documented is the normal case: no mark (a quiet row); every other status is an exception
ROW_MARKS = ('rounded', 'described', 'mismatch', 'fix', 'untracked', 'nodata', 'repeated',
             'hidden', 'unreleased', 'unannounced')


def is_hidden(changes: list[dict]) -> bool:
    """Something here was not in the patch notes (the eye; `render.NOT_IN_NOTES`)."""
    return any(c.get('status', 'hidden') in NOT_IN_NOTES for c in changes)


def card_head(name: str, icon_url: str | None, glyph: str, counted: list[dict], sub: str = '', trail: str = '',
              href: str = '') -> str:
    nm = f'<a href="{esc(href)}">{esc(name)}</a>' if href else esc(name)
    sub_html = f'<div class="sub">{esc(sub)}</div>' if sub else ''
    counted = player_facing(counted)
    counters = tag_summary(counted) if counted else ''
    return (f'<header class="ecard-h"><span class="ei">{visual(icon_url, glyph)}</span>'
            f'<div class="en"><div class="nm">{nm}</div>{sub_html}</div>'
            f'<div class="er">{counters}{trail}</div></header>')


def card(head: str, body: str, *, hidden: bool = False, dev: bool = False, search: str = '', anchor: str = '',
         extra: str = '') -> str:
    cls = 'ecard' + (' has-hidden' if hidden else '') + (' dev' if dev else '') + (f' {extra}' if extra else '')
    ds = f' data-search="{esc(search)}"' if search else ''
    aid = f' id="{esc(anchor)}"' if anchor else ''
    return f'<article class="{cls}"{aid}{ds}>{head}<div class="eb">{body}</div></article>'


def ability_plate(icon_url: str | None, glyph: str, ult: bool = False) -> str:
    """An ability's icon on a framed dark plate (the game's white glyphs read bare on the panel, owner
    2026-10-04), drawn smooth — no pixelated downscale of the 128px art; the ultimate gets a corner mark, no
    tooltip (its name is written beside it; AGENTS.md: tooltips only on text-less chips)."""
    return f'<span class="ab-ic{" ult" if ult else ""}">{visual(icon_url, glyph, "si2")}</span>'


def sub_head(name: str, icon_url: str | None, glyph: str, counted: list[dict], hidden: bool = False,
             icon: bool = True) -> str:
    """An ability inside its hero's card. `icon=False`: the caller puts the plate in its own column (an
    entity page's history: the icon anchors all of the ability's rows, like Sloppy's)."""
    counted = player_facing(counted)
    counters = tag_summary(counted) if counted else ''
    cls = 'esub' + (' has-hidden' if hidden else '')
    plate = ability_plate(icon_url, glyph) if icon else ''
    return f'<div class="{cls}">{plate}<span class="nm">{esc(name)}</span>{counters}</div>'


def row(status: str, tag: str, text_html: str, values_html: str = '', extra: str = '', attrs: str = '') -> str:
    m = mark(status) if status in ROW_MARKS else ''
    hid = ' is-hidden' if status in NOT_IN_NOTES else ''
    return (f'<div class="erow st-{esc(status)}{hid}{(" " + extra) if extra else ""}"{attrs}><span class="st">{m}</span>'
            f'<span class="tg">{tag}</span><span class="tx">{text_html}</span><span class="vv">{values_html}</span></div>')


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
        return list(changes)
    added =[a for g in adds.values() for a in g]
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
            x, y = _num(c.get('old_s', c.get('old'))), _num(a.get('new_s', a.get('new')))
            if _same_shown(c.get('old_s'), a.get('new_s')) or (
                    x is not None and y is not None and (x == y or abs(x / UNITS_PER_METER - y) < 0.01)):
                continue            # same value under a new key (or the same length now in metres)
            merged = {**a, 'op': 'change', 'old_s': c.get('old_s'), 'old': c.get('old'),
                      'status': min((a.get('status', 'hidden'), c.get('status', 'hidden')),
                                    key=lambda s: s not in HIDDEN_LIKE)}
            if x is not None and y is not None:
                # the NEW row carried dir='changed': judge the pair like any other change
                from pipeline.semantics import direction, gradient
                d, pct = direction(str(a.get('path', '')), x, y)
                merged.update(dir=d, pct=pct, grad=gradient(pct))
            out.append(merged)
            continue
        out.append(c)
    return [c for c in out if id(c) not in used]


def _rename_key(label) -> str:
    """'Pickup Radius' and 'Pickup Radius › Base' are one field moved into a sub-block."""
    return str(label or '').removesuffix(' › Base')


_TIER_HEAD = re.compile(r'^((?:T\d|Enhanced|Upgrade|Corrupted): )')
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
    hr, ha = _TIER_HEAD.match(lr), _TIER_HEAD.match(la)
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
    if x is None or x != y:
        return False
    ur, ua = _unit_of(old_s), _unit_of(new_s)
    if x == 0 or ur == ua or '%' not in (ur, ua):
        return True
    return bool(_PCT_NAME.search(_prop_of(r if ur != '%' else a)))


UNITS_PER_METER = 39.37
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
    r'|^m_mapDependentAbilities\.|(?:^|\.)m_fl(?:Preview)?ModelScale$|Observer(?:Origin|Pitch)$|^m_deploymentInfo\.m_b')


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


GAMEPLAY = ('balance', 'mechanic', 'availability')


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
        ch = [c for c in e['changes'] if c['cat'] in GAMEPLAY]
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


def change_row(c: dict) -> str:
    # a replaced tier lists both bonus sets: they go on their own full-width line under the
    # label (two lines at most, click to expand) instead of a tall right-aligned column
    extra = 'rw' if c.get('op') == 'rework' or c.get('bonus_list') else ''
    return row(c.get('status', 'hidden'), tag_html(c), esc(c.get('label')) + shared_chip(c), vals_html(c), extra)


def shared_chip(c: dict) -> str:
    """'shared ×9 heroes' after a row that one edit made in several entities at once (shared_rows.spread); a rule
    for all of them sits in its own fold instead (`every_rows`)."""
    if not c.get('shared_n') or is_every(c):
        return ''
    if c.get('shared_every'):        # the Game section lists a rule for all of them as its own row
        return f' <span class="chip shr">all {c["shared_n"]} {esc(c.get("shared_what") or "")}</span>'
    return f' <span class="chip shr">shared ×{c["shared_n"]} {esc(c.get("shared_what") or "")}</span>'


# A table edited row by row (souls per level 19-36, investment steps, the shotgun's pellet offsets)
# reads as one change: one summary row, the rows behind a click (audit 2026-10-01: ~700 rows in patches)
FAMILY_MIN = 4
# a number in a label, thousands separators included: "at 6,400 souls" is one number (the fold read
# "Vitality investment at 6–28,200 souls", review 2026-10-04)
_NUM_IN_LABEL = re.compile(r'\d{1,3}(?:,\d{3})+|\d+')


def _family(label: str) -> str:
    return _NUM_IN_LABEL.sub('N', label)


def _span(nums: list[int]) -> str:
    lo, hi = min(nums), max(nums)
    return f'{lo:,}' if lo == hi else f'{lo:,}–{hi:,}'


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


def family_rows(rows: list[dict]) -> str:
    rows = combine_levels(rows)
    fams: dict[str, list[dict]] = {}
    for c in rows:
        fams.setdefault(_family(str(c.get('label', ''))), []).append(c)
    html, done = [], set()
    for c in rows:
        fam = _family(str(c.get('label', '')))
        group = fams[fam]
        if len(group) < FAMILY_MIN:
            html.append(change_row(c))
            continue
        if fam in done:
            continue
        done.add(fam)
        html.append(_family_row(fam, group))
    return ''.join(html)


def _family_row(fam: str, group: list[dict]) -> str:
    """'Level 19–36: souls needed · 12 rows', tag of the group (mixed directions -> REWORK) and the
    range of % changes; the rows themselves fold under it."""
    from .render import tag_of
    first_nums = [int(m.group().replace(',', '')) for c in group for m in [_NUM_IN_LABEL.search(str(c.get('label', '')))] if m]
    base = str(group[0].get('label', ''))
    label = _NUM_IN_LABEL.sub(_span(first_nums), base, count=1) if first_nums else base
    kinds = {tag_of(c)[0] for c in group}
    rep = group[0] if len(kinds) == 1 else {'op': 'rework', 'grad': 6}
    pcts = [c['pct'] for c in group if isinstance(c.get('pct'), (int, float))]
    span = ''
    if pcts:
        lo, hi = min(pcts), max(pcts)
        span = f'{lo:+.0f}%' if round(lo) == round(hi) else f'{lo:+.0f}% … {hi:+.0f}%'
    status = min((c.get('status', 'hidden') for c in group), key=lambda s: s not in HIDDEN_LIKE)
    inner = ''.join(change_row(c) for c in group)
    vals = f'<span class="vals fam-span">{esc(span)}</span>' if span else ''
    head = row(status, tag_html(rep), f'{esc(label)} <span class="fam-n">· {len(group)} rows</span>', vals, 'fam-head')
    hid = ' has-hidden' if is_hidden(group) else ''
    return f'<details class="fam{hid}"><summary>{head}</summary>{inner}</details>'


# A newly added entity arrives with every field it has (Baba in build 6711: 218 rows, most of them
# the level table and item-cost curves every hero shares). What a reader wants is what it IS: the
# stats a player compares and its own abilities; the rest folds under "All fields".
ADDED_KEY = re.compile(
    r'^m_mapStartingStats\.E(MaxHealth|BaseHealthRegen|MaxMoveSpeed|SprintSpeed|Stamina|LightMeleeDamage|'
    r'HeavyMeleeDamage|BulletArmorDamageReduction|TechArmorDamageReduction)$'
    r'|^m_mapBoundAbilities\.ESlot_(Signature_\d|Weapon_Primary)$'
    r'|^m_eHeroDevelopmentState$'
    r'|^m_mapAbilityProperties\.[^.]+\.m_strValue$'
    r'|^m_(nMaxHealth|iMaxHealth|flMaxHealth|nCost|iItemTier|eItemSlotType)$')
ADDED_KEY_LIMIT = 12


def _added_split(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    key = [c for c in rows if ADDED_KEY.search(str(c.get('path') or '')) and str(c.get('new_s', '')) not in ('0', '')]
    keep = key[:ADDED_KEY_LIMIT]
    kept = {id(c) for c in keep}
    return keep, [c for c in rows if id(c) not in kept]


_PROP_KEY = re.compile(r'(?:m_mapAbilityProperties\.|PropertyUpgrades\{)(\w+)')
_CAMEL = re.compile(r'[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+')
_FIELD_PREFIX = re.compile(r'^(?:m_)?(?:fl|n|i|b|str|e|vec|map|un|s|v|h|ar|bits|sz)?(?=[A-Z])')
_HINT_SKIP = {'percent', 'pct', 'value', 'bonus', 'amount', 'base', 'max', 'm', 'str', 'fl', 'amp', 'penalty', 'power'}


def _prop_of(c: dict) -> str:
    """The property a row is about; an engine field names itself by its last segment (a weapon's spread
    struct: three rows under "Shoot Spread Penalty Per Shot Normalization")."""
    path = str(c.get('path') or '')
    m = _PROP_KEY.search(path)
    return m.group(1) if m else _FIELD_PREFIX.sub('', re.sub(r'[\[{].*$', '', path.rsplit('.', 1)[-1]))


def history_hints(changes: list[dict]) -> dict[tuple[str, str], str]:
    """(label, property) -> its hint over an entity's WHOLE history, so a row reads the same in every
    patch: Puddle Punch's T3 "Damage · base" also where the heavy-melee one did not move (2026-10-03)."""
    props: dict[str, list[str]] = {}
    for c in changes:
        p = _prop_of(c)
        if p and not is_noop(c) and not is_engine(c) and p not in props.setdefault(str(c.get('label')), []):
            props[str(c.get('label'))].append(p)
    out: dict[tuple[str, str], str] = {}
    for lab, ps in props.items():
        if len(ps) > 1:
            out |= {(lab, p): h for p, h in zip(ps, _group_hints(lab, ps)) if h}
    return out


def disambiguate(rows: list[dict], known: dict[tuple[str, str], str] | None = None) -> list[dict]:
    """Two fields of one entity under one label ("Healing Reduction" for both the receive and the regen
    penalty, Puddle Punch's two "T3: Damage" with opposite tags — 104 pairs, advisor round 3): each gets
    the words of its property name the label lacks, "Healing Reduction · receive". `known`: the
    entity's history_hints, which win so a row reads alike across patches."""
    known = known or {}
    groups: dict[str, list[tuple[int, str]]] = {}
    for i, c in enumerate(rows):
        prop = _prop_of(c)
        if prop:
            groups.setdefault(str(c.get('label')), []).append((i, prop))
    hint_of: dict[int, str] = {}
    for lab, members in groups.items():
        if len(members) > 1:
            hs = _group_hints(lab, [p for _, p in members])
            if not any(hs):     # one stat under two names ("TechPower" 7 → 0 beside a new "SpiritPower" 8)
                hs = [_moved_hint(rows[i]) for i, _ in members]
            hint_of |= dict(zip((i for i, _ in members), hs))
        hint_of |= {i: known[(lab, p)] for i, p in members if (lab, p) in known}
    return [{**c, 'label': f'{c.get("label")} · {hint_of[i]}'} if hint_of.get(i) else c for i, c in enumerate(rows)]


def _group_hints(label: str, props: list[str]) -> list[str]:
    """One hint per namesake. A bare one beside hinted ones gets a word too (Puddle Punch's T3: "Damage
    −50" beside "Damage · heavy melee +50" read as one stat twice, advisor round 4): its skipped words
    ("bonus"), else "base"; two alike hints keep their skipped words too ("base attack" / "attack bonus")."""
    hs = [_hint(label, p) for p in props]
    hs = [h or _hint(label, p, skip=frozenset()) for p, h in zip(props, hs)]
    hs = [_hint(label, p, skip=frozenset()) if hs.count(h) > 1 else h for p, h in zip(props, hs)]
    return [h or 'base' for h in hs] if any(hs) else hs


def _moved_hint(c: dict) -> str:
    if c.get('op') == 'add':
        return 'new field'
    return 'old field' if c.get('op') == 'remove' or str(c.get('new_s')) in ('0', '—', '', 'None') else ''


def _hint(label: str, prop: str, skip: frozenset[str] | set[str] = _HINT_SKIP) -> str:
    """The words of a property name its label lacks: 'HealAmpRegenPenaltyPercent' under "Healing
    Reduction" -> "regen"; Spirit is Tech in the files ("Spirit Power · tech" said nothing)."""
    have = {w.lower() for w in re.findall(r'[A-Za-z]+', label)}
    if 'spirit' in have:
        have.add('tech')

    def said(w: str) -> bool:               # "heal" is in "Healing"
        return w in have or any(len(w) >= 4 and (h.startswith(w) or w.startswith(h)) for h in have if len(h) >= 4)
    return ' '.join(w for w in (x.lower() for x in _CAMEL.findall(prop)) if not said(w) and w not in skip)


def entity_rows(changes: list[dict], known: dict[tuple[str, str], str] | None = None, every_href=None) -> str:
    """The rows of one entity in one patch on its own page (owner, 2026-10-03): what a player reads —
    no "Technical" fold (engine plumbing stays in data/, not on the page), and a newly added entity is
    its NEW head and key fields only, without "All fields". `known`: history_hints of the entity. A rule for every
    entity of its kind (shared_rows.is_every) is one link row after the entity's own (`every_rows`); `every_href`:
    system id -> the Game page's band of this patch."""
    every = [c for c in changes if is_every(c)]
    if every:
        own = [c for c in changes if not is_every(c)]
        return (entity_rows(own, known) if own else '') + every_rows(every, every_href)
    rows = disambiguate([c for c in sort_changes(fold_tier_swaps(fold_versions(merge_renames(changes))))
                         if not is_noop(c) and not is_engine(c)], known)
    if len(rows) > ADDED_KEY_LIMIT and all(c.get('op') == 'add' for c in rows):
        keep, _ = _added_split(rows)
        head = row('hidden' if is_hidden(rows) else rows[0].get('status', 'hidden'),
                   tag_badge('new', 'NEW'), 'Added to the game', attrs=behind_attr(changes, keep))
        return head + ''.join(change_row(c) for c in keep)
    return family_rows(rows)


def every_rows(changes: list[dict], every_href=None) -> str:
    """A rule for (almost) every entity of a kind on one of them — the level curve, the investment bonuses, a
    default of every melee attack — as ONE row per Game system that lists it: "All heroes: 35 changes · Hero
    progression ›" with its tag counters, a link to that system's band of the patch (coverage audit 2026-10-05:
    spread over the heroes, 35 level-curve rows drowned a hero's own patch). The rows themselves are on the Game
    page only: folded on every hero page they grew heroes/ from 13 to 37 MB (Haze 295 → 755 KB; review
    2026-10-05). Counted apart from the entity's own changes (history_view); `shr-all`: no tag or eye filter keeps
    the row, no band recount counts it (scripts.js hist-filter)."""
    from .game_systems import place_all_row, system
    rows = [c for c in sort_changes(fold_tier_swaps(fold_versions(merge_renames(changes))))
            if not is_noop(c) and not is_engine(c)]
    by_sys: dict[str, list[dict]] = {}
    for c in rows:
        by_sys.setdefault(place_all_row(str(c.get('file') or ''), c)[0], []).append(c)
    out = []
    for sid, got in by_sys.items():
        what = got[0].get('shared_what') or 'entities'
        text = f'All {esc(what)}: {plural(len(got), "change")}'
        name = esc(system(sid).name)
        go = (f' <a class="shr-go" href="{esc(every_href(sid))}">{name} ›</a>' if every_href
              else f' <span class="shr-go">{name}</span>')
        # no status mark: the rows' own marks are on the Game page; here it is a way there, not a change
        out.append(row('shared', '', f'<span class="shr-t">{text}</span>{go}', tag_summary(got), 'shr-all'))
    return ''.join(out)


def behind_attr(changes: list[dict], listed: list[dict]) -> str:
    """' data-n="new:57:40 on:1:1"' — the counted changes (player_facing, what the band's counters count) a
    head row stands for without listing them, as tag:changes:hidden. A filter recounts a band from its shown
    rows (scripts.js `hist-filter`); without this a new unit's band read NEW 71 built and 60 under a filter
    that kept every row (Old Gods, 2026-10-04)."""
    shown ={(c.get('key'), c.get('path')) for c in listed}
    per: dict[str, list[int]] = {}
    for c in player_facing(changes):
        if (c.get('key'), c.get('path')) in shown:
            continue
        n = per.setdefault(tag_of(c)[0], [0, 0])
        n[0] += 1
        n[1] += not_in_notes(c)
    return ' data-n="' + (' '.join(f'{t}:{n}:{h}' for t, (n, h) in per.items()) or 'new:0:0') + '"'


def change_rows(changes: list[dict], added: bool = False) -> str:
    rows = sort_changes(fold_tier_swaps(fold_versions(merge_renames(changes))))
    if added:
        keep, rest = _added_split(rows)
        head = row('hidden' if is_hidden(rows) else rows[0].get('status', 'hidden') if rows else 'hidden',
                   tag_badge('new', 'NEW'),
                   f'Added to the game files · {len(rows)} fields')
        html = head + ''.join(change_row(c) for c in keep)
        if rest:
            inner = ''.join(change_row(c) for c in rest)
            html += f'<details class="tech"><summary>All fields ({len(rest)})</summary>{inner}</details>'
        return html
    main, tech = [], []
    for c in rows:                                # one is_engine call a row (it ran twice)
        if not is_noop(c):
            (tech if is_engine(c) else main).append(c)
    html = family_rows(main)
    if tech:
        inner = ''.join(change_row(c) for c in tech)
        hid = ' has-hidden' if is_hidden(tech) else ''
        html += f'<details class="tech{hid}"><summary>Technical ({len(tech)})</summary>{inner}</details>'
    return html
