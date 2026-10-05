"""Patch notes written from the files: the patch page's "Not in patch notes" tab (what Valve's notes left out) and
"From the files" (an update Valve wrote nothing for).

One line per row the patch's counters count (`patch_counts.counted_rows`, so the tab says the number it lists), in
Valve's words ("Kelvin · Frozen Shelter: Charge Delay added (default)"), with the tag badge and the values the entity
pages print (`render.shown_pair`, `render.tag_of`; two namesakes told apart by `cards.disambiguate`). The lines were
`pipeline.match.sentence` over raw values (review 2026-10-05: 425 of 5,888 lines dumped whole flag masks, printed
"-1" where the hero page reads "default", engine enum words, and "Outgoing Bullet Damage Penalty reduced from -35% to
-40%" — the penalty grew)."""
from __future__ import annotations

import re

from .common import esc, plural

# Valve's sections, in its order; a line goes where its home icon goes (hero / item / unit page, else the Game's)
SECTIONS = (('heroes', 'Heroes'), ('items', 'Items'), ('units', 'Units'), ('game', 'Game rules & map objects'),
            ('convars', 'Console variables'))
LINE_LIMIT = 1500           # lines a tab prints (City Never Sleeps: 1,000 counted rows)
_NUM = re.compile(r'^([-−+]?)(\d+(?:\.\d+)?)(\D*)$')


def _number(s) -> tuple[float, str] | None:
    """(signed value, unit) of a shown value: "−35%" -> (-35.0, '%'); None for words."""
    m = _NUM.match(str(s or '').strip())
    if not m:
        return None
    return (-1 if m.group(1) in ('-', '−') else 1) * float(m.group(2)), m.group(3).strip()


def verb(old, new, pct=None) -> str:
    """'increased' / 'reduced' / 'changed' for two shown values. Below zero the row's percent decides, the one its
    pill shows (the pipeline reads a penalty or a slow by its size, a resist by its sign), else the size: a penalty
    of −35% → −40% grew, a slow of −25% → −22% got weaker (review 2026-10-05: the sign decided, so both read the wrong
    way). Not above zero: the percent of a value shown in other terms can run the other way ("Stamina Cooldown 5s →
    6s" is −16.7% of the regen rate). A sign flip, another unit or words: 'changed'."""
    a, b = _number(old), _number(new)
    if a is None or b is None or a[1] != b[1] or a[0] == b[0]:
        return 'changed'
    x, y = a[0], b[0]
    if x < 0 < y or y < 0 < x:
        return 'changed'
    if x >= 0 and y >= 0:
        return 'increased' if y > x else 'reduced'
    if isinstance(pct, (int, float)) and pct:
        return 'increased' if pct > 0 else 'reduced'
    return 'increased' if abs(y) > abs(x) else 'reduced'


def line_text(c: dict) -> str:
    """What changed, after the name: "Charge Delay added (default)", "Applies: +Air Jumps Disabled", "Health
    increased from 780 to 800" — the values as the entity pages show them (`render.shown_pair`)."""
    from .render import shown_pair
    path = str(c.get('path') or '')
    if path == '@add':
        return 'added to the game'
    if path == '@return':
        return 'back in the game files'
    if path == '@remove':
        return 'removed from the game'
    label = str(c.get('label') or '')
    op = c.get('op')
    v = shown_pair(c)
    if v[0] == 'none':
        return f'{label} changed'
    if v[0] == 'flags':
        return f'{label}: ' + ' '.join(w for w, _ in v[1])
    if v[0] == 'steps':
        return f'{label}: {v[1]}'
    old, new = v[1], v[2]
    if v[0] == 'list':
        if op == 'rework':
            return f'{label} reworked: {old} → {new}'
        return f'{label} added: {new}' if op == 'add' else f'{label} removed (was {old})'
    if op == 'add':
        return f'{label} added ({new})' if new not in ('', '—') else f'{label} added'
    if op == 'remove':
        return f'{label} removed (was {old})' if old not in ('', '—') else f'{label} removed'
    return f'{label} {verb(old, new, c.get("pct"))} from {old} to {new}'


def section_of(e: dict | None, on_page: bool) -> str:
    """The section of a counted row's entity: a hero's page (its abilities and guns), an item's, a unit's, else the
    Game's (rules, map objects: no page shows them); a console variable its own."""
    from .shared_rows import catalog
    if e is None:
        return 'convars'
    if not on_page:
        return 'game'
    own = f"{e['file']}:{e['id']}"
    # the catalog knows which units bind an ability (a Patron's Rocket Barrage, the zip line: the patch record does not)
    e = {**e, **{k: v for k, v in (catalog().get(own) or {}).items() if k in ('units', 'owner', 'kind')}}
    keys = (e.get('target_keys') or [own]) if e.get('id') == '@shared' else [own]
    file, _, eid = keys[0].partition(':')
    if file == 'heroes.vdata' or str(e.get('owner') or '').startswith('hero_'):
        return 'heroes'
    if file == 'npc_units.vdata' or e.get('units') or e.get('kind') in ('trooper', 'neutral', 'building', 'helper',
                                                                        'unit'):
        return 'units'
    if eid.startswith('upgrade_') or e.get('kind') == 'item':
        return 'items'
    return 'heroes' if file == 'abilities.vdata' else 'game'


def who(e: dict | None, name: str, heroes: dict[str, str]) -> str:
    """The line's subject: an ability with its hero ("Kelvin · Frozen Shelter", as Valve writes "Kelvin: …"), a
    hero's base stats by the hero, a console variable by its own name."""
    if e is None:
        return 'Console variable'
    owner = str(e.get('owner') or '')
    if owner.startswith('hero_') and e['file'] != 'heroes.vdata':
        hero = heroes.get(owner)
        if hero and hero != owner and hero != name:
            return f'{hero} · {name}'
    return name


def _lines(rows: list[tuple[dict | None, dict, bool]], name_of, heroes: dict[str, str]) -> dict[str, list[tuple]]:
    """section -> [(sort key, subject, row)]: one entity's rows told apart as on its page (`cards.disambiguate`)."""
    from .cards import disambiguate
    from .history_view import id_tail
    by_ent: dict[int, tuple[dict | None, list[dict], bool]] = {}
    for e, c, on_page in rows:
        slot = by_ent.setdefault(id(e) if e is not None else id(c), (e, [], on_page))
        slot[1].append(c)
    out: dict[str, list[tuple]] = {}
    first: dict[tuple[str, str], str] = {}        # (section, subject) -> the id that has it plain
    for e, got, on_page in by_ent.values():
        subject = who(e, name_of(e) if e is not None else '', heroes)
        sec = section_of(e, on_page)
        if e is not None and e['id'] != '@shared':
            # two entities of one name (City Never Sleeps' five removed guns all "Weapon"): the later ones say how
            # their id differs, as a page's namesake groups do (history_view._namesakes)
            had = first.setdefault((sec, subject), e['id'])
            tail = id_tail(had, e['id']) if had != e['id'] else ''
            subject = f'{subject} · {tail}' if tail else subject
        for c in disambiguate(got) if e is not None else got:
            out.setdefault(sec, []).append((subject.lower(), subject, c))
    return out


def notes_html(rows: list[tuple[dict | None, dict, bool]], name_of, heroes: dict[str, str]) -> tuple[str, int]:
    """(the written notes' HTML, how many lines they hold): Valve's sections, the lines of each by subject; a line
    is its tag badge (render.tag_badge) and its sentence."""
    from .render import TAG_ORDER, tag_badge, tag_of
    secs = _lines(rows, name_of, heroes)
    out, n, cut = [], 0, 0
    for sid, title in SECTIONS:
        got = sorted(secs.get(sid, ()), key=lambda x: (x[0], TAG_ORDER.get(tag_of(x[2])[0], 9)))
        lis = []
        for _, subject, c in got:
            if n >= LINE_LIMIT:
                cut += 1
                continue
            n += 1
            cls, word = tag_of(c)
            # a console variable's name is its subject, in the engine's spelling (the one id a page shows, AGENTS)
            text = (f'<code>{esc(c.get("label"))}</code> ' + esc(line_text({**c, 'label': ''}).lstrip(': '))
                    if sid == 'convars' else f'{esc(subject)}: {esc(line_text(c))}')
            lis.append(f'<li>{tag_badge(cls, word)}<span class="gn-t">{text}</span></li>')
        if lis:
            out.append(f'<h3 class="gn-h">{esc(title)}<span class="n">{len(lis)}</span></h3>'
                       f'<ul class="gen-notes cols-2">{"".join(lis)}</ul>')
    more = f'<p class="muted">+{plural(cut, "more line")}.</p>' if cut else ''
    return ''.join(out) + more, n + cut
