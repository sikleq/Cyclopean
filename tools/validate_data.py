"""Sanity checks over committed data/ (runs in CI, no tracker needed).

Severity: HIGH -> exit 1, MEDIUM/LOW -> printed only.

    python tools/validate_data.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import jsonio  # noqa: E402

DATA = ROOT / 'data'
TRACKER_START = '2024-08-10'
MISMATCH_WARN = 0.25            # share of note lines that disagree with the files
NOT_MATCHABLE = ('heading', 'untracked', 'nodata', 'repeated')


def main() -> int:
    issues: list[tuple[str, str]] = []
    patches = json.loads((DATA / 'patches' / 'index.json').read_text(encoding='utf-8'))
    for p in patches:
        if p['has_notes'] and p['date'] >= TRACKER_START and p['builds'] == 0:
            issues.append(('MEDIUM', f'patch {p["id"]} ({p["title"]}) has notes but no builds in its window'))
        # only lines that could match data: headings, untracked topics, lines without game
        # files and repeated lines from edited posts would dilute the ratio
        lines = sum(n for st, n in p['line_counts'].items() if st not in NOT_MATCHABLE)
        mis = p['line_counts'].get('mismatch', 0)
        if lines >= 20 and mis / lines > MISMATCH_WARN:
            issues.append(('MEDIUM', f'patch {p["id"]}: {mis}/{lines} lines mismatch the files — check the matcher'))
        if not (DATA / 'patches' / f'{p["id"]}.json.gz').exists():
            issues.append(('HIGH', f'patch {p["id"]} listed in index but its file is missing'))

    builds = json.loads((DATA / 'builds' / 'index.json').read_text(encoding='utf-8'))
    for b in builds:
        if not (DATA / 'builds' / b['file']).exists():
            issues.append(('HIGH', f'build {b["build"]} listed but {b["file"]} is missing'))
    covered = set()
    for p in patches:
        for row in jsonio.load(DATA / 'patches' / f'{p["id"]}.json.gz')['builds']:
            covered.add(row['file'])
    orphan = [b['build'] for b in builds if b['file'] not in covered]
    if orphan:
        issues.append(('HIGH', f'{len(orphan)} builds belong to no patch window, e.g. {orphan[:5]}'))

    table = json.loads((DATA / 'tables' / 'heroes.json').read_text(encoding='utf-8'))
    manifest_path = ROOT / 'icons' / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
    allowed = json.loads((DATA / 'overrides' / 'missing_icons.json').read_text(encoding='utf-8'))
    for h in table['heroes']:
        for col in ('hp', 'bullet_dmg', 'move'):
            if h['values'].get(col) is None:
                issues.append(('HIGH', f'hero {h["name"]} has no {col}'))
        key = f'heroes:{h["id"]}'
        if key not in manifest and key not in allowed:
            issues.append(('MEDIUM', f'hero {h["name"]} has no icon (run tools/extract_icons.py)'))

    # the shop must not empty out: on 2026-10-01 a build that left abilities.vdata alone marked
    # every item removed (catalog 'alive') and the live Items page showed none
    ents = json.loads((DATA / 'entities.json').read_text(encoding='utf-8'))['entities']
    for kind, least in (('item', 0.6), ('ability', 0.6), ('hero', 0.3)):
        group = [e for e in ents if e.get('kind') == kind and not e.get('template')]
        alive = sum(1 for e in group if e.get('alive'))
        if group and alive / len(group) < least:
            issues.append(('HIGH', f'only {alive} of {len(group)} {kind} entities are alive — catalog bug?'))

    for sev, msg in issues:
        print(f'[{sev}] {msg}')
    high = sum(1 for s, _ in issues if s == 'HIGH')
    print(f'{len(issues)} issues, {high} HIGH')
    return 1 if high else 0


if __name__ == '__main__':
    raise SystemExit(main())
