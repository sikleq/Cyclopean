"""Passes over a matched window and the extras of its record: the key changes and their sentences, the texts and
console variables a record keeps (`slim_extras`), lines that landed in a later build (`late_landings`), lines
repeated by an edited post (`repeated_lines`) and lines about the game's code (`code_lines`)."""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Callable

from . import cache, loc, tracker
from . import match_rules as rules
from .classify import GAMEPLAY_CATS
from .patches import Patch
from .match_values import _TIER_NAME, _tokens, expand_words, num, parse_pairs, value_matches, words


SHARED_NAMES = {'heroes.vdata': 'All heroes', 'abilities.vdata': 'Many abilities & items',
                'npc_units.vdata': 'Many units', 'misc.vdata': 'Many map objects', 'modifiers.vdata': 'Many modifiers'}


KEY_KINDS = {'hero', 'ability', 'weapon', 'item', 'building', 'trooper', 'neutral', 'shared'}


KEY_LIMIT = 24


def sentence(name: str, c: dict) -> str:
    """Valve-style line for a change: 'Abrams: Health increased from 780 to 800'."""
    label = c.get('label') or ''
    if c.get('path') == '@add':
        return f'{name}: added to the game'
    if c.get('path') == '@return':
        return f'{name}: back in the game files'
    if c.get('path') == '@remove':
        return f'{name}: removed from the game'
    # a sound, look or interface field keeps no value (diff.VALUELESS_CATS): "removed", not "removed (was —)"
    if c['op'] == 'add':
        new = c.get('new_s')
        return f'{name}: {label} added ({new})' if new not in (None, '', '—') else f'{name}: {label} added'
    if c['op'] == 'remove':
        old = c.get('old_s')
        return f'{name}: {label} removed (was {old})' if old not in (None, '', '—') else f'{name}: {label} removed'
    try:
        up = float(str(c.get('new_s')).rstrip('m%s')) > float(str(c.get('old_s')).rstrip('m%s'))
        verb = 'increased' if up else 'reduced'
    except ValueError:
        verb = 'changed'
    return f'{name}: {label} {verb} from {c.get("old_s", "")} to {c.get("new_s", "")}'


KEY_MAX_PCT = 300          # bigger jumps are format changes (0.99 -> 99), not balance


_TEST_ENTITY = re.compile(r'test|dummy|debug|_base$', re.I)


def key_changes(ents: list[dict]) -> list[dict]:
    """The biggest balance moves of the window (by |percent|) for a summary."""
    rows = []
    for e in ents:
        if e.get('kind') not in KEY_KINDS or e.get('id') == '@shared' or _TEST_ENTITY.search(e.get('id', '')) \
                or _TEST_ENTITY.search(e.get('name') or ''):
            continue
        for c in e['changes']:
            if c.get('cat') == 'balance' and isinstance(c.get('pct'), (int, float)) \
                    and 5 <= abs(c['pct']) <= KEY_MAX_PCT and c.get('dir') in ('buff', 'nerf') \
                    and c.get('status') not in ('unreleased',):
                rows.append({'entity': e['key'], 'name': e['name'], 'kind': e.get('kind'), 'owner': e.get('owner'),
                             'change': c})
    rows.sort(key=lambda r: -abs(r['change']['pct']))
    return rows[:KEY_LIMIT]


LOC_GROUPS = ('citadel_heroes', 'citadel_mods', 'citadel_attributes', 'citadel_main', 'citadel_seasonal',
              'citadel_gc_mod_names', 'citadel_gc_hero_names')


LOC_LIMIT = 400


# console variables are kept whole (coverage audit 2026-10-05: the list stopped at 300 of City Never Sleeps' 510
# without a word, and the Game section reads respawn times and soul rewards from them); the noted ones first
_CONVAR_ORDER = {'documented': 0, 'described': 0, 'rounded': 0, 'mismatch': 0}


_CONVAR_OP = {'change': 0, 'desc': 1, 'remove': 2, 'add': 3}


@lru_cache(maxsize=2)
def _abilities_blob(blob: str) -> dict:
    return cache.vdata_blob(blob)           # neighbouring windows share a state: one parse each


def text_state(commit: str | None, keys: set[str]) -> dict | None:
    """entity key -> {part: {token: value}} of the abilities and items in `keys` at `commit`
    (pipeline.abilities.text_values); None when the build is not known."""
    from .abilities import text_values
    if not commit:
        return None
    blob = tracker.blob_id(commit, tracker.SCRIPTS + 'abilities.vdata')
    if not blob:
        return None
    abilities, tok = _abilities_blob(blob), loc.tokens(commit)
    out = {}
    for k in keys:
        file, _, eid = k.partition(':')
        a = abilities.get(eid) if file == 'abilities.vdata' else None
        if isinstance(a, dict):
            out[k] = text_values(a, tok)
    return out


States = tuple[str | None, str | None]


def texts_with_values(texts: list[dict], states: States | Callable[[], States] | None,
                      own: Callable[[], Callable[[dict], States | None] | None] | None = None) -> list[dict]:
    """The window's text changes with the values the game filled into their old and new sides
    (`entity_texts.with_values`), read from the builds before and after the window. `states`: (before, after)
    commits, or what gives them (`window_states`, asked only when a text holds a value). `own`: gives the rows
    that read their own builds instead (`match_window.gap_text_states`: a window a release interrupts)."""
    from .entity_texts import needed, with_values
    keys = needed(texts)
    if not keys or not states:
        return texts
    per_row = own() if own else None
    groups: dict[States, list[int]] = {}
    window: States | None = None
    for i, row in enumerate(texts):
        st = per_row(row) if per_row else None
        if st is None:
            if window is None:
                window = states() if callable(states) else states
            st = window
        groups.setdefault(st, []).append(i)
    out = list(texts)
    for (before, after), idx in groups.items():
        rows = [texts[i] for i in idx]
        ks = needed(rows)
        filled = with_values(rows, text_state(before, ks), text_state(after, ks)) if ks else rows
        for i, row in zip(idx, filled):
            out[i] = row
    return out


def slim_extras(extras: dict, cat: dict[str, dict] | None = None,
                states: States | Callable[[], States] | None = None, own=None) -> dict:
    """Patch pages show a capped list of text changes, every console variable and asset totals; the full
    per-build detail stays on the build pages. `texts`: the name / description changes of the abilities, items
    and heroes a page shows, uncapped (`pipeline/entity_texts.py`), with the values the game filled in at
    `states` (`window_states`)."""
    from .entity_texts import entity_texts
    loc_rows = [x for x in extras['loc'] if x.get('group') in LOC_GROUPS]
    totals: dict[str, dict[str, int]] = {}
    hero_models: set[str] = set()
    for a in extras['assets']:
        for cat_, n in a.get('counts', {}).items():
            t = totals.setdefault(cat_, {'added': 0, 'removed': 0, 'modified': 0})
            for k in t:
                t[k] += n.get(k, 0)
        hero_models |= set(a.get('hero_models', {}))
    # a hero's model rebuilt (its file several times bigger or smaller): a row of the hero's history (model_rows)
    models = [{'ent': f"heroes.vdata:{m['hero']}", 'path': m['path'], 'old': m['old'], 'new': m['new'],
               'build': a['build']}
              for a in extras['assets'] for m in a.get('model_sizes') or () if m.get('hero')]
    return {
        'loc': loc_rows[:LOC_LIMIT], 'loc_total': len(loc_rows),
        'texts': texts_with_values(entity_texts(extras['loc'], cat or {}), states, own),
        'convars': sorted(extras['convars'], key=lambda x: (_CONVAR_ORDER.get(x.get('status'), 1),
                                                            _CONVAR_OP.get(x.get('op'), 4), x.get('build') or 0)),
        'convars_total': len(extras['convars']),
        'assets': {'counts': dict(sorted(totals.items())), 'hero_models': sorted(hero_models)},
        'models': models,
    }


# Notes sometimes precede the files: "Diviner's Kevlar: Cooldown Reduction reduced from 12% to 10%"
# is in the 2024-12-06 notes, the value changed in a build of 2024-12-14 (the next window).
LATE_DAYS = 14


def _days(a: str, b: str) -> int:
    from datetime import date
    return (date.fromisoformat(b[:10]) - date.fromisoformat(a[:10])).days


def _late_hit(later: list[tuple[Patch, dict]], p: Patch, subj: str, pairs, lw: set[str],
              hero_name: dict[str, str]) -> tuple | None:
    for q, qd in later:
        if _days(p.date, q.date) > LATE_DAYS:
            break
        for e in qd['entities']:
            names = {(e.get('name') or '').lower(), (hero_name.get(e.get('owner') or '') or '').lower()}
            if subj not in names:
                continue
            for c in e['changes']:
                # 'unannounced': the later build may be a notes-less window of its own (build-5433)
                if c.get('status') not in ('hidden', 'unannounced') or c.get('shared') or c.get('cat') != 'balance':
                    continue
                # "damage" counts here ("Holliday: Base damage reduced from 22 to 18" is the gun's Bullet
                # Damage two days later): the subject and the exact numbers already narrow it down
                if not (rules.expand_label_words(words(c['label'])) | _tokens(c['label'])) & lw:
                    continue
                o, n = num(c.get('old_s')), num(c.get('new_s'))
                if o is not None and n is not None and \
                        any(value_matches(o, a, False) and value_matches(n, b, False) for a, b in pairs):
                    return q, qd, c
    return None


def late_landings(results: list[tuple[Patch, dict]], cat: dict[str, dict]) -> int:
    """Link a numbered line left unmatched in its own window to a still-hidden change
    of the same subject within LATE_DAYS that has exactly its numbers and shares a
    label word. The line becomes documented (with where it landed), the change too."""
    hero_name = {e['id']: e.get('name') or '' for e in cat.values() if e['file'] == 'heroes.vdata'}
    linked = 0
    for i, (p, data) in enumerate(results):
        for s in data['sections']:
            for ln in s['lines']:
                if ln['status'] != 'unmatched' or not ln.get('subject'):
                    continue
                rest = ln['text'].split(':', 1)[1] if ':' in ln['text'][:48] else ln['text']
                pairs = parse_pairs(rest)
                if not pairs:
                    continue
                subj = ln['subject'].lower()
                lw = expand_words(words(rest)) | _tokens(rest)
                hit = _late_hit(results[i + 1:], p, subj, pairs, lw, hero_name)
                steps = [(p, data, None), hit] if hit else _chain_hit(data, results[i + 1:], p, subj, pairs, hero_name)
                if not steps:
                    continue
                q = steps[-1][0]
                ln['status'] = 'documented'
                ln['changes'] = list(dict.fromkeys(st[2]['key'] for st in steps if st[2]))
                ln['late'] = {'patch': q.id, 'title': q.title, 'builds': steps[-1][2].get('builds', [])}
                for _, qd, c in steps:
                    if c is None:
                        continue
                    qd['counts'][c['status']] -= 1
                    qd['counts']['documented'] = qd['counts'].get('documented', 0) + 1
                    c['status'] = 'documented'
                    if qd is not data:
                        c['noted_in'] = {'patch': p.id, 'title': p.title}
                data['line_counts']['unmatched'] -= 1
                data['line_counts']['documented'] = data['line_counts'].get('documented', 0) + 1
                linked += 1
    return linked


def _subject_of(e: dict, subj: str, hero_name: dict[str, str]) -> bool:
    return subj in {(e.get('name') or '').lower(), (hero_name.get(e.get('owner') or '') or '').lower()}


def _chain_hit(data: dict, later: list[tuple[Patch, dict]], p: Patch, subj: str, pairs,
               hero_name: dict[str, str]) -> list | None:
    """The line's change shipped in two steps across a window edge: Valve hotfixed it an hour later
    ("Lucky Shot: Damage reduced from 125% to 110%" = 125 -> 120 in build 5983, 120 -> 110 in 5984 of
    the follow-up window, 2025-11-21). The field starts at A in the line's window and the same field
    ends at B later (within LATE_DAYS), step by step: [(p, data, c0), (q, qd, c1)]."""
    for e in data['entities']:
        if not _subject_of(e, subj, hero_name):
            continue
        for c0 in e['changes']:
            if c0.get('status') not in ('hidden', 'unannounced') or c0.get('cat') != 'balance' or c0.get('shared'):
                continue
            o0, n0 = num(c0.get('old_s')), num(c0.get('new_s'))
            if o0 is None or n0 is None:
                continue
            for a, b in pairs:
                if not value_matches(o0, a, False) or value_matches(n0, b, False):
                    continue
                for q, qd in later:
                    if _days(p.date, q.date) > LATE_DAYS:
                        break
                    for e1 in qd['entities']:
                        for c1 in e1['changes']:
                            if c1.get('key') != c0.get('key') or c1.get('status') not in ('hidden', 'unannounced'):
                                continue
                            o1, n1 = num(c1.get('old_s')), num(c1.get('new_s'))
                            if o1 is not None and n1 is not None and abs(o1 - n0) < 1e-9 and value_matches(n1, b, False):
                                return [(p, data, c0), (q, qd, c1)]
    return None


def repeated_lines(results: list[tuple[Patch, dict]]) -> int:
    """Steam posts get edited: the 2026-03-06 post later carried the 03-21 lines too.
    An unmatched line whose exact text is matched in a LATER patch's notes belongs
    there: status 'repeated' with a pointer, not a matcher gap."""
    later_home: dict[str, tuple[str, str]] = {}
    moved = 0
    for p, data in reversed(results):
        for s in data['sections']:
            for ln in s['lines']:
                key = ln['text'].strip().lower()
                if ln['status'] == 'unmatched' and key in later_home:
                    pid, title = later_home[key]
                    ln['status'] = 'repeated'
                    ln['see'] = {'patch': pid, 'title': title}
                    data['line_counts']['unmatched'] -= 1
                    data['line_counts']['repeated'] = data['line_counts'].get('repeated', 0) + 1
                    moved += 1
        for s in data['sections']:
            for ln in s['lines']:
                if ln['status'] not in ('unmatched', 'repeated', 'heading', 'untracked', 'nodata'):
                    later_home[ln['text'].strip().lower()] = (p.id, p.title)
    return moved


# stricter than _PRESENTATION_LINE: "slow effect now persists" is the game's code, not a visual
_LOOK_LINE = re.compile(r'\b(sounds?|audio|sfx|vfx|visuals?|particles?|animations?|anims?|models?|icons?|'
                        r'ui|hud|tooltips?|music|voice|looks?|looking)\b', re.I)


_SOUND_WORD = re.compile(r'\b(sounds?|audio|sfx|music|voice)\b', re.I)


_DIGIT = re.compile(r'\d')


def code_lines(results: list[tuple[Patch, dict]]) -> int:
    """A line about a hero, an ability or an item whose game files did not move in its window, nor in a
    later one within LATE_DAYS, is a change in the game's code ("Vyper: Sliding uphill now allows for
    lateral movement"): status 'code', not a matcher miss ('unmatched'). The `_quiet` marks go away."""
    n = 0
    for i, (p, data) in enumerate(results):
        for s in data['sections']:
            for ln in s['lines']:
                about = ln.pop('_quiet', None)
                if not about or ln['status'] != 'unmatched':
                    continue
                if _LOOK_LINE.search(ln['text']):
                    # "Added cast and buff sounds", "Revision to buff and cast to look less modern"
                    ln['status'] = 'untracked'
                    ln['topic'] = 'sound' if _SOUND_WORD.search(ln['text']) else 'visual'
                    data['line_counts']['unmatched'] -= 1
                    data['line_counts']['untracked'] = data['line_counts'].get('untracked', 0) + 1
                    continue
                if _DIGIT.search(_TIER_NAME.sub('', ln['text'])):
                    continue        # a line with numbers left unmatched is more likely a miss of ours
                ids = set(about)
                later = False
                for q, qd in results[i + 1:]:
                    if _days(p.date, q.date) > LATE_DAYS:
                        break
                    if any(f"{e['file']}:{e['id']}" in ids and any(c.get('cat') in GAMEPLAY_CATS for c in e['changes'])
                           for e in qd.get('entities', [])):
                        later = True
                        break
                if later:
                    continue
                ln['status'] = 'code'
                data['line_counts']['unmatched'] -= 1
                data['line_counts']['code'] = data['line_counts'].get('code', 0) + 1
                n += 1
    return n
