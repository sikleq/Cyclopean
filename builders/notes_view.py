"""Official patch notes laid out like the rest of the site, not as Valve's wall of text:
lines grouped by the hero / item / ability they are about (icon header, name not
repeated), the mentioned ability's icon on hero lines, a tag per line from the change it
matched, "from A to B" numbers highlighted in the direction's colour."""
from __future__ import annotations

import re
from functools import lru_cache

from .common import entity_icon, esc, plural, glyph_for, hero_icon, load_json, mark, visual
from .pixel_icons import tag_svg
from .render import tag_html, tag_of, tag_summary

LINE_MARKS = ('documented', 'rounded', 'described', 'mismatch', 'fix', 'untracked', 'nodata', 'repeated')
TOPIC_LABEL = {'link': 'forum link', 'sound': 'sound', 'visual': 'visuals', 'interface': 'interface',
               'map': 'map', 'bots': 'bots', 'performance': 'performance'}
_FILE_ORDER = {'heroes.vdata': 0, 'abilities.vdata': 1, 'npc_units.vdata': 2}
INLINE_VALUES = 2       # a general line backed by this few values prints them instead of a toggle


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
    # notes write "Doorman:" for The Doorman; a second pass, so an exact name ("Rake") always
    # wins over a shortened one ("The Rake")
    for nm, e in list(out.items()):
        if nm.startswith('the '):
            out.setdefault(nm[4:], e)
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
# "from 6s Unstoppable to 5s": up to three words between the number and "to"
_FROM_WORDS_TO = re.compile(r'\b(from)\s+([+\-~]?\d[^\s,;()]*)((?:\s+[A-Za-z][\w%-]*){1,3})\s+(to)\s+([+\-~]?\d[^\s,;()]*)',
                            re.I)
_BY = re.compile(r'\b(by)\s+(~?[+-]?\d+(?:\.\d+)?\s*%?)', re.I)


def _strip(text: str, subject: str | None) -> str:
    if not subject:
        return text
    m = _PREFIX.match(text)
    if m and m.group(1).strip().lower() == subject.strip().lower():
        rest = text[m.end():]
        return rest[:1].upper() + rest[1:]
    return text


def _strip_name(text: str, name: str) -> str:
    """'Shining Wonder radius increased…' under the Shining Wonder sub-header -> 'Radius increased…'."""
    m = re.match(rf'\s*{re.escape(name)}\s*(?:[:\-–—]\s*|\s+(?=\S))', text, flags=re.I)
    if not m:
        return text
    rest = text[m.end():].strip()
    return rest[:1].upper() + rest[1:] if rest else text


def _highlight(text: str, d: str) -> str:
    """Escaped text with the old value dimmed and the new one in the direction's colour. The
    patterns run on the RAW text and each piece is escaped: run on escaped text they cut "->" (now
    "-&gt;") in half and printed "18m->;54m" on 13 pages (audit 2026-10-01)."""
    g = lambda m, i: esc(m.group(i))     # noqa: E731
    forms = (
        (_FROM_WORDS_TO, lambda m: f'{g(m, 1)} <span class="o">{g(m, 2)}</span>{g(m, 3)} {g(m, 4)} '
                                   f'<span class="n dir-{d}">{g(m, 5)}</span>'),
        (_FROM_TO, lambda m: f'{g(m, 1)} <span class="o">{g(m, 2)}</span> {g(m, 3)} '
                             f'<span class="n dir-{d}">{g(m, 4)}</span>'),
        (_BY, lambda m: f'{g(m, 1)} <span class="n dir-{d}">{g(m, 2)}</span>'),
    )
    for rx, mark_up in forms:
        m = rx.search(text)
        if m:
            return esc(text[:m.start()]) + mark_up(m) + esc(text[m.end():])
    return esc(text)


_TEXT_TAGS = (
    # (pattern on the line, tag class, badge) — only for lines that matched no change
    (re.compile(r'^(fixed|fix(es)?)\b', re.I), 'fix', 'FIX'),
    (re.compile(r'changed from\s+["“].+["”]\s+to\s+["“]|\breworked\b|\brework\b', re.I), 'rework', 'REWORK'),
    (re.compile(r'^no longer\b|\bremoved\b', re.I), 'del', 'DEL'),
    (re.compile(r'^(now|added|new)\b|\bnow (also )?(has|grants|applies|can)\b', re.I), 'new', 'NEW'),
)
TOPIC_TAG = {'sound': 'SOUND', 'visual': 'VISUAL', 'interface': 'UI', 'map': 'MAP', 'bots': 'BOTS',
             'performance': 'PERF', 'link': 'LINK'}


def text_tag(text: str, topic: str | None = None) -> str:
    """A badge for a line the files could not back: its topic, or the wording Valve uses."""
    if topic:
        return f'<span class="tag topic-tag">{esc(TOPIC_TAG.get(topic, topic.upper()))}</span>'
    for rx, cls, word in _TEXT_TAGS:
        if rx.search(text):
            return f'<span class="tag {cls}" data-g="5">{tag_svg(cls)}{word}</span>'
    return ''           # no kind in the wording: the line itself says what changed (CHANGED told nothing)


def _line_tag(changes: list[dict]) -> tuple[str, str]:
    """(tag html, direction class) for the changes a line matched."""
    if not changes:
        return '', 'changed'
    kinds = {tag_of(c)[0] for c in changes}
    first = changes[0]
    d = first.get('dir') if first.get('dir') in ('buff', 'nerf') else 'changed'
    if len(kinds) == 1:
        return tag_html(first), d
    # one line, many kinds of change: a mechanic rework ("now circular rather than in front"),
    # or a value line whose numbers already tell the direction
    return '<span class="tag rework" data-g="6">REWORK</span>', 'changed'


def _files_cell(ln: dict, changes: list[dict], subject_ent: dict | None) -> str:
    st = ln['status']
    if st == 'repeated':
        return f'also in <a href="{esc(ln["see"]["patch"])}.html">{esc(ln["see"]["title"])}</a>'
    if st == 'untracked':
        return ''        # the row's tag already names the topic (MAP, UI…)
    if st in ('mismatch', 'rounded') and ln.get('data'):
        vals = (f'<span class="v">{esc(ln["data"][0])}</span><span class="arrow">→</span>'
                f'<span class="v">{esc(ln["data"][1])}</span>')
        return ('files: ' if st == 'mismatch' else 'exact: ') + vals
    if st == 'documented' and ln.get('late'):
        late = ln['late']
        blds = ', '.join(str(b) for b in late.get('builds', []))
        return f'landed later: build {esc(blds)} · <a href="{esc(late["patch"])}.html">{esc(late["title"])}</a>'
    if st == 'documented':
        return ''        # the line's own numbers are the files' numbers: saying them twice is noise
    short = all(len(str(c.get('old_s') or '')) <= 16 and len(str(c.get('new_s') or '')) <= 16 for c in changes)
    if st == 'described' and 0 < len(changes) <= INLINE_VALUES and short:
        return '<br>'.join(f'<span class="proof">{esc(c["label"])} <span class="v">{esc(c["old_s"])}</span>'
                           f'<span class="arrow">→</span><span class="v">{esc(c["new_s"])}</span></span>'
                           for c in changes)
    if st == 'described' and changes:
        lis = ''.join(f'<li>{esc(c.get("ent_name", ""))} · {esc(c["label"])}: {esc(c["old_s"])} → {esc(c["new_s"])}</li>'
                      for c in changes[:60])
        more = len(ln['changes']) - 60
        return (f'<details><summary>{plural(len(ln["changes"]), "exact value")}</summary><ul>{lis}</ul>'
                f'{"<span class=muted>+" + str(more) + " more</span>" if more > 0 else ""}</details>')
    return ''


def _line_ability(ln: dict, changes: list[dict], hero: dict | None) -> tuple[str, str, str] | None:
    """(ability id, name, owner) a hero's line is about: the ability it matched, else the
    ability named in it; None for hero-wide lines."""
    if hero is None:
        return None
    ab = next((c for c in changes if c.get('file') == 'abilities.vdata' and c.get('id')), None)
    if ab:
        return ab['id'], _by_id_name(ab['id']) or ab.get('ent_name') or ab['id'], hero['id']
    low = ln['text'].lower()
    for name, e in _abilities_of().get(hero['id'], []):
        if name in low:
            return e['id'], e['name'], hero['id']
    return None


@lru_cache(maxsize=1)
def _names() -> dict[str, str]:
    return {e['id']: e['name'] for e in _catalog() if e.get('name') and e['name'] != e['id']}


def _by_id_name(eid: str) -> str | None:
    return _names().get(eid)


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


KIND_SUB = {'hero': 'Hero', 'ability': 'Ability', 'weapon': 'Weapon', 'item': 'Item', 'trooper': 'Trooper',
            'building': 'Building', 'neutral': 'Neutral', 'unit': 'Unit', 'ability_other': 'Ability'}


# A section about the interface, sound or settings is not balance: it gets its own tab, laid out as
# a compact grid of features (City Never Sleeps: ~150 such lines buried the gameplay ones)
_IFACE_SECTION = re.compile(r'interface|\bui\b|hud|settings|sandbox|spectat|accessib|sound|music|\bvo\b|'
                            r'visual|behavior|reporting|social|client', re.I)
IFACE_TOPICS = ('interface', 'sound', 'visual')
_GENERAL_SECTION = re.compile(r'additional|general|misc|other', re.I)
_FEATURE = re.compile(r'^\s*([^:—]{2,60}?)\s*(?::|\s—)\s+(.+)$')


LIST_MIN = 3          # "Label — A, B, C": three or more short names read better as chips
_LIST_ITEM_MAX = 32


def _list_chips(body: str, rel: str) -> str | None:
    """'Nurse Harrow, Deadman Danny, Baba' -> chips, with the game's icon where a name is known."""
    names = [n.strip() for n in body.split(',')]
    if len(names) < LIST_MIN or any(not n or len(n) > _LIST_ITEM_MAX for n in names):
        return None
    chips = []
    for n in names:
        e = _by_name().get(n.lower())
        src = _icon_src(e, rel) if e else None
        pic = f'<img class="px" src="{esc(src)}" alt="" loading="lazy">' if src else ''
        chips.append(f'<span class="nchip{" pic" if pic else ""}">{pic}{esc(n)}</span>')
    return f'<span class="nchips">{"".join(chips)}</span>'


def _feature_html(text: str, d: str, rel: str = '../') -> str:
    """'Tough Crates: Require a Heavy Melee…' -> the feature's name bold, the rest as the line;
    'Haunts — Specimen, Gutter Ghouls, …' -> the name and its list as chips."""
    m = _FEATURE.match(text)
    if not m:
        return _highlight(text, d)
    chips = _list_chips(m.group(2), rel)
    if chips:
        return f'<b class="fname">{esc(m.group(1))}</b>{chips}'
    return f'<b class="fname">{esc(m.group(1))}</b> {_highlight(m.group(2), d)}'


def split_sections(sections: list[dict]) -> tuple[list[dict], list[dict]]:
    """(gameplay sections, interface sections). A whole interface/sound section moves; inside the
    other sections, lines the matcher filed under an interface/sound/visual topic move too."""
    play, iface = [], []
    for s in sections:
        if _IFACE_SECTION.search(s['title']):
            iface.append(s)
            continue
        general = _GENERAL_SECTION.search(s['title'])
        keep = [ln for ln in s['lines']
                if not (general and ln['status'] == 'untracked' and ln.get('topic') in IFACE_TOPICS)]
        moved = [ln for ln in s['lines'] if ln not in keep]
        if keep:
            play.append({**s, 'lines': keep})
        if moved:
            iface.append({**s, 'lines': moved})
    return play, iface


def interface_table(sections: list[dict]) -> str:
    """Interface / sound / settings lines as a feature grid: the feature's name bold, what it does
    below; no tags (they would all say UI), a status mark only when the files back the line."""
    out = []
    for s in sections:
        items = []
        for ln in s['lines']:
            m = _FEATURE.match(ln['text'])
            title, body = (m.group(1), m.group(2)) if m else ('', ln['text'])
            mk = mark(ln['status']) if ln['status'] in ('documented', 'described', 'rounded', 'mismatch', 'fix') else ''
            head = f'<b>{esc(title)}</b>' if title else ''
            items.append(f'<li class="feat st-{esc(ln["status"])}">{mk}<span>{head}{esc(body)}</span></li>')
        out.append(f'<div class="banner sub"><span class="bt">{esc(s["title"])}</span>'
                   f'<span class="bc">{len(items)}</span></div><ul class="feats">{"".join(items)}</ul>')
    return ''.join(out)


def notes_table(p: dict, change_by_key: dict, rel: str) -> str:
    """Each Valve section under a banner; its lines as entity cards (icon, name, history strip)."""
    from .cards import card, row, sub_head
    from .trail import trail_html
    patch_ents = {}
    for e in p['entities']:
        if e.get('name') and e.get('id') != '@shared':
            patch_ents.setdefault(e['name'].strip().lower(), e)
    out = []
    for s in p['sections']:
        groups = _groups(s['lines'])
        n_lines = sum(len(ls) for _, ls in groups)
        out.append(f'<div class="banner"><span class="bt">{esc(s["title"])}</span>'
                   f'<span class="bc">{n_lines} line{"s" if n_lines != 1 else ""}</span></div>')
        cards = []
        for subject, lines in groups:
            ent = _subject_entity(subject, patch_ents) if subject else None
            hero = ent if ent and ent['file'] == 'heroes.vdata' else None
            linked = [[change_by_key[k] for k in ln.get('changes', []) if k in change_by_key] for ln in lines]
            # a hero's lines grouped under the ability they are about (sub-header with its icon);
            # hero-wide lines first, abilities in the order Valve mentions them
            buckets: dict = {None: []}
            for ln, changes in zip(lines, linked):
                buckets.setdefault(_line_ability(ln, changes, hero), []).append((ln, changes))
            rows = []
            for ab, items in buckets.items():
                if not items:
                    continue
                if ab is not None:
                    src = entity_icon('abilities.vdata', ab[0], '', rel, ab[1], ab[2])
                    rows.append(sub_head(ab[1], src, 'abilities', [c for _, cs in items for c in cs[:1]]))
                for ln, changes in items:
                    tag, d = _line_tag(changes)
                    text = _strip(ln['text'], subject)
                    if ab is not None:
                        text = _strip_name(text, ab[1])
                    if not tag:
                        tag = text_tag(text, ln.get('topic'))
                    rows.append(row(ln['status'], tag, _feature_html(text, d, rel) if not subject else _highlight(text, d),
                                    _files_cell(ln, changes, ent)))
            if not subject:
                cards.append(f'<article class="ecard plain"><div class="eb">{"".join(rows)}</div></article>')
                continue
            from .cards import card_head
            src_key = f"{ent['file']}:{ent['id']}" if ent else ''
            head = card_head(subject, _icon_src(ent, rel), _glyph(ent),
                             [c for cs in linked for c in cs[:1]],
                             trail=trail_html(src_key, p['id'], rel) if src_key else '')
            cards.append(card(head, ''.join(rows), search=subject.lower(),
                              anchor=f"n-{ent['id']}" if ent else ''))
        out.append('<div class="ecards">' + ''.join(cards) + '</div>')
    return ''.join(out)


def _icon_src(e: dict | None, rel: str) -> str | None:
    if e is None:
        return None
    return (hero_icon(e['id'], rel) if e['file'] == 'heroes.vdata'
            else entity_icon(e['file'], e['id'], e.get('kind', ''), rel, e.get('name'), e.get('owner')))


def _glyph(e: dict | None) -> str:
    return glyph_for(e['file'], e['id'], e.get('kind', '')) if e else 'units'
