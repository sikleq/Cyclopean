"""English localization tokens per build.

Files: game/citadel/resource/localization/<group>/<group>_english.txt (KV1).
Keys are case-insensitive in-game; Valve appends grammar tags such as ':n'
("hero_haze:n") which we strip. Voice-line subtitles (citadel_generated_vo)
are skipped — 4.7 MB of dialogue with no balance value.
"""
from __future__ import annotations

import pickle
import re

from . import tracker

SKIP_GROUPS = ('citadel_generated_vo',)
CACHE_DIR = tracker.ROOT / '.cache' / 'loc'

_TOKEN_RE = re.compile(r'"((?:[^"\\\n]|\\.)+)"[ \t]+"((?:[^"\\]|\\.)*)"', re.S)
_TAG_RE = re.compile(r':[a-z]+$')


def parse(text: str) -> dict[str, str]:
    body = text
    i = body.find('"Tokens"')
    if i >= 0:
        body = body[i + len('"Tokens"'):]
    out = {}
    for key, val in _TOKEN_RE.findall(body):
        k = _TAG_RE.sub('', key).lower()
        out.setdefault(k, val.replace('\\"', '"').replace('\\n', '\n'))
    return out


def _file_tokens(blob: str) -> dict[str, str]:
    path = CACHE_DIR / f'{blob}.pkl'
    if path.exists():
        with open(path, 'rb') as f:
            return pickle.load(f)
    data = parse(tracker.read_blob(blob).decode('utf-8-sig', 'replace'))
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, 'wb') as f:
        pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
    return data


def english_files(rev: str) -> dict[str, str]:
    """{path: blob} of every english token file at `rev` (minus skipped groups)."""
    blobs = tracker.tree_blobs(rev, tracker.LOC)
    return {
        p: b for p, b in blobs.items()
        if p.endswith('_english.txt') and not any(g in p for g in SKIP_GROUPS)
    }


def tokens(rev: str) -> dict[str, str]:
    merged: dict[str, str] = {}
    for path, blob in sorted(english_files(rev).items()):
        for k, v in _file_tokens(blob).items():
            merged.setdefault(k, v)
    return merged


def diff(old_rev: str, new_rev: str) -> list[dict]:
    """Changed tokens between two builds, per file (only files whose blob changed)."""
    a, b = english_files(old_rev), english_files(new_rev)
    out = []
    for path in sorted(a.keys() | b.keys()):
        if a.get(path) == b.get(path):
            continue
        ta = _file_tokens(a[path]) if path in a else {}
        tb = _file_tokens(b[path]) if path in b else {}
        group = path.split('/')[-2]
        for k in sorted(ta.keys() | tb.keys()):
            if ta.get(k) != tb.get(k):
                out.append({'group': group, 'key': k, 'old': ta.get(k), 'new': tb.get(k)})
    return out


# ---- display names -------------------------------------------------------

def hero_name(tok: dict[str, str], hid: str) -> str:
    return tok.get(hid) or tok.get(hid + '_search') or hid


def entity_name(tok: dict[str, str], eid: str) -> str:
    return tok.get(eid.lower()) or tok.get(eid.lower() + ':n') or eid


_HTML_RE = re.compile(r'<[^>]+>')


def plain(s: str | None) -> str:
    return _HTML_RE.sub('', s or '').strip()
