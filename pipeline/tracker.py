"""Access to the SteamTracking/GameTracking-Deadlock clone.

Every commit in the tracker is one game build; the subject starts with the
build number ("6711 | 7422 files | ..."). We never checkout — everything is
read with `git show <rev>:<path>` so the working tree stays untouched.
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRACKER = Path(os.environ.get('CYCLOPEAN_TRACKER', ROOT / 'vendor' / 'GameTracking-Deadlock'))
TRACKER_URL = 'https://github.com/SteamTracking/GameTracking-Deadlock.git'

SCRIPTS = 'game/citadel/pak01_dir/scripts/'
LOC = 'game/citadel/resource/localization/'

# vdata files whose content we diff entity-by-entity
VDATA_FILES = (
    'heroes.vdata',
    'abilities.vdata',
    'npc_units.vdata',
    'misc.vdata',
    'modifiers.vdata',
    'generic_data.vdata',
    'loot_tables.vdata',
    'accolades.vdata',
)
VDATA_PATHS = tuple(SCRIPTS + f for f in VDATA_FILES)
ASSET_LIST = 'game/citadel/pak01_dir.txt'
CONVARS = 'DumpSource2/convars.txt'
STEAM_INF = 'game/citadel/steam.inf'

_BUILD_RE = re.compile(r'^(\d+)\b')


@dataclass(frozen=True)
class Build:
    commit: str
    date: str          # ISO date-time when the tracker committed it (UTC)
    build: int | None  # game build number from the commit subject
    files: tuple[str, ...] = field(default=())

    @property
    def short(self) -> str:
        return self.commit[:8]


def git(*args: str, binary: bool = False):
    res = subprocess.run(['git', '-C', str(TRACKER), *args], capture_output=True, check=True)
    return res.stdout if binary else res.stdout.decode('utf-8', 'replace')


def ensure_clone() -> None:
    if (TRACKER / '.git').exists():
        return
    TRACKER.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['git', 'clone', '--quiet', TRACKER_URL, str(TRACKER)], check=True)


def sync() -> str:
    """Fast-forward the tracker clone; returns the new HEAD commit."""
    ensure_clone()
    git('fetch', '--quiet', 'origin')
    git('merge', '--quiet', '--ff-only', 'origin/HEAD')
    builds.cache_clear()
    return git('rev-parse', 'HEAD').strip()


@lru_cache(maxsize=None)
def builds() -> tuple[Build, ...]:
    """All tracker commits, oldest first, with the files each one touched."""
    out = git('log', '--reverse', '--no-renames', '--format=\x01%H\t%cI\t%s', '--name-only')
    result = []
    for chunk in out.split('\x01')[1:]:
        head, _, rest = chunk.partition('\n')
        commit, date, subject = head.split('\t', 2)
        m = _BUILD_RE.match(subject)
        files = tuple(line for line in rest.splitlines() if line.strip())
        result.append(Build(commit, date, int(m.group(1)) if m else None, files))
    return tuple(result)


def blob_id(rev: str, path: str) -> str | None:
    """Git blob sha of `path` at `rev` (None if the file did not exist)."""
    try:
        return git('rev-parse', '--verify', '--quiet', f'{rev}:{path}').strip() or None
    except subprocess.CalledProcessError:
        return None


def read_blob(blob: str) -> bytes:
    return git('cat-file', 'blob', blob, binary=True)


def read(rev: str, path: str) -> str | None:
    blob = blob_id(rev, path)
    if blob is None:
        return None
    return read_blob(blob).decode('utf-8-sig', 'replace')


def tree_blobs(rev: str, prefix: str) -> dict[str, str]:
    """{path: blob sha} for every file under `prefix` at `rev`."""
    out = git('ls-tree', '-r', rev, '--', prefix)
    result = {}
    for line in out.splitlines():
        meta, _, path = line.partition('\t')
        result[path] = meta.split()[2]
    return result
