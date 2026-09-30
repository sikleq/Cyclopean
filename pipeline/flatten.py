"""Flatten a vdata entity into {path: scalar} so two builds can be diffed.

Paths are stable across builds:
- dict keys join with '.';
- lists of dicts that carry an identifying field are keyed by it
  (`m_vecPropertyUpgrades{BonusDamage}`) so reordering is not a change;
- other lists of dicts keep their index (`m_vecAbilityUpgrades[2]` = tier 3);
- lists of scalars collapse to one sorted tuple leaf (set semantics).

Scalars are normalised: numeric strings become numbers ('4' == 4), a unit
suffix is kept separately ('1.5m' -> 1.5 with unit 'm').
"""
from __future__ import annotations

import re

ID_FIELDS = (
    'm_strPropertyName',
    '_my_subclass_name',
    'm_strName',
    'm_strAbilityName',
    'm_eModifierValue',
    'm_eStatType',
    'm_strImportantProperty',
    'm_strStatName',
)

_NUM_RE = re.compile(r'^\s*(-?(?:\d+\.?\d*|\.\d+))\s*(m|s|%|x|u)?\s*$')

# Schema renames: old path prefix -> canonical (current) prefix, so a rename is
# not reported as "every field removed + every field added".
ALIASES = (
    ('m_WeaponInfo.', 'm_mapWeaponInfos.primary.'),        # build 6711 (2026-09-29)
    ('m_nAbilityBehaviors', 'm_AbilityBehaviorsBits'),       # build 5201 (2024-09)
)

# Paths that are never a game change worth recording.
EXCLUDE_RE = re.compile(
    r'(m_PopularItems|m_mapItemDraftBucketing|ItemDraftCounterWeights|BotDifficulty|'
    r'm_HUDPanel|(^|\.)_editor|Tangent(\.|$)|m_nRecoilSeed|m_unTimestamp)'
)


def canonical(path: str) -> str:
    for old, new in ALIASES:
        if path.startswith(old):
            return new + path[len(old):]
        dotted = '.' + old
        if dotted in path:
            path = path.replace(dotted, '.' + new, 1)
    return path


class Num(float):
    """A float that remembers the unit suffix it was written with."""

    unit: str

    def __new__(cls, value: float, unit: str = ''):
        obj = super().__new__(cls, value)
        obj.unit = unit
        return obj

    def __repr__(self) -> str:
        return fmt(self)


def fmt(v) -> str:
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, float):
        unit = getattr(v, 'unit', '')
        s = f'{v:.6g}' if not v.is_integer() else str(int(v))
        return s + unit
    if isinstance(v, int):
        return str(v)
    if isinstance(v, tuple):
        return '[' + ', '.join(fmt(x) for x in v) + ']'
    return str(v)


def norm_scalar(v):
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, (int, float)):
        return Num(float(v))
    if isinstance(v, str):
        m = _NUM_RE.match(v)
        if m:
            return Num(float(m.group(1)), m.group(2) or '')
        return v
    return v


# Second field that disambiguates duplicates of an ID field: a tier can upgrade
# the same property twice — once the base value (default) and once its spirit
# scaling (m_eUpgradeType = EAddToScale / EMultiplyScale).
SUB_ID_FIELDS = ('m_eUpgradeType', 'm_eScaleStatFilter')


def _list_key(items: list):
    """Return a function item -> key string, or None to fall back to indexes."""
    if not items or not all(isinstance(x, dict) for x in items):
        return None
    for key in ID_FIELDS:
        vals = [x.get(key) for x in items]
        if not all(isinstance(v, str) and v for v in vals):
            continue
        if len(set(vals)) == len(vals):
            return lambda x, k=key: x[k]

        def composite(x, k=key):
            extra = [str(x[s]) for s in SUB_ID_FIELDS if x.get(s)]
            return '|'.join([x[k]] + extra)
        comp = [composite(x) for x in items]
        if len(set(comp)) == len(comp):
            return composite
    return None


def flatten(obj, prefix: str = '', out: dict | None = None) -> dict:
    """Flatten + canonicalise paths + drop excluded noise."""
    raw = _flatten(obj, prefix, {})
    result = out if out is not None else {}
    for path, value in raw.items():
        if EXCLUDE_RE.search(path):
            continue
        result[canonical(path)] = value
    return result


def _flatten(obj, prefix: str, out: dict) -> dict:
    if isinstance(obj, dict):
        if not obj and prefix:
            out[prefix] = '{}'
        for k, v in obj.items():
            _flatten(v, f'{prefix}.{k}' if prefix else str(k), out)
    elif isinstance(obj, list):
        if all(not isinstance(x, (dict, list)) for x in obj):
            out[prefix] = tuple(sorted((norm_scalar(x) for x in obj), key=lambda x: (str(type(x)), str(x))))
        else:
            keyfn = _list_key(obj)
            for i, item in enumerate(obj):
                if keyfn:
                    _flatten(item, f'{prefix}{{{keyfn(item)}}}', out)
                else:
                    _flatten(item, f'{prefix}[{i}]', out)
    else:
        out[prefix] = norm_scalar(obj)
    return out
