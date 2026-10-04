"""Shop items table with per-cell history.

What a row holds comes from the item's own tooltip card (m_vecTooltipSectionInfo + the header values),
i.e. what the game shows, not a hand-picked list (2026-10-04: 14 hardcoded properties left 67-84% of
the cells empty and never showed an item's headline number, e.g. Headshot Booster's +45):

  - Shop: tier, and cost from generic_data m_nItemPricePerTier[tier] of the same build;
  - stats: a property that feeds a hero stat (m_eProvidedPropertyType) and is always on (no
    "Conditional" usage flag, not listed in the card's Active section), keyed by the stat it provides —
    TechPower and SpiritPower are one Spirit Power. A stat that STAT_MIN_ITEMS shop items give is a
    column, grouped Weapon / Spirit / Vitality / Movement by the stat's name (family());
  - Utility: the item ability's cooldown and duration;
  - effects: every other number the card shows (Head Shot Bonus Damage +45, the +3000 Health a
    conditional active gives, a stat only one or two items have), with the card's label and value.

Every value keeps its history over all builds, tracked PER PROPERTY over every number of the item, on
the card or not (review 2026-10-04): which stat or effect a property feeds is decided by the newest build
only. Keyed by the stat, Valve's enum renames (BASEATTACK_DAMAGE_PERCENT -> WEAPON_DAMAGE_INCREASE in
6541), a usage flag flipped, or a property newly listed on the card read as 77 fake "added" entries and
lost the real history before them (Extended Magazine's 15 -> 12 -> 6 -> 8). A property renamed with the
stat it gives (BonusSpirit -> TechPower) joins its predecessor (joined()).

    python -m pipeline.item_table   ->  data/tables/items.json
"""
from __future__ import annotations

import json
import re
import time
from collections import Counter
from difflib import SequenceMatcher

from .abilities import css_class, is_speed
from .hero_table import history_changes
from .semantics import direction, humanize, polarity
from . import cache, loc, tracker

OUT = tracker.ROOT / 'data' / 'tables' / 'items.json'
WATCH = (tracker.SCRIPTS + 'abilities.vdata', tracker.SCRIPTS + 'generic_data.vdata')
SLOTS = {'EItemSlotType_WeaponMod': 'Weapon', 'EItemSlotType_Armor': 'Vitality', 'EItemSlotType_Tech': 'Spirit'}

# the item ability's own timing: always columns (Utility); cast range, charges and channel are effects
TIMING = {'AbilityCooldown': ('cooldown', 'Cooldown', 'cooldown'), 'AbilityDuration': ('duration', 'Duration', 'duration')}
HEADER_PROPS = ('AbilityCooldown', 'AbilityCastRange', 'AbilityDuration', 'AbilityCharges',
                'AbilityCooldownBetweenCharge', 'AbilityChannelTime')
STAT_MIN_ITEMS = 3            # a stat this many shop items give is a column; rarer ones are effects
# stat families, in column order; "Other" is a provided stat no family word matches (a new one), never
# dropped and never merged into the timing Utility group (two "Utility" groups broke the folding)
FAMILIES = ('Weapon', 'Spirit', 'Vitality', 'Movement', 'Other')
# the provided stat's name decides its family (checked in this order: "BULLET_ARMOR_DAMAGE_RESIST" is
# a resist, "MOVEMENT_SLOW_RESISTANCE" too)
_FAMILY_WORDS = (
    ('Vitality', ('RESIST', 'HEALTH', 'HEAL_AMP', 'BARRIER')),
    ('Movement', ('MOVEMENT', 'SPRINT', 'STAMINA', 'SLIDE', 'AIR_', 'DASH')),
    ('Weapon', ('WEAPON', 'BULLET', 'FIRE_RATE', 'AMMO', 'MELEE', 'RELOAD', 'ATTACK_RANGE', 'ZOOM')),
    ('Spirit', ('TECH', 'ABILITY', 'COOLDOWN', 'SPIRIT', 'ULTIMATE')),
)
_EMPTY = {'', 'None', '-1', '-2'}
INVALID = 'MODIFIER_VALUE_INVALID'
PROP = 'p:'                   # a property's own series in an item's history (tier and cost are plain keys)
# card sections whose stats are what the item does on a trigger, not the buyer's always-on stats
EFFECT_SECTIONS = ('Active', 'Conditional')
_TRIGGER = re.compile(r'Duration|Cooldown|ChargeUp|Stack|BuildUp', re.I)


def family(provided: str) -> str:
    for fam, words in _FAMILY_WORDS:
        if any(w in provided for w in words):
            return fam
    return 'Other'


def stat_key(provided: str) -> str:
    """'MODIFIER_VALUE_HEALTH_MAX' -> 'health_max'."""
    return provided.removeprefix('MODIFIER_VALUE_').lower()


def _num(v):
    if v is None or isinstance(v, bool):
        return None
    s = str(v).strip()
    if s in _EMPTY:
        return None
    try:
        x = float(s.rstrip('m%s'))
    except ValueError:
        return None
    return None if x == 0 else x


def _tier(item: dict) -> int | None:
    t = str(item.get('m_iItemTier') or '')
    return int(t.rsplit('_', 1)[-1]) if t.rsplit('_', 1)[-1].isdigit() else None


def _conditional(d: dict) -> bool:
    """Given only on a condition: m_eStatsUsageFlags (2025-04+) or the older m_UsageFlags."""
    return 'Conditional' in f'{d.get("m_eStatsUsageFlags") or ""} {d.get("m_UsageFlags") or ""}'


def _flag(d: dict, name: str) -> bool:
    return str(d.get(name)).lower() in ('true', '1')


def _section_props(sec: dict) -> list[str]:
    names: list[str] = []
    for attr in sec.get('m_vecSectionAttributes') or []:
        names += (list(attr.get('m_vecElevatedAbilityProperties') or [])
                  + [p.get('m_strImportantProperty') for p in attr.get('m_vecImportantAbilityProperties') or []]
                  + list(attr.get('m_vecAbilityProperties') or []))
    return [n for n in names if n]


def _triggered(names: list[str], props: dict) -> bool:
    """A Passive section that lists its own timer or stacks (a plain number named …Duration, …Cooldown,
    …ChargeUp…, …Stack…, BuildUp…) describes a buff the passive triggers — Active Reload's Move Speed after
    a perfect reload, Spellslinger's stacking Fire Rate, Spiritual Overflow's charged Spirit Power — not
    an always-on stat, though the game leaves its usage flags empty (review spot-check 2026-10-04: 7 of
    the 34 Passive-section stats)."""
    for n in names:
        d = props.get(n)
        if (isinstance(d, dict) and _num(d.get('m_strValue')) is not None and _TRIGGER.search(n)
                and str(d.get('m_eProvidedPropertyType') or INVALID) == INVALID):
            return True
    return False


def shown_props(item: dict) -> list[tuple[str, str]]:
    """(property, section) in the card's order: each tooltip section's elevated, important and plain
    properties, then the header values the sections did not list. A triggered Passive section
    (_triggered) reads 'Conditional'."""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    props = item.get('m_mapAbilityProperties') or {}
    for sec in item.get('m_vecTooltipSectionInfo') or []:
        kind = str(sec.get('m_eAbilitySectionType') or '').replace('EArea_', '')
        names = _section_props(sec)
        if kind == 'Passive' and _triggered(names, props):
            kind = 'Conditional'
        for n in names:
            if n not in seen:
                seen.add(n)
                out.append((n, kind))
    for n in HEADER_PROPS:
        if n not in seen:
            seen.add(n)
            out.append((n, 'Header'))
    return out


def key_of(prop: str, provided: str, conditional: bool, section: str | None) -> str:
    """The column a property feeds: its timing, the hero stat it always gives, or its own effect. A stat
    the card lists under Active is what the active does (Spirit Sap's -30 Spirit Power is the target's
    debuff; Colossus' +30% Melee Damage lasts while it runs), not the buyer's always-on stat, even when
    the game leaves its usage flags empty (review 2026-10-04: 7 such chips)."""
    if prop in TIMING:
        return TIMING[prop][0]
    if provided and provided != INVALID and not conditional and section not in EFFECT_SECTIONS:
        return stat_key(provided)
    return 'fx:' + prop


def prop_key(prop: str, d: dict, section: str | None = '') -> str:
    return key_of(prop, str(d.get('m_eProvidedPropertyType') or ''), _conditional(d), section)


def evaluate(item: dict, prices: list) -> dict:
    """Every number the item's card shows in this build, by column key (an absent one is not listed).
    A build whose item has no tooltip sections yet reads all its properties."""
    tier = _tier(item)
    out = {'tier': tier, 'cost': float(prices[tier]) if tier is not None and tier < len(prices) else None}
    props = item.get('m_mapAbilityProperties') or {}
    order = shown_props(item) if item.get('m_vecTooltipSectionInfo') else [(p, '') for p in props]
    for prop, section in order:
        d = props.get(prop)
        if not isinstance(d, dict):
            continue
        v = _num(d.get('m_strValue'))
        if v is None:
            continue
        out.setdefault(prop_key(prop, d, section), v)          # two properties giving one stat: the first, as the card
    return out


def snapshot(item: dict, prices: list) -> dict:
    """What history tracks of one build: tier, cost and EVERY number of the item by property name, on the
    card or not — a property later listed on the card, or later feeding another stat key, keeps its past."""
    tier = _tier(item)
    out = {'tier': tier, 'cost': float(prices[tier]) if tier is not None and tier < len(prices) else None}
    for prop, d in (item.get('m_mapAbilityProperties') or {}).items():
        if isinstance(d, dict):
            v = _num(d.get('m_strValue'))
            if v is not None:
                out[PROP + prop] = v
    return out


def prop_meta(item: dict) -> dict[str, tuple]:
    """prop -> (provided stat, conditional, card section, drawback, icon) for each number of the item.
    The section is the card's ('Innate', 'Passive', 'Active', 'Header'), None when the card leaves the
    property out, '' when the item has no card sections yet (builds before them)."""
    props = item.get('m_mapAbilityProperties') or {}
    secs = dict(shown_props(item)) if item.get('m_vecTooltipSectionInfo') else None
    out = {}
    for prop, d in props.items():
        if not isinstance(d, dict) or _num(d.get('m_strValue')) is None:
            continue
        out[prop] = (str(d.get('m_eProvidedPropertyType') or ''), _conditional(d),
                     '' if secs is None else secs.get(prop), _flag(d, 'm_bIsNegativeAttribute'), css_class(d))
    return out


class Enums:
    """Provided-stat enum names over the builds: when each was last used, and the switches properties
    made between them, so a name Valve retired maps to its successor (enum_aliases)."""

    def __init__(self) -> None:
        self.last_seen: dict[str, int] = {}
        self.moves: dict[tuple[str, str], int] = {}

    def aliases(self) -> dict[str, str]:
        """X -> Y when a property switched from X to Y in build B and no shop item used X from B on: a
        rename (BASEATTACK_DAMAGE_PERCENT -> WEAPON_DAMAGE_INCREASE, 6541), not one item changing stat."""
        out: dict[str, str] = {}
        for (x, y), b in sorted(self.moves.items(), key=lambda kv: kv[1]):
            if self.last_seen.get(x, 0) < b and x not in out:
                out[x] = y
        return out


def canon(provided: str, aliases: dict[str, str]) -> str:
    seen: set[str] = set()
    while provided in aliases and provided not in seen:
        seen.add(provided)
        provided = aliases[provided]
    return provided


def note_meta(metas: dict, iid: str, build: int, now: dict[str, tuple], enums: Enums) -> None:
    """Append each property's meta when it changed (kept only while the property has a value)."""
    ms = metas.setdefault(iid, {})
    for prop, m in now.items():
        if m[0]:
            enums.last_seen[m[0]] = build
        pts = ms.setdefault(prop, [])
        if pts and pts[-1][1] == m:
            continue
        if pts and pts[-1][1][0] and m[0] and pts[-1][1][0] != m[0]:
            enums.moves.setdefault((pts[-1][1][0], m[0]), build)
        pts.append([build, m])


def meta_at(ms: list, build: int) -> tuple | None:
    """The property's meta in `build`, or its last one before (a property without a value there)."""
    out = None
    for b, m in ms or []:
        if b > build:
            break
        out = m
    return out if out is not None else (ms[0][1] if ms else None)


def _feeds(prop: str, meta: tuple | None, aliases: dict[str, str]) -> str | None:
    """What a property fed, to join a renamed property to its predecessor: the stat it gives, or for a
    number with a provided type but no stat (conditional) that type; None for a plain number."""
    if meta is None:
        return None
    t = canon(meta[0], aliases)
    key = key_of(prop, t, meta[1], meta[2])
    if not key.startswith('fx:'):
        return key
    return 'fx-type:' + t if t and t != INVALID else None


def _added_at(pts: list) -> int | None:
    """The build a series got its first value, when it started empty (a property added later)."""
    if not pts or pts[0][2] is not None:
        return None
    return next((p[0] for p in pts if p[2] is not None), None)


def _ended_at(pts: list, build: int) -> float | None:
    """The value a series lost in `build` (None when it did not end there)."""
    return next((a[2] for a, b in zip(pts, pts[1:]) if a[2] is not None and b[2] is None and b[0] == build), None)


def _same_name(a: str, b: str) -> bool:
    """Two spellings of one property: Valve's "…TooltipOnly" twin, a typo fixed (InteruptCooldown)."""
    return a.startswith(b) or b.startswith(a) or SequenceMatcher(None, a, b).ratio() >= 0.9


def joined(hs: dict, metas: dict, prop: str, aliases: dict[str, str], taken: set) -> tuple[list, list]:
    """(points, [(from build, property)]) of a property's series, joined to the property it replaced: one
    of the same item that lost its value in the very build this one got its first, and fed the same stat
    (BonusSpirit -> TechPower, TechPower -> SpiritPower, ReturnFireBulletResist -> BulletResist) — or, a
    plain number, had the same value and the same name respelled (RicochetTargetsTooltipOnly ->
    RicochetTargets, InteruptCooldown -> InterruptCooldown). Renamed alone, the old value's history was
    lost and the new one read "added". Of several, the one that handed over the same value. `taken`
    collects the joined properties."""
    pts = list(hs.get(PROP + prop) or [])
    segs = [(0, prop)]
    cur = prop
    for _ in range(8):
        start = _added_at(pts)
        if start is None:
            break
        value = next(p[2] for p in pts if p[0] == start)
        feeds = _feeds(cur, meta_at(metas.get(cur), start), aliases)
        cands = []
        for q in (k[len(PROP):] for k in hs if k.startswith(PROP)):
            lost = _ended_at(hs[PROP + q], start) if q != cur and q not in taken else None
            if lost is None:
                continue
            q_feeds = _feeds(q, meta_at(metas.get(q), start), aliases)
            if (feeds is not None and q_feeds == feeds) or (
                    feeds is None and q_feeds is None and lost == value and _same_name(q, cur)):
                cands.append((lost != value, len(cands), q))
        if not cands:
            break
        prev = min(cands)[2]
        taken.add(prev)
        pts = [p for p in hs[PROP + prev] if p[0] < start] + [p for p in pts if p[0] >= start]
        segs = [(0, prev), (start, segs[0][1])] + segs[1:]
        cur = prev
    return pts, segs


def directed(changes: list[list], segs: list, metas: dict) -> list[list]:
    """[[build, date, old, new]] -> [[build, date, old, new, 'buff'|'nerf'|'changed']]: the direction the
    item pages give the same step (semantics.direction, the drawback flag of that build), so a table chip
    and the item's page never disagree (Toxic Bullets' anti-heal -30 -> -35 is a buff, Glass Cannon's
    health penalty -15 -> -13 too; 33 steps read the opposite way, review 2026-10-04)."""
    out = []
    for b, date, old, new in changes:
        prop = next(p for s, p in reversed(segs) if s <= b)
        m = meta_at(metas.get(prop), b)
        d, _ = direction(f'm_mapAbilityProperties.{prop}.m_strValue', old, new, 'item', bool(m and m[3]))
        out.append([b, date, old, new, d])
    return out


def overall(hist: list[list], prop: str, metas: dict) -> str | None:
    """The direction of a whole history (first old -> last new) for the tooltip's "Overall" line."""
    if not hist or not isinstance(hist[0][2], (int, float)) or not isinstance(hist[-1][3], (int, float)):
        return None
    m = (metas.get(prop) or [[0, None]])[-1][1]
    return direction(f'm_mapAbilityProperties.{prop}.m_strValue', hist[0][2], hist[-1][3], 'item',
                     bool(m and m[3]))[0]


def _unit(value: str, provided: str = '') -> str:
    """The unit a card value prints; a speed's "m" is m/s (the card writes "+2m/s" since
    abilities.is_speed, this keeps a stale card value consistent with the column)."""
    v = str(value).strip()
    if v.endswith('m/s'):
        return 'm/s'
    if v.endswith('%'):
        return '%'
    if v.endswith('m'):
        return 'm/s' if is_speed({'m_eProvidedPropertyType': provided}) else 'm'
    if v.endswith('s') and v[-2:-1].isdigit():
        return 's'
    return ''


def _digits(values) -> int:
    best = 0
    for v in values:
        if isinstance(v, float) and not v.is_integer():
            best = max(best, min(2, len(f'{v:.4f}'.rstrip('0').split('.')[1])))
    return best


def card_props(card: dict) -> dict[str, dict]:
    """prop -> {label, value, css, section} as the item's tooltip card prints it (pipeline.abilities)."""
    out: dict[str, dict] = {}
    for sec in card.get('sections') or []:
        for p in sec.get('props') or []:
            out.setdefault(p['prop'], {**p, 'section': sec.get('type') or ''})
    for h in card.get('header') or []:
        out.setdefault(h['prop'], {**h, 'section': 'Header'})
    return out


def derive_columns(items: list[dict]) -> list[dict]:
    """items: [{'values': {key: v}, 'raw': {key: (prop, provided type)}, 'card': {prop: {label, value, css}}}]
    of the shop's items in the newest build -> the table's columns: Shop, the stats STAT_MIN_ITEMS items
    give (by family, most common first), Utility (cooldown, duration)."""
    count: Counter = Counter()
    labels: dict[str, Counter] = {}
    units: dict[str, Counter] = {}
    css: dict[str, Counter] = {}
    props: dict[str, Counter] = {}
    provided: dict[str, str] = {}
    values: dict[str, list] = {}
    for it in items:
        for key, (prop, ptype) in it['raw'].items():
            if not ptype:
                continue
            count[key] += 1
            provided[key] = ptype
            c = it['card'].get(prop) or {}
            labels.setdefault(key, Counter())[c.get('label') or humanize(prop)] += 1
            units.setdefault(key, Counter())[_unit(c.get('value', ''), ptype)] += 1
            css.setdefault(key, Counter())[c.get('css') or ''] += 1
            props.setdefault(key, Counter())[prop] += 1
            values.setdefault(key, []).append(it['values'].get(key))
    stats = [k for k, n in count.items() if n >= STAT_MIN_ITEMS]
    stats.sort(key=lambda k: (FAMILIES.index(family(provided[k])), -count[k], k))
    cols = [{'key': 'tier', 'label': 'Tier', 'group': 'Shop', 'pol': 0, 'digits': 0, 'unit': ''},
            {'key': 'cost', 'label': 'Cost', 'group': 'Shop', 'pol': -1, 'digits': 0, 'unit': '', 'css': 'souls'}]
    for k in stats:
        prop = props[k].most_common(1)[0][0]
        cols.append({'key': k, 'label': labels[k].most_common(1)[0][0], 'group': family(provided[k]),
                     'pol': polarity(f'm_mapAbilityProperties.{prop}.m_strValue'), 'digits': _digits(values[k]),
                     'unit': units[k].most_common(1)[0][0], 'css': css[k].most_common(1)[0][0] or None,
                     'stat': True, 'n': count[k]})
    for prop, (key, label, icon) in TIMING.items():
        cols.append({'key': key, 'label': label, 'group': 'Utility',
                     'pol': polarity(f'm_mapAbilityProperties.{prop}.m_strValue'),
                     'digits': _digits([it['values'].get(key) for it in items]), 'unit': 's', 'css': icon})
    return cols


def row_effects(raw: dict, values: dict, card: dict, columns: set[str]) -> list[dict]:
    """The numbers of the card that have no column, in the card's order, as the game prints them; an
    Active-section number says so (`active`): "+70% Spirit Lifesteal" while Infuser runs is not its
    always-on +13%."""
    out = []
    for key, (prop, _) in raw.items():
        if key in columns:
            continue
        c = card.get(prop)
        if not c:                                     # the card leaves it out (an empty or -1 value)
            continue
        e = {'key': key, 'label': c['label'], 'value': c['value'], 'css': c.get('css'),
             'pol': polarity(f'm_mapAbilityProperties.{prop}.m_strValue'), 'digits': _digits([values.get(key)])}
        if c.get('section') == 'Active':
            e['active'] = True
        out.append(e)
    return out


def _raw_keys(item: dict) -> dict[str, tuple[str, str]]:
    """key -> (property, provided stat type or '') for the numbers evaluate() returns, in card order."""
    props = item.get('m_mapAbilityProperties') or {}
    out: dict[str, tuple[str, str]] = {}
    for prop, section in shown_props(item):
        d = props.get(prop)
        if not isinstance(d, dict) or _num(d.get('m_strValue')) is None:
            continue
        key = prop_key(prop, d, section)
        if key not in out:
            out[key] = (prop, '' if key.startswith('fx:') or prop in TIMING else str(d.get('m_eProvidedPropertyType')))
    return out


def _is_shop_item(iid: str, item: dict) -> bool:
    return (iid.startswith('upgrade_') and isinstance(item, dict) and item.get('m_iItemTier')
            and not item.get('_not_pickable'))


def in_shop(item: dict) -> bool:
    """Sold in the shop now: tier I-IV, not Street Brawl's draft-only tier V, not disabled."""
    return ((_tier(item) or 9) <= 4 and 'StreetBrawl' not in str(item.get('m_eAbilityRequirements') or '')
            and str(item.get('m_bDisabled')).lower() not in ('true', '1'))


def track(series: dict, first: dict, iid: str, build: int, date: str, vals: dict) -> None:
    """Append one build's values to an item's series: a key first seen after the item's own first build
    starts from None there (a stat added later is an addition, not the item's first value)."""
    hs = series.setdefault(iid, {})
    first.setdefault(iid, (build, date))
    for k in set(hs) | set(vals):
        v = vals.get(k)
        pts = hs.get(k)
        if pts is None:
            if v is None:
                continue
            pts = hs[k] = [] if first[iid][0] == build else [[first[iid][0], first[iid][1], None]]
        if not pts or pts[-1][2] != v:
            pts.append([build, date, v])


def item_history(hs: dict, metas: dict, raw: dict, now: dict, columns: set[str], aliases: dict[str, str]) -> dict:
    """An item's history by the newest build's keys: {'history': {key: steps}, 'odir': {key: overall},
    'removed': [{'prop', 'key', 'history'}]}. Each key reads the property that feeds it now (joined to a
    renamed predecessor); a property the item lost keeps its history under the key it fed last — a column
    stat as the column's empty "gone" marker, a card number as a removed effect."""
    history, odir, taken = {}, {}, set()
    for k in ('tier', 'cost'):
        h = history_changes(hs.get(k) or [])
        if h:
            history[k] = h
    sources = {prop for prop, _ in raw.values()}
    for key, (prop, _) in raw.items():
        pts, segs = joined(hs, metas, prop, aliases, taken | (sources - {prop}))
        taken.update(p for _, p in segs)
        h = directed(history_changes(pts), segs, metas)
        if h:
            history[key] = h
            d = overall(h, prop, metas)
            if d:
                odir[key] = d
    removed: list[dict] = []
    gone: dict[str, tuple[int, str, list]] = {}
    for k, pts in hs.items():
        prop = k[len(PROP):]
        if not k.startswith(PROP) or prop in taken or not pts or pts[-1][2] is not None:
            continue
        m = (metas.get(prop) or [[0, None]])[-1][1]
        if m is None:
            continue
        key = key_of(prop, canon(m[0], aliases), m[1], m[2])
        h = directed(history_changes(pts), [(0, prop)], metas)
        if not h:
            continue
        if key in columns and now.get(key) is None:
            if key not in gone or gone[key][0] < pts[-1][0]:
                gone[key] = (pts[-1][0], prop, h)
        elif key.startswith('fx:') and m[2]:
            # a number the card showed (its section is known) and the item no longer has
            removed.append({'prop': prop, 'key': key, 'css': m[4], 'history': h})
    for key, (_, prop, h) in gone.items():
        history[key] = h
    return {'history': history, 'odir': odir, 'removed': removed}


def collect(snapshots) -> tuple[dict, dict, Enums]:
    """[(build, date, abilities.vdata items, item prices)] oldest first -> (series, metas, enums): every
    shop item's numbers by property (track), each property's meta (note_meta) and the stat enums seen."""
    series: dict[str, dict[str, list]] = {}
    metas: dict[str, dict[str, list]] = {}
    first: dict[str, tuple] = {}
    enums = Enums()
    for build, date, items, prices in snapshots:
        for iid, it in items.items():
            if _is_shop_item(iid, it):
                track(series, first, iid, build, date, snapshot(it, prices))
                note_meta(metas, iid, build, prop_meta(it), enums)
    return series, metas, enums


def build() -> dict:
    from .abilities import _label, card as ability_card
    t0 = time.time()
    newest: dict = {}

    def snapshots():
        last = (None, None)
        for b in tracker.builds():
            if b.build is None or (last != (None, None) and not any(p in b.files for p in WATCH)):
                continue
            blobs = tuple(tracker.blob_id(b.commit, p) for p in WATCH)
            if blobs == last or None in blobs:
                continue
            last = blobs
            items = cache.vdata_blob(blobs[0])
            prices = cache.vdata_blob(blobs[1]).get('m_nItemPricePerTier') or []
            newest.update(items=items, prices=prices, build=b)
            yield b.build, b.date[:10], items, prices
    series, metas, enums = collect(snapshots())
    last_items, last_prices, last_build = newest['items'], newest['prices'], newest['build']
    aliases = enums.aliases()
    tok = loc.tokens(last_build.commit)
    live = {iid: it for iid, it in sorted(last_items.items())
            if _is_shop_item(iid, it) and str(it.get('m_bDisabled')).lower() not in ('true', '1')}
    cards = {iid: card_props(ability_card(iid, it, tok, 'item', None)) for iid, it in live.items()}
    now = {iid: evaluate(it, last_prices) for iid, it in live.items()}
    raw = {iid: _raw_keys(it) for iid, it in live.items()}
    cols = derive_columns([{'values': now[i], 'raw': raw[i], 'card': cards[i]} for i in live if in_shop(live[i])])
    col_keys = {c['key'] for c in cols}
    rows = []
    for iid, it in live.items():
        values = {k: now[iid][k] for k in col_keys if now[iid].get(k) is not None}
        shown = {k: cards[iid][p]['value'] for k, (p, _) in raw[iid].items() if k in col_keys and p in cards[iid]}
        effects = row_effects(raw[iid], now[iid], cards[iid], col_keys)
        hist = item_history(series.get(iid, {}), metas.get(iid, {}), raw[iid], values, col_keys, aliases)
        keys = col_keys | {e['key'] for e in effects}
        removed = [{'key': r['key'], 'label': _label(tok, r['prop'], iid), 'css': r['css'],
                    'pol': polarity(f'm_mapAbilityProperties.{r["prop"]}.m_strValue'),
                    'digits': _digits([h[2] for h in r['history']]), 'history': r['history']}
                   for r in hist['removed']]
        rows.append({
            'id': iid,
            'name': loc.plain(loc.entity_name(tok, iid)),
            'slot': SLOTS.get(str(it.get('m_eItemSlotType')), ''),
            'activation': 'Active' if 'PASSIVE' not in str(it.get('m_eAbilityActivation', '')) else 'Passive',
            'values': values,
            'shown': shown,
            'effects': effects,
            'removed': removed,
            'history': {k: h for k, h in hist['history'].items() if k in keys},
            'odir': {k: d for k, d in hist['odir'].items() if k in keys},
        })
    data = {'build': last_build.build, 'date': last_build.date, 'columns': cols,
            'items': sorted(rows, key=lambda r: (r['slot'], r['values'].get('tier') or 0, r['name'].lower()))}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    renamed = ', '.join(f'{stat_key(a)}->{stat_key(b)}' for a, b in sorted(aliases.items()))
    print(f'{len(rows)} items, {len(cols)} columns, renamed stats: {renamed or "none"}, '
          f'{time.time() - t0:.0f}s -> {OUT}')
    return data


if __name__ == '__main__':
    build()
