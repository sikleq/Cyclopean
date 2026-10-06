"""Where a change the patch notes left out comes from — the proof behind the eye (review 2026-10-06: "the eye must
say where it came from"; the hover read "found only in the game files" with nothing to check it against).

A change of a patch carries the builds of the window that moved it (`builds`, at most 3 in the data). The eye on its
row names them — "in the files of build 6340 (2026-04-11)", or "shipped silently …" for one that came in a later
build than the patch itself (1,389 rows) — and opens that build's page in the archive at the entity (`builds/<n>.html
#c-<id>`); the build page links the tracker's commit on GitHub. A band's banner eye does the same for the band's rows
(an all-hidden band shows only that eye). Quiet on purpose: no new line or block, the eye is the link."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache

from .common import build_pages

# the trackers the builds come from (pipeline.tracker): GameTracking-Deadlock from its first build on, its archived
# predecessor (Lifeismana/Deadlocked) before it — checked against both clones for all 622 builds on 2026-10-06
FIRST_MAIN_BUILD = 5044
MAIN_TRACKER = 'https://github.com/SteamTracking/GameTracking-Deadlock'
PRE_TRACKER = 'https://github.com/Lifeismana/Deadlocked'
HIDDEN_WORDS = 'Not in the patch notes'
LATE_WORDS = 'shipped silently'


def commit_url(build: int | None, commit: str) -> str:
    """The tracker commit of one build on GitHub (a build without a number came after the switch)."""
    repo = PRE_TRACKER if build is not None and build < FIRST_MAIN_BUILD else MAIN_TRACKER
    return f'{repo}/commit/{commit}'


# the builds of the patch whose rows are being written ({first, dates, files, rel}); set by `patch_builds` around a
# band (history_view) or a patch page's change lists, read by `row_evidence` / `band_evidence`
_PATCH: ContextVar[dict | None] = ContextVar('patch_builds', default=None)


@contextmanager
def patch_builds(builds: list[dict], rel: str = '../'):
    """While a patch's rows are written: its builds ([{build, date, file}], its window) and the pages' depth."""
    got = sorted((b for b in builds or () if b.get('build')), key=lambda b: b['build'])
    # a build number the tracker committed twice keeps its last commit here (sorted is stable): the first of such pairs
    # holds no gameplay rows (2024-12-06's build 5433: 0 entities, then 268), so the eye opens the one that has them
    tok = _PATCH.set({'first': got[0]['build'], 'rel': rel,
                      'dates': {b['build']: str(b.get('date') or '')[:10] for b in got},
                      'files': {b['build']: b.get('file') or '' for b in got}} if got else None)
    try:
        yield
    finally:
        _PATCH.reset(tok)


@lru_cache(maxsize=None)
def build_anchors(file: str) -> frozenset[str]:
    """The ids a build page has a `c-<id>` card for (builds_pages.page_entities, the cards it shows); none when the
    record is missing (a test's data)."""
    from .builds_pages import ENTITY_LIMIT, page_entities
    from .common import load_json
    from .patches_pages import own_anchors
    try:
        rec = load_json(f'builds/{file}')
    except (OSError, ValueError):
        return frozenset()
    return frozenset(own_anchors(page_entities(rec)[:ENTITY_LIMIT]))


def _anchor_id(c: dict) -> str | None:
    """The card a build page files the row under: a hero's ability under its hero, else the entity itself; a shared
    edit (one block in the build, no card per target) has none."""
    if c.get('shared_n'):
        return None
    file, eid = c.get('file'), c.get('id')
    if not file or not eid:
        key = str(c.get('key') or c.get('src_key') or '').split(':')     # src_key: a folded row (render.folded_source)
        if len(key) < 2:
            return None
        file, eid = key[0], key[1]
    if file == 'heroes.vdata':
        return eid
    from .shared_rows import catalog
    owner = (catalog().get(f'{file}:{eid}') or {}).get('owner')
    return owner or eid


def _href(build: int, ctx: dict, anchor: str | None) -> str | None:
    file = ctx['files'].get(build)
    stem = build_pages().get(file) if file else None
    if not stem:
        return None
    frag = f'#c-{anchor}' if anchor and anchor in build_anchors(file) else ''
    return f'{ctx["rel"]}builds/{stem}.html{frag}'


WORDS_MAX = 3            # builds named one by one; more read "6 builds, 6711 (…) to 6745 (…)"
OPEN_WORDS = ' · click to open that build'


def _words(builds: list[int], dates: dict[int, str]) -> str:
    """'build 6340 (2026-04-11)', 'builds 6340 (2026-04-11) and 6342 (2026-04-12)', '6 builds, 6711 (…) to 6745 (…)'."""
    parts = [f'{b} ({dates[b]})' if dates.get(b) else str(b) for b in builds]
    if len(parts) > WORDS_MAX:
        return f'{len(parts)} builds, {parts[0]} to {parts[-1]}'
    joined = parts[0] if len(parts) == 1 else ', '.join(parts[:-1]) + ' and ' + parts[-1]
    return ('build ' if len(parts) == 1 else 'builds ') + joined


def _lead(rows: list[dict]) -> str:
    """An update without notes says so (its eye chip reads "no patch notes"); else the eye's own words."""
    return ('Update shipped without patch notes' if rows and all(c.get('status') == 'unannounced' for c in rows)
            else HIDDEN_WORDS)


def _row_builds(c: dict, ctx: dict) -> list[int]:
    return sorted({b for b in c.get('builds') or () if isinstance(b, int) and b in ctx['dates']})


def row_evidence(c: dict, link: bool = True) -> tuple[str | None, str | None, bool]:
    """(the eye's words, the build page it opens, shipped later than the patch?) for one row not in the notes; all
    None outside a patch (`patch_builds`) or for a row in the notes. `link=False`: the words only (an eye inside a
    <summary> that folds rows with linked eyes of their own: a click there should fold, not leave the page)."""
    from .render import not_in_notes
    ctx = _PATCH.get()
    if ctx is None or not not_in_notes(c):
        return None, None, False
    builds = _row_builds(c, ctx)
    if not builds:
        return None, None, False
    href = _href(builds[0], ctx, _anchor_id(c)) if link else None
    open_ = OPEN_WORDS if href else ''
    # a silent hotfix: it came in a later build of the window than the patch itself
    if c.get('status') == 'hidden' and builds[0] != ctx['first']:
        b = builds[0]
        return f'{HIDDEN_WORDS} — {LATE_WORDS} {ctx["dates"][b]}, build {b}{open_}', href, True
    return f'{_lead([c])} — in the game files of {_words(builds, ctx["dates"])}{open_}', href, False


def band_evidence(rows: list[dict], anchor: str | None = None) -> tuple[str | None, str | None]:
    """(the banner eye's words, the build page it opens) for a band's rows not in the notes: the builds they came in;
    the first one opens, at the page's entity (`anchor`). Inside `patch_builds` only."""
    from .render import not_in_notes
    ctx = _PATCH.get()
    if ctx is None:
        return None, None
    out = [c for c in rows if not_in_notes(c)]
    builds = sorted({b for c in out for b in _row_builds(c, ctx)})
    if not builds:
        return None, None
    href = _href(builds[0], ctx, anchor)
    open_ = (' · click to open the first' if len(builds) > 1 else OPEN_WORDS) if href else ''
    return f'{_lead(out)} — in the game files of {_words(builds, ctx["dates"])}{open_}', href
