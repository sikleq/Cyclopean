"""Home page: the four sections (Heroes, Items, Units, Game) and what the last updates changed on each of them —
a strip of icons per update, each opening that hero's, item's, unit's or Game system's history at that update. The
site is about the entities, not the patch notes (owner, 2026-10-03: "closer to Sloppy")."""
from __future__ import annotations

from .common import (EYE_MARK, display_name, entity_icon, esc, glyph_for, hero_icon, load_json, mark, page,
                     patch_name, patch_title_html, plural, pretty_id, slug, visual, write)
from . import archive
from .site_search import search_box
from .weights import NET_WORDS, net_of

LATEST_UPDATES = 4        # updates with gameplay changes in the "what changed" feed
SECTIONS = (('heroes', 'Heroes'), ('items', 'Items'), ('units', 'Units'), ('game', 'Game'))
CHIP_SAMPLES = 2          # a feed icon's hover card lists this many of its biggest changes (217 icons on the page)
PHONE_ICONS = 18          # icons a phone shows per section of an update (styles.css .lu:nth-child(n+19))


def page_of(e: dict, templates: frozenset[str] = frozenset(), unit_main: dict[str, str] | None = None
            ) -> tuple[str, str] | None:
    """The page a patch entity's changes live on: (entity key, section). A hero's abilities and gun are the
    hero's; the Hideout's toys, the bots and effects, templates ('trooper_base') and changes shared by
    many ('@shared') have no page here."""
    file, eid, owner = e['file'], e['id'], e.get('owner') or ''
    if eid.startswith('@') or f'{file}:{eid}' in templates:
        return None
    if file == 'heroes.vdata':
        return f'heroes.vdata:{eid}', 'heroes'
    if file == 'abilities.vdata':
        if eid.startswith('upgrade_'):
            return f'abilities.vdata:{eid}', 'items'
        if owner.startswith('hero_'):
            return f'heroes.vdata:{owner}', 'heroes'
        return None
    named = (e.get('name') and e['name'] != eid) or e.get('kind') == 'building'     # unit_families.is_named
    if file == 'npc_units.vdata' and e.get('kind') != 'helper' and named:
        # a unit's page is its family's (unit_families: the five Gutter Ghouls I are one page)
        return f'npc_units.vdata:{(unit_main or {}).get(eid, eid)}', 'units'
    return None


def page_route(key: str, info: dict, pages: frozenset[str] | set[str], unit_main: dict[str, str] | None
               ) -> tuple[str, str] | None:
    """The page an entity's rows are on, by THE pages (patch_counts.page_set, entities_pages.page_keys) and the
    catalog — not by the patch record: (page key, section). A hero's abilities and guns are the hero's, an item its
    own, a unit (a helper too) its family's, an ability a unit binds that unit's family's. The record's name decided
    before, so Medic Trooper and Neutral bug (name == id in the record) fell off the home page while their pages
    showed the rows (review 2026-10-05: "Respawn Time 30s → 15s" was build 6736's biggest change)."""
    if key not in pages:
        return None
    file, _, eid = key.partition(':')
    main = unit_main or {}
    if file == 'heroes.vdata':
        return key, 'heroes'
    if file == 'abilities.vdata':
        owner = info.get('owner') or ''
        if owner.startswith('hero_') and f'heroes.vdata:{owner}' in pages:
            return f'heroes.vdata:{owner}', 'heroes'
        if eid.startswith('upgrade_'):
            return key, 'items'
        for u in info.get('units') or ():
            if f'npc_units.vdata:{u}' in pages:
                return f'npc_units.vdata:{main.get(u, u)}', 'units'
        return None
    if file == 'npc_units.vdata':
        return f'npc_units.vdata:{main.get(eid, eid)}', 'units'
    return None


def _feed_rows(p: dict, templates: frozenset[str], unit_main: dict[str, str] | None,
               pages: frozenset[str] | None = None):
    """(entity, its rows, page key, section) of one patch: a hero / item / unit page's (`page_route` by `pages`;
    without them the record's `page_of`), else the Game system's (game_systems: map objects, rules, effects,
    abilities no hero owns, a template's change no heir shows, a rule for every hero or ability — once —, console
    variables). Key of a Game row: 'game:<system>'."""
    from .cards import gameplay_entities
    from .game_systems import (convar_changes, convar_start, is_template, name_of, part_name, place, place_all_row,
                               place_entity)
    from .shared_rows import FOLD_FILES, catalog, entities as spread_all, own
    cat = catalog()
    spread = spread_all(gameplay_entities(p['entities']))
    heirs = {(e['file'], c.get('path'), str(c.get('old_s')), str(c.get('new_s')))
             for e in spread if not is_template(e) for c in e['changes']}
    for e in spread:
        rows = own(e['changes'])
        info = {**e, **cat.get(e['key'], {})}
        where = page_of(e, templates, unit_main) if pages is None else page_route(e['key'], info, pages, unit_main)
        if where:
            yield e, rows, where[0], where[1]
            continue
        hit = place_entity(e['key'], info)
        if not hit:
            continue
        if is_template(info):
            rows = [c for c in rows if (e['file'], c.get('path'), str(c.get('old_s')), str(c.get('new_s'))) not in heirs]
        yield {**e, 'what': name_of(e['key'], info)}, rows, f'game:{hit[0]}', 'game'
    rules: dict[tuple[str, str], tuple[dict, list[dict]]] = {}
    for e in gameplay_entities(p['entities']):
        if e.get('id') == '@shared' and e.get('scope') == 'all' and e['file'] in FOLD_FILES:
            for c in e['changes']:
                rules.setdefault(place_all_row(e['file'], c), (e, []))[1].append(c)
    # one list per part, as the system page reads it (a whole level added is one change: combine_levels)
    for (sid, pid), (e, cs) in rules.items():
        yield {**e, 'what': part_name(sid, pid)}, cs, f'game:{sid}', 'game'
    for c in convar_changes(p.get('extras', {}).get('convars') or [], convar_start()):
        yield {'file': 'convars', 'id': c['id'], 'what': c['id']}, [c], f'game:{place("convar:" + c["id"])[0]}', 'game'


def update_feed(p: dict, templates: frozenset[str] = frozenset(), unit_main: dict[str, str] | None = None,
                pages: frozenset[str] | None = None) -> dict[str, dict[str, dict]]:
    """section -> page key -> {n, hidden, buff, nerf, kind, rows}: what one update did to each page (rows:
    (what, change) for the icon's hover card).
    Counts are the player-facing rows (cards.player_facing) a page shows; work on unreleased heroes
    waits for their release. A change one edit made in some heroes counts on each of them; a rule for every hero
    (the level curve) on none of the hero icons — it is no one's own change (shared_rows) — but once on its Game
    system's icon (section 'game': the Soul Urn's rework of 2026-06-04 was on no icon, so the feed skipped it)."""
    from .cards import player_facing
    from .dynamics_page import _display
    from .render import not_in_notes
    out: dict[str, dict[str, dict]] = {}
    once: set = set()
    for e, rows, key, section in _feed_rows(p, templates, unit_main, pages):
        rows = [c for c in player_facing(rows) if c.get('status') != 'unreleased']
        if not rows:
            continue
        # the same change on several members of a family counts once; so does one edit spread over a system's
        # entries (twelve breakable props)
        if section in ('units', 'game'):
            rows = [c for c in rows if (key, c.get('label'), c.get('old_s'), c.get('new_s')) not in once]
            once |= {(key, c.get('label'), c.get('old_s'), c.get('new_s')) for c in rows}
            if not rows:
                continue
        slot = out.setdefault(section, {}).setdefault(key, {'n': 0, 'hidden': 0, 'buff': 0, 'nerf': 0,
                                                             'kind': e.get('kind'), 'rows': []})
        # what each row is about on its page: a hero's ability or gun by name, a Game entry by its name, an item's /
        # unit's own rows bare
        what = _display(e) if section == 'heroes' else e.get('what', '') if section == 'game' else ''
        slot['rows'] += [(what, c) for c in rows]
        slot['n'] += len(rows)
        slot['hidden'] += sum(1 for c in rows if not_in_notes(c))
        slot['buff'] += sum(1 for c in rows if c.get('dir') == 'buff')
        slot['nerf'] += sum(1 for c in rows if c.get('dir') == 'nerf')
    return out


def _chip(key: str, s: dict, pid: str, names: dict[str, str], named: bool = False, k: int | None = None,
          eye: bool = True, net: str | None = None) -> str:
    """`names`: entity key -> its name today (common.display_name: never an id). `named`: the name under
    the icon (the newest update; advisor round 4: names were in tooltips only). `k`: the icon's entry in the
    feed's hover-card data (chip_card) — the card replaces the one-line tooltip. `eye`: False when the group's
    label carries the one eye (every icon of it all out of the notes). `net`: the icon's net mark (weights.net_of
    of its rows, as `_feed` gives its card); None weighs them here."""
    file, _, eid = key.partition(':')
    if file == 'game':                 # a Game system (game_systems): its icon from the game files or a site glyph
        from .game_systems import SECTION, icon_html, system
        sys_ = system(eid)
        name, href, pic = sys_.name, f'{SECTION}/{sys_.href}', icon_html(sys_, '')
    else:
        name = names.get(key) or pretty_id(eid)
        ic = hero_icon(eid, '') if file == 'heroes.vdata' else entity_icon(file, eid, s.get('kind') or '', '', name)
        href, pic = slug(file, eid), visual(ic, glyph_for(file, eid))
    # the icon's underline: what the update did to the page on balance, weighed as everywhere (weights.net_of)
    if net is None:
        net = net_of(c for _, c in s['rows'])
    tip = f'{name}: {plural(s["n"], "change")}' + (f', {s["hidden"]} not in patch notes' if s['hidden'] else '')
    # with a card the eye says nothing of its own (its tooltip stacked on the card)
    eye_mark = mark('hidden') if k is None else EYE_MARK
    eye = f'<span class="lu-eye">{eye_mark}</span>' if s['hidden'] and eye else ''
    label = f'<span class="lu-nm">{esc(name)}</span>' if named else ''
    hover = (f'aria-label="{esc(tip)}" data-name="{esc(name)}" data-k="{k}"' if k is not None
             else f'data-tooltip="{esc(tip)}"')
    game = ' lu-game' if file == 'game' else ''
    return (f'<a class="lu net-{net or "mix"}{game}" href="{esc(href)}#p-{esc(pid)}" {hover}>'
            f'{pic}<span class="lu-n">{s["n"]}</span>{eye}{label}</a>')


def chip_card(s: dict) -> list:
    """[{tag: n}, hidden, samples] for a feed icon's hover card: its CHIP_SAMPLES biggest changes as
    [what (a hero's ability; '' for an item's / unit's own rows), label, old, new, tag, hidden 0/1]."""
    from .history_view import _rank
    from .render import not_in_notes, tag_of, vals_text
    counts: dict[str, int] = {}
    for _, c in s['rows']:
        counts[tag_of(c)[0]] = counts.get(tag_of(c)[0], 0) + 1
    ordered = sorted(s['rows'], key=lambda wc: _rank(wc[1]))
    top = ordered[:CHIP_SAMPLES]
    # one slot is the eye's when the card counts some not in the notes (review 2026-10-05)
    if s['hidden'] and top and not any(not_in_notes(c) for _, c in top):
        top[-1] = next(wc for wc in ordered if not_in_notes(wc[1]))
    return [counts, s['hidden'], [[w, str(c.get('label') or ''), *vals_text(c), tag_of(c)[0],
                                   int(not_in_notes(c))] for w, c in top]]


def _feed(patches: list[dict], names: dict[str, str], templates: frozenset[str], unit_main: dict[str, str],
          pages: frozenset[str] | None = None) -> str:
    """The latest updates' icons + ONE JSON blob of their hover cards (scripts.js dyn-tip, parsed on the first
    hover; owner 2026-10-04: "Graves: 17 changes" said nothing about what changed). `pages`: THE pages
    (patch_counts.page_set), so the icons route rows where the pages and the update's count put them."""
    import json
    from .common import patch_title_text
    from .patch_counts import for_id, off_pages
    from .render import TAG_WORD_ONE, TAG_WORDS
    blocks, updates, cards = [], [], []
    for row in reversed(patches):
        if len(blocks) == LATEST_UPDATES:
            break
        feed = update_feed(archive.patch(row['id']), templates, unit_main, pages)
        if not feed:
            continue
        updates.append([patch_title_text(row), bool(patch_name(row['title']))])
        groups = []
        for sec, title in SECTIONS:
            got = sorted(feed.get(sec, {}).items(), key=lambda kv: (-kv[1]['n'], kv[0]))
            if got:
                named = not blocks
                # every icon of the group all out of the notes: ONE eye on the group's label, none on the icons,
                # as one eye on an all-hidden band (review 2026-10-05: 171 of 246 icons had it, it marked nothing)
                # (an update with no notes at all says so once, on its banner: no eye anywhere below)
                notes = row.get('has_notes', True)
                all_out = notes and all(s['hidden'] == s['n'] for _, s in got)
                chips = []
                for k, s in got:
                    net = net_of(c for _, c in s['rows'])              # once: the icon's underline and its card
                    chips.append(_chip(k, s, row['id'], names, named, len(cards), eye=notes and not all_out, net=net))
                    # [update, {tag: n}, hidden, samples, net mark (weights.net_of) for the card's chip]
                    cards.append([len(updates) - 1, *chip_card(s), net])
                whole = f'<span class="lu-all">{EYE_MARK}all not in notes</span>' if all_out else ''
                # a phone shows three rows of icons (styles.css); the rest is the patch page's (City Never Sleeps'
                # 102 items were 17 rows, ~900px)
                more = (f'<a class="lu-more" href="patches/{esc(row["id"])}.html#changes">+{len(got) - PHONE_ICONS} '
                        f'more</a>' if len(got) > PHONE_ICONS and not named else '')
                groups.append(f'<div class="lu-group"><span class="lu-h">{title} <b>{len(got)}</b>{whole}</span>'
                              f'<div class="lu-row{" named" if named else ""}">{"".join(chips)}{more}</div></div>')
        # the update's one count (patch_counts: as its patch page and the patch list); what no icon below carries is
        # named apart — the game's rules and map objects only the patch page lists
        pc = for_id(row['id'])
        eye = ''
        if pc['not_in_notes']:
            # a way in: the patch page with its "Not in patch notes" filter pressed (scripts.js hidden-hash)
            # an update Valve posted no notes for says so, as its bands do (Rat King's build 6736: nothing was "left
            # out" of notes that do not exist)
            what = 'not in patch notes' if row.get('has_notes', True) else '· no patch notes'
            eye = (f'<a class="au au-hidden" href="patches/{esc(row["id"])}.html#hidden">{mark("hidden")}'
                   f'<b>{pc["not_in_notes"]}</b> {what}</a>')
            if off_pages(pc):
                # they have pages now: the Game section's — its change matrix shows this update's column per system
                # (the Game index said nothing about the update)
                eye += (f'<a class="au au-off" href="game/changes.html"><b>{off_pages(pc)}</b> of them in game rules '
                        f'&amp; map objects</a>')
        blocks.append(f'<section class="update px-frame"><div class="banner{" named" if patch_name(row["title"]) else ""}">'
                      f'<span class="bt"><a href="patches/{esc(row["id"])}.html">{patch_title_html(row)}</a></span>'
                      f'<span class="bc">{eye}</span></div>{"".join(groups)}</section>')
    # the counters' icons are CSS (`.pip.<tag>`), the eye a mark
    data = {'u': updates, 'c': cards, 'words': TAG_WORDS, 'word1': TAG_WORD_ONE, 'eye': EYE_MARK, 'nets': NET_WORDS}
    # JSON inside a script element: "</" would end it early
    blob = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    return ''.join(blocks) + f'<script type="application/json" class="feed-data">{blob}</script>'


def _tiles(counts: dict[str, int], faces: list[str], units: list[str], items: list[str] = ()) -> str:
    """The four sections as big tiles (Sloppy's landing tiles, without blurbs). Game: its systems' icons that come
    from the game files (the site glyphs stay on its own pages). Items: shop icons (the shop's tab glyphs when
    none are known)."""
    from .game_systems import icon_url, shown
    game_art = [u for u in (icon_url(s, '') for s in shown()) if u]
    item_art = (''.join(f'<img class="px" src="{esc(u)}" alt="" loading="lazy">' for u in items[:6]) if items else
                '<img src="icons/shop/tab_weapon.webp" alt=""><img src="icons/shop/tab_spirit.webp" alt="">'
                '<img src="icons/shop/tab_vitality.webp" alt="">')
    art = {'heroes': ''.join(f'<img class="px" src="{esc(f)}" alt="" loading="lazy">' for f in faces[:6]),
           'items': item_art,
           'units': ''.join(f'<img class="px" src="{esc(u)}" alt="" loading="lazy">' for u in units[:6]),
           'game': ''.join(f'<img src="{esc(u)}" alt="" loading="lazy">' for u in game_art[:6])}
    return '<div class="home-tiles">' + ''.join(
        f'<a class="htile px-frame {sec}" href="{sec}/index.html"><span class="ht-t">{title}</span>'
        f'<span class="ht-n">{counts.get(sec, 0)}</span><span class="ht-art">{art[sec]}</span></a>'
        for sec, title in SECTIONS) + '</div>'


def build_all() -> int:
    patches = archive.index()
    builds = load_json('builds/index.json')
    heroes = load_json('tables/heroes.json')['heroes']
    ents = load_json('entities.json')['entities']
    names = {f"{e['file']}:{e['id']}": display_name(e) for e in ents}
    templates = frozenset(f"{e['file']}:{e['id']}" for e in ents if e.get('template'))
    from .game_systems import systems
    from .unit_families import families, is_named
    fams = families([e for e in ents if e['file'] == 'npc_units.vdata' and not e.get('template')])
    unit_main = {m['id']: ms[0]['id'] for ms in fams.values() for m in ms}
    names |= {f"npc_units.vdata:{ms[0]['id']}": name for name, ms in fams.items()}     # "Slum Shroom", not "… I"
    # the one count of every patch (patch_counts: the patch pages and the list say the same) — no engine plumbing,
    # no work on unreleased heroes (round 3: "8620 hidden" counted both)
    from .patch_counts import for_id, page_set
    total = sum(for_id(row['id'])['changes'] - for_id(row['id']).get('unreleased', 0) for row in patches)
    total_hidden = sum(for_id(row['id'])['not_in_notes'] for row in patches)
    last_build = builds[-1] if builds else None
    # (a removed item's last known card, `last`, is no item on sale)
    shop = [c['item'] for c in load_json('abilities.json')['abilities'].values() if c.get('item') and not c.get('last')]
    counts = {'heroes': len(heroes),
              # what the shop sells now (the tiers 1-4 on the Shop page)
              'items': sum(1 for i in shop if not i.get('disabled') and not i.get('street_brawl')
                           and str(i.get('tier')) in '1234'),
              # the unit families the Units index shows (unit_families)
              'units': sum(1 for ms in fams.values() if ms[0].get('alive') and ms[0].get('kind') != 'helper'
                           and is_named(ms[0])),
              # the Game section's systems (game_systems: Souls & economy, Respawn, the Soul Urn…)
              'game': len(systems())}
    faces = [hero_icon(h['id'], '') or '' for h in heroes]
    # the Items tile shows items like the other tiles show heroes and units (it showed three dim category glyphs):
    # two of the dearest of each slot on sale now, by their shop icons
    on_sale = sorted(((k, c['item']) for k, c in load_json('abilities.json')['abilities'].items()
                      if c.get('item') and not c.get('last') and not c['item'].get('disabled')
                      and not c['item'].get('street_brawl')
                      and str(c['item'].get('tier')) in '1234'), key=lambda kc: (-int(kc[1].get('cost') or 0), kc[0]))
    item_art: list[str] = []
    for slot in ('WeaponMod', 'Armor', 'Tech'):
        mine = [entity_icon('abilities.vdata', k, 'item', '') for k, i in on_sale if i.get('slot') == slot]
        item_art += [u for u in mine if u][:2]
    # the units a player meets first: the objectives, then troopers and neutrals with their own icon
    order = {'building': 0, 'trooper': 1, 'neutral': 2}
    unit_art = [u for u in (entity_icon(e['file'], e['id'], e.get('kind') or '', '')
                            for e in sorted((e for e in ents if e['file'] == 'npc_units.vdata' and e.get('alive')
                                             and e.get('kind') in order and not e.get('template')),
                                            key=lambda e: (order[e['kind']], display_name(e)))) if u]
    unit_art = list(dict.fromkeys(unit_art))       # the same icon on namesakes once
    body = f'''
<div class="home-top">
  <div class="home-brand">{EYE_MARK}<h1>Cyclopean</h1></div>
  {search_box()}
  <div class="home-stats">
    <div class="hs"><span class="n">{total}</span><span class="l">changes</span></div>
    <a class="hs hidden" href="patches/index.html"><span class="n">{total_hidden}</span><span class="l">not in patch notes</span></a>
  </div>
</div>
{_tiles(counts, faces, unit_art, item_art)}
<h2 class="home-h">Latest changes</h2>
{_feed(patches, names, templates, unit_main, page_set())}
'''
    write('index.html', page('Deadlock change history', body, '', '', build=last_build['build'] if last_build else None,
                             description='What changed on every Deadlock hero, item, unit and game rule, from the game '
                                         'files: exact values and the changes the notes leave out.'))
    write('changelog.html', changelog_page())
    return 2


def changelog_page() -> str:
    entries = load_json('changelog.json')
    parts = ['<h1>Site changelog</h1>']
    for e in sorted(entries, key=lambda x: x['date'], reverse=True):
        items = ''.join(f'<li><span class="lbl">{esc(i)}</span></li>' for i in e['items'])
        parts.append(f'<section class="section px-frame"><h3 class="section-title">{esc(e["title"])}'
                     f'<span class="dimmer">{esc(e["date"])}</span></h3><ul class="change-list">{items}</ul></section>')
    return page('Site changelog', ''.join(parts), '', '')
