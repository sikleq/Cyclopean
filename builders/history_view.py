"""Entity history (hero, item and unit pages): patch by patch, one block per entity —
the official lines about it first (tag, highlighted numbers, prefix dropped), then what
the files changed that no line spelled out exactly. A line goes to the ability it matched
or names; only what fits no ability stays with the hero itself."""
from __future__ import annotations

import re

from .common import esc, glyph_for, mark
from .notes_view import _highlight, _line_tag

LINE_STATUSES = ('documented', 'rounded', 'described', 'mismatch', 'fix', 'untracked')
# a line that spells the change out exactly makes the change row redundant
EXACT = ('documented', 'rounded')


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


def history_table(keys: list[tuple[str, str, str | None]], names: list[str], by_ent, by_subject, rel: str) -> str:
    """keys: [(entity key, display name, icon url)] in display order, the page's own entity
    first; names: subjects whose note lines belong here (the hero / item / unit name)."""
    order = {k: i for i, (k, _, _) in enumerate(keys)}
    meta = {k: (nm, ic) for k, nm, ic in keys}
    names_by_key = {k: nm for k, nm, _ in keys}
    key_set = set(order)
    own = keys[0][0]
    subjects = [n for n in names if n] + [nm for k, nm, _ in keys[1:]]
    per_patch: dict[str, dict] = {}
    for key, _, _ in keys:
        for row, ch in by_ent.get(key, []):
            slot = per_patch.setdefault(row['id'], {'row': row, 'ch': {}, 'lines': {}})
            slot['ch'].setdefault(key, []).extend(ch)
    seen: set[tuple[str, str]] = set()
    for n in subjects:
        for row, ln in by_subject.get(n.lower(), []):
            if (row['id'], ln['text']) in seen:
                continue
            seen.add((row['id'], ln['text']))
            slot = per_patch.setdefault(row['id'], {'row': row, 'ch': {}, 'lines': {}})
            slot['lines'].setdefault(_entity_of_line(ln, key_set, names_by_key, own), []).append(ln)
    if not per_patch:
        return '<p class="muted">No recorded changes.</p>'
    from .cards import player_facing
    blocks = []
    opened = 0
    for pid in sorted(per_patch, key=lambda k: per_patch[k]['row']['date'], reverse=True):
        slot = per_patch[pid]
        # a patch that only moved engine plumbing does not take one of the open places
        real = bool(slot['lines']) or bool(player_facing([c for ch in slot['ch'].values() for c in ch]))
        open_ = real and opened < OPEN_PATCHES
        opened += open_
        blocks.append(_patch_block(pid, slot, order, meta, names, rel, open_=open_))
    return '<div class="hblocks">' + ''.join(blocks) + '</div>'


OPEN_PATCHES = 3        # the latest patches with player-facing rows open; the rest fold to their banner


def _patch_block(pid: str, slot: dict, order: dict, meta: dict, names: list[str], rel: str, open_: bool) -> str:
    """One patch = its banner + ONE full-width panel: an ability sub-header per entity, rows
    below it (design review: a 2-column grid of one-row cards left holes and read in zigzag)."""
    from .cards import change_rows, is_hidden, player_facing, row, sub_head
    from .notes_view import text_tag
    from .render import tag_summary
    hdr = slot['row']
    all_ch = [c for ch in slot['ch'].values() for c in ch]
    n_hidden = sum(1 for c in all_ch if c.get('status') == 'hidden')
    n_dev = sum(1 for c in all_ch if c.get('status') == 'unreleased')
    chips = f'<span class="chip eye-chip">{mark("hidden")}{n_hidden} hidden</span>' if n_hidden else ''
    if n_dev:
        chips += f'<span class="chip dev">{mark("unreleased")}{n_dev} in development</span>'
    parts = []
    counted_all = []
    # a page about one entity (an item, a unit) needs no sub-header repeating its own name
    single = len(order) == 1
    for key in sorted(set(slot['ch']) | set(slot['lines']), key=lambda k: order.get(k, 999)):
        nm, ic = meta[key]
        lines = slot['lines'].get(key, [])
        changes = slot['ch'].get(key, [])
        by_key = {c['key']: c for c in changes if c.get('key')}
        exact = {ck for ln in lines if ln['status'] in EXACT for ck in ln.get('changes', [])}
        rest = [c for c in changes if c.get('key') not in exact]
        file, _, eid = key.partition(':')
        rows = []
        for ln in lines:
            linked = [by_key[k] for k in ln.get('changes', []) if k in by_key]
            tag, d = _line_tag(linked)
            text = _drop_prefix(ln['text'], names + [nm])
            if not tag:
                tag = text_tag(text, ln.get('topic'))
            rows.append(row(ln['status'], tag, _highlight(text, d)))
        counted = [c for ln in lines for c in [by_key.get(k) for k in ln.get('changes', [])][:1] if c] + rest
        counted_all += counted
        hidden = is_hidden(rest)
        head = '' if single else sub_head(nm, ic, glyph_for(file, eid), counted, hidden)
        parts.append(f'<div class="hgroup{" has-hidden" if hidden else ""}">{head}{"".join(rows)}{change_rows(rest)}</div>')
    hidden_cls = ' has-hidden' if is_hidden(all_ch) else ''
    summary = (f'<summary class="banner{" hidden-only" if n_hidden and n_hidden == len(all_ch) else ""}">'
               f'<span class="bt"><a href="{rel}patches/{esc(pid)}.html">{esc(hdr["title"])}</a></span>'
               f'<span class="bd">{esc(hdr["date"])}</span>'
               f'<span class="bc">{tag_summary(player_facing(counted_all))}{chips}</span></summary>')
    return (f'<details class="pblock{hidden_cls}"{" open" if open_ else ""}>{summary}'
            f'<div class="hpanel{hidden_cls}">{"".join(parts)}</div></details>')
