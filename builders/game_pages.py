"""The Game section (coverage audit 2026-10-05): everything that is not one hero, item or unit — the Soul Urn, crates,
powerups, soul sharing, the level curve, respawn times — as systems (builders/game_systems.py), with the same three
tabs as the other sections: an index of the systems, the rules as they are now (Game rules: the console variables a
game reads, their values today and their history) and a change matrix "systems × patches" (dynamics_page).

A system's page is the history view of a unit family (history_view.history_table): one band per patch, a group per
entry, the parts as filters. Its entries: the map objects, game rules, effects and loot tables it names, the
abilities no hero owns (Drop Soul Urn; jump, dash and parry for every hero — heroes/shared.html moved here), a rule for
every hero or ability as one group per part ("Level curve · all 61 heroes"), the console variables as one group per
part, and a template's change only where no heir shows it ("Trooper template")."""
from __future__ import annotations

from collections import defaultdict

from .common import entity_icon, esc, page, plural, write
from .game_systems import (ALL_PREFIX, CONVAR_PREFIX, SECTION, is_template, merged_label, name_of, place,
                           place_all_row, place_entity, shown, system, systems)
from .shared_rows import is_every

RAW_CONVARS = '@convars:raw'      # by_ent: every patch's console variable rows as they are (Game rules table)


def _heir_sigs(by_ent: dict, cat: dict) -> dict[tuple[str, str], set]:
    """(file, patch id) -> {(path, old, new)} of the entries that are no template: a template's change one of its
    heirs shows too is the heir's (trooper_base's shrine range is every trooper's)."""
    out: dict[tuple[str, str], set] = defaultdict(set)
    for key, hist in by_ent.items():
        file, _, eid = key.partition(':')
        if not file.endswith('.vdata') or is_template(cat.get(key) or {'id': eid}):
            continue
        for row, ch in hist:
            out[(file, row['id'])] |= {(c.get('path'), str(c.get('old_s')), str(c.get('new_s'))) for c in ch}
    return out


def template_rows(key: str, hist: list, sigs: dict) -> list:
    """A template's history without the changes an heir shows: (patch row, rows) of the rest."""
    file = key.partition(':')[0]
    out = []
    for row, ch in hist:
        mine = [c for c in ch if (c.get('path'), str(c.get('old_s')), str(c.get('new_s'))) not in sigs.get((file, row['id']), ())]
        if mine:
            out.append((row, mine))
    return out


def collect(by_ent: dict, cat: dict, pages: set[str] | None = None) -> tuple[dict, dict]:
    """(entries, history): entries = system id -> part id -> [(key, name, icon kind)]; history = key -> [(patch row,
    rows)] for every Game key, the pseudo ones ('game:<system>:<part>:all' — a rule for every hero / ability — and
    '…:convars') included. `pages`: the keys hero / item / unit pages show (game_systems.place_entity)."""
    entries: dict = defaultdict(lambda: defaultdict(list))
    hist: dict = {}
    sigs = None
    for key, h in by_ent.items():
        if key.startswith(ALL_PREFIX):
            file = key[len(ALL_PREFIX):]
            per: dict = defaultdict(dict)          # (system, part) -> patch id -> (patch row, rows)
            for row, ch in h:
                for c in ch:
                    per[place_all_row(file, c)].setdefault(row['id'], (row, []))[1].append(c)
            for (sid, pid), by_patch in per.items():
                k = f'game:{sid}:{pid}:all:{file}'
                hist[k] = list(by_patch.values())
                entries[sid][pid].append((k, '', ''))
            continue
        if key.startswith(CONVAR_PREFIX):
            hit = place(f'convar:{key[len(CONVAR_PREFIX):]}')
            if hit:
                k = f'game:{hit[0]}:{hit[1]}:convars'
                if k not in hist:
                    hist[k] = []
                    entries[hit[0]][hit[1]].append((k, '', ''))
                hist[k].extend(h)
            continue
        file, _, eid = key.partition(':')
        if not file.endswith('.vdata'):          # 'text:…' (text_rows), '@convars:raw' (game_rules)
            continue
        e = cat.get(key) or {'file': file, 'id': eid}
        hit = place_entity(key, e, pages)
        if not hit:
            continue
        # a rule for every hero / ability is its part's own group here ('game:<system>:<part>:all'): on an entry
        # it was a link row to this very page and band ("Climb rope, Dash + 6 more" held only "All abilities &
        # items: 1 change · Movement & combat ›"; review 2026-10-05)
        h = [(row, own) for row, ch in h for own in [[c for c in ch if not is_every(c)]] if own]
        if not h:
            continue
        if is_template(e):
            if sigs is None:
                sigs = _heir_sigs(by_ent, cat)
            h = template_rows(key, h, sigs)
            if not h:
                continue
        hist[key] = h
        entries[hit[0]][hit[1]].append((key, name_of(key, e), e.get('kind') or ''))
    # an entry's name / description changes (text_rows: Drop Soul Urn was "Throw Idol")
    from .text_rows import TEXT_PREFIX
    for k in [k for k in hist if not k.startswith('game:')]:
        if TEXT_PREFIX + k in by_ent:
            hist[TEXT_PREFIX + k] = by_ent[TEXT_PREFIX + k]
    # a part's console variables: one group, its rows in patch order (several variables per patch)
    for k, h in hist.items():
        if k.endswith(':convars'):
            merged: dict = {}
            for row, ch in h:
                merged.setdefault(row['id'], (row, []))[1].extend(ch)
            hist[k] = list(merged.values())
    return entries, hist


def _keys(sys_id: str, parts: dict, rel: str) -> tuple[list, dict]:
    """history_table's keys of a system page in part order (entries by name, then the part's rules for all and its
    console variables) and their parts (`areas`)."""
    sys_ = system(sys_id)
    keys, areas = [(f'game:{sys_id}', sys_.name, None)], {}
    for part in sys_.parts:
        got = parts.get(part.id) or []
        real = sorted((x for x in got if not x[0].startswith('game:')), key=lambda x: x[1].lower())
        pseudo = sorted((x for x in got if x[0].startswith('game:')), key=lambda x: x[0].endswith(':convars'))
        for k, nm, kind in real:
            file, _, eid = k.partition(':')
            keys.append((k, nm, entity_icon(file, eid, kind, rel, nm)))
            areas[k] = part.id
        for k, _, _ in pseudo:
            # a rule for every hero / ability is the part itself ("Level curve"; its rows say "all 61 heroes")
            keys.append((k, 'Console variables' if k.endswith(':convars') else part.name, None))
            areas[k] = part.id
    return keys, areas


def system_page(sys_id: str, parts: dict, hist: dict, by_subject: dict) -> str:
    from .history_view import history_table
    from .game_systems import icon_html
    rel = '../'
    sys_ = system(sys_id)
    keys, areas = _keys(sys_id, parts, rel)
    # the parts are the toolbar's filters (Soul Urn / Unstable Rift): the head is the icon and the name
    labels = tuple((p.id, p.name) for p in sys_.parts if p.id in parts)
    head = (f'<div class="crumbs"><a href="index.html">Game</a> / {esc(sys_.name)}</div>'
            f'<div class="page-head">{icon_html(sys_, rel, "head-icon px px-frame")}<div><h1>{esc(sys_.name)}</h1>'
            f'</div></div>')
    body = history_table(keys, list(sys_.subjects), hist, by_subject, rel, line_names=False, areas=areas,
                         area_labels=labels, merge=merged_label)
    return page(sys_.name, head + body, rel, SECTION, cls='entity',
                description=f'Deadlock: every change to {sys_.name.lower()}, from the game files')


def _stats(hist: dict, keys: list[str]) -> tuple[int, str]:
    """(changes a player reads, the newest patch date) of a system: the history rows of its keys."""
    from .cards import player_facing
    n, last = 0, ''
    seen: set[tuple] = set()          # one edit over several entries counts once (the band, matrix and home icon)
    for k in keys:
        for row, ch in hist.get(k, ()):
            rows = [c for c in player_facing(ch) if c.get('status') != 'unreleased'
                    and (row['id'], c.get('label'), c.get('old_s'), c.get('new_s')) not in seen]
            seen.update((row['id'], c.get('label'), c.get('old_s'), c.get('new_s')) for c in rows)
            n += len(rows)
            if rows:
                last = max(last, row['date'][:10])
    return n, last


def index_page(entries: dict, hist: dict) -> str:
    from .game_systems import icon_html
    rel = '../'
    cards = []
    for s in shown():
        parts = entries.get(s.id)
        if not parts:
            continue
        n, last = _stats(hist, [k for got in parts.values() for k, _, _ in got])
        # the date in the body font (dates are never in the pixel fonts)
        when = f'<span class="last"><span class="d">last {esc(last)}</span></span>' if last else ''
        cards.append(f'<a class="card px-frame game-card" href="{esc(s.href)}" data-search="{esc(s.name.lower())}">'
                     f'{icon_html(s, rel)}<span class="nm">{esc(s.name)}</span>'
                     f'<span class="sub">{esc(plural(n, "change"))}</span>{when}</a>')
    body = ('<h1>Game</h1>' + section_tabs('index') +
            '<div class="toolbar"><input type="search" placeholder="System…" data-search-target=".game-card"></div>'
            f'<div class="grid units game-grid">{"".join(cards)}</div>')
    return page('Game', body, rel, SECTION, description='Deadlock: every change to the game rules, map objects, '
                                                         'souls, respawn and the Soul Urn, from the game files')


def section_tabs(active: str) -> str:
    from .common import section_tabs as tabs
    return tabs(SECTION, active)


def matrix_page() -> str:
    from .dynamics_page import game_entries, matrix_html, toolbar
    rel = '../'
    return page('Game changes', '<h1>Game changes</h1>' + section_tabs('changes') + toolbar('game', 0, '')
                + matrix_html(game_entries(rel), 'game'), rel, SECTION, wide=True)


def build_all(by_ent: dict, by_subject: dict, cat: dict, pages: set[str] | None = None
              ) -> tuple[int, list[list[str]]]:
    """Every Game page; returns (how many systems have one, their site_search rows). `pages`: the keys the hero,
    item and unit pages show (entities_pages.page_keys): the Game takes the rest."""
    from .game_rules import rules_page
    from .game_systems import missing_icons
    bad = missing_icons()
    if bad:              # AGENTS rule 8: a missing icon fails the build, never a silent stand-in
        raise SystemExit(f'game_systems.json: icons not in icons/: {", ".join(bad)}')
    entries, hist = collect(by_ent, cat, pages)
    n = 0
    for s in systems():
        if entries.get(s.id):
            write(f'{SECTION}/{s.href}', system_page(s.id, entries[s.id], hist, by_subject))
            n += 1
    write(f'{SECTION}/index.html', index_page(entries, hist))
    write(f'{SECTION}/rules.html', rules_page(by_ent.get(RAW_CONVARS, [])))
    write(f'{SECTION}/changes.html', matrix_page())
    return n, search_rows(entries)


def search_rows(entries: dict) -> list[list[str]]:
    """site_search rows: every system, and every named Game entry with a history (an entry opens its system's page
    filtered to it, #ab-<id>, as an ability opens its hero's). `entries`: `collect`'s."""
    from .game_systems import icon_url
    rows = []
    for s in systems():
        parts = entries.get(s.id)
        if not parts:
            continue
        ic = icon_url(s, '') or ''
        rows.append([s.name, f'{SECTION}/{s.href}', 'Game', ic])
        for got in parts.values():
            for k, nm, kind in got:
                if k.startswith('game:') or not nm:
                    continue
                file, _, eid = k.partition(':')
                rows.append([nm, f'{SECTION}/{s.href}#ab-{eid}', f'{s.name} · Game',
                             entity_icon(file, eid, kind, '', nm) or ic])
    return rows
