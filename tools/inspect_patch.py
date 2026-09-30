"""Print a patch's note lines with their match status (debugging the matcher).

    python tools/inspect_patch.py 2026-09-16 [status ...]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import jsonio  # noqa: E402


def main() -> None:
    pid = sys.argv[1]
    only = set(sys.argv[2:])
    p = jsonio.load(ROOT / 'data' / 'patches' / f'{pid}.json.gz')
    by_key = {c['key']: (e['name'], c) for e in p['entities'] for c in e['changes']}
    print(p['title'], p['counts'], p['line_counts'])
    for s in p['sections']:
        for ln in s['lines']:
            if only and ln['status'] not in only:
                continue
            print(f"[{ln['status'][:4]}] {ln['text'][:110]}")
            for k in ln.get('changes', [])[:3]:
                if k in by_key:
                    name, c = by_key[k]
                    print(f"        -> {name} | {c['label']}: {c['old_s']} -> {c['new_s']}")
            if ln.get('data'):
                print('        data:', ln['data'])


if __name__ == '__main__':
    main()
