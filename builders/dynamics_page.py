"""Hero / item / unit changes as a matrix (Sloppy's "Hero Dynamics"): one row per hero, item or unit, one column per
patch, each cell a tile striped in the colours of what the patch did (buff, nerf, new, removed…),
each stripe as tall as its share.

A hero's tile holds everything the patch did to the hero — stats, weapon and abilities in one cell;
a filter (All / Stats / Weapon / Abilities) narrows every tile to one part (owner, 2026-10-01: one
cell, a filter, no split tiles). Switches: older patches, buff-vs-nerf (one net colour per cell), tag filters, pre-release heroes /
removed items; a search over the rows; a hover card per cell (scripts.js, from the page's JSON).

The Game section's matrix (game/changes.html, coverage audit 2026-10-05) has a row per system (game_systems): what no
hero, item or unit page shows — map objects, rules, effects, abilities no hero owns, a template's change no heir
shows, a rule for every hero or ability (once), the console variables a game reads."""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from functools import lru_cache

from .common import (EYE_MARK, display_name, entity_icon, esc, hero_icon, load_json, patch_name, patch_title_text,
                     visual)
from .render import TAG_ORDER, TAG_WORD_ONE, TAG_WORDS, tag_badge, tag_of
from .weights import NET_WORDS, net_of

OLD_DAYS = 365            # columns older than this hide behind "Older patches"
SAMPLES = 2               # the hover card lists this many biggest changes per part of a hero
SAMPLES_ONE = 3           # … and of an item or unit (one part: the row itself)
PARTS = (('stats', 'Stats'), ('weapon', 'Weapon'), ('abil', 'Abilities'))
WEAPON_KINDS = ('weapon', 'melee')


def part_of(e: dict) -> str:
    if e['file'] == 'heroes.vdata':
        return 'stats'
    return 'weapon' if e.get('kind') in WEAPON_KINDS else 'abil'


def _sample_values(c: dict) -> tuple[str, str]:
    """(old, new) of a hover card's row: a flag field a player plays with reads as the bits that moved,
    in words ("+neutrals −doesn't interrupt melee", like its row on the page), not as two whole masks
    in engine words (review 2026-10-04); everything else as the page prints it — the row's own function
    (render.shown_pair): "Channel Move Speed 6m/s → -1" and "Charge Delay 0s → -1s" read "no limit" / "default"
    on the page (review 2026-10-05)."""
    from .render import vals_text
    return vals_text(c)


def _display(e: dict) -> str:
    if e['file'] == 'heroes.vdata':
        return 'Base stats'
    return display_name(e)


@lru_cache(maxsize=1)
def _collect() -> dict:
    """Everything the matrices draw, in one pass over the patches:
    rows       patch index rows, oldest first
    cells      {row key: {pid: {tag: n}}}
    parts      {row key: {pid: {part: {tag: n}}}}           (heroes: stats / weapon / abil)
    samples    {row key: {pid: [[what, field, old, new, tag, part, hidden], ...]}}
    hidden     {row key: {pid: n}}                          (not in the notes: render.not_in_notes)"""
    from . import archive
    from .render import not_in_notes
    from .cards import disambiguate, player_facing
    rows = list(archive.by_date())
    ents = load_json('entities.json')['entities']
    # an NPC's own abilities count on its row (Walker's Stomp), as they do on its page
    npc = {e['id']: e['units'] for e in ents if e.get('units')}
    # a unit counts on its family's row; the same change on several members (five Gutter Ghouls, four
    # Walkers) counts once (unit_families)
    from .unit_families import main_of
    fam = main_of([e for e in ents if e['file'] == 'npc_units.vdata' and not e.get('template')])
    cells: dict = {}
    parts: dict = {}
    raw: dict = {}
    hidden: dict = {}
    weighed: dict = {}         # {row key: {pid: [rows]}}: the cell's net mark (weights.net_of)
    once: set = set()
    from .game_systems import (convar_changes, convar_start, is_template, name_of, place, place_all_row, place_entity, system)
    from .shared_rows import FOLD_FILES, entities as spread_all, own
    cat = {f"{e['file']}:{e['id']}": e for e in ents}
    start = convar_start()       # the console variables' first build: a snapshot, not changes (game_systems)
    for r in rows:
        p = archive.patch(r['id'])
        found: list[tuple[list[str], str, str, list[dict], str]] = []     # (row keys, part, what, rows, ability id)
        spread = spread_all(archive.gameplay(r['id']))
        # a template's change an heir shows is the heir's (game_pages.template_rows)
        heirs = {(e['file'], c.get('path'), str(c.get('old_s')), str(c.get('new_s')))
                 for e in spread if not is_template(e) for c in e['changes']}
        # a change one edit made in some heroes counts in each one's cell; a rule for every hero (the level
        # curve) in none of theirs — it would fill a whole column (shared_rows) — but in its Game system's
        for e in spread:
            e = {**e, 'changes': own(e['changes'])}
            if not e['changes']:
                continue
            info = {**e, **cat.get(e['key'], {})}
            game = place_entity(e['key'], info)
            if game:                                 # not a hero, item or unit: its Game system's row
                ch = e['changes']
                if is_template(info):
                    ch = [c for c in ch if (e['file'], c.get('path'), str(c.get('old_s')), str(c.get('new_s')))
                          not in heirs]
                if ch:
                    found.append(([f'game:{game[0]}'], game[1], name_of(e['key'], info), ch, ''))
                continue
            # an ability removed in this patch carries no owner or kind in its record; the catalog still has them, and
            # its hero's page lists its DEL rows (Holliday 2026-09-29: the band read 7 DEL, the matrix cell 1 — the
            # band and the cell weighed different rows; review 2026-10-05)
            e = {**e, 'owner': e.get('owner') or info.get('owner'), 'kind': e.get('kind') or info.get('kind')}
            if e['file'] == 'heroes.vdata':
                keys = [f'hero:{e["id"]}']
            elif e.get('owner'):
                keys = [f'hero:{e["owner"]}']
            elif e.get('kind') == 'item':
                keys = [f'item:{e["id"]}']
            elif e['file'] == 'npc_units.vdata':
                keys = [f'unit:{fam.get(e["id"], e["id"])}']
            elif e['file'] == 'abilities.vdata' and e['id'] in npc:
                keys = list(dict.fromkeys(f'unit:{fam.get(u, u)}' for u in npc[e['id']]))
            else:
                continue
            found.append((keys, part_of(e), _display(e), e['changes'], e['file'] == 'abilities.vdata' and e['id']))
        rules: dict[tuple[str, str], list[dict]] = {}
        for e in archive.gameplay(r['id']):       # the rules for every hero / ability, once
            if e.get('id') == '@shared' and e.get('scope') == 'all' and e['file'] in FOLD_FILES:
                for c in e['changes']:
                    rules.setdefault(place_all_row(e['file'], c), []).append(c)
        # one list per part, as the system page reads them: a whole level added is one change (combine_levels),
        # not three — the level curve read 38 in the matrix and 34 on its band (review 2026-10-05)
        for (sid, pid), cs in rules.items():
            found.append(([f'game:{sid}'], pid, next(x.name for x in system(sid).parts if x.id == pid), cs, ''))
        cvs = p.get('extras', {}).get('convars') or []
        for c in convar_changes(cvs, start):
            sid, pid = place(f'convar:{c["id"]}')
            found.append(([f'game:{sid}'], pid, 'Console variables', [c], ''))
        for keys, part, what, changes, abil in found:
            for key in keys:
                cell = cells.setdefault(key, {}).setdefault(r['id'], {})
                pcell = parts.setdefault(key, {}).setdefault(r['id'], {}).setdefault(part, {})
                # two fields under one label say which is which, as on the entity's page ("Incoming Healing · receive"
                # / "· regen": Healbane's card listed "Incoming Healing" twice; review 2026-10-05)
                for c in disambiguate(player_facing(changes)):
                    # the same change on several members of a family counts once; so does one edit spread over a
                    # system's entries — the Breakables tile read 138 for 2026-09-29 where its band read 52 and
                    # the home icon 50 (review 2026-10-05; the same signature as home_page.update_feed)
                    if key.startswith(('unit:', 'game:')):
                        sig = (key, r['id'], abil if key.startswith('unit:') else '', c.get('label'), c.get('old_s'),
                               c.get('new_s'))
                        if sig in once:
                            continue
                        once.add(sig)
                    t = tag_of(c)[0]
                    for d in (cell, pcell):
                        d[t] = d.get(t, 0) + 1
                    weighed.setdefault(key, {}).setdefault(r['id'], []).append(c)
                    hid = int(bool(not_in_notes(c)))
                    if hid:
                        hidden.setdefault(key, {})[r['id']] = hidden.get(key, {}).get(r['id'], 0) + 1
                    s = (what, c.get('label') or '', *_sample_values(c),
                         t, part, abs(c['pct']) if isinstance(c.get('pct'), (int, float)) else 0, hid)
                    raw.setdefault(key, {}).setdefault(r['id'], []).append(s)
    samples: dict = {}
    for k, per in raw.items():
        for pid, lst in per.items():
            ranked = sorted(lst, key=lambda x: (-x[6], TAG_ORDER.get(x[4], 9)))
            picked, seen = [], {}
            limit = SAMPLES if k.startswith('hero:') else SAMPLES_ONE
            for x in ranked:                      # the biggest per part, the parts in their order
                if seen.get(x[5], 0) < limit:
                    seen[x[5]] = seen.get(x[5], 0) + 1
                    picked.append([*x[:6], x[7]])
            # a cell whose card says "N not in patch notes" shows one of them (review 2026-10-05: the biggest by %
            # were all in the notes)
            if picked and not any(x[6] for x in picked):
                first = next((x for x in ranked if x[7]), None)
                if first is not None:
                    picked[-1] = [*first[:6], first[7]]
            order = {p: i for i, (p, _) in enumerate(PARTS)}
            samples.setdefault(k, {})[pid] = sorted(picked, key=lambda x: order.get(x[5], 9))
    # the cell's net weighs what the row's page band counts (weights.weighed_rows: no rule for all, no work before
    # release — every hero on a matrix is released or pre-release, so its page counts released rows only)
    nets = {k: {pid: net_of(cs) for pid, cs in per.items()} for k, per in weighed.items()}
    return {'rows': rows, 'cells': cells, 'parts': parts, 'samples': samples, 'hidden': hidden, 'nets': nets}


def _net(counts: dict[str, int]) -> str:
    good = counts.get('buff', 0) + counts.get('new', 0) + counts.get('on', 0)
    bad = counts.get('nerf', 0) + counts.get('del', 0) + counts.get('off', 0)
    return 'net-buff' if good > bad else 'net-nerf' if bad > good else 'net-mix'


STRIPE_MIN = 0.12        # a stripe never thinner than this share of the tile (one buff among 30 rows)
STRIPE_COLOUR = {'up': 'changed', 'down': 'changed'}


def stripes(counts: dict[str, int]) -> str:
    """The tile's stripes as ONE gradient (scripts.js draws the same after a filter): a span per tag cost
    ~10k nodes on the item matrix (2026-10-03)."""
    tags = sorted((t for t in counts if counts[t]), key=lambda t: TAG_ORDER.get(t, 9))
    if not tags:
        return ''
    total = sum(counts[t] for t in tags)
    shares = [max(counts[t] / total, STRIPE_MIN) for t in tags]
    norm = sum(shares)
    stops, acc = [], 0.0
    for t, s in zip(tags, shares):
        a, acc = acc, acc + s / norm * 100
        stops.append(f'var(--tag-{STRIPE_COLOUR.get(t, t)}) {a:.3g}% {acc:.3g}%')
    return f'linear-gradient({",".join(stops)})'


def _cell(counts: dict[str, int], href: str, k: int | None, old: bool, hidden: int = 0,
          mark: str | None = None) -> str:
    """A tile of one colour is a class (`.dsq.s-<tag>`), not an inline gradient: 78% of the item matrix's
    tiles, ~95 KB of style attributes and a gradient to paint each (perf track 2026-10-05). scripts.js
    redraws a filtered tile with the inline gradient and its own classes."""
    data_k = f' data-k="{k}"' if k is not None else ''
    tags = [t for t in counts if counts[t]]
    # the eye in the corner, as on a strip tile, when the notes left something of it out (review 2026-10-05: the
    # matrices were the one view without it)
    hid = ' hid' if hidden else ''
    # "Buff vs nerf" by the weighed sum (weights.net_of: '' — no row takes a side — is the mix colour), not a majority
    # of rows; `mark` None: no rows to weigh (a test's counts only)
    net = _net(counts) if mark is None else f'net-{mark or "mix"}'
    if len(tags) == 1:
        look = f'dsq {net}{hid} s-{STRIPE_COLOUR.get(tags[0], tags[0])}"'
    else:
        look = f'dsq {net}{hid}" style="background:{stripes(counts)}"'
    return (f'<td{" class=old" if old else ""}><a class="{look} href="{esc(href)}"{data_k}>'
            f'<span class="dn">{sum(counts.values())}</span></a></td>')


def _gap(n: int, old: bool) -> str:
    """A run of empty patch cells is ONE cell (the column lines are its background): the item matrix had
    29k cells, 27k of them empty (2026-10-03). A run never crosses into the old columns, which hide."""
    span = f' colspan={n}' if n > 1 else ''
    cls = ' class=old' if old else ''
    return f'<td{cls}{span}></td>'


def _head(rows: list[dict], cutoff: str, label: str) -> str:
    months: list[tuple[str, int, bool]] = []
    for r in rows:
        m, old = r['date'][:7], r['date'] < cutoff
        if months and months[-1][0] == m:
            months[-1] = (m, months[-1][1] + 1, months[-1][2] and old)
        else:
            months.append((m, 1, old))
    top = ''.join(f'<th class="dm{" old" if old else ""}" colspan="{n}">{esc(m)}</th>' for m, n, old in months)
    sub = ''.join(f'<th class="dd{" old" if r["date"] < cutoff else ""}{" named" if patch_name(r["title"]) else ""}">'
                  f'<a href="../patches/{esc(r["id"])}.html" data-tooltip="{esc(patch_title_text(r))}">{esc(r["date"][8:])}</a></th>'
                  for r in rows)
    # fixed layout takes the widths from these: the name, then 30px per patch (0 for an old one while
    # the old patches are hidden) — the automatic layout of ~5k cells with colspans took 0.5 s per toggle
    cols = '<col class="nm">' + ''.join('<col class="old">' if r['date'] < cutoff else '<col>' for r in rows)
    return (f'<colgroup>{cols}</colgroup><thead><tr class="cats"><th class="name"></th>{top}</tr>'
            f'<tr class="cols"><th class="name">{esc(label)}</th>{sub}</tr></thead>')


def matrix_html(entries: list[tuple[str, str, str | None, str, str]], kind: str) -> str:
    """entries: (row key, display name, icon url, page href, extra row class)."""
    d = _collect()
    rows, cells, parts, samples, hidden = d['rows'], d['cells'], d['parts'], d['samples'], d['hidden']
    nets = d.get('nets', {})
    cutoff = (date.fromisoformat(rows[-1]['date'][:10]) - timedelta(days=OLD_DAYS)).isoformat() if rows else ''
    pidx = {r['id']: i for i, r in enumerate(rows)}
    tips: list = []
    body: list[str] = []

    def tds(key: str, mine: dict, href: str, part_of_cell: dict | None) -> str:
        out, run, run_old = [], 0, True
        for r in rows:
            counts = mine.get(r['id'])
            old = r['date'] < cutoff
            if run and (counts or old != run_old):
                out.append(_gap(run, run_old))
                run = 0
            if not counts:
                run, run_old = run + 1, old
                continue
            n_hid = hidden.get(key, {}).get(r['id'], 0)
            mark = nets[key].get(r['id']) if key in nets else None
            # [patch, counts, samples, {part: {tag: n}} for the hero filter or None, not in the notes,
            #  net mark 'buff' / 'nerf' / 'mix' / '' (weights.net_of; scripts.js reads it, never re-weighs)]
            entry = [pidx[r['id']], counts, samples.get(key, {}).get(r['id'], []),
                     part_of_cell.get(r['id'], {}) if part_of_cell is not None else None, n_hid, mark]
            tips.append(entry)
            # the row's own page at that patch (patch pages are off the bar since 2026-10-03)
            out.append(_cell(counts, f'{href}#p-{r["id"]}', len(tips) - 1, old, n_hid, mark))
        if run:
            out.append(_gap(run, run_old))
        return ''.join(out)

    for key, name, ic, href, extra, *more in entries:
        mine = cells.get(key, {})
        if not mine:
            continue
        attrs = ''.join(f' {k}="{esc(v)}"' for k, v in (more[0] if more else {}).items() if v)
        # a Game system without art from the game files has the site's glyph ('glyph:<name>', game_systems)
        img = (visual(None, ic[6:], 'mx-g') if ic and ic.startswith('glyph:') else
               f'<img src="{esc(ic)}" alt="" loading="lazy">' if ic else '')
        ic = '' if ic and ic.startswith('glyph:') else ic
        body.append(f'<tr class="{esc(extra)}"{attrs} data-search="{esc(name.lower())}" data-name="{esc(name)}" '
                    f'data-icon="{esc(ic or "")}"><td class="name"><a href="{esc(href)}">{img}{esc(name)}</a></td>'
                    f'{tds(key, mine, href, parts.get(key, {}) if kind == "hero" else None)}</tr>')
    data = {'patches': [[r['date'][:10], patch_title_text(r), bool(patch_name(r['title']))] for r in rows],
            'cells': tips, 'words': TAG_WORDS, 'word1': TAG_WORD_ONE,
            'parts': dict(PARTS), 'eye': EYE_MARK, 'nets': NET_WORDS}
    # JSON inside a script element: "</" would end it early
    blob = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    n_old = sum(1 for r in rows if r['date'] < cutoff)
    # a Game system's hover card names the entry of each change (scripts.js dyn-tip)
    what = ' data-what' if kind == 'game' else ''
    return (f'<div class="table-fade"><div class="table-scroll"><table class="dyn" id="dyn-{kind}"{what} '
            f'style="--n-all:{len(rows)};--n-new:{len(rows) - n_old}">{_head(rows, cutoff, kind.title())}'
            f'<tbody>{"".join(body)}</tbody></table></div></div>'
            f'<script type="application/json" class="dyn-data" data-for="dyn-{kind}">{blob}</script>')


def toolbar(kind: str, n_hidden_rows: int, hidden_label: str, roles: tuple[str, ...] = ()) -> str:
    target = f'#dyn-{kind}'
    # a tag chip SELECTS (only these tags), the same as on a hero / item / unit page (advisor 10-03: here
    # "on" used to hide the tag)
    # selected = aria-pressed, never the class "on" (that is the ON tag's colour: a chosen NERF turned green)
    tags = ''.join(tag_badge(t, t.upper(), 'button', f' data-dyn-tag="{t}" data-target="{target}" aria-pressed="false"')
                   for t in ('buff', 'nerf', 'new', 'del', 'rework', 'mech', 'up', 'down'))
    rows_switch = (f'<label class="switch"><input type="checkbox" data-toggle-class="show-extra" data-target="{target}">'
                   f'<span class="track"></span>{esc(hidden_label)} <span class="n">{n_hidden_rows}</span></label>'
                   if n_hidden_rows else '')
    # which part of a hero the tiles show: everything, or only its stats / weapon / abilities
    parts_filter = ''
    if kind == 'item':
        # the shop's slots and tiers as filters (Item Stats has them; the matrix had none): one choice per group,
        # pressed again to clear (scripts.js dyn-rows); Tier V too — 23 of the matrix's rows are tier 5
        parts_filter = ('<span class="sep"></span><span class="dyn-rows" data-target="' + target + '">' + ''.join(
            f'<button class="px-btn" data-rowf="cat" data-v="{c}" aria-pressed="false">{esc(lbl)}</button>'
            for _, c, lbl in ITEM_SLOTS) + '<span class="sep"></span>' + ''.join(
            f'<button class="px-btn" data-rowf="tier" data-v="{t}" aria-pressed="false">{"I II III IV V".split()[i]}</button>'
            for i, t in enumerate(ITEM_TIERS)) + '</span>')
    elif kind == 'hero' and roles:
        parts_filter = ('<span class="sep"></span><span class="dyn-rows" data-target="' + target + '">' + ''.join(
            f'<button class="px-btn" data-rowf="role" data-v="{esc(r.lower())}" aria-pressed="false">{esc(r)}</button>'
            for r in roles) + '</span>')
    if kind == 'hero':
        parts_filter = ('<span class="sep"></span><span class="dyn-parts">' + ''.join(
            f'<button class="px-btn{" on" if p == "all" else ""}" data-part="{p}" data-target="{target}" aria-pressed="{"true" if p == "all" else "false"}">{esc(lbl)}</button>'
            for p, lbl in (('all', 'All'),) + PARTS) + '</span>' + parts_filter)
    return (f'<div class="toolbar dyn-bar"><input type="search" placeholder="Search…" data-search-target="{target} tbody tr">'
            f'<span class="sep"></span>'
            f'<label class="switch"><input type="checkbox" data-toggle-class="show-old" data-target="{target}">'
            f'<span class="track"></span>Older patches</label>'
            f'<label class="switch"><input type="checkbox" data-toggle-class="bvn" data-target="{target}">'
            f'<span class="track"></span>Buff vs nerf</label>{rows_switch}{parts_filter}'
            f'<span class="sep"></span><span class="dyn-tags">{tags}</span></div>')


def hero_entries(heroes: list[dict], rel: str, trow: dict | None = None) -> list[tuple]:
    """A row per hero; its role (Hero Stats' `type`, e.g. "…_Brawler") rides on the row for the role filter. A hero
    the files give no role yet (Baba, Violet, Nurse Harrow… in development) is "*", which no role filter takes out
    (scripts.js dyn-rows; they all dropped out under any role, review 2026-10-05)."""
    from .common import slug
    out = []
    for h in sorted(heroes, key=lambda h: display_name(h).lower()):
        pre = h.get('state') != 'EHeroDevState_Release'
        role = str(((trow or {}).get(h['id']) or {}).get('type') or '').rsplit('_', 1)[-1].lower()
        # the page is heroes/atlas.html, not hero_atlas.html (every name link was a 404)
        out.append((f'hero:{h["id"]}', display_name(h), hero_icon(h['id'], rel),
                    slug(h['file'], h['id']).split('/', 1)[1], 'extra' if pre else '',
                    {'data-role': role or '*'}))
    return out


def unit_entries(units: list[dict], groups: tuple[tuple[str, str], ...], rel: str) -> list[tuple]:
    """A row per unit FAMILY (unit_families: Slum Shroom I-III, the four Walkers) in the order of the Units
    index (buildings, troopers, neutrals, others); removed ones and helpers hide."""
    from .common import slug
    from .unit_families import families, is_named
    order = {k: i for i, (k, _) in enumerate(groups)}
    out = []
    fams = sorted(families(units).items(),
                  key=lambda kv: (order.get(kv[1][0].get('kind'), len(order)), kv[0].lower()))
    for name, members in fams:
        u = members[0]
        # removed, Hideout / bots / effects, or unnamed (the code's own spawns)
        hidden = not u.get('alive') or u.get('kind') == 'helper' or not is_named(u)
        out.append((f'unit:{u["id"]}', name, entity_icon(u['file'], u['id'], u.get('kind') or 'unit', rel),
                    slug(u['file'], u['id']).split('/', 1)[1], 'extra' if hidden else ''))
    return out


def game_entries(rel: str) -> list[tuple]:
    """A row per Game system (game_systems), in the config's order."""
    from .game_systems import shown
    return [(f'game:{s.id}', s.name, s.icon if s.icon.startswith('glyph:') else f'{rel}icons/{s.icon}', s.href, '')
            for s in shown()]


ITEM_SLOTS = (('WeaponMod', 'w', 'Weapon'), ('Armor', 'v', 'Vitality'), ('Tech', 's', 'Spirit'))
ITEM_TIERS = ('1', '2', '3', '4', '5')


def _item_slot_tier(it: dict) -> tuple[str, str]:
    """('w' / 'v' / 's' / '', '1'-'5' / '') of a catalog item: its raw enums ('EItemSlotType_WeaponMod',
    'EModTier_3') as the shop's slot letters and tier digits."""
    slot = str(it.get('slot') or '').removeprefix('EItemSlotType_')
    cat = next((c for raw, c, _ in ITEM_SLOTS if raw == slot), '')
    m = re.search(r'(\d)$', str(it.get('tier') or ''))
    return cat, m.group(1) if m else ''


def item_entries(items: list[dict], cards: dict, rel: str) -> list[tuple]:
    """A row per item in the shop's order — Weapon, Vitality, Spirit, then tier and name (it was alphabetical over 238
    rows; review 2026-10-05) — each carrying its slot and tier for the toolbar's filters (`data-cat`, `data-tier`)."""
    from .common import slug
    order = {c: i for i, (_, c, _) in enumerate(ITEM_SLOTS)}
    out = []
    for it in sorted(items, key=lambda e: (order.get(_item_slot_tier(e)[0], 9), _item_slot_tier(e)[1] or '9',
                                           (e.get('name') or e['id']).lower())):
        info = (cards.get(it['id']) or {}).get('item') or {}
        gone = not it.get('alive') or it.get('disabled') or info.get('disabled')
        name = display_name(it)
        cat, tier = _item_slot_tier(it)
        out.append((f'item:{it["id"]}', name, entity_icon(it['file'], it['id'], 'item', rel),
                    slug(it['file'], it['id']).split('/', 1)[1], 'extra' if gone else '',
                    {'data-cat': cat, 'data-tier': tier}))
    return out
