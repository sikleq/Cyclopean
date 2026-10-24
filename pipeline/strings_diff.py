"""Text strings that appeared in or left the game's binaries (the tracker's <module>_strings.txt).

A new string in server.dll is often the first trace of a mechanic, a removed one of a dropped check: build 6810
(2026-10-22) lost `IsHighSkillRange` from client.dll. Only the game's own modules are read; the engine tools
the tracker also dumps (resourcecompiler, vconsole2, Qt, ffmpeg...) change with every SDK update and say nothing
about the game. Lines that are not text (bytes of a table read as characters, `;<}\\v<}...`) are dropped.
"""
from __future__ import annotations

import re

from . import tracker

MODULES = {
    'client': 'game/citadel/bin/win64/client_strings.txt',
    'server': 'game/citadel/bin/win64/server_strings.txt',
    'host': 'game/citadel/bin/win64/host_strings.txt',
    'engine2': 'game/bin/win64/engine2_strings.txt',
}
SHOWN = 60                      # strings kept per module and side; the counts keep the rest
MIN_LEN = 6                     # shorter ones are mostly byte runs read as text (`0TAB`, `6vRF`, `.PAF`)
# text: printable ASCII with letters in it, no backslash escapes of the dump, mostly word characters
_PRINTABLE = re.compile(r'^[\x20-\x7e]+$')
_WORDISH = re.compile(r'[A-Za-z0-9_ .:%/\-#<>]')
_REPEAT = re.compile(r'(.)\1{7,}')                       # `6666666666666666HeroPersona_t`
_BUILD_DATE = re.compile(r'^[A-Z][a-z]{2} +\d{1,2} \d{4}$')  # the engine's own build date: changes every build
_LEAD = re.compile(r'^[?:@]+(?=\w)')                    # a length byte the dump kept in front (`?citadel_...`)
# MSVC type names (RTTI): `.?AVCCitadelProjectile@@`, `.?AV?$CModifierFactory@VCCitadel_Modifier_X@@$0PPPP@@@`
_RTTI = re.compile(r'^\.\?A[VUW](.+)@@$')
_TEMPLATE = re.compile(r'^\?\$(\w+)@[VUW](\w+)@@')


def demangle(s: str) -> str:
    m = _RTTI.match(s)
    if not m:
        return s
    t = _TEMPLATE.match(m.group(1))
    return f'{t.group(1)}<{t.group(2)}>' if t else m.group(1).split('@')[0]


def clean(s: str) -> str | None:
    """The string as shown, or None when it is not text."""
    s = s.strip()
    if not _PRINTABLE.match(s) or '\\' in s:
        return None
    s = demangle(_LEAD.sub('', s))
    if len(s) < MIN_LEN or not re.search('[A-Za-z]{3}', s) or _REPEAT.search(s) or _BUILD_DATE.match(s):
        return None
    return s if sum(1 for ch in s if _WORDISH.match(ch)) >= 0.85 * len(s) else None


def is_text(s: str) -> bool:
    return clean(s) is not None


def _texts(blob: str) -> set[str]:
    return {c for c in map(clean, blob.splitlines()) if c}


def diff_text(old: str, new: str) -> dict | None:
    a, b = _texts(old), _texts(new)
    added, removed = sorted(b - a), sorted(a - b)
    if not added and not removed:
        return None
    return {'added': added[:SHOWN], 'removed': removed[:SHOWN], 'n_added': len(added), 'n_removed': len(removed)}


def strings_diff(prev: str, cur: str) -> dict[str, dict]:
    """{module: {added, removed, n_added, n_removed}} for the game modules whose strings changed."""
    out: dict[str, dict] = {}
    for mod, path in MODULES.items():
        old_blob, new_blob = tracker.blob_id(prev, path), tracker.blob_id(cur, path)
        if old_blob is None or new_blob is None or old_blob == new_blob:
            continue                 # a module the tracker starts or stops dumping is no change of the game
        d = diff_text(tracker.read_blob(old_blob).decode('utf-8', 'replace'),
                      tracker.read_blob(new_blob).decode('utf-8', 'replace'))
        if d:
            out[mod] = d
    return out
