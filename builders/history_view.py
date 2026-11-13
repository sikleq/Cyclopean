"""Entity history (hero, item and unit pages) — the heart of the site (owner, 2026-10-03: "closer to
Sloppy"): patch by patch, newest first, one group per part of the entity (base stats, the gun, each
ability), the rows = what the files changed (tag, field, old → new) with the eye on what the notes left
out, plus the changes the notes name that live in the game's code (status 'code') and the bug fixes they name
(status 'fix', owner 2026-11-03). Sound / look lines, engine plumbing ("Technical") and unmatched note lines stay
in data/, off the page.

A toolbar filters by tag, by "hidden", by part (Stats / Weapon / Abilities) and by ability (scripts.js
`hist-filter`). Work on a hero still in development hides behind "Before release" once the hero is out, a
band with only rules for every hero behind "For all heroes". Every band with the entity's own changes is open
and in the page (Sloppy's history reads as one document; review 2026-10-05: 86% loaded folded); only the
bands that stay folded are a <template> stamped when opened or filtered.

The patch strip above the toolbar and the ability cards' trail squares show a hover card of what a patch
did (scripts.js `dyn-tip`, the change matrices' card): its counts, how much was not in the notes and the
biggest changes by ability, from ONE JSON blob per page (`strip_data`) — the older bands are still
<template>s, so the card never reads the page (owner 2026-10-04: "2026-09-16 update: 3 changes" said
nothing about what changed)."""
from __future__ import annotations

import re

from .common import HIDDEN_WORDS, band_title_html, esc, glyph_for, mark, patch_name, visual
from .notes_view import text_tag
from .model_rows import MODEL_PREFIX, model_window
from .text_rows import TEXT_PREFIX

# split 2026-11-13: the patch strip (builders/patch_strip.py) and a band's groups (builders/history_groups.py),
# re-exported here for their callers
from .patch_strip import (CUE_GAP, GROUP_SAMPLES, STRIP_MAX, TILE_SAMPLES, WHOLE_PCT, WHOLE_TAGS, _NET_COLOUR, _rank,  # noqa: F401
                          month_cues, patch_strip, strip_bar, strip_data, tile_card, tile_colour)
from .history_groups import (CONVARS_KEY, _dev_only, _drop_prefix, _groups, _namesakes, every_groups, every_name,  # noqa: F401
                             every_sig, id_tail, split_every)

YEAR_BANNERS_MIN = 8      # a history longer than this gets a year banner where the year changes
# note lines shown as rows on their subject's page: changes in the game's code (the files did not move), bug fixes,
# and a line the files could not back ('unmatched', 'nodata' before mid-2024's files, 'untracked' sounds / looks /
# hitboxes): the concept audit of 2026-11-13 found 400 such lines naming a hero, item or unit on no page but the
# patch's ("Mid-Boss: Bounty reduced from 3000 to 1500")
TEXT_STATUSES = ('code', 'fix', 'unmatched', 'nodata', 'untracked')
TAG_FILTERS = ('new', 'rework', 'buff', 'nerf', 'del', 'mech', 'up', 'down')
AREAS = (('stats', 'Stats'), ('weapon', 'Weapon'), ('abil', 'Abilities'))
_ENHANCED = 'Enhanced: '


_BAND_CLASS = re.compile(r'<details class="([^"]*)"')


def band_kind(block: str) -> str:
    """'every' / 'dev' for a band that waits behind "For all …" / "Before release" (its `every-only` / `dev-only`
    class, `_patch_block`), '' for one shown by default."""
    m = _BAND_CLASS.match(block)
    cls = m.group(1).split() if m else []
    return 'every' if 'every-only' in cls else 'dev' if 'dev-only' in cls else ''


def year_class(kinds: list[str]) -> str:
    """The year banner's class from its bands' kinds: a year whose bands all wait behind a toolbar switch waits with
    them (Silencer's "2026" stood over nothing; styles.css hides it while no switch shows a band of it). No :has()."""
    got = set(kinds)
    if not got or '' in got:
        return ''
    return ' every-only' if got == {'every'} else ' dev-only' if got == {'dev'} else ' ed-only'


def _entity_of_line(ln: dict, key_set: set[str], names_by_key: dict[str, str], fallback: str) -> str:
    for ck in ln.get('changes', []):
        file, eid = ck.split(':', 2)[:2]
        if f'{file}:{eid}' in key_set:
            return f'{file}:{eid}'
    low = ln['text'].lower()
    for key, nm in sorted(names_by_key.items(), key=lambda kv: -len(kv[1])):
        if key != fallback and nm and nm.lower() in low:
            return key
    subj = (ln.get('subject') or '').lower()
    for key, nm in names_by_key.items():
        if nm and nm.lower() == subj:
            return key
    return fallback


def history_table(keys: list[tuple[str, str, str | None]], names: list[str], by_ent, by_subject, rel: str,
                  line_names: bool = True, areas: dict[str, str] | None = None, gone: set[str] = frozenset(),
                  in_dev: bool = False, area_labels: tuple[tuple[str, str], ...] = AREAS,
                  merge=None, enhanced: bool = False, ults: frozenset[str] = frozenset(),
                  every_label: str | None = None, chip_of: dict[str, str] | None = None,
                  facts_out: dict | None = None) -> str:
    """The History section: heading, toolbar, blocks. keys: [(entity key, display name, icon url)] in
    display order, the page's own entity first; names: subjects whose note lines belong here.
    `line_names`: the other keys' names pull note lines in too (a hero's abilities do; a boss's "Rocket
    Barrage" would drag in the hero ability of that name). `areas`: key -> stats / weapon / abil (a
    hero's page); `gone`: keys of abilities the entity no longer has; `in_dev`: the entity itself is in
    development, so its development work shows by default. `area_labels`: the part buttons (a unit
    family: its tiers); `merge`: members whose rows in a patch are identical show as ONE group named by
    merge(labels) (unit_families.merged_label) — the five Gutter Ghouls I, the four Walkers.
    `enhanced`: an item page — its "Enhanced: …" rows (the Enhanced version, 14% of item rows) are their
    own group under "Enhanced version", the parts Base / Enhanced. `ults`: keys of the hero's ultimate (its
    icon gets the corner mark). `every_label`: the toolbar button that shows the bands holding only rules for
    every hero / item ("For all heroes"); None: the kind those bands hold. `chip_of`: a sub-ability's key -> its
    parent's, whose toolbar chip holds it too (Ava's chip shows "Ava · trigger")."""
    order = {k: i for i, (k, _, _) in enumerate(keys)}
    meta = {k: (nm, ic) for k, nm, ic in keys}
    names_by_key = {k: nm for k, nm, _ in keys}
    key_set = set(order)
    own = keys[0][0]
    subjects = [n for n in names if n] + ([nm for k, nm, _ in keys[1:]] if line_names else [])
    per_patch: dict[str, dict] = {}
    if enhanced:
        enh = own + '#enh'
        order[enh] = len(order)
        meta[enh] = ('Enhanced version', meta[own][1])
        areas = {**(areas or {}), own: 'base', enh: 'enh'}
        area_labels = (('base', 'Base'), ('enh', 'Enhanced'))
    for key, _, _ in keys:
        for row, ch in by_ent.get(key, []):
            slot = per_patch.setdefault(row['id'], {'row': row, 'ch': {}, 'lines': {}})
            if enhanced and key == own:
                ups = [c for c in ch if str(c.get('label') or '').startswith(_ENHANCED)]
                if ups:
                    slot['ch'].setdefault(enh, []).extend(
                        {**c, 'label': str(c['label'])[len(_ENHANCED):]} for c in ups)
                ch = [c for c in ch if not str(c.get('label') or '').startswith(_ENHANCED)]
            slot['ch'].setdefault(key, []).extend(ch)
        # its name / description changes (text_rows): rows of its group, never counted
        for row, ts in by_ent.get(TEXT_PREFIX + key, []):
            slot = per_patch.setdefault(row['id'], {'row': row, 'ch': {}, 'lines': {}})
            slot.setdefault('texts', {}).setdefault(key, []).extend(ts)
        # its model rebuilt (model_rows): a row of its group, never counted
        for row, ms in by_ent.get(MODEL_PREFIX + key, []):
            slot = per_patch.setdefault(row['id'], {'row': row, 'ch': {}, 'lines': {}})
            slot.setdefault('models', {}).setdefault(key, []).extend(ms)
    seen: set[tuple[str, str]] = set()
    for n in subjects:
        for row, ln in by_subject.get(n.lower(), []):
            if ln['status'] not in TEXT_STATUSES or (row['id'], ln['text']) in seen:
                continue
            seen.add((row['id'], ln['text']))
            slot = per_patch.setdefault(row['id'], {'row': row, 'ch': {}, 'lines': {}})
            slot['lines'].setdefault(_entity_of_line(ln, key_set, names_by_key, own), []).append(ln)
    heading = '<div class="h2row"><h2>History</h2></div>'
    if not per_patch:
        return heading + '<p class="muted">No recorded changes.</p>'
    from .cards import history_hints, player_facing
    from .shared_rows import is_every
    # two fields under one label read alike in every patch of the history (cards.history_hints)
    every: dict[str, list[dict]] = {}
    for slot in per_patch.values():
        for key, ch in slot['ch'].items():
            every.setdefault(key, []).extend(ch)
    hints = {key: history_hints(ch) for key, ch in every.items()}
    blocks, facts = [], {'tags': set(), 'hidden': 0, 'dev': 0, 'areas': set(), 'abs': set()}
    year = None
    years: list[tuple[int, str, list[str]]] = []          # (its place in blocks, the year, its bands' kinds)
    # "patch ↗" lands on the page's own entity in the patch (a Game system is no entity of the files)
    link_id = own.partition(':')[2] if own.partition(':')[0].endswith('.vdata') else None
    for pid in sorted(per_patch, key=lambda k: per_patch[k]['row']['date'], reverse=True):
        slot = per_patch[pid]
        # every band with the entity's own changes stands open, like Sloppy's (86% loaded folded, review
        # 2026-10-05); a band of work before release or of rules for every hero only stays folded, and only a
        # folded band waits in a <template> (an open one is in the page: Ctrl+F finds it, #p- jumps land true)
        shown = [c for ch in slot['ch'].values() for c in ch
                 if (in_dev or c.get('status') != 'unreleased') and not is_every(c)]
        real = (bool(slot['lines']) or bool(slot.get('texts'))
                or any(model_window(ms) for ms in slot.get('models', {}).values()) or bool(player_facing(shown)))
        block = _patch_block(pid, slot, order, meta, names, rel, real, not real, areas, in_dev,
                             facts, merge, headless_own=enhanced, hints=hints, ults=ults, entity_id=link_id,
                             gone=gone)
        if not block:
            continue
        y = slot['row']['date'][:4]
        if y != year and len(per_patch) > YEAR_BANNERS_MIN:
            # a hero has 55-65 bands: the year in the section-banner style tells where one is (no fold)
            years.append((len(blocks), y, []))
            blocks.append('')
            year = y
        if years:
            years[-1][2].append(band_kind(block))
        blocks.append(block)
    for at, y, kinds in years:
        blocks[at] = f'<h3 class="banner sub hyear{year_class(kinds)}"><span class="bt">{esc(y)}</span></h3>'
    if every_label is None:
        # what the bands of rules for all hold, in words ("For all abilities & items"; a unit page's button read
        # "For all 1", review 2026-10-05)
        kinds = sorted(facts.get('every_names') or ())
        every_label = f'For {kinds[0][0].lower()}{kinds[0][1:]}' if len(kinds) == 1 else 'Rules for all'
    bar = toolbar(facts, keys, areas, gone, in_dev, rel, area_labels, ults, every_label, chip_of)
    strip = patch_strip(facts.get('strip', []))
    if facts_out is not None:
        # the page head's "N not in patch notes" link (hidden_link), and the strip: a hero, item or unit page puts
        # it right under its head (Sloppy's sits in the head row at y=312; ours was under History, 1365-2096 px
        # down — review 2026-10-05)
        facts_out['hidden'] = facts['hidden']
        facts_out['strip'], strip = strip, ''
        facts_out['strip_tiles'] = len(facts.get('strip', [])) > 1     # patch_strip draws tiles for two or more
    cls = 'hblocks' + (' show-dev' if in_dev else '')
    return f'{heading}{strip}{bar}<div id="history" class="{cls}">{"".join(blocks)}</div>'


def head_strip(told: dict) -> str:
    """The entity's patch strip (and the hover cards' data blob) inside the page head, under the name and its chips,
    with a small "Patches" label — as Sloppy's sits in its header band. Two or three tiles alone under the portrait
    read as leftovers (Violet, Deadman Danny, Ablative Coat; visual pass 2026-10-17, round 2). Without tiles (one
    patch) only the blob comes: the ability cards' trail squares read it."""
    strip = told.get('strip') or ''
    if not strip or not told.get('strip_tiles'):
        return strip
    return f'<div class="head-strip"><span class="hs-l">Patches</span>{strip}</div>'


def hidden_link(n: int) -> str:
    """The entity head's way to what Valve did not say about it: "N not in patch notes", a link that presses the
    history's eye and scrolls there (scripts.js hidden-hash; the button sat 1.8 screens down on Haze)."""
    if not n:
        return ''
    return f'<a class="chip eye-link" href="#hidden">{mark("hidden")}{n} not in patch notes</a>'


def now_fold(summary: str, body: str) -> str:
    """What an item or unit is today, above its history: open (owner 2026-10-04: nothing folded by default —
    a closed fold hid the best block of the page); the summary line still folds it away. `summary`: plain text."""
    if not body:
        return ''
    return (f'<details class="now px-frame" open><summary>{esc(summary)}</summary>'
            f'<div class="now-body">{body}</div></details>')


def toolbar(facts: dict, keys: list[tuple], areas: dict | None, gone: set[str], in_dev: bool, rel: str,
            area_labels: tuple[tuple[str, str], ...] = AREAS, ults: frozenset[str] = frozenset(),
            every_label: str = 'For all', chip_of: dict[str, str] | None = None) -> str:
    """Tags present (multi-select), the eye (only hidden), parts of a hero, its abilities as icons (the
    current ones in slot order, removed ones grey after a divider), "Before release". One compact row: the
    controls are badge-high (owner 2026-10-04). A chosen tag is aria-pressed, never the class "on" — that
    is the ON tag's colour (a chosen NERF turned green)."""
    from .render import tag_badge
    parts = []
    tags = [t for t in TAG_FILTERS if t in facts['tags']]
    if tags:
        parts.append('<span class="hf-tags">' + ''.join(
            tag_badge(t, t.upper(), 'button', f' data-f-tag="{t}" aria-pressed="false"') for t in tags) + '</span>')
    if facts['hidden']:
        parts.append(f'<button class="px-btn hf-hidden" data-toggle-class="only-hidden" data-target="#history" '
                     f'aria-pressed="false">'
                     f'{mark("hidden")}{HIDDEN_WORDS} <span class="n">{facts["hidden"]}</span></button>')
    if areas and len(facts['areas']) > 1:
        parts.append('<span class="hf-areas">' + ''.join(
            f'<button class="px-btn" data-f-area="{a}" aria-pressed="false">{esc(lbl)}</button>' for a, lbl in area_labels
            if a in facts['areas']) + '</span>')
    chips = [(k, nm, ic) for k, nm, ic in keys[1:] if k in facts['abs']]
    if len(chips) > 1:
        # one chip per name (Calico's two "Queen of Shadows"), the current ones in slot order; removed ones
        # fold behind "Removed (N)" (13 of Calico's 18 chips, advisor 10-03); no art -> the name as text
        meta = {k: (nm, ic) for k, nm, ic in keys}

        def merged(sel: list[tuple]) -> list[tuple[list[str], str, str | None]]:
            by_name: dict[str, list] = {}
            for k, nm, ic in sel:
                base = (chip_of or {}).get(k)          # a sub-ability rides on its parent's chip
                if base in meta:
                    nm, ic = meta[base][0], meta[base][1] or ic
                slot = by_name.setdefault(nm, [[], nm, ic])
                slot[0].append(k)
                slot[2] = slot[2] or ic
            return [tuple(v) for v in by_name.values()]
        # a removed namesake joins the current chip's ids (Viscous' removed "…_alt" had a chip of its own)
        every_chip = merged(chips)
        now = [c for c in every_chip if any(k not in gone for k in c[0])]
        old = [c for c in every_chip if all(k in gone for k in c[0])]

        def chip(ks: list[str], nm: str, ic: str | None, cls: str = '') -> str:
            eids = ' '.join(k.partition(':')[2] for k in ks)
            inner = visual(ic, '', 'hf-im') if ic else f'<span class="hf-txt">{esc(nm)}</span>'
            ult = ' ult' if any(k in ults for k in ks) else ''
            return (f'<button class="hf-ab{cls}{ult}{"" if ic else " txt"}" data-f-ab="{esc(eids)}" '
                    f'data-tooltip="{esc(nm)}" aria-label="{esc(nm)}" aria-pressed="false">{inner}</button>')
        gone_html = ''
        if old:
            gone_html = (f'<button class="px-btn hf-gone-btn" data-toggle-class="show-gone" data-target=".hf-abs" '
                         f'aria-pressed="false">'
                         f'Removed <span class="n">{len(old)}</span></button>' + ''.join(chip(*c, ' gone') for c in old))
        parts.append('<span class="hf-abs">' + ''.join(chip(*c) for c in now) + gone_html + '</span>')
    if facts['dev'] and not in_dev:
        # a toggle button like the eye's, not a switch with a track: the bar fits one row (owner 2026-10-04)
        parts.append(f'<button class="px-btn hf-dev" data-toggle-class="show-dev" data-target="#history" '
                     f'aria-pressed="false">{mark("unreleased")}Before release <span class="n">{facts["dev"]}</span></button>')
    if facts.get('every'):
        # the bands that hold only a rule for every hero (the level curve, a default of every ability): in place,
        # one click away — like "Before release" (23% of the bands, 22 hero pages opened their history with one)
        parts.append(f'<button class="px-btn hf-every" data-toggle-class="show-every" data-target="#history" '
                     f'aria-pressed="false">{esc(every_label)} <span class="n">{facts["every"]}</span></button>')
    if not parts:
        return ''
    return '<div class="toolbar hist-bar">' + '<span class="sep"></span>'.join(parts) + '</div>'


NOTED_LOOSELY = ('described', 'mismatch')  # rows a patch-note line covers without its exact numbers
BAND_NOTE_MIN = 3         # a line covering this many entities is said once per band, not under each ability


def valve_notes(pid: str, rows: list[dict]) -> tuple[dict[str, str], dict[str, str]]:
    """Valve's own words for the rows a line covers without exact numbers (described / mismatch): (lines about
    this group, lines about many entities said once for the band), each {its words, lower-cased: text} — a line
    Valve posted twice is said once. A documented row needs none: its line only repeats "label old → new".
    Sloppy's rows ARE the patch-note lines; ours showed none, so a described row looked like any other (review
    2026-10-05: Haze's 67 described rows)."""
    from . import archive
    idx, lines = archive.note_lines(pid)
    mine: dict[str, str] = {}
    wide: dict[str, str] = {}
    for c in rows:
        if c.get('status') not in NOTED_LOOSELY:
            continue
        for i in idx.get(str(c.get('key') or ''), ()):
            text, _, n_ents = lines[i]
            (wide if n_ents >= BAND_NOTE_MIN else mine).setdefault(' '.join(text.lower().split()), text)
    return mine, wide


def _vnote(text: str) -> str:
    """One patch-note line under the rows it covers, quiet: a note, never a row (no counter or filter counts it)."""
    return f'<div class="vnote"><span class="vn-l">Patch notes</span>{esc(text)}</div>'


def patch_href(pid: str, rel: str, entity_id: str | None = None, also: tuple[str, ...] | list[str] = ()) -> str:
    """The patch page, at the entity when there is one: its card in the Patch notes tab (what Valve said about it,
    `#n-<id>`) when the notes name it, else its place under All changes (`#c-<id>`, its own card or a shared edit's
    card: archive.change_anchors; scripts.js tabs opens the tab). Sloppy's band lands on the hero's block inside the
    patch (review 2026-10-05). `also`: other ids of the band (a unit family's members, in order) tried after the
    page's own; an id the patch page has no place for is no link target — the page itself is (2,112 of 6,295 band
    links pointed at a missing id, review 2026-10-05)."""
    from . import archive
    base = f'{rel}patches/{esc(pid)}.html'
    ids = [i for i in dict.fromkeys((entity_id, *also)) if i]
    if not ids:
        return base
    notes, cards = archive.note_anchors(pid), archive.change_anchors(pid)
    for i in ids:
        if i in notes:
            return f'{base}#n-{esc(i)}'
        if i in cards:
            return f'{base}#c-{esc(i)}'
    return base


def _eye_chip(text: str, words: str | None, href: str | None) -> str:
    """The banner's "N not in patch notes" chip. With a build to open the whole chip is the link (review 2026-10-17: only
    its 13px eye was, the words beside it folded the band); its words are the tooltip, the count and the words its
    name for a screen reader."""
    if not href:
        return f'<span class="chip eye-chip">{mark("hidden", words)}<span class="ec-n">{text}</span></span>'
    w = esc(words or '')
    return (f'<a class="chip eye-chip" href="{esc(href)}" data-tooltip="{w}" aria-label="{esc(text)} — {w}">'
            f'<span class="mark hidden" aria-hidden="true"></span><span class="ec-n">{text}</span></a>')


def _banner(pid: str, hdr: dict, counted_all: list[dict], rel: str, every: list[dict] = (),
            entity_id: str | None = None, texts: str | None = None, href: str | None = None,
            also: tuple[str, ...] | list[str] = (), net: str | None = None,
            eye: tuple[str | None, str | None] = (None, None)) -> tuple[str, str]:
    """(the band's <summary>, its has-hidden classes). The title is plain text, so a click opens the band in
    place (it used to leave for the patch archive); a small "patch ↗" goes there on purpose, at the entity
    (`patch_href`; `href`: where it goes instead — a band holding only rules for all goes to its Game band). The
    counters and the eye count are what scripts.js recounts while a filter is on. `every`: the rows of rules for
    every hero (shared_rows), counted apart in a chip of their own ("+38 for all heroes"). `net`: the band's net mark
    (weights.net_of of its counted rows, `_patch_block`); None weighs `counted_all` here. `eye`: the eye chip's words
    and the build page it opens (evidence.band_evidence)."""
    from .render import not_in_notes, tag_summary
    from .weights import net_chip, net_of
    if net is None:
        net = net_of(counted_all)
    n_hidden = sum(1 for c in counted_all if not_in_notes(c))
    # the banner says how many rows the notes left out — "all N" only when N is more than one; in a band the notes
    # never mentioned the rows' eyes are dimmed (styles.css .all-hidden), each still a link to its row's proof
    # (review 2026-10-17), except a row that came after the patch in a later build (its eye's words are the proof)
    all_hidden = bool(n_hidden) and n_hidden == len(counted_all)
    # an update that had no patch notes at all (Rat King's build 6736) says so: nothing was left out of notes
    no_notes = all_hidden and all(c.get('status') == 'unannounced' for c in counted_all)
    # one term a site (review 2026-10-17): "not in patch notes" for what the notes left out, "no patch notes" for an
    # update without any (scripts.js hist-filter keeps that one under a filter); the whole chip links the proof
    text = ('no patch notes' if no_notes else f'all {n_hidden} not in patch notes' if all_hidden and n_hidden > 1
            else f'{n_hidden} not in patch notes')
    chips = _eye_chip(text, *eye) if n_hidden else ''
    # one short chip per kind: they wrap under the title on a phone (one long chip ran 145px off a 390px screen)
    chips += ''.join(f'<span class="chip shr-chip">+{len(rows)} for {esc(name.lower())}</span>'
                     for name, rows in every_groups(list(every)).items())
    # a rename or a new description says so: a band that held only one read as an empty patch (Unstoppable
    # 2024-09-26; review 2026-10-05) — words, no counter (text_rows are never counted)
    if texts:
        chips += f'<span class="chip txt-chip">{esc(texts)}</span>'
    hidden_cls = ' has-hidden' + (' all-hidden' if all_hidden else '') if n_hidden else ''
    cls = ' named' if patch_name(hdr['title']) else ''
    # what the patch did to this entity on balance, weighed as the change matrices weigh it (weights.net_of): one
    # small chip after the counters, none when no row takes a side
    summary = (f'<summary class="banner{cls}"><span class="bt">{band_title_html(hdr)}</span>'
               f'<span class="bc">{tag_summary(counted_all)}{net_chip(net)}{chips}'
               f'<a class="pnotes" href="{href or patch_href(pid, rel, entity_id, also)}">patch ↗</a></span></summary>')
    return summary, hidden_cls


def _patch_block(pid: str, slot: dict, order: dict, meta: dict, names: list[str], rel: str, open_: bool,
                 lazy: bool, areas: dict | None, in_dev: bool, facts: dict, merge=None,
                 headless_own: bool = False, hints: dict | None = None, ults: frozenset[str] = frozenset(),
                 entity_id: str | None = None, gone: set[str] | frozenset[str] = frozenset()) -> str:
    """One patch = its banner + ONE full-width panel: per part its icon on a plate in a column of its own,
    then its name and rows (Sloppy's ability block). `hints`: part key -> its cards.history_hints."""
    from . import archive
    from .cards import ability_plate, disambiguate, every_key, every_links, is_hidden, player_facing, sub_head
    from .evidence import band_evidence, patch_builds
    from .render import not_in_notes, same_change, tag_of
    from .weights import net_of
    hdr = slot['row']
    from .game_systems import SECTION
    every_href = lambda sid: f'{rel}{SECTION}/{sid}.html#p-{pid}'      # noqa: E731
    own_slot, every_all = split_every(slot, in_dev)
    builds = archive.builds_of(pid)
    with patch_builds(builds, rel, pid):                 # each eye names the build it came in and opens it
        groups = _groups(own_slot, order, meta, names, hints, merge)
    namesakes = {} if merge else _namesakes(groups, meta, gone)
    band_notes: dict[str, str] = {}
    counted_all, all_dev, card = [], True, []
    band_seen: set[tuple] = set()
    single = len(order) == 1 or (merge and len(groups) == 1 and len(groups[0]['keys']) == len(order))
    # a group of text changes only (a rename) is work before release when every other group of the band is
    # (heroes in development rename their abilities): it waits behind "Before release" with them
    pre = [None if not g['changes'] and not g['lines'] else _dev_only(g, in_dev) for g in groups]
    others = [x for x in pre if x is not None]
    text_dev = bool(others) and all(others)
    parts = []
    for gi, g in enumerate(groups):
        key = g['keys'][0]
        nm, ic = meta[key]
        if len(g['keys']) > 1 and merge:
            nm = merge([meta[k][0] for k in g['keys']])
        nm = namesakes.get(gi, nm)
        file, _, eid = key.partition(':')
        rows = player_facing(g['changes'])
        dev = [c for c in rows if c.get('status') == 'unreleased']
        live = [c for c in rows if c.get('status') != 'unreleased']
        group_dev = text_dev if pre[gi] is None else pre[gi]
        all_dev = all_dev and group_dev
        # a rule for every hero (shared_rows.is_every) is not in the groups (split_every): the band's own counters,
        # its eye and the strip tile count what changed on THIS entity
        counted = rows if in_dev else live
        # a family or a Game system: the same change on several members counts once in the band (its groups still
        # list it), as in the change matrix and on the home icon (one edit over 15 breakables read 138 / 52 / 50)
        fresh = counted
        if merge:
            counted = list({same_change(c): c for c in counted}.values())   # a merged group's members, once
            fresh = [c for c in counted if same_change(c) not in band_seen]
            band_seen.update(same_change(c) for c in counted)
        counted_all += fresh
        facts['tags'] |= {tag_of(c)[0] for c in rows}
        facts['hidden'] += sum(1 for c in fresh if not_in_notes(c))
        facts['dev'] += len(dev)
        area = ' '.join(dict.fromkeys((areas or {}).get(k, 'abil') for k in g['keys']))
        facts['areas'] |= set(area.split())
        # ability chips are abilities and guns (a family's tiers are parts, not chips) — every key of a merged
        # group (the Patron's "Rocket Barrage · Stomp · Weapon"): its chips were Rocket Barrage's only
        for k in g['keys']:
            if len(order) > 1 and k != list(order)[0] and (areas or {}).get(k, 'abil') in ('abil', 'weapon'):
                facts['abs'].add(k)
        ids = ' '.join(k.partition(':')[2] for k in g['keys'])
        hidden = is_hidden(counted)
        # an item's own rows need no header naming the item (its Enhanced version gets one)
        headless = single or (headless_own and key == list(order)[0])
        ult = any(k in ults for k in g['keys'])
        plate = '' if headless else ability_plate(ic, glyph_for(file, eid), ult)
        head = '' if headless else sub_head(nm, ic, glyph_for(file, eid), counted, hidden, icon=False)
        cls = 'hgroup' + (' has-ic' if plate else '') + (' has-hidden' if hidden else '') + (' dev-only' if group_dev else '')
        mine, wide = valve_notes(pid, counted)
        band_notes.update(wide)
        notes = ''.join(_vnote(_drop_prefix(t, names + [nm])) for t in mine.values())
        # every id of a merged group: a filter or a link to its second entry ("Breakable lion statue") found none
        parts.append(f'<div class="{cls}" data-ab="{esc(ids)}" data-area="{esc(area)}">{plate}'
                     f'<div class="hg-b">{head}{g["rows"]}{notes}</div></div>')
        ref = ('' if headless else nm, ic or '', ids, int(ult), 0)
        card.append((ref, disambiguate(fresh, (hints or {}).get(key))))
    # a rule for every hero is ONE block of link rows for the whole band, after its groups: it sat under each of
    # the hero's abilities it touched (Calico 2026-01-22: 15 copies of "All abilities & items: 1 change", ~1000 px)
    if every_all:
        parts.append(f'<div class="hgroup shr-band" data-ab="" data-area=""><div class="hg-b">'
                     f'{every_links(every_all, every_href)}</div></div>')
    if not parts:
        return ''
    if band_notes:                    # a line about many entities, said once for the band ("…globally reduced by 7%")
        parts.insert(0, '<div class="vnotes">' + ''.join(_vnote(t) for t in band_notes.values()) + '</div>')
    every_only = not groups
    # the band's net mark, ONE for its banner and its strip tile's card (the matrix cell weighs the same rows)
    net = net_of(counted_all, in_dev)
    # the entity's patch strip above the toolbar: what this patch did, by tag, and its hover card (dev-only
    # bands excluded). A band that holds only a rule for every hero gets no tile, as in the matrices and the trail
    if not (all_dev and not in_dev) and counted_all:
        tally: dict[str, int] = {}
        for c in counted_all:
            tally[tag_of(c)[0]] = tally.get(tag_of(c)[0], 0) + 1
        for name, rows in every_groups(every_all).items():
            # a rule for all is counted apart (not in the tile's counts): its group says its own number in the card
            card.append(((name, '', '', 0, 1), rows))
        facts.setdefault('strip', []).append((pid, hdr, tally, sum(not_in_notes(c) for c in counted_all),
                                              tile_card(card), net))
    if every_only:
        facts['every'] = facts.get('every', 0) + 1
        facts.setdefault('every_names', set()).update(every_groups(every_all))
    from .text_rows import text_kind
    # "patch ↗": a band of rules for all only goes to its Game band (the patch page has no card for the entity); else
    # the entity's place in the patch, its family's members after it (patch_href)
    href = esc(every_href(every_key(every_all[0])[0])) if every_only and every_all else None
    also = [k.partition(':')[2] for g in groups for k in g['keys'] if k.partition(':')[0].endswith('.vdata')]
    with patch_builds(builds, rel, pid):
        eye = band_evidence(counted_all, entity_id)     # the banner's eye: the band's builds (an all-hidden band's only eye)
    summary, hidden_cls = _banner(pid, hdr, counted_all, rel, every_all, entity_id,
                                  text_kind([t for ts in (slot.get('texts') or {}).values() for t in ts]),
                                  href=href, also=also if entity_id else (), net=net, eye=eye)
    dev_cls = ' dev-only' if all_dev and not in_dev and not every_only else ''
    dev_cls += ' every-only' if every_only else ''
    panel = f'<div class="hpanel{hidden_cls}">{"".join(parts)}</div>'
    meta_attrs = ''
    if lazy:
        panel = f'<template class="hp-t">{panel}</template>'
        # what the band holds, so a filter skips stamping a band that cannot match
        tags = {tag_of(c)[0] for g in groups for c in player_facing(g['changes'])}
        tags |= {m.group(1) for g in groups for ln in g['lines']                  # a code line's word tag
                 for m in [re.search(r'class="tag (\w+)', text_tag(ln['text'], ln.get('topic')))] if m}
        abs_ = ' '.join(dict.fromkeys(k.partition(':')[2] for g in groups for k in g['keys']))
        areas_ = ' '.join(dict.fromkeys(a for g in groups for k in g['keys'] for a in [(areas or {}).get(k, 'abil')]))
        meta_attrs = f' data-tags="{esc(" ".join(sorted(tags)))}" data-abs="{esc(abs_)}" data-areas="{esc(areas_)}"'
    # the anchor change matrices and the home page link to (#p-<patch id>; scripts.js opens it)
    return (f'<details class="pblock{hidden_cls}{dev_cls}" id="p-{esc(pid)}"{meta_attrs}'
            f'{" open" if open_ and not lazy else ""}>{summary}{panel}</details>')
