"""Annotate official patch notes with the data changes they describe.

For every patch window we merge all field changes of its builds, then match
each note line to changes:

  documented — the line's numbers equal the data (old -> new)
  mismatch   — the line names a property but the data says other numbers
  described  — the line talks about the entity / a global keyword without
               exact numbers ("All slows reduced by ~20%", "Now builds from X")
  hidden     — (per change) nothing in the notes covers it
  heading    — (line) a bare entity name heading the lines below it
  untracked  — (line) sound / effects / UI / map / bots / links: not in the diffed data
  nodata     — (line) the patch predates every tracker, nothing to compare with
  repeated   — (line) an edited post repeats a line that a later patch's notes carry and match
  unmatched  — (line) should be in the data, but no change was found: a matcher gap

    python -m pipeline.match   ->  data/patches/<id>.json.gz + data/patches/index.json
"""
from __future__ import annotations

import json
import re

from . import cache, catalog, jsonio, loc, semantics, tracker
from . import flags as flag_rules
from . import match_rules as rules
from . import patches as patches_mod
from .diff import SHARED_MIN
from .classify import GAMEPLAY_CATS
from .patches import Patch, group
from .shared_groups import SharedGroups, window_of

# split 2026-11-13 into match_values (numbers, words, MChange), match_window (a window's changes) and match_passes
# (passes after the lines are read, the record's extras): every name is re-exported here for its callers
from .match_values import (ALIGNED_MAX, APPROX, EXACT, GENERIC_WORDS, HERO_STAT_WORDS, MChange, SYNONYMS, SYNONYM_ONLY,  # noqa: F401
                           WEAPON_WORDS, _ARROW_RE, _ATTACK_KIND, _BY_RE, _CHANGED_FROM, _COMPOUND, _COMPOUNDS,
                           _FIX_RE, _FOR_BOTH, _FROM_TO, _GRANT, _HALF_DAMAGE, _HP, _INSTEAD_RE, _ITEM_TIER_MOVE,
                           _LENGTHY, _METRES_ON_LINE, _MOVED_TO_TIER, _NOW_BY, _NUM, _PAIR_RE, _PARENS, _PART_STOP,
                           _PART_WORD, _PCT_LESS, _RATE_LIKE, _STOP, _SWAP_LINE, _SYNONYMS, _THOUSANDS, _TIER_NAME,
                           _TIER_RE, _TIER_TO, _TIME_WORDS, _WORD_RE, _aligned_pairs, _label_tokens, _number_list,
                           _numeric, _same_way, _shown_pair, _skeleton, _stems, _tokens, close, data_values,
                           exact_pair, expand_words, granted_pair, half_match, list_match, num, parse_pairs,
                           shown_in_meters, topic_words, two_sided, value_matches, words)
from .match_window import (BUILDS, LISTED_STATES, LIST_FILES, LIST_IDS, RELEASED_STATES, _BASE_LINK, _DEV_STATE,  # noqa: F401
                           _IN_DEV, _LIST_INDEX, _PROVIDED_TYPE, _SELECTABLE, _TRUTHY, _gameplay_entity, _state,
                           _window_change, event_name, gap_text_states, keyed_list, load_record, mark_availability_moves, mark_dud_guns,
                           mark_inherited_defaults, mark_retyped, merge_ops, nameless_part, rekey_lists,
                           window_changes, window_states)
from .match_passes import (KEY_KINDS, KEY_LIMIT, KEY_MAX_PCT, LATE_DAYS, LOC_GROUPS, LOC_LIMIT, SHARED_NAMES, States,  # noqa: F401
                           _CONVAR_OP, _CONVAR_ORDER, _DIGIT, _LOOK_LINE, _SOUND_WORD, _TEST_ENTITY, _abilities_blob,
                           _chain_hit, _days, _late_hit, _subject_of, code_lines, key_changes, late_landings,
                           repeated_lines, sentence, slim_extras, text_state, texts_with_values)
# second split 2026-11-13: match_score (who a line names, the score of a change for it) and match_lines (reading one
# line); the record's output, events, blankets, release and late-window passes stay here
from .match_score import (_BASE_DAMAGE, _close_hero, _core, _DOWN_VERB, ent_key, _GROWTH_WORDS, inline_alias,  # noqa: F401
                          INLINE_NAME_MAX_KEYS, INLINE_NAME_MIN, inline_names, _LABEL_FILLER, label_words, list_hits,
                          list_parts, _LIST_SPLIT, _LOOSE_PCT, _MINUTES, mismatch_field, name_index, _names_moved,
                          names_other_stat, names_whole_property, pair_hits, pct_close, resolve_subject,
                          _rounded_to_five, _same_kind, score, _SECONDS, _SPAWN_TIMER, STAT_NOUNS, Subject,
                          system_alias, system_lines_pools, system_pools, _TIME_LIKE, twin_hits, _UP_VERB, verb_sign)
from .match_lines import (annotate, annotate_line, _fix_or, _FLAG_FILLER, _FLAG_PREFIX, _FLAG_WORD_FIELDS, flag_words,  # noqa: F401
                          heading, _HEADING_MAX, _Line, _line_aim, _line_numbers, _line_subject, _line_words, _link,
                          _NO_LONGER, _old_from_notes, _OLD_TIER, post_pass, _PRESENTATION_LINE, _read_line,
                          _REMOVED_LINE, _STATE_MASK, _STREET_BRAWL, _SUBHEAD)

OUT = tracker.ROOT / 'data' / 'patches'


# ---- output -----------------------------------------------------------------

def change_json(c: MChange) -> dict:
    kind = c.kind or ''
    # one side in metres, the other bare (engine units): both in metres, for the numbers and the % alike
    old, new = semantics.units_when_bare(c.path, *semantics.metres_pair(c.old, c.new))
    dirn, pct = semantics.direction(c.path, num(old), num(new), kind, c.drawback, c.neg_base)
    flag = flag_rules.is_flag_field(c.path)
    if flag and kind not in semantics.SHARED_KINDS:
        dirn = flag_rules.direction(c.path, c.old, c.new) or dirn     # "Can target: + neutrals" is a buff
    shown = semantics.M_SPEED if c.speed_m and not c.meters else c.meters
    if not c.meters and semantics.length_in_units(c.path, c.unit, (c.old, c.new)):
        shown = True                  # a property length no build gave a unit: engine units, shown in metres
    unit = c.unit
    if not c.meters and c.old_unit is None and semantics.bare_engine_length(c.unit, (c.old, c.new)):
        # the tooltip's "m" over bare engine units: converted, not "500m" (semantics.bare_engine_length)
        shown, unit = (semantics.SPEED if c.unit == 'm/s' else True), ''
    magnitude = c.sign == '-'
    switched = c.old_unit is not None
    if switched:
        dirn, pct = 'changed', None   # another unit: the numbers do not compare (labels.unit_switch)
    return {
        'key': c.key, 'file': c.file, 'id': c.eid, 'path': c.path, 'op': c.op, 'cat': c.cat,
        'label': c.shown or c.label,
        'old_s': semantics.show(old, shown, c.old_unit if switched else unit, c.invert, magnitude),
        'new_s': semantics.show(new, shown, unit, c.invert, magnitude),
        'dir': dirn, 'pct': None if pct is None else round(pct, 1), 'grad': semantics.gradient(pct),
        'status': c.status, 'builds': sorted(set(c.builds)), 'shared': c.shared,
        'same': (semantics.reencoded(c.old, c.new, c.path) or (c.retyped and semantics.sign_flip(c.old, c.new))
                 or c.moved),
        **({'flag': True} if flag else {}),
        **({'unit_switch': True} if switched else {}),
    }


# 'shared': every hero's ability (jump, dash…), ownerless since 2026-10-04 — still an event of its own
ENTITY_EVENT_KINDS = {'hero', 'item', 'ability', 'weapon', 'trooper', 'building', 'neutral', 'unit', 'shared'}
# kinds that count only with proof they matter (audit B12, 2026-10-02: 102 removed abilities such
# as Splatapult, 85 new pickups such as the permanent ammo powerup and game-rule blocks such as
# m_RejuvParams were on no patch page): an ability with a name or an NPC that binds it; a rules
# entry with gameplay fields (removed: a gameplay-like id). Not a hero's melee: its name is the shared
# "Melee" string, and the hero and its gun already make the event
EVENT_IF_NAMED = {'ability_other'}


def event_worthy(x: dict) -> bool:
    kind = x.get('kind')
    if kind in ENTITY_EVENT_KINDS:
        return True
    if kind in EVENT_IF_NAMED:
        return bool(x.get('units')) or bool(x.get('name')) and x['name'] != x['id']
    return kind == 'global' and bool(x.get('gameplay'))


def entity_events(extras: dict, notes_text: str, tok: dict[str, str]) -> list[dict]:
    """One change per entity added to / removed from the files in this window."""
    out = []
    for bucket, op, path, label in (('entities_added', 'add', '@add', 'Added to the game files'),
                                    ('entities_returned', 'add', '@return', 'Back in the game files'),
                                    ('entities_removed', 'remove', '@remove', 'Removed from the game files')):
        for x in extras.get(bucket, []):
            if not event_worthy(x) or x['id'] == '@shared':
                continue
            name = x.get('name') or x['id']
            status = 'described' if name and name != x['id'] and name.lower() in notes_text else 'hidden'
            out.append({**x, 'name': name, 'change': {
                'key': f"{x['file']}:{x['id']}:{path}", 'file': x['file'], 'id': x['id'], 'path': path,
                'op': op, 'cat': 'mechanic', 'label': label, 'old': None, 'new': None, 'old_s': '', 'new_s': '',
                'dir': 'changed', 'pct': None, 'grad': 5, 'status': status, 'builds': [x['build']], 'shared': False}})
    return out


_OPEN_LINE = ('unmatched', 'untracked')


def _claim_line(ln: dict, key: str) -> None:
    """A line that announces a change: it links the change, and a line nothing had claimed is 'described'."""
    if key not in ln.setdefault('changes', []):
        ln['changes'].append(key)
    if ln.get('status') in _OPEN_LINE:
        ln['status'] = 'described'
        ln.pop('topic', None)


def name_events(sections: list[dict], events: list[dict]) -> int:
    """An entity that came or went is 'described' when a line of its window names it (`rules.names_event`:
    "Haunts (new neutral camps): … Barrel Mimics" for Barrel Mimic I-III, "Tough Crates: …", the "Bell Tower"
    line, which is also a map line). Only the event: the numbers of a new entity the notes do not give stay
    hidden. Returns the events it described."""
    lines = [ln for s in sections for ln in s['lines'] if ln.get('status') not in ('heading', 'repeated')]
    n = 0
    for ev in events:
        ch = ev['change']
        if ch['status'] != 'hidden':
            continue
        phrases = rules.event_phrases(f"{ev['file']}:{ev['id']}", ev.get('name'))
        hit = next((ln for ln in lines if phrases and rules.names_event(ln['text'], phrases)), None)
        if hit is None:
            continue
        ch['status'] = 'described'
        _claim_line(hit, ch['key'])
        n += 1
    return n


BLANKET_FILE = tracker.ROOT / 'data' / 'overrides' / 'blanket_lines.json'


def load_blankets() -> list[dict]:
    try:
        return json.loads(BLANKET_FILE.read_text(encoding='utf-8')).get('lines', [])
    except FileNotFoundError:
        return []


def _in_scope(scope: dict, file: str, eid: str, path: str, op: str, kind: str | None) -> bool:
    if scope.get('file') and scope['file'] != file:
        return False
    if scope.get('path') and not re.search(scope['path'], path):
        return False
    if scope.get('ops') and op not in scope['ops']:
        return False
    if scope.get('kinds') and (kind or '') not in scope['kinds']:
        return False
    return not scope.get('id') or bool(re.search(scope['id'], eid))


def blanket_lines(pid: str, sections: list[dict], changes: list[MChange], events: list[dict],
                  cat: dict[str, dict], blankets: list[dict] | None = None) -> int:
    """A line that announces a whole feature without numbers ('Full shop rework, including many new items')
    covers the changes `data/overrides/blanket_lines.json` scopes to it — by field and kind of operation, never a
    whole file. Only hidden changes move (to 'described', linked to the line). Returns the changes it covered."""
    n = 0
    for b in (load_blankets() if blankets is None else blankets):
        if b.get('patch') != pid:
            continue
        needle = b['line'].lower()
        line = next((ln for s in sections for ln in s['lines'] if needle in ln['text'].lower()), None)
        if line is None:
            continue
        scopes = b.get('match') or []
        for c in changes:
            if c.status != 'hidden' or c.file == 'convars':
                continue
            kind = cat.get(ent_key(c), {}).get('kind') or c.kind
            if any(_in_scope(sc, c.file, c.eid, c.path, c.op, kind) for sc in scopes):
                c.status = 'described'
                c.lines.append(line['text'])
                _claim_line(line, c.key)
                n += 1
        for ev in events:
            ch = ev['change']
            op = ch['path'].lstrip('@')
            if ch['status'] == 'hidden' and any(_in_scope(sc, ev['file'], ev['id'], ch['path'], op, ev.get('kind'))
                                                for sc in scopes):
                ch['status'] = 'described'
                _claim_line(line, ch['key'])
                n += 1
    return n


def count_statuses(changes: list[MChange], events: list[dict]) -> dict[str, int]:
    """Gameplay changes by status; a change repeated across many entities
    ('@shared') counts once, an added/removed entity counts once."""
    counts = {'documented': 0, 'described': 0, 'hidden': 0, 'unannounced': 0, 'unreleased': 0}
    seen_shared: set[tuple] = set()
    for c in changes:
        if c.cat not in GAMEPLAY_CATS or c.file == 'convars' or c.moved:
            continue
        if c.shared:
            sig = (c.file, c.path, repr(c.old), repr(c.new), c.status)
            if sig in seen_shared:
                continue
            seen_shared.add(sig)
        counts[c.status] = counts.get(c.status, 0) + 1
    for ev in events:
        counts[ev['change']['status']] += 1
    return counts


_MODIFIER_KEY = re.compile(r'\{modifier_[^}]*\}')
# a modifier's own switches, wherever the entity keeps the modifier (m_UIRecastModifier, m_PickUpAura.…ByAura)
_MODIFIER_TAIL = re.compile(r'(?:^|\.)(m_nAttributes)$')


def _alike_path(path: str) -> str | None:
    """The path an edit shares with the same edit in other entities' modifiers, or None: a modifier key wildcarded
    ({modifier_x} -> {*}), or a modifier switch alone (m_UIRecastModifier.m_nAttributes -> m_nAttributes)."""
    tail = _MODIFIER_TAIL.search(path)
    if tail:
        return tail.group(1)
    return _MODIFIER_KEY.sub('{*}', path) if _MODIFIER_KEY.search(path) else None


def alike_in_modifiers(changes: list[MChange]) -> dict[int, tuple]:
    """id(change) -> its '@shared' signature for an edit repeated in the modifiers of many entities: each ability keeps
    its own modifier ({modifier_medic_bullets}, m_UIRecastModifier), so the record's verbatim match
    (diff.collapse_shared) misses it — "+can't be purged" on many abilities and items in build 6711 were a row each
    (todo 2026-10-17, done 2026-11-15). Only the modifier is wildcarded: a property key ({HealPctVsHeroes}) names WHAT
    moved, and six of them are six changes."""
    groups: dict[tuple, list[MChange]] = {}
    # a record's own '@shared' block (the same modifier path in 7 map objects) counts and joins too: misc.vdata's
    # block of 7 and its 4 rows under other modifiers were two things on the 2026-09-29 page
    for c in changes:
        path = None if c.file == 'convars' else _alike_path(c.path)
        if path is None:
            continue
        sig = (c.file, path, repr(c.old), repr(c.new), c.moved)
        groups.setdefault(sig, []).append(c)
    out: dict[int, tuple] = {}
    for sig, cs in groups.items():
        if len({c.eid for c in cs}) >= SHARED_MIN:
            out.update({id(c): sig for c in cs})
    return out


def modifier_block_json(c: MChange, path: str) -> dict:
    """The block's row: the field without the first target's modifier ("Proc Notification › Attributes" was one
    ability's modifier name, the block's row is "Attributes"; "Pick Up Aura effect" one map object's, the row of a
    bare switch is the switch's own label)."""
    from .field_labels import describe
    row = change_json(c)
    label = describe(path, {})['label'] if _MODIFIER_TAIL.fullmatch(path) else row['label'].rsplit('›', 1)[-1].strip()
    row.update(path=path, shared=True, label=label)
    return row


def build_patch(p: Patch, cat: dict[str, dict]) -> dict:
    commit = None
    if p.builds:
        commit = load_record(p.builds[-1]['file'])['commit']
    tok = loc.tokens(commit) if commit else {}
    changes, extras = window_changes(p, cat, tok)
    sections = annotate(p, changes, cat, tok)
    notes_text = ' '.join(ln for s in (p.notes.sections if p.notes else []) for ln in s.lines).lower()
    events = entity_events(extras, notes_text, tok)
    if not p.notes:
        # no changelog exists for this window: nothing can be "hidden from" notes
        for c in changes:
            c.status = 'unannounced'
        for ev in events:
            ev['change']['status'] = 'unannounced'
        if p.release:
            release_pass(p.release, changes, events, cat)
    if commit:
        mark_unreleased(p, commit, changes, events, cat)
    if p.notes and commit:
        # lines that announce what came or went, and features announced in one sentence (after the
        # unreleased pass: work on a hero still in development stays "Before release")
        name_events(sections, events)
        blanket_lines(p.id, sections, changes, events, cat)
    entities: dict[str, dict] = {}
    cv_status = {c.eid: c.status for c in changes if c.file == 'convars'}
    for cv in extras['convars']:
        # a hero's release post is the window's notes: what it left out is hidden (release_pass)
        cv['status'] = cv_status.get(cv['name'], 'unannounced' if not p.notes and not p.release else 'hidden')
    shared = SharedGroups()
    alike = alike_in_modifiers(changes)
    for c in changes:
        if c.file == 'convars':
            continue
        name = (loc.plain(loc.hero_name(tok, c.eid) if c.file == 'heroes.vdata'
                          else loc.entity_name(tok, c.eid, cat.get(ent_key(c), {}).get('owner')))
                if c.eid else c.eid)
        if id(c) in alike:
            sig = alike[id(c)]
            shared.add(sig, modifier_block_json(c, sig[1]) if sig not in shared else None, name, ent_key(c), c.status)
            continue
        if c.shared:
            # one edit copied into many entities (a global rule): one block, not N — with the keys of the
            # entities it hit, so their pages show it (pipeline/shared_groups.py)
            # (a field that only moved for some of its targets is two blocks: no change / a change)
            sig = (c.file, c.path, repr(c.old), repr(c.new), c.moved)
            shared.add(sig, change_json(c) if sig not in shared else None, name, ent_key(c), c.status)
            continue
        k = ent_key(c)
        e = cat.get(k, {})
        ent = entities.setdefault(k, {
            'key': k, 'file': c.file, 'id': c.eid, 'kind': e.get('kind'), 'owner': e.get('owner'),
            'name': name, 'changes': [],
        })
        ent['changes'].append(change_json(c))
    for ev in events:
        k = f"{ev['file']}:{ev['id']}"
        ent = entities.setdefault(k, {'key': k, 'file': ev['file'], 'id': ev['id'], 'kind': ev.get('kind'),
                                      'owner': ev.get('owner'), 'name': ev['name'], 'changes': []})
        ent['changes'].insert(0, ev['change'])
    for ent in shared.entities(cat, window_of(p.builds), SHARED_NAMES):
        entities[ent['key']] = ent
    for ent in entities.values():
        for c in ent['changes']:
            c['sentence'] = sentence(ent['name'], c)
    counts = count_statuses(changes, events)
    line_counts: dict[str, int] = {}
    for s in sections:
        for ln in s['lines']:
            if ln['status'] == 'unmatched' and not p.builds:
                ln['status'] = 'nodata'     # May 2024: no tracker holds game files for these dates
            line_counts[ln['status']] = line_counts.get(ln['status'], 0) + 1
    ents = sorted(entities.values(), key=lambda e: (e['file'], e['name'] or ''))
    return {
        'id': p.id, 'title': p.title, 'date': p.date[:10],
        'url': p.notes.url if p.notes else p.link, 'source': p.notes.source if p.notes else ('announcement' if p.link else None),
        'builds': [{'build': b['build'], 'date': b['date'], 'file': b['file']} for b in p.builds],
        'sections': sections,
        'entities': ents,
        'key_changes': key_changes(ents),
        'extras': slim_extras(extras, cat, lambda: window_states(p), lambda: gap_text_states(p)),
        'counts': counts,
        'line_counts': line_counts,
        **({'release': list(p.release)} if p.release else {}),
    }


def mark_unreleased(p: Patch, commit: str, changes: list[MChange], events: list[dict], cat: dict[str, dict]) -> None:
    """Work on heroes that are not in the game yet is not "hidden from the notes" — judged at the build the change
    shipped in: a hero revealed inside the window was still unreleased while tuned before the reveal (Paige, Doorman,
    Venator…: ~500 changes were "hidden", audit 2026-10-01). In a window without notes too: Nurse Harrow's boon
    tuning in Violet's release build (6790) had the eye while she was pre-release (data review 2026-10-17)."""
    commit_of = {row['build']: row['commit'] for row in p.builds if row.get('commit')}
    at: dict = {}

    def unreleased_at(builds) -> set[str]:
        out = set()
        for b in builds or [None]:
            key = commit_of.get(b, commit)
            if key not in at:
                at[key] = unreleased_heroes(key)
            out |= at[key]
        return out
    open_ = ('hidden', 'unannounced')
    for c in changes:
        owner = c.eid if c.file == 'heroes.vdata' else cat.get(ent_key(c), {}).get('owner')
        if c.status in open_ and owner and owner in unreleased_at(c.builds):
            c.status = 'unreleased'
    for ev in events:
        owner = ev['id'] if ev['file'] == 'heroes.vdata' else ev.get('owner')
        if ev['change']['status'] in open_ and owner and owner in unreleased_at([ev.get('build')]):
            ev['change']['status'] = 'unreleased'


def release_kit(hid: str, cat: dict[str, dict]) -> set[str]:
    """The entities a hero's release ships: the hero, what it owns (abilities, guns), every entry named after it
    (Violet's citadel_artist_strokeblocker, her sketch pickups pickup_artist_drawing_*) and the units its abilities
    make, which bear their names (Solomon's bishop piece is "Setup Bishop": data/overrides/unit_names.json)."""
    code = re.compile(rf'(?:^|_){re.escape(hid[len("hero_"):])}(?:_|$)')
    owned = {k for k, e in cat.items() if e.get('owner') == hid}
    names = {cat[k].get('name') for k in owned} - {None, ''}
    summons = {k for k, e in cat.items() if e['file'] == 'npc_units.vdata' and e.get('name') in names}
    return {f'heroes.vdata:{hid}'} | owned | summons | {k for k, e in cat.items() if code.search(e['id'])}


_HERO_NUMBERS = re.compile(r'^m_map(StartingStats|StandardLevelUpUpgrades|ScalingStats)\.')


def release_pass(heroes: list[str], changes: list[MChange], events: list[dict], cat: dict[str, dict]) -> None:
    """A hero's release window (pipeline.patches.release_windows): its announcement post names the hero, so the
    hero's development state turning Release is documented and its kit — the abilities, guns, summons and pickups
    that came with it, the stats it shipped with — is the release itself, described by that post, not "not in patch
    notes" (Violet's 18 rows, Baba's 19 had the eye; data review 2026-10-17). Everything else the window changed —
    other heroes' tuning, an edit shared by many entities — is what that post left out: hidden, the eye of any update
    with notes (Solomon's silent Move Piece rework sat unmarked among Violet's launch lines, its patch read 0% "not in
    notes" in the archive; review 2026-10-17, round 4). Only a window with no post at all is "unannounced".
    The hero's own numbers (`_HERO_NUMBERS`: base stats, per-boon growth, spirit scaling) are not the kit: the post
    names the hero, not its numbers, so they are hidden too; the kit slots ("Kit: Ability 1"), its role, complexity
    and sounds stay described (owner 2026-10-21, question 14)."""
    kit = set().union(*(release_kit(h, cat) for h in heroes))
    for c in changes:
        if c.shared or ent_key(c) not in kit:
            c.status = 'hidden'
        elif c.file == 'heroes.vdata' and c.path == _DEV_STATE:
            c.status = 'documented'
        elif c.file == 'heroes.vdata' and _HERO_NUMBERS.match(c.path):
            c.status = 'hidden'
        else:
            c.status = 'described'
    for ev in events:
        ev['change']['status'] = 'described' if f"{ev['file']}:{ev['id']}" in kit else 'hidden'


def unreleased_heroes(commit: str) -> set[str]:
    """Heroes not playable at that build (in development / disabled / pre-release)."""
    heroes = cache.vdata(commit, tracker.SCRIPTS + 'heroes.vdata')
    out = set()
    for hid, h in heroes.items():
        if not hid.startswith('hero_') or not isinstance(h, dict):
            continue
        state = h.get('m_eHeroDevelopmentState')
        if state is not None:
            released = state in RELEASED_STATES
        else:   # builds before the field existed
            released = not (str(h.get('m_bDisabled')).lower() in ('true', '1')
                            or str(h.get('m_bInDevelopment')).lower() in ('true', '1'))
        if not released:
            out.add(hid)
    return out


def documented_lines(p: Patch, row: dict, cat: dict[str, dict]) -> int:
    """How many of p's note lines this single build documents with exact numbers."""
    if not p.notes:
        return 0
    probe = Patch(p.id, p.title, p.date, p.notes, [row])
    commit = load_record(row['file'])['commit']
    tok = loc.tokens(commit)
    changes, _ = window_changes(probe, cat, tok)
    sections = annotate(probe, changes, cat, tok)
    return sum(1 for s in sections for ln in s['lines'] if ln['status'] == 'documented')


REASSIGN_MIN_LINES = 2
REASSIGN_MIN_SHARE = 0.05      # documented lines per gameplay field of the build


def reassign_ambiguous(patches: list[Patch], cat: dict[str, dict]) -> int:
    """Move boundary builds to the patch whose notes they match better."""
    moved = 0
    for row, prev, cur in patches_mod.ambiguous_builds(patches):
        if not (prev.notes and cur.notes):
            continue          # a synthetic (notes-less) patch keeps its own build
        a, b = documented_lines(prev, row, cat), documented_lines(cur, row, cat)
        home, other = (prev, cur) if row in prev.builds else (cur, prev)
        score_home = a if home is prev else b
        score_other = b if home is prev else a
        # a few lines that happen to match say nothing about a big build: City Never Sleeps
        # (build 6711, 1,400+ changes) matched 2 lines of the 09-16 notes and moved 13 days back
        need = max(REASSIGN_MIN_LINES, REASSIGN_MIN_SHARE * patches_mod.gameplay_fields(row))
        if score_other >= need and score_other > score_home and row in home.builds:
            home.builds.remove(row)
            other.builds.append(row)
            other.builds.sort(key=lambda r: r['date'])
            moved += 1
    return moved


# A notes-less window right after a changelog that carries this many of its numbered
# lines exactly is that changelog's update shipping late (2024-12-06 notes: 81 lines landed
# in the notes-less build 5433 of 12-14): merge the windows instead of calling it unannounced.
ABSORB_MIN = 10


def _late_count(p: Patch, data: dict, later: list[tuple[Patch, dict]], hero_name: dict[str, str]) -> int:
    n = 0
    for s in data['sections']:
        for ln in s['lines']:
            if ln['status'] != 'unmatched' or not ln.get('subject'):
                continue
            rest = ln['text'].split(':', 1)[1] if ':' in ln['text'][:48] else ln['text']
            pairs = parse_pairs(rest)
            if pairs and _late_hit(later, p, ln['subject'].lower(), pairs, expand_words(words(rest)), hero_name):
                n += 1
    return n


def absorb_late_windows(results: list[tuple[Patch, dict]], cat: dict[str, dict]) -> tuple[list, list[str]]:
    hero_name = {e['id']: e.get('name') or '' for e in cat.values() if e['file'] == 'heroes.vdata'}
    out, absorbed, i = [], [], 0
    while i < len(results):
        p, data = results[i]
        if i + 1 < len(results):
            q, qd = results[i + 1]
            # (never a hero's release window: its own announcement names it)
            if p.notes and not q.notes and not q.release and p.builds and _days(p.date, q.date) <= LATE_DAYS \
                    and _late_count(p, data, [(q, qd)], hero_name) >= ABSORB_MIN:
                p.builds = sorted(p.builds + q.builds, key=lambda b: b['date'])
                out.append((p, build_patch(p, cat)))
                absorbed.append(q.id)
                i += 2
                continue
        out.append((p, data))
        i += 1
    return out, absorbed


def run() -> None:
    cat = catalog.load()
    OUT.mkdir(parents=True, exist_ok=True)
    for old in list(OUT.glob('*.json')) + list(OUT.glob('*.json.gz')):
        old.unlink()
    index = []
    patches = group()
    print('re-assigned boundary builds:', reassign_ambiguous(patches, cat))
    results = [(p, build_patch(p, cat)) for p in patches]
    results, absorbed = absorb_late_windows(results, cat)
    print('notes-less windows merged into the changelog they implement:', absorbed)
    print('notes that landed in a later build:', late_landings(results, cat))
    print('lines repeated from a later patch (edited posts):', repeated_lines(results))
    print('lines about unmoved files (in the code):', code_lines(results))
    for p, data in results:
        jsonio.dump(OUT / f'{p.id}.json.gz', data)
        index.append({'id': p.id, 'title': p.title, 'date': p.date[:10], 'builds': len(p.builds),
                      'counts': data['counts'], 'line_counts': data['line_counts'], 'has_notes': p.has_notes,
                      **({'release': list(p.release)} if p.release else {})})
        print(p.id, p.title[:40], len(p.builds), 'builds', data['counts'], data['line_counts'])
    jsonio.dump(OUT / 'index.json', index, indent=1)


if __name__ == '__main__':
    run()
