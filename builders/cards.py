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
            adds.setdefault(c.get('label'), []).append(c)
    out, used = [], set()
    for c in changes:
        if c.get('op') == 'remove' and adds.get(c.get('label')):
            a = adds[c['label']].pop(0)
            used.add(id(a))
            out.append({**a, 'op': 'change', 'old_s': c.get('old_s'), 'old': c.get('old'),
                        'status': min((a.get('status', 'hidden'), c.get('status', 'hidden')),
                                      key=lambda s: s not in HIDDEN_LIKE)})
            continue
        out.append(c)
    return [c for c in out if id(c) not in used]


def is_engine(c: dict) -> bool:
    vals = [str(c.get(k) or '').strip() for k in ('old_s', 'new_s')]
    vals = [v for v in vals if v and v != '—']
    return bool(vals) and all(_ENGINE_VALUE.match(v) for v in vals) or bool(_ENGINE_LABEL.search(str(c.get('label'))))


def player_facing(changes: list[dict]) -> list[dict]:
    """The rows a player reads, which is what EVERY counter counts (home summary, patches index,
    heroes index, card headers, history bands): renames merged, replaced tiers folded into one
    REWORK, engine plumbing out. Folding works per entity (a hero card mixes its abilities)."""
    groups: dict[str, list[dict]] = {}
    for c in changes:
        groups.setdefault(':'.join(str(c.get('key') or '').split(':', 2)[:2]), []).append(c)
    return [c for g in groups.values() for c in fold_tier_swaps(merge_renames(g)) if not is_engine(c)]


def change_row(c: dict) -> str:
    # a replaced tier lists both bonus sets: they go on their own full-width line under the
    # label (two lines at most, click to expand) instead of a tall right-aligned column
    extra = 'rw' if c.get('op') == 'rework' else ''
    return row(c.get('status', 'hidden'), tag_html(c), esc(c.get('label')), vals_html(c), extra)


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
    main = [c for c in rows if not is_engine(c)]
    tech = [c for c in rows if is_engine(c)]
    html = ''.join(change_row(c) for c in main)
    if tech:
        inner = ''.join(change_row(c) for c in tech)
        hid = ' has-hidden' if is_hidden(tech) else ''
        html += f'<details class="tech{hid}"><summary>Technical ({len(tech)})</summary>{inner}</details>'
    return html
