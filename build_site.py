"""Cyclopean — the single site build entrypoint.

    python build_site.py              # build every page into dist/
    python build_site.py patches      # only some steps (patches builds entities tables home)
    python build_site.py --data       # refresh data/ from the tracker first (needs vendor/ clone)

The site is built ONLY from data/ (committed JSON) + site/ + icons/, so CI can
build and deploy without the 200 MB tracker clone. `--data` runs the
pipeline: tracker sync -> history -> enrich -> catalog -> cosmetics -> hero table -> notes -> match.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from builders import builds_pages, entities_pages, home_page, patches_pages, tables_pages  # noqa: E402
from builders.common import DIST, ICONS, SITE  # noqa: E402

STEPS = (
    ('patches', patches_pages.build_all),
    ('builds', builds_pages.build_all),
    ('entities', entities_pages.build_all),
    ('tables', tables_pages.build_all),
    ('home', home_page.build_all),
)
# page folders each step owns: emptied first, so a patch that no longer exists
# (merged or renamed window) leaves no stale page behind
STEP_DIRS = {'patches': ('patches',), 'builds': ('builds',), 'entities': ('heroes', 'items', 'units', 'game'),
             'tables': ('tables',)}


def refresh_data(sync: bool) -> None:
    from pipeline import (abilities, catalog, cosmetics, enrich, hero_table, history, item_table, match, news, tracker,
                          unit_table)
    if sync:
        print('tracker ->', tracker.sync()[:8])
    # the last processed tracker commit: update-data.yml compares it with
    # `git ls-remote` every 15 minutes and only clones when the tracker moved
    head = tracker.git('rev-parse', 'HEAD').strip()
    (ROOT / 'data' / 'tracker_head.txt').write_text(head + '\n', encoding='utf-8', newline='\n')
    history.run()
    enrich.run()
    catalog.build()
    cosmetics.build()
    abilities.build()
    hero_table.build()
    unit_table.build()
    item_table.build()
    try:
        news.refresh()
    except OSError as e:          # Steam API down must not block the build
        print('WARN: Steam news refresh failed:', e)
    match.run()


def copy_assets() -> None:
    DIST.mkdir(exist_ok=True)
    css = (SITE / 'styles.css').read_text(encoding='utf-8')
    js = (SITE / 'scripts.js').read_text(encoding='utf-8')
    try:
        import rcssmin
        import rjsmin
        css, js = rcssmin.cssmin(css), rjsmin.jsmin(js)
    except ImportError:
        pass
    (DIST / 'styles.css').write_text(css, encoding='utf-8')
    (DIST / 'scripts.js').write_text(js, encoding='utf-8')
    shutil.copyfile(SITE / 'favicon.svg', DIST / 'favicon.svg')
    if ICONS.exists():
        sync_tree(ICONS, DIST / 'icons')
    # the shop's UI sounds from the game (tools/extract_shop_assets.py)
    if (ICONS.parent / 'sounds').exists():
        sync_tree(ICONS.parent / 'sounds', DIST / 'sounds')
    (DIST / '.nojekyll').write_text('', encoding='utf-8')


def sync_tree(src: Path, dst: Path) -> int:
    """Copy what is new or changed (size or modification time; copy2 keeps the time), like copytree but
    without rewriting ~1,400 unchanged icons every build (1.2 s of copying on Windows). Returns the files
    copied."""
    n = 0
    for folder, _, files in os.walk(src):
        out = dst / Path(folder).relative_to(src)
        out.mkdir(parents=True, exist_ok=True)
        for name in files:
            a, b = Path(folder) / name, out / name
            sa = a.stat()
            try:
                sb = b.stat()
                if sb.st_size == sa.st_size and int(sb.st_mtime) == int(sa.st_mtime):
                    continue
            except FileNotFoundError:
                pass
            shutil.copy2(a, b)
            n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('steps', nargs='*', help='subset of: ' + ' '.join(k for k, _ in STEPS))
    ap.add_argument('--data', action='store_true', help='refresh data/ from the tracker before building')
    ap.add_argument('--no-sync', action='store_true', help='with --data: do not pull the tracker')
    args = ap.parse_args()
    t0 = time.time()
    if args.data:
        refresh_data(sync=not args.no_sync)
    copy_assets()
    wanted = set(args.steps) or {k for k, _ in STEPS}
    unknown = wanted - {k for k, _ in STEPS}
    if unknown:
        print('unknown steps:', ', '.join(sorted(unknown)))
        return 2
    for key, fn in STEPS:
        if key in wanted:
            for d in STEP_DIRS.get(key, ()):
                shutil.rmtree(DIST / d, ignore_errors=True)
            t = time.time()
            n = fn()
            print(f'  {key:9s} {n} ({time.time() - t:.1f}s)')
    print(f'built dist/ in {time.time() - t0:.1f}s')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
