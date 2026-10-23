"""Where a change the patch notes left out comes from — the proof behind the eye (review 2026-10-06: "the eye must
say where it came from"; the hover read "found only in the game files" with nothing to check it against).

A change of a patch carries the builds of the window that moved it (`builds`, at most 3 in the data). The eye on its
row names them — "in the files of build 6340 (2026-04-11)", dated by the game build's own date (the record's
`version_date`, not the tracker's UTC commit time: 6785 is "Oct 14 2026", committed 2026-10-15 03:14 UTC) — or
"came in build N (…), after the patch" for one that came in a build newer than the notes' own build that carries
nothing the notes announced (`notes_window`; with nothing announced: a build dated after the notes). It opens that
build's page in the archive at the row itself (`builds/<n>.html#r-<hash>`: `row_anchor`), else at the entity
(`#c-<id>`); the build page's row holds the source — the file, entity and field path, the raw old → new, the tracker
commit's diff of that file and what the update's notes say of it (`row_source`). A band's banner chip does the same
for the band's rows (review 2026-10-17, "the eye's evidence": 15 of Deadman Danny's 10-14 rows said they shipped
silently on 2026-10-15 in build 6785 — the build that carried the notes' own changes; the rule was "any build but the
window's first", 4,727 such claims, about 1,400 now)."""
from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from functools import lru_cache

from pipeline.tracker import SCRIPTS        # where the data files sit (the same layout in both trackers)

from .common import build_pages, esc

# the trackers the builds come from (pipeline.tracker): GameTracking-Deadlock from its first build on, its archived
# predecessor (Lifeismana/Deadlocked) before it — checked against both clones for all 622 builds on 2026-10-06
FIRST_MAIN_BUILD = 5044
MAIN_TRACKER = 'https://github.com/SteamTracking/GameTracking-Deadlock'
PRE_TRACKER = 'https://github.com/Lifeismana/Deadlocked'
# the site's one term (review 2026-10-17): "not in patch notes" for what the notes left out, "no patch notes" for an
# update without any; a change that came in a later build than the notes' own says "after the patch"
HIDDEN_WORDS = 'Not in patch notes'
NO_NOTES_WORDS = 'No patch notes for this update'
VERSION_DATE = '%b %d %Y %H:%M:%S'       # a record's `version_date`: "Oct 14 2026 20:01:37" (steam.inf)


def commit_url(build: int | None, commit: str) -> str:
    """The tracker commit of one build on GitHub (a build without a number came after the switch)."""
    repo = PRE_TRACKER if build is not None and build < FIRST_MAIN_BUILD else MAIN_TRACKER
    return f'{repo}/commit/{commit}'


def diff_url(build: int | None, commit: str, file: str) -> str:
    """That commit's diff of one data file: GitHub's file anchor is '#diff-' + the sha256 of the file's path."""
    return f'{commit_url(build, commit)}#diff-{hashlib.sha256((SCRIPTS + file).encode()).hexdigest()}'


def row_key(file: str, eid: str, path: str) -> str:
    """A row's key in a patch record ('file:id:path'); a shared edit's block in a build record is 'file:@shared:path'."""
    return f'{file}:{eid}:{path}'


ANCHOR_HEX = 12          # 48 bits: no two keys of the archive share an anchor


def row_anchor(key: str) -> str:
    """The build page's id of one row ('r-' + 12 hex): the same key on an entity page and on the build page."""
    return 'r-' + hashlib.sha1(key.encode('utf-8')).hexdigest()[:ANCHOR_HEX]


def game_day(version_date) -> str:
    """'Oct 14 2026 20:01:37' -> '2026-10-14'; '' when there is none."""
    try:
        return datetime.strptime(str(version_date or ''), VERSION_DATE).strftime('%Y-%m-%d')
    except ValueError:
        return ''


# the builds of the patch whose rows are being written ({first, dates, files, rel, notes_build, notes_date}); set by
# `patch_builds` around a band (history_view), read by `row_evidence` / `band_evidence`
_PATCH: ContextVar[dict | None] = ContextVar('patch_builds', default=None)


@lru_cache(maxsize=None)
def notes_window(pid: str) -> tuple[int | None, frozenset[int], str]:
    """(the notes' own build — the one an announced change came in most often, the earliest of a tie —, every build
    that carries an announced change, the notes' date) of a patch: what a change "after the patch" is newer than;
    (None, ∅, '') for a patch the archive does not hold. Not the FIRST such build: 2026-01-30's 6198 carried 2 of its
    140 announced changes a day early, and its 112 hidden ones in 6211 — the notes' own build — read as a later
    build's. Every build of an announced change counts as carrying one, not only its first (2024-09-12: a change in
    5136 and 5138 left 5138 out, and its hidden rows read as after the patch)."""
    from collections import Counter

    from . import archive
    from .cards import NOTED
    try:
        p = archive.patch(pid)
    except (OSError, KeyError):
        return None, frozenset(), ''
    announced = [bs for e in p.get('entities') or () for c in e.get('changes') or () if c.get('status') in NOTED
                 for bs in [[b for b in c.get('builds') or () if isinstance(b, int)]] if bs]
    firsts = Counter(min(bs) for bs in announced)
    main = min(firsts, key=lambda b: (-firsts[b], b)) if firsts else None
    return main, frozenset(b for bs in announced for b in bs), str(p.get('date') or '')[:10]


@contextmanager
def patch_builds(builds: list[dict], rel: str = '../', pid: str | None = None):
    """While a patch's rows are written: its builds ([{build, date, file}], its window), the pages' depth and the
    patch (`pid`: what its notes announced, `notes_window`; without it nothing reads as a silent hotfix)."""
    got = sorted((b for b in builds or () if b.get('build')), key=lambda b: b['build'])
    # a build number the tracker committed twice keeps its last commit here (sorted is stable): the first of such pairs
    # holds no gameplay rows (2024-12-06's build 5433: 0 entities, then 268), so the eye opens the one that has them
    notes_build, noted, notes_date = notes_window(pid) if pid else (None, frozenset(), '')
    tok = _PATCH.set({'first': got[0]['build'], 'rel': rel, 'notes_build': notes_build, 'noted': noted,
                      'notes_date': notes_date,
                      'dates': {b['build']: game_date(b.get('file') or '') or str(b.get('date') or '')[:10]
                                for b in got},
                      'files': {b['build']: b.get('file') or '' for b in got}} if got else None)
    try:
        yield
    finally:
        _PATCH.reset(tok)


@lru_cache(maxsize=None)
def _facts(file: str) -> tuple[frozenset[str], frozenset[str], str]:
    """(the ids a build page has a `c-<id>` card for, its row anchors, the game build's date) — read once per build
    record; empty when the record is missing (a test's data). A key the page writes twice (two '@shared' blocks with
    one path, other values: 41 rows in 15 builds) has no anchor: an eye there opens the card or the page."""
    from .builds_pages import ENTITY_LIMIT, page_entities, unique_keys
    from .common import load_json
    from .patches_pages import own_anchors
    try:
        rec = load_json(f'builds/{file}')
    except (OSError, ValueError):
        return frozenset(), frozenset(), ''
    ents = page_entities(rec)[:ENTITY_LIMIT]
    return (frozenset(own_anchors(ents)), frozenset(map(row_anchor, unique_keys(ents)[0])),
            game_day(rec.get('version_date')))


def build_anchors(file: str) -> frozenset[str]:
    """The ids a build page has a `c-<id>` card for (builds_pages.page_entities, the cards it shows)."""
    return _facts(file)[0]


def build_rows(file: str) -> frozenset[str]:
    """The row anchors a build page has (`row_anchor` of each key it writes once: builds_pages.unique_keys)."""
    return _facts(file)[1]


def game_date(file: str) -> str:
    """The game build's own date of a build record ('' when it has none)."""
    return _facts(file)[2] if file else ''


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


def _row_keys(c: dict) -> list[str]:
    """The keys the build page may hold the row under: its own ('file:id:path'), a shared edit's block
    ('file:@shared:path'); a folded row tries its first source row's."""
    key = str(c.get('key') or c.get('src_key') or '')
    parts = key.split(':', 2)
    if len(parts) < 3:
        return []
    out = [key]
    if c.get('shared_n') or c.get('shared'):
        out.append(row_key(parts[0], '@shared', parts[2]))
    return out


def _href(build: int, ctx: dict, anchor: str | None, keys: list[str] = ()) -> str | None:
    file = ctx['files'].get(build)
    stem = build_pages().get(file) if file else None
    if not stem:
        return None
    rows = build_rows(file) if keys else frozenset()
    frag = next((f'#{a}' for a in map(row_anchor, keys) if a in rows), '')
    if not frag and anchor and anchor in build_anchors(file):
        frag = f'#c-{anchor}'
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
    return (NO_NOTES_WORDS if rows and all(c.get('status') == 'unannounced' for c in rows)
            else HIDDEN_WORDS)


def _row_builds(c: dict, ctx: dict) -> list[int]:
    return sorted({b for b in c.get('builds') or () if isinstance(b, int) and b in ctx['dates']})


def _late(build: int, ctx: dict) -> bool:
    """After the patch: a build newer than the notes' own (`notes_window`) that carries nothing they announced; in a
    window where the notes matched nothing, a game build dated after the notes."""
    if ctx['notes_build'] is not None:
        return build > ctx['notes_build'] and build not in ctx['noted']
    return bool(ctx['notes_date']) and ctx['dates'].get(build, '') > ctx['notes_date']


def row_evidence(c: dict, link: bool = True) -> tuple[str | None, str | None, bool]:
    """(the eye's words, the build page it opens, came after the patch?) for one row not in the notes; all
    None outside a patch (`patch_builds`) or for a row in the notes. `link=False`: the words only (an eye inside a
    <summary> that folds rows with linked eyes of their own: a click there should fold, not leave the page)."""
    from .render import not_in_notes
    ctx = _PATCH.get()
    if ctx is None or not not_in_notes(c):
        return None, None, False
    builds = _row_builds(c, ctx)
    if not builds:
        return None, None, False
    href = _href(builds[0], ctx, _anchor_id(c), _row_keys(c)) if link else None
    open_ = OPEN_WORDS if href else ''
    if c.get('status') == 'hidden' and _late(builds[0], ctx):
        b = builds[0]
        return f'{HIDDEN_WORDS} — came in build {b} ({ctx["dates"][b]}), after the patch{open_}', href, True
    return f'{_lead([c])} — in the game files of {_words(builds, ctx["dates"])}{open_}', href, False


def build_evidence(build: int) -> tuple[str | None, str | None, bool]:
    """row_evidence for a row that is no field change, only its build (a model rebuilt: model_rows)."""
    ctx = _PATCH.get()
    if ctx is None or build not in ctx['dates']:
        return None, None, False
    href = _href(build, ctx, None)
    open_ = OPEN_WORDS if href else ''
    if _late(build, ctx):
        return f'{HIDDEN_WORDS} — came in build {build} ({ctx["dates"][build]}), after the patch{open_}', href, True
    return f'{HIDDEN_WORDS} — in the game files of {_words([build], ctx["dates"])}{open_}', href, False


def band_evidence(rows: list[dict], anchor: str | None = None) -> tuple[str | None, str | None]:
    """(the banner chip's words, the build page it opens) for a band's rows not in the notes: the builds they came in;
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


# ---- the build page's rows: each one's source ------------------------------------------------------------------

# while a build page's rows are written: {diff: the files the head links a diff of, dupes: the keys the page writes
# more than once (no anchor)}
_BUILD: ContextVar[dict | None] = ContextVar('build_rows', default=None)
RAW_MAX = 160            # a raw value longer than this (a list of flags) is cut: the file diff has all of it
# what this update's notes say of a build page's row, by its status (builds_pages.page_entities: only these two)
SOURCE_SAYS = {'hidden': "This update's notes: no line mentions this", 'unannounced': NO_NOTES_WORDS}


@contextmanager
def build_rows_scope(diff, dupes: frozenset[str] | set[str] = frozenset()):
    """While a build page's rows are written: every row gets its source and, its key written once, its anchor
    (`row_source`)."""
    tok = _BUILD.set({'diff': diff, 'dupes': dupes})
    try:
        yield
    finally:
        _BUILD.reset(tok)


def source_of(c: dict) -> tuple | None:
    """(file, entity, path, op, old, new) of the build record's own row behind a build page's row
    (builds_pages.page_entities `src`); None for a row folded from several (REWORK, a re-keyed field, a whole level)."""
    raw = c.get('src')
    if not raw or c.get('path') != raw[2] or c.get('op') != raw[3] or c.get('old') is not raw[4] \
            or c.get('new') is not raw[5]:
        return None
    return raw


def _text(s: str) -> str:
    """Escaped for an element's text (quotes stay: a raw string value is "12", not &quot;12&quot;)."""
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _raw(v) -> str:
    """A raw value as the record holds it (JSON); none: —."""
    if v is None:
        return '—'
    s = json.dumps(v, ensure_ascii=False)
    return f'<code>{_text(s if len(s) <= RAW_MAX else s[:RAW_MAX] + "…")}</code>'


def row_source(c: dict) -> tuple[str | None, str]:
    """(the row's anchor, its source block) on a build page (`build_rows_scope`); (None, '') elsewhere or for a
    folded row; no anchor for a key the page writes twice (two '@shared' blocks with one path: an eye could not tell
    them apart). The block: file › entity › field path as the file writes them (the proof: internal ids on purpose),
    the raw old → new, the tracker commit's diff of the file and what this update's notes say of it."""
    ctx = _BUILD.get()
    raw = source_of(c) if ctx is not None else None
    if raw is None:
        return None, ''
    file, eid, path, _, old, new = raw
    key = row_key(file, eid, path)
    aid = None if key in ctx['dupes'] else row_anchor(key)
    # the file's diff: the head's link of that file (`df-<file>`, its URL written once a page — 6,000 rows repeated a
    # 190-character URL); scripts.js build-src gives the row's link that URL when its source opens
    link = f'<a class="src-d" href="#df-{esc(file)}">file diff ↗</a>' if file in ctx['diff'] else ''
    words = SOURCE_SAYS.get(c.get('status', ''))
    said = f'<span class="src-w">{words}</span>' if words else ''
    return aid, (f'<div class="src-b"><code>{_text(key.replace(":", " › ", 2))}</code>'
                 f'<span>{_raw(old)} → {_raw(new)}</span>{link}{said}</div>')
