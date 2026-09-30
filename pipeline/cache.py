"""Parsed-file cache keyed by git blob sha.

The same blob appears in many builds (a file only changes in some of them),
so keying by blob sha means every distinct file version is parsed once.

Stored as plain JSON (not pickle): antivirus heuristics flag .pkl files, and
JSON cannot carry code.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from . import kv3, tracker

CACHE_ROOT = tracker.ROOT / '.cache'
CACHE_DIR = CACHE_ROOT / 'kv3'


def cached_json(folder: str, key: str, compute: Callable[[], object]):
    """Load `<.cache>/<folder>/<key>.json`, or compute, store and return it."""
    path = CACHE_ROOT / folder / f'{key}.json'
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    data = compute()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    tmp.replace(path)
    return data


def vdata_blob(blob: str) -> dict:
    return cached_json('kv3', blob, lambda: kv3.loads(tracker.read_blob(blob).decode('utf-8-sig')) or {})


def vdata(rev: str, path: str) -> dict:
    blob = tracker.blob_id(rev, path)
    return vdata_blob(blob) if blob else {}


def clear() -> None:
    for p in Path(CACHE_DIR).glob('*.json'):
        p.unlink()
