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

import html
import json
import re

from . import cache, labels, loc, tracker
from .classify import ability_kind, hero_bound_abilities, shared_abilities
from .flatten import _id_case, _list_key
from .semantics import SCALE_STAT_WORDS, describe, humanize, scale_stat, scaling_suffix

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


SPEED_DISPLAY = ('EMaxMoveSpeed', 'ESprintSpeed')


def is_speed(d: dict) -> bool:
    """A movement speed the game writes as metres ("2m" Sprint Speed is +2 m/s): it says so in its
    display units, its display type, or the hero stat it gives (Item Stats' Sprint Speed column said
    m/s while its chips said "+2m", 2026-10-04). A percent of a speed keeps its "%"."""
    t = str(d.get('m_eProvidedPropertyType') or '')
    return (d.get('m_eDisplayUnits') == 'EDisplayUnit_MetersPerSecond' or d.get('m_eDisplayType') in SPEED_DISPLAY
            or ('SPEED' in t and 'PERCENT' not in t))

_SUB_RE = re.compile(r'\{s:([A-Za-z0-9_]+)\}')
_G_RE = re.compile(r"\{g:([^}:]*):'([^']*)'\}|\{g:([^}:]*):([^}:]*)\}")
INLINE_ATTRIBUTE = 'citadel_inline_attribute'
KEY_BINDING = 'citadel_binding'
_SPACES_RE = re.compile(r'[ \t]{2,}')
_TAG_RE = re.compile(r'<br\s*/?>', re.I)
_HTML_RE = re.compile(r'<[^>]+>')
_UNIT_AFTER = re.compile(r' ?(m/s|m|s|%|meters?|seconds?)(?![a-z])')


def _empty(v) -> bool:
    """A value the tooltip leaves out: none, 0 (also "0m", "0s", "0%": Smoke Bomb showed
    "Invis Sprint Speed +0m"), or the engine's -1 / -2 placeholders."""
    return str(v).strip() in EMPTY or _num_s(v).rstrip('ms%') == '0'


def _num_s(v) -> str:
    s = str(v).strip()
    m = re.match(r'^(-?\d*\.?\d+)(m|s|%)?$', s)
    if not m:
        return s
    x = float(m.group(1))
    t = str(int(x)) if x.is_integer() else f'{x:.3f}'.rstrip('0').rstrip('.')
    return t + (m.group(2) or '')


def _tokens(vals: dict[str, str], alias: dict[str, str]) -> dict[str, str]:
    """Values under the names the tooltip text uses: a property's m_strLocTokenOverride as well as
    its own name ({s:BuffDuration} in Bounce Pad's T2 is SpeedOnLandDuration; without this the
    card printed "for BuffDurations" in 40-odd upgrade lines)."""
    return {**vals, **{o: vals[p] for p, o in alias.items() if p in vals and o not in vals}}


def _label(tok, prop, aid, kind: str = '', alias: str | None = None, path: str | None = None,
           fmap: dict | None = None) -> dict:
    """{label, unit, sign, src} of a card property — the resolver the history rows use
    (`pipeline.labels`): the card and the newest history row of a field say the same (26 items read
    "Incoming Healing" on the card and "Healing Reduction" in the history, audit 2026-10-04).
    `path`: a tier bonus's own path; its "T1: " goes, the card shows it under its tier."""
    path = path or f'm_mapAbilityProperties.{prop}.m_strValue'
    d = describe(path, tok, aid, kind, None, alias)
    cn = labels.canonical(labels.field_key('abilities.vdata', aid, path), d, fmap if fmap is not None else {})
    return {**cn, 'label': re.sub(r'^(?:T\d|Enhanced|Upgrade): ', '', cn['label'])}


def _tier_paths(i: int, ups: list) -> dict[int, str]:
    """{index in the tier: the path the build records keep its bonus under} (flatten's list keys)."""
    items = [_id_case(u) for u in ups]
    keyfn = _list_key(items)
    return {j: f'm_vecAbilityUpgrades[{i - 1}].m_vecPropertyUpgrades'
               + (f'{{{keyfn(u)}}}' if keyfn else f'[{j}]') + '.m_strBonus'
            for j, u in enumerate(items)}


def _affix(tok, prop, which):
    return tok.get(f'{prop}_{which}'.lower(), '')


def fmt_prop(tok, prop, value, aid, bonus=False, magnitude=False) -> str:
    """'-28%' / '20m' / '+80' the way the tooltip writes it. `magnitude`: the tooltip's own minus goes
    (prop_sign '-': the label already says "Movement Slow")."""
    v = _num_s(value)
    pre, post = _affix(tok, prop, 'prefix'), _affix(tok, prop, 'postfix')
    if magnitude and pre.strip() == '-':
        pre, v = '', v.lstrip('-')
    if '{s:sign}' in pre:                  # the game prints the value's own sign
        pre = pre.replace('{s:sign}', '' if v.startswith('-') else '+')
    # the value already carries the unit the postfix adds ("3m" + " m" printed "+3m m" on 47 rows)
    unit = post.strip()
    if unit and v.endswith(unit):
        post = ''
    elif unit and v[-1:].isalpha() and unit.startswith(v[-1]):      # "4m" + " m/s" -> "4m/s"
        v, post = v[:-1], unit
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
        if nxt and not nxt.isdigit() and v.endswith(nxt):
            return v[:-1]
        # "{s:BonusMoveSpeed} m/s" with "1.2m": the text's unit wins ("1.2m m/s" in a T1, 2026-10-02)
        unit = _UNIT_AFTER.match(m.string, m.end())
        if unit and v[-1:].isalpha() and unit.group(1).startswith(v[-1]):
            return v[:-1]
        return v

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
    # the text's entities as characters: the page escapes once ("Bullet, Spirit &amp;amp; Melee")
    t = html.unescape(_HTML_RE.sub('', t))
    return '\n'.join(ln.strip() for ln in t.splitlines() if ln.strip())


def card(aid: str, a: dict, tok: dict[str, str], kind: str, owner: str | None, fmap: dict | None = None) -> dict:
    """`fmap`: pipeline.labels' map (the field's label over its whole history); without it the
    newest build's text alone names the properties."""
    props = a.get('m_mapAbilityProperties') or {}
    alias = {p: str(d['m_strLocTokenOverride']) for p, d in props.items()
             if isinstance(d, dict) and d.get('m_strLocTokenOverride')}
    base_vals = {}
    for p, d in props.items():
        if isinstance(d, dict) and d.get('m_strValue') is not None:
            base_vals[p] = _num_s(d['m_strValue']).rstrip('ms%') if not str(d['m_strValue']).endswith('m') else _num_s(d['m_strValue'])
    base_vals = _tokens(base_vals, alias)
    # "{s:hero_name} is slowed" — the game prints the owner's name
    base_vals['hero_name'] = loc.plain(loc.hero_name(tok, owner)) if owner else 'the hero'
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
        if not isinstance(d, dict) or _empty(d.get('m_strValue', '')):
            return None
        scale = (d.get('m_subclassScaleFunction') or {}).get('m_flStatScale')
        stat = scale_stat(a, p)
        name = _label(tok, p, aid, kind, alias.get(p), fmap=fmap)
        value = fmt_prop(tok, p, d['m_strValue'], aid, magnitude=name['sign'] == '-')
        if is_speed(d) and value.endswith('m'):
            value += '/s'                     # a speed: "Sleep Movespeed 1.5m/s", not "1.5m"
        return {'prop': p, 'label': name['label'], 'value': value,
                'scale': float(scale) if isinstance(scale, (int, float)) and scale else None,
                # what the coefficient multiplies: "+4×Boon" on Headhunter, not "×Spirit" (34 rows)
                'scale_by': SCALE_STAT_WORDS[stat].title() if stat in SCALE_STAT_WORDS else None,
                'css': css_class(d)}

    header = []
    for p, lbl in HEADER_PROPS:
        d = props.get(p)
        if isinstance(d, dict) and not _empty(d.get('m_strValue', '')):
            header.append({'prop': p, 'label': lbl, 'value': fmt_prop(tok, p, d['m_strValue'], aid),
                           'css': css_class(d)})
    header_props = {h['prop'] for h in header}
    tiers = []
    for i, t in enumerate(a.get('m_vecAbilityUpgrades') or [], start=1):
        ups = t.get('m_vecPropertyUpgrades') or []
        vals = dict(base_vals)
        bonuses = []
        paths = _tier_paths(i, ups)
        for j, u in enumerate(ups):
            u = _id_case(u)
            p, b = u.get('m_strPropertyName'), u.get('m_strBonus')
            if not p or b is None or _num_s(b).rstrip('ms%') in ('0', '-0'):
                continue                       # a zero bonus ("Cooldown +0s" on 103 rows) is no bonus
            scale = u.get('m_eUpgradeType') in ('EAddToScale', 'EMultiplyScale')
            vals.setdefault(p, _num_s(b))
            if scale:                          # "{s:MaxBonusBulletDamage_scale}%": the tier's scaling bonus
                vals[f'{p}_scale'] = _num_s(b)
            else:
                vals[p] = _num_s(b).lstrip('-') if _affix(tok, p, 'prefix') == '-' else _num_s(b)
            # the tier's own path: its label carries "(spirit scaling)", "(% of base)" like the history row;
            # a bonus keyed by its property alone hides its scaling there, the card adds it
            name = _label(tok, p, aid, kind, alias.get(p), paths[j], fmap)
            suffix = scaling_suffix([u.get('m_eUpgradeType'), u.get('m_eScaleStatFilter')]) if scale else ''
            bonuses.append({'label': name['label'] + (suffix if suffix and 'scaling' not in name['label'] else ''),
                            'value': fmt_prop(tok, p, b, aid, bonus=True, magnitude=name['sign'] == '-')})
        vals.update({o: vals[p] for p, o in alias.items() if p in vals and o not in props})
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
            # a property listed twice in one block (elevated and plain: Decay's "Cast Range 20m" twice)
            # once — the first, the important one
            seen_props: set[str] = set()
            props_ = [r for r in rows if r and not (r['prop'] in seen_props or seen_props.add(r['prop']))]
            sections.append({'type': kind_s, 'desc': fill(tok.get(key), base_vals, tok) if key else '',
                             'props': props_})
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
            # T5 items exist only in Street Brawl's draft (ERequirementStreetBrawl), not in the shop
            'street_brawl': 'StreetBrawl' in str(a.get('m_eAbilityRequirements') or ''),
            # the shop's IMBUE label: the item is applied onto one of your abilities
            'imbue': 'IMBUE' in json.dumps(a.get('m_TargetAbilityEffectsToApply') or ''),
        } if kind == 'item' else None,
    }


def corrupted_penalties(generic: dict, tok: dict[str, str]) -> dict[str, str]:
    """The game's name of each Corrupted penalty (generic_data m_vecCorruptedPenaltyDefs: m_strName -> its first
    shown effect's m_strLocTokenOverride -> that token's label): an item's "Excluded Penalties TechDuration" is
    "Ability Duration" (review 2026-10-05: engine names on 38 Corrupted rows)."""
    out = {}
    for d in generic.get('m_vecCorruptedPenaltyDefs') or []:
        if not isinstance(d, dict) or not d.get('m_strName'):
            continue
        shown = [e for e in d.get('m_vecEffects') or [] if isinstance(e, dict)
                 and str(e.get('m_bDisplay', True)).lower() not in ('false', '0')]
        token = (shown[0].get('m_strLocTokenOverride') if shown else '') or ''
        label = tok.get(f'{token}_label'.lower()) if token else None
        out[d['m_strName']] = loc.plain(label) if label else humanize(d['m_strName'])
    return out


def last_cards(have: set[str], fmap: dict) -> dict[str, dict]:
    """A removed item's card as it was in the last build that had it, marked `last` = [build, date] (review
    2026-10-05: Ablative Coat's page had only its history, no values). Each such build's files are read once."""
    from . import catalog
    try:
        ents = catalog.load()
    except FileNotFoundError:
        return {}
    gone = [e for e in ents.values() if e['file'] == 'abilities.vdata' and e.get('kind') == 'item'
            and not e.get('alive') and e['id'] not in have and e.get('last')]
    commits = {b.build: b for b in tracker.builds() if b.build is not None}
    out: dict[str, dict] = {}
    by_build: dict[int, list[dict]] = {}
    for e in gone:
        by_build.setdefault(e['last'][0], []).append(e)
    for build, group in by_build.items():
        b = commits.get(build)
        if b is None:
            continue
        abilities = cache.vdata(b.commit, tracker.SCRIPTS + 'abilities.vdata')
        tok = loc.tokens(b.commit)
        generic = cache.vdata(b.commit, tracker.SCRIPTS + 'generic_data.vdata')
        prices = generic.get('m_nItemPricePerTier') or []
        for e in group:
            a = abilities.get(e['id'])
            if not isinstance(a, dict):
                continue
            c = card(e['id'], a, tok, 'item', None, fmap)
            if c['item'] and c['item']['tier'].isdigit() and int(c['item']['tier']) < len(prices):
                c['item']['cost'] = prices[int(c['item']['tier'])]
            c['last'] = [build, b.date[:10]]
            out[e['id']] = c
    return out


def build() -> dict:
    head = tracker.head_build()
    tok = loc.tokens(head.commit)
    heroes = cache.vdata(head.commit, tracker.SCRIPTS + 'heroes.vdata')
    abilities = cache.vdata(head.commit, tracker.SCRIPTS + 'abilities.vdata')
    generic = cache.vdata(head.commit, tracker.SCRIPTS + 'generic_data.vdata')
    prices = generic.get('m_nItemPricePerTier') or []
    owners = hero_bound_abilities(heroes, abilities)
    shared = shared_abilities(heroes)
    fmap = labels.field_map()
    slots = {}
    for hid, h in heroes.items():
        for slot, aid in (h.get('m_mapBoundAbilities') or {}).items() if isinstance(h, dict) else []:
            slots.setdefault(aid, slot)
    out = {}
    for aid, a in abilities.items():
        if not isinstance(a, dict) or a.get('_not_pickable'):
            continue
        kind = ability_kind(aid, a, owners, shared)
        # 'shared': every hero's jump / dash / parry… — a card without an owner
        if kind not in ('ability', 'weapon', 'item', 'shared'):
            continue
        c = card(aid, a, tok, kind, owners.get(aid), fmap)
        c['slot'] = slots.get(aid, '').replace('ESlot_', '')
        if c['item'] and c['item']['tier'].isdigit() and int(c['item']['tier']) < len(prices):
            c['item']['cost'] = prices[int(c['item']['tier'])]
        out[aid] = c
    out.update(last_cards(set(out), fmap))
    OUT.write_text(json.dumps({'build': head.build, 'abilities': out,
                               'penalties': corrupted_penalties(generic, tok)},
                              ensure_ascii=False, separators=(',', ':')),
                   encoding='utf-8', newline='\n')
    print(f'{len(out)} ability/item cards -> {OUT}')
    return out


if __name__ == '__main__':
    build()
