"""Shared page shell and helpers for every builder."""
from __future__ import annotations

import gzip
import hashlib
import html
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
SITE = ROOT / 'site'
ICONS = ROOT / 'icons'
DIST = ROOT / 'dist'

FONTS = ('https://fonts.googleapis.com/css2?family=Jacquard+24&family=Pixelify+Sans:wght@400..700'
         '&family=Silkscreen:wght@400;700&display=swap')

NAV = (
    ('patches', 'Patches', 'patches/index.html'),
    ('builds', 'Builds', 'builds/index.html'),
    ('heroes', 'Heroes', 'heroes/index.html'),
    ('items', 'Items', 'items/index.html'),
    ('units', 'Units', 'units/index.html'),
    ('tables', 'Hero Stats', 'tables/heroes.html'),
)

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

STATUS_MARK = {
    'fix': ('fix', WRENCH_SVG, 'Bug fix in the patch notes'),
    'hidden': ('hidden', EYE_SVG, 'Not in the patch notes — found only in the game files'),
    'documented': ('documented', CHECK_SVG, 'Patch notes list these exact numbers'),
    'rounded': ('rounded', CHECK_SVG, 'Patch notes list rounded numbers; exact values from the files are shown'),
    'described': ('described', TILDE_SVG, 'Covered by a patch-note line without exact numbers'),
    'mismatch': ('mismatch', BANG_SVG, 'Patch notes give different numbers than the game files'),
}


def esc(s) -> str:
    return html.escape('' if s is None else str(s), quote=True)


def mark(status: str) -> str:
    cls, svg, tip = STATUS_MARK.get(status, STATUS_MARK['hidden'])
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
    return icon(f'heroes:{hid}', rel)


def entity_icon(file: str, eid: str, kind: str, rel: str) -> str | None:
    if file == 'heroes.vdata':
        return hero_icon(eid, rel)
    if file == 'abilities.vdata':
        return icon(f'item:{eid}', rel) or icon(f'ability:{eid}', rel)
    if file == 'npc_units.vdata':
        return icon(f'unit:{eid}', rel)
    return None


def img(src: str | None, alt: str = '', cls: str = '') -> str:
    if not src:
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
         description: str = '') -> str:
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
<link rel="stylesheet" href="{rel}styles.css?v={ver}">
</head>
<body>
<nav class="top-nav"><div class="nav-inner">
<a class="nav-brand" href="{rel}index.html"><span class="mark hidden eye-logo">{EYE_SVG}</span><span class="nav-brand-text">Cyclopean<small>deadlock.vpk</small></span></a>
<div class="nav-tabs">{tabs}</div>
{build_s}
</div></nav>
<main class="page">
{body}
</main>
<footer class="site-foot">Data: SteamTracking GameTracking-Deadlock, Steam News, the official Deadlock forum; icons from the game files. Not affiliated with Valve. · <a href="{rel}changelog.html">Site changelog</a> · <a href="https://github.com/sikleq/Cyclopean" rel="noopener">Source</a></footer>
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
def build_pages() -> dict[str, str]:
    """{build record file name: page stem}. Stem = build number, '-2' etc. when a
    build number was committed more than once by the tracker."""
    seen: dict[int, int] = {}
    out = {}
    for r in load_json('builds/index.json'):
        n = seen.get(r['build'], 0) + 1
        seen[r['build']] = n
        out[r['file']] = str(r['build']) if n == 1 else f'{r["build"]}-{n}'
    return out


def build_href(file_name: str, rel: str) -> str:
    return f'{rel}builds/{build_pages().get(file_name, file_name.split("_")[0])}.html'


def fmt_date(iso: str) -> str:
    return (iso or '')[:10]
