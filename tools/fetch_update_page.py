"""Turn a big update's designed web page into a notes file.

    python tools/fetch_update_page.py cityneversleeps
    python tools/fetch_update_page.py cityneversleeps --from-file page_text.json

Rules per page (which keys are changelog lines, feature cards or lore) live in
data/overrides/update_pages.json; the output is data/notes/forum/<date>.txt. Then rebuild the
data (`python build_site.py --data`) so the lines are matched against the game files."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import update_page  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('slug', help='page name on playdeadlock.com, e.g. cityneversleeps')
    ap.add_argument('--from-file', help='use a saved page text JSON instead of fetching')
    args = ap.parse_args()
    text = (json.loads(Path(args.from_file).read_text(encoding='utf-8')) if args.from_file
            else update_page.fetch(args.slug))
    path = update_page.write(args.slug, text)
    n = sum(1 for ln in path.read_text(encoding='utf-8').splitlines() if ln.startswith('- '))
    print(f'{path}: {n} lines')


if __name__ == '__main__':
    main()
