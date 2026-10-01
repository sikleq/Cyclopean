"""Units & buildings stats table with per-cell history (troopers, guardians,
walkers, patron, shrines, neutrals, mid-boss).

Fields moved over time (flat trooper DPS fields became m_VS* blocks in build
6468; m_WeaponInfo became m_mapWeaponInfos.primary in 6711), so every column
lists candidate paths and takes the first that exists in that build.

    python -m pipeline.unit_table   ->  data/tables/units.json
"""
from __future__ import annotations

import json
import time

from . import cache, loc, tracker
from .classify import unit_kind
from .semantics import UNITS_PER_METER

OUT = tracker.ROOT / 'data' / 'tables' / 'units.json'
PATH = tracker.SCRIPTS + 'npc_units.vdata'
KINDS = ('building', 'trooper', 'neutral')
WEAPON_PREFIXES = ('m_mapWeaponInfos.primary.', 'm_WeaponInfo.')

# key, label, group, candidate paths, metres?, polarity (for colouring only), digits
COLUMNS = (
    ('hp', 'Health', 'Vitality', ('m_nMaxHealth', 'm_iMaxHealth', 'm_iStartingHealth', 'm_iMaxHealthGenerator'), False, 0, 0),
    ('hp_min', 'Health / min', 'Vitality', ('m_iHealthGainPerMinute', 'm_ObjectiveHealthGrowthPhase1'), False, 0, 1),
    ('res_hero', 'Resist vs Heroes', 'Vitality', ('m_flPlayerDamageResistPct', 'm_VSPlayer.m_flDamageResist'), False, 0, 1),
    ('res_trooper', 'Resist vs Troopers', 'Vitality', ('m_flTrooperDamageResistPct', 'm_VSTrooper.m_flDamageResist'), False, 0, 1),
    ('backdoor_regen', 'Backdoor Regen', 'Vitality', ('m_BackdoorProtectionModifier.m_flHealthPerSecondRegen',), False, 0, 1),
    ('dps_hero', 'DPS vs Heroes', 'Attack', ('m_flPlayerDPS', 'm_VSPlayer.m_flBaseDPS'), False, 0, 1),
    ('dps_trooper', 'DPS vs Troopers', 'Attack', ('m_flTrooperDPS', 'm_VSTrooper.m_flBaseDPS'), False, 0, 1),
    ('melee', 'Melee Damage', 'Attack', ('m_flMeleeDamage',), False, 0, 1),
    ('stomp', 'Stomp Damage', 'Attack', ('m_flStompDamage',), False, 0, 0),
    ('bullet', 'Bullet Damage', 'Attack', tuple(p + 'm_flBulletDamage' for p in WEAPON_PREFIXES), False, 0, 2),
    ('cycle', 'Fire Interval (s)', 'Attack', tuple(p + 'm_flCycleTime' for p in WEAPON_PREFIXES), False, 0, 3),
    ('range', 'Range (m)', 'Attack', tuple(p + 'm_flRange' for p in WEAPON_PREFIXES), True, 0, 1),
    ('bounty', 'Soul Bounty', 'Reward', ('m_flGoldReward',), False, 0, 0),
    ('bounty_min', 'Bounty growth %/min', 'Reward', ('m_flGoldRewardBonusPercentPerMinute',), False, 0, 2),
    ('run', 'Run Speed (m/s)', 'Movement', ('m_flRunSpeed',), True, 0, 2),
    ('walk', 'Walk Speed (m/s)', 'Movement', ('m_flWalkSpeed',), True, 0, 2),
)


def _get(obj: dict, dotted: str):
    cur = obj
    for part in dotted.split('.'):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    if isinstance(cur, bool) or cur is None:
        return None
    try:
        return float(str(cur).rstrip('m%s'))
    except ValueError:
        return None


def evaluate(unit: dict) -> dict:
    out = {}
    for key, _, _, paths, meters, _, digits in COLUMNS:
        v = next((x for x in (_get(unit, p) for p in paths) if x is not None), None)
        if v is not None and meters:
            v = v / UNITS_PER_METER
        out[key] = None if v is None else round(v, digits + 2)
    return out


def build() -> dict:
    t0 = time.time()
    series: dict[str, dict[str, list]] = {}
    last_blob = None
    last_units: dict = {}
    last_build = None
    for b in tracker.builds():
        if b.build is None or (last_blob is not None and PATH not in b.files):
            continue
        blob = tracker.blob_id(b.commit, PATH)
        if blob is None or blob == last_blob:
            continue
        last_blob = blob
        units = cache.vdata_blob(blob)
        for uid, u in units.items():
            if not isinstance(u, dict) or u.get('_not_pickable') or unit_kind(uid, u) not in KINDS:
                continue
            hs = series.setdefault(uid, {})
            for k, v in evaluate(u).items():
                pts = hs.setdefault(k, [])
                if not pts or pts[-1][2] != v:
                    pts.append([b.build, b.date[:10], v])
        last_units, last_build = units, b
    tok = loc.tokens(last_build.commit)
    rows = []
    for uid, u in sorted(last_units.items()):
        if uid not in series or not isinstance(u, dict):
            continue
        hs = series[uid]
        values = {k: pts[-1][2] for k, pts in hs.items()}
        if not any(v is not None for v in values.values()):
            continue
        rows.append({
            'id': uid,
            'name': loc.unit_name(tok, uid, u),
            'kind': unit_kind(uid, u),
            'values': values,
            'history': {k: [[pts[i][0], pts[i][1], pts[i - 1][2], pts[i][2]] for i in range(1, len(pts))]
                        for k, pts in hs.items() if len(pts) > 1},
        })
    data = {
        'build': last_build.build, 'date': last_build.date,
        'columns': [{'key': k, 'label': lbl, 'group': g, 'pol': pol, 'digits': d}
                    for k, lbl, g, _, _, pol, d in COLUMNS],
        'units': sorted(rows, key=lambda r: (KINDS.index(r['kind']), r['name'].lower())),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'{len(rows)} units, {time.time() - t0:.0f}s -> {OUT}')
    return data


if __name__ == '__main__':
    build()
