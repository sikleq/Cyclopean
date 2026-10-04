"""Shop items table with per-cell history.

What a row holds comes from the item's own tooltip card (m_vecTooltipSectionInfo + the header values),
i.e. what the game shows, not a hand-picked list (2026-10-04: 14 hardcoded properties left 67-84% of
the cells empty and never showed an item's headline number, e.g. Headshot Booster's +45):

  - Shop: tier, and cost from generic_data m_nItemPricePerTier[tier] of the same build;
  - stats: a property that feeds a hero stat (m_eProvidedPropertyType) and is always on (no
    "Conditional" usage flag), keyed by the stat it provides — TechPower and SpiritPower are one
    Spirit Power. A stat that STAT_MIN_ITEMS shop items give is a column, grouped Weapon / Spirit /
    Vitality / Movement by the stat's name (family());
  - Utility: the item ability's cooldown and duration;
  - effects: every other number the card shows (Head Shot Bonus Damage +45, the +3000 Health a
    conditional active gives, a stat only one or two items have), with the card's label and value.

Every value keeps its history over all builds.

    python -m pipeline.item_table   ->  data/tables/items.json
"""
from __future__ import annotations

import json
import time
from collections import Counter

from .hero_table import history_changes
from .semantics import humanize, polarity
from . import cache, loc, tracker

OUT = tracker.ROOT / 'data' / 'tables' / 'items.json'
WATCH = (tracker.SCRIPTS + 'abilities.vdata', tracker.SCRIPTS + 'generic_data.vdata')
SLOTS = {'EItemSlotType_WeaponMod': 'Weapon', 'EItemSlotType_Armor': 'Vitality', 'EItemSlotType_Tech': 'Spirit'}

# the item ability's own timing: always columns (Utility); cast range, charges and channel are effects
TIMING = {'AbilityCooldown': ('cooldown', 'Cooldown', 'cooldown'), 'AbilityDuration': ('duration', 'Duration', 'duration')}
HEADER_PROPS = ('AbilityCooldown', 'AbilityCastRange', 'AbilityDuration', 'AbilityCharges',
                'AbilityCooldownBetweenCharge', 'AbilityChannelTime')
STAT_MIN_ITEMS = 3            # a stat this many shop items give is a column; rarer ones are effects
FAMILIES = ('Weapon', 'Spirit', 'Vitality', 'Movement', 'Utility')
# the provided stat's name decides its family (checked in this order: "BULLET_ARMOR_DAMAGE_RESIST" is
# a resist, "MOVEMENT_SLOW_RESISTANCE" too); an unknown new stat lands in Utility, never dropped
_FAMILY_WORDS = (
    ('Vitality', ('RESIST', 'HEALTH', 'HEAL_AMP', 'BARRIER')),
    ('Movement', ('MOVEMENT', 'SPRINT', 'STAMINA', 'SLIDE', 'AIR_', 'DASH')),
    ('Weapon', ('WEAPON', 'BULLET', 'FIRE_RATE', 'AMMO', 'MELEE', 'RELOAD', 'ATTACK_RANGE', 'ZOOM')),
    ('Spirit', ('TECH', 'ABILITY', 'COOLDOWN', 'SPIRIT', 'ULTIMATE')),
)
_EMPTY = {'', 'None', '-1', '-2'}


def family(provided: str) -> str:
    for fam, words in _FAMILY_WORDS:
        if any(w in provided for w in words):
            return fam
    return 'Utility'


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


def shown_props(item: dict) -> list[tuple[str, str]]:
    """(property, section) in the card's order: each tooltip section's elevated, important and plain
    properties, then the header values the sections did not list."""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for sec in item.get('m_vecTooltipSectionInfo') or []:
        kind = str(sec.get('m_eAbilitySectionType') or '').replace('EArea_', '')
        for attr in sec.get('m_vecSectionAttributes') or []:
            names = (list(attr.get('m_vecElevatedAbilityProperties') or [])
                     + [p.get('m_strImportantProperty') for p in attr.get('m_vecImportantAbilityProperties') or []]
                     + list(attr.get('m_vecAbilityProperties') or []))
            for n in names:
                if n and n not in seen:
                    seen.add(n)
                    out.append((n, kind))
    for n in HEADER_PROPS:
        if n not in seen:
            seen.add(n)
            out.append((n, 'Header'))
    return out


def prop_key(prop: str, d: dict) -> str:
    """The column a shown property feeds: its timing, the hero stat it always gives, or its own effect."""
    if prop in TIMING:
        return TIMING[prop][0]
    t = str(d.get('m_eProvidedPropertyType') or '')
    if t and t != 'MODIFIER_VALUE_INVALID' and not _conditional(d):
        return stat_key(t)
    return 'fx:' + prop


def evaluate(item: dict, prices: list) -> dict:
    """Every number the item's card shows in this build, by column key (an absent one is not listed).
    A build whose item has no tooltip sections yet reads all its properties, so a stat the card lists
    later does not turn into an "addition" on the day the sections appeared."""
    tier = _tier(item)
    out = {'tier': tier, 'cost': float(prices[tier]) if tier is not None and tier < len(prices) else None}
    props = item.get('m_mapAbilityProperties') or {}
    order = shown_props(item) if item.get('m_vecTooltipSectionInfo') else [(p, '') for p in props]
    for prop, _ in order:
        d = props.get(prop)
        if not isinstance(d, dict):
            continue
        v = _num(d.get('m_strValue'))
        if v is None:
            continue
        out.setdefault(prop_key(prop, d), v)          # two properties giving one stat: the first, as the card
    return out


def _unit(value: str, provided: str = '') -> str:
    v = str(value).strip()
    if v.endswith('m/s'):
        return 'm/s'
    if v.endswith('%'):
        return '%'
    if v.endswith('m'):
        return 'm/s' if 'SPEED' in provided else 'm'
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
    """The numbers of the card that have no column, in the card's order, as the game prints them."""
    out = []
    for key, (prop, _) in raw.items():
        if key in columns:
            continue
        c = card.get(prop)
        if not c:                                     # the card leaves it out (an empty or -1 value)
            continue
        out.append({'key': key, 'label': c['label'], 'value': c['value'], 'css': c.get('css'),
                    'pol': polarity(f'm_mapAbilityProperties.{prop}.m_strValue'), 'digits': _digits([values.get(key)])})
    return out


def _raw_keys(item: dict) -> dict[str, tuple[str, str]]:
    """key -> (property, provided stat type or '') for the numbers evaluate() returns, in card order."""
    props = item.get('m_mapAbilityProperties') or {}
    out: dict[str, tuple[str, str]] = {}
    for prop, _ in shown_props(item):
        d = props.get(prop)
        if not isinstance(d, dict) or _num(d.get('m_strValue')) is None:
            continue
        key = prop_key(prop, d)
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


def build() -> dict:
    from .abilities import card as ability_card
    t0 = time.time()
    series: dict[str, dict[str, list]] = {}
    first: dict[str, tuple] = {}
    last = (None, None)
    last_items: dict = {}
    last_prices: list = []
    last_build = None
    for b in tracker.builds():
        if b.build is None or (last != (None, None) and not any(p in b.files for p in WATCH)):
            continue
        blobs = tuple(tracker.blob_id(b.commit, p) for p in WATCH)
        if blobs == last or None in blobs:
            continue
        last = blobs
        items = cache.vdata_blob(blobs[0])
        prices = cache.vdata_blob(blobs[1]).get('m_nItemPricePerTier') or []
        for iid, it in items.items():
            if _is_shop_item(iid, it):
                track(series, first, iid, b.build, b.date[:10], evaluate(it, prices))
        last_items, last_prices, last_build = items, prices, b
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
        hs = series.get(iid, {})
        values = {k: now[iid][k] for k in col_keys if now[iid].get(k) is not None}
        shown = {k: cards[iid][p]['value'] for k, (p, _) in raw[iid].items() if k in col_keys and p in cards[iid]}
        effects = row_effects(raw[iid], now[iid], cards[iid], col_keys)
        keys = col_keys | {e['key'] for e in effects}
        history = {k: history_changes(pts) for k, pts in hs.items() if k in keys}
        rows.append({
            'id': iid,
            'name': loc.plain(loc.entity_name(tok, iid)),
            'slot': SLOTS.get(str(it.get('m_eItemSlotType')), ''),
            'activation': 'Active' if 'PASSIVE' not in str(it.get('m_eAbilityActivation', '')) else 'Passive',
            'values': values,
            'shown': shown,
            'effects': effects,
            'history': {k: h for k, h in history.items() if h},
        })
    data = {'build': last_build.build, 'date': last_build.date, 'columns': cols,
            'items': sorted(rows, key=lambda r: (r['slot'], r['values'].get('tier') or 0, r['name'].lower()))}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'{len(rows)} items, {len(cols)} columns, {time.time() - t0:.0f}s -> {OUT}')
    return data


if __name__ == '__main__':
    build()
