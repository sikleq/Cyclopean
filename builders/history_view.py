"""Entity history (hero, item and unit pages) — the heart of the site (owner, 2026-10-03: "closer to
Sloppy"): patch by patch, newest first, one group per part of the entity (base stats, the gun, each
ability), the rows = what the files changed (tag, field, old → new) with the eye on what the notes left
out, plus the changes the notes name that live in the game's code (status 'code'). Bug fixes, sound /
look lines, engine plumbing ("Technical") and unmatched note lines stay in data/, off the page.

A toolbar filters by tag, by "hidden", by part (Stats / Weapon / Abilities) and by ability (scripts.js
`hist-filter`). Work on a hero still in development hides behind "In development" once the hero is out.
Only the newest EAGER_PATCHES blocks are in the page; older ones are a <template> stamped when opened
or filtered (Nano's page: 12k elements)."""
from __future__ import annotations

import re

from .common import esc, glyph_for, mark, patch_name, patch_title_html, visual
from .notes_view import _highlight, text_tag

OPEN_PATCHES = 3          # the latest patches with rows open; the rest fold to their banner
EAGER_PATCHES = 6         # blocks rendered in the page; older ones wait in a <template>
TEXT_STATUSES = ('code',)  # note lines shown as rows: changes in the game's code (the files did not move)
TAG_FILTERS = ('new', 'rework', 'buff', 'nerf', 'del', 'mech', 'up', 'down')
AREAS = (('stats', 'Stats'), ('weapon', 'Weapon'), ('abil', 'Abilities'))


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
                  in_dev: bool = False) -> str:
    """The History section: heading, toolbar, blocks. keys: [(entity key, display name, icon url)] in
    display order, the page's own entity first; names: subjects whose note lines belong here.
    `line_names`: the other keys' names pull note lines in too (a hero's abilities do; a boss's "Rocket
    Barrage" would drag in the hero ability of that name). `areas`: key -> stats / weapon / abil (a
    hero's page); `gone`: keys of abilities the entity no longer has; `in_dev`: the entity itself is in
    development, so its development work shows by default."""
    order = {k: i for i, (k, _, _) in enumerate(keys)}
    meta = {k: (nm, ic) for k, nm, ic in keys}
    names_by_key = {k: nm for k, nm, _ in keys}
    key_set = set(order)
    own = keys[0][0]
    subjects = [n for n in names if n] + ([nm for k, nm, _ in keys[1:]] if line_names else [])
    per_patch: dict[str, dict] = {}
    for key, _, _ in keys:
        for row, ch in by_ent.get(key, []):
            slot = per_patch.setdefault(row['id'], {'row': row, 'ch': {}, 'lines': {}})
            slot['ch'].setdefault(key, []).extend(ch)
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
    from .cards import player_facing
    blocks, facts = [], {'tags': set(), 'hidden': 0, 'dev': 0, 'areas': set(), 'abs': set()}
    opened = 0
    for i, pid in enumerate(sorted(per_patch, key=lambda k: per_patch[k]['row']['date'], reverse=True)):
        slot = per_patch[pid]
        shown = [c for ch in slot['ch'].values() for c in ch if in_dev or c.get('status') != 'unreleased']
        real = bool(slot['lines']) or bool(player_facing(shown))
        open_ = real and opened < OPEN_PATCHES
        opened += open_
        blocks.append(_patch_block(pid, slot, order, meta, names, rel, open_, i >= EAGER_PATCHES, areas, in_dev, facts))
    bar = toolbar(facts, keys, areas, gone, in_dev, rel)
    cls = 'hblocks' + (' show-dev' if in_dev else '')
    return f'{heading}{bar}<div id="history" class="{cls}">{"".join(blocks)}</div>'


def toolbar(facts: dict, keys: list[tuple], areas: dict | None, gone: set[str], in_dev: bool, rel: str) -> str:
    """Tags present (multi-select), the eye (only hidden), parts of a hero, its abilities as icons (the
    current ones in slot order, removed ones grey after a divider), "In development"."""
    from .pixel_icons import tag_svg
    parts = []
    tags = [t for t in TAG_FILTERS if t in facts['tags']]
    if tags:
        parts.append('<span class="hf-tags">' + ''.join(
            f'<button class="tag {t}" data-f-tag="{t}">{tag_svg(t)}{t.upper()}</button>' for t in tags) + '</span>')
    if facts['hidden']:
        parts.append(f'<button class="px-btn hf-hidden" data-toggle-class="only-hidden" data-target="#history">'
                     f'{mark("hidden")}Only hidden <span class="n">{facts["hidden"]}</span></button>')
    if areas and len(facts['areas']) > 1:
        parts.append('<span class="hf-areas">' + ''.join(
            f'<button class="px-btn" data-f-area="{a}">{lbl}</button>' for a, lbl in AREAS if a in facts['areas'])
            + '</span>')
    chips = [(k, nm, ic) for k, nm, ic in keys[1:] if k in facts['abs']]
    if len(chips) > 1:
        now = [c for c in chips if c[0] not in gone]
        old = [c for c in chips if c[0] in gone]

        def chip(k: str, nm: str, ic: str | None, cls: str = '') -> str:
            file, _, eid = k.partition(':')
            return (f'<button class="hf-ab{cls}" data-f-ab="{esc(eid)}" data-tooltip="{esc(nm)}" aria-label="{esc(nm)}">'
                    f'{visual(ic, glyph_for(file, eid), "px")}</button>')
        parts.append('<span class="hf-abs">' + ''.join(chip(*c) for c in now)
                     + ('<span class="sep"></span>' + ''.join(chip(*c, ' gone') for c in old) if old else '')
                     + '</span>')
    if facts['dev'] and not in_dev:
        parts.append(f'<label class="switch"><input type="checkbox" data-toggle-class="show-dev" data-target="#history">'
                     f'<span class="track"></span>In development <span class="n">{facts["dev"]}</span></label>')
    if not parts:
        return ''
    return '<div class="toolbar hist-bar">' + '<span class="sep"></span>'.join(parts) + '</div>'


def _patch_block(pid: str, slot: dict, order: dict, meta: dict, names: list[str], rel: str, open_: bool,
                 lazy: bool, areas: dict | None, in_dev: bool, facts: dict) -> str:
    """One patch = its banner + ONE full-width panel: a sub-header per part, rows below it."""
    from .cards import entity_rows, is_hidden, player_facing, row, sub_head
    from .render import tag_of, tag_summary
    hdr = slot['row']
    parts, counted_all, all_dev = [], [], True
    single = len(order) == 1                 # a page about one entity repeats no sub-header with its name
    for key in sorted(set(slot['ch']) | set(slot['lines']), key=lambda k: order.get(k, 999)):
        nm, ic = meta[key]
        file, _, eid = key.partition(':')
        changes = slot['ch'].get(key, [])
        lines = slot['lines'].get(key, [])
        facing = player_facing(changes)
        dev = [c for c in facing if c.get('status') == 'unreleased']
        live = [c for c in facing if c.get('status') != 'unreleased']
        rows = entity_rows(changes)
        for ln in lines:
            text = _drop_prefix(ln['text'], names + [nm])
            rows += row(ln['status'], text_tag(text, ln.get('topic')), _highlight(text, 'changed'))
        if not rows:
            continue
        group_dev = bool(dev) and not live and not lines and not in_dev
        all_dev = all_dev and group_dev
        counted = facing if in_dev else live
        counted_all += counted
        facts['tags'] |= {tag_of(c)[0] for c in facing}
        facts['hidden'] += sum(1 for c in counted if c.get('status') == 'hidden')
        facts['dev'] += len(dev)
        area = (areas or {}).get(key, 'abil')
        facts['areas'].add(area)
        if not single and key != list(order)[0]:
            facts['abs'].add(key)
        hidden = is_hidden(counted)
        head = '' if single else sub_head(nm, ic, glyph_for(file, eid), counted, hidden)
        cls = 'hgroup' + (' has-hidden' if hidden else '') + (' dev-only' if group_dev else '')
        parts.append(f'<div class="{cls}" data-ab="{esc(eid)}" data-area="{area}">{head}{rows}</div>')
    if not parts:
        return ''
    n_hidden = sum(1 for c in counted_all if c.get('status') == 'hidden')
    chips = f'<span class="chip eye-chip">{mark("hidden")}{n_hidden} hidden</span>' if n_hidden else ''
    hidden_cls = ' has-hidden' if n_hidden else ''
    dev_cls = ' dev-only' if all_dev and not in_dev else ''
    cls = ' named' if patch_name(hdr['title']) else ''
    summary = (f'<summary class="banner{cls}">'
               f'<span class="bt"><a href="{rel}patches/{esc(pid)}.html">{patch_title_html(hdr)}</a></span>'
               f'<span class="bc">{tag_summary(counted_all)}{chips}</span></summary>')
    panel = f'<div class="hpanel{hidden_cls}">{"".join(parts)}</div>'
    if lazy:
        panel = f'<template class="hp-t">{panel}</template>'
    # the anchor change matrices and the home page link to (#p-<patch id>; scripts.js opens it)
    return (f'<details class="pblock{hidden_cls}{dev_cls}" id="p-{esc(pid)}"{" open" if open_ and not lazy else ""}>'
            f'{summary}{panel}</details>')
