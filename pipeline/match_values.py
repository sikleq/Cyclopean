"""The matcher's values and words: a change (`MChange`), numbers on a patch-note line (`parse_pairs`), a number
against a change (`value_matches`, `list_match`, `two_sided`), the words of a line or a label (`words`)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import semantics
from . import match_rules as rules


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
    'rejuvenator': {'rejuv', 'rejuvenator', 'rejuvinator'},     # the files spell it 'Rejuvinator' (m_RejuvParams)
    'faster': {'faster', 'speed'},             # "Now travels 40% faster" is the projectile's Speed (2026-10-30)
    'slower': {'slower', 'speed'},
}


_SYNONYMS = rules.stemmed_synonyms(SYNONYMS)       # as words() writes them ('breakables' -> 'breakable')


_ARROW_RE = re.compile(rf'(?P<a>{_NUM})\s*[a-z%]*\s*(?:->|→)\s*(?P<b>{_NUM})', re.I)


_BY_RE = re.compile(rf'(increased|reduced|decreased|lowered|raised)\s+by\s+~?(?P<p>{_NUM})\s*%', re.I)


_PCT_LESS = re.compile(rf'(?P<p>{_NUM})\s*%\s+(?:less|more|shorter|longer|lower|higher|faster|slower)\b', re.I)


_HALF_DAMAGE = re.compile(r'\bhalf\s+(?:the\s+)?damage\s+(?:to|against|on|vs\.?)\s+(?:the\s+)?(?:objectives?|bosse?s?)\b',
                          re.I)


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


HERO_STAT_WORDS = {'health', 'regen', 'move', 'sprint', 'stamina', 'boon', 'melee', 'resist', 'resistance', 'dash',
                   'speed'}


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
    moved: bool = False                           # the same fact moved to another field (mark_availability_moves)
    # the old value's unit when Valve dropped or replaced the printed unit inside the window (labels.unit_switch):
    # "Extra Ammo Consumed 30% → 2" is CHANGED, no percent — 30% of a clip and 2 bullets do not compare
    old_unit: str | None = None
    base: object = None                           # a Street Brawl value's normal value (enrich.street_brawl_base)

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
        if self.base is not None and self.op == 'add':
            # a mode's value set against the value it replaces: "Threadsap duration lasts 35% less" is 22 -> 14
            pairs.append((self.base, self.new))
        if self.scale != 1.0:
            # the patch rescaled every per-boon value (rules.boon_rescale): the notes quote the new value
            # in the old scale ("Kelvin: Bullet damage growth 1.2 -> 0.9" is 1.2 -> 0.707 in the files)
            pairs += [(o, num(n) / self.scale) for o, n in pairs if num(n) is not None]
        pairs += _one_moved(pairs)
        return pairs


def _one_moved(pairs: list[tuple]) -> list[tuple]:
    """The one element that moved in a number list: "points to reach a new badge from a final subrank decreased
    from 2000 to 1500" is m_vecSubRankXP (1000 ×5, 2000) -> (1000 ×5, 1500), the last element alone (Ranked Beta
    Season 2, unmatched until 2026-11-15). A list with two or more moved elements stays whole: which one a single
    pair names would be a guess."""
    out = []
    for o, n in pairs:
        a, b = _number_list(o), _number_list(n)
        if not a or not b or len(a) != len(b):
            continue
        moved = [(x, y) for x, y in zip(a, b) if x != y]
        if len(moved) == 1 and moved[0] not in out:
            out.append(moved[0])
    return out


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


def _number_list(v) -> list[float] | None:
    """A value that is a list of numbers (a soul split per player count, a resist per enemy count), else None."""
    if not isinstance(v, (tuple, list)) or not v:
        return None
    out = [num(x) for x in v]
    return None if any(x is None for x in out) else out


def list_match(c: MChange, pairs, rel: float = EXACT) -> bool:
    """A number list the line gives element by element: "Trooper bounty split ratios updated from 1/0.65/0.28/…
    to 1/0.54/0.36/…" is m_flTrooperKillGoldShareFrac (1, 0.65, 0.28, …) -> (1, 0.54, 0.36, …), every element
    under the field's own transforms (a fraction as the notes' percent). A list never matched a pair: its value
    is no number (coverage finding 8)."""
    if len(pairs) < 2:
        return False
    for o, n in c.steps():
        a, b = _number_list(o), _number_list(n)
        if not a or not b or len(a) != len(b):
            continue
        if len(a) == len(pairs) + 1 and a[0] == b[0]:
            # an entry the notes skip because it did not move: Walkers' resist per nearby enemy starts at
            # "0 enemies: 0%" (0, 0, 8, … 40 -> 0, 0, 0, 20, … 50), the notes list 1-6 enemies
            a, b = a[1:], b[1:]
        if len(a) == len(pairs) and all(value_matches(x, p, c, rel) and value_matches(y, q, c, rel)
                                        for x, y, (p, q) in zip(a, b, pairs)):
            return True
    return False


def two_sided(c: MChange, pairs) -> bool:
    """Both numbers of a pair (or a whole list) are the field's, within the notes' rounding: not one value alone."""
    return list_match(c, pairs, APPROX) or any(value_matches(o, a, c, APPROX) and value_matches(n, b, c, APPROX)
                                               for a, b in pairs for o, n in c.steps())


def exact_pair(c: MChange, pairs) -> bool:
    if list_match(c, pairs):
        return True
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
    return [semantics.display_value(_number_list(v) or num(v), meters) for v in (c.old, c.new)]


def half_match(c: MChange, pairs) -> bool:
    """One side of a 'from A to B' agrees with the files: the property is
    identified, so a disagreement on the other side is a real mismatch."""
    return any(value_matches(o, a, c, APPROX) or value_matches(n, b, c, APPROX)
               for a, b in pairs for o, n in c.steps())


# which attack a field belongs to ("Baba Bench Melee Attack Light › Attack Impulse Max Upward"): the attack's kind is
# no topic of its own — "Repeat light melees while airborne…" and "Heavy melee ground pound…" took that launch field
_ATTACK_KIND = {'melee', 'light', 'heavy', 'attack'}


def topic_words(c: MChange) -> set[str]:
    """The words a field is about: its label's, but of a block's attack ("… Attack Light ›") only what names more."""
    head, sep, prop = (c.label or '').rpartition('›')
    return words(c.label or '') if not sep else words(prop) | (words(head) - _ATTACK_KIND)


def _stems(ws: set[str]) -> set[str]:
    """Words without an -ing or a final e: "bouncing" and "bounce" are one, "targeting" is "target"."""
    out = set()
    for w in ws:
        if w.endswith('ing') and len(w) > 6:
            w = w[:-3]
        out.add(w[:-1] if w.endswith('e') and len(w) > 4 else w)
    return out


def _shown_pair(c: MChange) -> tuple[float, float] | None:
    """The field's old and new numbers the way the page prints them (a rate shown as a time is inverted), or None."""
    o, n = num(c.old), num(c.new)
    if o is None or n is None:
        return None
    if c.invert and o and n:
        o, n = 1 / o, 1 / n
    return o, n


def _numeric(c: MChange) -> bool:
    return _shown_pair(c) is not None


def _same_way(c: MChange, pairs) -> bool:
    """The field moved the way a pair of the line moves (both up or both down), or the line gives its multiplier as
    a reduction: "Headshot reduction increased from 25% to 35%" is Headshot Damage Taken × 0.75 → 0.65, "No longer
    has -30% Lifesteal Effectiveness" 0.7 → 1."""
    on = _shown_pair(c)
    if not on:
        return False
    if any((b - a) * (on[1] - on[0]) > 0 for a, b in pairs):
        return True
    o, n = on
    return 0 <= o <= 2 and 0 <= n <= 2 and any(
        close((1 - o) * 100, abs(a), APPROX) and close((1 - n) * 100, abs(b), APPROX) for a, b in pairs)


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
    if not pairs:
        # "T1 +1m/s Move Speed to +2m/s Move Speed": a tier's bonus without "from" (Rat King, 2026-10-05: exact, but
        # only "described")
        for m in _TIER_TO.finditer(text):
            pairs.append((float(m.group('a')), float(m.group('b'))))
    if not pairs:
        # "T2 slow from -24% Slow and -26% Dash distance to -28% for both": two values to one (Sand Blast, 2026-11-04:
        # its Movement Slow 24 → 28 stayed hidden)
        m = _FOR_BOTH.search(text)
        if m:
            pairs = [(float(m.group('a')), float(m.group('c'))), (float(m.group('b')), float(m.group('c')))]
    if not pairs and not _SWAP_LINE.search(text):
        # (not 'T1 changed from "-15s Cooldown" to "+50 Max Health Steal"': two properties, no pair)
        pairs = _aligned_pairs(text)
    return pairs


_INSTEAD_RE = re.compile(rf'(?P<b>{_NUM})\s*[a-z%]*\s+instead of\s+(?P<a>{_NUM})', re.I)


_FOR_BOTH = re.compile(rf'\bfrom\s+(?P<a>{_NUM})[^\d]{{0,30}}?\band\s+(?P<b>{_NUM})[^\d]{{0,30}}?\bto\s+(?P<c>{_NUM})'
                       rf'[^\d]{{0,10}}\bfor\s+both\b', re.I)


_TIER_TO = re.compile(rf'\bT[1-4]\s+(?P<a>{_NUM})\s*[a-z%/]*(?:\s+[a-z]+){{0,4}}\s+to\s+(?P<b>{_NUM})', re.I)


# "Cooldown increased from 25s to 27s (moved to T2)": the tier's bonus to the same property moved with it
_MOVED_TO_TIER = re.compile(r'\(\s*moved\s+to\s+T([1-3])\s*\)', re.I)


_ITEM_TIER_MOVE = re.compile(r'\bmoved\s+from\s+T([1-5])\s+to\s+T([1-5])\b', re.I)


_FROM_TO = re.compile(r'\bfrom\b(?P<a>(?:[^.;:]|(?<=\d)\.(?=\d))*?)\bto\b(?P<b>(?:[^.;:]|(?<=\d)\.(?=\d))*)', re.I)


ALIGNED_MAX = 4


def _aligned_pairs(text: str) -> list[tuple[float, float]]:
    """"from A … B … to C … D …" with as many numbers on each side, paired in order — the words between
    them hold numbers too, which the strict pattern does not allow: "T2 reduced from -15% Spirit Resist
    for 8s to -10% for 6s", "from 150 (+1.2) to 125 (+1.0)", 'from "+225s within 4s" to "+200 within 3s"',
    "spawn interval improved from every 5s to every 4s" (data-quality audit 2026-10-04: their rows kept
    the eye). An ability tier ("T2") is no number."""
    m = _FROM_TO.search(text)
    if not m:
        return []
    a, b = (re.findall(_NUM, _TIER_NAME.sub(' ', m.group(g))) for g in ('a', 'b'))
    if not a or len(a) != len(b) or len(a) > ALIGNED_MAX:
        return []
    # the same words around the numbers (one side may leave some out: "-10% for 6s"): not one property
    # traded for another ("T3 changed from -56s Cooldown to Impact Area Stuns for 1s")
    wa, wb = (_skeleton(m.group(g)) for g in ('a', 'b'))
    if not (wa <= wb or wb <= wa):
        return []
    return [(float(x), float(y)) for x, y in zip(a, b)]


_TIME_WORDS = {'minute': 'min', 'minutes': 'min', 'mins': 'min', 'second': 's', 'seconds': 's', 'sec': 's'}


def _skeleton(part: str) -> set[str]:
    return {_TIME_WORDS.get(w, w) for w in re.findall(r'[a-z]{2,}', part.lower())}


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


_PARENS = re.compile(r'\([^)]*\)')


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


def _label_tokens(c: MChange) -> set[str]:
    out = rules.expand_label_words(_tokens(c.label))
    return out | {'growth'} if rules.GROWTH_LABEL.search(c.label or '') else out


_SWAP_LINE = re.compile(r'changed from\s+["“]|\bnow\b.*\binstead of\b|\breplaced\b', re.I)


# any "changed from A to B" swaps one thing for another, quoted or not: "Leaping Slash T2 changed from +40 damage to
# +300 souls on hero kill" gave the new souls field a "was 40" (data audit 2026-11-13: Gloom Bombs 16.2 -> 75, Boot
# Kick -25 -> 80 the same way)
_CHANGED_FROM = re.compile(r'\bchanged from\b', re.I)


# a number written in metres on the line ("bomb radius increased from 14m to 20m") is a length: it is never the old
# value of a field the files keep without metres (Air Drop's Outgoing Damage 20% read "14% -> 20%")
_METRES_ON_LINE = re.compile(rf'{_NUM}\s*m\b')
