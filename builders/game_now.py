"""A Game system's values today, open above its history (review 2026-10-05: a hero, item or unit page opens on what
it is now, a system page went straight into its history).

Two sources, both from data/ (no tracker at build time):
- the console variables the system reads (game_rules.ledger: the first tracked build is a snapshot of every
  variable, each later row moves one) — all of them, with the value now in the game's units and its history on hover,
  one panel per part;
- the numbers of its entries (the Soul Urn's carrier, a powerup, a crate) where the data has them: a field's newest
  value in the entry's history is its value today, because the history holds every move. A field never moved since
  the tracking began is not in the data, so an entry shows only the numbers Valve has tuned — the most recent first
  (`NOW_ROWS`), the most recently tuned entries (`NOW_PANELS`); entries with the same numbers share one panel;
- an entry that never moved since it came (Halloween's Candy Cauldron, owner 2026-11-01: its page said only "Added to
  the game files"): the numbers it came with, from the build record (`added_values`; a patch folds them into that row).
A rule for every hero or ability (the level curve) is no entry's number: its history below lists its moves."""
from __future__ import annotations

import re
from functools import lru_cache

from . import archive
from .common import esc, load_json, wbr_ids
from .game_systems import merged_label, system
from .now_values import Row, flow as now_flow, group as now_group

NOW_PANELS = 6         # entry panels a system's block shows (two rows of three): its most recently tuned entries
NOW_ROWS = 6           # numbers an entry's panel shows: its most recently moved ones
NOW_ADDED_ROWS = 30    # numbers of an entry that never moved: nothing says which matter, the troll's four buffs do
EVENTS_SYSTEM = 'events'
_DIGIT = re.compile(r'\d')
# numbers a new entry is born with that tell a player nothing, or a label that is a raw id (a map's key)
_ADDED_NOISE = re.compile(r'citadel|Debris|Model Scale|Bullet Velocity|Target Limit|Charge Delay|Channel Move|Time M(ax|in)')


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


@lru_cache(maxsize=16)
def _record(file: str) -> dict:
    return load_json(f'builds/{file}')


def _added_rows(key: str, pid: str) -> list[dict]:
    """The number rows an entry came with, from the record of the build that added it; its own fields before those of
    what it nests (the troll's chance before its four buffs)."""
    file, _, eid = key.partition(':')
    for b in archive.patch(pid).get('builds') or ():
        for e in _record(b['file'])['entities']:
            if e.get('file') == file and e.get('id') == eid:
                rows = [c for c in e['changes'] if c.get('op') == 'add' and c.get('cat') == 'balance']
                if rows:
                    return sorted(rows, key=lambda c: '{' in str(c.get('path')))
    return []


def added_values(key: str, h: list) -> list[tuple[str, str, str]]:
    """(label, value, date) of the numbers an entry came with. Only for an entry whose every row is its coming: one
    that moved shows its moves (`entry_values`)."""
    added = [row for row, ch in h if any(c.get('path') == '@add' for c in ch)]
    if len(h) != 1 or not added:
        return []
    vals = entry_values([(added[0], _added_rows(key, added[0]['id']))])
    return [v for v in vals if not _ADDED_NOISE.search(v[0]) and not v[1].startswith(('-1', '−1'))][:NOW_ADDED_ROWS]


def entry_panels(groups: list[list[tuple]], hist: dict, cat: dict) -> list[tuple[list[str], list[tuple[str, str, str]]]]:
    """([names], values) of the system's entries that have numbers today, in part order (`groups`: each part's
    [(key, name, icon kind)]); entries with the same numbers are one panel (twelve breakables share one edit); the
    `NOW_PANELS` most recently tuned are kept."""
    panels: dict[tuple, tuple[list[str], list, str]] = {}     # (label, value)s -> (names, values, newest move)
    for got in groups:
        for key, name, _ in got:
            if key.startswith('game:') or (cat.get(key) or {}).get('alive') is False:
                continue
            vals = entry_values(hist.get(key, ()))[:NOW_ROWS] or added_values(key, hist.get(key, ()))
            if not vals:
                continue
            same = tuple((k, v) for k, v, _ in vals)          # the same numbers, whenever each last moved
            names, first, newest = panels.get(same, ([], vals, ''))
            panels[same] = (names + [name], first, max(newest, vals[0][2]))
    keep = sorted(panels, key=lambda k: panels[k][2], reverse=True)[:NOW_PANELS]
    return [(names, vals) for k, (names, vals, _) in panels.items() if k in keep]


def _panel(title: str, rows: str, cls: str = '') -> str:
    return f'<section class="stat-panel{cls}"><h3>{esc(title)}</h3>{rows}</section>'


def _value_rows(vals: list[tuple[str, str, str]]) -> list[Row]:
    return [Row(esc(label), esc(v)) for label, v, _ in vals]


def _convar_rows(got: list[tuple[str, dict]]) -> str:
    from .game_rules import value_parts
    out = []
    for name, slot in got:
        cls, attrs, text = value_parts(name, slot)
        out.append(f'<div class="sc-row"><span class="k"><code>{wbr_ids(esc(name))}</code></span>'
                   f'<span class="{cls}"{attrs}>{text}</span></div>')
    return f'<div class="cv-rows">{"".join(out)}</div>'


def _event_groups(sys_id: str) -> list:
    """The seasonal events' dates from the game's own definition (data/events.json), newest event first."""
    if sys_id != EVENTS_SYSTEM:
        return []
    out = []
    for e in reversed(load_json('events.json')):
        rows = [('Starts', f'{e["start"]} UTC' if e['start'] else 'not set'),
                ('Valve test from', f'{e["test_start"]} UTC' if e['test_start'] else 'not set'),
                ('Ends', f'{e["end"]} UTC' if e['end'] else 'not set in the files'),
                ('Must be owned', 'yes' if e['must_be_owned'] else 'no')]
        out.append(now_group(e['name'], [Row(esc(k), esc(v)) for k, v in rows]))
    return out


def now_block(sys_id: str, parts: dict, hist: dict, cat: dict, convars: dict) -> str:
    """The system's "now" panels (a stat flow like a unit's "Current stats"): its entries' numbers, then its console
    variables per part. `parts`: game_pages.collect's entries of the system; `convars`: `game_rules.convar_parts` of it. '' when
    the data has no value of it today."""
    sys_ = system(sys_id)
    order = [p.id for p in sys_.parts]
    # the entries' numbers: groups of the one "today" component (now_values), flowing in columns — three columns of
    # boxes as tall as their tallest left empty frames (visual pass 2026-10-17, round 2)
    groups = now_flow(_event_groups(sys_id) +
                      [now_group(merged_label(names), _value_rows(vals))
                       for names, vals in entry_panels([parts[p] for p in order if p in parts], hist, cat)])
    # the console variables after them, across the width, their rows in columns of their own
    with_cvs = [p for p in sys_.parts if convars.get(p.id)]
    cvs = ''.join(_panel('Console variables' + (f' · {p.name}' if len(with_cvs) > 1 else ''),
                         _convar_rows(convars[p.id]), ' now-cv') for p in with_cvs)
    return f'<div class="now-flow">{groups}{cvs}</div>' if groups or cvs else ''
