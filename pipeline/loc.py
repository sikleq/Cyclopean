"""English localization tokens per build.

Files: game/citadel/resource/localization/<group>/<group>_english.txt (KV1).
Keys are case-insensitive in-game; Valve appends grammar tags such as ':n'
("hero_haze:n") which we strip. Voice-line subtitles (citadel_generated_vo)
are skipped — 4.7 MB of dialogue with no balance value.
"""
from __future__ import annotations

import re
from functools import lru_cache

from . import cache, tracker

SKIP_GROUPS = ('citadel_generated_vo',)

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


@lru_cache(maxsize=256)
def _file_tokens_cached(blob: str) -> dict[str, str]:
    return cache.cached_json('loc', blob, lambda: parse(tracker.read_blob(blob).decode('utf-8-sig', 'replace')))


def _file_tokens(blob: str) -> dict[str, str]:
    return _file_tokens_cached(blob)


# Where english token files lived over time (the predecessor tracker, mid-2024):
#   game/citadel/resource/citadel_english.txt            (single file, before build 5042)
#   game/citadel/pak01_dir/resource/localization/...      (packed copies)
#   game/citadel/resource/localization/<group>/...        (current layout)
LOC_ROOTS = ('game/citadel/resource/', 'game/citadel/pak01_dir/resource/')
_LOC_FILE = re.compile(r'(resource/localization/([^/]+/)?[^/]+_english\.txt|resource/[^/]+_english\.txt)$')
SKIP_FILES = ('closecaption_', 'citadel_generated_vo', 'generated_vo')


def english_files(rev: str) -> dict[str, str]:
    """{path: blob} of every english token file at `rev` (minus voice-line / caption files)."""
    out = {}
    for root in LOC_ROOTS:
        for p, b in tracker.tree_blobs(rev, root).items():
            if _LOC_FILE.search(p) and not any(x in p for x in SKIP_FILES + SKIP_GROUPS):
                out[p] = b
    return out


def tokens(rev: str) -> dict[str, str]:
    merged: dict[str, str] = {}
    for path, blob in sorted(english_files(rev).items()):
        for k, v in _file_tokens(blob).items():
            merged.setdefault(k, v)
    return merged


LEGACY_GROUPS = {'citadel': 'citadel_main', 'citadel_common': 'citadel_main', 'items': 'citadel_mods'}


def _group(path: str) -> str:
    name = path.rsplit('/', 1)[-1].removesuffix('_english.txt')
    return LEGACY_GROUPS.get(name, name)


def _grouped_tokens(rev: str) -> tuple[dict[str, str], dict[str, str], tuple]:
    files = english_files(rev)
    values: dict[str, str] = {}
    groups: dict[str, str] = {}
    for path, blob in sorted(files.items()):
        g = _group(path)
        for k, v in _file_tokens(blob).items():
            if k not in values:
                values[k] = v
                groups[k] = g
    return values, groups, tuple(sorted(files.values()))


def diff(old_rev: str, new_rev: str) -> list[dict]:
    """Changed tokens between two builds, compared key by key across ALL files,
    so tokens that moved between files (the 2024 layout change) are not reported."""
    va, ga, blobs_a = _grouped_tokens(old_rev)
    vb, gb, blobs_b = _grouped_tokens(new_rev)
    if blobs_a == blobs_b or not va or not vb:
        return []
    out = []
    for k in sorted(va.keys() | vb.keys()):
        if va.get(k) != vb.get(k):
            out.append({'group': gb.get(k) or ga.get(k), 'key': k, 'old': va.get(k), 'new': vb.get(k)})
    return out


# ---- display names -------------------------------------------------------

def hero_name(tok: dict[str, str], hid: str) -> str:
    return tok.get(hid) or tok.get(hid + '_search') or hid


def loc_base(tok: dict[str, str], eid: str, owner: str | None = None) -> str:
    """Localization key of an entity. Weapons are localized under the owning hero's
    name, not their own id: Abrams' `citadel_weapon_bull_set` is `citadel_weapon_atlas_set`."""
    if tok.get(eid.lower()) or tok.get(eid.lower() + ':n'):
        return eid.lower()
    # alt fire (`_alt`, `_set2`, `_set_2`) must not borrow the primary gun's name
    if owner and owner.startswith('hero_') and eid.startswith('citadel_weapon_') \
            and not eid.endswith(('_alt', '_set2', '_set_2')):
        key = f'citadel_weapon_{owner[5:]}_set'.lower()
        if tok.get(key):
            return key
    return eid.lower()


def entity_name(tok: dict[str, str], eid: str, owner: str | None = None) -> str:
    base = loc_base(tok, eid, owner)
    return tok.get(base) or tok.get(base + ':n') or eid


_HTML_RE = re.compile(r'<[^>]+>')


def plain(s: str | None) -> str:
    return _HTML_RE.sub('', s or '').strip()
