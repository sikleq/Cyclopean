"""A Game system's values today, open above its history (review 2026-10-05: a hero, item or unit page opens on what
it is now, a system page went straight into its history).

Two sources, both from data/ (no tracker at build time):
- the console variables the system reads (game_rules.ledger: the first tracked build is a snapshot of every
  variable, each later row moves one) — all of them, with the value now in the game's units and its history on hover,
  one panel per part;
- the numbers of its entries (the Soul Urn's carrier, a powerup, a crate) where the data has them: a field's newest
  value in the entry's history is its value today, because the history holds every move. A field never moved since
  the tracking began is not in the data, so an entry shows only the numbers Valve has tuned — the most recent first
  (`NOW_ROWS`), the most recently tuned entries (`NOW_PANELS`); entries with the same numbers share one panel.
A rule for every hero or ability (the level curve) is no entry's number: its history below lists its moves."""
from __future__ import annotations

import re

from .common import esc
from .game_systems import merged_label, system

NOW_PANELS = 6         # entry panels a system's block shows (two rows of three): its most recently tuned entries
NOW_ROWS = 6           # numbers an entry's panel shows: its most recently moved ones
_DIGIT = re.compile(r'\d')


def entry_values(hist: list) -> list[tuple[str, str, str]]:
    """(label, value now, date of its last move) of an entry's numbers, the newest move first: each field's newest
    value in its history (`hist`: [(patch row, rows)]). A field removed since, a value with no number (a switch, a
    name) and work before release are left out."""
    from .cards import player_facing
    from .render import shown_pair
    last: dict[str, tuple[str, str]] = {}
    for prow, ch in sorted(hist, key=lambda rc: rc[0]['date']):
        for c in player_facing(ch):
            if c.get('status') == 'unreleased':
                continue
            label = str(c.get('label') or '')
            last.pop(label, None)           # a newer move of the field: its older number is not today's
            v = shown_pair(c)
            if v[0] == 'pair' and c.get('op') != 'remove' and v[2] and _DIGIT.search(str(v[2])):
                last[label] = (str(v[2]), prow['date'][:10])
    return sorted(((k, v, d) for k, (v, d) in last.items()), key=lambda x: x[2], reverse=True)


def entry_panels(groups: list[list[tuple]], hist: dict, cat: dict) -> list[tuple[list[str], list[tuple[str, str, str]]]]:
    """([names], values) of the system's entries that have numbers today, in part order (`groups`: each part's
    [(key, name, icon kind)]); entries with the same numbers are one panel (twelve breakables share one edit); the
    `NOW_PANELS` most recently tuned are kept."""
    panels: dict[tuple, tuple[list[str], list, str]] = {}     # (label, value)s -> (names, values, newest move)
    for got in groups:
        for key, name, _ in got:
            if key.startswith('game:') or (cat.get(key) or {}).get('alive') is False:
                continue
            vals = entry_values(hist.get(key, ()))[:NOW_ROWS]
            if not vals:
                continue
            same = tuple((k, v) for k, v, _ in vals)          # the same numbers, whenever each last moved
            names, first, newest = panels.get(same, ([], vals, ''))
            panels[same] = (names + [name], first, max(newest, vals[0][2]))
    keep = sorted(panels, key=lambda k: panels[k][2], reverse=True)[:NOW_PANELS]
    return [(names, vals) for k, (names, vals, _) in panels.items() if k in keep]


def _panel(title: str, rows: str, cls: str = '') -> str:
    return f'<section class="stat-panel{cls}"><h3>{esc(title)}</h3>{rows}</section>'


def _value_rows(vals: list[tuple[str, str, str]]) -> str:
    return ''.join(f'<div class="sc-row"><span class="k">{esc(label)}</span><span class="v">{esc(v)}</span></div>'
                   for label, v, _ in vals)


def _convar_rows(got: list[tuple[str, dict]]) -> str:
    from .game_rules import value_parts
    out = []
    for name, slot in got:
        cls, attrs, text = value_parts(name, slot)
        out.append(f'<div class="sc-row"><span class="k"><code>{esc(name)}</code></span>'
                   f'<span class="{cls}"{attrs}>{text}</span></div>')
    return f'<div class="cv-rows">{"".join(out)}</div>'


def now_block(sys_id: str, parts: dict, hist: dict, cat: dict, convars: dict) -> str:
    """The system's "now" panels (a stat flow like a unit's "Current stats"): its entries' numbers, then its console
    variables per part. `parts`: game_pages.collect's entries of the system; `convars`: `game_rules.convar_parts` of it. '' when
    the data has no value of it today."""
    sys_ = system(sys_id)
    order = [p.id for p in sys_.parts]
    panels = [_panel(merged_label(names), _value_rows(vals))
              for names, vals in entry_panels([parts[p] for p in order if p in parts], hist, cat)]
    with_cvs = [p for p in sys_.parts if convars.get(p.id)]
    for p in with_cvs:
        title = 'Console variables' + (f' · {p.name}' if len(with_cvs) > 1 else '')
        panels.append(_panel(title, _convar_rows(convars[p.id]), ' now-cv'))
    return f'<div class="stat-flow now-flow">{"".join(panels)}</div>' if panels else ''
