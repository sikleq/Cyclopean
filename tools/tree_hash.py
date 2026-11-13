"""Hash every file under the given folders, to prove a refactor changed no output byte.

    python tools/tree_hash.py data dist > before.txt   (then after the change: diff the two)
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path


def tree_hash(roots: list[str]) -> list[str]:
    out = []
    for root in roots:
        for p in sorted(Path(root).rglob('*')):
            if p.is_file():
                out.append(f'{hashlib.sha256(p.read_bytes()).hexdigest()[:16]}  {p.as_posix()}')
    return out


if __name__ == '__main__':
    print('\n'.join(tree_hash(sys.argv[1:] or ['data', 'dist'])))
