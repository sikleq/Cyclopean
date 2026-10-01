"""Entity cards: the one component every change list uses (patch notes, all changes,
build pages, hero / item / unit history). A card = framed 48px icon, name, subtitle,
tag counters and the strip of history squares; inside it optional ability sub-headers
and rows on a fixed grid: status | tag | text | old -> new."""
from __future__ import annotations

import re

from .common import esc, mark, visual
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
    counters = tag_summary(counted) if counted else ''
    return (f'<header class="ecard-h"><span class="ei">{visual(icon_url, glyph)}</span>'
            f'<div class="en"><div class="nm">{nm}</div>{sub_html}</div>'
            f'<div class="er">{counters}{trail}</div></header>')


COMPACT_ROWS = 2      # a card with this few rows gets a slim header (design review: one row under a 58px header)


def card(head: str, body: str, *, hidden: bool = False, dev: bool = False, search: str = '', anchor: str = '',
         extra: str = '', rows: int | None = None) -> str:
    compact = rows is not None and rows <= COMPACT_ROWS
    cls = ('ecard' + (' compact' if compact else '') + (' has-hidden' if hidden else '') + (' dev' if dev else '')
           + (f' {extra}' if extra else ''))
    ds = f' data-search="{esc(search)}"' if search else ''
    aid = f' id="{esc(anchor)}"' if anchor else ''
    return f'<article class="{cls}"{aid}{ds}>{head}<div class="eb">{body}</div></article>'


def sub_head(name: str, icon_url: str | None, glyph: str, counted: list[dict], hidden: bool = False) -> str:
    """An ability inside its hero's card."""
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


def change_rows(changes: list[dict]) -> str:
    rows = sort_changes(fold_tier_swaps(merge_renames(changes)))
    main = [c for c in rows if not is_engine(c)]
    tech = [c for c in rows if is_engine(c)]
    html = ''.join(row(c.get('status', 'hidden'), tag_html(c), esc(c.get('label')), vals_html(c)) for c in main)
    if tech:
        inner = ''.join(row(c.get('status', 'hidden'), tag_html(c), esc(c.get('label')), vals_html(c)) for c in tech)
        hid = ' has-hidden' if is_hidden(tech) else ''
        html += f'<details class="tech{hid}"><summary>Technical ({len(tech)})</summary>{inner}</details>'
    return html
