"""Official patch notes from the Steam News API (appid 1422450).

Steam announcements carry the full patch text as BBCode and start on
2024-10-24. Earlier notes (Aug–Oct 2024) exist only on the Deadlock forum and
are imported separately into data/notes/forum/*.txt.

    python -m pipeline.news     # refresh data/notes/steam.json
"""
from __future__ import annotations

import html
import json
import re
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone

from . import tracker

APPID = 1422450
API = ('https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/'
       f'?appid={APPID}&count=500&maxlength=0&feeds=steam_community_announcements&format=json')
OUT = tracker.ROOT / 'data' / 'notes' / 'steam.json'
FORUM_DIR = tracker.ROOT / 'data' / 'notes' / 'forum'


def fetch() -> list[dict]:
    req = urllib.request.Request(API, headers={'User-Agent': 'cyclopean-site-builder'})
    with urllib.request.urlopen(req, timeout=60) as r:
        items = json.load(r)['appnews']['newsitems']
    keep = ('gid', 'title', 'url', 'date', 'contents', 'feedname')
    return [{k: it.get(k) for k in keep} for it in items]


_CHANGE_LINE = re.compile(
    r'(\bfrom\b.+\bto\b|increas|decreas|reduc|lower|raise|fixed|no longer|\bnow\b|added|removed|'
    r'changed|improved|adjusted|updated|reworked|->|→)', re.I)


def is_changelog_text(lines: list[str]) -> bool:
    """A changelog lists changes; hero reveals / event posts are prose."""
    return sum(1 for ln in lines if _CHANGE_LINE.search(ln)) >= 5


def refresh() -> list[dict]:
    items = fetch()
    old = json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else []
    by_gid = {it['gid']: it for it in old}
    by_gid.update({it['gid']: it for it in items})   # Steam only returns recent ones
    for it in by_gid.values():
        # marketing posts (hero reveals, events) keep title + link only
        if it.get('contents') and not is_changelog_text(bbcode_lines(it['contents'])):
            it['contents'] = ''
    merged = sorted(by_gid.values(), key=lambda it: it['date'])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
    return merged


# ---- BBCode -> structured lines ------------------------------------------

@dataclass
class Section:
    title: str
    lines: list[str] = field(default_factory=list)


@dataclass
class Notes:
    title: str
    date: str          # YYYY-MM-DD (publication, UTC)
    url: str
    source: str        # steam | forum
    sections: list[Section]

    def all_lines(self):
        for s in self.sections:
            for ln in s.lines:
                yield s.title, ln


_TAG_RE = re.compile(r'\[/?(?:b|i|u|p|h\d|list|olist|url[^\]]*|img[^\]]*|previewyoutube[^\]]*|hr|strike|spoiler|quote[^\]]*|code|table|tr|td|th)\]', re.I)
_SECTION_RE = re.compile(r'^\[\s*(.+?)\s*\]$')


def bbcode_lines(text: str) -> list[str]:
    t = text.replace('\\[', '\x00').replace('\\]', '\x01')
    t = re.sub(r'\[\*\]', '\n', t)
    t = re.sub(r'\[/p\]|\[br\]|\[/h\d\]|\[/list\]|\[/olist\]', '\n', t, flags=re.I)
    t = _TAG_RE.sub('', t)
    t = html.unescape(t).replace('\x00', '[').replace('\x01', ']')
    return [ln.strip() for ln in t.splitlines() if ln.strip()]


def parse_lines(lines: list[str]) -> list[Section]:
    sections = [Section('General')]
    for ln in lines:
        m = _SECTION_RE.match(ln)
        if m:
            sections.append(Section(m.group(1).strip()))
            continue
        ln = re.sub(r'^[-•*]\s*', '', ln)
        if sections[-1].lines and not re.match(r'^[A-Z0-9"\'(]', ln) and not sections[-1].lines[-1].endswith(('.', ')')):
            # wrapped continuation of the previous bullet
            sections[-1].lines[-1] += ' ' + ln
        else:
            sections[-1].lines.append(ln)
    return [s for s in sections if s.lines]


_TITLE_DATE = re.compile(r'(\d{2})-(\d{2})-(\d{4})')


def title_date(title: str) -> str | None:
    """'Minor Update - 06-11-2026' -> '2026-06-11' (the US patch day, not the UTC post time)."""
    m = _TITLE_DATE.search(title)
    return f'{m.group(3)}-{m.group(1)}-{m.group(2)}' if m else None


def steam_notes() -> list[Notes]:
    items = json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else []
    out = []
    for it in items:
        date = title_date(it['title']) or datetime.fromtimestamp(it['date'], timezone.utc).strftime('%Y-%m-%d')
        out.append(Notes(it['title'], date, it['url'], 'steam', parse_lines(bbcode_lines(it['contents']))))
    return out


NOT_CHANGELOGS = {'changelog feedback process'}
_SERVICE_LINE = re.compile(r'^(@@|Source: Steam News|View attachment)', re.I)


def forum_notes() -> list[Notes]:
    """Imported forum threads: data/notes/forum/<YYYY-MM-DD>[-n].txt, line 1 = title, line 2 = url.
    Threads whose first post only linked to Steam carry the Steam text after a
    'Source: Steam News …' line; author follow-ups follow '[ Follow-up <date> ]'."""
    out = []
    for p in sorted(FORUM_DIR.glob('*.txt')):
        raw = p.read_text(encoding='utf-8').splitlines()
        title, url, body = raw[0], raw[1], raw[2:]
        if title.strip().lower() in NOT_CHANGELOGS:
            continue
        lines = [ln for ln in body if ln.strip() and not _SERVICE_LINE.match(ln.strip())]
        # author follow-ups shipped in later builds: each becomes its own notes
        chunks: list[tuple[str, list[str]]] = [(p.stem[:10], [])]
        for ln in lines:
            m = _FOLLOW_UP.match(ln.strip())
            if m:
                chunks.append((m.group(1), []))
            else:
                chunks[-1][1].append(ln)
        for i, (date, chunk) in enumerate(chunks):
            if not chunk:
                continue
            if i == 0:
                out.append(Notes(title, date, url, 'forum', parse_lines(chunk)))
            else:
                out.append(Notes(f'{title} · follow-up {date}', date, f'{url}#follow-up-{date}', 'forum',
                                 parse_lines(chunk)))
    return out


_FOLLOW_UP = re.compile(r'^\[\s*Follow-up\s+(\d{4}-\d{2}-\d{2})\s*\]$', re.I)


def all_notes() -> list[Notes]:
    seen = set()
    result = []
    for n in sorted(forum_notes() + steam_notes(), key=lambda n: n.date):
        key = (n.date, n.title.lower())
        if key in seen:
            continue
        seen.add(key)
        result.append(n)
    return result


if __name__ == '__main__':
    items = refresh()
    print(f'{len(items)} announcements -> {OUT}')
