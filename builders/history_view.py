"""Entity history (hero, item and unit pages) — the heart of the site (owner, 2026-10-03: "closer to
Sloppy"): patch by patch, newest first, one group per part of the entity (base stats, the gun, each
ability), the rows = what the files changed (tag, field, old → new) with the eye on what the notes left
out, plus the changes the notes name that live in the game's code (status 'code'). Bug fixes, sound /
look lines, engine plumbing ("Technical") and unmatched note lines stay in data/, off the page.

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

import json
import re

from .common import EYE_MARK, esc, glyph_for, mark, patch_name, patch_title_html, patch_title_text, visual
from .notes_view import _highlight, text_tag
from .text_rows import TEXT_PREFIX, text_rows

YEAR_BANNERS_MIN = 8      # a history longer than this gets a year banner where the year changes
TEXT_STATUSES = ('code',)  # note lines shown as rows: changes in the game's code (the files did not move)
TAG_FILTERS = ('new', 'rework', 'buff', 'nerf', 'del', 'mech', 'up', 'down')
AREAS = (('stats', 'Stats'), ('weapon', 'Weapon'), ('abil', 'Abilities'))
_ENHANCED = 'Enhanced: '


def _drop_prefix(text: str, names: list[str]) -> str:
    """'Abrams: Siphon Life DPS reduced…' under the Siphon Life block -> 'DPS reduced…'."""
    out = text
    changed = True
    while changed:                       # "Abrams: Siphon Life …" carries both, hero first
        changed = False
        for n in sorted((n for n in names if n), key=len, reverse=True):
            m = re.match(rf'\s*{re.escape(n)}\s*(?:[:\-–—]\s*|\s+(?=\S))', out, flags=re.I)
            if m:
                out = out[m.end():]
                changed = True
    out = out.strip()
    return out[:1].upper() + out[1:] if out else text


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
                  every_label: str = 'For all', chip_of: dict[str, str] | None = None) -> str:
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
    every hero / item ("For all heroes"). `chip_of`: a sub-ability's key -> its parent's, whose toolbar chip
    holds it too (Ava's chip shows "Ava · trigger")."""
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
    for pid in sorted(per_patch, key=lambda k: per_patch[k]['row']['date'], reverse=True):
        slot = per_patch[pid]
        # every band with the entity's own changes stands open, like Sloppy's (86% loaded folded, review
        # 2026-10-05); a band of work before release or of rules for every hero only stays folded, and only a
        # folded band waits in a <template> (an open one is in the page: Ctrl+F finds it, #p- jumps land true)
        shown = [c for ch in slot['ch'].values() for c in ch
                 if (in_dev or c.get('status') != 'unreleased') and not is_every(c)]
        real = bool(slot['lines']) or bool(slot.get('texts')) or bool(player_facing(shown))
        block = _patch_block(pid, slot, order, meta, names, rel, real, not real, areas, in_dev,
                             facts, merge, headless_own=enhanced, hints=hints, ults=ults)
        if not block:
            continue
        y = slot['row']['date'][:4]
        if y != year and len(per_patch) > YEAR_BANNERS_MIN:
            # a hero has 55-65 bands: the year in the section-banner style tells where one is (no fold)
            blocks.append(f'<h3 class="banner sub hyear"><span class="bt">{esc(y)}</span></h3>')
            year = y
        blocks.append(block)
    bar = toolbar(facts, keys, areas, gone, in_dev, rel, area_labels, ults, every_label, chip_of)
    cls = 'hblocks' + (' show-dev' if in_dev else '')
    return f'{heading}{patch_strip(facts.get("strip", []))}{bar}<div id="history" class="{cls}">{"".join(blocks)}</div>'


STRIP_MAX = 40            # the latest patches in the strip (one row that never scrolls: tiles shrink to fit)
TILE_SAMPLES = 6          # a strip tile's hover card lists the patch's biggest changes…
GROUP_SAMPLES = 3         # …and keeps an ability's own biggest ones for its trail squares' card


def now_fold(summary: str, body: str) -> str:
    """What an item or unit is today, above its history: open (owner 2026-10-04: nothing folded by default —
    a closed fold hid the best block of the page); the summary line still folds it away."""
    if not body:
        return ''
    return (f'<details class="now px-frame" open><summary>{summary}</summary>'
            f'<div class="now-body">{body}</div></details>')


WHOLE_TAGS = ('new', 'rework', 'del')   # a thing added, reworked or removed: no %, but as big as 100%
WHOLE_PCT = 100.0


def _rank(c: dict) -> tuple:
    """The hover cards' order of "biggest" (strip tile, trail square, home feed icon): the size of the change,
    then the tag order. A NEW / REWORK / DEL row has no % and counts as 100%: a hero's release card listed two
    small base-stat NERFs ahead of its 14 new things (Rat King, review 2026-10-04). The change matrices keep
    their own order (dynamics_page._collect: the owner's call)."""
    from .render import TAG_ORDER, tag_of
    tag = tag_of(c)[0]
    pct = c.get('pct')
    size = abs(pct) if isinstance(pct, (int, float)) else WHOLE_PCT if tag in WHOLE_TAGS else 0.0
    return (-size, TAG_ORDER.get(tag, 9))


def tile_card(groups: list[tuple[tuple, list[dict]]]) -> list[list]:
    """One strip tile's hover card: per group (ability, gun, base stats) [ref, {tag: n}, hidden, samples], a
    sample = [label, old, new, tag, hidden 0/1, rank in the patch]. A group keeps its GROUP_SAMPLES biggest
    rows and any row among the patch's TILE_SAMPLES biggest, so the strip card (top rows across the patch)
    and a trail square's card (one ability) both come from it. `groups`: [(ref, its counted rows)]."""
    from .render import not_in_notes, tag_of, vals_text
    from .shared_rows import is_every
    # a rule for every hero ranks after the entity's own changes: the card is about what changed on THIS one
    flat = sorted((c for _, cs in groups for c in cs), key=lambda c: (is_every(c), *_rank(c)))
    rank = {id(c): r for r, c in enumerate(flat)}
    out = []
    for ref, cs in groups:
        if not cs:
            continue
        mine = sorted(cs, key=lambda c: rank[id(c)])
        keep = [c for i, c in enumerate(mine) if i < GROUP_SAMPLES or rank[id(c)] < TILE_SAMPLES]
        counts: dict[str, int] = {}
        for c in cs:
            counts[tag_of(c)[0]] = counts.get(tag_of(c)[0], 0) + 1
        hidden = sum(1 for c in cs if not_in_notes(c))
        out.append([ref, counts, hidden, [[str(c.get('label') or ''), *vals_text(c), tag_of(c)[0],
                                           int(not_in_notes(c)), rank[id(c)]] for c in keep]])
    return out


def strip_data(items: list[tuple]) -> dict:
    """The page's hover-card data for its strip tiles and trail squares: t = tiles in strip order,
    [patch id, title, named?, {tag: n}, hidden, [[group, {tag: n}, hidden, samples], …]]; g = the groups
    [name ('' for the page's own rows), icon url, entity ids, ultimate 0/1]; the tags' icons and words; top /
    per = how many rows the strip card / a trail card lists. The counters' icons are CSS (`.pip.<tag>`)."""
    from .render import TAG_WORD_ONE, TAG_WORDS
    refs: dict[tuple, int] = {}
    tiles = []
    for pid, hdr, tally, hidden, card, *_ in items[:STRIP_MAX]:
        groups = []
        for ref, counts, hid, samples in card:
            groups.append([refs.setdefault(ref, len(refs)), counts, hid, samples])
        tiles.append([pid, patch_title_text(hdr), bool(patch_name(hdr['title'])), tally, hidden, groups])
    return {'t': tiles, 'g': [list(r) for r in refs], 'words': TAG_WORDS, 'word1': TAG_WORD_ONE, 'eye': EYE_MARK,
            'top': TILE_SAMPLES, 'per': GROUP_SAMPLES + 1}


def patch_strip(items: list[tuple]) -> str:
    """The entity's patches as ONE row of tiles, oldest → newest: the newest on the right, as in the change
    matrices and the trail squares (owner 2026-10-05: "новые справа везде"; data-k still indexes the
    newest-first blob). Stripes in tag colours, the number of changes, the eye when something was not in
    the notes; a tile opens that patch below (#p-<patch>), its hover card says what it changed. The row
    never scrolls: tiles shrink to fit the column, a phone shows the newest ones (styles.css).
    The data blob comes even without a strip (one patch): the ability cards' trail squares read it too."""
    from .common import plural
    from .dynamics_page import stripes
    if not items:
        return ''
    tiles = []
    for k, (pid, hdr, tally, hidden, _) in enumerate(items[:STRIP_MAX] if len(items) > 1 else []):
        text = f'{patch_title_text(hdr)}: {plural(sum(tally.values()), "change")}'
        if hidden:
            text += f', {hidden} not in patch notes'
        # the eye is CSS (a mask on ::after): one inline SVG per tile cost 13 KB on a unit page
        cls = ' hid' if hidden else ''
        tiles.append(f'<a class="ps-tile{cls}" href="#p-{esc(pid)}" data-k="{k}" '
                     f'aria-label="{esc(text)}" style="background:{stripes(tally)}">'
                     f'<span class="dn">{sum(tally.values())}</span></a>')
    tiles.reverse()                                        # oldest left, newest right
    # JSON inside a script element: "</" would end it early
    blob = json.dumps(strip_data(items), ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    strip = f'<div class="patch-strip">{"".join(tiles)}</div>' if tiles else ''
    return f'{strip}<script type="application/json" class="strip-data">{blob}</script>'


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
                     f'{mark("hidden")}Not in patch notes <span class="n">{facts["hidden"]}</span></button>')
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


def _groups(slot: dict, order: dict, meta: dict, names: list[str], hints: dict | None, merge,
            every_href=None) -> list[dict]:
    """The patch's parts in page order: {'keys', 'rows' html, 'changes', 'lines'}; members whose rows are
    the same merge into one group (unit families). `every_href`: system id -> the Game page's band of this patch
    (the link row of a rule for every hero, cards.every_rows)."""
    from .cards import entity_rows, row
    groups: list[dict] = []
    texts = slot.get('texts', {})
    for key in sorted(set(slot['ch']) | set(slot['lines']) | set(texts), key=lambda k: order.get(k, 999)):
        nm, _ = meta[key]
        changes = slot['ch'].get(key, [])
        lines = slot['lines'].get(key, [])
        rows = entity_rows(changes, (hints or {}).get(key), every_href)
        for ln in lines:
            text = _drop_prefix(ln['text'], names + [nm])
            rows += row(ln['status'], text_tag(text, ln.get('topic')), _highlight(text, 'changed'))
        rows += text_rows(texts.get(key, []))
        if not rows:
            continue
        same = next((g for g in groups if merge and g['rows'] == rows), None)
        if same:                             # the same rows on another member: one group, both named
            same['keys'].append(key)
            continue
        groups.append({'keys': [key], 'rows': rows, 'changes': changes, 'lines': lines})
    return groups


def _dev_only(g: dict, in_dev: bool) -> bool:
    """Every counted row of the group is work on a hero still in development (and the page is not that hero's)."""
    from .cards import player_facing
    rows = player_facing(g['changes'])
    return (any(c.get('status') == 'unreleased' for c in rows) and all(c.get('status') == 'unreleased' for c in rows)
            and not g['lines'] and not in_dev)


def every_sig(c: dict) -> tuple:
    """One rule for all, whichever of the entity's abilities carries its copy (shared_rows.spread writes the same
    path, values and noun into every target)."""
    return (c.get('file'), c.get('path'), str(c.get('old_s')), str(c.get('new_s')), c.get('shared_what'))


def split_every(slot: dict, in_dev: bool) -> tuple[dict, list[dict]]:
    """(the band's slot with only the entity's own rows, the rules for every hero / ability it carries — counted as
    the counters count, `player_facing`, released ones unless the page is a hero in development — ONCE each). The
    same rule sat under each of the entity's abilities it touched and the banner counted every copy (Holliday
    2026-01-22: "+9 for all abilities & items" for one rule; review 2026-10-05)."""
    from .cards import player_facing
    from .shared_rows import is_every
    own: dict[str, list[dict]] = {}
    every: dict[tuple, dict] = {}
    for key, ch in slot['ch'].items():
        mine = [c for c in ch if not is_every(c)]
        if mine:
            own[key] = mine
        rules = [c for c in ch if is_every(c)]
        if rules:
            for c in player_facing(rules):
                if in_dev or c.get('status') != 'unreleased':
                    every.setdefault(every_sig(c), c)
    return {**slot, 'ch': own}, list(every.values())


def every_name(rows: list[dict]) -> str:
    """'All heroes' for the rows of a rule for every entity of a kind (shared_rows)."""
    return f'All {rows[0].get("shared_what") or "entities"}' if rows else ''


def every_groups(rows: list[dict]) -> dict[str, list[dict]]:
    """The rows of rules for every entity of a kind, by kind: {'All heroes': rows, 'All melee attacks': rows}."""
    out: dict[str, list[dict]] = {}
    for c in rows:
        out.setdefault(every_name([c]), []).append(c)
    return out


def _banner(pid: str, hdr: dict, counted_all: list[dict], rel: str, every: list[dict] = ()) -> tuple[str, str]:
    """(the band's <summary>, its has-hidden classes). The title is plain text, so a click opens the band in
    place (it used to leave for the patch archive); a small "patch ↗" goes there on purpose. The counters
    and the eye count are what scripts.js recounts while a filter is on. `every`: the rows of rules for every
    hero (shared_rows), counted apart in a chip of their own ("+38 for all heroes")."""
    from .render import not_in_notes, tag_summary
    n_hidden = sum(1 for c in counted_all if not_in_notes(c))
    # a patch the notes said nothing about (every row hidden) carries ONE eye, on its banner: an eye on
    # each row marked 46% of hero rows and 77% of unit rows (advisor, 2026-10-03)
    all_hidden = bool(n_hidden) and n_hidden == len(counted_all)
    # an update that had no patch notes at all (Rat King's build 6736) says so: nothing was left out of notes
    no_notes = all_hidden and all(c.get('status') == 'unannounced' for c in counted_all)
    text = ('no patch notes' if no_notes else f'all {n_hidden} not in notes' if all_hidden
            else f'{n_hidden} not in notes')
    chips = f'<span class="chip eye-chip">{mark("hidden")}<span class="ec-n">{text}</span></span>' if n_hidden else ''
    # one short chip per kind: they wrap under the title on a phone (one long chip ran 145px off a 390px screen)
    chips += ''.join(f'<span class="chip shr-chip">+{len(rows)} for {esc(name.lower())}</span>'
                     for name, rows in every_groups(list(every)).items())
    hidden_cls = ' has-hidden' + (' all-hidden' if all_hidden else '') if n_hidden else ''
    cls = ' named' if patch_name(hdr['title']) else ''
    summary = (f'<summary class="banner{cls}"><span class="bt">{patch_title_html(hdr)}</span>'
               f'<span class="bc">{tag_summary(counted_all)}{chips}'
               f'<a class="pnotes" href="{rel}patches/{esc(pid)}.html">patch ↗</a></span></summary>')
    return summary, hidden_cls


def _patch_block(pid: str, slot: dict, order: dict, meta: dict, names: list[str], rel: str, open_: bool,
                 lazy: bool, areas: dict | None, in_dev: bool, facts: dict, merge=None,
                 headless_own: bool = False, hints: dict | None = None, ults: frozenset[str] = frozenset()) -> str:
    """One patch = its banner + ONE full-width panel: per part its icon on a plate in a column of its own,
    then its name and rows (Sloppy's ability block). `hints`: part key -> its cards.history_hints."""
    from .cards import ability_plate, disambiguate, every_links, is_hidden, player_facing, sub_head
    from .render import not_in_notes, tag_of
    hdr = slot['row']
    from .game_systems import SECTION
    every_href = lambda sid: f'{rel}{SECTION}/{sid}.html#p-{pid}'      # noqa: E731
    own_slot, every_all = split_every(slot, in_dev)
    groups = _groups(own_slot, order, meta, names, hints, merge)
    counted_all, all_dev, card = [], True, []
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
        if len(g['keys']) > 1:
            nm = merge([meta[k][0] for k in g['keys']])
        file, _, eid = key.partition(':')
        rows = player_facing(g['changes'])
        dev = [c for c in rows if c.get('status') == 'unreleased']
        live = [c for c in rows if c.get('status') != 'unreleased']
        group_dev = text_dev if pre[gi] is None else pre[gi]
        all_dev = all_dev and group_dev
        # a rule for every hero (shared_rows.is_every) is not in the groups (split_every): the band's own counters,
        # its eye and the strip tile count what changed on THIS entity
        counted = rows if in_dev else live
        counted_all += counted
        facts['tags'] |= {tag_of(c)[0] for c in rows}
        facts['hidden'] += sum(1 for c in counted if not_in_notes(c))
        facts['dev'] += len(dev)
        area = ' '.join(dict.fromkeys((areas or {}).get(k, 'abil') for k in g['keys']))
        facts['areas'] |= set(area.split())
        # ability chips are abilities and guns (a family's tiers are parts, not chips)
        if len(order) > 1 and key != list(order)[0] and (areas or {}).get(key, 'abil') in ('abil', 'weapon'):
            facts['abs'].add(key)
        hidden = is_hidden(counted)
        # an item's own rows need no header naming the item (its Enhanced version gets one)
        headless = single or (headless_own and key == list(order)[0])
        ult = any(k in ults for k in g['keys'])
        plate = '' if headless else ability_plate(ic, glyph_for(file, eid), ult)
        head = '' if headless else sub_head(nm, ic, glyph_for(file, eid), counted, hidden, icon=False)
        cls = 'hgroup' + (' has-ic' if plate else '') + (' has-hidden' if hidden else '') + (' dev-only' if group_dev else '')
        parts.append(f'<div class="{cls}" data-ab="{esc(eid)}" data-area="{esc(area)}">{plate}'
                     f'<div class="hg-b">{head}{g["rows"]}</div></div>')
        ref = ('' if headless else nm, ic or '', ' '.join(k.partition(':')[2] for k in g['keys']), int(ult))
        card.append((ref, disambiguate(counted, (hints or {}).get(key))))
    # a rule for every hero is ONE block of link rows for the whole band, after its groups: it sat under each of
    # the hero's abilities it touched (Calico 2026-01-22: 15 copies of "All abilities & items: 1 change", ~1000 px)
    if every_all:
        parts.append(f'<div class="hgroup shr-band" data-ab="" data-area=""><div class="hg-b">'
                     f'{every_links(every_all, every_href)}</div></div>')
    if not parts:
        return ''
    every_only = not groups
    # the entity's patch strip above the toolbar: what this patch did, by tag, and its hover card (dev-only
    # bands excluded). A band that holds only a rule for every hero gets no tile, as in the matrices and the trail
    if not (all_dev and not in_dev) and counted_all:
        tally: dict[str, int] = {}
        for c in counted_all:
            tally[tag_of(c)[0]] = tally.get(tag_of(c)[0], 0) + 1
        for name, rows in every_groups(every_all).items():
            card.append(((name, '', '', 0), rows))
        facts.setdefault('strip', []).append((pid, hdr, tally, sum(not_in_notes(c) for c in counted_all),
                                              tile_card(card)))
    if every_only:
        facts['every'] = facts.get('every', 0) + 1
    summary, hidden_cls = _banner(pid, hdr, counted_all, rel, every_all)
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
        abs_ = ' '.join(dict.fromkeys(g['keys'][0].partition(':')[2] for g in groups))
        areas_ = ' '.join(dict.fromkeys(a for g in groups for k in g['keys'] for a in [(areas or {}).get(k, 'abil')]))
        meta_attrs = f' data-tags="{esc(" ".join(sorted(tags)))}" data-abs="{esc(abs_)}" data-areas="{esc(areas_)}"'
    # the anchor change matrices and the home page link to (#p-<patch id>; scripts.js opens it)
    return (f'<details class="pblock{hidden_cls}{dev_cls}" id="p-{esc(pid)}"{meta_attrs}'
            f'{" open" if open_ and not lazy else ""}>{summary}{panel}</details>')
