"""Game rules (the Game section's stats tab): the console variables a game reads — respawn times, soul rewards,
crate, Soul Urn and Unstable Rift timers — with their values today and each value's history on hover (the stats
tables' `hist-tip`). Valve tunes several of these in patches ("Respawn Time at 20 minutes increased from 35s to 38s"
is `citadel_player_spawn_time_max_ramp_1`), and they were only in the patch archive's list (coverage audit
2026-10-05, finding 2).

Values come from the patches' console variable rows: the first build with them (6395, 2026-03-10) is a snapshot of
every variable; each later row moves one. The level curve and the shop's tier prices are not here: the files list
them only when they change, so their values today are not known for every level (the Game › Hero progression page
has their history)."""
from __future__ import annotations

from .common import esc, json_attr, page
from .game_systems import SECTION, convar_number, convar_place, convar_side, convar_unit, convar_value, shown

DIGITS = 3


def _num(v):
    try:
        f = float(str(v))
    except (TypeError, ValueError):
        return v
    return int(f) if f.is_integer() else f


def ledger(raw: list) -> dict[str, dict]:
    """name -> {value, flags, hist: [[build, date, old, new], …]} of every console variable, from the patches'
    rows (patch row, convars) in patch order; a removed variable has value None."""
    from .game_systems import convar_start
    out: dict[str, dict] = {}
    start = convar_start()
    for row, cvs in raw:
        for cv in sorted(cvs, key=lambda x: x.get('build') or 0):
            if cv.get('op') == 'desc':
                continue
            slot = out.setdefault(cv['name'], {'value': None, 'flags': cv.get('flags'), 'hist': []})
            new = None if cv.get('op') == 'remove' else cv.get('new')
            if cv.get('build') != start:
                slot['hist'].append([cv.get('build'), row['date'][:10], _num(slot['value']) if slot['value'] is not None
                                     else None, _num(new) if new is not None else None])
            slot['value'] = new
            slot['flags'] = cv.get('flags') or slot['flags']
    return out


def convar_parts(led: dict) -> dict[str, dict[str, list[tuple[str, dict]]]]:
    """system id -> part id -> [(name, ledger entry)] of the variables a game reads that exist today, by name
    (`led`: `ledger`); a system page's "now" block lists them per part (game_now), this table per system."""
    out: dict = {}
    for name, slot in sorted(led.items()):
        hit = convar_place({'name': name, 'flags': slot['flags']})
        if hit and slot['value'] is not None:
            out.setdefault(hit[0], {}).setdefault(hit[1], []).append((name, slot))
    return out


def rules_rows(raw: list, led: dict | None = None) -> dict[str, list[tuple[str, dict]]]:
    """system id -> [(name, ledger entry)] of the variables a game reads that exist today, by name. `led`: the
    ledger of `raw` when the caller has it already."""
    parts = convar_parts(ledger(raw) if led is None else led)
    return {sid: sorted((x for got in by_part.values() for x in got), key=lambda x: x[0])
            for sid, by_part in parts.items()}


def value_parts(name: str, slot: dict) -> tuple[str, str, str]:
    """(class, attributes, text) of a console variable's value now in the game's units (game_systems.convar_value:
    2165.35 engine units read 55m) with its history on hover on the same scale (`data-unit`) — the Game rules table
    and a system page's "now" block (game_now) print it alike."""
    unit = convar_unit(name)[0]

    def scaled(v):
        x = convar_number(name, v)
        return v if x is None else x
    hist = [[b, d, None if o is None else scaled(o), scaled(n)] for b, d, o, n in slot['hist'] if n is not None]
    attrs = f' data-pol="{convar_side(name)}" data-digits="{DIGITS}"' + (f' data-unit="{esc(unit)}"' if unit else '')
    cls = 'v'
    if hist:
        cls += ' has-hist'
        attrs += json_attr('data-hist', hist) + f' data-title="{esc(name)}"'
    return cls, attrs, esc(convar_value(name, slot['value']))


def _cell(name: str, slot: dict) -> str:
    cls, attrs, text = value_parts(name, slot)
    return f'<td class="{cls}"{attrs}>{text}</td>'


DASH = '<span class="dash">—</span>'


def _row(name: str, slot: dict) -> str:
    """Name | value now (its history on hover) | how many times it moved (NEW: added since the tracking began, no
    move yet — "—" beside a date read as a contradiction on 55 of 190; review 2026-10-05) | the date of the last
    move."""
    from .render import tag_badge
    moves = [h for h in slot['hist'] if h[2] is not None and h[3] is not None]
    last = esc(slot['hist'][-1][1]) if slot['hist'] else DASH
    count = str(len(moves)) if moves else tag_badge('new', 'NEW') if slot['hist'] else DASH
    return (f'<tr data-search="{esc(name.lower())}"><td class="nm"><code>{esc(name)}</code></td>{_cell(name, slot)}'
            f'<td>{count}</td><td>{last}</td></tr>')


def rules_page(raw: list, led: dict | None = None) -> str:
    from .game_pages import section_tabs
    from .game_systems import icon_html
    rel = '../'
    rows = rules_rows(raw, led)
    body = []
    for s in shown():                 # ONE table: a band row per system (its page), its variables below
        got = rows.get(s.id)
        if not got:
            continue
        body.append(f'<tr class="sec"><td colspan="4"><a href="{esc(s.href)}">{icon_html(s, rel, "px rules-ic")}'
                    f'{esc(s.name)}</a></td></tr>' + ''.join(_row(name, slot) for name, slot in got))
    # one column: the heading, the tabs and a search over the variables above the table, which scrolls with the
    # page (its own 816px scroll box inside the page's was a double scroll over 200 rows; review 2026-10-05)
    content = (f'<div class="toolbar"><input type="search" placeholder="Variable…" '
               f'data-search-target="table.game-rules tbody tr:not(.sec)"></div>'
               f'<table class="game-rules"><thead><tr><th>Console variable</th><th>Now</th><th>Changes</th>'
               f'<th>Last change</th></tr></thead><tbody>{"".join(body)}</tbody></table>'
               if body else '<p class="muted">No console variables recorded.</p>')
    return page('Game rules', '<div class="rules-col"><h1>Game rules</h1>' + section_tabs('stats') + content + '</div>',
                rel, SECTION,
                description='Deadlock: respawn times, soul rewards and objective timers as the game sets them today')
