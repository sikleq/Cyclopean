"""Annotate official patch notes with the data changes they describe.

For every patch window we merge all field changes of its builds, then match
each note line to changes:

  documented — the line's numbers equal the data (old -> new)
  mismatch   — the line names a property but the data says other numbers
  described  — the line talks about the entity / a global keyword without
               exact numbers ("All slows reduced by ~20%", "Now builds from X")
  hidden     — (per change) nothing in the notes covers it
  heading    — (line) a bare entity name heading the lines below it
  untracked  — (line) sound / effects / UI / map / bots / links: not in the diffed data
  nodata     — (line) the patch predates every tracker, nothing to compare with
  repeated   — (line) an edited post repeats a line that a later patch's notes carry and match
  unmatched  — (line) should be in the data, but no change was found: a matcher gap

    python -m pipeline.match   ->  data/patches/<id>.json.gz + data/patches/index.json
"""
from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass, field

from . import cache, catalog, game_map, jsonio, loc, semantics, tracker
from . import flags as flag_rules
from . import match_rules as rules
from . import patches as patches_mod
from . import classify as classify_mod
from .classify import GAMEPLAY_CATS
from .patches import Patch, group
from .shared_groups import SharedGroups, window_of

# split 2026-11-13 into match_values (numbers, words, MChange), match_window (a window's changes) and match_passes
# (passes after the lines are read, the record's extras): every name is re-exported here for its callers
from .match_values import (ALIGNED_MAX, APPROX, EXACT, GENERIC_WORDS, HERO_STAT_WORDS, MChange, SYNONYMS, SYNONYM_ONLY,  # noqa: F401
                           WEAPON_WORDS, _ARROW_RE, _ATTACK_KIND, _BY_RE, _CHANGED_FROM, _COMPOUND, _COMPOUNDS,
                           _FIX_RE, _FOR_BOTH, _FROM_TO, _GRANT, _HALF_DAMAGE, _HP, _INSTEAD_RE, _ITEM_TIER_MOVE,
                           _LENGTHY, _METRES_ON_LINE, _MOVED_TO_TIER, _NOW_BY, _NUM, _PAIR_RE, _PARENS, _PART_STOP,
                           _PART_WORD, _PCT_LESS, _RATE_LIKE, _STOP, _SWAP_LINE, _SYNONYMS, _THOUSANDS, _TIER_NAME,
                           _TIER_RE, _TIER_TO, _TIME_WORDS, _WORD_RE, _aligned_pairs, _label_tokens, _number_list,
                           _numeric, _same_way, _shown_pair, _skeleton, _stems, _tokens, close, data_values,
                           exact_pair, expand_words, granted_pair, half_match, list_match, num, parse_pairs,
                           shown_in_meters, topic_words, two_sided, value_matches, words)
from .match_window import (BUILDS, LISTED_STATES, LIST_FILES, LIST_IDS, RELEASED_STATES, _BASE_LINK, _DEV_STATE,  # noqa: F401
                           _IN_DEV, _LIST_INDEX, _PROVIDED_TYPE, _SELECTABLE, _TRUTHY, _gameplay_entity, _state,
                           _window_change, event_name, keyed_list, load_record, mark_availability_moves, mark_dud_guns,
                           mark_inherited_defaults, mark_retyped, merge_ops, nameless_part, rekey_lists,
                           window_changes, window_states)
from .match_passes import (KEY_KINDS, KEY_LIMIT, KEY_MAX_PCT, LATE_DAYS, LOC_GROUPS, LOC_LIMIT, SHARED_NAMES, States,  # noqa: F401
                           _CONVAR_OP, _CONVAR_ORDER, _DIGIT, _LOOK_LINE, _SOUND_WORD, _TEST_ENTITY, _abilities_blob,
                           _chain_hit, _days, _late_hit, _subject_of, code_lines, key_changes, late_landings,
                           repeated_lines, sentence, slim_extras, text_state, texts_with_values)

OUT = tracker.ROOT / 'data' / 'patches'


# ---- line matching --------------------------------------------------------

@dataclass
class Subject:
    ids: set
    name: str
    kind: str
    # a game system's entries the line names (`system_alias`): tried by the line's numbers only, after `ids` and the
    # whole patch (first for a number list) — by words, dozens of them would link
    numeric_ids: set = field(default_factory=set)


def name_index(changes: list[MChange], cat: dict[str, dict], tok: dict[str, str]) -> dict[str, list[str]]:
    idx: dict[str, list[str]] = {}
    for key, e in cat.items():
        if e.get('template'):
            continue
        nm = e.get('name')
        if e['file'] == 'heroes.vdata':
            nm = loc.hero_name(tok, e['id'])
        elif e['file'] == 'abilities.vdata':
            nm = loc.entity_name(tok, e['id'], e.get('owner'))
        # the name at that build AND the latest one: notes said "Sinclair:" while the files still
        # called him "The Magnificent Sinclair" (22 lines), items renamed later (~30) — audit 2026-10-01
        for name in {nm, e.get('name')}:
            if name and name != e['id']:
                for variant in rules.name_variants(loc.plain(name)):
                    if key not in idx.get(variant, []):
                        idx.setdefault(variant, []).append(key)
    return idx


def inline_alias(text: str, idx: dict[str, list[str]]) -> set[str]:
    """Aliases named inside a line — unless the word is part of a longer name the line uses
    ("Veil Walker" is an item, not the Walkers: 11 lines were given to the bosses)."""
    low = text.lower()
    return rules.alias_keys(text, tuple(n for n in idx if ' ' in n and len(n) > 5 and n in low))


def system_pools(by_ent: dict[str, list[MChange]], cat: dict[str, dict]) -> dict[str, set[str]]:
    """game system id -> the window's changed entries in it (pipeline.game_map): the map objects, game rules and
    effects no hero, item or unit page claims, and the console variables its parts name."""
    out: dict[str, set[str]] = {}
    for k, cs in by_ent.items():
        c = cs[0]
        if c.file == 'convars':
            sid = game_map.convar_system(c.eid)
        else:
            e = cat.get(k) or {'file': c.file, 'id': c.eid}
            # as the Game pages place it (game_systems.place_entity): not a page's entry, scenery or a test object
            skip = game_map.claimed(e) or game_map.is_decor(e) or game_map.is_dev(e)
            hit = None if skip else game_map.place(f'{k}#{e.get("kind") or ""}')
            sid = hit[0] if hit else None
        if sid:
            out.setdefault(sid, set()).add(k)
    return out


def _names_moved(text: str, idx: dict[str, list[str]], cat: dict[str, dict], by_ent: dict[str, list[MChange]]) -> bool:
    """The line names an entity (an alias or its own name) whose gameplay fields moved in the window."""
    keys = inline_alias(text, idx) | inline_names(text, idx, cat, by_ent)
    return any(c.cat in GAMEPLAY_CATS for k in keys for c in by_ent.get(k, ()))


def system_lines_pools(text: str, pools: dict[str, set[str]] | None) -> dict[str, set[str]] | None:
    """The game systems' pools for a line that gives numbers (a pair, a percent, a granted value), else None."""
    if not pools:
        return None
    return pools if (parse_pairs(text) or _BY_RE.search(text) or granted_pair(text)) else None


# the words that say WHAT a number is: a field labelled by one the line does not use, while the line uses another,
# is another stat ("movespeed" is not "Extra Stamina")
STAT_NOUNS = {'stamina', 'speed', 'movespeed', 'health', 'radiu', 'range', 'duration', 'cooldown', 'ammo', 'clip',
              'regen', 'resist', 'damage', 'dps', 'lifesteal', 'charge', 'sprint', 'slow', 'distance', 'heal'}


def names_other_stat(c: MChange, line_words: set[str]) -> bool:
    """The field's label names a stat the line does not, and the line names one of its own."""
    own = {w for w in line_words if w in STAT_NOUNS}
    label = _label_tokens(c) & STAT_NOUNS
    return bool(own) and bool(label) and not label & rules.expand_label_words(line_words)


def system_alias(text: str, pools: dict[str, set[str]] | None) -> set[str]:
    """The window's entries of every game system a line names by its notes word ("Jump Pad stun window …",
    "Trooper bounty split …", "Time an Urn will wait …"): the files give these entries no name of their own."""
    if not pools:
        return set()
    return {k for _, sid in game_map.phrases_in(text) for k in pools.get(sid, ())}


INLINE_NAME_MIN = 5          # "Stomp" yes, "Bash" no
INLINE_NAME_MAX_KEYS = 6     # a name shared by dozens of entities ("Melee") names none of them


def inline_names(text: str, idx: dict[str, list[str]], cat: dict[str, dict],
                 by_ent: dict[str, list] | None = None) -> set[str]:
    """Entities a subject-less line names by their own name: its numbers belong to them, not to any
    field of the patch that moved the same way ("Base Guardian Health +20%" took Bebop's regen and two
    items, P12/P13 2026-10-02). Names in parentheses are exceptions ("except for Viscous"); a name
    inside a longer one the line uses is not named; a hero brings its abilities. With `by_ent`, only
    entities changed in the window count: "Fire Rate powerup" is not about the old item "Fire Rate"."""
    low = _PARENS.sub(' ', text.lower())
    found = [n for n, ks in idx.items()
             if len(n) >= INLINE_NAME_MIN and len(ks) <= INLINE_NAME_MAX_KEYS and n not in GENERIC_WORDS
             and n in low and re.search(rf'\b{re.escape(n)}\b', low)]
    found = [n for n in found if not any(n != m and n in m for m in found)]
    keys: set[str] = set()
    for n in found:
        s = resolve_subject(n, idx, cat)
        keys |= s.ids if s else set(idx[n])
    # a unit brings the abilities it binds ("Medic Trooper heal cooldown" is its heal ability's)
    units = {k.split(':', 1)[1] for k in keys if k.startswith('npc_units.vdata:')}
    if units:
        keys |= {k for k, e in cat.items() if units & set(e.get('units') or ())}
    if by_ent is None:
        return keys
    return {k for k in keys if any(c.cat in GAMEPLAY_CATS for c in by_ent.get(k, ()))}


def _close_hero(prefix: str, idx: dict[str, list[str]]) -> list[str] | None:
    """A hero name Valve misspelled ("Vindcita: Crow Familiar cooldown…", 2026-03-06)."""
    p = prefix.strip().lower()
    if len(p) < 5 or ' ' in p:
        return None
    heroes = [n for n, ks in idx.items() if any(k.startswith('heroes.vdata:') for k in ks) and n[:1] == p[:1]]
    hit = difflib.get_close_matches(p, heroes, n=1, cutoff=0.85)
    return idx[hit[0]] if hit else None


def resolve_subject(prefix: str, idx: dict[str, list[str]], cat: dict[str, dict]) -> Subject | None:
    """The entity a "Name:" prefix names (an alias word too: "Urn:", "Rejuv:"). A game system's word that is no alias
    ("Street Brawl:") is no subject: the line goes the way of one without (the rules for all, then its system's
    entries, `system_alias`)."""
    keys = idx.get(prefix.strip().lower())
    if not keys:
        aliased = rules.alias_keys(prefix)
        if aliased:
            return Subject(aliased, prefix, 'alias')
        keys = _close_hero(prefix, idx)
        if not keys:
            return None
    heroes = [k for k in keys if k.startswith('heroes.vdata:')]
    if heroes:
        hid = heroes[0].split(':', 1)[1]
        ids = {heroes[0]} | {k for k, e in cat.items() if e.get('owner') == hid}
        return Subject(ids, prefix, 'hero')
    # a name that is also an alias brings the alias's entries: "Mid-Boss" is the unit and the Rejuvenator it drops
    # ("Mid-Boss: Rejuvenator crystal drop time increased from 6s to 7.5s" was unmatched, 2026-10-30)
    same = {f'{f}:{i}' for f, i in rules.ALIASES.get(prefix.strip().lower(), ())}
    return Subject(set(keys) | same, prefix, cat[keys[0]].get('kind', ''))


def ent_key(c: MChange) -> str:
    return f'{c.file}:{c.eid}'


def label_words(c: MChange) -> set[str]:
    out = rules.expand_label_words(words(c.label))
    return out | {'growth'} if rules.GROWTH_LABEL.search(c.label or '') else out


_MINUTES = re.compile(r'\b(minutes?|mins?)\b', re.I)
_BASE_DAMAGE = re.compile(r'^\s*(base|gun)\s+damage\b', re.I)
_SPAWN_TIMER = re.compile(r'\b(spawns?|respawns?|spawn time|interval)\b', re.I)
_SECONDS = re.compile(r'\d\s*(s|sec|secs|seconds?)\b', re.I)
_UP_VERB = re.compile(r'\b(increas\w*|rais\w*|more|higher|faster|boost\w*)\b', re.I)
_DOWN_VERB = re.compile(r'\b(reduc\w*|decreas\w*|lower\w*|less|slower|cut)\b', re.I)
_TIME_LIKE = re.compile(r'(time|cooldown|interval|delay|cost|duration)', re.I)


def verb_sign(text: str) -> int:
    """+1 the line says up, -1 down, 0 neither or both."""
    up, down = bool(_UP_VERB.search(text)), bool(_DOWN_VERB.search(text))
    return 1 if up and not down else -1 if down and not up else 0


def _rounded_to_five(o: float, n: float, by_pct: float) -> bool:
    """Valve rounds a percent cut of round numbers to a step of 5: "Spirit damage on all abilities reduced by 10%"
    made Mo & Krill's Combo 40 → 35 and Burrow 75 → 65 (2026-10-30). Both values on that step, the new one within
    half a step of the exact result, and the field moved by some percent near the line's."""
    if o % 5 or n % 5 or abs(o) < 20 or o == n:
        return False
    exact = [o * (1 + by_pct / 100), o * (1 - by_pct / 100)]
    return any(abs(n - x) <= 2.5 for x in exact) and abs(abs(n / o - 1) * 100 - by_pct) <= max(5.0, 0.5 * by_pct)


# a percent over many values at once ("on all abilities", "by ~8%"): each one was rounded on its own. A line about one
# property is exact ("Slow effectiveness in air reduced by 15%" is not a cooldown 30s → 25s; "Neutral bounty increased by
# 5%" not a trooper's 65 → 70)
_LOOSE_PCT = re.compile(r'~|\b(all|every|abilities)\b', re.I)


def pct_close(c: MChange, by_pct: float, sign: int = 0, rate_line: bool = False, loose: bool = False) -> bool:
    """The field moved by the line's percent — the same way the line says: "Walker HP increased by
    40%" is not a cooldown cut by 40% (audit 2026-10-01: 115 links ran the wrong way). A rate on the
    line may move a time field the other way (fire rate up = interval down)."""
    for o, n in c.steps():
        o, n = num(o), num(n)
        if not o or n is None:
            continue
        if abs(abs(n / o - 1) * 100 - by_pct) > max(1.0, 0.1 * by_pct) \
                and not (loose and _rounded_to_five(o, n, by_pct)):
            continue
        moved = 1 if abs(n) > abs(o) else -1
        if sign and moved != sign and not (rate_line and _TIME_LIKE.search(c.label or c.path)):
            continue
        return True
    return False


_LIST_SPLIT = re.compile(r',\s*(?:and\s+)?|\s+and\s+|\s*&\s*|/')


_GROWTH_WORDS = {'growth', 'boon', 'scaling', 'minute'}


def list_parts(head: str) -> list[set[str]]:
    """The properties a line lists before its verb, each as words; [] for one property."""
    head = re.sub(r'\([^)]*\)', ' ', head)
    parts = [expand_words(_tokens(p)) for p in _LIST_SPLIT.split(head) if p.strip()]
    parts = [p for p in parts if p]
    return parts if len(parts) >= 2 else []


def list_hits(head: str, pool: list[MChange], by_pct: float, text: str, ability_hits: set[str]) -> list[MChange]:
    """For each listed property, the fields that moved by the line's percent and share most of its
    words (P13 2026-10-02: "Neutral respawn times, hp, and bounty reduced by 30%" linked the bounty
    only; "Siphon Life damage and spirit scaling" the scaling only). Two properties at least must
    find a field, or the line is one property after all."""
    parts = list_parts(head)
    if not parts:
        return []
    sign, rate = verb_sign(text), bool(re.search(r'rate|speed', text, re.I))
    moved = [c for c in pool if pct_close(c, by_pct, sign, rate, bool(_LOOSE_PCT.search(text)))]
    named = [c for c in moved if ent_key(c) in ability_hits]
    if named and len(ability_hits) < len({ent_key(c) for c in pool}):
        moved = named                   # the ability the line names, when it is not the whole pool
    out: list[MChange] = []
    found = 0
    for words_ in parts:
        # "Melee damage and growth": the first property is the base stat, not its per-boon growth
        grows = bool(words_ & _GROWTH_WORDS)
        scored = [(len(_label_tokens(c) & words_), c) for c in moved
                  if grows or not rules.GROWTH_LABEL.search(c.label or '')]
        best = max((s for s, _ in scored), default=0)
        if best:
            found += 1
            out += [c for s, c in scored if s == best and c not in out]
    return out if found >= 2 else []


# label words that name no property of their own: containers, units, shapes of a value
_LABEL_FILLER = {'scale', 'percentage', 'percent', 'pct', 'multiplier', 'mult', 'modifier', 'provided', 'aura',
                 'ally', 'effect', 'intrinsic', 'stat', 'level', 'value'}


def _core(c: MChange) -> set[str]:
    return words(re.sub(r'^T[1-3]:\s*', '', c.label or '')) - GENERIC_WORDS - _LABEL_FILLER


def names_whole_property(c: MChange, line_words: set[str]) -> bool:
    """Every word that names the field's property is in the line (or a synonym of it is): "Time Wall T3
    +1 Charge -> +2" is not the T3 Charge DELAY. Only for calling a line a mismatch — a claim that
    Valve's numbers are wrong needs the field to be the one the line means."""
    return all(w in line_words or rules.expand_label_words({w}) & line_words for w in _core(c))


def _same_kind(c: MChange, line_words: set[str]) -> bool:
    """A bullet field for a bullet line, a spirit one for a spirit line ("+185 Spirit Shield Health" is not
    the Bullet Shield Health that also became 185, Veil Walker 2024-07-18)."""
    label = words(c.label or '')
    return all(w in line_words for w in ('bullet', 'spirit') if w in label)


def mismatch_field(c: MChange, line_words: set[str], own: set[str], line_tokens: set[str]) -> bool:
    """The line means this field: it names the whole property, by a word of its own — or, for a label of
    common words only ("Bullet Damage"), by all of them, "damage" too (Haze's Bullet Dance "10 -> 7" vs
    6 -> 7; not "Time To Damage" for an Urn line about time)."""
    if not names_whole_property(c, line_words):
        return False
    return bool(label_words(c) & own) or (not _core(c) and _tokens(c.label or '') <= line_tokens)


def twin_hits(scored: list[tuple[int, MChange]], hits: list[MChange], pairs, lw: set[str],
              tier: int | None) -> list[MChange]:
    """Other fields of the matched entities that moved by the line's exact numbers and that the line names
    by a word (a synonym counts): "Ability Range reduced from +6% to +5%" is the range AND the radius
    multiplier (Knockdown and 11 items 2026-03-21), "damage and debuff resistance reduced from 80% to 70%"
    the bullet AND the spirit resist (Shadow Transformation 2024-06-27): 62 rows kept the eye while their
    own note gave both numbers (data-quality audit 2026-10-04). Not a field the line does not name
    (Sticky Bomb's "radius 12m to 10m" is not its Kill Check Window 12 -> 10), not a T1-T3 bonus of
    another tier than the line's (Air Drop's T1 barrier scaling 1 -> 0.7 is not "damage spirit scaling
    reduced from 1 to 0.7"), and only a value that changed (not a field removed with the old value)."""
    same = {ent_key(h) for h in hits}

    def tier_ok(c: MChange) -> bool:
        t = re.match(r'T([1-3]):', c.label or '')
        return (int(t.group(1)) if t else None) == tier
    return [c for _, c in scored if c not in hits and c.status == 'hidden' and c.op == 'change'
            and ent_key(c) in same and tier_ok(c) and label_words(c) & lw and exact_pair(c, pairs)]


def pair_hits(scored: list[tuple[int, MChange]], pairs, least: int) -> list[MChange]:
    """The best-scoring fields of each number pair on its own (scored: [(score, change)])."""
    out: list[MChange] = []
    for a, b in pairs:
        cands = [(s, c) for s, c in scored if s >= least
                 and any(value_matches(o, a, c, APPROX) and value_matches(n, b, c, APPROX) for o, n in c.steps())]
        # a field with the pair's exact numbers before one within the notes' rounding: "from -24% Slow and -26% Dash
        # distance to -28%" is Slow 24 → 28, though Dash -26 → -28 is within 10% of it and scores more (2026-11-04)
        exact = [(s, c) for s, c in cands if any(value_matches(o, a, c) and value_matches(n, b, c) for o, n in c.steps())]
        cands = exact or cands
        top = max((s for s, _ in cands), default=None)
        out += [c for s, c in cands if s == top and c not in out]
    return out


def score(c: MChange, text: str, pairs, by_pct, lw: set[str], tier: int | None, ability_hits: set[str],
          granted: bool = False) -> int:
    """`granted`: the pairs come from "now grants +N" (0 -> N) / "no longer grants +N" (N -> 0)."""
    s = 0
    steps = c.steps()
    if list_match(c, pairs):
        s += 10
    elif list_match(c, pairs, APPROX):
        s += 8              # "100/70/45/33%" for 1 / 0.7 / 0.45 / 0.333: a whole list within the notes' rounding
    for a, b in pairs:
        if any(value_matches(o, a, c) and value_matches(n, b, c) for o, n in steps):
            s += 10
        elif any(value_matches(o, a, c, APPROX) and value_matches(n, b, c, APPROX) for o, n in steps):
            s += 7          # the notes rounded a value ("0.5" for 0.54)
        elif c.op == 'add' and value_matches(c.new, b, c):
            s += 8          # value made explicit: "stacks from +2 to +3" where 2 was the default
        elif c.op == 'remove' and value_matches(c.old, a, c):
            s += 8
        elif granted and not a and c.op == 'change' and value_matches(c.new, b, c):
            s += 8          # "Now has a 8s cooldown" while it was 3s: the line states the new value
    if by_pct is not None and pct_close(c, by_pct, verb_sign(text), bool(re.search(r'rate|speed', text, re.I)),
                                        bool(_LOOSE_PCT.search(text))):
        s += 6
    overlap = len(label_words(c) & lw)
    s += min(overlap, 3)
    t = re.match(r'T([1-3]):', c.label)
    if tier is not None:
        s += 2 if (t and int(t.group(1)) == tier) else -3
    elif t:
        s -= 1
    if ability_hits and ent_key(c) in ability_hits:
        s += 2
    return s


def annotate(p: Patch, changes: list[MChange], cat: dict[str, dict], tok: dict[str, str]) -> list[dict]:
    idx = name_index(changes, cat, tok)
    by_ent: dict[str, list[MChange]] = {}
    for c in changes:
        by_ent.setdefault(ent_key(c), []).append(c)
    notes = '\n'.join(ln for s in (p.notes.sections if p.notes else []) for ln in s.lines)
    rescale = rules.boon_rescale(notes)
    for c in changes:
        c.scale = rescale[0] if rules.rescaled_field(c, rescale) else 1.0
    pools = system_pools(by_ent, cat)
    # an ability's Street Brawl numbers answer only the lines about that mode (classify.STREET_BRAWL_VALUE)
    plain = [c for c in changes if not classify_mod.STREET_BRAWL_VALUE.search(c.path)]
    plain_by_ent: dict[str, list[MChange]] = {}
    for c in plain:
        plain_by_ent.setdefault(ent_key(c), []).append(c)
    sections = []
    for sec in (p.notes.sections if p.notes else []):
        out_lines = []
        head = None
        mode_sec = bool(_STREET_BRAWL.search(sec.title or ''))
        for text in sec.lines:
            if _SUBHEAD.match(text) and not heading(text, idx):       # not a bare "Sinclair:" (heading)
                # "Items:" / "Street Brawl:" inside one post (2026-10-30): a heading of the lines below it, and the
                # mode's lines answer with its Street Brawl numbers ("Scrap Grenade - Radius reduced from 8m to 6m")
                mode_sec = bool(_STREET_BRAWL.search(text) or _STREET_BRAWL.search(sec.title or ''))
                head = None
                out_lines.append({'text': text, 'subject': None, 'status': 'heading', 'changes': []})
                continue
            mode = mode_sec or bool(_STREET_BRAWL.search(text))
            cs, be = (changes, by_ent) if mode else (plain, plain_by_ent)
            h = heading(text, idx)
            if h:
                # the 2025 layout: a bare 'Sinclair' line heads the lines below it
                head = h
                out_lines.append({'text': text, 'subject': h, 'status': 'heading', 'changes': []})
                continue
            own_prefix = ':' in text[:48] and resolve_subject(text.split(':', 1)[0], idx, cat)
            probe = f'{head}: {text}' if head and not own_prefix else text
            res = annotate_line(probe, cs, be, idx, cat, tok, rescale, pools)
            res['text'] = text
            if res['status'] == 'unmatched':
                topic = rules.untracked_topic(text.split(':', 1)[1] if own_prefix else text, sec.title,
                                              has_subject=bool(res.get('subject')))
                if topic:
                    res['status'] = 'untracked'
                    res['topic'] = topic
            out_lines.append(res)
        sections.append({'title': sec.title, 'lines': out_lines})
    post_pass(changes, by_ent)
    return sections


_HEADING_MAX = 40
_STREET_BRAWL = re.compile(r'street\s*brawl', re.I)
# a sub-heading line of a post: a few words and a colon, nothing after it ("General:", "Street Brawl:")
_SUBHEAD = re.compile(r'^\s*[A-Z][\w&\'\- ]{1,30}:\s*$')


def heading(text: str, idx: dict[str, list[str]]) -> str | None:
    """A line that is only an entity name ('Boundless Spirit') is a sub-heading."""
    t = text.strip().rstrip(':').strip()
    if not t or len(t) > _HEADING_MAX or ':' in t or re.search(r'\d', t):
        return None
    return t if idx.get(t.lower()) else None


_NO_LONGER = re.compile(r'\b(no longer|removed)\b', re.I)
_OLD_TIER = re.compile(r'\b(old|previous|former)\s+T[1-3]\b.*\bbase\b', re.I)


def post_pass(changes: list[MChange], by_ent: dict[str, list[MChange]]) -> None:
    """Rules that look at matches as a whole (audit patterns 2 and 7)."""
    for c in list(changes):
        if c.status not in ('documented', 'described') or not c.lines:
            continue
        line = c.lines[0]
        # 7: a feature added in one go: the matched field's siblings (added/removed together)
        root = rules.cluster_root(c.path)
        mode = bool(_STREET_BRAWL.search(line))
        for sib in by_ent.get(ent_key(c), []):
            if sib.status == 'hidden' and sib.cat in GAMEPLAY_CATS and sib.op in ('add', 'remove') \
                    and rules.cluster_root(sib.path) == root \
                    and (mode or not classify_mod.STREET_BRAWL_VALUE.search(sib.path)):
                sib.status = 'described'
                sib.lines.append(line)
        # a line that tells a rework in words is about every field of that entity that came or went with it:
        # "Baba's Brew - No longer has an initial brew time" took its Brew Time 1.5s → 0s, and its Barrier / Fire /
        # Silence Lock Time removed kept the eye (owner 2026-10-30: "described another way, not hidden"). Tuned
        # numbers stay hidden; a field that came or went with a number of its own only when the line says something
        # went away (the audit's real finds: Walker's new 30% trooper factor, Kinetic Pulse's new T2 +8s)
        if c.status == 'described':
            gone = bool(_NO_LONGER.search(line))
            for sib in by_ent.get(ent_key(c), []):
                if sib.status == 'hidden' and sib.cat in GAMEPLAY_CATS and sib.op in ('add', 'remove') \
                        and (num(sib.old if sib.op == 'remove' else sib.new) is None or gone and sib.op == 'remove'):
                    sib.status = 'described'
                    sib.lines.append(line)
        # 2: "(affects upgrades)": items built from this one moved the same way
        if c.status == 'documented' and rules.AFFECTS_UPGRADES_RE.search(line):
            for other in changes:
                if other.status == 'hidden' and other.path == c.path and other.old == c.old and other.new == c.new:
                    other.status = 'described'
                    other.lines.append(line)


@dataclass
class _Line:
    """One patch-note line on its way through `annotate_line`'s steps: what the line says (its numbers, words,
    tier), what it is about (`subject`, the `pool` of changes, the abilities it names) and its `result`."""
    text: str
    changes: list
    by_ent: dict
    idx: dict
    cat: dict
    tok: dict
    rescale: object
    pools: object
    subject: Subject | None
    rest: str
    lw: set
    pairs: list
    fix_line: bool
    granted: bool
    by_pct: float | None
    by_at: int | None
    tier: int | None
    result: dict
    pool: list = field(default_factory=list)
    ability_hits: set = field(default_factory=set)
    by_name: set = field(default_factory=set)


def annotate_line(text, changes, by_ent, idx, cat, tok, rescale=None, pools=None) -> dict:
    """`pools`: the window's game systems and their changed entries (`system_pools`), for a line with numbers only:
    a system holds dozens of entries, and a line without numbers would link whichever shares a word ("Added Dash
    Speed to the Vitality stat screen" took the zipline's Latch End Speed)."""
    ln = _read_line(text, changes, by_ent, idx, cat, tok, rescale, pools)
    done = _line_subject(ln)
    if done is not None:
        return done
    _line_aim(ln)
    done = _line_numbers(ln)
    if done is not None:
        return done
    return _line_words(ln)


def _read_line(text, changes, by_ent, idx, cat, tok, rescale, pools) -> _Line:
    """What the line says: its subject before a colon, its words, its number pairs (minutes, a fix's swap, a value
    granted or taken), a percent it moves by and the tier it names."""
    pools = system_lines_pools(text, pools)
    subject = None
    rest = text
    if ':' in text[:48]:
        prefix, rest = text.split(':', 1)
        subject = resolve_subject(prefix, idx, cat)
    lw = expand_words(words(rest))
    pairs = parse_pairs(rest)
    fix_line = bool(_FIX_RE.search(text))
    if fix_line and pairs:
        # "Fixed Health Regen being 3 instead of 1.5": the value WAS 3 and is 1.5 now, the other way round
        # from "drops now happen at 15 minutes instead of 20" (Seven 2025-05-27 stayed hidden)
        pairs = pairs + [(b, a) for a, b in pairs if (b, a) not in pairs]
    if _MINUTES.search(rest) or (_SPAWN_TIMER.search(rest) and not _SECONDS.search(rest)
                                 and all(max(a, b) <= 60 for a, b in pairs)):
        # "Rejuv duration 4 -> 3 minutes" while the files count seconds (240 -> 180): 8 lines unmatched;
        # a spawn timer says minutes without the word ("Vaults spawn time/interval 10/5 -> 8/4")
        pairs = pairs + [(a * 60, b * 60) for a, b in pairs]
    granted = False
    # the numbers outside parentheses are the change; inside, a total or an aside ("(0->14%)")
    outer = rest if not pairs else _PARENS.sub(' ', rest)
    if not pairs or not parse_pairs(outer):
        # "Now grants +75 Health" / "No longer grants +16% Spirit Resist": one number is a value that
        # appeared (0 -> N) or went away (N -> 0) — 769 numeric lines were unmatched, these the most;
        # "Now gains 1% Bullet Resist per Boon (0->14%)" is 0 -> 1, the 14% its total
        g = granted_pair(outer)
        if g:
            pairs, granted = g, True
    if not pairs and not fix_line and _HALF_DAMAGE.search(rest):
        # "Vexing Bolt - Now does half damage to objectives": its Boss Damage Scale 100% -> 50% (review 2026-10-17)
        pairs = [(100.0, 50.0)]
    # "Threadsap duration lasts 35% less" says by how much as "increased by 35%" does
    m = _BY_RE.search(rest) or _PCT_LESS.search(rest)
    by_pct = float(m.group('p')) if m else None
    by_at = m.start() if m else None
    mv = _ITEM_TIER_MOVE.search(rest)
    if mv and not pairs:
        # "Shadow Weave: Moved from T4 to T3" is the item's tier 4 -> 3, not an ability's T3 upgrade
        pairs = [(float(mv.group(1)), float(mv.group(2)))]
    tm = None if mv else _TIER_RE.search(rest)
    tier = int(tm.group(1)) if tm else None
    result = {'text': text, 'subject': subject.name if subject else None, 'status': 'unmatched', 'changes': []}
    return _Line(text, changes, by_ent, idx, cat, tok, rescale, pools, subject, rest, lw, pairs, fix_line, granted,
                 by_pct, by_at, tier, result)


def _line_subject(ln: _Line) -> dict | None:
    """A line without a subject: untracked topics, the rules for lines over many entities (boons, "all ..."), a
    name or alias inside it. The result when the line is done, else None (`ln.subject` may be set)."""
    text, changes, by_ent, idx, cat = ln.text, ln.changes, ln.by_ent, ln.idx, ln.cat
    rescale, pools, subject, pairs, by_pct, result = ln.rescale, ln.pools, ln.subject, ln.pairs, ln.by_pct, ln.result
    if not subject:
        topic = None if pairs or by_pct is not None else rules.untracked_topic(text)
        if topic not in (None, 'visual') and not (topic == 'interface' and _names_moved(text, idx, cat, by_ent)):
            # sound / interface / map words first: "Lowered volumes for UI death notification sounds
            # and respawn music" is not about respawn (annotate() tags it untracked) — P12; a bug fix
            # stays a fix ("…caused audio bugs as well"); not "visual": "Guardian melee no longer has a
            # splash range much larger than its visuals" is gameplay. An interface word next to an entity
            # whose files moved is matched first (#47.2): "Added keybinds for 'Fly Up' and 'Fly Down'. Used for
            # flying abilities like Ivy's Air Drop and Vindicta's Flight" is their new flight controls
            return _fix_or(result, text)
        covered = (rules.boon_lines(text, changes, rescale, num) or rules.global_line(text, changes, cat, num)
                   or rules.global_delta_line(text, changes, cat, num))
        if covered:
            return _link(result, covered, text, 'described')
        # "Walker bounty increased by 5%": the unit is named inside the line; failing a common word,
        # an entity's own name ("Medic Pack ally search radius from 30 to 35"); the game system the line names
        # ("Jump Pad stun window …"), with an alias or alone
        aliased = inline_alias(text, idx)
        named = set() if aliased else inline_names(text, idx, cat, by_ent)
        systems = system_alias(text, pools)
        if aliased or (systems and not named):
            subject = Subject(aliased, None, 'alias_inline', systems - aliased)
        elif named:
            subject = Subject(named, None, 'name_inline')
    ln.subject = subject
    return None


def _line_aim(ln: _Line) -> None:
    """The changes the line can be about (`ln.pool`, gameplay only) and the abilities / guns it names
    (`ln.ability_hits`, `ln.by_name`); a line about an entity whose files did not move is marked `_quiet`."""
    changes, by_ent, idx, cat, tok = ln.changes, ln.by_ent, ln.idx, ln.cat, ln.tok
    subject, rest, lw, result = ln.subject, ln.rest, ln.lw, ln.result
    if subject:
        # sorted: set order changes between runs (hash randomisation) -> unstable output
        pool = [c for k in sorted(subject.ids) for c in by_ent.get(k, [])]
    else:
        pool = changes
    ability_hits = set()
    by_name: set[str] = set()       # the hero's abilities / guns the line names by their own name
    if subject and subject.kind == 'hero':
        low = rest.lower()
        for k in subject.ids:
            e = cat.get(k, {})
            nm = loc.plain(loc.entity_name(tok, e.get('id', ''), e.get('owner'))).lower()
            if nm and len(nm) > 2 and any(v in low for v in rules.name_variants(nm)):
                ability_hits.add(k)
                # a name of its own, as a whole word: every hero's "Melee" names no one ability ("Gloom Bomb T2 …
                # Melee Resist"), nor does "Heal" inside "Health"
                if (not k.startswith('heroes.vdata:') and len(idx.get(nm, ())) <= INLINE_NAME_MAX_KEYS
                        and any(re.search(rf'\b{re.escape(v)}s?\b', low) for v in rules.name_variants(nm))):
                    by_name.add(k)
        if _BASE_DAMAGE.search(rest) and not ability_hits:
            # a hero's "base damage" is its gun's bullet damage ("Celeste: Base damage reduced from 29 to
            # 25" is the gun's 28.75 -> 25; "damage" and "base" are no words of their own here)
            lw = lw | {'bullet'}
        if lw & WEAPON_WORDS:
            ability_hits |= {k for k in subject.ids if cat.get(k, {}).get('kind') == 'weapon'}
        if not ability_hits and lw & HERO_STAT_WORDS:
            ability_hits |= {k for k in subject.ids if k.startswith('heroes.vdata:')}
        if lw & {'growth', 'boon'}:
            # "Bullet damage growth 0.28 -> 0.32": per-boon stats live on the hero, not on the gun
            ability_hits |= {k for k in subject.ids if k.startswith('heroes.vdata:')}
        # ability_hits only add score: "Bullet damage per boon" names the gun
        # but the value lives on the hero, so the pool is never narrowed.
    elif subject:
        ability_hits = set(subject.ids)     # an item / unit line is about that entity
    if subject and subject.kind not in ('alias_inline', 'name_inline'):
        # what the line is about, to tell later whether its files moved at all: the abilities it names,
        # else the whole subject (run() turns a still-unmatched line about unmoved files into "code")
        named = {k for k in ability_hits if not k.startswith('heroes.vdata:')
                 and cat.get(k, {}).get('kind') != 'weapon'} if subject.kind == 'hero' else set()
        about = named or set(subject.ids)
        if not any(c.cat in GAMEPLAY_CATS for k in about for c in by_ent.get(k, [])):
            result['_quiet'] = sorted(about)
    pool = [c for c in pool if c.cat in GAMEPLAY_CATS]
    ln.pool, ln.ability_hits, ln.by_name, ln.lw = pool, ability_hits, by_name, lw


def _line_numbers(ln: _Line) -> dict | None:
    """A line with numbers: the best-scored fields (its subject's, a game system's, the whole patch's), or a
    disagreement between the notes and the files (mismatch). The result, or None to try its words."""
    text, changes, by_ent, subject, rest, lw = ln.text, ln.changes, ln.by_ent, ln.subject, ln.rest, ln.lw
    pairs, by_pct, by_at, tier, granted, fix_line = ln.pairs, ln.by_pct, ln.by_at, ln.tier, ln.granted, ln.fix_line
    pool, ability_hits, result = ln.pool, ln.ability_hits, ln.result
    # an inline name or alias whose entity did not move at all still gets the whole-patch pass below (the Dash
    # ability had no change on 2026-07-28: "… ground dash time 0.7s to 0.72s" never reached it)
    inline = bool(subject) and subject.kind in ('alias_inline', 'name_inline')
    sys_ids = subject.numeric_ids if subject else set()
    sys_pool = [c for k in sorted(sys_ids) for c in by_ent.get(k, []) if c.cat in GAMEPLAY_CATS]
    if (pairs or by_pct is not None) and (pool or inline or sys_pool):
        # a line without a subject must also share a word with the field label; so must one whose
        # subject is only named inside it ("Medic Trooper … heal 14% → 12%" is not its range 14 → 12 m).
        # Not an alias's: "Walker HP increased by 40%" shares no word ("HP", "damage" are not words here)
        need_word = not subject or subject.kind == 'name_inline'
        need = 1 if need_word else 0

        def rank(cands, hits_):
            out = sorted(((score(c, rest, pairs, by_pct, lw, tier, hits_, granted), c) for c in cands
                          if not need_word or label_words(c) & lw), key=lambda x: -x[0])
            return out, (out[0][0] if out else 0)

        def enough(b) -> bool:
            return b >= 10 + need or (by_pct is not None and b >= 6 + need)
        # the game system the line names (`system_alias`): its entries carry no name a line could use and often no
        # word of it ("Jump Pad stun window increased from 0.6s to 0.9s" is the catapult watcher's Duration;
        # coverage finding 8) — not a field that names another stat than the line ("Movement Speed powerup
        # movespeed reduced from 2 to 1" is not the stamina powerup's Extra Stamina 2 -> 1)
        # — and no word is waived for one number alone: a field that only took the line's new value (an add, "now
        # grants") or moved by its percent must share a word with the line; both sides of a pair need none
        sys_pool = [c for c in sys_pool if not names_other_stat(c, lw)
                    and (label_words(c) & lw or two_sided(c, pairs))]
        tried = False

        def system_pass() -> None:
            nonlocal scored, best, pool, ability_hits, need_word, need, tried
            tried = True
            before = (scored, best, pool, ability_hits, need_word, need)
            need_word, need = False, 0
            pool, ability_hits = sys_pool, set(sys_ids)
            scored, best = rank(pool, ability_hits)
            if not enough(best):
                scored, best, pool, ability_hits, need_word, need = before
        scored, best = rank(pool, ability_hits)
        if not enough(best) and any(list_match(c, pairs, APPROX) for c in sys_pool):
            # a whole number list ("Trooper bounty split from 100/60/35/25/20/16% to 100/60/30/20/15/11") is the
            # list field of its system before any lone number of the patch (it took 87 investment bonuses)
            system_pass()
        if not enough(best) and subject and subject.kind in ('name_inline', 'alias_inline'):
            # the name was a coincidence ("Gun Powerup … Fire Rate" names the old item "Fire Rate"), or the
            # alias was: "Stamina bucket 3 heroes … ground dash time increased from 0.7s to 0.72s" is not the
            # Dash ability, "Heavy Melee cooldown increased from 0.9s to 1.0s" not the Parry — the pairs are
            # every slow hero's / every melee's, one '@shared' block each (unmatched until review 2026-10-05).
            # The whole patch, as for a line without a subject: a field must share a word with the line
            own_pass = (scored, best, pool, ability_hits, need_word, need)
            need_word, need = True, 1
            pool, ability_hits = [c for c in changes if c.cat in GAMEPLAY_CATS], set()
            scored, best = rank(pool, ability_hits)
            if subject.kind == 'alias_inline' and not enough(best):
                # nothing there either: a disagreement is judged on the alias's own fields, as before
                scored, best, pool, ability_hits, need_word, need = own_pass
        if not enough(best) and sys_pool and not tried:
            system_pass()       # last otherwise: a line an earlier pass matched keeps its fields
        if enough(best):
            hits = [c for s, c in scored if s == best]
            if len(pairs) > 1:
                # one best field for EACH pair: "Base HP 6725 -> 12500 and growth 470 -> 200" is two fields,
                # though "growth" scores the second one higher (P13 2026-10-02)
                hits += [c for c in pair_hits(scored, pairs, 9 + need) if c not in hits]
            if granted:
                # every field that took the value and shares a word: "Now grants +5% Ability Range" is the
                # range AND the radius multiplier (Echo Shard, 2025-11-21)
                # — of the same ability, by a word of the label (not by "T3" alone: Heavy Barrage's "+2m
                # explosion radius" took Spectral Wall's "Create Turrets 2")
                same = {ent_key(h) for h in hits}
                hits += [c for s, c in scored if s >= 9 + need and c not in hits
                         and ent_key(c) in same and label_words(c) & lw
                         and names_whole_property(c, lw) and _same_kind(c, lw)]
            if by_pct is not None and not pairs:
                # "respawn times, hp, and bounty reduced by 30%": the best field of EACH property listed
                hits += [c for c in list_hits(rest[:by_at], pool, by_pct, text, ability_hits) if c not in hits]
                if tier is None and subject and subject.kind not in ('alias_inline', 'name_inline'):
                    # a cut to a property without a tier is its tier bonuses too, where they moved by as much: "Strix
                    # Salvo - Spirit scaling reduced by 8%" is the base scaling and T3's +0.35 → +0.322 (2026-11-04);
                    # a line with a subject only ("Breakables growth values reduced by 10%" is no Burrow's T1)
                    props = {(ent_key(h), semantics.property_name(h.path)) for h in hits}
                    sign, rate = verb_sign(text), bool(re.search(r'rate|speed', text, re.I))
                    hits += [c for c in pool if c not in hits and re.match(r'T[1-3]:', c.label or '')
                             and (ent_key(c), semantics.property_name(c.path)) in props
                             and pct_close(c, by_pct, sign, rate, bool(_LOOSE_PCT.search(text)))]
                if re.search(r'\b(all|every)\b', rest, re.I):
                    # "Mo & Krill: Spirit damage on all abilities reduced by 10%": every damage that moved by it
                    # (Combo 40 → 35, Burrow 75 → 65, rounded), not the best-scored field alone (2026-10-30)
                    sign, rate = verb_sign(text), bool(re.search(r'rate|speed', text, re.I))
                    # (a tier's own value too: "all abilities" is base and upgrades, T1 Burrow 50 → 45)
                    # (the line's own words: words() drops "damage" as too common, and it is the property here)
                    said = set(re.findall(r'[a-z]+', rest.lower())) - {'spirit', 'ability', 'abilities', 'all', 'base'}
                    hits += [c for s, c in scored if s >= 5 + need and c not in hits
                             and set(re.findall(r'[a-z]+', (c.label or '').lower())) & said
                             and pct_close(c, by_pct, sign, rate, True)]
            if pairs and not granted:
                hits += twin_hits(scored, hits, pairs, lw, tier)
            for c in hits:
                c.status = 'documented'
                c.lines.append(text)
                if not granted:          # "now grants +75" keeps the NEW value, not an invented 0 -> 75
                    _old_from_notes(c, pairs, text, pool)
            moved_to = _MOVED_TO_TIER.search(rest)
            if moved_to:
                # "Baba's Brew - Cooldown increased from 25s to 27s (moved to T2)": T2's cooldown bonus -12s → -14s
                # is that move (it had the eye, data review 2026-10-17)
                props = {(ent_key(h), semantics.property_name(h.path)) for h in hits}
                for c in pool:
                    if c.status == 'hidden' and c.label.startswith(f'T{moved_to.group(1)}:') \
                            and (ent_key(c), semantics.property_name(c.path)) in props:
                        c.status = 'described'
                        c.lines.append(text)
            # a "now grants +N" value is stated exactly; its invented 0 is not a rounding
            rounded = pairs and not granted and not any(exact_pair(c, pairs) for c in hits)
            result['status'] = 'fix' if fix_line else 'rounded' if rounded else 'documented'
            result['changes'] = [c.key for c in hits]
            if rounded:
                result['data'] = data_values(hits[0], pairs)
            return result
        # names a property of this entity and one side of the numbers agrees,
        # the other does not: the notes and the files disagree. "Names" by a word of its own — not a
        # common one ("time", "resistance") nor one the subject brings ("guardian" -> "tier"): 2025-07-04
        # "Guardian base resistance 40% -> 60%" was a "mismatch" with Tier2 Gold Kill (review 10-02)
        own = words(rest) - GENERIC_WORDS - rules.ALIAS_WORDS
        # the pairs a disagreement is judged on: outside parentheses, and a real change — "changed from
        # 0.2s cast delay to 0.2s post cast time" moves a value to another property, 0.2 = 0.2
        said = [(a, b) for a, b in parse_pairs(_PARENS.sub(' ', rest)) if a != b] if not granted else []
        top = [c for s, c in scored
               if num(c.old) is not None and mismatch_field(c, lw, own, _tokens(rest))
               and (not ability_hits or ent_key(c) in ability_hits)
               and half_match(c, said)]
        # not for a name found inside the line: by now its pool may be the whole patch
        # nor for "now / no longer grants +N": its other side (0) is ours, not Valve's — the property is
        # often reused ("No longer grants +15% Spirit Lifesteal as base stat" while the field went 15 -> 16)
        if subject and subject.kind != 'name_inline' and top and not granted:
            c = top[0]
            if c.status == 'hidden':
                c.status = 'described'
            c.lines.append(text)
            result['status'] = 'mismatch'
            result['changes'] = [c.key]
            result['data'] = data_values(c, pairs)
            return result
    ln.pool, ln.ability_hits = pool, ability_hits         # a pass over the whole patch keeps its pool
    return None


def _line_words(ln: _Line) -> dict:
    """A line the numbers did not settle: its subject's fields by the words they share with it (a tier's, a
    component list, a removal, the ability it names), else its mechanics."""
    text, by_ent, idx, cat, subject, rest, lw = ln.text, ln.by_ent, ln.idx, ln.cat, ln.subject, ln.rest, ln.lw
    pairs, by_pct, tier, result = ln.pairs, ln.by_pct, ln.tier, ln.result
    pool, ability_hits, by_name = ln.pool, ln.ability_hits, ln.by_name
    if not subject:
        return _fix_or(result, text)
    if _FIX_RE.search(text):
        return _fix_or(result, text)
    specific = lw - GENERIC_WORDS

    def on_topic(c: MChange) -> bool:
        """The field shares a specific word with the line (not just 'bullet' or 'damage'), or a flag that
        came or went names it ("Decay: No longer interrupts sliding" = DONT_INTERRUPT_SLIDE_ON_CAST)."""
        flags = flag_words(c) & specific
        # a hero line's flags: of the ability it names ("Viscous: Can now use down dash during Goo Ball" is
        # not The Cube's behaviour)
        if flags and subject.kind == 'hero' and ability_hits and ent_key(c) not in ability_hits:
            flags = set()
        if _STATE_MASK.search(c.path):
            return bool(flags)
        own = topic_words(c)
        wide = label_words(c) if '›' not in (c.label or '') else rules.expand_label_words(own)
        return bool(own & specific) or bool(wide & specific - SYNONYM_ONLY) or bool(flags)

    def came(c: MChange) -> bool:
        """An item's field that came, by a word's stem — only when no field shares a word (`on_topic`): "Healbane:
        Stacks now diminish 20% more aggressively" is its new Stacking Penalty Anchor 80%, "Toxic Bullets: Now scales
        with Spirit Power (0.005%)" its new spirit scaling (2026-11-04); "Headhunter: Heal now scales with spirit power"
        has its heal field and is not the bonus damage's new scaling."""
        return (subject.kind == 'item' and c.op == 'add' and not _STATE_MASK.search(c.path)
                and bool((_stems(topic_words(c)) - GENERIC_WORDS) & (_stems(specific) - GENERIC_WORDS)))

    def named_whole(c: MChange) -> bool:
        """Every word of the label is in the line, common ones too: "Fury Trance: Active Bullet Resistance
        changed to Spirit Resistance" names Bullet Resist and Spirit Resist. The subject's own fields only
        (a hero line: the ability it names)."""
        core = words(c.label or '') - _LABEL_FILLER
        # two words at least, or one of its own: "Bullet Damage" is just "bullet" (Afterburn "… each bullet")
        enough = (len(core) >= 2 or bool(core - GENERIC_WORDS)) and not _STATE_MASK.search(c.path)
        return (enough and all(w in lw or rules.expand_label_words({w}) & lw for w in core)
                and (subject.kind != 'hero' or ent_key(c) in ability_hits))

    if subject.kind in ('alias_inline', 'name_inline'):
        # a unit merely named inside a sentence: link only on the field's own words (not a synonym:
        # "Continuous interior from jungle area to the walker" is not the aura radius) and never from
        # a line about sounds or looks ("Updated Mo & Krill Burrow … end sounds" is not falloff end)
        if pairs or _PRESENTATION_LINE.search(text):
            return result
        linked = [c for c in pool if words(c.label) & specific and not _STATE_MASK.search(c.path)]
        return _link(result, linked, text, 'described') if linked else result
    # 3: "T2 changed from 'A' to 'B'" / "T3 also increases radius": that tier's fields of the ability
    if tier is not None:
        scope = [c for c in pool if (not ability_hits or ent_key(c) in ability_hits)
                 and re.match(rf'T{tier}:', c.label)]
        topical = [c for c in scope if on_topic(c)]
        whole_tier = re.search(r'changed from|reworked|replaced|swapped', text, re.I)
        # "T3 no longer has 'Ink is no longer destroyed'": what that tier lost (its Destroy On Damage, 2026-10-30)
        gone = [c for c in scope if c.op == 'remove'] if _NO_LONGER.search(text) else []
        chosen = topical or (scope if whole_tier else gone)
        if chosen and _OLD_TIER.search(text):
            # "Now grants the old T2 barrier in the base ability": the base took what the tier had — its fields that
            # came from nothing (Traveler's Barrier 0 → 400, Buff Duration 0s → 12s, 2026-10-30)
            abil = {ent_key(c) for c in chosen}
            chosen = chosen + [c for c in pool if ent_key(c) in abil and not re.match(r'T[1-3]:', c.label)
                               and (c.op == 'add' or num(c.old) == 0) and c not in chosen]
        if chosen:
            return _link(result, chosen, text, 'described')
    # 2: "Now builds from Sprint Boots": component list of the item
    if rules.COMPONENT_RE.search(text):
        comp = [c for c in pool if 'ComponentItems' in c.path]
        if comp:
            linked = comp + [c for c in pool if c not in comp and on_topic(c)]
            return _link(result, linked, text, 'described')
        # "Berserker: Now builds into Frenzy": the list that moved is Frenzy's
        into = [c for k in inline_names(rest, idx, cat, by_ent) - set(subject.ids)
                for c in by_ent.get(k, ()) if 'ComponentItems' in c.path]
        if into:
            return _link(result, into, text, 'described')
    # textual line: link changes of the subject that share a specific word with the line; failing
    # that, a line naming an ability describes that ability's MECHANICS (flags, targets, behaviour) —
    # never its numbers, and never from a line about how it looks or sounds ("Storm Cloud audio is
    # clearer" had claimed its cooldown 180 → 148; 468 changes were "described" only that way)
    fallback = []
    if ability_hits and subject.kind == 'hero' and not _PRESENTATION_LINE.search(text):
        # (a modifier's states only when a state a player plays with moved: not "has fire beetles debuff")
        fallback = [c for c in pool if ent_key(c) in ability_hits and c.cat == 'mechanic'
                    and (not _STATE_MASK.search(c.path) or flag_rules.is_gameplay(c.path, c.old, c.new))]
    if _REMOVED_LINE.search(text):
        # "Soul Rebirth: Removed from the game" is its Disabled false -> true
        gone = [c for c in pool if c.cat == 'availability'
                and (subject.kind != 'hero' or not ability_hits or ent_key(c) in ability_hits)]
        if gone:
            return _link(result, gone, text, 'described')
    linked = [c for c in pool if on_topic(c) or named_whole(c)] or [c for c in pool if came(c)]
    # the ability the line names, when it has such a field: "Siphon Life range now scales…" is not
    # Seismic Impact's collide radius
    named = [c for c in linked if ent_key(c) in ability_hits]
    if by_name and not pairs:
        # the named ability's fields by a word's stem: "Scrap Grenade - Fixed some bugs with bouncing targeting" is its
        # Bounce Target Distance Check / Power and Bounce Max Horizontal Speed (they kept the eye, review 2026-10-17)
        stems = _stems(specific) - GENERIC_WORDS
        named += [c for c in pool if ent_key(c) in by_name and c not in named and not _STATE_MASK.search(c.path)
                  and (_stems(topic_words(c)) - GENERIC_WORDS) & stems]
    # a line that names an ability or gun by its name is about it, never the hero's base stats: "Strix Salvo -
    # Cooldown from 30s to 25s" took Danny's Stamina Cooldown 4.5s → 5s, "Chimera Mk1 - Slow effectiveness in air
    # reduced by 15%" his Air Dash Duration (data review 2026-10-17)
    linked = named or ([] if by_name else linked)
    if linked and pairs:
        # the line's numbers must agree with the field: one side of a pair within the notes' rounding, or the same
        # way up (30 → 25 is not 4.5 → 5); a field without numbers (a flag, a class) is judged by its words
        said = [(a, b) for a, b in parse_pairs(_PARENS.sub(' ', rest)) if a != b] or pairs
        linked = [c for c in linked if not _numeric(c) or half_match(c, said) or _same_way(c, said)]
    if linked and (pairs or by_pct is not None):
        # a line with numbers no field matched: the fields that share the MOST of its words ("Bullet
        # damage growth reduced by 18%" is the bullet growth, not the health growth)
        # (not the words in parentheses: "(affects base damage, AP and spirit scaling)" names no field)
        core = expand_words(words(_PARENS.sub(' ', rest)))
        most = max(len(label_words(c) & core) for c in linked)
        linked = [c for c in linked if len(label_words(c) & core) == most]
    if linked and fallback and all(c.cat == 'mechanic' and ent_key(c) in ability_hits for c in linked):
        # only the named ability's flags spoke: its other mechanics stay described as before
        linked = linked + [c for c in fallback if c not in linked]
    linked = linked or fallback
    if not linked and by_name and not pairs:
        # a words line whose one number is a value the named ability's field had or took: "Guided Owl - Now launches in
        # the exact direction you're aiming (previously always launched at least 45° upward)" is its Arrow Initial
        # Pitch -45 → 89 (2026-10-30)
        # (in the field's unit — "-20s cd" is no Fire Rate 20% — and of the tier the line names, if it names one)
        said = {(abs(float(m.group('v'))), m.group('u') or '')
                for m in re.finditer(rf'(?P<v>{_NUM})\s*(?P<u>%|s\b|m\b)?', _TIER_NAME.sub(' ', rest))}
        tiers = set(re.findall(r'\bT([1-3])\b', rest))

        def says(c: MChange) -> bool:
            t = re.match(r'T([1-3]):', c.label)
            if (t.group(1) if t else None) not in (tiers or {None}):
                return False            # a line without a tier is about the base ("Afterburn (20% for light melee)")
            vals = {abs(v) for v in (num(c.old), num(c.new)) if v}
            unit = (c.unit or '')[:1]
            return any(v in vals and (not u or not unit or u == unit) for v, u in said)
        linked = [c for c in pool if ent_key(c) in by_name and not _STATE_MASK.search(c.path) and says(c)]
    if linked:
        return _link(result, linked, text, 'described')
    return result


# a modifier's states: its label is the modifier's container ("Holding Idol › Applies"), so a line links it
# only by the states that came or went ("not disarmed or silenced"), never by the container's words ("Please
# continue to give feedback on the Urn" took the Urn runner's states, 2026-10-04)
_STATE_MASK = re.compile(r'\.m_nEnabledStateMask$')
_FLAG_WORD_FIELDS = {'m_AbilityBehaviorsBits', 'm_nAbilityBehaviors', 'm_nAbilityTargetTypes', 'm_nAbilityTargetFlags',
                     'm_bitsInterruptingStates', 'm_nBehaviors', 'm_eAbilityTargetingLocation',
                     'm_eAbilityTargetingShape', 'm_nAttributes', 'm_nEnabledStateMask', 'm_nDisabledStateMask'}
_REMOVED_LINE = re.compile(r'\b(removed from the (game|shop)|(is|are|now) disabled|no longer (available|in the shop))\b',
                           re.I)
_FLAG_PREFIX = re.compile(r'^(CITADEL_ABILITY_BEHAVIOR_|CITADEL_UNIT_TARGET_|CITADEL_|MODIFIER_STATE_|MODIFIER_)')


def flag_words(c: MChange) -> set[str]:
    """The words of the flags a flag field gained or lost (Behaviour, Can target, Interrupted by…)."""
    leaf = c.path.rsplit('.', 1)[-1]
    # a modifier's attributes too: "Multiple instances stack" = MODIFIER_ATTRIBUTE_MULTIPLE (Slice and Dice);
    # bit sets only (not the enums and switches FLAG_FIELDS also names)
    if leaf not in _FLAG_WORD_FIELDS:
        return set()
    split = lambda v: {f.strip() for f in str(v or '').split('|') if f.strip()}      # noqa: E731
    moved = split(c.old) ^ split(c.new)
    out = set().union(*(words(_FLAG_PREFIX.sub('', f).replace('_', ' ')) for f in moved)) if moved else set()
    # a state is named by its -ing form, a line by the verb: MODIFIER_STATE_SLIDING_DISABLED is "Restored being able
    # to slide while using Bullet Dance" (2026-04-30; the line had gone to Bullet Dance's channel move speed)
    out |= {v for w in out if w.endswith('ing') and len(w) > 5 for v in (w[:-3], w[:-3] + 'e')}
    return out - _FLAG_FILLER


# flag words every behaviour list repeats: they name no behaviour of their own
_FLAG_FILLER = {'can', 'use', 'cast', 'ability', 'target', 'unit', 'set', 'dont', 'allow', 'while', 'during',
                'displays', 'damage', 'impact', 'friendly', 'enemy', 'all', 'hero', 'heroe', 'ui', 'instant',
                'attribute'}


_PRESENTATION_LINE = re.compile(r'\b(sounds?|audio|sfx|vfx|visuals?|effects?|particles?|animations?|anims?|models?|'
                                r'icons?|ui|hud|tooltips?|indicators?|music|voice|crosshair|readability)\b', re.I)


def _link(result: dict, changes: list[MChange], text: str, status: str) -> dict:
    for c in changes:
        if c.status == 'hidden':
            c.status = 'described'
        c.lines.append(text)
    result['status'] = status
    result['changes'] = [c.key for c in changes]
    return result


def _fix_or(result: dict, text: str) -> dict:
    """Bug-fix lines rarely change data: tag them instead of calling them unmatched."""
    if result['status'] == 'unmatched' and _FIX_RE.search(text):
        result['status'] = 'fix'
    return result


# ---- output -----------------------------------------------------------------

def _old_from_notes(c: MChange, pairs: list[tuple[float, float]], text: str = '',
                    siblings: list[MChange] | None = None) -> None:
    """A field that appeared with the value Valve says it was raised TO: before, the game used its
    default, and the notes name it ("Headshot stack count increased from +2 to +3" while the files
    only gained HeadshotStacks = 3). The line's old value makes it a change (BUFF/NERF), not a NEW.
    Not on a line that swaps one bonus for another ('T2 changed from "-12s Cooldown" to …'), nor when
    the entity lost a field holding that old value — then A belonged to the other field (audit
    2026-10-01: ~25 invented "was → now" such as "T2: Cooldown 12 → −15")."""
    if c.op != 'add' or c.old is not None or c.meters or num(c.new) is None or _SWAP_LINE.search(text) \
            or _CHANGED_FROM.search(text):
        return
    # a value the files write with its unit ("16m", Street Brawl radii) takes the old one in the same unit: a bare 20
    # was read as engine units and shown 0.508m (Rule, Ratannia!, 2026-10-30)
    suffix = re.sub(rf'^\s*{_NUM}\s*', '', c.new) if isinstance(c.new, str) else ''
    if _METRES_ON_LINE.search(text) and suffix != 'm':
        return
    removed_values = {num(s.old) for s in siblings or () if s.eid == c.eid and s.op == 'remove' and num(s.old) is not None}
    olds = {a for a, b in pairs if abs(b - num(c.new)) < 1e-9 and a != b}
    if len(olds) == 1 and not any(abs(a - r) < 1e-9 for a in olds for r in removed_values):
        old = olds.pop()
        c.old = f'{old:g}{suffix}' if suffix else old
        c.op = 'change'


def change_json(c: MChange) -> dict:
    kind = c.kind or ''
    # one side in metres, the other bare (engine units): both in metres, for the numbers and the % alike
    old, new = semantics.units_when_bare(c.path, *semantics.metres_pair(c.old, c.new))
    dirn, pct = semantics.direction(c.path, num(old), num(new), kind, c.drawback, c.neg_base)
    flag = flag_rules.is_flag_field(c.path)
    if flag and kind not in semantics.SHARED_KINDS:
        dirn = flag_rules.direction(c.path, c.old, c.new) or dirn     # "Can target: + neutrals" is a buff
    shown = semantics.M_SPEED if c.speed_m and not c.meters else c.meters
    if not c.meters and semantics.length_in_units(c.path, c.unit, (c.old, c.new)):
        shown = True                  # a property length no build gave a unit: engine units, shown in metres
    unit = c.unit
    if not c.meters and c.old_unit is None and semantics.bare_engine_length(c.unit, (c.old, c.new)):
        # the tooltip's "m" over bare engine units: converted, not "500m" (semantics.bare_engine_length)
        shown, unit = (semantics.SPEED if c.unit == 'm/s' else True), ''
    magnitude = c.sign == '-'
    switched = c.old_unit is not None
    if switched:
        dirn, pct = 'changed', None   # another unit: the numbers do not compare (labels.unit_switch)
    return {
        'key': c.key, 'file': c.file, 'id': c.eid, 'path': c.path, 'op': c.op, 'cat': c.cat,
        'label': c.shown or c.label,
        'old_s': semantics.show(old, shown, c.old_unit if switched else unit, c.invert, magnitude),
        'new_s': semantics.show(new, shown, unit, c.invert, magnitude),
        'dir': dirn, 'pct': None if pct is None else round(pct, 1), 'grad': semantics.gradient(pct),
        'status': c.status, 'builds': sorted(set(c.builds)), 'shared': c.shared,
        'same': (semantics.reencoded(c.old, c.new, c.path) or (c.retyped and semantics.sign_flip(c.old, c.new))
                 or c.moved),
        **({'flag': True} if flag else {}),
        **({'unit_switch': True} if switched else {}),
    }


# 'shared': every hero's ability (jump, dash…), ownerless since 2026-10-04 — still an event of its own
ENTITY_EVENT_KINDS = {'hero', 'item', 'ability', 'weapon', 'trooper', 'building', 'neutral', 'unit', 'shared'}
# kinds that count only with proof they matter (audit B12, 2026-10-02: 102 removed abilities such
# as Splatapult, 85 new pickups such as the permanent ammo powerup and game-rule blocks such as
# m_RejuvParams were on no patch page): an ability with a name or an NPC that binds it; a rules
# entry with gameplay fields (removed: a gameplay-like id). Not a hero's melee: its name is the shared
# "Melee" string, and the hero and its gun already make the event
EVENT_IF_NAMED = {'ability_other'}


def event_worthy(x: dict) -> bool:
    kind = x.get('kind')
    if kind in ENTITY_EVENT_KINDS:
        return True
    if kind in EVENT_IF_NAMED:
        return bool(x.get('units')) or bool(x.get('name')) and x['name'] != x['id']
    return kind == 'global' and bool(x.get('gameplay'))


def entity_events(extras: dict, notes_text: str, tok: dict[str, str]) -> list[dict]:
    """One change per entity added to / removed from the files in this window."""
    out = []
    for bucket, op, path, label in (('entities_added', 'add', '@add', 'Added to the game files'),
                                    ('entities_returned', 'add', '@return', 'Back in the game files'),
                                    ('entities_removed', 'remove', '@remove', 'Removed from the game files')):
        for x in extras.get(bucket, []):
            if not event_worthy(x) or x['id'] == '@shared':
                continue
            name = x.get('name') or x['id']
            status = 'described' if name and name != x['id'] and name.lower() in notes_text else 'hidden'
            out.append({**x, 'name': name, 'change': {
                'key': f"{x['file']}:{x['id']}:{path}", 'file': x['file'], 'id': x['id'], 'path': path,
                'op': op, 'cat': 'mechanic', 'label': label, 'old': None, 'new': None, 'old_s': '', 'new_s': '',
                'dir': 'changed', 'pct': None, 'grad': 5, 'status': status, 'builds': [x['build']], 'shared': False}})
    return out


_OPEN_LINE = ('unmatched', 'untracked')


def _claim_line(ln: dict, key: str) -> None:
    """A line that announces a change: it links the change, and a line nothing had claimed is 'described'."""
    if key not in ln.setdefault('changes', []):
        ln['changes'].append(key)
    if ln.get('status') in _OPEN_LINE:
        ln['status'] = 'described'
        ln.pop('topic', None)


def name_events(sections: list[dict], events: list[dict]) -> int:
    """An entity that came or went is 'described' when a line of its window names it (`rules.names_event`:
    "Haunts (new neutral camps): … Barrel Mimics" for Barrel Mimic I-III, "Tough Crates: …", the "Bell Tower"
    line, which is also a map line). Only the event: the numbers of a new entity the notes do not give stay
    hidden. Returns the events it described."""
    lines = [ln for s in sections for ln in s['lines'] if ln.get('status') not in ('heading', 'repeated')]
    n = 0
    for ev in events:
        ch = ev['change']
        if ch['status'] != 'hidden':
            continue
        phrases = rules.event_phrases(f"{ev['file']}:{ev['id']}", ev.get('name'))
        hit = next((ln for ln in lines if phrases and rules.names_event(ln['text'], phrases)), None)
        if hit is None:
            continue
        ch['status'] = 'described'
        _claim_line(hit, ch['key'])
        n += 1
    return n


BLANKET_FILE = tracker.ROOT / 'data' / 'overrides' / 'blanket_lines.json'


def load_blankets() -> list[dict]:
    try:
        return json.loads(BLANKET_FILE.read_text(encoding='utf-8')).get('lines', [])
    except FileNotFoundError:
        return []


def _in_scope(scope: dict, file: str, eid: str, path: str, op: str, kind: str | None) -> bool:
    if scope.get('file') and scope['file'] != file:
        return False
    if scope.get('path') and not re.search(scope['path'], path):
        return False
    if scope.get('ops') and op not in scope['ops']:
        return False
    if scope.get('kinds') and (kind or '') not in scope['kinds']:
        return False
    return not scope.get('id') or bool(re.search(scope['id'], eid))


def blanket_lines(pid: str, sections: list[dict], changes: list[MChange], events: list[dict],
                  cat: dict[str, dict], blankets: list[dict] | None = None) -> int:
    """A line that announces a whole feature without numbers ('Full shop rework, including many new items')
    covers the changes `data/overrides/blanket_lines.json` scopes to it — by field and kind of operation, never a
    whole file. Only hidden changes move (to 'described', linked to the line). Returns the changes it covered."""
    n = 0
    for b in (load_blankets() if blankets is None else blankets):
        if b.get('patch') != pid:
            continue
        needle = b['line'].lower()
        line = next((ln for s in sections for ln in s['lines'] if needle in ln['text'].lower()), None)
        if line is None:
            continue
        scopes = b.get('match') or []
        for c in changes:
            if c.status != 'hidden' or c.file == 'convars':
                continue
            kind = cat.get(ent_key(c), {}).get('kind') or c.kind
            if any(_in_scope(sc, c.file, c.eid, c.path, c.op, kind) for sc in scopes):
                c.status = 'described'
                c.lines.append(line['text'])
                _claim_line(line, c.key)
                n += 1
        for ev in events:
            ch = ev['change']
            op = ch['path'].lstrip('@')
            if ch['status'] == 'hidden' and any(_in_scope(sc, ev['file'], ev['id'], ch['path'], op, ev.get('kind'))
                                                for sc in scopes):
                ch['status'] = 'described'
                _claim_line(line, ch['key'])
                n += 1
    return n


def count_statuses(changes: list[MChange], events: list[dict]) -> dict[str, int]:
    """Gameplay changes by status; a change repeated across many entities
    ('@shared') counts once, an added/removed entity counts once."""
    counts = {'documented': 0, 'described': 0, 'hidden': 0, 'unannounced': 0, 'unreleased': 0}
    seen_shared: set[tuple] = set()
    for c in changes:
        if c.cat not in GAMEPLAY_CATS or c.file == 'convars' or c.moved:
            continue
        if c.shared:
            sig = (c.file, c.path, repr(c.old), repr(c.new), c.status)
            if sig in seen_shared:
                continue
            seen_shared.add(sig)
        counts[c.status] = counts.get(c.status, 0) + 1
    for ev in events:
        counts[ev['change']['status']] += 1
    return counts


def build_patch(p: Patch, cat: dict[str, dict]) -> dict:
    commit = None
    if p.builds:
        commit = load_record(p.builds[-1]['file'])['commit']
    tok = loc.tokens(commit) if commit else {}
    changes, extras = window_changes(p, cat, tok)
    sections = annotate(p, changes, cat, tok)
    notes_text = ' '.join(ln for s in (p.notes.sections if p.notes else []) for ln in s.lines).lower()
    events = entity_events(extras, notes_text, tok)
    if not p.notes:
        # no changelog exists for this window: nothing can be "hidden from" notes
        for c in changes:
            c.status = 'unannounced'
        for ev in events:
            ev['change']['status'] = 'unannounced'
        if p.release:
            release_pass(p.release, changes, events, cat)
    if commit:
        mark_unreleased(p, commit, changes, events, cat)
    if p.notes and commit:
        # lines that announce what came or went, and features announced in one sentence (after the
        # unreleased pass: work on a hero still in development stays "Before release")
        name_events(sections, events)
        blanket_lines(p.id, sections, changes, events, cat)
    entities: dict[str, dict] = {}
    cv_status = {c.eid: c.status for c in changes if c.file == 'convars'}
    for cv in extras['convars']:
        # a hero's release post is the window's notes: what it left out is hidden (release_pass)
        cv['status'] = cv_status.get(cv['name'], 'unannounced' if not p.notes and not p.release else 'hidden')
    shared = SharedGroups()
    for c in changes:
        if c.file == 'convars':
            continue
        name = (loc.plain(loc.hero_name(tok, c.eid) if c.file == 'heroes.vdata'
                          else loc.entity_name(tok, c.eid, cat.get(ent_key(c), {}).get('owner')))
                if c.eid else c.eid)
        if c.shared:
            # one edit copied into many entities (a global rule): one block, not N — with the keys of the
            # entities it hit, so their pages show it (pipeline/shared_groups.py)
            # (a field that only moved for some of its targets is two blocks: no change / a change)
            sig = (c.file, c.path, repr(c.old), repr(c.new), c.moved)
            shared.add(sig, change_json(c) if sig not in shared else None, name, ent_key(c), c.status)
            continue
        k = ent_key(c)
        e = cat.get(k, {})
        ent = entities.setdefault(k, {
            'key': k, 'file': c.file, 'id': c.eid, 'kind': e.get('kind'), 'owner': e.get('owner'),
            'name': name, 'changes': [],
        })
        ent['changes'].append(change_json(c))
    for ev in events:
        k = f"{ev['file']}:{ev['id']}"
        ent = entities.setdefault(k, {'key': k, 'file': ev['file'], 'id': ev['id'], 'kind': ev.get('kind'),
                                      'owner': ev.get('owner'), 'name': ev['name'], 'changes': []})
        ent['changes'].insert(0, ev['change'])
    for ent in shared.entities(cat, window_of(p.builds), SHARED_NAMES):
        entities[ent['key']] = ent
    for ent in entities.values():
        for c in ent['changes']:
            c['sentence'] = sentence(ent['name'], c)
    counts = count_statuses(changes, events)
    line_counts: dict[str, int] = {}
    for s in sections:
        for ln in s['lines']:
            if ln['status'] == 'unmatched' and not p.builds:
                ln['status'] = 'nodata'     # May 2024: no tracker holds game files for these dates
            line_counts[ln['status']] = line_counts.get(ln['status'], 0) + 1
    ents = sorted(entities.values(), key=lambda e: (e['file'], e['name'] or ''))
    return {
        'id': p.id, 'title': p.title, 'date': p.date[:10],
        'url': p.notes.url if p.notes else p.link, 'source': p.notes.source if p.notes else ('announcement' if p.link else None),
        'builds': [{'build': b['build'], 'date': b['date'], 'file': b['file']} for b in p.builds],
        'sections': sections,
        'entities': ents,
        'key_changes': key_changes(ents),
        'extras': slim_extras(extras, cat, lambda: window_states(p)),
        'counts': counts,
        'line_counts': line_counts,
        **({'release': list(p.release)} if p.release else {}),
    }


def mark_unreleased(p: Patch, commit: str, changes: list[MChange], events: list[dict], cat: dict[str, dict]) -> None:
    """Work on heroes that are not in the game yet is not "hidden from the notes" — judged at the build the change
    shipped in: a hero revealed inside the window was still unreleased while tuned before the reveal (Paige, Doorman,
    Venator…: ~500 changes were "hidden", audit 2026-10-01). In a window without notes too: Nurse Harrow's boon
    tuning in Violet's release build (6790) had the eye while she was pre-release (data review 2026-10-17)."""
    commit_of = {row['build']: row['commit'] for row in p.builds if row.get('commit')}
    at: dict = {}

    def unreleased_at(builds) -> set[str]:
        out = set()
        for b in builds or [None]:
            key = commit_of.get(b, commit)
            if key not in at:
                at[key] = unreleased_heroes(key)
            out |= at[key]
        return out
    open_ = ('hidden', 'unannounced')
    for c in changes:
        owner = c.eid if c.file == 'heroes.vdata' else cat.get(ent_key(c), {}).get('owner')
        if c.status in open_ and owner and owner in unreleased_at(c.builds):
            c.status = 'unreleased'
    for ev in events:
        owner = ev['id'] if ev['file'] == 'heroes.vdata' else ev.get('owner')
        if ev['change']['status'] in open_ and owner and owner in unreleased_at([ev.get('build')]):
            ev['change']['status'] = 'unreleased'


def release_kit(hid: str, cat: dict[str, dict]) -> set[str]:
    """The entities a hero's release ships: the hero, what it owns (abilities, guns), every entry named after it
    (Violet's citadel_artist_strokeblocker, her sketch pickups pickup_artist_drawing_*) and the units its abilities
    make, which bear their names (Solomon's bishop piece is "Setup Bishop": data/overrides/unit_names.json)."""
    code = re.compile(rf'(?:^|_){re.escape(hid[len("hero_"):])}(?:_|$)')
    owned = {k for k, e in cat.items() if e.get('owner') == hid}
    names = {cat[k].get('name') for k in owned} - {None, ''}
    summons = {k for k, e in cat.items() if e['file'] == 'npc_units.vdata' and e.get('name') in names}
    return {f'heroes.vdata:{hid}'} | owned | summons | {k for k, e in cat.items() if code.search(e['id'])}


_HERO_NUMBERS = re.compile(r'^m_map(StartingStats|StandardLevelUpUpgrades|ScalingStats)\.')


def release_pass(heroes: list[str], changes: list[MChange], events: list[dict], cat: dict[str, dict]) -> None:
    """A hero's release window (pipeline.patches.release_windows): its announcement post names the hero, so the
    hero's development state turning Release is documented and its kit — the abilities, guns, summons and pickups
    that came with it, the stats it shipped with — is the release itself, described by that post, not "not in patch
    notes" (Violet's 18 rows, Baba's 19 had the eye; data review 2026-10-17). Everything else the window changed —
    other heroes' tuning, an edit shared by many entities — is what that post left out: hidden, the eye of any update
    with notes (Solomon's silent Move Piece rework sat unmarked among Violet's launch lines, its patch read 0% "not in
    notes" in the archive; review 2026-10-17, round 4). Only a window with no post at all is "unannounced".
    The hero's own numbers (`_HERO_NUMBERS`: base stats, per-boon growth, spirit scaling) are not the kit: the post
    names the hero, not its numbers, so they are hidden too; the kit slots ("Kit: Ability 1"), its role, complexity
    and sounds stay described (owner 2026-10-21, question 14)."""
    kit = set().union(*(release_kit(h, cat) for h in heroes))
    for c in changes:
        if c.shared or ent_key(c) not in kit:
            c.status = 'hidden'
        elif c.file == 'heroes.vdata' and c.path == _DEV_STATE:
            c.status = 'documented'
        elif c.file == 'heroes.vdata' and _HERO_NUMBERS.match(c.path):
            c.status = 'hidden'
        else:
            c.status = 'described'
    for ev in events:
        ev['change']['status'] = 'described' if f"{ev['file']}:{ev['id']}" in kit else 'hidden'


def unreleased_heroes(commit: str) -> set[str]:
    """Heroes not playable at that build (in development / disabled / pre-release)."""
    heroes = cache.vdata(commit, tracker.SCRIPTS + 'heroes.vdata')
    out = set()
    for hid, h in heroes.items():
        if not hid.startswith('hero_') or not isinstance(h, dict):
            continue
        state = h.get('m_eHeroDevelopmentState')
        if state is not None:
            released = state in RELEASED_STATES
        else:   # builds before the field existed
            released = not (str(h.get('m_bDisabled')).lower() in ('true', '1')
                            or str(h.get('m_bInDevelopment')).lower() in ('true', '1'))
        if not released:
            out.add(hid)
    return out


def documented_lines(p: Patch, row: dict, cat: dict[str, dict]) -> int:
    """How many of p's note lines this single build documents with exact numbers."""
    if not p.notes:
        return 0
    probe = Patch(p.id, p.title, p.date, p.notes, [row])
    commit = load_record(row['file'])['commit']
    tok = loc.tokens(commit)
    changes, _ = window_changes(probe, cat, tok)
    sections = annotate(probe, changes, cat, tok)
    return sum(1 for s in sections for ln in s['lines'] if ln['status'] == 'documented')


REASSIGN_MIN_LINES = 2
REASSIGN_MIN_SHARE = 0.05      # documented lines per gameplay field of the build


def reassign_ambiguous(patches: list[Patch], cat: dict[str, dict]) -> int:
    """Move boundary builds to the patch whose notes they match better."""
    moved = 0
    for row, prev, cur in patches_mod.ambiguous_builds(patches):
        if not (prev.notes and cur.notes):
            continue          # a synthetic (notes-less) patch keeps its own build
        a, b = documented_lines(prev, row, cat), documented_lines(cur, row, cat)
        home, other = (prev, cur) if row in prev.builds else (cur, prev)
        score_home = a if home is prev else b
        score_other = b if home is prev else a
        # a few lines that happen to match say nothing about a big build: City Never Sleeps
        # (build 6711, 1,400+ changes) matched 2 lines of the 09-16 notes and moved 13 days back
        need = max(REASSIGN_MIN_LINES, REASSIGN_MIN_SHARE * patches_mod.gameplay_fields(row))
        if score_other >= need and score_other > score_home and row in home.builds:
            home.builds.remove(row)
            other.builds.append(row)
            other.builds.sort(key=lambda r: r['date'])
            moved += 1
    return moved


# A notes-less window right after a changelog that carries this many of its numbered
# lines exactly is that changelog's update shipping late (2024-12-06 notes: 81 lines landed
# in the notes-less build 5433 of 12-14): merge the windows instead of calling it unannounced.
ABSORB_MIN = 10


def _late_count(p: Patch, data: dict, later: list[tuple[Patch, dict]], hero_name: dict[str, str]) -> int:
    n = 0
    for s in data['sections']:
        for ln in s['lines']:
            if ln['status'] != 'unmatched' or not ln.get('subject'):
                continue
            rest = ln['text'].split(':', 1)[1] if ':' in ln['text'][:48] else ln['text']
            pairs = parse_pairs(rest)
            if pairs and _late_hit(later, p, ln['subject'].lower(), pairs, expand_words(words(rest)), hero_name):
                n += 1
    return n


def absorb_late_windows(results: list[tuple[Patch, dict]], cat: dict[str, dict]) -> tuple[list, list[str]]:
    hero_name = {e['id']: e.get('name') or '' for e in cat.values() if e['file'] == 'heroes.vdata'}
    out, absorbed, i = [], [], 0
    while i < len(results):
        p, data = results[i]
        if i + 1 < len(results):
            q, qd = results[i + 1]
            # (never a hero's release window: its own announcement names it)
            if p.notes and not q.notes and not q.release and p.builds and _days(p.date, q.date) <= LATE_DAYS \
                    and _late_count(p, data, [(q, qd)], hero_name) >= ABSORB_MIN:
                p.builds = sorted(p.builds + q.builds, key=lambda b: b['date'])
                out.append((p, build_patch(p, cat)))
                absorbed.append(q.id)
                i += 2
                continue
        out.append((p, data))
        i += 1
    return out, absorbed


def run() -> None:
    cat = catalog.load()
    OUT.mkdir(parents=True, exist_ok=True)
    for old in list(OUT.glob('*.json')) + list(OUT.glob('*.json.gz')):
        old.unlink()
    index = []
    patches = group()
    print('re-assigned boundary builds:', reassign_ambiguous(patches, cat))
    results = [(p, build_patch(p, cat)) for p in patches]
    results, absorbed = absorb_late_windows(results, cat)
    print('notes-less windows merged into the changelog they implement:', absorbed)
    print('notes that landed in a later build:', late_landings(results, cat))
    print('lines repeated from a later patch (edited posts):', repeated_lines(results))
    print('lines about unmoved files (in the code):', code_lines(results))
    for p, data in results:
        jsonio.dump(OUT / f'{p.id}.json.gz', data)
        index.append({'id': p.id, 'title': p.title, 'date': p.date[:10], 'builds': len(p.builds),
                      'counts': data['counts'], 'line_counts': data['line_counts'], 'has_notes': p.has_notes,
                      **({'release': list(p.release)} if p.release else {})})
        print(p.id, p.title[:40], len(p.builds), 'builds', data['counts'], data['line_counts'])
    jsonio.dump(OUT / 'index.json', index, indent=1)


if __name__ == '__main__':
    run()
