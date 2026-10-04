"""Rendering of change records shared by patch, build and entity pages."""
from __future__ import annotations

import re

from pipeline import flags as flag_rules
from pipeline.semantics import SHOP_SLOT

from .pixel_icons import tag_svg
from .common import esc, glyph_for, ids_to_names, mark, visual

# The tag set, chosen from what the data actually contains (all patches, 2026-10-01):
# NEW 20k, DEL 11k, NERF 5.2k, BUFF 4k, CHANGED 2.5k, MECH 0.9k, availability 92.
# The percentage is NOT in the badge: the value cell already shows it.
TAG_ORDER = {'new': 0, 'rework': 1, 'buff': 2, 'nerf': 3, 'del': 4, 'on': 5, 'off': 5, 'up': 6, 'down': 6, 'mech': 7,
             'changed': 8}
KIND_LABEL = {
    'hero': 'Hero', 'ability': 'Ability', 'weapon': 'Weapon', 'melee': 'Melee', 'item': 'Item',
    'ability_other': 'Ability', 'trooper': 'Trooper', 'building': 'Building', 'neutral': 'Neutral',
    'unit': 'Unit', 'helper': 'Helper', 'modifier': 'Modifier', 'global': 'Game rules',
}
# availability fields where a truthy value means "switched OFF" ('Disabled', 'In Development');
# for the rest ('Player Selectable', 'Enabled') truthy means ON
_OFF_WHEN_TRUE = re.compile(r'disabled|in development|prerelease|pre-release', re.I)
_TRUE = ('true', '1', 'yes')
_FALSE = ('false', '0', 'no')


def tag_of(c: dict) -> tuple[str, str]:
    """(css class, badge text) for one change dict (from data/patches or build pages)."""
    op, cat = c.get('op'), c.get('cat')
    if op == 'rework':
        return 'rework', 'REWORK'
    if cat == 'availability':
        new = str(c.get('new_s', c.get('new'))).lower()
        if 'release' in new:          # EHeroDevState_Release / _PreRelease
            return ('off', 'OFF') if 'pre' in new else ('on', 'ON')
        truthy = True if new in _TRUE else False if new in _FALSE else None
        if truthy is None:
            # "Disabled On Heroes: — -> hero_kelvin, hero_mirage": a list that grew disables more
            old_n, new_n = (len([x for x in str(v or '').split(', ') if x.strip() and x != '—'])
                            for v in (c.get('old_s', c.get('old')), c.get('new_s', c.get('new'))))
            if old_n != new_n and _OFF_WHEN_TRUE.search(str(c.get('label', '')) + str(c.get('path', ''))):
                return ('off', 'OFF') if new_n > old_n else ('on', 'ON')
            return 'changed', 'CHANGED'
        off = truthy if _OFF_WHEN_TRUE.search(str(c.get('label', '')) + str(c.get('path', ''))) else not truthy
        return ('off', 'OFF') if off else ('on', 'ON')
    d = c.get('dir')
    if c.get('flag') and d in ('buff', 'nerf'):
        # a bit set gaining its first bit is not a new field: "Can target: + neutrals" is a BUFF
        return d, d.upper()
    if op == 'add':
        return 'new', 'NEW'
    if op == 'remove':
        return 'del', 'DEL'
    if d in ('buff', 'nerf', 'up', 'down'):
        return d, d.upper()
    return ('mech', 'MECH') if cat == 'mechanic' else ('changed', 'CHANGED')


def tag_html(c: dict) -> str:
    cls, txt = tag_of(c)
    g = c.get('grad', 5)
    return f'<span class="tag {cls}" data-g="{g}">{tag_svg(cls)}{esc(txt)}</span>'


def sort_changes(changes: list[dict]) -> list[dict]:
    return sorted(changes, key=lambda c: (TAG_ORDER.get(tag_of(c)[0], 9), c.get('label', '')))


# ---- grouping: one header per entity, tier swaps folded into REWORK rows ----

_TIER = re.compile(r'^T(\d): (.+)$')
# which status the folded row takes: the least documented one wins, so "Only hidden" keeps it
_STATUS_WEIGHT = {'mismatch': 0, 'unreleased': 1, 'unannounced': 2, 'hidden': 3, 'described': 4,
                  'rounded': 5, 'documented': 6, 'fix': 7}
HIDDEN_LIKE = ('hidden', 'unreleased', 'unannounced')


def fold_tier_swaps(changes: list[dict]) -> list[dict]:
    """An upgrade tier whose bonuses were both removed and added in one patch was
    replaced, not tweaked: 'T2: Buff Duration DEL, T2: Stun Duration NEW' becomes one
    REWORK row 'T2 upgrade: Buff Duration 25, … → Stun Duration 0.6'."""
    by_tier: dict[str, list[dict]] = {}
    for c in changes:
        m = _TIER.match(str(c.get('label', '')))
        if m:
            by_tier.setdefault(m.group(1), []).append(c)
    swapped = {t for t, cs in by_tier.items()
               if any(c.get('op') == 'add' for c in cs) and any(c.get('op') == 'remove' for c in cs)}
    if not swapped:
        return changes
    out, done = [], set()
    for c in changes:
        m = _TIER.match(str(c.get('label', '')))
        if not m or m.group(1) not in swapped:
            out.append(c)
            continue
        t = m.group(1)
        if t in done:
            continue
        done.add(t)
        cs = by_tier[t]

        def part(x: dict, side: str) -> str:
            return f'{_TIER.match(x["label"]).group(2)} {x.get(side) or ""}'.strip()
        old = ', '.join(part(x, 'old_s') for x in cs if x.get('op') != 'add')
        new = ', '.join(part(x, 'new_s') for x in cs if x.get('op') != 'remove')
        status = min((x.get('status', 'hidden') for x in cs), key=lambda s: _STATUS_WEIGHT.get(s, 9))
        out.append({'op': 'rework', 'cat': cs[0].get('cat'), 'label': f'T{t} upgrade', 'old_s': old,
                    'new_s': new, 'status': status, 'grad': 8, 'folded': len(cs)})
    return out


CORRUPTED = 'm_CorruptedItemInfo'
CORRUPTED_MIN = 3


def _signed(v) -> str:
    s = str(v or '')
    return f'+{s}' if re.match(r'^\d', s) else s


def fold_corrupted(changes: list[dict]) -> list[dict]:
    """City Never Sleeps gave 97 items a Corrupted version (the Broker trades it for the item:
    bonuses plus random penalties, m_CorruptedItemInfo): ~5 bonus rows an item, 474 NEW rows in all.
    An item whose corrupted bonuses all appear (or all go) at once is ONE row — "Corrupted version:
    Cooldown -4, Base Health +10" — and one change for the counters; a later tweak of a few bonuses
    stays row by row with its own direction."""
    mine = [c for c in changes if str(c.get('path') or '').startswith(CORRUPTED)]
    ops = {c.get('op') for c in mine}
    if len(mine) < CORRUPTED_MIN or len(ops) != 1 or ops & {'change'}:
        return changes
    op = ops.pop()
    side = 'new_s' if op == 'add' else 'old_s'
    # sub-fields ("… › Fixed Corrupted Bonus") are how the bonus rolls, not a bonus
    parts = [f'{str(c.get("label", "")).removeprefix("Corrupted: ")} {_signed(c.get(side))}'.strip()
             for c in mine if '›' not in str(c.get('label', ''))]
    status = min((c.get('status', 'hidden') for c in mine), key=lambda s: _STATUS_WEIGHT.get(s, 9))
    first = changes.index(mine[0])
    row = {**mine[0], 'op': op, 'cat': 'balance', 'label': 'Corrupted version', 'path': CORRUPTED,
           'old_s': ', '.join(parts) if op == 'remove' else '', 'new_s': ', '.join(parts) if op == 'add' else '',
           'status': status, 'dir': 'changed', 'pct': None, 'folded': len(mine), 'bonus_list': True}
    folded = {id(c) for c in mine}
    rest = [c for c in changes if id(c) not in folded]
    return rest[:first] + [row] + rest[first:]     # where the first bonus row was


# the counters' icons are the site's own pixel art (builders/pixel_icons.py), not font glyphs;
# tooltips (plain text) use words
TAG_WORDS = {'buff': 'buffs', 'nerf': 'nerfs', 'new': 'new', 'del': 'removed', 'rework': 'reworked', 'up': 'up', 'down': 'down',
             'mech': 'mechanics', 'changed': 'changed', 'on': 'enabled', 'off': 'disabled'}
TAG_WORD_ONE = {'buff': 'buff', 'nerf': 'nerf', 'mech': 'mechanic'}      # "1 buff", not "1 buffs"


def tag_word(tag: str, n: int) -> str:
    return TAG_WORD_ONE.get(tag, TAG_WORDS.get(tag, tag)) if n == 1 else TAG_WORDS.get(tag, tag)


def pip(cls: str, n: int | str = '') -> str:
    """One counter: the tag's pixel icon and a number, in the tag colour."""
    return f'<span class="pip {cls}">{tag_svg(cls)}{n}</span>'


def counts_text(counts: dict[str, int]) -> str:
    """'9 new, 8 buffs, 9 nerfs' for a tooltip, in the tag order."""
    return ', '.join(f'{n} {tag_word(k, n)}' for k, n in sorted(counts.items(), key=lambda kv: TAG_ORDER.get(kv[0], 9)))


def tag_summary(changes: list[dict]) -> str:
    """Counters for an entity header in the index's glyph grammar: '▲3 ▼1 ✦2' (no zeros)."""
    counts: dict[str, int] = {}
    for c in changes:
        cls = tag_of(c)[0]
        counts[cls] = counts.get(cls, 0) + 1
    return '<span class="tsum">' + ''.join(
        pip(cls, n) for cls, n in sorted(counts.items(), key=lambda kv: TAG_ORDER.get(kv[0], 9))) + '</span>'


def top_pips(changes: list[dict], k: int) -> str:
    """The k biggest counters only (a 50-110px tile fits two), in the usual tag order."""
    counts: dict[str, int] = {}
    for c in changes:
        cls = tag_of(c)[0]
        counts[cls] = counts.get(cls, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], TAG_ORDER.get(kv[0], 9)))[:k]
    return '<span class="tsum">' + ''.join(
        pip(cls, n) for cls, n in sorted(ranked, key=lambda kv: TAG_ORDER.get(kv[0], 9))) + '</span>'


def key_change_rows(rows: list[dict], rel: str, owner_names: dict[str, str] | None = None) -> str:
    """'Biggest changes' table rows: icon + entity (+ its hero, dimmed) | tag | label | values."""
    from .common import entity_icon, pretty_id
    out = []
    for r in rows:
        file, _, eid = r['entity'].partition(':')
        ic = entity_icon(file, eid, r.get('kind') or '', rel, r.get('name'), r.get('owner'))
        pic = visual(ic, glyph_for(file, eid, r.get('kind') or ''))
        name = r['name'] if r.get('name') and r['name'] != eid else pretty_id(eid, r.get('owner'))
        who = (owner_names or {}).get(r.get('owner') or '')
        who = f'<span class="own">{esc(who)}</span>' if who and who != name else ''
        c = r['change']
        out.append(f'<tr class="ch"><td class="sc">{pic}{esc(name)}{who}</td><td class="tg">{tag_html(c)}</td>'
                   f'<td>{esc(c["label"])}</td><td class="ov">{vals_html(c)}</td></tr>')
    return ''.join(out)


def change_row(c: dict, extra_cls: str = '', search: str = '') -> str:
    st = c.get('status', 'hidden')
    ds = f' data-search="{esc(search)}"' if search else ''
    return (f'<tr class="ch st-{esc(st)}{extra_cls}"{ds}><td class="st">{mark(st)}</td><td class="tg">{tag_html(c)}</td>'
            f'<td class="lb">{esc(c.get("label"))}</td><td class="ov">{vals_html(c)}</td></tr>')


def entity_rows(name: str, icon_url: str | None, changes: list[dict], search: str = '', href: str = '',
                glyph: str = 'abilities') -> list[str]:
    """Header row (icon, name, tag counters) + one row per change, name not repeated.
    No game icon: the category glyph (`common.glyph_for`) in the same box."""
    rows = sort_changes(fold_tier_swaps(fold_corrupted(changes)))
    if not rows:
        return []
    return [entity_header(name, icon_url, rows, search, href, glyph)] + [change_row(c, '', search) for c in rows]


def entity_header(name: str, icon_url: str | None, counted: list[dict], search: str = '', href: str = '',
                  glyph: str = 'abilities', hidden: bool | None = None) -> str:
    """The icon + name + tag counters row that opens an entity's block."""
    ic = visual(icon_url, glyph)
    nm = f'<a href="{esc(href)}">{esc(name)}</a>' if href else esc(name)
    if hidden is None:
        hidden = any(c.get('status', 'hidden') in HIDDEN_LIKE for c in counted)
    dev = ' dev' if any(c.get('status') == 'unreleased' for c in counted) else ''
    ds = f' data-search="{esc(search)}"' if search else ''
    counters = tag_summary(counted) if counted else ''
    return (f'<tr class="eh{" has-hidden" if hidden else ""}{dev}"{ds}><td colspan="4"><span class="en">{ic}{nm}</span>'
            f'{counters}</td></tr>')


_FLAG_PREFIX = re.compile(r'^(CITADEL_UNIT_TARGET_|CITADEL_ABILITY_BEHAVIOR_|CITADEL_|MODIFIER_STATE_|MODIFIER_VALUE_|'
                          r'EAbility|E[A-Z][a-z]+_|DOTA_)')
LONG_VALUE = 60


_NUMBERISH = re.compile(r'^[-+]?(\d+\.?\d*|\.\d+)[a-z%/]*$')
# flags Valve also writes without spaces: "CITADEL_ABILITY_BEHAVIOR_CHANNELLED|CITADEL_…" (2026-10-02)
_PIPED = re.compile(r'^[A-Z][A-Z0-9_]+(?:\s*\|\s*[A-Z][A-Z0-9_]+)+$')


def _flags(s) -> list[str] | None:
    """'A | B' bit flags or 'a, b, c' id lists -> items; None for plain values. Numbers are
    never flags: a recoil range "-0.1, 0.1" read "+-0.1 +0.1" on 314 rows (audit 2026-10-02) —
    a pair, a vector or prices by tier keep their order and repeats."""
    if not isinstance(s, str):
        return None
    if ' | ' in s or _PIPED.match(s):
        return [f.strip() for f in s.split('|') if f.strip()]
    parts = [f.strip() for f in s.split(', ')]
    if len(parts) > 1 and all(p and ' ' not in p for p in parts) and not any(_NUMBERISH.match(p) for p in parts):
        return parts
    return None


def _short_flag(f: str) -> str:
    named = ids_to_names(f)
    if named != f:
        return named
    return _FLAG_PREFIX.sub('', f).replace('_', ' ').lower()


_SIDE_CLASS = {1: 'good', -1: 'bad', 0: 'even'}


def _bits_html(added: list[tuple[str, int]], removed: list[tuple[str, int]]) -> str:
    """A listed bit's chip takes the colour of the side it moved the owner to (pipeline.flags), not of
    added / removed: "Interrupted by +silenced" is a nerf, "Interrupted by −rooted" a buff (review
    2026-10-04: green chips under a NERF tag)."""
    return ('<span class="vals flags">'
            + ''.join(f'<span class="flag add {_SIDE_CLASS[s]}">+{esc(w)}</span>' for w, s in added)
            + ''.join(f'<span class="flag rem {_SIDE_CLASS[-s]}">−{esc(w)}</span>' for w, s in removed) + '</span>')


def flag_moves(path: str, old_s, new_s) -> list[str] | None:
    """The listed bits of a flag field that moved, as '+words' / '−words' (pipeline.flags), for plain-text
    places (the matrices' hover cards); None when the field is no flag field or no listed bit moved."""
    d = flag_rules.diff(path, old_s, new_s) if path else None
    if not d or not (d[0] or d[1]):
        return None
    return [f'+{w}' for w, _ in d[0]] + [f'−{w}' for w, _ in d[1]]


def flags_html(old_s, new_s, path: str = '') -> str | None:
    """Bit-flag lists ('A | B | C') show only what was added / removed; in a flag field a player plays
    with, only its listed bits, in words ("+ignored by troopers and neutrals", pipeline.flags). A field
    whose moved bits are all unlisted (a "Technical" row) shows them the engine's way: the words left
    1,168 empty cells (review 2026-10-04)."""
    d = flag_rules.diff(path, old_s, new_s) if path else None
    if d is not None and (d[0] or d[1]):
        return _bits_html(*d)
    a, b = _flags(old_s), _flags(new_s)
    if a is None and b is None:
        return None
    none = ('', '—', None)                    # an absent side is no flag ("−—" on 41 rows)
    a = set(a or ([old_s] if old_s not in none else []))
    b = set(b or ([new_s] if new_s not in none else []))
    added = ''.join(f'<span class="flag add">+{esc(_short_flag(f))}</span>' for f in sorted(b - a))
    removed = ''.join(f'<span class="flag rem">−{esc(_short_flag(f))}</span>' for f in sorted(a - b))
    return f'<span class="vals flags">{added}{removed}</span>'


_ENUM_VALUE = re.compile(r'^E[A-Z][A-Za-z0-9]*?_([A-Za-z0-9_]+)$')            # EHeroDevState_PreRelease
_CAPS_VALUE = re.compile(r'^[A-Z][A-Z0-9]+(?:_[A-Z0-9]+)+$')                 # CITADEL_UNIT_TARGET_NEUTRAL
_CAPS_PREFIX = re.compile(r'^(CITADEL_UNIT_TARGET_|CITADEL_ABILITY_BEHAVIOR_|CITADEL_|MODIFIER_STATE_|MODIFIER_VALUE_|DOTA_)')
_FILE_VALUE = re.compile(r'^file://\{[a-z]+\}/(?:.*/)?([^/]+?)(?:\.[a-z0-9]+)?$', re.I)
_CAMEL = re.compile(r'(?<=[a-z0-9])(?=[A-Z])|_')


def readable_value(s: str) -> str:
    """Engine spellings a player cannot read, as words: 'EHeroDevState_PreRelease' -> 'Pre Release',
    'CITADEL_UNIT_TARGET_NEUTRAL' -> 'Neutral', 'file://{images}/…/sticker_baba.psd' -> 'sticker_baba'.
    Numbers and ordinary text pass through; a 'A | B' flag list word by word (171 raw
    CITADEL_ABILITY_BEHAVIOR_* in the notes' "described" lists, 2026-10-02)."""
    if ' | ' in s or _PIPED.match(s):
        return ' | '.join(readable_value(p.strip()) for p in s.split('|') if p.strip())
    m = _ENUM_VALUE.match(s)
    if m:
        if s.startswith('EItemSlotType_') and m.group(1) in SHOP_SLOT:
            return SHOP_SLOT[m.group(1)]        # the shop's words: "Tech" is Spirit, "Armor" Vitality
        return ' '.join(w for w in _CAMEL.split(m.group(1)) if w)
    if _CAPS_VALUE.match(s):
        return _CAPS_PREFIX.sub('', s).replace('_', ' ').title()
    m = _FILE_VALUE.match(s)
    if m:
        return m.group(1)
    return s


# 9999 / 99999 is how the game writes "no limit" (Channel Move Speed 50 -> 9999, Max Stacks 99 -> 9999)
_NO_LIMIT = re.compile(r'^(?:9999|99999)(?:\.0+)?[a-z%/]*$')
# one wording for both of the game's spellings (9999 and -1): "∞ → no limit" read as a change on 4 rows
# (Rabbit Hex's Channel Move Speed, audit 2026-10-04)
NO_LIMIT = 'no limit'


def shown_value(s) -> str:
    """A value as the page prints it: ids as names, engine enums as words, 9999 as "no limit"."""
    if s is None:
        return ''
    s = str(s)
    return NO_LIMIT if _NO_LIMIT.match(s.strip()) else readable_value(ids_to_names(s))


def _clip(s) -> str:
    s = shown_value(s)
    return s if len(s) <= LONG_VALUE else s[:LONG_VALUE - 1] + '…'


PCT_PAD = '<span class="pct-pad"></span>'
PCT_STEPS = (5, 15, 30, 60)      # |%| boundaries of the pill's 5 colour strengths (scripts.js pctGrade mirrors them)


def pct_grade(pct: float) -> int:
    """1 (a nudge, faint pill) .. 5 (60%+, full colour)."""
    a = abs(pct)
    return 1 + sum(a >= s for s in PCT_STEPS)


_MINUS_ONE = re.compile(r'^[-−]1(?:\.0+)?(?:m|s|m/s)?$')       # not "-1%": a real one-percent penalty
_UNIT_TAIL = re.compile(r'^([-−+]?\d+(?:\.\d+)?)(m/s|m|s|%)$')
_BARE_NUM = re.compile(r'^[-−+]?\d+(?:\.\d+)?$')


_BONUS_PATH = re.compile(r'\.m_strBonus$')
_NEG_NUM = re.compile(r'^[-−](\d+(?:\.\d+)?)')


def _sentinel(s: str, c: dict | None = None, other: str | None = None) -> str:
    """The game's "-1" (no cap, no charge limit, the default) and an empty value, as a reader says them
    (advisor round 3: "Channel Move Speed 8m → −1" on 29 rows, "Weapon Damage 20% →"). Not a T1-T3 /
    Enhanced / Corrupted bonus (`c`'s path ends .m_strBonus: "−1s" there is a second off the cooldown,
    Djinn's Mark T3 −0.75s → −1s read "no limit"), nor a value whose other side is another negative
    number (Sharpshooter's move speed penalty −0.5 → −1 m/s; python audit 2026-10-04)."""
    if s is None or str(s).strip() == '':
        return '—'
    if not _MINUS_ONE.match(str(s).strip()):
        return s
    if c is not None and _BONUS_PATH.search(str(c.get('path') or '')):
        return s
    m = _NEG_NUM.match(str(other or '').strip())
    if m and float(m.group(1)) != 1.0:
        return s
    path = str((c or {}).get('path') or '')
    return next((w for rx, w in _SENTINEL_WORDS if rx.search(path)), NO_LIMIT)


# what -1 means where it is not "no limit": a charge delay, a weapon's spin-up or spread decay "as the
# ability's default" (16 Venator rows read "Charge Delay 0s → no limit", audit 2026-10-04), a buff that
# never runs out
_SENTINEL_WORDS = ((re.compile(r'AbilityCooldownBetweenCharge|m_fl(?:BuildUpRate|MaxSpinCycleTime|'
                               r'ShootSpreadPenaltyDecayDelay)$'), 'default'),
                   (re.compile(r'(?:^|\.)m_flDuration$'), 'permanent'))


def _same_unit(old: str, new: str) -> tuple[str, str]:
    """"50 → 20m" reads as two kinds of number: the unit goes on both sides."""
    mo, mn = _UNIT_TAIL.match(str(old)), _UNIT_TAIL.match(str(new))
    if mn and not mo and _BARE_NUM.match(str(old)):
        return f'{old}{mn.group(2)}', new
    if mo and not mn and _BARE_NUM.match(str(new)):
        return old, f'{new}{mo.group(2)}'
    return old, new


def vals_html(c: dict) -> str:
    op = c.get('op')
    if c.get('cat') in ('visual', 'audio', 'ui'):
        return f'<span class="vals muted">{esc(op)}</span>'
    if str(c.get('path', '')).startswith('@'):
        return ''                 # "Added to the game files": the event itself, no value (it read "· —")
    old_s = c.get('old_s', c.get('old'))
    new_s = c.get('new_s', c.get('new'))
    if op == 'rework':            # folded tier swap: bonus lists, may wrap
        return (f'<span class="vals wrap"><span class="old">{esc(old_s)}</span><span class="arrow">→</span>'
                f'<span class="new">{esc(new_s)}</span></span>')
    if c.get('bonus_list'):       # folded corrupted version: one list of bonuses, may wrap
        return f'<span class="vals wrap"><span class="{"new" if op == "add" else "old"}">{esc(new_s or old_s)}</span></span>'
    path = str(c.get('path') or '')
    fl = flags_html(old_s, new_s, path)
    if fl:
        return fl
    # "EItemSlotType_Tech → EItemSlotType_Armor" is the item moving from the Spirit to the Vitality shop
    old_s, new_s = (flag_rules.enum_words(path, v) or v for v in (old_s, new_s))
    old_s, new_s = _clip(old_s), _clip(new_s)
    old_s, new_s = _sentinel(old_s, c, new_s), _sentinel(new_s, c, old_s)
    if not c.get('unit_switch'):     # "30% → 2": Valve dropped the unit, the old one is not the new one's
        old_s, new_s = _same_unit(old_s, new_s)
    # rows without a % pill keep its slot (.pct-pad, shown only in change rows), so the new
    # values of every row end on one vertical line
    if op == 'add':
        return f'<span class="vals"><span class="new">{esc(new_s)}</span>{PCT_PAD}</span>'
    if op == 'remove':
        return f'<span class="vals"><span class="old">{esc(old_s)}</span>{PCT_PAD}</span>'
    d = c.get('dir', 'changed')
    pct = c.get('pct')
    pct_s = (f'<span class="pct dir-{d}" data-g="{pct_grade(pct)}">{pct:+.1f}%</span>'
             if isinstance(pct, (int, float)) else PCT_PAD)
    return (f'<span class="vals"><span class="old">{esc(old_s)}</span><span class="arrow">→</span>'
            f'<span class="new dir-{d}">{esc(new_s)}</span>{pct_s}</span>')


def change_li(c: dict, show_status: bool = True, show_builds: bool = False) -> str:
    st = c.get('status', 'hidden')
    status = mark(st) if show_status else ''
    builds = ''
    if show_builds and c.get('builds'):
        builds = f'<span class="bld">{esc(", ".join(str(b) for b in c["builds"]))}</span>'
    return (f'<li class="st-{esc(st)} cat-{esc(c.get("cat", ""))}">{status}{tag_html(c)}'
            f'<span class="lbl">{esc(c.get("label"))}</span>{vals_html(c)}{builds}</li>')
