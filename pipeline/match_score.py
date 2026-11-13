"""How a patch-note line is scored against the changes of a window: who it names (`Subject`, `name_index`,
`resolve_subject`), which words say what a number is, and the score of one change for a line (`score`, `pct_close`,
`list_hits`, `mismatch_field`). Split out of `match` 2026-11-13; every name is re-exported there."""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

from . import game_map, loc
from . import match_rules as rules
from .classify import GAMEPLAY_CATS
from .match_values import (APPROX, GENERIC_WORDS, MChange, _BY_RE, _PARENS, _label_tokens, _tokens, exact_pair,
                           expand_words, granted_pair, list_match, num, parse_pairs, value_matches, words)


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
