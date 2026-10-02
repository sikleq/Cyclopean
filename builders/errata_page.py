"""Patches / Notes vs files: every patch-note line whose numbers the game files contradict.

A "mismatch" line names a property and one side of its numbers agrees with the files, the other does
not (pipeline/match.py, `mismatch_field`). After the 2026-10-02 review they are Valve's own slips —
a wrong old value, a later retune, two items' numbers swapped (Surge of Power / Spirit Snatch,
2026-05-22) — so they are worth one list."""
from __future__ import annotations

import re

from pipeline.match import parse_pairs

from .common import entity_icon, esc, glyph_for, load_json, page, visual
from .patches_pages import _display_name
from .render import shown_value

_PARENS = re.compile(r'\([^)]*\)')


def _num(x: float) -> str:
    return f'{x:g}'


def rows() -> list[dict]:
    """Newest patch first: {patch, line, valve, files, entity, label, icon args}."""
    out = []
    for row in reversed(load_json('patches/index.json')):
        if not row['line_counts'].get('mismatch'):
            continue
        p = load_json(f'patches/{row["id"]}.json.gz')
        by_key = {c['key']: (e, c) for e in p['entities'] for c in e['changes']}
        for s in p['sections']:
            for ln in s['lines']:
                if ln['status'] != 'mismatch':
                    continue
                key = (ln.get('changes') or [None])[0]
                e, c = by_key.get(key, ({}, {}))
                text = ln['text']
                rest = text.split(':', 1)[1] if ':' in text[:48] else text
                pairs = [(a, b) for a, b in parse_pairs(_PARENS.sub(' ', rest)) if a != b]
                # the files' values as every other list prints them (with the tooltip's unit)
                data = [c.get('old_s'), c.get('new_s')] if c.get('new_s') or c.get('old_s') else ln.get('data') or ['', '']
                unit = _UNIT.search(str(data[1] or data[0] or ''))
                u = unit.group(0) if unit and unit.group(0) in rest else ''
                out.append({'patch': row, 'line': text,
                            'valve': f'{_num(pairs[0][0])}{u} → {_num(pairs[0][1])}{u}' if pairs else '',
                            'files': f'{shown_value(data[0]) or "—"} → {shown_value(data[1]) or "—"}',
                            'entity': e, 'label': c.get('label') or ''})
    return out


_UNIT = re.compile(r'(?<=\d)(%|m/s|m|s)$')


def table(items: list[dict], rel: str) -> str:
    if not items:
        return '<p class="muted">No patch-note line disagrees with the files.</p>'
    trs = []
    for r in items:
        p, e = r['patch'], r['entity']
        ic = entity_icon(e.get('file', ''), e.get('id', ''), e.get('kind', ''), rel, e.get('name'), e.get('owner')) \
            if e else None
        name = _display_name(e) if e else ''
        if e.get('owner_name') and name in ('Weapon', 'Alt weapon'):
            name = f'{e["owner_name"]} · {name}'          # "Celeste · Weapon", not citadel_weapon_unicorn_set
        trs.append(
            f'<tr><td class="d"><a href="{p["id"]}.html">{esc(p["date"])}</a></td>'
            f'<td class="nm">{visual(ic, glyph_for(e.get("file", ""), e.get("id", ""), e.get("kind", "")), "px si2")}'
            f'<span>{esc(name)}</span><span class="lb">{esc(r["label"])}</span></td>'
            f'<td class="ln">{esc(r["line"])}</td>'
            f'<td class="v">{esc(r["valve"])}</td><td class="v f">{esc(r["files"])}</td></tr>')
    return ('<div class="table-scroll"><table class="errata px-frame"><thead><tr><th>Patch</th><th>Field</th>'
            '<th>Valve wrote</th><th>Notes say</th><th>Files say</th></tr></thead>'
            f'<tbody>{"".join(trs)}</tbody></table></div>')


def errata_page(tabs: str) -> str:
    rel = '../'
    items = rows()
    body = f'<h1>Notes vs files</h1>{tabs}{table(items, rel)}'
    return page('Notes vs files', body, rel, 'patches')
