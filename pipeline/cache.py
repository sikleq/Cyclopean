"""Parsed-file cache keyed by git blob sha.

The same blob appears in many builds (a file only changes in some of them),
so keying by blob sha means every distinct file version is parsed once.
"""
from __future__ import annotations

import pickle
from pathlib import Path

from . import kv3, tracker

CACHE_DIR = tracker.ROOT / '.cache' / 'kv3'


def vdata_blob(blob: str) -> dict:
    path = CACHE_DIR / f'{blob}.pkl'
    if path.exists():
        with open(path, 'rb') as f:
            return pickle.load(f)
    text = tracker.read_blob(blob).decode('utf-8-sig')
    data = kv3.loads(text) or {}
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    with open(tmp, 'wb') as f:
        pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
    tmp.replace(path)
    return data


def vdata(rev: str, path: str) -> dict:
    blob = tracker.blob_id(rev, path)
    return vdata_blob(blob) if blob else {}


def clear() -> None:
    for p in Path(CACHE_DIR).glob('*.pkl'):
        p.unlink()
