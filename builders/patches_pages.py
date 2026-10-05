"""Patch pages: official notes annotated with the data, plus hidden changes."""
from __future__ import annotations

import html
import re
from functools import lru_cache

from .cards import GAMEPLAY
from .notes_view import notes_table
from .common import (build_href, esc, plural, load_json, mark, names_by_id, page, patch_name, patch_title_html,
                     patch_title_text, pretty_id, write)

FILES_TAB_MIN = 100     # hidden changes before a notes patch also gets the "From the files" tab


SUMMARY_TAGS = (('buff', 'Buffs'), ('nerf', 'Nerfs'), ('new', 'New'), ('del', 'Removed'), ('rework', 'Reworks'),
                ('other', 'Other'))


def _summary(p: dict, gameplay: list[dict], rel: str, link_base: str = '') -> str:
    """The patch's first screen: how big and which way (tag counters + bar), who was hit
    (hero portraits with up/down counts), then one thin line of the notes check."""
    from .cards import player_facing
    from .common import hero_icon
    from .render import tag_of
    counts = {k: 0 for k, _ in SUMMARY_TAGS}
    per_hero: dict[str, dict[str, int]] = {}
    for e in gameplay:
        owner = e['id'] if e['file'] == 'heroes.vdata' and e['id'] != '@shared' else e.get('owner')
        for c in player_facing(e['changes']):        # the same rule as every other counter
            cls = tag_of(c)[0]
            counts[cls if cls in counts else 'other'] += 1
            if owner and owner != 'hero_base':
                tags = per_hero.setdefault(owner, {})
                tags[cls] = tags.get(cls, 0) + 1
    total = sum(counts.values()) or 1
    tiles = ''.join(f'<div class="sum-tile t-{k}"><span class="n">{counts[k]}</span><span class="l">{esc(lbl)}</span></div>'
                    for k, lbl in SUMMARY_TAGS if counts[k])
    bar = ''.join(f'<span class="b-{k}" style="width:{counts[k] / total * 100:.2f}%"></span>' for k, _ in SUMMARY_TAGS
                  if counts[k])
    names = hero_names()
    live = released_heroes()
    heroes = sorted(per_hero, key=lambda h: (-(sum(per_hero[h].values())), names.get(h, h)))
    # heroes still in development (placeholder art) do not crowd the strip: one counter for them
    in_dev = [h for h in heroes if h not in live]
    strip = ''.join(_hero_chip(h, names.get(h, h), per_hero[h], rel, link_base)
                    for h in heroes if h in live and hero_icon(h, rel))
    if in_dev:
        strip += f'<span class="chip dev hdev">{mark("unreleased")}+{len(in_dev)} in development</span>'
    audit_html = _audit_line(p)
    return (f'<section class="summary px-frame"><div class="sum-tiles">{tiles}</div><div class="sum-bar">{bar}</div>'
            f'{"<div class=sum-heroes>" + strip + "</div>" if strip else ""}'
            f'<div class="sum-audit">{audit_html}</div></section>')


def _audit_line(p: dict) -> str:
    """The notes check under the tiles, by the one count (`patch_counts`): the changes the tiles count, by status —
    not the matcher's raw field counts (City Never Sleeps read "1232 not in the notes" over tiles summing to 861).
    The hidden ones no hero, item or unit page shows are named right after them."""
    from .patch_counts import for_id, off_pages
    c = for_id(p['id'])
    lc = p.get('line_counts', {})
    if p.get('sections'):
        audit = [('documented', c.get('documented', 0), 'exact in the notes'),
                 ('described', c.get('described', 0), 'covered by a general line'),
                 ('hidden', c.get('not_in_notes', 0), 'not in patch notes'),
                 ('mismatch', lc.get('mismatch', 0), 'notes disagree with the files'),
                 ('code', lc.get('code', 0), "in the game's code"),
                 ('fix', lc.get('fix', 0), 'bug fixes')]
        if c.get('unreleased'):
            audit.insert(3, ('unreleased', c['unreleased'], 'heroes in development'))
    else:
        audit = [('hidden', c.get('unannounced', 0), 'changes, no official notes')]
        if c.get('documented'):
            audit.append(('documented', c['documented'], 'announced in earlier notes'))
    off = off_pages(c)
    html = ''
    for k, n, lbl in audit:
        if n and k == 'hidden':
            # the count opens the "All changes" tab with its "Not in patch notes" filter on (scripts.js hidden-hash)
            html += f'<a class="au au-{k}" href="#hidden">{mark(k)}<b>{n}</b> {esc(lbl)}</a>'
        elif n:
            html += f'<span class="au au-{k}">{mark(k)}<b>{n}</b> {esc(lbl)}</span>'
        if k == 'hidden' and n and off:
            # their pages are the Game section's (the patch page and the list both live in patches/)
            html += (f'<a class="au au-off" href="../game/index.html"><b>{off}</b> of them in game rules '
                     f'&amp; map objects</a>')
    return html


HCHIP_KINDS = 2      # a 50px chip fits two counters; the tooltip carries them all


def _hero_chip(hid: str, name: str, tags: dict[str, int], rel: str, link_base: str) -> str:
    """Portrait + its two biggest counters in the tag glyphs (a rework- or new-only hero
    used to show an empty slab: only ▲/▼ were counted)."""
    from .common import hero_icon
    from .render import TAG_ORDER, counts_text, pip
    ranked = sorted(tags.items(), key=lambda kv: (-kv[1], TAG_ORDER.get(kv[0], 9)))
    shown = sorted(ranked[:HCHIP_KINDS], key=lambda kv: TAG_ORDER.get(kv[0], 9))
    pips = ''.join(pip(k, n) for k, n in shown)
    return (f'<a class="hchip" href="{esc(link_base)}#c-{esc(hid)}" data-tooltip="{esc(name)}: {esc(counts_text(tags))}">'
            f'<img class="px" src="{esc(hero_icon(hid, rel) or "")}" alt="{esc(name)}" loading="lazy">'
            f'<span class="hc">{pips}</span></a>')


@lru_cache(maxsize=1)
def hero_names() -> dict[str, str]:
    """hero id -> display name from the entity catalog (heroes that did not change themselves)."""
    return {e['id']: e.get('name') or e['id'] for e in load_json('entities.json')['entities']
            if e['file'] == 'heroes.vdata'}


@lru_cache(maxsize=1)
def released_heroes() -> set[str]:
    """Heroes a player can pick today (release or pre-release, still in the files)."""
    return {e['id'] for e in load_json('entities.json')['entities']
            if e['file'] == 'heroes.vdata' and e.get('alive')
            and e.get('state') in ('EHeroDevState_Release', 'EHeroDevState_PreRelease')}


@lru_cache(maxsize=1)
def catalog_names() -> dict[str, str]:
    """entity key -> the latest known name: an ability localized only after the patch
    still shows a name, not its internal id."""
    return {f"{e['file']}:{e['id']}": e['name'] for e in load_json('entities.json')['entities']
            if e.get('name') and e['name'] != e['id']}


def _display_name(e: dict) -> str:
    """Name at the patch's build; else the latest known name; else a readable stand-in, never the id. An edit
    shared by many entities says how many and what ("10 heroes", "All heroes (61)": shared_rows.block_name)."""
    if e.get('id') == '@shared' and e.get('target_keys'):
        from .shared_rows import block_name
        return block_name(e)
    name = e.get('name') or e['id']
    if name != e['id']:
        return name + (f' · {len(e["variants"])} variants' if e.get('variants') else '')
    known = catalog_names().get(f"{e['file']}:{e['id']}")
    if not known and e['file'] not in ('heroes.vdata', 'abilities.vdata', 'npc_units.vdata'):
        # a map object or rule the files give no text: the Game section's name ("Soul Urn delivery", not
        # "Idol cashin"; coverage audit 2026-10-05, finding 4)
        from .game_systems import name_of
        return name_of(f"{e['file']}:{e['id']}", e)
    # a hero in development has no name in any build: the catalog keeps its id ('hero_airheart')
    return known if known and known != e['id'] else pretty_id(e['id'], e.get('owner'))


def _counted(e: dict) -> list[dict]:
    """What the entity's counters count: a newly added entity is ONE new thing, not its N fields."""
    if e.get('status') == 'added' and e['changes']:
        first = e['changes'][0]
        return [{'op': 'add', 'cat': 'mechanic', 'status': first.get('status', 'hidden'), 'key': first.get('key'),
                 'label': 'Added'}]
    return e['changes']


def _changes_table(ents: list[dict], rel: str, pid: str | None = None) -> str:
    """All gameplay changes as entity cards: one card per hero (its abilities as
    sub-headers), then one per item, unit and rule; each with its history strip."""
    from .cards import card, card_head, change_rows, is_hidden, player_facing, sub_head
    from .common import entity_icon, glyph_for, hero_icon
    from .trail import trail_html
    heroes = {e['id']: e for e in ents if e['file'] == 'heroes.vdata' and e['id'] != '@shared'}
    by_owner: dict[str, list] = {}
    rest = []
    for e in ents:
        if e['file'] == 'heroes.vdata' and e['id'] != '@shared':
            by_owner.setdefault(e['id'], []).insert(0, e)
        elif e.get('owner'):
            # everything a hero owns sits in the hero's card — the summary chip counts it there, and
            # sub-abilities (kind ability_other) in cards of their own left the chip's #c-hero link
            # pointing nowhere (Sinclair 2026-09-16, Holliday's gun 2026-01-20)
            by_owner.setdefault(e['owner'], []).append(e)
        else:
            rest.append(e)
    order_rest = {'shared': 0, 'item': 1, 'building': 2, 'trooper': 3, 'neutral': 4, 'unit': 5}
    rest.sort(key=lambda e: (order_rest.get(e.get('kind'), 9), e.get('name') or ''))
    names = hero_names()

    def hero_label(hid: str) -> str:
        if hid == 'hero_base':
            return 'Common abilities (all heroes)'
        found = (heroes.get(hid, {}).get('name'), names.get(hid), *(x.get('owner_name') for x in by_owner[hid]))
        return next((n for n in found if n and n != hid), None) or pretty_id(hid)

    out = []
    for hid in sorted(by_owner, key=lambda h: hero_label(h).lower()):
        members = by_owner[hid]
        all_ch = [c for e in members for c in _counted(e)]
        hname = hero_label(hid)
        body = []
        for e in members:
            if e['file'] == 'heroes.vdata':
                scope, ic, glyph = 'Base stats', hero_icon(hid, rel), 'hero'
            else:
                scope = _display_name(e)
                ic = entity_icon(e['file'], e['id'], e.get('kind', ''), rel, e.get('name'), e.get('owner'))
                glyph = glyph_for(e['file'], e['id'], e.get('kind', ''))
            # the eye filter's marks follow what is counted: plumbing rows (Technical) are not
            body.append(sub_head(scope, ic, glyph, _counted(e), is_hidden(player_facing(e['changes']))))
            body.append(change_rows(e['changes'], added=e.get('status') == 'added'))
        head = card_head(hname, hero_icon(hid, rel), 'heroes' if hid == 'hero_base' else 'hero', all_ch,
                         trail=trail_html(f'heroes.vdata:{hid}', pid, rel))
        out.append(card(head, ''.join(body), hidden=is_hidden(player_facing(all_ch)),
                        dev=any(c.get('status') == 'unreleased' for c in all_ch),
                        search=hname.lower(), anchor=f'c-{hid}'))
    # an item's or unit's card is a place to land too ("patch ↗" on its page: history_view.patch_href), once per id
    anchored = set(by_owner)
    for e in rest:
        name = _display_name(e)
        if e.get('targets') and not e.get('target_keys'):      # a block named by shared_rows.block_name has its count
            name += f' ({len(e["targets"])})' if f'({len(e["targets"])})' not in name else ''
        ic = entity_icon(e['file'], e['id'], e.get('kind', ''), rel, e.get('name'), e.get('owner'))
        head = card_head(name, ic, glyph_for(e['file'], e['id'], e.get('kind', '')), _counted(e),
                         trail=trail_html(f"{e['file']}:{e['id']}", pid, rel))
        anchor = '' if e['id'] in anchored or e['id'] == '@shared' else f'c-{e["id"]}'
        anchored.add(e['id'])
        out.append(card(head, change_rows(e['changes'], added=e.get('status') == 'added'),
                        hidden=is_hidden(player_facing(e['changes'])), search=name.lower(), anchor=anchor))
    return '<div class="ecards">' + ''.join(out) + '</div>'


def _key_changes(p: dict, rel: str) -> str:
    rows = p.get('key_changes') or []
    if not rows:
        return ''
    from .render import key_change_rows
    trs = key_change_rows(rows, rel, hero_names())
    return f'<h2>Biggest changes</h2><table class="hist px-frame">{trs}</table>'


def _generated_notes(p: dict) -> str:
    """Valve-style notes written from the files for updates without official numbers: the rows the
    counters count (cards.player_facing), each entity by its name and values as the pages print them
    — the stored sentences carried ids and engine enums (492 of 1500 lines in City Never Sleeps)."""
    from pipeline.match import sentence
    from .cards import player_facing
    from .render import shown_value
    lines = []
    for e in p['entities']:
        name = _display_name(e)
        for c in player_facing(e['changes']):
            if c.get('cat') in GAMEPLAY:
                lines.append(sentence(name, {**c, 'old_s': shown_value(c.get('old_s')),
                                             'new_s': shown_value(c.get('new_s'))}))
    if not lines:
        return ''
    lis = ''.join(f'<li>{esc(s)}</li>' for s in lines[:1500])
    more = f'<p class="muted">+{len(lines) - 1500} more lines.</p>' if len(lines) > 1500 else ''
    return (f'<h2>Patch notes written from the files</h2><p class="muted">Valve published no numbers for this update; '
            f'every line below is read from the game files.</p><ul class="gen-notes cols-2">{lis}</ul>{more}')


def _bar(c: dict) -> str:
    total = sum(c.get(k, 0) for k in ('documented', 'described', 'hidden')) or 1
    seg = ''.join(f'<span class="{cls}" style="width:{c.get(k, 0) / total * 100:.1f}%"></span>'
                  for k, cls in (('documented', 'b-doc'), ('described', 'b-des'), ('hidden', 'b-hid')))
    return f'<div class="bar">{seg}</div>'


def patch_page(p: dict, prev: dict | None, nxt: dict | None) -> str:
    rel = '../'
    # copies: the patch record is the build's shared archive (builders/archive.py), never written into
    change_by_key = {}
    for e in p['entities']:
        name = _display_name(e)
        for c in e['changes']:
            change_by_key[c['key']] = {**c, 'ent_name': name}
    # patch switcher next to the title (players step through patches)
    step = ''
    if prev:
        step += f'<a class="step" href="{esc(prev["id"])}.html" data-tooltip="{esc(patch_title_text(prev))}">◀</a>'
    if nxt:
        step += f'<a class="step" href="{esc(nxt["id"])}.html" data-tooltip="{esc(patch_title_text(nxt))}">▶</a>'
    named = ' named' if patch_name(p['title']) else ''
    parts = ['<div class="crumbs"><a href="index.html">Patches</a></div>',
             f'<div class="ptitle{named}"><h1>{patch_title_html(p)}</h1><span class="steps">{step}</span></div>']
    # Valve sometimes ships one build number twice (two tracker commits): "6698, 6698 (#2)", not a repeat
    seen: dict = {}
    links = []
    for b in p['builds'][:30]:
        seen[b['build']] = seen.get(b['build'], 0) + 1
        nth = f' (#{seen[b["build"]]})' if seen[b['build']] > 1 else ''
        num = b['build'] if b['build'] is not None else 'text update'
        links.append(f'<a href="{esc(build_href(b["file"], rel))}">{esc(num)}{nth}</a>')
    builds = ', '.join(links)
    link_text = 'official notes' if p.get('source') != 'announcement' else 'official announcement'
    src = f' · <a href="{esc(p["url"])}" rel="noopener">{link_text}</a>' if p.get('url') else ''
    parts.append(f'<div class="meta muted">builds: {builds or "—"}{src}</div>')

    from .cards import gameplay_entities
    from .patch_counts import for_id
    names = {e['id']: e.get('name') for e in p['entities'] if e['file'] == 'heroes.vdata'}
    # gameplay_entities copies each entity, so the owner's name is not written into the shared record
    gameplay = [{**e, 'owner_name': names.get(e['owner'])} if e.get('owner') else e
                for e in gameplay_entities(p['entities'])]
    # the tab counts what the tiles count (cards.player_facing), not raw rows: City Never Sleeps
    # read 1524 in the tab against 1000 in the tiles (71 of 104 pages differed, audit 2026-10-01) —
    # the one count of patch_counts, as on the patch list and the home page
    pc = for_id(p['id'])
    n_changes = pc['changes']
    parts.append(_summary(p, gameplay, rel))
    tabs = []
    if p['sections']:
        from .notes_view import interface_table, split_sections
        play, iface = split_sections(p['sections'])
        tabs.append(('notes', 'Patch notes', sum(len(s['lines']) for s in play),
                     notes_table({**p, 'sections': play}, change_by_key, rel)))
        if iface:
            # interface, sound and settings lines: their own tab, a compact grid of features
            tabs.append(('interface', 'Interface & sound', sum(len(s['lines']) for s in iface), interface_table(iface)))
        c = pc
        # notes that say little about a big update (City Never Sleeps: 11 interface lines,
        # 1,400+ gameplay changes): the files' own summary sits next to the official text
        if c.get('hidden', 0) >= FILES_TAB_MIN and c.get('hidden', 0) > 3 * (c.get('documented', 0) + c.get('described', 0)):
            # 'generated', not 'files': the asset tab "Game files" already uses id="files"
            tabs.append(('generated', 'From the files', n_changes,
                         _key_changes(p, rel) + _generated_notes({**p, 'entities': gameplay})))
    else:
        tabs.append(('notes', 'From the files', n_changes,
                     _key_changes(p, rel) + _generated_notes({**p, 'entities': gameplay})))
    # the eye filter keeps exactly the rows its number counts (patch_counts; it kept 1024 rows under 776)
    eye_btn = (f'<button class="px-btn hf-hidden" data-toggle-class="only-hidden" data-target="#changes" '
               f'aria-pressed="false">{mark("hidden")}Not in patch notes <span class="n">{pc["not_in_notes"]}</span></button>'
               f'<span class="sep"></span>' if pc['not_in_notes'] else '')
    changes_panel = (f'<div class="toolbar">{eye_btn}<input type="search" placeholder="Hero, item…" '
                     'data-search-target="#changes .ecard[data-search]"></div>' + _changes_table(gameplay, rel, p['id']))
    tabs.append(('changes', 'All changes', n_changes, changes_panel))
    extra_parts = _extras_parts(p, rel)
    tabs += extra_parts
    parts.append('<div class="tabs toolbar">' + ''.join(
        f'<button class="px-btn{" on" if i == 0 else ""}" data-tab="{k}" aria-pressed="{"true" if i == 0 else "false"}">{esc(lbl)}<span class="count">{n}</span></button>'
        for i, (k, lbl, n, _) in enumerate(tabs)) + '</div>')
    for i, (k, _, _, panel) in enumerate(tabs):
        parts.append(f'<div class="tab-panel{" on" if i == 0 else ""}" id="{k}">{panel}</div>')
    nav = []
    if prev:
        nav.append(f'<a class="px-btn" href="{esc(prev["id"])}.html">← {esc(patch_title_text(prev))}</a>')
    if nxt:
        nav.append(f'<a class="px-btn" href="{esc(nxt["id"])}.html">{esc(patch_title_text(nxt))} →</a>')
    parts.append('<div class="flex">' + ''.join(nav) + '</div>')
    return page(patch_title_text(p), ''.join(parts), rel, 'patches',
                description=f'Deadlock {patch_title_text(p)}: official notes vs game files')


def _extras_parts(p: dict, rel: str) -> list[tuple[str, str, int, str]]:
    """Secondary tabs: text/tooltips, console variables, packed game files."""
    ex = p.get('extras', {})
    out = []
    loc_rows = ex.get('loc', [])
    if loc_rows:
        more = ex.get('loc_total', len(loc_rows)) - len(loc_rows)
        more_s = f'<p class="muted">+{more} more on the build pages.</p>' if more > 0 else ''
        out.append(('text', 'Text & tooltips', ex.get('loc_total', len(loc_rows)),
                    f'<ul class="change-list px-frame">{"".join(_loc_li(x) for x in loc_rows)}</ul>{more_s}'))
    cv = ex.get('convars', [])
    if cv:
        # every one (coverage audit 2026-10-05: City Never Sleeps' tab said 510 and listed 300 without a word); data
        # written before the list was whole says how many more the build pages hold
        more = ex.get('convars_total', len(cv)) - len(cv)
        more_s = (f'<p class="muted">+{more} more on the build pages: '
                  + ', '.join(f'<a href="{build_href(b["file"], rel)}">{b["build"]}</a>' for b in p.get('builds', [])
                              if b.get('build') is not None) + '.</p>') if more > 0 else ''
        # the build that starts the tracking (6395, 2026-03-10) lists all 1,365 variables: a snapshot, not changes —
        # one line, out of the tab's number (20.8k elements on the page; the Game pages skip it too, review 2026-10-05)
        from .game_systems import convar_start
        start = convar_start()
        snap = [x for x in cv if start is not None and x.get('build') == start]
        cv = [x for x in cv if start is None or x.get('build') != start]
        snap_li = ''
        if snap:
            b = next((b for b in p.get('builds', []) if b.get('build') == start), None)
            where = f'<a href="{build_href(b["file"], rel)}">build {start}</a>' if b else f'build {start}'
            snap_li = (f'<li class="st-snap"><span class="lbl">Tracking of console variables starts here: '
                       f'{len(snap)} variables in {where}</span></li>')
        out.append(('console', 'Console variables', ex.get('convars_total', len(cv) + len(snap)) - len(snap),
                    f'<ul class="change-list px-frame">{snap_li}{"".join(convar_li(x) for x in cv)}</ul>{more_s}'))
    assets = ex.get('assets') or {}
    totals = assets.get('counts', {})
    if totals:
        heroes = assets.get('hero_models', [])
        rows = ''.join(f'<tr><td>{esc(cat)}</td><td class="v">+{t["added"]}</td><td class="v">−{t["removed"]}</td>'
                       f'<td class="v">~{t["modified"]}</td></tr>' for cat, t in sorted(totals.items()))
        hm = f'<p class="muted">Hero model folders touched: {esc(", ".join(heroes))}</p>' if heroes else ''
        other = sum(1 for e in p['entities'] for c in e['changes'] if c['cat'] in ('visual', 'audio', 'ui', 'meta', 'technical'))
        other_s = f'<p class="muted">Also {other} visual / audio / UI / technical data fields (see the build pages).</p>' if other else ''
        out.append(('files', 'Game files', sum(sum(t.values()) for t in totals.values()),
                    f'<table class="kvt px-frame"><caption>Packed files: added / removed / modified</caption>{rows}</table>{hm}{other_s}'))
    return out


# "{g:citadel_binding:'Attack'}", also with a form word: "{g:citadel_binding:1st:'Spectator.SpecNext'}"
_KEY_HINT = re.compile(r"\{g:citadel_(?:binding|keybind):(?:\w+:)?'([^']*)'\}")
_VALUE_TOKEN = re.compile(r'\{[sf]:(?:\d+:)?(\w+)\}')
_GLOSSARY = re.compile(r"\{g:[\w]+:'?([^}']*)'?\}")
_PRINTF = re.compile(r'%s\d')


def _plain(s, limit: int | None = 400) -> str:
    """Loc text for display: no markup or entities ("&amp;" printed as "&amp;amp;"); key bindings
    as [Attack]; a value the game fills in as [Enemy Health Percent], a glossary word as words
    (1677 lines showed "{s:Damage}" / "{g:citadel_inline_attribute:'SpiritDamage'}")."""
    from pipeline.semantics import humanize
    t = re.sub(r'<br\s*/?>', ' · ', str(s or ''), flags=re.I)        # a line break is a separator, not glue
    t = html.unescape(re.sub(r'<[^>]+>', '', t))
    t = _KEY_HINT.sub(lambda m: f' [{humanize(m.group(1).rsplit(".", 1)[-1])}] ', t)
    t = _VALUE_TOKEN.sub(lambda m: f'[{humanize(m.group(1))}]', t)
    t = _GLOSSARY.sub(lambda m: humanize(m.group(1)).lower(), t)
    t = _PRINTF.sub('…', t)
    t = re.sub(r'\s{2,}', ' ', t).strip()
    return t[:limit] if limit else t


_LOC_SUFFIX = re.compile(r'^(?P<base>.+?)(?P<suf>(?:_t(?P<tier>[1-3]))?_(?P<kind>desc|quip|header|lore|name|label|'
                         r'tooltip|note)|_t(?P<tier2>[1-3])|:n)?$')
_LOC_KIND = {'desc': 'description', 'quip': 'quip', 'header': 'header', 'lore': 'lore', 'name': 'name',
             'label': 'label', 'tooltip': 'tooltip', 'note': 'note'}


_UI_GROUPS = (('citadel_chatwheel', 'Chat wheel'), ('citadel_combat_log', 'Combat log'), ('citadel_ranked', 'Ranked'),
              ('citadel_chattarget', 'Chat'), ('citadel_chat', 'Chat'), ('citadel_settings', 'Settings'),
              ('citadel_hud', 'HUD'), ('citadel_shop', 'Shop'), ('citadel_matchmaking', 'Matchmaking'),
              ('citadel_tutorial', 'Tutorial'), ('citadel_hideout', 'Hideout'), ('citadel_party', 'Party'),
              ('citadel_postgame', 'Post-game'), ('citadel_streetbrawl', 'Street Brawl'),
              ('citadel_rankednotallowed', 'Ranked'), ('citadel_ping', 'Pings'), ('citadel_mainmenu', 'Main menu'))
# '<property>_label' / '_postvalue_label' / '_postfix' / '_prefix': the words a tooltip prints next to a value
_STAT_KEY = re.compile(r'^(?:modifier_value_)?[a-z0-9_]+?_(?P<part>postvalue_label|label|postfix|prefix)$')
_STAT_PART = {'label': 'stat name', 'postvalue_label': 'stat name', 'postfix': 'stat unit', 'prefix': 'stat sign'}


def loc_key_label(key: str) -> str:
    """'ability_afterburn_t1_desc' -> 'Afterburn · T1 description'; UI strings by their screen
    ('citadel_chatwheel_push_green' -> 'Chat wheel · push green'); a stat's words 'Stat name';
    other keys humanised ('citadel_commend_toast_seconds' -> 'commend toast seconds')."""
    low = key.lower()
    for prefix, screen in sorted(_UI_GROUPS, key=lambda g: -len(g[0])):
        if low.startswith(prefix):
            rest = low[len(prefix):].strip('_').replace('_', ' ')
            return f'{screen} · {rest}' if rest else screen
    sm = _STAT_KEY.match(low)
    if sm and not low.startswith(('ability_', 'citadel_ability_', 'upgrade_')):
        return _STAT_PART[sm.group('part')].capitalize()
    m = _LOC_SUFFIX.match(low)
    base, tier = m.group('base'), m.group('tier') or m.group('tier2')
    part = ' '.join(p for p in (f'T{tier}' if tier else '', _LOC_KIND.get(m.group('kind') or '', '')) if p)
    if m.group('suf') == ':n':
        part = 'name'
    names = names_by_id()
    whole, name, extra = base, names.get(base), []
    while not name and '_' in base:       # 'ability_afterburn_burn' -> 'Afterburn' + 'burn'
        base, _, tail = base.rpartition('_')
        extra.insert(0, tail)
        name = names.get(base)
    if not name and whole.startswith(('ability_', 'citadel_ability_', 'upgrade_')):
        name, extra = pretty_id(whole), []          # an ability not named yet (a hero in development)
    if not name:
        return re.sub(r'^(citadel_|ability_|modifier_|upgrade_)+', '', low).replace('_', ' ').replace(':', ' ')
    part = ' '.join(extra + ([part] if part else []))
    return f'{name} · {part}' if part else name


def _loc_li(x: dict) -> str:
    from .render import tag_badge
    key = f'<span class="chip">{esc(loc_key_label(x["key"]))}</span>'     # the raw key is an internal id: not shown
    old, new = x.get('old'), x.get('new')
    if old and new and _plain(old) == _plain(new):
        return ''          # only the markup changed (a colour span, a token's spelling): nothing to read
    if old and new:
        body = (f'<span class="old">{esc(_plain(old))}</span><span class="arrow">→</span>'
                f'<span class="new">{esc(_plain(new))}</span>')
    elif new:
        body = f'{tag_badge("new", "NEW")} {esc(_plain(new))}'
    else:
        body = f'{tag_badge("del", "DEL")} <span class="old">{esc(_plain(old))}</span>'
    return f'<li>{key}<span class="lbl">{body}</span></li>'


def convar_li(x: dict) -> str:
    desc = f' — {esc(x["desc"])}' if x.get('desc') else ''
    old, new = x.get('old'), x.get('new')
    if old is not None and new is not None:
        vals = f'<span class="old">{esc(old)}</span><span class="arrow">→</span><span class="new">{esc(new)}</span>'
    else:
        vals = f'<span class="new">{esc(new if new is not None else old)}</span>'
    st = x.get('status')
    m = mark(st) if st in ('documented', 'described', 'hidden') else ''
    # a description change carries sentences, not numbers: they wrap (510 rows stretched a 390px page to 3010px)
    wrap = ' wrap' if x.get('op') == 'desc' else ''
    return (f'<li class="st-{esc(st or "")}">{m}<span class="chip">{esc(x["op"])}</span><span class="lbl"><code>{esc(x["name"])}</code>{desc}</span>'
            f'<span class="vals{wrap}">{vals}</span></li>')


MONTHS = ('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
          'November', 'December')
INDEX_HEROES = 6


def _index_row(p: dict, stats: dict, rel: str, follow: bool) -> str:
    from .common import hero_icon
    from .patch_counts import for_id
    from .render import pip
    # the one count (patch_counts), as on the patch page and the home page — not the matcher's raw field counts
    c, lc = for_id(p['id']), p['line_counts']
    st = stats.get(p['id'], {'tags': {}, 'heroes': []})
    t = st['tags']
    # four fixed cells (empty when zero) so the counts line up from row to row
    dirs = ''.join(f'<span class="ix-{k}">{pip(k, t[k]) if t.get(k) else ""}</span>'
                   for k in ('buff', 'nerf', 'new', 'del'))
    names = hero_names()
    faces = ''.join(f'<img class="px" src="{esc(hero_icon(h, rel) or "")}" alt="" loading="lazy" '
                    f'data-tooltip="{esc(names.get(h, h))}">' for h in st['heroes'][:INDEX_HEROES] if hero_icon(h, rel))
    if p.get('has_notes'):
        audit = (f'<span class="au">{mark("documented")}<b>{c.get("documented", 0)}</b></span>'
                 f'<span class="au au-hidden">{mark("hidden")}<b>{c.get("not_in_notes", 0)}</b></span>')
        if p['line_counts'].get('mismatch'):
            audit += f'<span class="au au-mismatch">{mark("mismatch")}<b>{lc["mismatch"]}</b></span>'
    else:
        # no notes to hide from: a plain count, not the "hidden" eye (the eye summed to 8767 here
        # against 8041 hidden on the home page)
        audit = f'<span class="au"><b>{c.get("unannounced", 0)}</b> changes · no notes</span>'
    # the date is the row's first column: the title cell shows only the name (or 'update')
    name = patch_name(p['title'])
    title = ('<span class="pfu">follow-up</span>' if follow
             else f'<span class="pname">{esc(name)}</span>' if name else '<span class="pkind">update</span>')
    return (f'<a class="ix{" fu" if follow else ""}" href="{esc(p["id"])}.html">'
            f'<span class="ixd">{esc(p["date"])}</span>'
            f'<span class="ixt"><span class="t">{title}</span><span class="b">{plural(p["builds"], "build")}</span></span>'
            f'<span class="ixh">{faces}</span><span class="ixs">{dirs}</span>'
            f'<span class="ixa">{audit}{_bar(c)}</span></a>')


def patch_tabs(active: str) -> str:
    """The patch list and its calendar (Sloppy's Patches / Calendar pair)."""
    return '<div class="flex table-tabs">' + ''.join(
        f'<a class="px-btn{" on" if k == active else ""}" href="{k}.html">{lbl}</a>'
        for k, lbl in (('index', 'List'), ('calendar', 'Calendar'), ('errata', 'Notes vs files'))) + '</div>'


def index_page(index: list[dict]) -> str:
    """Patches by month; a follow-up sits under its parent; each row says which way the
    patch went and who it hit."""
    from .trail import patch_stats
    stats = patch_stats()
    rel = '../'
    # a thread's follow-ups stay with their parent (06-30 Update and its 07-01..07-28 follow-ups),
    # families newest first, the month taken from the parent
    families: dict[str, list[dict]] = {}
    for p in index:
        families.setdefault(p['title'].split(' · follow-up ')[0], []).append(p)
    ordered = []
    for fam in families.values():
        parent = next((p for p in fam if ' · follow-up ' not in p['title']), fam[0])
        follows = sorted((p for p in fam if p is not parent), key=lambda p: p['date'], reverse=True)
        ordered.append((parent, follows))
    ordered.sort(key=lambda pf: pf[0]['date'], reverse=True)
    month_n: dict[str, int] = {}
    for parent, _ in ordered:
        month_n[parent['date'][:7]] = month_n.get(parent['date'][:7], 0) + 1
    out, month = [], None
    for parent, follows in ordered:
        m = parent['date'][:7]
        if m != month:
            month = m
            n = month_n[m]
            out.append(f'<div class="banner sub"><span class="bt">{MONTHS[int(m[5:7]) - 1]} {m[:4]}</span>'
                       f'<span class="bc">{n} update{"s" if n != 1 else ""}</span></div>')
        out.append(_index_row(parent, stats, rel, False))
        out.extend(_index_row(f, stats, rel, True) for f in follows)
    body = f'<h1>Patches</h1>{patch_tabs("index")}<div class="ixlist">{"".join(out)}</div>'
    return page('Patches', body, rel, 'patches')


def build_all() -> int:
    from . import archive
    index = archive.index()
    for i, row in enumerate(index):
        p = archive.patch(row['id'])
        prev = index[i - 1] if i > 0 else None
        nxt = index[i + 1] if i + 1 < len(index) else None
        write(f'patches/{row["id"]}.html', patch_page(p, prev, nxt))
    write('patches/index.html', index_page(index))
    from .calendar_page import calendar_page
    write('patches/calendar.html', calendar_page(patch_tabs('calendar')))
    from .errata_page import errata_page
    write('patches/errata.html', errata_page(patch_tabs('errata')))
    return len(index)
