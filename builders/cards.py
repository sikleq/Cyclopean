"""Entity cards: the one component every change list uses (patch notes, all changes,
build pages, hero / item / unit history). A card = framed 48px icon, name, subtitle,
tag counters and the strip of history squares; inside it optional ability sub-headers
and rows on a fixed grid: status | tag | text | old -> new."""
from __future__ import annotations

import re

from .common import esc, mark, visual
from .pixel_icons import tag_svg
from .render import HIDDEN_LIKE, fold_tier_swaps, sort_changes, tag_html, tag_summary, vals_html

# documented is the normal case: no mark (a quiet row); every other status is an exception
ROW_MARKS = ('rounded', 'described', 'mismatch', 'fix', 'untracked', 'nodata', 'repeated',
             'hidden', 'unreleased', 'unannounced')


def is_hidden(changes: list[dict]) -> bool:
    return any(c.get('status', 'hidden') in HIDDEN_LIKE for c in changes)


def card_head(name: str, icon_url: str | None, glyph: str, counted: list[dict], sub: str = '', trail: str = '',
              href: str = '') -> str:
    nm = f'<a href="{esc(href)}">{esc(name)}</a>' if href else esc(name)
    sub_html = f'<div class="sub">{esc(sub)}</div>' if sub else ''
    counted = player_facing(counted)
    counters = tag_summary(counted) if counted else ''
    return (f'<header class="ecard-h"><span class="ei">{visual(icon_url, glyph)}</span>'
            f'<div class="en"><div class="nm">{nm}</div>{sub_html}</div>'
            f'<div class="er">{counters}{trail}</div></header>')


def card(head: str, body: str, *, hidden: bool = False, dev: bool = False, search: str = '', anchor: str = '',
         extra: str = '') -> str:
    cls = 'ecard' + (' has-hidden' if hidden else '') + (' dev' if dev else '') + (f' {extra}' if extra else '')
    ds = f' data-search="{esc(search)}"' if search else ''
    aid = f' id="{esc(anchor)}"' if anchor else ''
    return f'<article class="{cls}"{aid}{ds}>{head}<div class="eb">{body}</div></article>'


def sub_head(name: str, icon_url: str | None, glyph: str, counted: list[dict], hidden: bool = False) -> str:
    """An ability inside its hero's card."""
    counted = player_facing(counted)
    counters = tag_summary(counted) if counted else ''
    cls = 'esub' + (' has-hidden' if hidden else '')
    return f'<div class="{cls}">{visual(icon_url, glyph, "px si2")}<span class="nm">{esc(name)}</span>{counters}</div>'


def row(status: str, tag: str, text_html: str, values_html: str = '', extra: str = '') -> str:
    m = mark(status) if status in ROW_MARKS else ''
    hid = ' is-hidden' if status in HIDDEN_LIKE else ''
    return (f'<div class="erow st-{esc(status)}{hid}{(" " + extra) if extra else ""}"><span class="st">{m}</span>'
            f'<span class="tg">{tag}</span><span class="tx">{text_html}</span><span class="vv">{values_html}</span></div>')


# engine plumbing that reached a gameplay category: '{}' blocks, ENUM_CONSTANTS, ETypeNames
_ENGINE_VALUE = re.compile(r'^\{\}$|^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$|^E[A-Z][a-zA-Z]+(?:_[A-Za-z]+)*$')
_ENGINE_LABEL = re.compile(r'\b(scaling stats|roster|layout|background|css|panel|particle)\b', re.I)


def merge_renames(changes: list[dict]) -> list[dict]:
    """A field re-keyed between builds arrives as DEL + NEW with the same label ('Hit Speed
    80' removed, 'Hit Speed 78.74' added): one CHANGED row 80 -> 78.74."""
    adds = {}
    for c in changes:
        if c.get('op') == 'add':
            adds.setdefault(_rename_key(c.get('label')), []).append(c)
    out, used = [], set()
    for c in changes:
        if c.get('op') == 'remove' and adds.get(_rename_key(c.get('label'))):
            a = adds[_rename_key(c['label'])].pop(0)
            used.add(id(a))
            x, y = _num(c.get('old_s', c.get('old'))), _num(a.get('new_s', a.get('new')))
            if x is not None and y is not None and (x == y or abs(x / UNITS_PER_METER - y) < 0.01):
                continue            # same value under a new key (or the same length now in metres)
            merged = {**a, 'op': 'change', 'old_s': c.get('old_s'), 'old': c.get('old'),
                      'status': min((a.get('status', 'hidden'), c.get('status', 'hidden')),
                                    key=lambda s: s not in HIDDEN_LIKE)}
            if x is not None and y is not None:
                # the NEW row carried dir='changed': judge the pair like any other change
                from pipeline.semantics import direction, gradient
                d, pct = direction(str(a.get('path', '')), x, y)
                merged.update(dir=d, pct=pct, grad=gradient(pct))
            out.append(merged)
            continue
        out.append(c)
    return [c for c in out if id(c) not in used]


def _rename_key(label) -> str:
    """'Pickup Radius' and 'Pickup Radius › Base' are one field moved into a sub-block."""
    return str(label or '').removesuffix(' › Base')


UNITS_PER_METER = 39.37
_NUM = re.compile(r'^\s*([-+]?\d*\.?\d+)\s*(m|s|%)?\s*$')


def _num(v) -> float | None:
    m = _NUM.match(str(v)) if v is not None else None
    return float(m.group(1)) if m else None


def is_engine(c: dict) -> bool:
    if c.get('cat') == 'availability':      # "Pre Release", "Disabled": never plumbing
        return False
    vals = [str(c.get(k) or '').strip() for k in ('old_s', 'new_s')]
    vals = [v for v in vals if v and v != '—']
    return bool(vals) and all(_ENGINE_VALUE.match(v) for v in vals) or bool(_ENGINE_LABEL.search(str(c.get('label'))))


GAMEPLAY = ('balance', 'mechanic', 'availability')


def merge_variants(ents: list[dict]) -> list[dict]:
    """One object kept under several ids (Walker: alt_npc_boss_tier2, npc_boss_tier2, their _weak
    copies; two crate ids) gets the same edit in each: one card 'Walker · 4 variants' (audit
    2026-10-01: a third of CHANGED rows were such repeats). Heroes and unnamed ids never merge."""
    groups: dict[tuple, list[dict]] = {}
    order: list[tuple] = []
    for e in ents:
        name = e.get('name')
        if e['file'] == 'heroes.vdata' or e.get('id') == '@shared' or not name or name == e.get('id'):
            key: tuple = ('solo', id(e))
        else:
            key = (e['file'], name, frozenset((c.get('path'), c.get('op'), str(c.get('old_s')), str(c.get('new_s')))
                                              for c in e['changes']))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(e)
    out = []
    for key in order:
        g = groups[key]
        out.append(g[0] if len(g) == 1 else {**g[0], 'variants': [x['id'] for x in g]})
    return out


def gameplay_entities(entities: list[dict]) -> list[dict]:
    """A patch's entities as players read them: gameplay rows only, repeated variants merged.
    Every page that lists or counts a patch's changes starts here (one rule, same numbers)."""
    out = []
    for e in entities:
        ch = [c for c in e['changes'] if c['cat'] in GAMEPLAY]
        if ch:
            out.append({**e, 'changes': ch})
    return merge_variants(out)


def player_facing(changes: list[dict]) -> list[dict]:
    """The rows a player reads, which is what EVERY counter counts (home summary, patches index,
    heroes index, card headers, history bands): renames merged, replaced tiers folded into one
    REWORK, engine plumbing out. Folding works per entity (a hero card mixes its abilities)."""
    groups: dict[str, list[dict]] = {}
    for c in changes:
        groups.setdefault(':'.join(str(c.get('key') or '').split(':', 2)[:2]), []).append(c)
    return [c for g in groups.values() for c in combine_levels(fold_tier_swaps(merge_renames(g)))
            if not is_engine(c) and not is_noop(c)]


_ZERO_RE = re.compile(r'^[+-]?0(?:\.0+)?\s*(?:m|s|%|m/s|x|u)?$')


def is_noop(c: dict) -> bool:
    """'1.5 → 1.5': the shown values are equal (a re-keyed or re-typed field), nothing to read.
    A field added or removed with a zero / "no" value changes nothing either: the patch window's
    final value decides (Sleep Dagger's "Explosion Radius 0" NEW in City Never Sleeps was a field
    tuned to 0 within the window)."""
    op = c.get('op')
    if op == 'change':
        return str(c.get('old_s')) == str(c.get('new_s'))
    if op in ('add', 'remove') and not str(c.get('path') or '').startswith('@'):
        v = str(c.get('new_s' if op == 'add' else 'old_s') or '').strip().lower()
        return bool(_ZERO_RE.match(v)) or v in ('no', 'false')
    return False


def change_row(c: dict) -> str:
    # a replaced tier lists both bonus sets: they go on their own full-width line under the
    # label (two lines at most, click to expand) instead of a tall right-aligned column
    extra = 'rw' if c.get('op') == 'rework' else ''
    return row(c.get('status', 'hidden'), tag_html(c), esc(c.get('label')), vals_html(c), extra)


# A table edited row by row (souls per level 19-36, investment steps, the shotgun's pellet offsets)
# reads as one change: one summary row, the rows behind a click (audit 2026-10-01: ~700 rows in patches)
FAMILY_MIN = 4
_NUM_IN_LABEL = re.compile(r'\d+')


def _family(label: str) -> str:
    return _NUM_IN_LABEL.sub('N', label)


def _span(nums: list[int]) -> str:
    lo, hi = min(nums), max(nums)
    return str(lo) if lo == hi else f'{lo}–{hi}'


_LEVEL_ROW = re.compile(r'^Level (\d+): (.+)$')
_LEVEL_WORDS = {'souls needed': '{} souls', 'gives a boon': 'boon', 'ability points': '{} ability point',
                'ability unlocks': 'unlocks an ability'}


def combine_levels(rows: list[dict]) -> list[dict]:
    """A whole level added or removed ('Level 35: souls needed / gives a boon / ability points',
    three NEW rows) is one row: 'Level 35 added · 47000 souls · boon · 1 ability point'."""
    by_level: dict[tuple, list[dict]] = {}
    for c in rows:
        m = _LEVEL_ROW.match(str(c.get('label', '')))
        if m and c.get('op') in ('add', 'remove'):
            by_level.setdefault((m.group(1), c['op']), []).append(c)
    whole = {k: g for k, g in by_level.items() if len(g) >= 2}
    if not whole:
        return rows
    out, done = [], set()
    for c in rows:
        m = _LEVEL_ROW.match(str(c.get('label', '')))
        key = (m.group(1), c.get('op')) if m else None
        if key not in whole:
            out.append(c)
            continue
        if key in done:
            continue
        done.add(key)
        parts = []
        for x in whole[key]:
            what = _LEVEL_ROW.match(x['label']).group(2)
            val = x.get('new_s') if key[1] == 'add' else x.get('old_s')
            if str(val).lower() in ('no', 'false', '0'):
                continue
            fmt = _LEVEL_WORDS.get(what)
            parts.append(fmt.format(val) if fmt else f'{what} {val}')
        side = 'new_s' if key[1] == 'add' else 'old_s'
        out.append({**whole[key][0], 'label': f'Level {key[0]} {"added" if key[1] == "add" else "removed"}',
                    side: ' · '.join(parts), 'path': f'level:{key[0]}'})
    return out


def family_rows(rows: list[dict]) -> str:
    rows = combine_levels(rows)
    fams: dict[str, list[dict]] = {}
    for c in rows:
        fams.setdefault(_family(str(c.get('label', ''))), []).append(c)
    html, done = [], set()
    for c in rows:
        fam = _family(str(c.get('label', '')))
        group = fams[fam]
        if len(group) < FAMILY_MIN:
            html.append(change_row(c))
            continue
        if fam in done:
            continue
        done.add(fam)
        html.append(_family_row(fam, group))
    return ''.join(html)


def _family_row(fam: str, group: list[dict]) -> str:
    """'Level 19–36: souls needed · 12 rows', tag of the group (mixed directions -> REWORK) and the
    range of % changes; the rows themselves fold under it."""
    from .render import tag_of
    first_nums = [int(m.group()) for c in group for m in [_NUM_IN_LABEL.search(str(c.get('label', '')))] if m]
    base = str(group[0].get('label', ''))
    label = _NUM_IN_LABEL.sub(_span(first_nums), base, count=1) if first_nums else base
    kinds = {tag_of(c)[0] for c in group}
    rep = group[0] if len(kinds) == 1 else {'op': 'rework', 'grad': 6}
    pcts = [c['pct'] for c in group if isinstance(c.get('pct'), (int, float))]
    span = ''
    if pcts:
        lo, hi = min(pcts), max(pcts)
        span = f'{lo:+.0f}%' if round(lo) == round(hi) else f'{lo:+.0f}% … {hi:+.0f}%'
    status = min((c.get('status', 'hidden') for c in group), key=lambda s: s not in HIDDEN_LIKE)
    inner = ''.join(change_row(c) for c in group)
    vals = f'<span class="vals fam-span">{esc(span)}</span>' if span else ''
    head = row(status, tag_html(rep), f'{esc(label)} <span class="fam-n">· {len(group)} rows</span>', vals, 'fam-head')
    hid = ' has-hidden' if is_hidden(group) else ''
    return f'<details class="fam{hid}"><summary>{head}</summary>{inner}</details>'


# A newly added entity arrives with every field it has (Baba in build 6711: 218 rows, most of them
# the level table and item-cost curves every hero shares). What a reader wants is what it IS: the
# stats a player compares and its own abilities; the rest folds under "All fields".
ADDED_KEY = re.compile(
    r'^m_mapStartingStats\.E(MaxHealth|BaseHealthRegen|MaxMoveSpeed|SprintSpeed|Stamina|LightMeleeDamage|'
    r'HeavyMeleeDamage|BulletArmorDamageReduction|TechArmorDamageReduction)$'
    r'|^m_mapBoundAbilities\.ESlot_(Signature_\d|Weapon_Primary)$'
    r'|^m_eHeroDevelopmentState$'
    r'|^m_mapAbilityProperties\.[^.]+\.m_strValue$'
    r'|^m_(nMaxHealth|iMaxHealth|flMaxHealth|nCost|iItemTier|eItemSlotType)$')
ADDED_KEY_LIMIT = 12


def _added_split(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    key = [c for c in rows if ADDED_KEY.search(str(c.get('path') or '')) and str(c.get('new_s', '')) not in ('0', '')]
    keep = key[:ADDED_KEY_LIMIT]
    kept = {id(c) for c in keep}
    return keep, [c for c in rows if id(c) not in kept]


def change_rows(changes: list[dict], added: bool = False) -> str:
    rows = sort_changes(fold_tier_swaps(merge_renames(changes)))
    if added:
        keep, rest = _added_split(rows)
        head = row('hidden' if is_hidden(rows) else rows[0].get('status', 'hidden') if rows else 'hidden',
                   '<span class="tag new" data-g="8">' + tag_svg('new') + 'NEW</span>',
                   f'Added to the game files · {len(rows)} fields')
        html = head + ''.join(change_row(c) for c in keep)
        if rest:
            inner = ''.join(change_row(c) for c in rest)
            html += f'<details class="tech"><summary>All fields ({len(rest)})</summary>{inner}</details>'
        return html
    rows = [c for c in rows if not is_noop(c)]
    main = [c for c in rows if not is_engine(c)]
    tech = [c for c in rows if is_engine(c)]
    html = family_rows(main)
    if tech:
        inner = ''.join(change_row(c) for c in tech)
        hid = ' has-hidden' if is_hidden(tech) else ''
        html += f'<details class="tech{hid}"><summary>Technical ({len(tech)})</summary>{inner}</details>'
    return html
