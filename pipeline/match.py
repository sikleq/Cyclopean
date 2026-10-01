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

import json
import re
from dataclasses import dataclass, field

from . import cache, catalog, jsonio, loc, semantics, tracker
from . import match_rules as rules
from . import patches as patches_mod
from .patches import Patch, group

OUT = tracker.ROOT / 'data' / 'patches'
BUILDS = tracker.ROOT / 'data' / 'builds'
GAMEPLAY_CATS = ('balance', 'mechanic', 'availability')

_NUM = r'[-+]?\d*\.?\d+'
# "from 50% to 40%", "from +40 degrees angle to +25", "from 18m->54m to 16m->48m",
# "from 100+1.5 to 120+1.75" (base + spirit scaling)
_COMPOUND = rf'{_NUM}(?:\s*[a-z%]*\s*(?:->|→|\+|/)\s*{_NUM})*'     # "6800/9350/11900" = per-phase values
_PAIR_RE = re.compile(
    rf'from\s+(?P<a>{_COMPOUND})(?:\s*[a-z%°.\'/]+){{0,4}}?\s*(?:to|->|→)\s*(?P<b>{_COMPOUND})',
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
    return abs(a - b) <= max(0.011, rel * abs(b))


def value_matches(v, x: float, meters: bool, rel: float = EXACT) -> bool:
    """Does data value v equal the notes' number x under a display transform?
    (raw, magnitude, fraction->percent, units->metres, rate<->interval)."""
    n = num(v)
    if n is None:
        return False
    candidates = [n, abs(n), n * 100, n / semantics.UNITS_PER_METER, abs(n) * 100]
    if n not in (0, 0.0):
        candidates.append(1 / abs(n))      # "stamina cooldown 5s" vs regen 0.2/s
    return any(close(c, abs(x), rel) or close(c, x, rel) for c in candidates)


def exact_pair(c: MChange, pairs) -> bool:
    for a, b in pairs:
        if any(value_matches(o, a, c.meters) and value_matches(n, b, c.meters) for o, n in c.steps()):
            return True
        if c.op == 'add' and value_matches(c.new, b, c.meters):
            return True
        if c.op == 'remove' and value_matches(c.old, a, c.meters):
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
    return any(value_matches(o, a, c.meters, APPROX) or value_matches(n, b, c.meters, APPROX)
               for a, b in pairs for o, n in c.steps())


def expand_words(ws: set[str]) -> set[str]:
    out = set(ws)
    for w in ws:
        out |= SYNONYMS.get(w, set())
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
    return pairs


def words(text: str) -> set[str]:
    """Content words, lightly stemmed (pellet/pellets, charge/charges)."""
    out = set()
    for w in _WORD_RE.findall(text.lower()):
        if w in _STOP:
            continue
        out.add(w[:-1] if len(w) > 4 and w.endswith('s') and not w.endswith('ss') else w)
    return out


# ---- window merge ---------------------------------------------------------

def load_record(file_name: str) -> dict:
    return jsonio.load(BUILDS / file_name)


def window_changes(p: Patch, cat: dict[str, dict], tok: dict[str, str]) -> tuple[list[MChange], dict]:
    """Merge the builds of a window. Entities added inside the window are not
    diffed field by field (their whole data is "new"): they become one
    'entity added' change each."""
    merged: dict[str, MChange] = {}
    extras = {'loc': [], 'convars': [], 'assets': [], 'entities_added': [], 'entities_removed': []}
    added_here: set[str] = set()
    for row in p.builds:
        rec = load_record(row['file'])
        for e in rec['entities']:
            targets_default = [e['id']]
            ekey = f"{e['file']}:{e['id']}"
            if e['status'] in ('added', 'removed'):
                if e['status'] == 'added':
                    added_here.add(ekey)
                bucket = 'entities_added' if e['status'] == 'added' else 'entities_removed'
                extras[bucket].append({'file': e['file'], 'id': e['id'], 'build': rec['build'],
                                       'name': e.get('name'), 'kind': e.get('kind'), 'owner': e.get('owner')})
                continue
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
                        d = semantics.describe(c['path'], tok, tid, ce.get('kind', ''))
                        merged[key] = MChange(
                            e['file'], tid, c['path'], c['op'], c.get('old'), c.get('new'), c['cat'],
                            ce.get('kind', ''), ce.get('owner'), d['label'], d['meters'],
                            [rec['build']], bool(c.get('targets')), chain=[c.get('old'), c.get('new')])
                    else:
                        mc.new = c.get('new')
                        mc.chain.append(c.get('new'))
                        mc.builds.append(rec['build'])
                        mc.op = 'change' if mc.op == 'change' or (mc.op == 'add' and c['op'] != 'remove') else c['op']
        extras['loc'].extend(dict(x, build=rec['build']) for x in rec.get('loc') or [])
        extras['convars'].extend(dict(x, build=rec['build']) for x in rec.get('convars') or [])
        if rec.get('assets'):
            extras['assets'].append({'build': rec['build'], **rec['assets']})
    changes = [c for c in merged.values() if not (c.op == 'change' and c.old == c.new)]
    # console variables take part in matching ("Respawn time … from 35s to 38s")
    for cv in extras['convars']:
        if cv.get('op') != 'change' or num(cv.get('old')) is None or num(cv.get('new')) is None:
            continue
        label = cv['name'].replace('citadel_', '').replace('_', ' ')
        changes.append(MChange('convars', cv['name'], cv['name'], 'change', cv['old'], cv['new'], 'balance',
                               'global', None, label, False, [cv['build']]))
    # an entity added and removed within one window never shipped
    removed = {f"{x['file']}:{x['id']}" for x in extras['entities_removed']}
    both = added_here & removed
    extras['entities_added'] = [x for x in extras['entities_added'] if f"{x['file']}:{x['id']}" not in both]
    extras['entities_removed'] = [x for x in extras['entities_removed'] if f"{x['file']}:{x['id']}" not in both]
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
        if nm and nm != e['id']:
            for variant in rules.name_variants(loc.plain(nm)):
                idx.setdefault(variant, []).append(key)
    return idx


def resolve_subject(prefix: str, idx: dict[str, list[str]], cat: dict[str, dict]) -> Subject | None:
    keys = idx.get(prefix.strip().lower())
    if not keys:
        aliased = rules.alias_keys(prefix)
        return Subject(aliased, prefix, 'alias') if aliased else None
    heroes = [k for k in keys if k.startswith('heroes.vdata:')]
    if heroes:
        hid = heroes[0].split(':', 1)[1]
        ids = {heroes[0]} | {k for k, e in cat.items() if e.get('owner') == hid}
        return Subject(ids, prefix, 'hero')
    return Subject(set(keys), prefix, cat[keys[0]].get('kind', ''))


def ent_key(c: MChange) -> str:
    return f'{c.file}:{c.eid}'


def label_words(c: MChange) -> set[str]:
    return rules.expand_label_words(words(c.label))


def pct_close(c: MChange, by_pct: float) -> bool:
    for o, n in c.steps():
        o, n = num(o), num(n)
        if o and n is not None and abs(abs(n / o - 1) * 100 - by_pct) <= max(1.0, 0.1 * by_pct):
            return True
    return False


def score(c: MChange, text: str, pairs, by_pct, lw: set[str], tier: int | None, ability_hits: set[str]) -> int:
    s = 0
    steps = c.steps()
    for a, b in pairs:
        if any(value_matches(o, a, c.meters) and value_matches(n, b, c.meters) for o, n in steps):
            s += 10
        elif any(value_matches(o, a, c.meters, APPROX) and value_matches(n, b, c.meters, APPROX) for o, n in steps):
            s += 7          # the notes rounded a value ("0.5" for 0.54)
        elif c.op == 'add' and value_matches(c.new, b, c.meters):
            s += 8          # value made explicit: "stacks from +2 to +3" where 2 was the default
        elif c.op == 'remove' and value_matches(c.old, a, c.meters):
            s += 8
    if by_pct is not None and pct_close(c, by_pct):
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
            res = annotate_line(probe, changes, by_ent, idx, cat, tok)
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


def annotate_line(text, changes, by_ent, idx, cat, tok) -> dict:
    subject = None
    rest = text
    if ':' in text[:48]:
        prefix, rest = text.split(':', 1)
        subject = resolve_subject(prefix, idx, cat)
    lw = expand_words(words(rest))
    pairs = parse_pairs(rest)
    m = _BY_RE.search(rest)
    by_pct = float(m.group('p')) if m else None
    tm = _TIER_RE.search(rest)
    tier = int(tm.group(1)) if tm else None
    result = {'text': text, 'subject': subject.name if subject else None, 'status': 'unmatched', 'changes': []}

    if not subject:
        covered = rules.global_line(text, changes, cat, num) or rules.global_delta_line(text, changes, cat, num)
        if covered:
            return _link(result, covered, text, 'described')
        aliased = rules.alias_keys(text)
        if aliased:            # "Walker bounty increased by 5%": the unit is named inside the line
            subject = Subject(aliased, None, 'alias_inline')

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
        if lw & WEAPON_WORDS:
            ability_hits |= {k for k in subject.ids if cat.get(k, {}).get('kind') == 'weapon'}
        if not ability_hits and lw & HERO_STAT_WORDS:
            ability_hits |= {k for k in subject.ids if k.startswith('heroes.vdata:')}
        # ability_hits only add score: "Bullet damage per boon" names the gun
        # but the value lives on the hero, so the pool is never narrowed.
    elif subject:
        ability_hits = set(subject.ids)     # an item / unit line is about that entity
    pool = [c for c in pool if c.cat in GAMEPLAY_CATS]

    if (pairs or by_pct is not None) and pool:
        scored = sorted(((score(c, rest, pairs, by_pct, lw, tier, ability_hits), c) for c in pool),
                        key=lambda x: -x[0])
        best = scored[0][0]
        # a line without a subject must also share a word with the field label
        need = 0 if subject else 1
        if best >= 10 + need or (by_pct is not None and best >= 6 + need):
            hits = [c for s, c in scored if s == best]
            for c in hits:
                c.status = 'documented'
                c.lines.append(text)
            rounded = pairs and not any(exact_pair(c, pairs) for c in hits)
            result['status'] = 'rounded' if rounded else 'documented'
            result['changes'] = [c.key for c in hits]
            if rounded:
                result['data'] = data_values(hits[0], pairs)
            return result
        # names a property of this entity and one side of the numbers agrees,
        # the other does not: the notes and the files disagree
        top = [c for s, c in scored
               if num(c.old) is not None and label_words(c) & lw
               and (not ability_hits or ent_key(c) in ability_hits)
               and half_match(c, pairs)]
        if subject and top:
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
        """The field shares a specific word with the line (not just 'bullet' or 'damage')."""
        return bool(words(c.label) & specific) or bool(label_words(c) & specific - SYNONYM_ONLY)

    if subject.kind == 'alias_inline':
        # a unit merely named inside a sentence: link only on specific property words
        linked = [c for c in pool if on_topic(c)]
        return _link(result, linked, text, 'described') if linked and not pairs else result
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
    # textual line: link changes of the subject that share a specific word with the line
    linked = [c for c in pool if on_topic(c)] or \
             ([c for c in pool if ent_key(c) in ability_hits] if ability_hits and subject.kind == 'hero' else [])
    if linked:
        return _link(result, linked, text, 'described')
    return result


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

def change_json(c: MChange) -> dict:
    kind = c.kind or ''
    dirn, pct = semantics.direction(c.path, num(c.old), num(c.new), kind)
    return {
        'key': c.key, 'file': c.file, 'id': c.eid, 'path': c.path, 'op': c.op, 'cat': c.cat,
        'label': c.label,
        'old_s': semantics.display_value(num(c.old) if num(c.old) is not None else c.old, c.meters),
        'new_s': semantics.display_value(num(c.new) if num(c.new) is not None else c.new, c.meters),
        'dir': dirn, 'pct': None if pct is None else round(pct, 1), 'grad': semantics.gradient(pct),
        'status': c.status, 'builds': sorted(set(c.builds)), 'shared': c.shared,
    }


ENTITY_EVENT_KINDS = {'hero', 'item', 'ability', 'weapon', 'trooper', 'building', 'neutral', 'unit'}


def entity_events(extras: dict, notes_text: str, tok: dict[str, str]) -> list[dict]:
    """One change per entity added to / removed from the files in this window."""
    out = []
    for bucket, op, label in (('entities_added', 'add', 'Added to the game files'),
                              ('entities_removed', 'remove', 'Removed from the game files')):
        for x in extras.get(bucket, []):
            if x.get('kind') not in ENTITY_EVENT_KINDS or x['id'] == '@shared':
                continue
            name = x.get('name') or x['id']
            status = 'described' if name and name != x['id'] and name.lower() in notes_text else 'hidden'
            out.append({**x, 'name': name, 'change': {
                'key': f"{x['file']}:{x['id']}:@{op}", 'file': x['file'], 'id': x['id'], 'path': f'@{op}',
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
        # work on heroes that are not in the game yet is not "hidden from the notes"
        unreleased = unreleased_heroes(commit)
        for c in changes:
            owner = c.eid if c.file == 'heroes.vdata' else cat.get(ent_key(c), {}).get('owner')
            if c.status == 'hidden' and owner in unreleased:
                c.status = 'unreleased'
        for ev in events:
            owner = ev['id'] if ev['file'] == 'heroes.vdata' else ev.get('owner')
            if ev['change']['status'] == 'hidden' and owner in unreleased:
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
            if STATUS_RANK[c.status] > STATUS_RANK[grp['change']['status']]:
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
KEY_KINDS = {'hero', 'ability', 'weapon', 'item', 'building', 'trooper', 'neutral'}
KEY_LIMIT = 24


def sentence(name: str, c: dict) -> str:
    """Valve-style line for a change: 'Abrams: Health increased from 780 to 800'."""
    label = c.get('label') or ''
    if c.get('path') == '@add':
        return f'{name}: added to the game'
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
        if e.get('kind') not in KEY_KINDS or _TEST_ENTITY.search(e.get('id', '')) \
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
                if not rules.expand_label_words(words(c['label'])) & lw:
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
                hit = _late_hit(results[i + 1:], p, ln['subject'].lower(), pairs, expand_words(words(rest)), hero_name)
                if not hit:
                    continue
                q, qd, c = hit
                ln['status'] = 'documented'
                ln['changes'] = [c['key']]
                ln['late'] = {'patch': q.id, 'title': q.title, 'builds': c.get('builds', [])}
                qd['counts'][c['status']] -= 1
                qd['counts']['documented'] = qd['counts'].get('documented', 0) + 1
                c['status'] = 'documented'
                c['noted_in'] = {'patch': p.id, 'title': p.title}
                data['line_counts']['unmatched'] -= 1
                data['line_counts']['documented'] = data['line_counts'].get('documented', 0) + 1
                linked += 1
    return linked


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
    for p, data in results:
        jsonio.dump(OUT / f'{p.id}.json.gz', data)
        index.append({'id': p.id, 'title': p.title, 'date': p.date[:10], 'builds': len(p.builds),
                      'counts': data['counts'], 'line_counts': data['line_counts'], 'has_notes': p.has_notes})
        print(p.id, p.title[:40], len(p.builds), 'builds', data['counts'], data['line_counts'])
    jsonio.dump(OUT / 'index.json', index, indent=1)


if __name__ == '__main__':
    run()
