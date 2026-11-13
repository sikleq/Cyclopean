"""Print the ids of Steam announcements that data/notes/steam.json does not hold yet (nothing when there are none).

The update-data workflow's cheap check pipes the Steam News API's newest posts in: a patch-notes post Valve makes
after the last game build used to wait for the next build (data audit 2026-11-13). Bad or empty input prints nothing:
a Steam outage must not start a data run.

    curl -s '<GetNewsForApp url>' | python3 tools/new_steam_posts.py data/notes/steam.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def new_ids(feed: dict, known: list[dict]) -> list[str]:
    have = {str(it.get('gid')) for it in known}
    items = ((feed or {}).get('appnews') or {}).get('newsitems') or []
    return sorted(str(it['gid']) for it in items if it.get('gid') and str(it['gid']) not in have)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        feed = json.load(sys.stdin)
    except ValueError:
        return 0
    path = Path(sys.argv[1])
    known = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    print(','.join(new_ids(feed, known)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
