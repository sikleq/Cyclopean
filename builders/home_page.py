"""Home page: the three sections (Heroes, Items, Units) and what the last updates changed on each of them —
a strip of icons per update, each opening that hero's, item's or unit's history at that update. The site
is about the entities, not the patch notes (owner, 2026-10-03: "closer to Sloppy")."""
from __future__ import annotations

from .common import (EYE_SVG, display_name, entity_icon, esc, glyph_for, hero_icon, load_json, mark, page,
                     patch_name, patch_title_html, plural, pretty_id, slug, visual, write)

LATEST_UPDATES = 4        # updates with gameplay changes in the "what changed" feed
SECTIONS = (('heroes', 'Heroes'), ('items', 'Items'), ('units', 'Units'))


def page_of(e: dict, templates: frozenset[str] = frozenset()) -> tuple[str, str] | None:
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
    if file == 'npc_units.vdata' and e.get('kind') != 'helper':
        return f'npc_units.vdata:{eid}', 'units'
    return None


def update_feed(p: dict, templates: frozenset[str] = frozenset()) -> dict[str, dict[str, dict]]:
    """section -> page key -> {n, hidden, buff, nerf, kind}: what one update did to each page.
    Counts are the player-facing rows (cards.player_facing) a page shows; work on unreleased heroes
    waits for their release."""
    from .cards import gameplay_entities, player_facing
    out: dict[str, dict[str, dict]] = {}
    for e in gameplay_entities(p['entities']):
        where = page_of(e, templates)
        rows = [c for c in player_facing(e['changes']) if c.get('status') != 'unreleased']
        if not where or not rows:
            continue
        key, section = where
        slot = out.setdefault(section, {}).setdefault(key, {'n': 0, 'hidden': 0, 'buff': 0, 'nerf': 0,
                                                             'kind': e.get('kind')})
        slot['n'] += len(rows)
        slot['hidden'] += sum(1 for c in rows if c.get('status') == 'hidden')
        slot['buff'] += sum(1 for c in rows if c.get('dir') == 'buff')
        slot['nerf'] += sum(1 for c in rows if c.get('dir') == 'nerf')
    return out


def _chip(key: str, s: dict, pid: str, names: dict[str, str]) -> str:
    """`names`: entity key -> its name today (common.display_name: never an id)."""
    file, _, eid = key.partition(':')
    name = names.get(key) or pretty_id(eid)
    ic = hero_icon(eid, '') if file == 'heroes.vdata' else entity_icon(file, eid, s.get('kind') or '', '', name)
    net = 'buff' if s['buff'] > s['nerf'] else 'nerf' if s['nerf'] > s['buff'] else 'mix'
    tip = f'{name}: {plural(s["n"], "change")}' + (f', {s["hidden"]} hidden' if s['hidden'] else '')
    eye = f'<span class="lu-eye">{mark("hidden")}</span>' if s['hidden'] else ''
    return (f'<a class="lu net-{net}" href="{esc(slug(file, eid))}#p-{esc(pid)}" data-tooltip="{esc(tip)}">'
            f'{visual(ic, glyph_for(file, eid))}<span class="lu-n">{s["n"]}</span>{eye}</a>')


def _feed(patches: list[dict], names: dict[str, str], templates: frozenset[str]) -> str:
    blocks = []
    for row in reversed(patches):
        if len(blocks) == LATEST_UPDATES:
            break
        p = load_json(f'patches/{row["id"]}.json.gz')
        feed = update_feed(p, templates)
        if not feed:
            continue
        groups = []
        for sec, title in SECTIONS:
            got = sorted(feed.get(sec, {}).items(), key=lambda kv: (-kv[1]['n'], kv[0]))
            if got:
                groups.append(f'<div class="lu-group"><span class="lu-h">{title} <b>{len(got)}</b></span>'
                              f'<div class="lu-row">{"".join(_chip(k, s, row["id"], names) for k, s in got)}</div></div>')
        hidden = sum(s['hidden'] for sec in feed.values() for s in sec.values())
        eye = f'<span class="au au-hidden">{mark("hidden")}<b>{hidden}</b> hidden</span>' if hidden else ''
        blocks.append(f'<section class="update px-frame"><div class="banner{" named" if patch_name(row["title"]) else ""}">'
                      f'<span class="bt"><a href="patches/{esc(row["id"])}.html">{patch_title_html(row)}</a></span>'
                      f'<span class="bc">{eye}</span></div>{"".join(groups)}</section>')
    return ''.join(blocks)


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
    patches = load_json('patches/index.json')
    builds = load_json('builds/index.json')
    heroes = load_json('tables/heroes.json')['heroes']
    ents = load_json('entities.json')['entities']
    names = {f"{e['file']}:{e['id']}": display_name(e) for e in ents}
    templates = frozenset(f"{e['file']}:{e['id']}" for e in ents if e.get('template'))
    total_hidden = sum(p['counts'].get('hidden', 0) for p in patches)
    last_build = builds[-1] if builds else None
    shop = [c['item'] for c in load_json('abilities.json')['abilities'].values() if c.get('item')]
    counts = {'heroes': len(heroes),
              # what the shop sells now (the tiers 1-4 on the Shop page)
              'items': sum(1 for i in shop if not i.get('disabled') and not i.get('street_brawl')
                           and str(i.get('tier')) in '1234'),
              'units': sum(1 for e in ents if e['file'] == 'npc_units.vdata' and e.get('alive')
                           and e.get('kind') != 'helper' and not e.get('template'))}
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
  <div class="home-brand"><span class="mark hidden">{EYE_SVG}</span><h1>Cyclopean</h1></div>
  <div class="home-stats">
    <div class="hs"><span class="n">{len(builds)}</span><span class="l">builds compared</span></div>
    <div class="hs hidden"><span class="n">{total_hidden}</span><span class="l">hidden changes</span></div>
  </div>
</div>
{_tiles(counts, faces, unit_art)}
<h2 class="home-h">Latest changes</h2>
{_feed(patches, names, templates)}
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
