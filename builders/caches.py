"""One way to forget what every builder memoised (its `functools` caches) — for a test that swaps data/ or the patch
archive for fixtures.

Each builder reads what it needs once a build and keeps it: the archive (`archive`), the history squares (`trail`),
the patch counts (`patch_counts.for_id`, `page_set`), the eye's proof and the stats steps' eyes (`evidence`,
`stat_eyes`)… `archive.clear()` forgot only the archive, so a test that swapped it still got the other builders'
answers from the data before the swap — tests cleared caches one by one (trail._index, trail._positions,
dynamics_page._collect…). `clear_all` clears every cache a `builders.*` module defines; `archive.clear()` calls it."""
from __future__ import annotations

import sys


def clear_all() -> int:
    """Clear every functools cache defined in a loaded `builders` module; returns how many."""
    n = 0
    for name, mod in list(sys.modules.items()):
        if mod is None or not (name == 'builders' or name.startswith('builders.')):
            continue
        for value in list(vars(mod).values()):
            clear = getattr(value, 'cache_clear', None)
            if callable(clear) and getattr(value, '__module__', None) == name:
                clear()
                n += 1
    return n
