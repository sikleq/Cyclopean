"""Big updates (City Never Sleeps, Old Gods, New Blood) publish their change list as a designed web
page, not as text notes: the page's words live in a webpack chunk '<slug>_english.json' that the
browser loads. This module fetches that chunk and turns it into an ordinary notes file
(data/notes/forum/<date>.txt) by the rules in data/overrides/update_pages.json:

- the plain changelog part ('Additional Update Notes') verbatim;
- feature cards as 'Title: Body' (one change each);
- lore (landmark stories, monster bios, taglines) never — only the names it introduces, as one list
  line per block ('Haunts: Specimen, Gutter Ghouls, …'). Marketing text is not republished.
"""
from __future__ import annotations

import json
import re
from html import unescape
import urllib.request
from pathlib import Path

from . import tracker

RULES = tracker.ROOT / 'data' / 'overrides' / 'update_pages.json'
NOTES_DIR = tracker.ROOT / 'data' / 'notes' / 'forum'
SITE = 'https://www.playdeadlock.com'
_TAG = re.compile(r'</?\d+>|<[^>]+>')
_SPACES = re.compile(r'\s+')


def clean(text: str) -> str:
    """Page markup out ('<1>Updated item art</1>' -> 'Updated item art'), one line."""
    return _SPACES.sub(' ', _TAG.sub('', str(text))).strip()


# ---- fetching -------------------------------------------------------------------------------

def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={'User-Agent': 'cyclopean (+https://github.com/sikleq/Cyclopean)'})
    with urllib.request.urlopen(req, timeout=30) as r:          # noqa: S310 (fixed https host)
        return r.read().decode('utf-8', 'replace')


def fetch(slug: str) -> dict[str, str]:
    """The page's text keys. The chunk's file name carries a content hash that changes when Valve
    edits the text, so it is looked up every time: page -> main.js -> manifest.js -> chunk."""
    page = _get(f'{SITE}/{slug}')
    scripts = [unescape(s) for s in re.findall(r'src="((?:https://www\.playdeadlock\.com)?/public/javascript/react/[^"]+)"', page)]
    scripts = [s if s.startswith('http') else SITE + s for s in scripts]
    main = next((s for s in scripts if '/main.js' in s), None)
    manifest = next((s for s in scripts if '/manifest.js' in s), None)
    if not main or not manifest:
        raise RuntimeError(f'{slug}: no main.js/manifest.js on the page')
    main_js = _get(main)
    m = re.search(rf'"\./{re.escape(slug)}_english\.json":\[\d+,(\d+)\]', main_js)
    if not m:
        raise RuntimeError(f'{slug}: no {slug}_english.json chunk in main.js')
    chunk = m.group(1)
    manifest_js = _get(manifest)
    h = re.search(rf'\b{chunk}:"([0-9a-f]{{8,}})"', manifest_js)
    if not h:
        raise RuntimeError(f'{slug}: chunk {chunk} has no content hash in manifest.js')
    chunk_js = _get(f'{SITE}/public/javascript/react/{chunk}.js?contenthash={h.group(1)}')
    j = re.search(r"JSON\.parse\('(.*)'\)", chunk_js, re.S)
    if not j:
        raise RuntimeError(f'{slug}: chunk {chunk} holds no JSON.parse')
    raw = j.group(1).encode('utf-8').decode('unicode_escape').encode('latin-1').decode('utf-8')
    return json.loads(raw)


# ---- converting -------------------------------------------------------------------------------

def _cards(keys: list[str], text: dict[str, str], base_rx: str, skip: re.Pattern | None, prefix: str = '') -> list[str]:
    rx = re.compile(base_rx)
    out = []
    for k in keys:
        if not k.endswith('_Title'):
            continue
        base = k[:-len('_Title')]
        if not rx.search(base) or (skip and skip.search(base)):
            continue
        title, body = clean(text[k]), clean(text.get(base + '_Body', ''))
        out.append(prefix + (f'{title}: {body}' if body else title))
    return out


def _in_range(keys: list[str], rng: list[str] | None) -> list[str]:
    if not rng:
        return keys
    start = keys.index(rng[0]) if rng[0] in keys else 0
    end = keys.index(rng[1]) if len(rng) > 1 and rng[1] in keys else len(keys)
    return keys[start:end]


def to_lines(text: dict[str, str], rules: dict) -> list[str]:
    """The notes file body: '[ Section ]' headers and '- line' items, in the page's key order."""
    keys = list(text)
    skip = re.compile(rules['skip']) if rules.get('skip') else None
    out = []
    for sec in rules['sections']:
        lines: list[str] = []
        for item in sec['items']:
            scope = _in_range(keys, item.get('range'))
            if 'line' in item:
                try:
                    lines.append(clean(item['line'].format(**text)))
                except KeyError:
                    continue
            elif 'list' in item:
                names = [clean(text[k]) for k in scope if re.search(item['keys'], k)]
                if names:
                    lines.append(f'{item["list"]}: {", ".join(names)}')
            elif 'verbatim' in item:
                lines += [clean(text[k]) for k in scope if re.search(item['verbatim'], k)
                          and not (skip and skip.search(clean(text[k])))]
            elif 'cards' in item:
                lines += _cards(scope, text, item['cards'], re.compile(item['skip_cards']) if item.get('skip_cards') else None,
                                item.get('prefix', ''))
        lines = [ln for ln in lines if ln]
        if lines:
            out.append(f'[ {sec["title"]} ]')
            out += [f'- {ln}' for ln in lines]
    return out


def notes_text(text: dict[str, str], slug: str, rules: dict) -> str:
    head = [rules['title'], f'{SITE}/{slug}',
            f'Source: Official update page {SITE}/{slug} (page text; lore and taglines not republished)']
    return '\n'.join(head + to_lines(text, rules)) + '\n'


def write(slug: str, text: dict[str, str]) -> Path:
    rules = json.loads(RULES.read_text(encoding='utf-8'))[slug]
    path = NOTES_DIR / f'{rules["date"]}.txt'
    path.write_text(notes_text(text, slug, rules), encoding='utf-8', newline='\n')
    return path
