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


def clear() -> None:
    """Forget everything (tests that swap data/ for fixtures)."""
    for f in (index, by_date, patch, gameplay):
        f.cache_clear()
