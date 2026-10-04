"""Home page: the three sections (Heroes, Items, Units) and what the last updates changed on each of them —
a strip of icons per update, each opening that hero's, item's or unit's history at that update. The site
is about the entities, not the patch notes (owner, 2026-10-03: "closer to Sloppy")."""
from __future__ import annotations

from .common import (EYE_MARK, display_name, entity_icon, esc, glyph_for, hero_icon, load_json, mark, page,
                     patch_name, patch_title_html, plural, pretty_id, slug, visual, write)
from . import archive
from .site_search import search_box

LATEST_UPDATES = 4        # updates with gameplay changes in the "what changed" feed
SECTIONS = (('heroes', 'Heroes'), ('items', 'Items'), ('units', 'Units'))
CHIP_SAMPLES = 2          # a feed icon's hover card lists this many of its biggest changes (217 icons on the page)


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


def update_feed(p: dict, templates: frozenset[str] = frozenset(), unit_main: dict[str, str] | None = None
                ) -> dict[str, dict[str, dict]]:
    """section -> page key -> {n, hidden, buff, nerf, kind, rows}: what one update did to each page (rows:
    (what, change) for the icon's hover card).
    Counts are the player-facing rows (cards.player_facing) a page shows; work on unreleased heroes
    waits for their release."""
    from .cards import gameplay_entities, player_facing
    from .dynamics_page import _display
    out: dict[str, dict[str, dict]] = {}
    once: set = set()
    for e in gameplay_entities(p['entities']):
        where = page_of(e, templates, unit_main)
        rows = [c for c in player_facing(e['changes']) if c.get('status') != 'unreleased']
        if not where or not rows:
            continue
        key, section = where
        if section == 'units':          # the same change on several members of a family counts once
            rows = [c for c in rows if (key, c.get('label'), c.get('old_s'), c.get('new_s')) not in once]
            once |= {(key, c.get('label'), c.get('old_s'), c.get('new_s')) for c in rows}
            if not rows:
                continue
        slot = out.setdefault(section, {}).setdefault(key, {'n': 0, 'hidden': 0, 'buff': 0, 'nerf': 0,
                                                             'kind': e.get('kind'), 'rows': []})
        # what each row is about on its page: a hero's ability or gun by name, an item's / unit's own rows bare
        what = _display(e) if section == 'heroes' else ''
        slot['rows'] += [(what, c) for c in rows]
        slot['n'] += len(rows)
        slot['hidden'] += sum(1 for c in rows if c.get('status') == 'hidden')
        slot['buff'] += sum(1 for c in rows if c.get('dir') == 'buff')
        slot['nerf'] += sum(1 for c in rows if c.get('dir') == 'nerf')
    return out


def _chip(key: str, s: dict, pid: str, names: dict[str, str], named: bool = False, k: int | None = None) -> str:
    """`names`: entity key -> its name today (common.display_name: never an id). `named`: the name under
    the icon (the newest update; advisor round 4: names were in tooltips only). `k`: the icon's entry in the
    feed's hover-card data (chip_card) — the card replaces the one-line tooltip."""
    file, _, eid = key.partition(':')
    name = names.get(key) or pretty_id(eid)
    ic = hero_icon(eid, '') if file == 'heroes.vdata' else entity_icon(file, eid, s.get('kind') or '', '', name)
    net = 'buff' if s['buff'] > s['nerf'] else 'nerf' if s['nerf'] > s['buff'] else 'mix'
    tip = f'{name}: {plural(s["n"], "change")}' + (f', {s["hidden"]} not in patch notes' if s['hidden'] else '')
    # with a card the eye says nothing of its own (its tooltip stacked on the card)
    eye_mark = mark('hidden') if k is None else EYE_MARK
    eye = f'<span class="lu-eye">{eye_mark}</span>' if s['hidden'] else ''
    label = f'<span class="lu-nm">{esc(name)}</span>' if named else ''
    hover = (f'aria-label="{esc(tip)}" data-name="{esc(name)}" data-k="{k}"' if k is not None
             else f'data-tooltip="{esc(tip)}"')
    return (f'<a class="lu net-{net}" href="{esc(slug(file, eid))}#p-{esc(pid)}" {hover}>'
            f'{visual(ic, glyph_for(file, eid))}<span class="lu-n">{s["n"]}</span>{eye}{label}</a>')


def chip_card(s: dict) -> list:
    """[{tag: n}, hidden, samples] for a feed icon's hover card: its CHIP_SAMPLES biggest changes as
    [what (a hero's ability; '' for an item's / unit's own rows), label, old, new, tag, hidden 0/1]."""
    from .history_view import _rank
    from .render import tag_of, vals_text
    counts: dict[str, int] = {}
    for _, c in s['rows']:
        counts[tag_of(c)[0]] = counts.get(tag_of(c)[0], 0) + 1
    top = sorted(s['rows'], key=lambda wc: _rank(wc[1]))[:CHIP_SAMPLES]
    return [counts, s['hidden'], [[w, str(c.get('label') or ''), *vals_text(c), tag_of(c)[0],
                                   int(c.get('status') == 'hidden')] for w, c in top]]


def _feed(patches: list[dict], names: dict[str, str], templates: frozenset[str], unit_main: dict[str, str]) -> str:
    """The latest updates' icons + ONE JSON blob of their hover cards (scripts.js dyn-tip, parsed on the first
    hover; owner 2026-10-04: "Graves: 17 changes" said nothing about what changed)."""
    import json
    from .common import patch_title_text
    from .render import TAG_WORD_ONE, TAG_WORDS
    blocks, updates, cards = [], [], []
    for row in reversed(patches):
        if len(blocks) == LATEST_UPDATES:
            break
        feed = update_feed(archive.patch(row['id']), templates, unit_main)
        if not feed:
            continue
        updates.append([patch_title_text(row), bool(patch_name(row['title']))])
        groups = []
        for sec, title in SECTIONS:
            got = sorted(feed.get(sec, {}).items(), key=lambda kv: (-kv[1]['n'], kv[0]))
            if got:
                named = not blocks
                chips = []
                for k, s in got:
                    chips.append(_chip(k, s, row['id'], names, named, len(cards)))
                    cards.append([len(updates) - 1, *chip_card(s)])
                groups.append(f'<div class="lu-group"><span class="lu-h">{title} <b>{len(got)}</b></span>'
                              f'<div class="lu-row{" named" if named else ""}">{"".join(chips)}</div></div>')
        hidden = sum(s['hidden'] for sec in feed.values() for s in sec.values())
        eye = f'<span class="au au-hidden">{mark("hidden")}<b>{hidden}</b> not in patch notes</span>' if hidden else ''
        blocks.append(f'<section class="update px-frame"><div class="banner{" named" if patch_name(row["title"]) else ""}">'
                      f'<span class="bt"><a href="patches/{esc(row["id"])}.html">{patch_title_html(row)}</a></span>'
                      f'<span class="bc">{eye}</span></div>{"".join(groups)}</section>')
    # the counters' icons are CSS (`.pip.<tag>`), the eye a mark
    data = {'u': updates, 'c': cards, 'words': TAG_WORDS, 'word1': TAG_WORD_ONE, 'eye': EYE_MARK}
    # JSON inside a script element: "</" would end it early
    blob = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    return ''.join(blocks) + f'<script type="application/json" class="feed-data">{blob}</script>'


def _tiles(counts: dict[str, int], faces: list[str], units: list[str]) -> str:
    """The three sections as big tiles (Sloppy's landing tiles, without blurbs)."""
    art = {'heroes': ''.join(f'<img class="px" src="{esc(f)}" alt="" loading="lazy">' for f in faces[:6]),
           'items': '<img src="icons/shop/tab_weapon.webp" alt=""><img src="icons/shop/tab_spirit.webp" alt="">'
                    '<img src="icons/shop/tab_vitality.webp" alt="">',
           'units': ''.join(f'<img class="px" src="{esc(u)}" alt="" loading="lazy">' for u in units[:6])}
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
    from .unit_families import families, is_named
    fams = families([e for e in ents if e['file'] == 'npc_units.vdata' and not e.get('template')])
    unit_main = {m['id']: ms[0]['id'] for ms in fams.values() for m in ms}
    names |= {f"npc_units.vdata:{ms[0]['id']}": name for name, ms in fams.items()}     # "Slum Shroom", not "… I"
    # the counters count what the hero / item / unit pages show (round 3: "8620 hidden" counted engine
    # plumbing and work on unreleased heroes too)
    total, total_hidden = 0, 0
    for row in patches:
        for sec in update_feed(archive.patch(row['id']), templates, unit_main).values():
            total += sum(s['n'] for s in sec.values())
            total_hidden += sum(s['hidden'] for s in sec.values())
    last_build = builds[-1] if builds else None
    shop = [c['item'] for c in load_json('abilities.json')['abilities'].values() if c.get('item')]
    counts = {'heroes': len(heroes),
              # what the shop sells now (the tiers 1-4 on the Shop page)
              'items': sum(1 for i in shop if not i.get('disabled') and not i.get('street_brawl')
                           and str(i.get('tier')) in '1234'),
              # the unit families the Units index shows (unit_families)
              'units': sum(1 for ms in fams.values() if ms[0].get('alive') and ms[0].get('kind') != 'helper'
                           and is_named(ms[0]))}
    faces = [hero_icon(h['id'], '') or '' for h in heroes]
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
    <div class="hs hidden"><span class="n">{total_hidden}</span><span class="l">not in patch notes</span></div>
  </div>
</div>
{_tiles(counts, faces, unit_art)}
<h2 class="home-h">Latest changes</h2>
{_feed(patches, names, templates, unit_main)}
'''
    write('index.html', page('Deadlock change history', body, '', '', build=last_build['build'] if last_build else None,
                             description='What changed on every Deadlock hero, item and unit, from the game files: '
                                         'exact values and the changes the notes leave out.'))
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
