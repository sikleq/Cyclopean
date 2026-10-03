"""Shared page shell and helpers for every builder."""
from __future__ import annotations

import gzip
import hashlib
import html
import json
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
SITE = ROOT / 'site'
ICONS = ROOT / 'icons'
DIST = ROOT / 'dist'

# Jersey 20: headings, names, big numbers (unambiguous pixel digits); VT323: labels and
# badges at 16px+; IBM Plex Sans: body text and table numbers (design review 2026-10-01)
FONTS = ('https://fonts.googleapis.com/css2?family=Jacquard+24&family=Jersey+20&family=VT323'
         '&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap')

# the site is about what changed on each hero, item and unit (owner, 2026-10-03: "closer to Sloppy"):
# three sections; patches, builds, the calendar and Notes vs files are still built but live off the bar
NAV = (
    ('heroes', 'Heroes', 'heroes/index.html'),
    ('items', 'Items', 'items/index.html'),
    ('units', 'Units', 'units/index.html'),
)
# each section: its index, its stats table, its change matrix (Sloppy's Materials / Dynamics)
SECTION_TABS = {
    'heroes': (('index', 'Heroes', 'heroes/index.html'), ('stats', 'Hero Stats', 'tables/heroes.html'),
               ('changes', 'Hero changes', 'heroes/changes.html')),
    'items': (('index', 'Shop', 'items/index.html'), ('stats', 'Item Stats', 'tables/items.html'),
              ('changes', 'Item changes', 'items/changes.html')),
    'units': (('index', 'Units', 'units/index.html'), ('stats', 'Unit Stats', 'tables/units.html'),
              ('changes', 'Unit changes', 'units/changes.html')),
}


def section_tabs(section: str, active: str, rel: str = '../') -> str:
    return '<div class="flex table-tabs">' + ''.join(
        f'<a class="px-btn{" on" if k == active else ""}" href="{rel}{href}">{esc(lbl)}</a>'
        for k, lbl, href in SECTION_TABS[section]) + '</div>'

EYE_SVG = ('<svg viewBox="0 0 16 16" shape-rendering="crispEdges" aria-hidden="true"><path fill="currentColor" '
           'd="M5 4h6v1H5zM3 5h2v1H3zM11 5h2v1h-2zM1 6h2v1H1zM13 6h2v1h-2zM0 7h1v2H0zM15 7h1v2h-1zM1 9h2v1H1z'
           'M13 9h2v1h-2zM3 10h2v1H3zM11 10h2v1h-2zM5 11h6v1H5zM6 6h4v4H6z"/></svg>')
CHECK_SVG = ('<svg viewBox="0 0 16 16" shape-rendering="crispEdges" aria-hidden="true"><path fill="currentColor" '
             'd="M13 3h2v2h-2zM11 5h2v2h-2zM9 7h2v2H9zM7 9h2v2H7zM3 7h2v2H3zM5 9h2v2H5z"/></svg>')
BANG_SVG = ('<svg viewBox="0 0 16 16" shape-rendering="crispEdges" aria-hidden="true"><path fill="currentColor" '
            'd="M7 2h2v8H7zM7 12h2v2H7z"/></svg>')
TILDE_SVG = ('<svg viewBox="0 0 16 16" shape-rendering="crispEdges" aria-hidden="true"><path fill="currentColor" '
             'd="M2 8h2v2H2zM4 6h3v2H4zM7 8h2v2H7zM9 8h3v2H9zM12 6h2v2h-2z"/></svg>')

WRENCH_SVG = ('<svg viewBox="0 0 16 16" shape-rendering="crispEdges" aria-hidden="true"><path fill="currentColor" '
              'd="M10 2h3v1h-3zM9 3h2v3H9zM13 3h1v3h-1zM11 6h2v1h-2zM8 6h2v2H8zM6 8h2v2H6zM4 10h2v2H4zM2 12h2v2H2z"/></svg>')

FLASK_SVG = ('<svg viewBox="0 0 16 16" shape-rendering="crispEdges" aria-hidden="true"><path fill="currentColor" '
             'd="M5 2h6v1H5zM6 3h1v4H6zM9 3h1v4H9zM5 7h1v1H5zM10 7h1v1h-1zM4 8h1v2H4zM11 8h1v2h-1zM3 10h1v3H3z'
             'M12 10h1v3h-1zM3 13h10v1H3zM4 11h8v2H4z"/></svg>')
NOTES_OFF_SVG = ('<svg viewBox="0 0 16 16" shape-rendering="crispEdges" aria-hidden="true"><path fill="currentColor" '
                 'd="M3 1h7v1H3zM3 2h1v12H3zM10 2h1v1h-1zM11 3h1v1h-1zM12 4h1v10h-1zM3 14h10v1H3zM6 6h1v1H6zM9 6h1v1H9z'
                 'M6 10h4v1H6zM5 11h1v1H5zM10 11h1v1h-1z"/></svg>')

NA_SVG = ('<svg viewBox="0 0 16 16" shape-rendering="crispEdges" aria-hidden="true"><path fill="currentColor" '
          'd="M6 2h4v1H6zM4 3h2v1H4zM10 3h2v1h-2zM3 4h1v2H3zM12 4h1v2h-1zM2 6h1v4H2zM13 6h1v4h-1zM3 10h1v2H3z'
          'M12 10h1v2h-1zM4 12h2v1H4zM10 12h2v1h-2zM6 13h4v1H6zM10 5h1v1h-1zM9 6h1v1H9zM8 7h1v1H8zM7 8h1v1H7z'
          'M6 9h1v1H6zM5 10h1v1H5z"/></svg>')

# "</>": the change lives in the game's code, not in the data files compared here
CODE_SVG = ('<svg viewBox="0 0 16 16" shape-rendering="crispEdges" aria-hidden="true"><path fill="currentColor" '
            'd="M4 4h2v1H4zM3 5h2v1H3zM2 6h2v1H2zM1 7h2v2H1zM2 9h2v1H2zM3 10h2v1H3zM4 11h2v1H4z'
            'M10 4h2v1h-2zM11 5h2v1h-2zM12 6h2v1h-2zM13 7h2v2h-2zM12 9h2v1h-2zM11 10h2v1h-2zM10 11h2v1h-2z'
            'M9 2h1v3H9zM8 5h1v3H8zM7 8h1v3H7zM6 11h1v3H6z"/></svg>')

STATUS_MARK = {
    'code': ('code', CODE_SVG, "No game file of this changed in the update: the change is in the game's code, "
                               'which is not compared here'),
    'untracked': ('untracked', NA_SVG, 'Sound, effects, interface or map: not part of the game data compared here'),
    'nodata': ('nodata', NA_SVG, 'No game files survive for this date — nothing to compare with'),
    'repeated': ('repeated', TILDE_SVG, 'The post was edited later: this line belongs to a later update'),
    'fix': ('fix', WRENCH_SVG, 'Bug fix in the patch notes'),
    'hidden': ('hidden', EYE_SVG, 'Not in the patch notes — found only in the game files'),
    'unreleased': ('unreleased', FLASK_SVG, 'Hero still in development at this build — not in the patch notes'),
    'unannounced': ('unannounced', NOTES_OFF_SVG, 'Update shipped without patch notes — found only in the game files'),
    'documented': ('documented', CHECK_SVG, 'Patch notes list these exact numbers'),
    'rounded': ('rounded', CHECK_SVG, 'Patch notes list rounded numbers; exact values from the files are shown'),
    'described': ('described', TILDE_SVG, 'Covered by a patch-note line without exact numbers'),
    'mismatch': ('mismatch', BANG_SVG, 'Patch notes give different numbers than the game files'),
}


def plural(n: int, word: str, many: str | None = None) -> str:
    """'1 build', '3 builds' — never '1 builds' (audit 2026-10-01: thousands of tooltips)."""
    return f'{n} {word if n == 1 else many or word + "s"}'


def esc(s) -> str:
    return html.escape('' if s is None else str(s), quote=True)


def mark(status: str) -> str:
    if status not in STATUS_MARK:
        return '<span class="mark"></span>'       # e.g. raw build-page changes: no notes to compare with
    cls, svg, tip = STATUS_MARK[status]
    return f'<span class="mark {cls}" data-tooltip="{esc(tip)}">{svg}</span>'


@lru_cache(maxsize=1)
def icon_manifest() -> dict[str, str]:
    p = ICONS / 'manifest.json'
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}


def icon(key: str, rel: str) -> str | None:
    """Icon URL for manifest key ('heroes:hero_haze', 'item:upgrade_x', 'ability:x', 'unit:x')."""
    path = icon_manifest().get(key)
    return f'{rel}icons/{path}' if path else None


def hero_icon(hid: str, rel: str) -> str | None:
    # heroes in development often ship only a minimap or card image
    return icon(f'heroes:{hid}', rel) or icon(f'heroes/minimap:{hid}', rel) or icon(f'heroes/card:{hid}', rel)


@lru_cache(maxsize=1)
def names_by_id() -> dict[str, str]:
    """lower-case entity id -> its latest localized name (only entities that have one)."""
    return {e['id'].lower(): e['name'] for e in load_json('entities.json')['entities']
            if e.get('name') and e['name'] != e['id']}


# lower-case only: 'CITADEL_ABILITY_BEHAVIOR_*' flags are not entity ids
_ID_IN_TEXT = re.compile(r'\b(?:citadel_(?:ability|weapon)_|ability_|upgrade_|hero_)[a-z0-9_]+\b')
# any other snake_case word is an id only if the catalog knows it: a hero in development names its
# abilities after itself ("Kit: Ultimate slork_ability_invis → fathom_reefdweller_harpoon", 2026-10-02)
_SNAKE_WORD = re.compile(r'\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b')


@lru_cache(maxsize=1)
def _catalog_owners() -> dict[str, str | None]:
    """lower-case id of every ability / hero / unit -> its owner hero (for a readable stand-in).
    Not a template: '_base: invis_base' names an engine class, not a thing a player sees."""
    return {e['id'].lower(): e.get('owner') for e in load_json('entities.json')['entities']
            if e['file'] in ('abilities.vdata', 'heroes.vdata', 'npc_units.vdata') and not e.get('template')}


def ids_to_names(s: str) -> str:
    """'ability_blood_bomb, ability_blood_shards' -> 'Blood Bomb, Blood Shards' in shown values."""
    names = names_by_id()
    s = _ID_IN_TEXT.sub(lambda m: names.get(m.group(0).lower()) or pretty_id(m.group(0)), s)
    known = _catalog_owners()

    def other(m: re.Match) -> str:
        w = m.group(0)
        return names.get(w) or pretty_id(w, known[w]) if w in known else w
    return _SNAKE_WORD.sub(other, s)


_ID_PREFIX = re.compile(r'^(citadel_ability_|citadel_weapon_|citadel_|ability_|upgrade_|npc_)')


def display_name(e: dict) -> str:
    """An entity's localized name, else a readable stand-in — never its id ('hero_airheart' sat in an h1)."""
    name = e.get('name')
    return name if name and name != e['id'] else pretty_id(e['id'], e.get('owner'))


def pretty_id(eid: str, owner: str | None = None) -> str:
    """A readable stand-in for an entity that has no localized name yet (heroes in
    development): internal ids are never shown. 'citadel_weapon_frank_set' -> 'Weapon',
    'ability_druid_sprout' -> 'Sprout', 'ability_doorman_ult' -> 'Ultimate'."""
    if eid.startswith('citadel_weapon_'):
        return 'Alt weapon' if eid.endswith(('_alt', '_set2', '_set_2')) else 'Weapon'
    if eid.startswith('m_'):                 # a game-rules block: 'm_RejuvParams' -> 'Rejuv Params'
        from pipeline.semantics import humanize
        return humanize(eid)
    if eid.startswith('hero_'):              # a hero with no name yet: 'hero_airheart' -> 'Airheart'
        return eid[5:].replace('_', ' ').title()
    s = _ID_PREFIX.sub('', eid)
    code = (owner or '').removeprefix('hero_')
    if code and s.startswith(code + '_'):
        s = _ID_PREFIX.sub('', s[len(code) + 1:])         # 'slork_ability_invis' -> 'invis'
    s = re.sub(r'^tier\dboss_', '', s)                    # a boss's own: 'tier2boss_aoe_wave' -> 'Aoe wave'
    s = re.sub(r'^ult(imate)?$', 'ultimate', s)
    s = re.sub(r'ability0?(\d)', r'ability \1', s).replace('_', ' ').strip()
    return s[:1].upper() + s[1:] if s else eid


def _ability_icon_key(eid: str) -> str | None:
    man = icon_manifest()
    return next((k for k in (f'item:{eid}', f'ability:{eid}') if k in man), None)


@lru_cache(maxsize=1)
def _icon_by_name() -> dict[tuple, str]:
    """(owner, lower-case name) -> manifest key of an ability that has art. Valve
    re-creates abilities under new ids (the same 'Seismic Impact' under two ids across
    patches); the id without art borrows its namesake's, never across owners."""
    out: dict[tuple, str] = {}
    for e in load_json('entities.json')['entities']:
        if e['file'] != 'abilities.vdata' or not e.get('name') or e['name'] == e['id']:
            continue
        key = _ability_icon_key(e['id'])
        if key:
            out.setdefault((e.get('owner'), e['name'].lower()), key)
    return out


def entity_icon(file: str, eid: str, kind: str, rel: str, name: str | None = None,
                owner: str | None = None) -> str | None:
    if file == 'heroes.vdata':
        return hero_icon(eid, rel)
    if file == 'abilities.vdata':
        key = _ability_icon_key(eid)
        if not key and name and name != eid:
            key = _icon_by_name().get((owner, name.lower()))
        return icon(key, rel) if key else None
    if file == 'npc_units.vdata':
        return icon(f'unit:{eid}', rel)
    if file == 'misc.vdata':
        return icon(f'misc:{eid}', rel)
    return None


# Category glyphs (site UI, not game art) for rows that stand for a group or a rule,
# never for one entity: "All heroes (24)", game rules, map objects without art.
_G = '<svg viewBox="0 0 16 16" shape-rendering="crispEdges" aria-hidden="true"><path fill="currentColor" fill-rule="evenodd" d="{}"/></svg>'
GLYPHS = {
    'heroes': 'M6 2h4v4H6zM2 4h3v3H2zM11 4h3v3h-3zM5 7h6v7H5zM1 8h3v5H1zM12 8h3v5h-3z',
    'hero': 'M5 2h6v5H5zM3 8h10v6H3z',
    'abilities': 'M7 1h2v4H7zM7 11h2v4H7zM1 7h4v2H1zM11 7h4v2h-4zM6 6h4v4H6zM3 3h2v2H3zM11 3h2v2h-2zM3 11h2v2H3zM11 11h2v2h-2z',
    'units': 'M6 1h4v4H6zM4 6h8v5H4zM4 11h3v4H4zM9 11h3v4H9zM13 2h1v10h-1z',
    'map': 'M2 3h12v11H2zM3 4h10v9H3zM4 5h2v2H4zM6 7h2v2H6zM8 9h2v2H8zM10 11h2v1h-2z',
    'modifier': 'M7 1h2v1H7zM6 2h4v1H6zM5 3h6v1H5zM4 4h8v1H4zM3 5h10v1H3zM6 6h4v9H6z',
    # even-odd fill: shapes must not overlap, an inner rect punches a hole (gear axle, chest lock)
    'rules': 'M7 1h2v2H7zM7 13h2v2H7zM1 7h2v2H1zM13 7h2v2h-2zM3 3h2v2H3zM11 3h2v2h-2zM3 11h2v2H3zM11 11h2v2h-2z'
             'M5 4h6v1H5zM4 5h8v6H4zM5 11h6v1H5zM7 7h2v2H7z',
    'loot': 'M3 3h10v3H3zM2 6h12v8H2zM7 8h2v3H7z',
    # home navigation tiles
    'book': 'M1 3h6v10H1zM9 3h6v10H9zM2 4h4v1H2zM10 4h4v1h-4zM2 6h4v1H2zM10 6h4v1h-4zM2 8h4v1H2zM10 8h4v1h-4z'
            'M7 13h2v1H7z',
    'table': 'M1 2h14v12H1zM2 5h3v2H2zM6 5h3v2H6zM10 5h4v2h-4zM2 8h3v2H2zM6 8h3v2H6zM10 8h4v2h-4zM2 11h3v2H2z'
             'M6 11h3v2H6zM10 11h4v2h-4z',
}
_SHARED_GLYPH = {'heroes.vdata': 'heroes', 'abilities.vdata': 'abilities', 'npc_units.vdata': 'units',
                 'misc.vdata': 'map', 'modifiers.vdata': 'modifier'}


def glyph_for(file: str, eid: str, kind: str = '') -> str:
    if eid == '@shared':
        return _SHARED_GLYPH.get(file, 'rules')
    return {'heroes.vdata': 'hero', 'abilities.vdata': 'abilities', 'npc_units.vdata': 'units',
            'misc.vdata': 'map', 'modifiers.vdata': 'modifier', 'loot_tables.vdata': 'loot'}.get(file, 'rules')


def visual(src: str | None, glyph: str, cls: str = 'px') -> str:
    """The game's icon if there is one, else the category glyph in the same box."""
    if src:
        return f'<img class="{esc(cls)}" src="{esc(src)}" alt="" loading="lazy">'
    return f'<span class="{esc(cls)} glyph g-{esc(glyph)}">{_G.format(GLYPHS.get(glyph, GLYPHS["rules"]))}</span>'


def img(src: str | None, alt: str = '', cls: str = '', glyph: str | None = None) -> str:
    if not src:
        if glyph:
            return visual(None, glyph, cls or 'px')
        return f'<span class="{esc(cls)} noimg"></span>' if cls else ''
    c = f' class="{esc(cls)}"' if cls else ''
    return f'<img{c} src="{esc(src)}" alt="{esc(alt)}" loading="lazy">'


def slug(file: str, eid: str) -> str:
    if file == 'heroes.vdata':
        return 'heroes/' + eid.removeprefix('hero_') + '.html'
    if file == 'abilities.vdata' and eid.startswith('upgrade_'):
        return 'items/' + eid.removeprefix('upgrade_') + '.html'
    if file == 'npc_units.vdata':
        return 'units/' + eid + '.html'
    return ''


@lru_cache(maxsize=1)
def asset_version() -> str:
    h = hashlib.sha1()
    for name in ('styles.css', 'scripts.js'):
        h.update((SITE / name).read_bytes())
    return h.hexdigest()[:10]


def page(title: str, body: str, rel: str = '', active: str = '', build: int | None = None,
         description: str = '', wide: bool = False, fonts: str = '') -> str:
    """`fonts`: one more Google Fonts stylesheet for this page only (the shop's stand-ins)."""
    tabs = ''.join(
        f'<a class="nav-tab{" active" if key == active else ""}" href="{rel}{href}">{label}</a>'
        for key, label, href in NAV)
    ver = asset_version()
    build_s = f'<span class="nav-build">build {build}</span>' if build else ''
    desc = f'<meta name="description" content="{esc(description)}">' if description else ''
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · Cyclopean</title>
{desc}
<link rel="icon" type="image/svg+xml" href="{rel}favicon.svg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
{f'<link rel="stylesheet" href="{esc(fonts)}">' if fonts else ''}
<link rel="stylesheet" href="{rel}styles.css?v={ver}">
</head>
<body>
<nav class="top-nav"><div class="nav-inner">
<a class="nav-brand" href="{rel}index.html"><span class="mark hidden eye-logo">{EYE_SVG}</span><span class="nav-brand-text">Cyclopean<small>deadlock.vpk</small></span></a>
<div class="nav-tabs">{tabs}</div>
{build_s}
</div></nav>
<main class="page{' wide' if wide else ''}">
{body}
</main>
<footer class="site-foot">Data: SteamTracking GameTracking-Deadlock, Steam News, the official Deadlock forum; icons from the game files. Not affiliated with Valve. · <a href="{rel}patches/index.html">Patch archive</a> · <a href="{rel}changelog.html">Site changelog</a> · <a href="https://github.com/sikleq/Cyclopean" rel="noopener">Source</a></footer>
<script src="{rel}scripts.js?v={ver}"></script>
</body>
</html>
'''


def write(rel_path: str, content: str) -> None:
    out = DIST / rel_path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding='utf-8')


def load_json(rel: str):
    p = DATA / rel
    if p.name.endswith('.gz'):
        with gzip.open(p, 'rt', encoding='utf-8') as f:
            return json.load(f)
    return json.loads(p.read_text(encoding='utf-8'))


@lru_cache(maxsize=1)
def cosmetics() -> dict:
    """data/cosmetics.json (pipeline/cosmetics.py): skin-system groundwork by build and by hero."""
    p = DATA / 'cosmetics.json'
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {'events': [], 'heroes': {}}


COSMETIC_KINDS = {'base body': 'Base body (what a skin is put on)', 'cosmetic animation': 'Cosmetic animation',
                  'cosmetic sounds': 'Cosmetic sounds', 'cosmetic code': 'Cosmetic item code'}


@lru_cache(maxsize=1)
def build_pages() -> dict[str, str]:
    """{build record file name: page stem}. Stem = build number, '-2' etc. when a
    build number was committed more than once by the tracker."""
    seen: dict[int, int] = {}
    out = {}
    for r in load_json('builds/index.json'):
        if r['build'] is None:               # a tracker commit without a build number (texts only)
            out[r['file']] = 'text-' + r['file'].split('_', 1)[1].split('.', 1)[0]
            continue
        n = seen.get(r['build'], 0) + 1
        seen[r['build']] = n
        out[r['file']] = str(r['build']) if n == 1 else f'{r["build"]}-{n}'
    return out


def build_label(build: int | None) -> str:
    """'Build 6728', or 'Text update' for a tracker commit Valve shipped without a build number
    (2025-08-23: 498 texts; its page was 'Build None')."""
    return f'Build {build}' if build is not None else 'Text update'


def build_href(file_name: str, rel: str) -> str:
    return f'{rel}builds/{build_pages().get(file_name, file_name.split("_")[0])}.html'


def fmt_date(iso: str) -> str:
    return (iso or '')[:10]


# ---- patch titles: the date once; a named update shows its name -------------------------
_TITLE_DATE = re.compile(r'\b\d{2}-\d{2}-\d{4}\b|\b\d{4}-\d{2}-\d{2}\b')
FOLLOW_UP = ' · follow-up '


def patch_name(title: str) -> str | None:
    """The update's own name without dates: 'City Never Sleeps · 09-29-2026' -> 'City Never Sleeps',
    'Gameplay Update - 03-06-2026' -> 'Gameplay Update'; '09-16-2026 Update' has none (its only
    name was the date, which the site shows anyway). A follow-up carries its parent's name."""
    base = title.split(FOLLOW_UP)[0]
    rest = _TITLE_DATE.sub(' ', base)
    rest = re.sub(r'[\s·\-–—]+', ' ', rest).strip()
    return None if rest.lower() in ('', 'update', 'patch', 'patch notes') else rest


def patch_parts(row: dict) -> tuple[str | None, str, bool]:
    """(name or None, ISO date, is a follow-up) for a patch index row."""
    return patch_name(row['title']), fmt_date(row['date']), FOLLOW_UP in row['title']


def patch_title_text(row: dict) -> str:
    """Plain text for tooltips and <title>: 'City Never Sleeps · 2026-09-29', '2026-09-16 update'."""
    name, date, follow = patch_parts(row)
    out = f'{name} · {date}' if name else f'{date} update'
    return out + (' · follow-up' if follow else '')


def patch_title_html(row: dict) -> str:
    """A named update: its name highlighted, then the date; otherwise the date alone."""
    name, date, follow = patch_parts(row)
    fu = '<span class="pfu">follow-up</span>' if follow else ''
    if name:
        return f'<span class="pname">{esc(name)}</span><span class="pdate">{esc(date)}</span>{fu}'
    return f'<span class="pdate solo">{esc(date)}</span><span class="pkind">update</span>{fu}'
