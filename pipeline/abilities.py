"""Current ability / item cards for entity pages (data/abilities.json).

For every hero ability, weapon and shop item of the newest build:
  - the properties the in-game tooltip shows (m_AbilityTooltipDetails: important
    ones first, then basic), with the game's own labels, prefixes and units;
  - spirit scaling of each property;
  - header values (cooldown, cast range, charges, duration, cast time);
  - T1/T2/T3 upgrades: the game's tier text with {s:Prop} filled in from the
    tier bonuses, plus the raw bonus list;
  - the description text with values filled in.

    python -m pipeline.abilities
"""
from __future__ import annotations

import json
import re

from . import cache, loc, tracker
from .classify import ability_kind, hero_bound_abilities
from .semantics import humanize

OUT = tracker.ROOT / 'data' / 'abilities.json'
HEADER_PROPS = (
    ('AbilityCooldown', 'Cooldown'),
    ('AbilityCastRange', 'Range'),
    ('AbilityDuration', 'Duration'),
    ('AbilityCharges', 'Charges'),
    ('AbilityCooldownBetweenCharge', 'Charge delay'),
    ('AbilityCastDelay', 'Cast time'),
    ('AbilityChannelTime', 'Channel'),
)
EMPTY = {'', '0', '0.0', '-1', '-1.0', '-2', 'None'}
# m_strCSSClass picks the property's icon in the in-game tooltip (icons/stats/prop/<class>);
# a few spellings differ from the icon names
CSS_ALIASES = {'movement_speed': 'move_speed', 'fireRate': 'fire_rate', 'ETechPower': 'tech_power',
               'time': 'duration'}


def css_class(d: dict) -> str | None:
    css = str(d.get('m_strCSSClass') or '').strip()
    return CSS_ALIASES.get(css, css) or None

_SUB_RE = re.compile(r'\{s:([A-Za-z0-9_]+)\}')
_G_RE = re.compile(r"\{g:([^}:]*):'([^']*)'\}|\{g:([^}:]*):([^}:]*)\}")
INLINE_ATTRIBUTE = 'citadel_inline_attribute'
KEY_BINDING = 'citadel_binding'
_SPACES_RE = re.compile(r'[ \t]{2,}')
_TAG_RE = re.compile(r'<br\s*/?>', re.I)
_HTML_RE = re.compile(r'<[^>]+>')


def _num_s(v) -> str:
    s = str(v).strip()
    m = re.match(r'^(-?\d*\.?\d+)(m|s|%)?$', s)
    if not m:
        return s
    x = float(m.group(1))
    t = str(int(x)) if x.is_integer() else f'{x:.3f}'.rstrip('0').rstrip('.')
    return t + (m.group(2) or '')


def _label(tok, prop, aid):
    for key in (f'{aid}_{prop}_label', f'{prop}_label'):
        v = tok.get(key.lower())
        if v and '{' not in v:
            return _HTML_RE.sub('', v).strip()
    return humanize(prop)


def _affix(tok, prop, which):
    return tok.get(f'{prop}_{which}'.lower(), '')


def fmt_prop(tok, prop, value, aid, bonus=False) -> str:
    """'-28%' / '20m' / '+80' the way the tooltip writes it."""
    v = _num_s(value)
    pre, post = _affix(tok, prop, 'prefix'), _affix(tok, prop, 'postfix')
    if '{s:sign}' in pre:                  # the game prints the value's own sign
        pre = pre.replace('{s:sign}', '' if v.startswith('-') else '+')
    if v.endswith('m') and post == 'm':
        post = ''
    if bonus and not v.startswith('-') and not pre:
        pre = '+'
    if pre == '-' and v.startswith('-'):
        pre = ''
    return f'{pre}{v}{post}'


def fill(text: str | None, values: dict[str, str], tok: dict[str, str] | None = None) -> str:
    """Tooltip text with {s:Prop} filled and markup removed. {g:citadel_inline_attribute:'X'}
    is what the game prints for InlineAttribute_X ('SpiritDPS' -> 'spirit damage over time')."""
    if not text:
        return ''

    def value(m: re.Match) -> str:
        v = values.get(m.group(1), m.group(1))
        # "+{s:Radius}m" with a value that already ends in m: the unit once ("+2m", not "+2mm")
        nxt = m.string[m.end():m.end() + 1]
        return v[:-1] if nxt and not nxt.isdigit() and v.endswith(nxt) else v

    def glossary(m: re.Match) -> str:
        kind, name = (m.group(1), m.group(2)) if m.group(2) is not None else (m.group(3), m.group(4))
        if kind == KEY_BINDING:          # the game draws the key: "Hold [Move Forward] while…"
            return f' [{humanize(name)}] '
        if tok is not None and kind == INLINE_ATTRIBUTE:
            words = tok.get(f'inlineattribute_{name}'.lower())
            return words if words is not None else humanize(name).lower()
        return name or ''
    t = _SUB_RE.sub(value, text)
    t = _SPACES_RE.sub(' ', _G_RE.sub(glossary, t))
    t = _TAG_RE.sub('\n', t)
    t = _HTML_RE.sub('', t)
    return '\n'.join(ln.strip() for ln in t.splitlines() if ln.strip())


def card(aid: str, a: dict, tok: dict[str, str], kind: str, owner: str | None) -> dict:
    props = a.get('m_mapAbilityProperties') or {}
    base_vals = {}
    for p, d in props.items():
        if isinstance(d, dict) and d.get('m_strValue') is not None:
            base_vals[p] = _num_s(d['m_strValue']).rstrip('ms%') if not str(d['m_strValue']).endswith('m') else _num_s(d['m_strValue'])
    important, basic = [], []
    for sec in ((a.get('m_AbilityTooltipDetails') or {}).get('m_vecAbilityInfoSections') or []):
        for blk in sec.get('m_vecAbilityPropertiesBlock') or []:
            for p in blk.get('m_vecAbilityProperties') or []:
                name = p.get('m_strImportantProperty')
                if name and name not in important:
                    important.append(name)
        for name in sec.get('m_vecBasicProperties') or []:
            if name not in basic and name not in important:
                basic.append(name)

    def row(p):
        d = props.get(p)
        if not isinstance(d, dict) or str(d.get('m_strValue', '')).strip() in EMPTY:
            return None
        scale = (d.get('m_subclassScaleFunction') or {}).get('m_flStatScale')
        return {'prop': p, 'label': _label(tok, p, aid), 'value': fmt_prop(tok, p, d['m_strValue'], aid),
                'scale': float(scale) if isinstance(scale, (int, float)) and scale else None,
                'css': css_class(d)}

    header = []
    for p, lbl in HEADER_PROPS:
        d = props.get(p)
        if isinstance(d, dict) and str(d.get('m_strValue', '')).strip() not in EMPTY:
            header.append({'prop': p, 'label': lbl, 'value': fmt_prop(tok, p, d['m_strValue'], aid),
                           'css': css_class(d)})
    header_props = {h['prop'] for h in header}
    tiers = []
    for i, t in enumerate(a.get('m_vecAbilityUpgrades') or [], start=1):
        ups = t.get('m_vecPropertyUpgrades') or []
        vals = dict(base_vals)
        bonuses = []
        for u in ups:
            p, b = u.get('m_strPropertyName'), u.get('m_strBonus')
            if not p or b is None:
                continue
            scale = u.get('m_eUpgradeType') in ('EAddToScale', 'EMultiplyScale')
            vals.setdefault(p, _num_s(b))
            if not scale:
                vals[p] = _num_s(b).lstrip('-') if _affix(tok, p, 'prefix') == '-' else _num_s(b)
            bonuses.append({'label': _label(tok, p, aid) + (' (spirit scaling)' if scale else ''),
                            'value': fmt_prop(tok, p, b, aid, bonus=True)})
        text = fill(tok.get(f'{aid}_t{i}_desc'.lower()), vals, tok)
        tiers.append({'tier': i, 'text': text, 'bonuses': bonuses})
    sections = []
    for sec in a.get('m_vecTooltipSectionInfo') or []:      # items: Innate / Passive / Active blocks
        kind_s = str(sec.get('m_eAbilitySectionType', '')).replace('EArea_', '')
        for attr in sec.get('m_vecSectionAttributes') or []:
            imp = [p.get('m_strImportantProperty') for p in attr.get('m_vecImportantAbilityProperties') or []]
            rows = [row(p) for p in list(attr.get('m_vecElevatedAbilityProperties') or []) + imp
                    + list(attr.get('m_vecAbilityProperties') or []) if p]
            key = str(attr.get('m_strLocString') or '').lstrip('#').lower()
            sections.append({'type': kind_s, 'desc': fill(tok.get(key), base_vals, tok) if key else '',
                             'props': [r for r in rows if r]})
    base = loc.loc_base(tok, aid, owner)
    return {
        'id': aid, 'kind': kind, 'owner': owner,
        'name': loc.plain(loc.entity_name(tok, aid, owner)),
        'quip': loc.plain(tok.get(f'{base}_quip')),
        'desc': fill(tok.get(f'{base}_desc'), base_vals, tok),
        'header': header,
        'important': [r for r in (row(p) for p in important) if r and r['prop'] not in header_props],
        'basic': [r for r in (row(p) for p in basic) if r and r['prop'] not in header_props],
        'sections': sections,
        # items carry one upgrade entry whose meaning is not verified: not shown
        'tiers': tiers if kind != 'item' else [],
        'item': {
            'tier': str(a.get('m_iItemTier') or '').replace('EModTier_', ''),
            'slot': str(a.get('m_eItemSlotType') or '').replace('EItemSlotType_', ''),
            'activation': 'Passive' if 'PASSIVE' in str(a.get('m_eAbilityActivation', '')) else 'Active',
            'components': list(a.get('m_vecComponentItems') or []),
            'disabled': str(a.get('m_bDisabled')).lower() in ('true', '1'),
        } if kind == 'item' else None,
    }


def build() -> dict:
    head = tracker.builds()[-1]
    tok = loc.tokens(head.commit)
    heroes = cache.vdata(head.commit, tracker.SCRIPTS + 'heroes.vdata')
    abilities = cache.vdata(head.commit, tracker.SCRIPTS + 'abilities.vdata')
    generic = cache.vdata(head.commit, tracker.SCRIPTS + 'generic_data.vdata')
    prices = generic.get('m_nItemPricePerTier') or []
    owners = hero_bound_abilities(heroes)
    slots = {}
    for hid, h in heroes.items():
        for slot, aid in (h.get('m_mapBoundAbilities') or {}).items() if isinstance(h, dict) else []:
            slots.setdefault(aid, slot)
    out = {}
    for aid, a in abilities.items():
        if not isinstance(a, dict) or a.get('_not_pickable'):
            continue
        kind = ability_kind(aid, a, owners)
        if kind not in ('ability', 'weapon', 'item'):
            continue
        c = card(aid, a, tok, kind, owners.get(aid))
        c['slot'] = slots.get(aid, '').replace('ESlot_', '')
        if c['item'] and c['item']['tier'].isdigit() and int(c['item']['tier']) < len(prices):
            c['item']['cost'] = prices[int(c['item']['tier'])]
        out[aid] = c
    OUT.write_text(json.dumps({'build': head.build, 'abilities': out}, ensure_ascii=False, separators=(',', ':')),
                   encoding='utf-8', newline='\n')
    print(f'{len(out)} ability/item cards -> {OUT}')
    return out


if __name__ == '__main__':
    build()
