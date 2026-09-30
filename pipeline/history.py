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


def entity_changes(prev: tracker.Build, cur: tracker.Build) -> list[dict]:
    entities = []
    for path in tracker.VDATA_PATHS:
        if path not in cur.files:
            continue
        old_blob = tracker.blob_id(prev.commit, path)
        new_blob = tracker.blob_id(cur.commit, path)
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


def build_record(prev: tracker.Build, cur: tracker.Build) -> dict | None:
    entities = entity_changes(prev, cur)
    loc_changes = loc.diff(prev.commit, cur.commit) if any(f.startswith(tracker.LOC) for f in cur.files) else []
    convars = extras.convar_diff(prev.commit, cur.commit) if tracker.CONVARS in cur.files else []
    assets = extras.asset_diff(prev.commit, cur.commit) if tracker.ASSET_LIST in cur.files else None
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
    for prev, cur in zip(all_builds, all_builds[1:]):
        out = record_path(cur)
        name = out.name
        rec = None
        if prev is all_builds[0] and is_baseline(prev):
            out.unlink(missing_ok=True)
            continue
        if out.exists() and not rebuild:
            rec = jsonio.load(out)
            if rec.get('v') != FORMAT_VERSION:
                rec = None
        if rec is None:
            rec = build_record(prev, cur)
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
