"""Official patch notes laid out like the rest of the site, not as Valve's wall of text:
lines grouped by the hero / item / ability they are about (icon header, name not
repeated), the mentioned ability's icon on hero lines, a tag per line from the change it
matched, "from A to B" numbers highlighted in the direction's colour."""
from __future__ import annotations

import re
from functools import lru_cache

from .common import entity_icon, esc, glyph_for, hero_icon, load_json, mark, visual
from .render import tag_html, tag_of, tag_summary

LINE_MARKS = ('documented', 'rounded', 'described', 'mismatch', 'fix', 'untracked', 'nodata', 'repeated')
TOPIC_LABEL = {'link': 'forum link', 'sound': 'sound', 'visual': 'visuals', 'interface': 'interface',
               'map': 'map', 'bots': 'bots', 'performance': 'performance'}
_FILE_ORDER = {'heroes.vdata': 0, 'abilities.vdata': 1, 'npc_units.vdata': 2}


@lru_cache(maxsize=1)
def _catalog() -> list[dict]:
    return load_json('entities.json')['entities']


@lru_cache(maxsize=1)
def _by_name() -> dict[str, dict]:
    """lower-case name -> entity: heroes first, then abilities/items, then units; live before removed."""
    out: dict[str, dict] = {}
    for e in sorted(_catalog(), key=lambda e: (_FILE_ORDER.get(e['file'], 9), not e.get('alive'))):
        nm = (e.get('name') or '').strip().lower()
        if nm and nm != e['id'].lower():
            out.setdefault(nm, e)
    return out


@lru_cache(maxsize=1)
def _abilities_of() -> dict[str, list[tuple[str, dict]]]:
    """hero id -> [(lower-case ability name, entity)], longest names first (for text search)."""
    out: dict[str, list] = {}
    for e in _catalog():
        if e['file'] == 'abilities.vdata' and e.get('owner') and e.get('name') and e['name'] != e['id']:
            out.setdefault(e['owner'], []).append((e['name'].lower(), e))
    return {h: sorted(v, key=lambda x: -len(x[0])) for h, v in out.items()}


def _subject_entity(subject: str, patch_ents: dict[str, dict]) -> dict | None:
    key = subject.strip().lower()
    return patch_ents.get(key) or _by_name().get(key)


def _icon_of(e: dict | None, rel: str) -> str:
    if e is None:
        return visual(None, 'units')                     # Walker, Guardian… named by alias
    src = (hero_icon(e['id'], rel) if e['file'] == 'heroes.vdata'
           else entity_icon(e['file'], e['id'], e.get('kind', ''), rel, e.get('name'), e.get('owner')))
    return visual(src, glyph_for(e['file'], e['id'], e.get('kind', '')))


_PREFIX = re.compile(r'^\s*([^:]{1,48}):\s*')
_FROM_TO = re.compile(r'\b(from)\s+(\S+(?:\s*(?:->|→|/|\+)\s*\S+)*)\s+(to)\s+([^\s,;()]+)', re.I)
_BY = re.compile(r'\b(by)\s+(~?[+-]?\d+(?:\.\d+)?\s*%?)', re.I)


def _strip(text: str, subject: str | None) -> str:
    if not subject:
        return text
    m = _PREFIX.match(text)
    if m and m.group(1).strip().lower() == subject.strip().lower():
        rest = text[m.end():]
        return rest[:1].upper() + rest[1:]
    return text


def _highlight(text: str, d: str) -> str:
    """Escaped text with the old value dimmed and the new one in the direction's colour."""
    out = esc(text)
    out = _FROM_TO.sub(lambda m: f'{m.group(1)} <span class="o">{m.group(2)}</span> {m.group(3)} '
                                 f'<span class="n dir-{d}">{m.group(4)}</span>', out, count=1)
    if 'class="n ' not in out:
        out = _BY.sub(lambda m: f'{m.group(1)} <span class="n dir-{d}">{m.group(2)}</span>', out, count=1)
    return out


def _line_tag(changes: list[dict]) -> tuple[str, str]:
    """(tag html, direction class) for the changes a line matched."""
    if not changes:
        return '', 'changed'
    kinds = {tag_of(c)[0] for c in changes}
    first = changes[0]
    d = first.get('dir') if first.get('dir') in ('buff', 'nerf') else 'changed'
    if len(kinds) == 1:
        return tag_html(first), d
    return tag_summary(changes), 'changed'


def _files_cell(ln: dict, changes: list[dict], subject_ent: dict | None) -> str:
    st = ln['status']
    if st == 'repeated':
        return f'also in <a href="{esc(ln["see"]["patch"])}.html">{esc(ln["see"]["title"])}</a>'
    if st == 'untracked':
        return f'<span class="topic">{esc(TOPIC_LABEL.get(ln.get("topic"), ln.get("topic") or ""))}</span>'
    if st in ('mismatch', 'rounded') and ln.get('data'):
        vals = (f'<span class="v">{esc(ln["data"][0])}</span><span class="arrow">→</span>'
                f'<span class="v">{esc(ln["data"][1])}</span>')
        return ('files: ' if st == 'mismatch' else 'exact: ') + vals
    if st == 'documented' and ln.get('late'):
        late = ln['late']
        blds = ', '.join(str(b) for b in late.get('builds', []))
        return f'landed later: build {esc(blds)} · <a href="{esc(late["patch"])}.html">{esc(late["title"])}</a>'
    if st == 'documented' and changes:
        c = changes[0]
        # the entity is the group's header: name it only when the change sits elsewhere
        same = subject_ent is not None and c.get('id') == subject_ent.get('id')
        who = '' if same else f'{esc(c.get("ent_name", ""))} · '
        return (f'{who}{esc(c["label"])}: <span class="v">{esc(c["old_s"])}</span>'
                f'<span class="arrow">→</span><span class="v">{esc(c["new_s"])}</span>')
    if st == 'described' and changes:
        lis = ''.join(f'<li>{esc(c.get("ent_name", ""))} · {esc(c["label"])}: {esc(c["old_s"])} → {esc(c["new_s"])}</li>'
                      for c in changes[:60])
        more = len(ln['changes']) - 60
        return (f'<details><summary>{len(ln["changes"])} exact values</summary><ul>{lis}</ul>'
                f'{"<span class=muted>+" + str(more) + " more</span>" if more > 0 else ""}</details>')
    return ''


def _line_icon(ln: dict, changes: list[dict], hero: dict | None, rel: str) -> str:
    """On a hero's lines: the icon of the ability the line is about."""
    if hero is None:
        return ''
    ab = next((c for c in changes if c.get('file') == 'abilities.vdata' and c.get('id')), None)
    if ab:
        src = entity_icon('abilities.vdata', ab['id'], '', rel, ab.get('ent_name'), hero['id'])
        return visual(src, 'abilities', 'li') if src else ''
    low = ln['text'].lower()
    for name, e in _abilities_of().get(hero['id'], []):
        if name in low:
            src = entity_icon('abilities.vdata', e['id'], e.get('kind', ''), rel, e.get('name'), hero['id'])
            return visual(src, 'abilities', 'li') if src else ''
    return ''


def _groups(lines: list[dict]) -> list[tuple[str | None, list[dict]]]:
    """Consecutive lines about the same subject; a heading line opens its group."""
    out: list[tuple[str | None, list[dict]]] = []
    for ln in lines:
        subj = ln.get('subject')
        if ln['status'] == 'heading' or not out or (subj or None) != out[-1][0]:
            out.append((subj or None, []))
        if ln['status'] != 'heading':
            out[-1][1].append(ln)
    return [(s, ls) for s, ls in out if ls]


def notes_table(p: dict, change_by_key: dict, rel: str) -> str:
    patch_ents = {}
    for e in p['entities']:
        if e.get('name') and e.get('id') != '@shared':
            patch_ents.setdefault(e['name'].strip().lower(), e)
    rows = []
    for s in p['sections']:
        rows.append(f'<tr class="sec"><td colspan="4">{esc(s["title"])}</td></tr>')
        for subject, lines in _groups(s['lines']):
            ent = _subject_entity(subject, patch_ents) if subject else None
            hero = ent if ent and ent['file'] == 'heroes.vdata' else None
            linked = [[change_by_key[k] for k in ln.get('changes', []) if k in change_by_key] for ln in lines]
            if subject:
                counters = tag_summary([c for cs in linked for c in cs[:1]]) if any(linked) else ''
                rows.append(f'<tr class="nh"><td colspan="4"><span class="en">{_icon_of(ent, rel)}'
                            f'{esc(subject)}</span>{counters}</td></tr>')
            for ln, changes in zip(lines, linked):
                st = ln['status']
                tag, d = _line_tag(changes)
                m = mark(st) if st in LINE_MARKS else ''
                text = _highlight(_strip(ln['text'], subject), d)
                rows.append(f'<tr class="nl st-{esc(st)}{" in" if subject else ""}"><td class="st">{m}</td>'
                            f'<td class="tg">{tag}</td><td class="tx">{_line_icon(ln, changes, hero, rel)}{text}</td>'
                            f'<td class="fv">{_files_cell(ln, changes, ent)}</td></tr>')
    return f'<table class="notes">{"".join(rows)}</table>'
