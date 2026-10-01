"""Rendering of change records shared by patch, build and entity pages."""
from __future__ import annotations

import re

from .common import esc, glyph_for, ids_to_names, mark, visual

# The tag set, chosen from what the data actually contains (all patches, 2026-10-01):
# NEW 20k, DEL 11k, NERF 5.2k, BUFF 4k, CHANGED 2.5k, MECH 0.9k, availability 92.
# The percentage is NOT in the badge: the value cell already shows it.
TAG_ORDER = {'new': 0, 'rework': 1, 'buff': 2, 'nerf': 3, 'del': 4, 'on': 5, 'off': 5, 'mech': 6, 'changed': 7}
KIND_LABEL = {
    'hero': 'Hero', 'ability': 'Ability', 'weapon': 'Weapon', 'melee': 'Melee', 'item': 'Item',
    'ability_other': 'Ability', 'trooper': 'Trooper', 'building': 'Building', 'neutral': 'Neutral',
    'unit': 'Unit', 'modifier': 'Modifier', 'global': 'Game rules',
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
            return 'changed', 'CHANGED'
        off = truthy if _OFF_WHEN_TRUE.search(str(c.get('label', '')) + str(c.get('path', ''))) else not truthy
        return ('off', 'OFF') if off else ('on', 'ON')
    if op == 'add':
        return 'new', 'NEW'
    if op == 'remove':
        return 'del', 'DEL'
    d = c.get('dir')
    if d in ('buff', 'nerf'):
        return d, d.upper()
    return ('mech', 'MECH') if cat == 'mechanic' else ('changed', 'CHANGED')


def tag_html(c: dict) -> str:
    cls, txt = tag_of(c)
    g = c.get('grad', 5)
    return f'<span class="tag {cls}" data-g="{g}">{esc(txt)}</span>'


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


TAG_GLYPH = {'buff': '▲', 'nerf': '▼', 'new': '✦', 'del': '✕', 'rework': '⟳', 'mech': '◆', 'changed': '●',
             'on': '●', 'off': '○'}


def tag_summary(changes: list[dict]) -> str:
    """Counters for an entity header in the index's glyph grammar: '▲3 ▼1 ✦2' (no zeros)."""
    counts: dict[str, int] = {}
    for c in changes:
        cls = tag_of(c)[0]
        counts[cls] = counts.get(cls, 0) + 1
    return '<span class="tsum">' + ''.join(
        f'<span class="pip {cls}">{TAG_GLYPH.get(cls, "●")}{n}</span>'
        for cls, n in sorted(counts.items(), key=lambda kv: TAG_ORDER.get(kv[0], 9))) + '</span>'


def top_pips(changes: list[dict], k: int) -> str:
    """The k biggest counters only (a 50-110px tile fits two), in the usual tag order."""
    counts: dict[str, int] = {}
    for c in changes:
        cls = tag_of(c)[0]
        counts[cls] = counts.get(cls, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], TAG_ORDER.get(kv[0], 9)))[:k]
    return '<span class="tsum">' + ''.join(
        f'<span class="pip {cls}">{TAG_GLYPH.get(cls, "●")}{n}</span>'
        for cls, n in sorted(ranked, key=lambda kv: TAG_ORDER.get(kv[0], 9))) + '</span>'


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
    rows = sort_changes(fold_tier_swaps(changes))
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


_FLAG_PREFIX = re.compile(r'^(CITADEL_ABILITY_BEHAVIOR_|MODIFIER_STATE_|MODIFIER_VALUE_|EAbility|E[A-Z][a-z]+_|DOTA_)')
LONG_VALUE = 60


def _flags(s) -> list[str] | None:
    """'A | B' bit flags or 'a, b, c' id lists -> items; None for plain values."""
    if not isinstance(s, str):
        return None
    if ' | ' in s:
        return [f.strip() for f in s.split('|') if f.strip()]
    parts = [f.strip() for f in s.split(', ')]
    if len(parts) > 1 and all(p and ' ' not in p for p in parts):
        return parts
    return None


def _short_flag(f: str) -> str:
    named = ids_to_names(f)
    if named != f:
        return named
    return _FLAG_PREFIX.sub('', f).replace('_', ' ').lower()


def flags_html(old_s, new_s) -> str | None:
    """Bit-flag lists ('A | B | C') show only what was added / removed."""
    a, b = _flags(old_s), _flags(new_s)
    if a is None and b is None:
        return None
    a, b = set(a or ([old_s] if old_s else [])), set(b or ([new_s] if new_s else []))
    added = ''.join(f'<span class="flag add">+{esc(_short_flag(f))}</span>' for f in sorted(b - a))
    removed = ''.join(f'<span class="flag rem">−{esc(_short_flag(f))}</span>' for f in sorted(a - b))
    return f'<span class="vals flags">{added}{removed}</span>'


def _clip(s) -> str:
    s = '' if s is None else ids_to_names(str(s))
    return s if len(s) <= LONG_VALUE else s[:LONG_VALUE - 1] + '…'


PCT_PAD = '<span class="pct-pad"></span>'


def vals_html(c: dict) -> str:
    op = c.get('op')
    if c.get('cat') in ('visual', 'audio', 'ui'):
        return f'<span class="vals muted">{esc(op)}</span>'
    old_s = c.get('old_s', c.get('old'))
    new_s = c.get('new_s', c.get('new'))
    if op == 'rework':            # folded tier swap: bonus lists, may wrap
        return (f'<span class="vals wrap"><span class="old">{esc(old_s)}</span><span class="arrow">→</span>'
                f'<span class="new">{esc(new_s)}</span></span>')
    fl = flags_html(old_s, new_s)
    if fl:
        return fl
    old_s, new_s = _clip(old_s), _clip(new_s)
    # rows without a % pill keep its slot (.pct-pad, shown only in change rows), so the new
    # values of every row end on one vertical line
    if op == 'add':
        return f'<span class="vals"><span class="new">{esc(new_s)}</span>{PCT_PAD}</span>'
    if op == 'remove':
        return f'<span class="vals"><span class="old">{esc(old_s)}</span>{PCT_PAD}</span>'
    d = c.get('dir', 'changed')
    pct = c.get('pct')
    pct_s = f'<span class="pct dir-{d}">{pct:+.1f}%</span>' if isinstance(pct, (int, float)) else PCT_PAD
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
