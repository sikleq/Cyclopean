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

from . import cache, catalog, jsonio, labels, loc, semantics, tracker
from . import match_rules as rules
from . import patches as patches_mod
from .classify import category
from .patches import Patch, group

OUT = tracker.ROOT / 'data' / 'patches'
BUILDS = tracker.ROOT / 'data' / 'builds'
GAMEPLAY_CATS = ('balance', 'mechanic', 'availability')

_NUM = r'[-+]?\d*\.?\d+'
# "from 50% to 40%", "from +40 degrees angle to +25", "from 18m->54m to 16m->48m",
# "from 100+1.5 to 120+1.75" (base + spirit scaling)
_COMPOUND = rf'{_NUM}(?:\s*[a-z%]*\s*(?:->|→|\+|/)\s*{_NUM})*'     # "6800/9350/11900" = per-phase values
_PAIR_RE = re.compile(
    # up to 6 words between: "from 6% Max Health as spirit damage to 6.5%"
    rf'from\s+(?P<a>{_COMPOUND})(?:\s*[a-z%°.\'/]+){{0,6}}?\s*(?:to|->|→)\s*(?P<b>{_COMPOUND})',
    re.I)
# "Fixed …" / "Hero: Fixed …" — not "a fixed amount of souls"
_FIX_RE = re.compile(r'^(fixed|fix(es)?)\b|:\s*(fixed|fix(es)?)\b', re.I)
SYNONYMS = {
    'bounty': {'gold', 'reward', 'souls', 'bounty'},
    'guardian': {'tier', 'boss', 'guardian'},
    'walker': {'tier', 'boss', 'walker'},
    'respawn': {'spawn', 'respawn'},
    'breakables': {'breakable', 'spawn'},
    'urn': {'idol', 'urn'},
    'rejuvenator': {'rejuv', 'rejuvenator'},
}
_SYNONYMS = rules.stemmed_synonyms(SYNONYMS)       # as words() writes them ('breakables' -> 'breakable')
_ARROW_RE = re.compile(rf'(?P<a>{_NUM})\s*[a-z%]*\s*(?:->|→)\s*(?P<b>{_NUM})', re.I)
_BY_RE = re.compile(rf'(increased|reduced|decreased|lowered|raised)\s+by\s+~?(?P<p>{_NUM})\s*%', re.I)
_WORD_RE = re.compile(r'[a-z]{3,}')
_TIER_RE = re.compile(r'\bT([1-3])\b')
_STOP = {'the', 'and', 'from', 'now', 'with', 'for', 'increased', 'reduced', 'decreased', 'per', 'base',
         'damage', 'when', 'that', 'this', 'are', 'was', 'has', 'into', 'than', 'also', 'its', 'you', 'your'}
WEAPON_WORDS = {'gun', 'weapon', 'bullet', 'bullets', 'clip', 'ammo', 'reload', 'fire', 'falloff', 'pellets',
                'spread', 'alt', 'altfire', 'headshot', 'velocity'}
# words too common to tie a line to one field on their own
GENERIC_WORDS = {'damage', 'bounty', 'soul', 'souls', 'gold', 'health', 'value', 'bonu', 'bonus', 'amount', 'time',
                 'rate', 'hero', 'heroe', 'trooper', 'walker', 'guardian', 'patron', 'shrine', 'boss', 'attack',
                 'player', 'enemy', 'nearby', 'max', 'min', 'resist', 'resistance', 'bullet', 'spirit', 'weapon',
                 'ability', 'abilitie', 'also', 'longer', 'more', 'less', 'able', 'will', 'when', 'target', 'unit'}
SYNONYM_ONLY = {'armor', 'resistance', 'healing', 'time', 'cd'}
HERO_STAT_WORDS = {'health', 'regen', 'move', 'sprint', 'stamina', 'boon', 'melee', 'resist', 'dash', 'speed'}
GENERAL_KEYWORDS = {
    'slow': re.compile(r'slow', re.I),
    'ground dash': re.compile(r'GroundDash', re.I),
    'bounty': re.compile(r'(bounty|gold|reward)', re.I),
    'respawn': re.compile(r'(respawn|spawn_time)', re.I),
}


@dataclass
class MChange:
    file: str
    eid: str
    path: str
    op: str
    old: object
    new: object
    cat: str
    kind: str
    owner: str | None
    label: str
    meters: bool
    builds: list = field(default_factory=list)
    shared: bool = False
    status: str = 'hidden'
    lines: list = field(default_factory=list)
    chain: list = field(default_factory=list)     # every value the field took inside the window
    drawback: bool = False                        # the holder's own downside (enrich.drawbacks)
    neg_base: bool = False                        # a bonus to a property stored negative (enrich.negative_props)
    unit: str = ''                                # what the tooltip prints after the value ('s', '%', 'm')
    invert: bool = False                          # a rate the game shows as a time (stamina per second -> cooldown)
    scale: float = 1.0                            # the patch's boon rescale for this per-boon field (old / new count)
    speed_m: bool = False                         # a speed written "20m": shown m/s (semantics.M_SPEED), display only
    # what the page prints (pipeline.labels: one label / unit / sign per field over its history); `label`
    # stays the window's own wording, which the note lines of that time are matched against
    shown: str = ''
    sign: str = ''                                # '-': the tooltip's own minus (an enemy slow), shown as a size
    retyped: bool = False                         # the property's provided type flipped with its sign (Riposte)

    @property
    def key(self) -> str:
        return f'{self.file}:{self.eid}:{self.path}'

    def steps(self) -> list[tuple]:
        """(old, new) pairs a note line may describe: each build-to-build step
        and the window total ("100 -> 75" and later "75 -> 125")."""
        chain = self.chain or [self.old, self.new]
        pairs = list(zip(chain, chain[1:]))
        if (chain[0], chain[-1]) not in pairs:
            pairs.append((chain[0], chain[-1]))
        if self.scale != 1.0:
            # the patch rescaled every per-boon value (rules.boon_rescale): the notes quote the new value
            # in the old scale ("Kelvin: Bullet damage growth 1.2 -> 0.9" is 1.2 -> 0.707 in the files)
            pairs += [(o, num(n) / self.scale) for o, n in pairs if num(n) is not None]
        return pairs


def num(v):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = re.match(rf'^\s*({_NUM})\s*[a-z%]*\s*$', str(v), re.I)
    return float(m.group(1)) if m else None


EXACT = 0.005      # relative tolerance for "the same number"
APPROX = 0.10      # the notes round: 0.54 -> "0.5", 31.5 -> "32", 53.5 m/s -> "53m/s"


def close(a: float | None, b: float | None, rel: float = EXACT) -> bool:
    if a is None or b is None:
        return False
    # relative only: an absolute 0.011 made 0.06 -> 0.05 match 26 unrelated fields (audit 2026-10-01)
    return abs(a - b) <= max(1e-6, rel * abs(b))


_LENGTHY = re.compile(r'(range|radius|distance|speed|velocity|width|height|length|falloff)', re.I)
_RATE_LIKE = re.compile(r'(rate|interval|recovery|regen|per second|cycle)', re.I)


def value_matches(v, x: float, meters=False, rel: float = EXACT) -> bool:
    """Does data value v equal the notes' number x under a display transform the FIELD allows?
    raw, magnitude; a fraction as a percent (|v| <= 5); engine units as metres for lengths and
    speeds; a rate as an interval for rate-like fields. `meters` is the MChange (or a bool for
    "may be in engine units"). Every transform for every field linked "Walkers Resistance 0/8/16%"
    to Health 9000 -> 7000 and "Heavy Melee cooldown 0.9s" to a damage scale 35 (audit 2026-10-01)."""
    n = num(v)
    if n is None:
        return False
    if isinstance(meters, MChange):            # the change itself: its field decides the transforms
        name = meters.label or meters.path
        # engine units only for a field that is engine units: not a share, not one already in metres
        not_engine = (semantics.FRACTION, semantics.METRES, semantics.MPS)
        units = (bool(meters.meters) and meters.meters not in not_engine
                 or not meters.meters and bool(_LENGTHY.search(name)))
        inverse = bool(_RATE_LIKE.search(name))
    else:
        units, inverse = bool(meters), True
    candidates = [n, abs(n)]
    if abs(n) <= 5:
        candidates += [n * 100, abs(n) * 100]
    if units:
        candidates.append(n / semantics.UNITS_PER_METER)
    if inverse and n not in (0, 0.0):
        candidates.append(1 / abs(n))      # "stamina cooldown 5s" vs regen 0.2/s
    return any(close(c, abs(x), rel) or close(c, x, rel) for c in candidates)


def exact_pair(c: MChange, pairs) -> bool:
    for a, b in pairs:
        if any(value_matches(o, a, c) and value_matches(n, b, c) for o, n in c.steps()):
            return True
        if c.op == 'add' and value_matches(c.new, b, c):
            return True
        if c.op == 'remove' and value_matches(c.old, a, c):
            return True
    return False


def shown_in_meters(c: MChange, pairs) -> bool:
    """The notes quote this value in metres (source units ÷ 39.37)."""
    for a, b in pairs:
        for v, x in ((c.old, a), (c.new, b)):
            n = num(v)
            if n is not None and abs(n) > 50 and close(abs(n) / semantics.UNITS_PER_METER, abs(x), APPROX):
                return True
    return False


def data_values(c: MChange, pairs) -> list[str]:
    meters = c.meters or shown_in_meters(c, pairs)
    return [semantics.display_value(num(c.old), meters), semantics.display_value(num(c.new), meters)]


def half_match(c: MChange, pairs) -> bool:
    """One side of a 'from A to B' agrees with the files: the property is
    identified, so a disagreement on the other side is a real mismatch."""
    return any(value_matches(o, a, c, APPROX) or value_matches(n, b, c, APPROX)
               for a, b in pairs for o, n in c.steps())


def expand_words(ws: set[str]) -> set[str]:
    out = set(ws)
    for w in ws:
        out |= _SYNONYMS.get(w, set())
    return out


# "5,175" / "12,000" but not the unspaced list "160,180,200"
_THOUSANDS = re.compile(r'(?<![\d,])(\d{1,3}),(\d{3})(?![\d,])')


def parse_pairs(text: str) -> list[tuple[float, float]]:
    # "from 5,175 to 7,000": thousands separators; list commas ("5, 6") keep their space
    text = _THOUSANDS.sub(r'\1\2', text)
    pairs = []
    for m in _PAIR_RE.finditer(text):
        a = [float(x) for x in re.findall(_NUM, m.group('a'))]
        b = [float(x) for x in re.findall(_NUM, m.group('b'))]
        if len(a) == len(b):
            pairs.extend(zip(a, b))
        elif a and b:
            pairs.append((a[0], b[0]))
    if not pairs:
        for m in _ARROW_RE.finditer(text):
            pairs.append((float(m.group('a')), float(m.group('b'))))
    if not pairs:
        # "level 2 drops now happen at 15 minutes instead of 20": the new value first
        for m in _INSTEAD_RE.finditer(text):
            pairs.append((float(m.group('a')), float(m.group('b'))))
    return pairs


_INSTEAD_RE = re.compile(rf'(?P<b>{_NUM})\s*[a-z%]*\s+instead of\s+(?P<a>{_NUM})', re.I)


# "T2 is now +50 Damage" is a value; "Luggage Cart is now 20% larger" is a change: "is now" needs the "+"
_GRANT = re.compile(r'\b(?P<neg>no longer\s+)?(?:grants?|gives?|gains?|provides?|has|have|deals?|applies?|adds?|'
                    r'(?:is|are)\s+now(?=\s+\+))\s+'
                    rf'(?:an?\s+|bonus\s+|extra\s+)?(?P<v>[-+]?{_NUM})', re.I)


def granted_pair(text: str) -> list[tuple[float, float]]:
    """[(0, N)] for "now grants +N …", [(N, 0)] for "no longer grants +N …" (one number only — a tier
    name "T3" and an aside in parentheses are no numbers: "T3 no longer grants +100% Ammo")."""
    bare = _TIER_NAME.sub(' ', _PARENS.sub(' ', text))
    if len(re.findall(_NUM, bare)) != 1:
        return []
    m = _GRANT.search(bare) or _NOW_BY.search(bare)
    if not m:
        return []
    v = abs(float(m.group('v')))
    return [(v, 0.0)] if m.groupdict().get('neg') else [(0.0, v)]


_TIER_NAME = re.compile(r'\bT[1-4]\b')
# "Crow Familiar now reduces bullet armor by 6%", "Barriers now last for 16s", "T2 is now +50 Damage"
_NOW_BY = re.compile(rf'\bnow\s+(?:also\s+)?(?:(?:reduces?|increases?|slows?|amplifies?|lowers?|raises?)\b.*?\bby\s+'
                     rf'|lasts?\s+(?:for\s+)?)~?(?P<v>[-+]?{_NUM})', re.I)


def words(text: str) -> set[str]:
    """Content words, lightly stemmed (pellet/pellets, charge/charges)."""
    out = set()
    for w in _WORD_RE.findall(text.lower()):
        if w in _STOP:
            continue
        out.add(w[:-1] if len(w) > 4 and w.endswith('s') and not w.endswith('ss') else w)
    if _HP.search(text):
        out.add('health')            # "Walker HP" — two letters the word pattern skips
    for joined, parts in _COMPOUNDS:
        if joined in out:
            out |= parts             # "Movespeed scaling" names Move Speed per Spirit
    return out


_COMPOUNDS = (('movespeed', {'move', 'speed'}), ('firerate', {'fire', 'rate'}))


_HP = re.compile(r'\bhp\b', re.I)


# ---- window merge ---------------------------------------------------------

def load_record(file_name: str) -> dict:
    return jsonio.load(BUILDS / file_name)


def merge_ops(first: str, then: str) -> str:
    """One field's op across the window's builds. A field added then tuned is still NEW (it was
    shown as '— → 0.75' CHANGED), tuned then removed is DEL ('16.2 → —'); added then removed
    never shipped and becomes a no-op change (old == new == None, dropped below)."""
    if first == 'add':
        return 'change' if then == 'remove' else 'add'
    if first == 'remove':
        return 'change' if then == 'add' else 'remove'
    return 'remove' if then == 'remove' else 'change'


_PROVIDED_TYPE = re.compile(r'^m_mapAbilityProperties\.([^.]+)\.m_eProvidedPropertyType$')


def mark_retyped(changes: list[MChange]) -> None:
    """A property whose provided type flipped in the window (REDUCTION_PERCENT → INCREASE_PERCENT) flips
    the sign of its numbers with it: Riposte's "Melee Resist −22% → 22%" is the same resist written the
    other way round (`retyped` -> change_json 'same'). A sign flip without it stays a change."""
    retyped = {(c.file, c.eid, m.group(1)) for c in changes if c.op == 'change'
               for m in [_PROVIDED_TYPE.match(c.path)] if m}
    if not retyped:
        return
    for c in changes:
        if (c.file, c.eid, semantics.property_name(c.path)) in retyped and not _PROVIDED_TYPE.match(c.path):
            c.retyped = True


def window_changes(p: Patch, cat: dict[str, dict], tok: dict[str, str]) -> tuple[list[MChange], dict]:
    """Merge the builds of a window. Entities added inside the window are not
    diffed field by field (their whole data is "new"): they become one
    'entity added' change each."""
    merged: dict[str, MChange] = {}
    extras = {'loc': [], 'convars': [], 'assets': [], 'entities_added': [], 'entities_removed': [],
              'entities_returned': []}
    added_here: set[str] = set()
    for row in p.builds:
        rec = load_record(row['file'])
        for e in rec['entities']:
            targets_default = [e['id']]
            ekey = f"{e['file']}:{e['id']}"
            if e['status'] in ('added', 'removed', 'returned'):
                if e['status'] == 'added':
                    added_here.add(ekey)
                ce = cat.get(ekey, {})
                extras[f"entities_{e['status']}"].append({
                    'file': e['file'], 'id': e['id'], 'build': rec['build'],
                    'name': event_name(e, ce), 'kind': e.get('kind'), 'owner': e.get('owner'),
                    'units': ce.get('units'), 'gameplay': _gameplay_entity(e)})
                if e['status'] != 'returned':
                    continue                  # a returned entity's fields differ from its last version: diffed below
            if ekey in added_here:
                continue
            for c in e['changes']:
                for tid in (c.get('targets') or targets_default):
                    if f"{e['file']}:{tid}" in added_here:
                        continue
                    ce = cat.get(f"{e['file']}:{tid}", {})
                    key = f"{e['file']}:{tid}:{c['path']}"
                    mc = merged.get(key)
                    if mc is None:
                        d = semantics.describe(c['path'], tok, tid, ce.get('kind', ''), c.get('scaled_by'),
                                               c.get('loc_token'))
                        cn = labels.canonical(key, d)
                        merged[key] = MChange(
                            e['file'], tid, c['path'], c['op'], c.get('old'), c.get('new'), c['cat'],
                            # an NPC's ability (catalog 'units': Walker's Stomp) is judged as its unit: UP / DOWN
                            'unit' if ce.get('units') else ce.get('kind', ''), ce.get('owner'), d['label'], d['meters'],
                            [rec['build']], bool(c.get('targets')), chain=[c.get('old'), c.get('new')],
                            drawback=bool(c.get('drawback')), neg_base=bool(c.get('neg_base')),
                            unit=labels.display_unit(d, cn), invert=bool(d.get('invert')),
                            speed_m=bool(d.get('speed_m')), shown=cn['label'], sign=cn['sign'])
                    else:
                        mc.new = c.get('new')
                        mc.chain.append(c.get('new'))
                        mc.builds.append(rec['build'])
                        mc.op = merge_ops(mc.op, c['op'])
        extras['loc'].extend(dict(x, build=rec['build']) for x in rec.get('loc') or [])
        extras['convars'].extend(dict(x, build=rec['build']) for x in rec.get('convars') or [])
        if rec.get('assets'):
            extras['assets'].append({'build': rec['build'], **rec['assets']})
    changes = [c for c in merged.values() if not (c.op == 'change' and c.old == c.new)]
    mark_retyped(changes)
    # console variables take part in matching ("Respawn time … from 35s to 38s")
    for cv in extras['convars']:
        if cv.get('op') != 'change' or num(cv.get('old')) is None or num(cv.get('new')) is None:
            continue
        label = cv['name'].replace('citadel_', '').replace('_', ' ')
        changes.append(MChange('convars', cv['name'], cv['name'], 'change', cv['old'], cv['new'], 'balance',
                               'global', None, label, False, [cv['build']]))
    # an entity added and removed within one window never shipped; one removed and back within one
    # window (or back and removed again) is where it started: only its field changes remain
    removed = {f"{x['file']}:{x['id']}" for x in extras['entities_removed']}
    returned = {f"{x['file']}:{x['id']}" for x in extras['entities_returned']}
    both = (added_here | returned) & removed
    for bucket in ('entities_added', 'entities_removed', 'entities_returned'):
        extras[bucket] = [x for x in extras[bucket] if f"{x['file']}:{x['id']}" not in both]
    return changes, extras


# ---- line matching --------------------------------------------------------

@dataclass
class Subject:
    ids: set
    name: str
    kind: str


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


_PARENS = re.compile(r'\([^)]*\)')
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
    return Subject(set(keys), prefix, cat[keys[0]].get('kind', ''))


def ent_key(c: MChange) -> str:
    return f'{c.file}:{c.eid}'


def label_words(c: MChange) -> set[str]:
    out = rules.expand_label_words(words(c.label))
    return out | {'growth'} if rules.GROWTH_LABEL.search(c.label or '') else out


_MINUTES = re.compile(r'\b(minutes?|mins?)\b', re.I)
_BASE_DAMAGE = re.compile(r'^\s*(base|gun)\s+damage\b', re.I)
_SPAWN_TIMER = re.compile(r'\b(spawns?|respawns?|spawn time|interval)\b', re.I)
_SECONDS = re.compile(r'\d\s*(s|sec|secs|seconds?)\b', re.I)
_UP_VERB = re.compile(r'\b(increas\w*|rais\w*|more|higher|boost\w*)\b', re.I)
_DOWN_VERB = re.compile(r'\b(reduc\w*|decreas\w*|lower\w*|less|cut)\b', re.I)
_TIME_LIKE = re.compile(r'(time|cooldown|interval|delay|cost|duration)', re.I)


def verb_sign(text: str) -> int:
    """+1 the line says up, -1 down, 0 neither or both."""
    up, down = bool(_UP_VERB.search(text)), bool(_DOWN_VERB.search(text))
    return 1 if up and not down else -1 if down and not up else 0


def pct_close(c: MChange, by_pct: float, sign: int = 0, rate_line: bool = False) -> bool:
    """The field moved by the line's percent — the same way the line says: "Walker HP increased by
    40%" is not a cooldown cut by 40% (audit 2026-10-01: 115 links ran the wrong way). A rate on the
    line may move a time field the other way (fire rate up = interval down)."""
    for o, n in c.steps():
        o, n = num(o), num(n)
        if not o or n is None or abs(abs(n / o - 1) * 100 - by_pct) > max(1.0, 0.1 * by_pct):
            continue
        moved = 1 if abs(n) > abs(o) else -1
        if sign and moved != sign and not (rate_line and _TIME_LIKE.search(c.label or c.path)):
            continue
        return True
    return False


_LIST_SPLIT = re.compile(r',\s*(?:and\s+)?|\s+and\s+|\s*&\s*|/')
_PART_STOP = {'the', 'and', 'its', 'of', 'to', 'for', 'all', 'value', 'values', 'base', 'now', 'their'}
_PART_WORD = re.compile(r'[a-z]{2,}')


def _tokens(text: str) -> set[str]:
    """Words of a listed property or a field label, 'damage' kept (words() drops it as too common):
    "Siphon Life damage and spirit scaling" names two fields."""
    low = text.lower()
    out = {rules.stem(w) for w in _PART_WORD.findall(low) if w not in _PART_STOP}
    if 'hp' in out:
        out = (out - {'hp'}) | {'health'}
    return out


_GROWTH_WORDS = {'growth', 'boon', 'scaling', 'minute'}


def _label_tokens(c: MChange) -> set[str]:
    out = rules.expand_label_words(_tokens(c.label))
    return out | {'growth'} if rules.GROWTH_LABEL.search(c.label or '') else out


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
    moved = [c for c in pool if pct_close(c, by_pct, sign, rate)]
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


def pair_hits(scored: list[tuple[int, MChange]], pairs, least: int) -> list[MChange]:
    """The best-scoring fields of each number pair on its own (scored: [(score, change)])."""
    out: list[MChange] = []
    for a, b in pairs:
        cands = [(s, c) for s, c in scored if s >= least
                 and any(value_matches(o, a, c, APPROX) and value_matches(n, b, c, APPROX) for o, n in c.steps())]
        top = max((s for s, _ in cands), default=None)
        out += [c for s, c in cands if s == top and c not in out]
    return out


def score(c: MChange, text: str, pairs, by_pct, lw: set[str], tier: int | None, ability_hits: set[str],
          granted: bool = False) -> int:
    """`granted`: the pairs come from "now grants +N" (0 -> N) / "no longer grants +N" (N -> 0)."""
    s = 0
    steps = c.steps()
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
    if by_pct is not None and pct_close(c, by_pct, verb_sign(text), bool(re.search(r'rate|speed', text, re.I))):
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
    sections = []
    for sec in (p.notes.sections if p.notes else []):
        out_lines = []
        head = None
        for text in sec.lines:
            h = heading(text, idx)
            if h:
                # the 2025 layout: a bare 'Sinclair' line heads the lines below it
                head = h
                out_lines.append({'text': text, 'subject': h, 'status': 'heading', 'changes': []})
                continue
            own_prefix = ':' in text[:48] and resolve_subject(text.split(':', 1)[0], idx, cat)
            probe = f'{head}: {text}' if head and not own_prefix else text
            res = annotate_line(probe, changes, by_ent, idx, cat, tok, rescale)
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


def heading(text: str, idx: dict[str, list[str]]) -> str | None:
    """A line that is only an entity name ('Boundless Spirit') is a sub-heading."""
    t = text.strip().rstrip(':').strip()
    if not t or len(t) > _HEADING_MAX or ':' in t or re.search(r'\d', t):
        return None
    return t if idx.get(t.lower()) else None


def post_pass(changes: list[MChange], by_ent: dict[str, list[MChange]]) -> None:
    """Rules that look at matches as a whole (audit patterns 2 and 7)."""
    for c in list(changes):
        if c.status not in ('documented', 'described') or not c.lines:
            continue
        line = c.lines[0]
        # 7: a feature added in one go: the matched field's siblings (added/removed together)
        root = rules.cluster_root(c.path)
        for sib in by_ent.get(ent_key(c), []):
            if sib.status == 'hidden' and sib.cat in GAMEPLAY_CATS and sib.op in ('add', 'remove') \
                    and rules.cluster_root(sib.path) == root:
                sib.status = 'described'
                sib.lines.append(line)
        # 2: "(affects upgrades)": items built from this one moved the same way
        if c.status == 'documented' and rules.AFFECTS_UPGRADES_RE.search(line):
            for other in changes:
                if other.status == 'hidden' and other.path == c.path and other.old == c.old and other.new == c.new:
                    other.status = 'described'
                    other.lines.append(line)


def annotate_line(text, changes, by_ent, idx, cat, tok, rescale=None) -> dict:
    subject = None
    rest = text
    if ':' in text[:48]:
        prefix, rest = text.split(':', 1)
        subject = resolve_subject(prefix, idx, cat)
    lw = expand_words(words(rest))
    pairs = parse_pairs(rest)
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
    m = _BY_RE.search(rest)
    by_pct = float(m.group('p')) if m else None
    by_at = m.start() if m else None
    tm = _TIER_RE.search(rest)
    tier = int(tm.group(1)) if tm else None
    result = {'text': text, 'subject': subject.name if subject else None, 'status': 'unmatched', 'changes': []}

    if not subject:
        if not pairs and by_pct is None and rules.untracked_topic(text) not in (None, 'visual'):
            # sound / interface / map words first: "Lowered volumes for UI death notification sounds
            # and respawn music" is not about respawn (annotate() tags it untracked) — P12; a bug fix
            # stays a fix ("…caused audio bugs as well"); not "visual": "Guardian melee no longer has a
            # splash range much larger than its visuals" is gameplay
            return _fix_or(result, text)
        covered = (rules.boon_lines(text, changes, rescale, num) or rules.global_line(text, changes, cat, num)
                   or rules.global_delta_line(text, changes, cat, num))
        if covered:
            return _link(result, covered, text, 'described')
        # "Walker bounty increased by 5%": the unit is named inside the line; failing a common word,
        # an entity's own name ("Medic Pack ally search radius from 30 to 35")
        aliased = inline_alias(text, idx)
        if aliased:
            subject = Subject(aliased, None, 'alias_inline')
        else:
            named = inline_names(text, idx, cat, by_ent)
            if named:
                subject = Subject(named, None, 'name_inline')

    if subject:
        # sorted: set order changes between runs (hash randomisation) -> unstable output
        pool = [c for k in sorted(subject.ids) for c in by_ent.get(k, [])]
    else:
        pool = changes
    ability_hits = set()
    if subject and subject.kind == 'hero':
        low = rest.lower()
        for k in subject.ids:
            e = cat.get(k, {})
            nm = loc.plain(loc.entity_name(tok, e.get('id', ''), e.get('owner'))).lower()
            if nm and len(nm) > 2 and any(v in low for v in rules.name_variants(nm)):
                ability_hits.add(k)
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

    if (pairs or by_pct is not None) and pool:
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
        scored, best = rank(pool, ability_hits)
        if not enough(best) and subject and subject.kind == 'name_inline':
            # the name was a coincidence ("Gun Powerup … Fire Rate" names the old item "Fire Rate"):
            # the whole patch, as for a line without a subject
            pool, ability_hits = [c for c in changes if c.cat in GAMEPLAY_CATS], set()
            scored, best = rank(pool, ability_hits)
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
            for c in hits:
                c.status = 'documented'
                c.lines.append(text)
                if not granted:          # "now grants +75" keeps the NEW value, not an invented 0 -> 75
                    _old_from_notes(c, pairs, text, pool)
            # a "now grants +N" value is stated exactly; its invented 0 is not a rounding
            rounded = pairs and not granted and not any(exact_pair(c, pairs) for c in hits)
            result['status'] = 'rounded' if rounded else 'documented'
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
        return bool(words(c.label) & specific) or bool(label_words(c) & specific - SYNONYM_ONLY) or bool(flags)

    def named_whole(c: MChange) -> bool:
        """Every word of the label is in the line, common ones too: "Fury Trance: Active Bullet Resistance
        changed to Spirit Resistance" names Bullet Resist and Spirit Resist. The subject's own fields only
        (a hero line: the ability it names)."""
        core = words(c.label or '') - _LABEL_FILLER
        # two words at least, or one of its own: "Bullet Damage" is just "bullet" (Afterburn "… each bullet")
        enough = len(core) >= 2 or bool(core - GENERIC_WORDS)
        return (enough and all(w in lw or rules.expand_label_words({w}) & lw for w in core)
                and (subject.kind != 'hero' or ent_key(c) in ability_hits))

    if subject.kind in ('alias_inline', 'name_inline'):
        # a unit merely named inside a sentence: link only on the field's own words (not a synonym:
        # "Continuous interior from jungle area to the walker" is not the aura radius) and never from
        # a line about sounds or looks ("Updated Mo & Krill Burrow … end sounds" is not falloff end)
        if pairs or _PRESENTATION_LINE.search(text):
            return result
        linked = [c for c in pool if words(c.label) & specific]
        return _link(result, linked, text, 'described') if linked else result
    # 3: "T2 changed from 'A' to 'B'" / "T3 also increases radius": that tier's fields of the ability
    if tier is not None:
        scope = [c for c in pool if (not ability_hits or ent_key(c) in ability_hits)
                 and re.match(rf'T{tier}:', c.label)]
        topical = [c for c in scope if on_topic(c)]
        whole_tier = re.search(r'changed from|reworked|replaced|swapped', text, re.I)
        chosen = topical or (scope if whole_tier else [])
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
        fallback = [c for c in pool if ent_key(c) in ability_hits and c.cat == 'mechanic']
    if _REMOVED_LINE.search(text):
        # "Soul Rebirth: Removed from the game" is its Disabled false -> true
        gone = [c for c in pool if c.cat == 'availability'
                and (subject.kind != 'hero' or not ability_hits or ent_key(c) in ability_hits)]
        if gone:
            return _link(result, gone, text, 'described')
    linked = [c for c in pool if on_topic(c) or named_whole(c)]
    # the ability the line names, when it has such a field: "Siphon Life range now scales…" is not
    # Seismic Impact's collide radius
    named = [c for c in linked if ent_key(c) in ability_hits]
    linked = named or linked
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
    if linked:
        return _link(result, linked, text, 'described')
    return result


_REMOVED_LINE = re.compile(r'\b(removed from the (game|shop)|(is|are|now) disabled|no longer (available|in the shop))\b',
                           re.I)
_FLAG_PREFIX = re.compile(r'^(CITADEL_ABILITY_BEHAVIOR_|CITADEL_UNIT_TARGET_|CITADEL_|MODIFIER_STATE_|MODIFIER_)')


def flag_words(c: MChange) -> set[str]:
    """The words of the flags a flag field gained or lost (Behaviour, Can target, Interrupted by…)."""
    leaf = c.path.rsplit('.', 1)[-1]
    # a modifier's attributes too: "Multiple instances stack" = MODIFIER_ATTRIBUTE_MULTIPLE (Slice and Dice)
    if leaf not in semantics.FLAG_FIELDS and leaf != 'm_nAttributes':
        return set()
    split = lambda v: {f.strip() for f in str(v or '').split('|') if f.strip()}      # noqa: E731
    moved = split(c.old) ^ split(c.new)
    out = set().union(*(words(_FLAG_PREFIX.sub('', f).replace('_', ' ')) for f in moved)) if moved else set()
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


def general_line(text: str, changes: list[MChange], cat: dict | None = None) -> dict | None:
    """Kept for callers/tests: global lines ('All move slow values reduced by ~20% globally')."""
    covered = rules.global_line(text, changes, cat or {}, num)
    if not covered:
        return None
    for c in covered:
        if c.status == 'hidden':
            c.status = 'described'
        c.lines.append(text)
    return {'status': 'described', 'changes': [c.key for c in covered]}


def _fix_or(result: dict, text: str) -> dict:
    """Bug-fix lines rarely change data: tag them instead of calling them unmatched."""
    if result['status'] == 'unmatched' and _FIX_RE.search(text):
        result['status'] = 'fix'
    return result


# ---- output -----------------------------------------------------------------

_SWAP_LINE = re.compile(r'changed from\s+["“]|\bnow\b.*\binstead of\b|\breplaced\b', re.I)


def _old_from_notes(c: MChange, pairs: list[tuple[float, float]], text: str = '',
                    siblings: list[MChange] | None = None) -> None:
    """A field that appeared with the value Valve says it was raised TO: before, the game used its
    default, and the notes name it ("Headshot stack count increased from +2 to +3" while the files
    only gained HeadshotStacks = 3). The line's old value makes it a change (BUFF/NERF), not a NEW.
    Not on a line that swaps one bonus for another ('T2 changed from "-12s Cooldown" to …'), nor when
    the entity lost a field holding that old value — then A belonged to the other field (audit
    2026-10-01: ~25 invented "was → now" such as "T2: Cooldown 12 → −15")."""
    if c.op != 'add' or c.old is not None or c.meters or num(c.new) is None or _SWAP_LINE.search(text):
        return
    removed_values = {num(s.old) for s in siblings or () if s.eid == c.eid and s.op == 'remove' and num(s.old) is not None}
    olds = {a for a, b in pairs if abs(b - num(c.new)) < 1e-9 and a != b}
    if len(olds) == 1 and not any(abs(a - r) < 1e-9 for a in olds for r in removed_values):
        c.old = olds.pop()
        c.op = 'change'


def change_json(c: MChange) -> dict:
    kind = c.kind or ''
    dirn, pct = semantics.direction(c.path, num(c.old), num(c.new), kind, c.drawback, c.neg_base)
    shown = semantics.M_SPEED if c.speed_m and not c.meters else c.meters
    if not c.meters and semantics.length_in_units(c.path, c.unit, (c.old, c.new)):
        shown = True                  # a property length no build gave a unit: engine units, shown in metres
    magnitude = c.sign == '-'
    return {
        'key': c.key, 'file': c.file, 'id': c.eid, 'path': c.path, 'op': c.op, 'cat': c.cat,
        'label': c.shown or c.label,
        'old_s': semantics.show(c.old, shown, c.unit, c.invert, magnitude),
        'new_s': semantics.show(c.new, shown, c.unit, c.invert, magnitude),
        'dir': dirn, 'pct': None if pct is None else round(pct, 1), 'grad': semantics.gradient(pct),
        'status': c.status, 'builds': sorted(set(c.builds)), 'shared': c.shared,
        'same': semantics.reencoded(c.old, c.new, c.path) or (c.retyped and semantics.sign_flip(c.old, c.new)),
    }


# 'shared': every hero's ability (jump, dash…), ownerless since 2026-10-04 — still an event of its own
ENTITY_EVENT_KINDS = {'hero', 'item', 'ability', 'weapon', 'trooper', 'building', 'neutral', 'unit', 'shared'}
# kinds that count only with proof they matter (audit B12, 2026-10-02: 102 removed abilities such
# as Splatapult, 85 new pickups such as the permanent ammo powerup and game-rule blocks such as
# m_RejuvParams were on no patch page): an ability with a name or an NPC that binds it; a rules
# entry with gameplay fields (removed: a gameplay-like id). Not a hero's melee: its name is the shared
# "Melee" string, and the hero and its gun already make the event
EVENT_IF_NAMED = {'ability_other'}


def event_name(e: dict, ce: dict) -> str | None:
    """A removed ability loses its text in the build that removes it: the catalog keeps the name it
    had in game (Witching Hour, Pulse Cannon — 29 events lost until review 2026-10-02)."""
    name = e.get('name')
    return ce.get('name') or name if not name or name == e['id'] else name


def _gameplay_entity(e: dict) -> bool:
    if e['status'] == 'removed':        # a removed entity carries no fields: judge its id
        return e['file'] != 'generic_data.vdata' or category(e['id'], None, None) in GAMEPLAY_CATS
    return any(c.get('cat') in GAMEPLAY_CATS for c in e['changes'])


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


def count_statuses(changes: list[MChange], events: list[dict]) -> dict[str, int]:
    """Gameplay changes by status; a change repeated across many entities
    ('@shared') counts once, an added/removed entity counts once."""
    counts = {'documented': 0, 'described': 0, 'hidden': 0, 'unannounced': 0, 'unreleased': 0}
    seen_shared: set[tuple] = set()
    for c in changes:
        if c.cat not in GAMEPLAY_CATS or c.file == 'convars':
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
    elif commit:
        # work on heroes that are not in the game yet is not "hidden from the notes" — judged at the
        # build the change shipped in: a hero revealed inside the window was still unreleased while
        # tuned before the reveal (Paige, Doorman, Venator…: ~500 changes were "hidden", audit 2026-10-01)
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
        for c in changes:
            owner = c.eid if c.file == 'heroes.vdata' else cat.get(ent_key(c), {}).get('owner')
            if c.status == 'hidden' and owner and owner in unreleased_at(c.builds):
                c.status = 'unreleased'
        for ev in events:
            owner = ev['id'] if ev['file'] == 'heroes.vdata' else ev.get('owner')
            if ev['change']['status'] == 'hidden' and owner and owner in unreleased_at([ev.get('build')]):
                ev['change']['status'] = 'unreleased'
    entities: dict[str, dict] = {}
    cv_status = {c.eid: c.status for c in changes if c.file == 'convars'}
    for cv in extras['convars']:
        cv['status'] = cv_status.get(cv['name'], 'unannounced' if not p.notes else 'hidden')
    shared_groups: dict[tuple, dict] = {}
    for c in changes:
        if c.file == 'convars':
            continue
        name = (loc.plain(loc.hero_name(tok, c.eid) if c.file == 'heroes.vdata'
                          else loc.entity_name(tok, c.eid, cat.get(ent_key(c), {}).get('owner')))
                if c.eid else c.eid)
        if c.shared:
            # one edit copied into many entities (a global rule): one block, not N
            sig = (c.file, c.path, repr(c.old), repr(c.new))
            grp = shared_groups.get(sig)
            if grp is None:
                grp = shared_groups[sig] = {'change': change_json(c), 'targets': []}
            grp['targets'].append(name)
            cur = grp['change']['status']
            # a rule for all heroes is "unreleased" only if every hero it touches is: a dev hero listed
            # first had made 41 "All heroes" rows unreleased (audit 2026-10-01)
            if STATUS_RANK[c.status] > STATUS_RANK[cur] or (cur == 'unreleased' and c.status != 'unreleased'
                                                             and STATUS_RANK[c.status] == STATUS_RANK[cur]):
                grp['change']['status'] = c.status
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
    for (file, *_), grp in shared_groups.items():
        targets = sorted(set(grp['targets']))
        label = SHARED_NAMES.get(file, 'Many entries')
        key = f"@shared:{file}:{len(targets)}:{','.join(targets[:3])}"
        ent = entities.setdefault(key, {'key': key, 'file': file, 'id': '@shared', 'kind': 'shared',
                                        'owner': None, 'name': f'{label} ({len(targets)})',
                                        'targets': targets, 'changes': []})
        ent['changes'].append(grp['change'])
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
        'extras': slim_extras(extras),
        'counts': counts,
        'line_counts': line_counts,
    }


STATUS_RANK = {'hidden': 0, 'unannounced': 0, 'unreleased': 0, 'described': 1, 'documented': 2}
RELEASED_STATES = ('EHeroDevState_Release', 'EHeroDevState_PreRelease')


def unreleased_heroes(commit: str) -> set[str]:
    """Heroes not playable at that build (in development / disabled)."""
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
SHARED_NAMES = {'heroes.vdata': 'All heroes', 'abilities.vdata': 'Many abilities & items',
                'npc_units.vdata': 'Many units', 'misc.vdata': 'Many map objects', 'modifiers.vdata': 'Many modifiers'}
KEY_KINDS = {'hero', 'ability', 'weapon', 'item', 'building', 'trooper', 'neutral', 'shared'}
KEY_LIMIT = 24


def sentence(name: str, c: dict) -> str:
    """Valve-style line for a change: 'Abrams: Health increased from 780 to 800'."""
    label = c.get('label') or ''
    if c.get('path') == '@add':
        return f'{name}: added to the game'
    if c.get('path') == '@return':
        return f'{name}: back in the game files'
    if c.get('path') == '@remove':
        return f'{name}: removed from the game'
    if c['op'] == 'add':
        return f'{name}: {label} added ({c.get("new_s", "")})'
    if c['op'] == 'remove':
        return f'{name}: {label} removed (was {c.get("old_s", "")})'
    try:
        up = float(str(c.get('new_s')).rstrip('m%s')) > float(str(c.get('old_s')).rstrip('m%s'))
        verb = 'increased' if up else 'reduced'
    except ValueError:
        verb = 'changed'
    return f'{name}: {label} {verb} from {c.get("old_s", "")} to {c.get("new_s", "")}'


KEY_MAX_PCT = 300          # bigger jumps are format changes (0.99 -> 99), not balance
_TEST_ENTITY = re.compile(r'test|dummy|debug|_base$', re.I)


def key_changes(ents: list[dict]) -> list[dict]:
    """The biggest balance moves of the window (by |percent|) for a summary."""
    rows = []
    for e in ents:
        if e.get('kind') not in KEY_KINDS or e.get('id') == '@shared' or _TEST_ENTITY.search(e.get('id', '')) \
                or _TEST_ENTITY.search(e.get('name') or ''):
            continue
        for c in e['changes']:
            if c.get('cat') == 'balance' and isinstance(c.get('pct'), (int, float)) \
                    and 5 <= abs(c['pct']) <= KEY_MAX_PCT and c.get('dir') in ('buff', 'nerf') \
                    and c.get('status') not in ('unreleased',):
                rows.append({'entity': e['key'], 'name': e['name'], 'kind': e.get('kind'), 'owner': e.get('owner'),
                             'change': c})
    rows.sort(key=lambda r: -abs(r['change']['pct']))
    return rows[:KEY_LIMIT]


LOC_GROUPS = ('citadel_heroes', 'citadel_mods', 'citadel_attributes', 'citadel_main',
              'citadel_gc_mod_names', 'citadel_gc_hero_names')
LOC_LIMIT = 400
CONVAR_LIMIT = 300


def slim_extras(extras: dict) -> dict:
    """Patch pages show a capped list of text/convar changes and asset totals;
    the full per-build detail stays on the build pages."""
    loc_rows = [x for x in extras['loc'] if x.get('group') in LOC_GROUPS]
    totals: dict[str, dict[str, int]] = {}
    hero_models: set[str] = set()
    for a in extras['assets']:
        for cat_, n in a.get('counts', {}).items():
            t = totals.setdefault(cat_, {'added': 0, 'removed': 0, 'modified': 0})
            for k in t:
                t[k] += n.get(k, 0)
        hero_models |= set(a.get('hero_models', {}))
    return {
        'loc': loc_rows[:LOC_LIMIT], 'loc_total': len(loc_rows),
        'convars': extras['convars'][:CONVAR_LIMIT], 'convars_total': len(extras['convars']),
        'assets': {'counts': dict(sorted(totals.items())), 'hero_models': sorted(hero_models)},
    }


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


# Notes sometimes precede the files: "Diviner's Kevlar: Cooldown Reduction reduced from 12% to 10%"
# is in the 2024-12-06 notes, the value changed in a build of 2024-12-14 (the next window).
LATE_DAYS = 14


def _days(a: str, b: str) -> int:
    from datetime import date
    return (date.fromisoformat(b[:10]) - date.fromisoformat(a[:10])).days


def _late_hit(later: list[tuple[Patch, dict]], p: Patch, subj: str, pairs, lw: set[str],
              hero_name: dict[str, str]) -> tuple | None:
    for q, qd in later:
        if _days(p.date, q.date) > LATE_DAYS:
            break
        for e in qd['entities']:
            names = {(e.get('name') or '').lower(), (hero_name.get(e.get('owner') or '') or '').lower()}
            if subj not in names:
                continue
            for c in e['changes']:
                # 'unannounced': the later build may be a notes-less window of its own (build-5433)
                if c.get('status') not in ('hidden', 'unannounced') or c.get('shared') or c.get('cat') != 'balance':
                    continue
                # "damage" counts here ("Holliday: Base damage reduced from 22 to 18" is the gun's Bullet
                # Damage two days later): the subject and the exact numbers already narrow it down
                if not (rules.expand_label_words(words(c['label'])) | _tokens(c['label'])) & lw:
                    continue
                o, n = num(c.get('old_s')), num(c.get('new_s'))
                if o is not None and n is not None and \
                        any(value_matches(o, a, False) and value_matches(n, b, False) for a, b in pairs):
                    return q, qd, c
    return None


def late_landings(results: list[tuple[Patch, dict]], cat: dict[str, dict]) -> int:
    """Link a numbered line left unmatched in its own window to a still-hidden change
    of the same subject within LATE_DAYS that has exactly its numbers and shares a
    label word. The line becomes documented (with where it landed), the change too."""
    hero_name = {e['id']: e.get('name') or '' for e in cat.values() if e['file'] == 'heroes.vdata'}
    linked = 0
    for i, (p, data) in enumerate(results):
        for s in data['sections']:
            for ln in s['lines']:
                if ln['status'] != 'unmatched' or not ln.get('subject'):
                    continue
                rest = ln['text'].split(':', 1)[1] if ':' in ln['text'][:48] else ln['text']
                pairs = parse_pairs(rest)
                if not pairs:
                    continue
                subj = ln['subject'].lower()
                lw = expand_words(words(rest)) | _tokens(rest)
                hit = _late_hit(results[i + 1:], p, subj, pairs, lw, hero_name)
                steps = [(p, data, None), hit] if hit else _chain_hit(data, results[i + 1:], p, subj, pairs, hero_name)
                if not steps:
                    continue
                q = steps[-1][0]
                ln['status'] = 'documented'
                ln['changes'] = list(dict.fromkeys(st[2]['key'] for st in steps if st[2]))
                ln['late'] = {'patch': q.id, 'title': q.title, 'builds': steps[-1][2].get('builds', [])}
                for _, qd, c in steps:
                    if c is None:
                        continue
                    qd['counts'][c['status']] -= 1
                    qd['counts']['documented'] = qd['counts'].get('documented', 0) + 1
                    c['status'] = 'documented'
                    if qd is not data:
                        c['noted_in'] = {'patch': p.id, 'title': p.title}
                data['line_counts']['unmatched'] -= 1
                data['line_counts']['documented'] = data['line_counts'].get('documented', 0) + 1
                linked += 1
    return linked


def _subject_of(e: dict, subj: str, hero_name: dict[str, str]) -> bool:
    return subj in {(e.get('name') or '').lower(), (hero_name.get(e.get('owner') or '') or '').lower()}


def _chain_hit(data: dict, later: list[tuple[Patch, dict]], p: Patch, subj: str, pairs,
               hero_name: dict[str, str]) -> list | None:
    """The line's change shipped in two steps across a window edge: Valve hotfixed it an hour later
    ("Lucky Shot: Damage reduced from 125% to 110%" = 125 -> 120 in build 5983, 120 -> 110 in 5984 of
    the follow-up window, 2025-11-21). The field starts at A in the line's window and the same field
    ends at B later (within LATE_DAYS), step by step: [(p, data, c0), (q, qd, c1)]."""
    for e in data['entities']:
        if not _subject_of(e, subj, hero_name):
            continue
        for c0 in e['changes']:
            if c0.get('status') not in ('hidden', 'unannounced') or c0.get('cat') != 'balance' or c0.get('shared'):
                continue
            o0, n0 = num(c0.get('old_s')), num(c0.get('new_s'))
            if o0 is None or n0 is None:
                continue
            for a, b in pairs:
                if not value_matches(o0, a, False) or value_matches(n0, b, False):
                    continue
                for q, qd in later:
                    if _days(p.date, q.date) > LATE_DAYS:
                        break
                    for e1 in qd['entities']:
                        for c1 in e1['changes']:
                            if c1.get('key') != c0.get('key') or c1.get('status') not in ('hidden', 'unannounced'):
                                continue
                            o1, n1 = num(c1.get('old_s')), num(c1.get('new_s'))
                            if o1 is not None and n1 is not None and abs(o1 - n0) < 1e-9 and value_matches(n1, b, False):
                                return [(p, data, c0), (q, qd, c1)]
    return None


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
            if p.notes and not q.notes and p.builds and _days(p.date, q.date) <= LATE_DAYS \
                    and _late_count(p, data, [(q, qd)], hero_name) >= ABSORB_MIN:
                p.builds = sorted(p.builds + q.builds, key=lambda b: b['date'])
                out.append((p, build_patch(p, cat)))
                absorbed.append(q.id)
                i += 2
                continue
        out.append((p, data))
        i += 1
    return out, absorbed


def repeated_lines(results: list[tuple[Patch, dict]]) -> int:
    """Steam posts get edited: the 2026-03-06 post later carried the 03-21 lines too.
    An unmatched line whose exact text is matched in a LATER patch's notes belongs
    there: status 'repeated' with a pointer, not a matcher gap."""
    later_home: dict[str, tuple[str, str]] = {}
    moved = 0
    for p, data in reversed(results):
        for s in data['sections']:
            for ln in s['lines']:
                key = ln['text'].strip().lower()
                if ln['status'] == 'unmatched' and key in later_home:
                    pid, title = later_home[key]
                    ln['status'] = 'repeated'
                    ln['see'] = {'patch': pid, 'title': title}
                    data['line_counts']['unmatched'] -= 1
                    data['line_counts']['repeated'] = data['line_counts'].get('repeated', 0) + 1
                    moved += 1
        for s in data['sections']:
            for ln in s['lines']:
                if ln['status'] not in ('unmatched', 'repeated', 'heading', 'untracked', 'nodata'):
                    later_home[ln['text'].strip().lower()] = (p.id, p.title)
    return moved


# stricter than _PRESENTATION_LINE: "slow effect now persists" is the game's code, not a visual
_LOOK_LINE = re.compile(r'\b(sounds?|audio|sfx|vfx|visuals?|particles?|animations?|anims?|models?|icons?|'
                        r'ui|hud|tooltips?|music|voice|looks?|looking)\b', re.I)
_SOUND_WORD = re.compile(r'\b(sounds?|audio|sfx|music|voice)\b', re.I)
_DIGIT = re.compile(r'\d')


def code_lines(results: list[tuple[Patch, dict]]) -> int:
    """A line about a hero, an ability or an item whose game files did not move in its window, nor in a
    later one within LATE_DAYS, is a change in the game's code ("Vyper: Sliding uphill now allows for
    lateral movement"): status 'code', not a matcher miss ('unmatched'). The `_quiet` marks go away."""
    n = 0
    for i, (p, data) in enumerate(results):
        for s in data['sections']:
            for ln in s['lines']:
                about = ln.pop('_quiet', None)
                if not about or ln['status'] != 'unmatched':
                    continue
                if _LOOK_LINE.search(ln['text']):
                    # "Added cast and buff sounds", "Revision to buff and cast to look less modern"
                    ln['status'] = 'untracked'
                    ln['topic'] = 'sound' if _SOUND_WORD.search(ln['text']) else 'visual'
                    data['line_counts']['unmatched'] -= 1
                    data['line_counts']['untracked'] = data['line_counts'].get('untracked', 0) + 1
                    continue
                if _DIGIT.search(_TIER_NAME.sub('', ln['text'])):
                    continue        # a line with numbers left unmatched is more likely a miss of ours
                ids = set(about)
                later = False
                for q, qd in results[i + 1:]:
                    if _days(p.date, q.date) > LATE_DAYS:
                        break
                    if any(f"{e['file']}:{e['id']}" in ids and any(c.get('cat') in GAMEPLAY_CATS for c in e['changes'])
                           for e in qd.get('entities', [])):
                        later = True
                        break
                if later:
                    continue
                ln['status'] = 'code'
                data['line_counts']['unmatched'] -= 1
                data['line_counts']['code'] = data['line_counts'].get('code', 0) + 1
                n += 1
    return n


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
                      'counts': data['counts'], 'line_counts': data['line_counts'], 'has_notes': p.has_notes})
        print(p.id, p.title[:40], len(p.builds), 'builds', data['counts'], data['line_counts'])
    jsonio.dump(OUT / 'index.json', index, indent=1)


if __name__ == '__main__':
    run()
