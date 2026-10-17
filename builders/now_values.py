"""What an entity is today, above its history: ONE component for a unit's stats, an item's sections, a Game system's
entries and a hero's other stats (visual pass 2026-10-17, round 2 — equal-height boxes with one row in a box made for
six, values floating mid-card, three-column lists leaving empty boxes: three looks for one thing).

Groups — a heading, maybe a line of chips and a text, then label · value rows — flow down CSS columns like the console
variables (styles.css `.stat-flow`): a group stays whole where it fits, a long one (more than `LONG_GROUP` rows) may go
on in the next column, a lone group's rows flow on under its heading. No box per group, so a short group leaves no
empty frame; each value sits at its column's right edge; in a group every row has an icon slot, or none does."""
from __future__ import annotations

from dataclasses import dataclass

from .common import esc

LONG_GROUP = 8            # rows a group keeps in one column; a longer one may continue in the next


@dataclass(frozen=True)
class Row:
    """One label · value row. `label` and `value` are HTML; `icon`: the icon's URL (None: the game has none);
    `cls`: classes of the row (`p-<css>` colours a value as the game does); `vcls` / `attrs`: of the value (its
    history on hover)."""
    label: str
    value: str
    icon: str | None = None
    cls: str = ''
    vcls: str = ''
    attrs: str = ''


def _row_html(r: Row, slots: bool) -> str:
    ic = ''
    if slots:
        ic = (f'<img class="si" src="{esc(r.icon)}" alt="" loading="lazy">' if r.icon else '<span class="si"></span>')
    cls = f' {r.cls}' if r.cls else ''
    vcls = f' {r.vcls}' if r.vcls else ''
    return f'<div class="sc-row{cls}"><span class="k">{ic}{r.label}</span><span class="v{vcls}"{r.attrs}>{r.value}</span></div>'


def group(title: str, rows: list[Row], top: str = '', cls: str = '') -> str:
    """A group: its heading (plain text; an item's untitled section — the tooltip gives some none — has no heading
    bar, an empty one read as a glitch), `top` (HTML: an item section's chips and text) and its rows; '' without
    rows or top. An icon slot on every row when any row has an icon, else none."""
    if not rows and not top:
        return ''
    slots = any(r.icon for r in rows)
    classes = ''.join(f' {c}' for c in (('long' if len(rows) > LONG_GROUP else ''), ('' if title else 'untitled'), cls)
                      if c)
    head = f'<h3>{esc(title)}</h3>' if title else ''
    top_html = f'<div class="vg-top">{top}</div>' if top else ''
    return (f'<section class="stat-panel{classes}">{head}{top_html}'
            + ''.join(_row_html(r, slots) for r in rows) + '</section>')


def flow(groups: list[str]) -> str:
    """The groups in columns; '' when none has anything."""
    got = [g for g in groups if g]
    return f'<div class="stat-flow">{"".join(got)}</div>' if got else ''
