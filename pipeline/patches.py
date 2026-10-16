"""Group tracker builds into patches.

A *patch* is an official changelog (Steam or forum) with a date, or — for a big
build nobody wrote notes for — a synthetic "Unannounced update".

Window of patch P: [P.start, next.start) with start = date 00:00 UTC − LEAD.
Valve ships around 17–26 h after the date in the title, but a build sometimes
lands a few hours BEFORE the title date (and sometimes a hotfix title is dated
the day after the big build). Builds inside the fuzzy zone around a boundary
are later re-assigned by pipeline.match to whichever patch's notes describe
them better (see `ambiguous_builds`).

Announcement posts without a change list (hero reveals, events) never open a
window — except a hero's release: the build that ships a hero as released, with its
own announcement near, is a window of its own (`release_windows`) that interrupts
the notes window around it for its release day only.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from . import tracker
from .news import _CHANGE_LINE, TITLE_ONLY, Notes, all_notes, is_changelog_text

LEAD = timedelta(hours=3)
FUZZ_BEFORE = timedelta(hours=12)     # boundary zone: [start - 12h, start + 30h]
FUZZ_AFTER = timedelta(hours=30)
UNANNOUNCED_MIN_FIELDS = 150          # gameplay fields that make a notes-less build its own "patch"
UNANNOUNCED_GAP = timedelta(days=3)   # ... when no changelog lies within this distance
HUGE_BUILD_FIELDS = 1000              # a build this big is an update of its own even beside a follow-up
BUILDS_DIR = tracker.ROOT / 'data' / 'builds'
ANNOUNCEMENT_GAP = timedelta(days=2)  # an announcement names a notes-less big build this close
# a hero's release build is a window of its own, with the hotfixes of its release day (Baba's 6757 at 21:03, its fix
# 6759 at 00:03; Rat King's 6736 and three builds within 4 h); a later build goes back to the notes window around it
RELEASE_TAIL = timedelta(hours=6)


@dataclass
class Patch:
    id: str                    # YYYY-MM-DD, or build-<n> for unannounced updates
    title: str
    date: str
    notes: Notes | None
    builds: list[dict] = field(default_factory=list)   # build index rows
    link: str | None = None                            # announcement URL for notes-less updates
    release: list[str] = field(default_factory=list)   # heroes this window releases (`release_windows`)

    @property
    def has_notes(self) -> bool:
        return self.notes is not None

    @property
    def start(self) -> datetime:
        return _dt(self.date) - LEAD if self.notes else _dt(self.date)


def _dt(s: str) -> datetime:
    if len(s) == 10:
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(s)


def gameplay_fields(row: dict) -> int:
    f = row.get('fields', {})
    return f.get('balance', 0) + f.get('mechanic', 0) + f.get('availability', 0)


_DATED_UPDATE = re.compile(r'\b\d{2}-\d{2}-\d{4}\s+(Update|Patch)\b|· follow-up ', re.I)


def is_patch_notes(n: Notes) -> bool:
    """A changelog: five change lines — or fewer under a dated "MM-DD-YYYY Update" title or as an
    author follow-up. Short ones read as announcements lost 20 posts (2025-01-17's four hero
    releases, 08-18-2024's Restorative Locket…) and ~210 changes were called hidden (audit 2026-10-01)."""
    lines = [ln for s in n.sections for ln in s.lines]
    if is_changelog_text(lines):
        return True
    return bool(_DATED_UPDATE.search(n.title)) and any(_CHANGE_LINE.search(ln) for ln in lines)


def build_index() -> list[dict]:
    path = BUILDS_DIR / 'index.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else []


def _norm(line: str) -> str:
    return ' '.join(line.lower().split())


def drop_near_duplicates(notes: list[Notes], days: int = 2) -> list[Notes]:
    """The forum titles use the US date, Steam uses UTC: the same notes can sit
    a day apart. Keep the longer copy when two notes within `days` share
    at least half of their lines."""
    notes = sorted(notes, key=lambda n: -sum(len(s.lines) for s in n.sections))
    kept: list[Notes] = []
    for n in notes:
        lines = [_norm(ln) for s in n.sections for ln in s.lines]
        dup = False
        for k in kept:
            if abs((_dt(k.date) - _dt(n.date)).days) > days:
                continue
            seen = {_norm(ln) for s in k.sections for ln in s.lines}
            if lines and sum(ln in seen for ln in lines) / len(lines) >= 0.5:
                dup = True
                break
        if not dup:
            kept.append(n)
    return sorted(kept, key=lambda n: n.date)


def merge_same_day(notes: list[Notes]) -> list[Notes]:
    """One patch per day: a Steam announcement and a forum thread of the same
    date become one Notes, the longer text first, the other's sections appended."""
    by_date: dict[str, list[Notes]] = {}
    for n in notes:
        by_date.setdefault(n.date, []).append(n)
    merged = []
    for date, group_ in sorted(by_date.items()):
        group_.sort(key=lambda n: -sum(len(s.lines) for s in n.sections))
        main = group_[0]
        if len(group_) > 1:
            sections = list(main.sections)
            seen = {_norm(ln) for s in main.sections for ln in s.lines}
            for other in group_[1:]:
                lines = [_norm(ln) for s in other.sections for ln in s.lines]
                if lines and sum(ln in seen for ln in lines) / len(lines) >= 0.5:
                    continue
                for s in other.sections:
                    sections.append(type(s)(f'{other.title} · {s.title}', list(s.lines)))
            main = Notes(main.title, main.date, main.url, main.source, sections)
        merged.append(main)
    return merged


def announcements(notes: list[Notes] | None = None) -> list[Notes]:
    """Posts that are not changelogs (hero reveals, events) — never open a window."""
    notes = notes if notes is not None else all_notes()
    return [n for n in notes if not is_patch_notes(n)]


_BARE_DATE = re.compile(r'^\d{2}-\d{2}-\d{4}$')


def _titled(n: Notes, anns: list[Notes]) -> str:
    """A changelog titled only by its date ('09-29-2026') next to an announcement is that
    update's notes: 'City Never Sleeps · 09-29-2026'."""
    if not _BARE_DATE.match(n.title.strip()):
        return n.title
    near = [a for a in anns if abs(_dt(n.date) - _dt(a.date)) <= ANNOUNCEMENT_GAP]
    if not near:
        return n.title
    a = min(near, key=lambda a: abs(_dt(n.date) - _dt(a.date)))
    return f'{a.title} · {n.title}'


def group(notes: list[Notes] | None = None, builds: list[dict] | None = None) -> list[Patch]:
    all_ = notes if notes is not None else all_notes()
    named_only = [a for a in announcements(all_) if a.source == TITLE_ONLY]
    anns = [a for a in announcements(all_) if a.source != TITLE_ONLY]
    notes = merge_same_day(drop_near_duplicates([n for n in all_ if is_patch_notes(n)]))
    builds = builds if builds is not None else build_index()
    patches = [Patch(n.date, _titled(n, anns), n.date, n) for n in sorted(notes, key=lambda n: n.date)]
    releases = release_windows(builds, notes, anns + named_only)
    patches += releases
    released = {r.builds[0]['date'] for r in releases}

    # big builds far from any changelog get their own patch, named after a
    # nearby announcement when there is one ("City Never Sleeps")
    # distance to a MAIN changelog: a small author follow-up next to a big update does not own it
    # (Old Gods, New Blood — build 6127, 4,056 fields — sat in the 2026-01-20 follow-up's window with
    # 1,029 changes called hidden; hero reveal days in hotfix windows, ~500; audit 2026-10-01)
    main = [p for p in patches if p.notes and ' · follow-up ' not in p.notes.title]
    for b in builds:
        if gameplay_fields(b) < UNANNOUNCED_MIN_FIELDS or b['date'] in released:
            continue
        t = _dt(b['date'])
        near = [a for a in anns if abs(t - _dt(a.date)) <= ANNOUNCEMENT_GAP]
        if any(abs(t - _dt(p.date)) <= UNANNOUNCED_GAP for p in main):
            continue
        if (not near and gameplay_fields(b) < HUGE_BUILD_FIELDS
                and any(abs(t - _dt(p.date)) <= UNANNOUNCED_GAP for p in patches if p.notes)):
            continue                         # unnamed, beside a follow-up: stays in that window
        # a post without text (most hero reveals) only names a window that opened anyway
        near = near or [a for a in named_only if abs(t - _dt(a.date)) <= ANNOUNCEMENT_GAP]
        if near:
            a = min(near, key=lambda a: abs(t - _dt(a.date)))
            patches.append(Patch(f'build-{b["build"]}', a.title, b['date'], None, link=a.url))
        else:
            patches.append(Patch(f'build-{b["build"]}', f'Unannounced update (build {b["build"]})', b['date'], None))
    patches.sort(key=lambda p: p.start)

    pre = Patch('pre-notes', 'Before public patch notes', builds[0]['date'][:10] if builds else '', None)
    windows = [p for p in patches if not p.release]
    for r in releases:
        r.builds = []
    for b in builds:
        t = _dt(b['date'])
        # a release takes its build and that day's hotfixes; the notes window around it goes on after them
        owner = next((r for r in releases if r.start <= t < r.start + RELEASE_TAIL), None) or locate(windows, t)
        (owner if owner is not None else pre).builds.append(b)
    # in the order their builds shipped: Danny's release (10-13 21:02) before the 10-14 window it interrupts
    patches.sort(key=lambda p: _dt(p.builds[0]['date']) if p.builds else p.start)
    return ([pre] if pre.builds else []) + patches


def release_windows(builds: list[dict], changelogs: list[Notes], posts: list[Notes]) -> list[Patch]:
    """A build that releases a hero (`history.released_heroes`, the index row's 'released') and has the hero's own
    announcement within `ANNOUNCEMENT_GAP` is a window of its own, named after that post ("Mind the Birds!") — unless
    a changelog is dated the build's own day (then those notes are the release's: 01-17-2025's four heroes). Any build
    within 3 days of a changelog had stayed in that changelog's window: Baba (6757) in 10-05's, Deadman Danny (6779)
    and Violet (6790) in 10-14's, where his release and the balance build after it merged ("Max Health 780 → 730"
    for the notes' 680 → 730, nine of his lines unmatched) and their kits read as hidden (data review 2026-10-17)."""
    out = []
    days = {n.date[:10] for n in changelogs}
    for b in builds:
        if not b.get('released') or b['date'][:10] in days:
            continue
        t = _dt(b['date'])
        near = [a for a in posts if abs(t - _dt(a.date)) <= ANNOUNCEMENT_GAP]
        if not near:
            continue
        a = min(near, key=lambda a: abs(t - _dt(a.date)))
        out.append(Patch(f'build-{b["build"]}', a.title, b['date'], None, [b], link=a.url, release=list(b['released'])))
    return out


def locate(patches: list[Patch], t: datetime) -> Patch | None:
    owner = None
    for p in patches:
        if t >= p.start:
            owner = p
        else:
            break
    return owner


def ambiguous_builds(patches: list[Patch]) -> list[tuple[dict, Patch, Patch]]:
    """(build row, earlier patch, later patch) for builds near a window boundary (a hero's release window keeps its
    builds: the windows around it are each other's neighbours)."""
    out = []
    patches = [p for p in patches if not p.release]
    for prev, cur in zip(patches, patches[1:]):
        lo, hi = cur.start - FUZZ_BEFORE, cur.start + FUZZ_AFTER
        for p in (prev, cur):
            for b in p.builds:
                if lo <= _dt(b['date']) <= hi and gameplay_fields(b) > 0:
                    out.append((b, prev, cur))
    return out
