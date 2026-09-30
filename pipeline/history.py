"""Walk every tracker build and write one change record per build.

Output: data/builds/<build>_<commit8>.json.gz + data/builds/index.json.
A record is written for every commit that changed anything we track:
vdata entities, english localization, citadel convars, packed assets.

    python -m pipeline.history            # incremental (skips existing files)
    python -m pipeline.history --rebuild  # regenerate everything
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from . import cache, extras, jsonio, loc, tracker
from .diff import diff_file

OUT = tracker.ROOT / 'data' / 'builds'
FORMAT_VERSION = 3
SUFFIX = '.json.gz'


def _dump(path: Path, obj) -> None:
    jsonio.dump(path, obj)


def record_path(build: tracker.Build) -> Path:
    return OUT / f'{build.build}_{build.short}{SUFFIX}'


def entity_changes(prev: tracker.Build, cur: tracker.Build, last_known: dict[str, str] | None = None) -> list[dict]:
    """Diff each tracked vdata file against its LAST KNOWN version.

    Some predecessor builds (5034-5043) carry no vdata at all: a missing file
    means "no data for this build", never "everything was removed", and the
    next build is compared with the last version seen. The first version of a
    file is the baseline, not a change."""
    entities = []
    boundary = prev.repo != cur.repo
    for path in tracker.VDATA_PATHS:
        if path not in cur.files and not boundary:
            continue
        new_blob = tracker.blob_id(cur.commit, path)
        if new_blob is None:
            continue
        if last_known is not None:
            old_blob = last_known.get(path)
            last_known[path] = new_blob
            if old_blob is None:
                continue                      # first time we see this file: baseline
        else:
            old_blob = tracker.blob_id(prev.commit, path)
        if old_blob == new_blob:
            continue
        old = cache.vdata_blob(old_blob) if old_blob else {}
        new = cache.vdata_blob(new_blob) if new_blob else {}
        name = path.rsplit('/', 1)[1]
        for ec in diff_file(name, old, new):
            rec = ec.to_json()
            if ec.status == 'added':
                # a new entity keeps gameplay data only; cosmetics would bloat
                rec['changes'] = [c for c in rec['changes'] if c['cat'] in ('balance', 'mechanic', 'availability')]
            entities.append(rec)
    return entities


def is_baseline(prev: tracker.Build) -> bool:
    """The tracker's first real build is compared with an empty repo: that is
    the starting point, not a change."""
    return all(tracker.blob_id(prev.commit, p) is None for p in tracker.VDATA_PATHS)


def _source_base(last_known: dict | None, key: str, prev: tracker.Build, cur: tracker.Build,
                 present: bool) -> str | None:
    """Commit to diff a non-vdata source against: the last build that had it.
    Returns None when this build has no such data or it is the first sighting."""
    if last_known is None:
        return prev.commit if present else None
    base = last_known.get(key)
    if present:
        last_known[key] = cur.commit
    return base if present else None


def touches(cur: tracker.Build, prev: tracker.Build) -> dict[str, bool]:
    boundary = prev.repo != cur.repo
    return {
        '@loc': boundary or any(f.endswith('_english.txt') and any(f.startswith(r) for r in loc.LOC_ROOTS)
                                for f in cur.files),
        '@convars': boundary or tracker.CONVARS in cur.files,
        '@assets': boundary or tracker.ASSET_LIST in cur.files,
    }


def build_record(prev: tracker.Build, cur: tracker.Build, last_known: dict[str, str] | None = None) -> dict | None:
    entities = entity_changes(prev, cur, last_known)
    t = touches(cur, prev)
    has_loc = t['@loc'] and bool(loc.english_files(cur.commit))
    base = _source_base(last_known, '@loc', prev, cur, has_loc)
    loc_changes = loc.diff(base, cur.commit) if base else []
    has_cv = t['@convars'] and tracker.blob_id(cur.commit, tracker.CONVARS) is not None
    base = _source_base(last_known, '@convars', prev, cur, has_cv)
    convars = extras.convar_diff(base, cur.commit) if base else []
    has_assets = t['@assets'] and tracker.blob_id(cur.commit, tracker.ASSET_LIST) is not None
    base = _source_base(last_known, '@assets', prev, cur, has_assets)
    assets = extras.asset_diff(base, cur.commit) if base else None
    if not (entities or loc_changes or convars or assets):
        return None
    info = extras.steam_inf(cur.commit)
    return {
        'v': FORMAT_VERSION,
        'build': cur.build,
        'commit': cur.commit,
        'prev_commit': prev.commit,
        'prev_build': prev.build,
        'date': cur.date,
        'version_date': f"{info.get('VersionDate', '')} {info.get('VersionTime', '')}".strip(),
        'entities': entities,
        'loc': loc_changes,
        'convars': convars,
        'assets': assets,
    }


def summary(rec: dict, file_name: str) -> dict:
    by_cat: dict[str, int] = {}
    for e in rec['entities']:
        for c in e['changes']:
            by_cat[c['cat']] = by_cat.get(c['cat'], 0) + 1
    return {
        'build': rec['build'], 'commit': rec['commit'], 'date': rec['date'], 'file': file_name,
        'entities': len(rec['entities']),
        'added': sum(1 for e in rec['entities'] if e['status'] == 'added'),
        'removed': sum(1 for e in rec['entities'] if e['status'] == 'removed'),
        'fields': by_cat,
        'loc': len(rec['loc']),
        'convars': len(rec['convars']),
        'assets': {k: sum(v.values()) for k, v in (rec['assets'] or {}).get('counts', {}).items()},
    }


def run(rebuild: bool = False) -> None:
    all_builds = tracker.builds()
    index = []
    t0 = time.time()
    for stale in OUT.glob('*_*.json'):          # pre-gzip format
        stale.unlink()
    last_known: dict[str, str] = {}
    for prev, cur in zip(all_builds, all_builds[1:]):
        out = record_path(cur)
        name = out.name
        rec = None
        if out.exists() and not rebuild:
            rec = jsonio.load(out)
            if rec.get('v') != FORMAT_VERSION:
                rec = None
            else:
                remember(last_known, prev, cur)
        if rec is None:
            rec = build_record(prev, cur, last_known)
            if rec is None:
                if out.exists():
                    out.unlink()
                continue
            _dump(out, rec)
            s = summary(rec, name)
            print(f"{cur.date[:10]} {cur.build} ent={s['entities']:4d} bal={s['fields'].get('balance', 0):5d} "
                  f"loc={s['loc']:4d} cvar={s['convars']:3d} ({time.time() - t0:.0f}s)", flush=True)
        index.append(summary(rec, name))
    jsonio.dump(OUT / 'index.json', index, indent=0)
    print(f'{len(index)} build records, {time.time() - t0:.0f}s')


def remember(last_known: dict[str, str], prev: tracker.Build, cur: tracker.Build) -> None:
    """Advance last-known versions for a build whose record came from disk."""
    boundary = prev.repo != cur.repo
    for path in tracker.VDATA_PATHS:
        if path in cur.files or boundary:
            blob = tracker.blob_id(cur.commit, path)
            if blob:
                last_known[path] = blob
    t = touches(cur, prev)
    if t['@loc'] and loc.english_files(cur.commit):
        last_known['@loc'] = cur.commit
    if t['@convars'] and tracker.blob_id(cur.commit, tracker.CONVARS):
        last_known['@convars'] = cur.commit
    if t['@assets'] and tracker.blob_id(cur.commit, tracker.ASSET_LIST):
        last_known['@assets'] = cur.commit


def reindex() -> None:
    """Rewrite index.json from the records on disk. Must run after
    pipeline.enrich: enrichment re-derives field categories, and the index
    summaries count fields per category."""
    old = jsonio.load(OUT / 'index.json') if (OUT / 'index.json').exists() else []
    index = [summary(jsonio.load(OUT / row['file']), row['file']) for row in old if (OUT / row['file']).exists()]
    jsonio.dump(OUT / 'index.json', index, indent=0)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--rebuild', action='store_true')
    args = ap.parse_args()
    run(args.rebuild)
