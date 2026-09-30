"""Shop items table with per-cell history.

Cost comes from generic_data m_nItemPricePerTier[tier] of the same build (items
have no own price field). Property columns read m_mapAbilityProperties.<P>.m_strValue;
an item that does not have a property shows a dash.

    python -m pipeline.item_table   ->  data/tables/items.json
"""
from __future__ import annotations

import json
import time

from . import cache, loc, tracker

OUT = tracker.ROOT / 'data' / 'tables' / 'items.json'
WATCH = (tracker.SCRIPTS + 'abilities.vdata', tracker.SCRIPTS + 'generic_data.vdata')
SLOTS = {'EItemSlotType_WeaponMod': 'Weapon', 'EItemSlotType_Armor': 'Vitality', 'EItemSlotType_Tech': 'Spirit'}

# key, label, group, property (None = computed), polarity, digits
PROPS = (
    ('cooldown', 'Cooldown', 'Active', 'AbilityCooldown', -1, 1),
    ('duration', 'Duration', 'Active', 'AbilityDuration', 1, 1),
    ('cast_range', 'Cast Range', 'Active', 'AbilityCastRange', 1, 1),
    ('health', 'Bonus Health', 'Stats', 'BonusHealth', 1, 0),
    ('health_regen', 'Health Regen', 'Stats', 'BonusHealthRegen', 1, 1),
    ('ooc_regen', 'Out-of-combat Regen', 'Stats', 'OutOfCombatHealthRegen', 1, 1),
    ('weapon_dmg', 'Weapon Damage %', 'Stats', 'BaseAttackDamagePercent', 1, 0),
    ('fire_rate', 'Fire Rate %', 'Stats', 'BonusFireRate', 1, 0),
    ('ammo', 'Ammo %', 'Stats', 'BonusClipSizePercent', 1, 0),
    ('spirit', 'Spirit Power', 'Stats', 'TechPower', 1, 0),
    ('bullet_resist', 'Bullet Resist', 'Stats', 'BulletResist', 1, 0),
    ('spirit_resist', 'Spirit Resist', 'Stats', 'TechResist', 1, 0),
    ('move', 'Move Speed', 'Stats', 'BonusMoveSpeed', 1, 1),
    ('sprint', 'Sprint', 'Stats', 'BonusSprintSpeed', 1, 1),
)


def _num(v):
    if v is None or isinstance(v, bool):
        return None
    try:
        return float(str(v).rstrip('m%s'))
    except ValueError:
        return None


def _tier(item: dict) -> int | None:
    t = str(item.get('m_iItemTier') or '')
    return int(t.rsplit('_', 1)[-1]) if t.rsplit('_', 1)[-1].isdigit() else None


def evaluate(item: dict, prices: list) -> dict:
    tier = _tier(item)
    out = {'tier': tier, 'cost': float(prices[tier]) if tier is not None and tier < len(prices) else None}
    props = item.get('m_mapAbilityProperties') or {}
    for key, _, _, prop, _, _ in PROPS:
        p = props.get(prop)
        v = _num(p.get('m_strValue')) if isinstance(p, dict) else None
        out[key] = None if v in (None, 0.0) else v
    return out


def _is_shop_item(iid: str, item: dict) -> bool:
    return (iid.startswith('upgrade_') and isinstance(item, dict) and item.get('m_iItemTier')
            and not item.get('_not_pickable'))


def build() -> dict:
    t0 = time.time()
    series: dict[str, dict[str, list]] = {}
    last = (None, None)
    last_items: dict = {}
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
            if not _is_shop_item(iid, it):
                continue
            hs = series.setdefault(iid, {})
            for k, v in evaluate(it, prices).items():
                pts = hs.setdefault(k, [])
                if not pts or pts[-1][2] != v:
                    pts.append([b.build, b.date[:10], v])
        last_items, last_build = items, b
    tok = loc.tokens(last_build.commit)
    rows = []
    for iid, it in sorted(last_items.items()):
        if not _is_shop_item(iid, it) or str(it.get('m_bDisabled')).lower() in ('true', '1'):
            continue
        hs = series.get(iid, {})
        values = {k: pts[-1][2] for k, pts in hs.items()}
        active = 'Active' if 'PASSIVE' not in str(it.get('m_eAbilityActivation', '')) else 'Passive'
        rows.append({
            'id': iid,
            'name': loc.plain(loc.entity_name(tok, iid)),
            'slot': SLOTS.get(str(it.get('m_eItemSlotType')), ''),
            'activation': active,
            'values': values,
            'history': {k: [[pts[i][0], pts[i][1], pts[i - 1][2], pts[i][2]] for i in range(1, len(pts))]
                        for k, pts in hs.items() if len(pts) > 1},
        })
    cols = [{'key': 'tier', 'label': 'Tier', 'group': 'Shop', 'pol': 0, 'digits': 0},
            {'key': 'cost', 'label': 'Cost', 'group': 'Shop', 'pol': -1, 'digits': 0}]
    cols += [{'key': k, 'label': lbl, 'group': g, 'pol': pol, 'digits': d} for k, lbl, g, _, pol, d in PROPS]
    data = {'build': last_build.build, 'date': last_build.date, 'columns': cols,
            'items': sorted(rows, key=lambda r: (r['slot'], r['values'].get('tier') or 0, r['name'].lower()))}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'{len(rows)} items, {time.time() - t0:.0f}s -> {OUT}')
    return data


if __name__ == '__main__':
    build()
