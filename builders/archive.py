"""The patch archive (data/patches), read and gunzipped ONCE per build.

Every builder that walks the patches (entity histories, the change matrices, the history squares, the home
feed, the patch, build and errata pages) used to load the 128 patch files itself: ~1,500 opens and gunzips
per build, 13 ms an open on Windows with an antivirus (python audit 2026-10-04: 56 s of a 244 s profile).

The cached objects are SHARED: a builder never writes into them (a page that needs an extra field on a
change or an entity copies it first, `{**c, ...}`), or the next builder would read what the last one wrote.
"""
from __future__ import annotations

from functools import lru_cache

from .common import load_json


@lru_cache(maxsize=1)
def index() -> list[dict]:
    """data/patches/index.json as stored (oldest first)."""
    return load_json('patches/index.json')


@lru_cache(maxsize=1)
def by_date() -> list[dict]:
    """The index rows sorted by date, oldest first."""
    return sorted(index(), key=lambda r: r['date'])


@lru_cache(maxsize=None)
def patch(pid: str) -> dict:
    """One patch record (data/patches/<id>.json.gz)."""
    return load_json(f'patches/{pid}.json.gz')


@lru_cache(maxsize=None)
def gameplay(pid: str) -> list[dict]:
    """The patch's entities as players read them (`cards.gameplay_entities`: gameplay rows only, repeated
    variants merged): the start of every list and counter."""
    from .cards import gameplay_entities
    return gameplay_entities(patch(pid)['entities'])


def builds_of(pid: str) -> list[dict]:
    """The patch's builds ([{build, date, file}], its window), none for a patch the archive does not hold."""
    try:
        return patch(pid).get('builds') or []
    except (OSError, KeyError):
        return []


@lru_cache(maxsize=None)
def note_lines(pid: str) -> tuple[dict[str, tuple[int, ...]], tuple[tuple[str, str, int], ...]]:
    """(change key -> the indices of the patch-note lines that name it, the lines as (text, status, how many
    entities they cover)): which of Valve's lines a row comes from (the match's own link, sections[].lines[].changes)."""
    try:
        p = patch(pid)
    except (OSError, KeyError):
        return {}, ()
    keys: dict[str, list[int]] = {}
    lines: list[tuple[str, str, int]] = []
    for s in p.get('sections') or ():
        for ln in s.get('lines') or ():
            ch = ln.get('changes') or ()
            if not ch:
                continue
            ents = {':'.join(k.split(':', 2)[:2]) for k in ch}
            for k in ch:
                keys.setdefault(k, []).append(len(lines))
            lines.append((ln['text'], ln.get('status') or '', len(ents)))
    return {k: tuple(v) for k, v in keys.items()}, tuple(lines)


@lru_cache(maxsize=None)
def note_anchors(pid: str) -> frozenset[str]:
    """The ids with a card in the patch page's Patch notes tab (notes_view.note_anchors); none for a patch the
    archive does not hold (a test's)."""
    from .notes_view import note_anchors as anchors
    try:
        return frozenset(anchors(patch(pid)))
    except (OSError, KeyError):         # no such file, or a test's fixture data without it
        return frozenset()


def clear() -> None:
    """Forget everything (tests that swap data/ for fixtures)."""
    for f in (index, by_date, patch, gameplay, note_anchors, note_lines):
        f.cache_clear()
