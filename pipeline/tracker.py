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
    repo: str = 'main'  # 'main' = GameTracking-Deadlock, 'pre' = its predecessor (Jun-Aug 2024)

    @property
    def short(self) -> str:
        return self.commit[:8]


# The predecessor tracker (Lifeismana/Deadlocked, archived) covers builds
# 4243 (2024-06-06) .. 5044 in the same layout; GameTracking starts at 5044.
PRE_TRACKER = Path(os.environ.get('CYCLOPEAN_PRE_TRACKER', ROOT / 'vendor' / 'Deadlocked'))
PRE_TRACKER_URL = 'https://github.com/Lifeismana/Deadlocked.git'
REPOS = {'main': TRACKER, 'pre': PRE_TRACKER}


def git(*args: str, binary: bool = False, repo: str = 'main', check: bool = True):
    res = subprocess.run(['git', '-C', str(REPOS[repo]), *args], capture_output=True, check=check)
    return res.stdout if binary else res.stdout.decode('utf-8', 'replace')


def ensure_clone() -> None:
    for repo, url in (('main', TRACKER_URL), ('pre', PRE_TRACKER_URL)):
        path = REPOS[repo]
        if (path / '.git').exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', 'clone', '--quiet', url, str(path)], check=True)


def sync() -> str:
    """Move the main tracker clone to upstream's HEAD (the predecessor is archived); returns HEAD.
    The clone is a read-only mirror (data is read with `git show`), so it follows upstream with a
    hard reset: the tracker's own .gitattributes (`* text eol=lf`) marks binaries such as
    vconsole2.exe as text, git then always sees them as modified, and a fast-forward merge
    refused every update that touched one (2026-10-01, build 6728)."""
    ensure_clone()
    git('fetch', '--quiet', 'origin')
    git('reset', '--quiet', '--hard', 'origin/HEAD')
    builds.cache_clear()
    _repo_of.cache_clear()
    return git('rev-parse', 'HEAD').strip()


def _log(repo: str) -> list[Build]:
    out = git('log', '--reverse', '--no-renames', '--format=\x01%H\t%cI\t%s', '--name-only', repo=repo)
    result = []
    for chunk in out.split('\x01')[1:]:
        head, _, rest = chunk.partition('\n')
        commit, date, subject = head.split('\t', 2)
        m = _BUILD_RE.match(subject)
        files = tuple(line for line in rest.splitlines() if line.strip())
        result.append(Build(commit, date, int(m.group(1)) if m else None, files, repo))
    return result


@lru_cache(maxsize=None)
def builds() -> tuple[Build, ...]:
    """All tracker commits, oldest first: predecessor builds older than the
    main tracker's first build, then the main tracker."""
    main = _log('main')
    first_main = next((b.build for b in main if b.build is not None), None)
    pre = []
    if (PRE_TRACKER / '.git').exists() and first_main is not None:
        pre = [b for b in _log('pre') if b.build is None or b.build < first_main]
        # the predecessor's leading setup commits ("Initial commit", "YOLO") carry no build
        while pre and pre[0].build is None and not pre[0].files:
            pre.pop(0)
    return tuple(pre + main)


@lru_cache(maxsize=None)
def _repo_of(rev: str) -> str:
    if rev == 'HEAD':
        return 'main'
    for b in builds():
        if b.commit.startswith(rev) or rev.startswith(b.commit):
            return b.repo
    return 'main'


def blob_id(rev: str, path: str) -> str | None:
    """Git blob sha of `path` at `rev` (None if the file did not exist)."""
    out = git('rev-parse', '--verify', '--quiet', f'{rev}:{path}', repo=_repo_of(rev), check=False)
    return out.strip() or None


def read_blob(blob: str) -> bytes:
    for repo in ('main', 'pre'):
        if not (REPOS[repo] / '.git').exists():
            continue
        res = subprocess.run(['git', '-C', str(REPOS[repo]), 'cat-file', 'blob', blob], capture_output=True)
        if res.returncode == 0:
            return res.stdout
    raise KeyError(f'blob {blob} not found in any tracker clone')


def read(rev: str, path: str) -> str | None:
    blob = blob_id(rev, path)
    if blob is None:
        return None
    return read_blob(blob).decode('utf-8-sig', 'replace')


def tree_blobs(rev: str, prefix: str) -> dict[str, str]:
    """{path: blob sha} for every file under `prefix` at `rev`."""
    out = git('ls-tree', '-r', rev, '--', prefix, repo=_repo_of(rev), check=False)
    result = {}
    for line in out.splitlines():
        meta, _, path = line.partition('\t')
        result[path] = meta.split()[2]
    return result
