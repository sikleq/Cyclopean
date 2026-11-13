"""Reading one patch-note line (`annotate`, `annotate_line`): its subject, its numbers and its words against the changes
of the window, the status it gets and the changes it links. Split out of `match` 2026-11-13; every name is
re-exported there."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import loc, semantics
from . import classify as classify_mod
from . import flags as flag_rules
from . import match_rules as rules
from .classify import GAMEPLAY_CATS
from .match_score import (INLINE_NAME_MAX_KEYS, Subject, _BASE_DAMAGE, _LABEL_FILLER, _LOOSE_PCT, _MINUTES, _SECONDS,
                          _SPAWN_TIMER, _names_moved, _same_kind, ent_key, inline_alias, inline_names, label_words,
                          list_hits, mismatch_field, name_index, names_other_stat, names_whole_property, pair_hits,
                          pct_close, resolve_subject, score, system_alias, system_lines_pools, system_pools,
                          twin_hits, verb_sign)
from .match_values import (APPROX, GENERIC_WORDS, HERO_STAT_WORDS, MChange, SYNONYM_ONLY, WEAPON_WORDS, _BY_RE,
                           _CHANGED_FROM, _FIX_RE, _HALF_DAMAGE, _ITEM_TIER_MOVE, _METRES_ON_LINE, _MOVED_TO_TIER,
                           _NUM, _PARENS, _PCT_LESS, _SWAP_LINE, _TIER_NAME, _TIER_RE, _numeric, _same_way, _stems,
                           _tokens, data_values, exact_pair, expand_words, granted_pair, half_match, list_match, num,
                           parse_pairs, topic_words, two_sided, words)
from .patches import Patch


def annotate(p: Patch, changes: list[MChange], cat: dict[str, dict], tok: dict[str, str]) -> list[dict]:
    idx = name_index(changes, cat, tok)
    by_ent: dict[str, list[MChange]] = {}
    for c in changes:
        by_ent.setdefault(ent_key(c), []).append(c)
    notes = '\n'.join(ln for s in (p.notes.sections if p.notes else []) for ln in s.lines)
    rescale = rules.boon_rescale(notes)
    for c in changes:
        c.scale = rescale[0] if rules.rescaled_field(c, rescale) else 1.0
    pools = system_pools(by_ent, cat)
    # an ability's Street Brawl numbers answer only the lines about that mode (classify.STREET_BRAWL_VALUE)
    plain = [c for c in changes if not classify_mod.STREET_BRAWL_VALUE.search(c.path)]
    plain_by_ent: dict[str, list[MChange]] = {}
    for c in plain:
        plain_by_ent.setdefault(ent_key(c), []).append(c)
    sections = []
    for sec in (p.notes.sections if p.notes else []):
        out_lines = []
        head = None
        mode_sec = bool(_STREET_BRAWL.search(sec.title or ''))
        for text in sec.lines:
            if _SUBHEAD.match(text) and not heading(text, idx):       # not a bare "Sinclair:" (heading)
                # "Items:" / "Street Brawl:" inside one post (2026-10-30): a heading of the lines below it, and the
                # mode's lines answer with its Street Brawl numbers ("Scrap Grenade - Radius reduced from 8m to 6m")
                mode_sec = bool(_STREET_BRAWL.search(text) or _STREET_BRAWL.search(sec.title or ''))
                head = None
                out_lines.append({'text': text, 'subject': None, 'status': 'heading', 'changes': []})
                continue
            mode = mode_sec or bool(_STREET_BRAWL.search(text))
            cs, be = (changes, by_ent) if mode else (plain, plain_by_ent)
            h = heading(text, idx)
            if h:
                # the 2025 layout: a bare 'Sinclair' line heads the lines below it
                head = h
                out_lines.append({'text': text, 'subject': h, 'status': 'heading', 'changes': []})
                continue
            own_prefix = ':' in text[:48] and resolve_subject(text.split(':', 1)[0], idx, cat)
            probe = f'{head}: {text}' if head and not own_prefix else text
            res = annotate_line(probe, cs, be, idx, cat, tok, rescale, pools)
            res['text'] = text
            if res['status'] == 'unmatched':
                topic = rules.untracked_topic(text.split(':', 1)[1] if own_prefix else text, sec.title,
                                              has_subject=bool(res.get('subject')))
                if topic:
                    res['status'] = 'untracked'
                    res['topic'] = topic
            out_lines.append(res)
        sections.append({'title': sec.title, 'lines': out_lines})
    post_pass(changes, by_ent)
    return sections


_HEADING_MAX = 40
_STREET_BRAWL = re.compile(r'street\s*brawl', re.I)
# a sub-heading line of a post: a few words and a colon, nothing after it ("General:", "Street Brawl:")
_SUBHEAD = re.compile(r'^\s*[A-Z][\w&\'\- ]{1,30}:\s*$')


def heading(text: str, idx: dict[str, list[str]]) -> str | None:
    """A line that is only an entity name ('Boundless Spirit') is a sub-heading."""
    t = text.strip().rstrip(':').strip()
    if not t or len(t) > _HEADING_MAX or ':' in t or re.search(r'\d', t):
        return None
    return t if idx.get(t.lower()) else None


_NO_LONGER = re.compile(r'\b(no longer|removed)\b', re.I)
_OLD_TIER = re.compile(r'\b(old|previous|former)\s+T[1-3]\b.*\bbase\b', re.I)


def post_pass(changes: list[MChange], by_ent: dict[str, list[MChange]]) -> None:
    """Rules that look at matches as a whole (audit patterns 2 and 7)."""
    for c in list(changes):
        if c.status not in ('documented', 'described') or not c.lines:
            continue
        line = c.lines[0]
        # 7: a feature added in one go: the matched field's siblings (added/removed together)
        root = rules.cluster_root(c.path)
        mode = bool(_STREET_BRAWL.search(line))
        for sib in by_ent.get(ent_key(c), []):
            if sib.status == 'hidden' and sib.cat in GAMEPLAY_CATS and sib.op in ('add', 'remove') \
                    and rules.cluster_root(sib.path) == root \
                    and (mode or not classify_mod.STREET_BRAWL_VALUE.search(sib.path)):
                sib.status = 'described'
                sib.lines.append(line)
        # a line that tells a rework in words is about every field of that entity that came or went with it:
        # "Baba's Brew - No longer has an initial brew time" took its Brew Time 1.5s → 0s, and its Barrier / Fire /
        # Silence Lock Time removed kept the eye (owner 2026-10-30: "described another way, not hidden"). Tuned
        # numbers stay hidden; a field that came or went with a number of its own only when the line says something
        # went away (the audit's real finds: Walker's new 30% trooper factor, Kinetic Pulse's new T2 +8s)
        if c.status == 'described':
            gone = bool(_NO_LONGER.search(line))
            for sib in by_ent.get(ent_key(c), []):
                if sib.status == 'hidden' and sib.cat in GAMEPLAY_CATS and sib.op in ('add', 'remove') \
                        and (num(sib.old if sib.op == 'remove' else sib.new) is None or gone and sib.op == 'remove'):
                    sib.status = 'described'
                    sib.lines.append(line)
        # 2: "(affects upgrades)": items built from this one moved the same way
        if c.status == 'documented' and rules.AFFECTS_UPGRADES_RE.search(line):
            for other in changes:
                if other.status == 'hidden' and other.path == c.path and other.old == c.old and other.new == c.new:
                    other.status = 'described'
                    other.lines.append(line)


@dataclass
class _Line:
    """One patch-note line on its way through `annotate_line`'s steps: what the line says (its numbers, words,
    tier), what it is about (`subject`, the `pool` of changes, the abilities it names) and its `result`."""
    text: str
    changes: list
    by_ent: dict
    idx: dict
    cat: dict
    tok: dict
    rescale: object
    pools: object
    subject: Subject | None
    rest: str
    lw: set
    pairs: list
    fix_line: bool
    granted: bool
    by_pct: float | None
    by_at: int | None
    tier: int | None
    result: dict
    pool: list = field(default_factory=list)
    ability_hits: set = field(default_factory=set)
    by_name: set = field(default_factory=set)


def annotate_line(text, changes, by_ent, idx, cat, tok, rescale=None, pools=None) -> dict:
    """`pools`: the window's game systems and their changed entries (`system_pools`), for a line with numbers only:
    a system holds dozens of entries, and a line without numbers would link whichever shares a word ("Added Dash
    Speed to the Vitality stat screen" took the zipline's Latch End Speed)."""
    ln = _read_line(text, changes, by_ent, idx, cat, tok, rescale, pools)
    done = _line_subject(ln)
    if done is not None:
        return done
    _line_aim(ln)
    done = _line_numbers(ln)
    if done is not None:
        return done
    return _line_words(ln)


def _read_line(text, changes, by_ent, idx, cat, tok, rescale, pools) -> _Line:
    """What the line says: its subject before a colon, its words, its number pairs (minutes, a fix's swap, a value
    granted or taken), a percent it moves by and the tier it names."""
    pools = system_lines_pools(text, pools)
    subject = None
    rest = text
    if ':' in text[:48]:
        prefix, rest = text.split(':', 1)
        subject = resolve_subject(prefix, idx, cat)
    lw = expand_words(words(rest))
    pairs = parse_pairs(rest)
    fix_line = bool(_FIX_RE.search(text))
    if fix_line and pairs:
        # "Fixed Health Regen being 3 instead of 1.5": the value WAS 3 and is 1.5 now, the other way round
        # from "drops now happen at 15 minutes instead of 20" (Seven 2025-05-27 stayed hidden)
        pairs = pairs + [(b, a) for a, b in pairs if (b, a) not in pairs]
    if _MINUTES.search(rest) or (_SPAWN_TIMER.search(rest) and not _SECONDS.search(rest)
                                 and all(max(a, b) <= 60 for a, b in pairs)):
        # "Rejuv duration 4 -> 3 minutes" while the files count seconds (240 -> 180): 8 lines unmatched;
        # a spawn timer says minutes without the word ("Vaults spawn time/interval 10/5 -> 8/4")
        pairs = pairs + [(a * 60, b * 60) for a, b in pairs]
    granted = False
    # the numbers outside parentheses are the change; inside, a total or an aside ("(0->14%)")
    outer = rest if not pairs else _PARENS.sub(' ', rest)
    if not pairs or not parse_pairs(outer):
        # "Now grants +75 Health" / "No longer grants +16% Spirit Resist": one number is a value that
        # appeared (0 -> N) or went away (N -> 0) — 769 numeric lines were unmatched, these the most;
        # "Now gains 1% Bullet Resist per Boon (0->14%)" is 0 -> 1, the 14% its total
        g = granted_pair(outer)
        if g:
            pairs, granted = g, True
    if not pairs and not fix_line and _HALF_DAMAGE.search(rest):
        # "Vexing Bolt - Now does half damage to objectives": its Boss Damage Scale 100% -> 50% (review 2026-10-17)
        pairs = [(100.0, 50.0)]
    # "Threadsap duration lasts 35% less" says by how much as "increased by 35%" does
    m = _BY_RE.search(rest) or _PCT_LESS.search(rest)
    by_pct = float(m.group('p')) if m else None
    by_at = m.start() if m else None
    mv = _ITEM_TIER_MOVE.search(rest)
    if mv and not pairs:
        # "Shadow Weave: Moved from T4 to T3" is the item's tier 4 -> 3, not an ability's T3 upgrade
        pairs = [(float(mv.group(1)), float(mv.group(2)))]
    tm = None if mv else _TIER_RE.search(rest)
    tier = int(tm.group(1)) if tm else None
    result = {'text': text, 'subject': subject.name if subject else None, 'status': 'unmatched', 'changes': []}
    return _Line(text, changes, by_ent, idx, cat, tok, rescale, pools, subject, rest, lw, pairs, fix_line, granted,
                 by_pct, by_at, tier, result)


def _line_subject(ln: _Line) -> dict | None:
    """A line without a subject: untracked topics, the rules for lines over many entities (boons, "all ..."), a
    name or alias inside it. The result when the line is done, else None (`ln.subject` may be set)."""
    text, changes, by_ent, idx, cat = ln.text, ln.changes, ln.by_ent, ln.idx, ln.cat
    rescale, pools, subject, pairs, by_pct, result = ln.rescale, ln.pools, ln.subject, ln.pairs, ln.by_pct, ln.result
    if not subject:
        topic = None if pairs or by_pct is not None else rules.untracked_topic(text)
        if topic not in (None, 'visual') and not (topic == 'interface' and _names_moved(text, idx, cat, by_ent)):
            # sound / interface / map words first: "Lowered volumes for UI death notification sounds
            # and respawn music" is not about respawn (annotate() tags it untracked) — P12; a bug fix
            # stays a fix ("…caused audio bugs as well"); not "visual": "Guardian melee no longer has a
            # splash range much larger than its visuals" is gameplay. An interface word next to an entity
            # whose files moved is matched first (#47.2): "Added keybinds for 'Fly Up' and 'Fly Down'. Used for
            # flying abilities like Ivy's Air Drop and Vindicta's Flight" is their new flight controls
            return _fix_or(result, text)
        covered = (rules.boon_lines(text, changes, rescale, num) or rules.global_line(text, changes, cat, num)
                   or rules.global_delta_line(text, changes, cat, num))
        if covered:
            return _link(result, covered, text, 'described')
        # "Walker bounty increased by 5%": the unit is named inside the line; failing a common word,
        # an entity's own name ("Medic Pack ally search radius from 30 to 35"); the game system the line names
        # ("Jump Pad stun window …"), with an alias or alone
        aliased = inline_alias(text, idx)
        named = set() if aliased else inline_names(text, idx, cat, by_ent)
        systems = system_alias(text, pools)
        if aliased or (systems and not named):
            subject = Subject(aliased, None, 'alias_inline', systems - aliased)
        elif named:
            subject = Subject(named, None, 'name_inline')
    ln.subject = subject
    return None


def _line_aim(ln: _Line) -> None:
    """The changes the line can be about (`ln.pool`, gameplay only) and the abilities / guns it names
    (`ln.ability_hits`, `ln.by_name`); a line about an entity whose files did not move is marked `_quiet`."""
    changes, by_ent, idx, cat, tok = ln.changes, ln.by_ent, ln.idx, ln.cat, ln.tok
    subject, rest, lw, result = ln.subject, ln.rest, ln.lw, ln.result
    if subject:
        # sorted: set order changes between runs (hash randomisation) -> unstable output
        pool = [c for k in sorted(subject.ids) for c in by_ent.get(k, [])]
    else:
        pool = changes
    ability_hits = set()
    by_name: set[str] = set()       # the hero's abilities / guns the line names by their own name
    if subject and subject.kind == 'hero':
        low = rest.lower()
        for k in subject.ids:
            e = cat.get(k, {})
            nm = loc.plain(loc.entity_name(tok, e.get('id', ''), e.get('owner'))).lower()
            if nm and len(nm) > 2 and any(v in low for v in rules.name_variants(nm)):
                ability_hits.add(k)
                # a name of its own, as a whole word: every hero's "Melee" names no one ability ("Gloom Bomb T2 …
                # Melee Resist"), nor does "Heal" inside "Health"
                if (not k.startswith('heroes.vdata:') and len(idx.get(nm, ())) <= INLINE_NAME_MAX_KEYS
                        and any(re.search(rf'\b{re.escape(v)}s?\b', low) for v in rules.name_variants(nm))):
                    by_name.add(k)
        if _BASE_DAMAGE.search(rest) and not ability_hits:
            # a hero's "base damage" is its gun's bullet damage ("Celeste: Base damage reduced from 29 to
            # 25" is the gun's 28.75 -> 25; "damage" and "base" are no words of their own here)
            lw = lw | {'bullet'}
        if lw & WEAPON_WORDS:
            ability_hits |= {k for k in subject.ids if cat.get(k, {}).get('kind') == 'weapon'}
        if not ability_hits and lw & HERO_STAT_WORDS:
            ability_hits |= {k for k in subject.ids if k.startswith('heroes.vdata:')}
        if lw & {'growth', 'boon'}:
            # "Bullet damage growth 0.28 -> 0.32": per-boon stats live on the hero, not on the gun
            ability_hits |= {k for k in subject.ids if k.startswith('heroes.vdata:')}
        # ability_hits only add score: "Bullet damage per boon" names the gun
        # but the value lives on the hero, so the pool is never narrowed.
    elif subject:
        ability_hits = set(subject.ids)     # an item / unit line is about that entity
    if subject and subject.kind not in ('alias_inline', 'name_inline'):
        # what the line is about, to tell later whether its files moved at all: the abilities it names,
        # else the whole subject (run() turns a still-unmatched line about unmoved files into "code")
        named = {k for k in ability_hits if not k.startswith('heroes.vdata:')
                 and cat.get(k, {}).get('kind') != 'weapon'} if subject.kind == 'hero' else set()
        about = named or set(subject.ids)
        if not any(c.cat in GAMEPLAY_CATS for k in about for c in by_ent.get(k, [])):
            result['_quiet'] = sorted(about)
    pool = [c for c in pool if c.cat in GAMEPLAY_CATS]
    ln.pool, ln.ability_hits, ln.by_name, ln.lw = pool, ability_hits, by_name, lw


def _line_numbers(ln: _Line) -> dict | None:
    """A line with numbers: the best-scored fields (its subject's, a game system's, the whole patch's), or a
    disagreement between the notes and the files (mismatch). The result, or None to try its words."""
    text, changes, by_ent, subject, rest, lw = ln.text, ln.changes, ln.by_ent, ln.subject, ln.rest, ln.lw
    pairs, by_pct, by_at, tier, granted, fix_line = ln.pairs, ln.by_pct, ln.by_at, ln.tier, ln.granted, ln.fix_line
    pool, ability_hits, result = ln.pool, ln.ability_hits, ln.result
    # an inline name or alias whose entity did not move at all still gets the whole-patch pass below (the Dash
    # ability had no change on 2026-07-28: "… ground dash time 0.7s to 0.72s" never reached it)
    inline = bool(subject) and subject.kind in ('alias_inline', 'name_inline')
    sys_ids = subject.numeric_ids if subject else set()
    sys_pool = [c for k in sorted(sys_ids) for c in by_ent.get(k, []) if c.cat in GAMEPLAY_CATS]
    if (pairs or by_pct is not None) and (pool or inline or sys_pool):
        # a line without a subject must also share a word with the field label; so must one whose
        # subject is only named inside it ("Medic Trooper … heal 14% → 12%" is not its range 14 → 12 m).
        # Not an alias's: "Walker HP increased by 40%" shares no word ("HP", "damage" are not words here)
        need_word = not subject or subject.kind == 'name_inline'
        need = 1 if need_word else 0

        def rank(cands, hits_):
            out = sorted(((score(c, rest, pairs, by_pct, lw, tier, hits_, granted), c) for c in cands
                          if not need_word or label_words(c) & lw), key=lambda x: -x[0])
            return out, (out[0][0] if out else 0)

        def enough(b) -> bool:
            return b >= 10 + need or (by_pct is not None and b >= 6 + need)
        # the game system the line names (`system_alias`): its entries carry no name a line could use and often no
        # word of it ("Jump Pad stun window increased from 0.6s to 0.9s" is the catapult watcher's Duration;
        # coverage finding 8) — not a field that names another stat than the line ("Movement Speed powerup
        # movespeed reduced from 2 to 1" is not the stamina powerup's Extra Stamina 2 -> 1)
        # — and no word is waived for one number alone: a field that only took the line's new value (an add, "now
        # grants") or moved by its percent must share a word with the line; both sides of a pair need none
        sys_pool = [c for c in sys_pool if not names_other_stat(c, lw)
                    and (label_words(c) & lw or two_sided(c, pairs))]
        tried = False

        def system_pass() -> None:
            nonlocal scored, best, pool, ability_hits, need_word, need, tried
            tried = True
            before = (scored, best, pool, ability_hits, need_word, need)
            need_word, need = False, 0
            pool, ability_hits = sys_pool, set(sys_ids)
            scored, best = rank(pool, ability_hits)
            if not enough(best):
                scored, best, pool, ability_hits, need_word, need = before
        scored, best = rank(pool, ability_hits)
        if not enough(best) and any(list_match(c, pairs, APPROX) for c in sys_pool):
            # a whole number list ("Trooper bounty split from 100/60/35/25/20/16% to 100/60/30/20/15/11") is the
            # list field of its system before any lone number of the patch (it took 87 investment bonuses)
            system_pass()
        if not enough(best) and subject and subject.kind in ('name_inline', 'alias_inline'):
            # the name was a coincidence ("Gun Powerup … Fire Rate" names the old item "Fire Rate"), or the
            # alias was: "Stamina bucket 3 heroes … ground dash time increased from 0.7s to 0.72s" is not the
            # Dash ability, "Heavy Melee cooldown increased from 0.9s to 1.0s" not the Parry — the pairs are
            # every slow hero's / every melee's, one '@shared' block each (unmatched until review 2026-10-05).
            # The whole patch, as for a line without a subject: a field must share a word with the line
            own_pass = (scored, best, pool, ability_hits, need_word, need)
            need_word, need = True, 1
            pool, ability_hits = [c for c in changes if c.cat in GAMEPLAY_CATS], set()
            scored, best = rank(pool, ability_hits)
            if subject.kind == 'alias_inline' and not enough(best):
                # nothing there either: a disagreement is judged on the alias's own fields, as before
                scored, best, pool, ability_hits, need_word, need = own_pass
        if not enough(best) and sys_pool and not tried:
            system_pass()       # last otherwise: a line an earlier pass matched keeps its fields
        if enough(best):
            hits = [c for s, c in scored if s == best]
            if len(pairs) > 1:
                # one best field for EACH pair: "Base HP 6725 -> 12500 and growth 470 -> 200" is two fields,
                # though "growth" scores the second one higher (P13 2026-10-02)
                hits += [c for c in pair_hits(scored, pairs, 9 + need) if c not in hits]
            if granted:
                # every field that took the value and shares a word: "Now grants +5% Ability Range" is the
                # range AND the radius multiplier (Echo Shard, 2025-11-21)
                # — of the same ability, by a word of the label (not by "T3" alone: Heavy Barrage's "+2m
                # explosion radius" took Spectral Wall's "Create Turrets 2")
                same = {ent_key(h) for h in hits}
                hits += [c for s, c in scored if s >= 9 + need and c not in hits
                         and ent_key(c) in same and label_words(c) & lw
                         and names_whole_property(c, lw) and _same_kind(c, lw)]
            if by_pct is not None and not pairs:
                # "respawn times, hp, and bounty reduced by 30%": the best field of EACH property listed
                hits += [c for c in list_hits(rest[:by_at], pool, by_pct, text, ability_hits) if c not in hits]
                if tier is None and subject and subject.kind not in ('alias_inline', 'name_inline'):
                    # a cut to a property without a tier is its tier bonuses too, where they moved by as much: "Strix
                    # Salvo - Spirit scaling reduced by 8%" is the base scaling and T3's +0.35 → +0.322 (2026-11-04);
                    # a line with a subject only ("Breakables growth values reduced by 10%" is no Burrow's T1)
                    props = {(ent_key(h), semantics.property_name(h.path)) for h in hits}
                    sign, rate = verb_sign(text), bool(re.search(r'rate|speed', text, re.I))
                    hits += [c for c in pool if c not in hits and re.match(r'T[1-3]:', c.label or '')
                             and (ent_key(c), semantics.property_name(c.path)) in props
                             and pct_close(c, by_pct, sign, rate, bool(_LOOSE_PCT.search(text)))]
                if re.search(r'\b(all|every)\b', rest, re.I):
                    # "Mo & Krill: Spirit damage on all abilities reduced by 10%": every damage that moved by it
                    # (Combo 40 → 35, Burrow 75 → 65, rounded), not the best-scored field alone (2026-10-30)
                    sign, rate = verb_sign(text), bool(re.search(r'rate|speed', text, re.I))
                    # (a tier's own value too: "all abilities" is base and upgrades, T1 Burrow 50 → 45)
                    # (the line's own words: words() drops "damage" as too common, and it is the property here)
                    said = set(re.findall(r'[a-z]+', rest.lower())) - {'spirit', 'ability', 'abilities', 'all', 'base'}
                    hits += [c for s, c in scored if s >= 5 + need and c not in hits
                             and set(re.findall(r'[a-z]+', (c.label or '').lower())) & said
                             and pct_close(c, by_pct, sign, rate, True)]
            if pairs and not granted:
                hits += twin_hits(scored, hits, pairs, lw, tier)
            for c in hits:
                c.status = 'documented'
                c.lines.append(text)
                if not granted:          # "now grants +75" keeps the NEW value, not an invented 0 -> 75
                    _old_from_notes(c, pairs, text, pool)
            moved_to = _MOVED_TO_TIER.search(rest)
            if moved_to:
                # "Baba's Brew - Cooldown increased from 25s to 27s (moved to T2)": T2's cooldown bonus -12s → -14s
                # is that move (it had the eye, data review 2026-10-17)
                props = {(ent_key(h), semantics.property_name(h.path)) for h in hits}
                for c in pool:
                    if c.status == 'hidden' and c.label.startswith(f'T{moved_to.group(1)}:') \
                            and (ent_key(c), semantics.property_name(c.path)) in props:
                        c.status = 'described'
                        c.lines.append(text)
            # a "now grants +N" value is stated exactly; its invented 0 is not a rounding
            rounded = pairs and not granted and not any(exact_pair(c, pairs) for c in hits)
            result['status'] = 'fix' if fix_line else 'rounded' if rounded else 'documented'
            result['changes'] = [c.key for c in hits]
            if rounded:
                result['data'] = data_values(hits[0], pairs)
            return result
        # names a property of this entity and one side of the numbers agrees,
        # the other does not: the notes and the files disagree. "Names" by a word of its own — not a
        # common one ("time", "resistance") nor one the subject brings ("guardian" -> "tier"): 2025-07-04
        # "Guardian base resistance 40% -> 60%" was a "mismatch" with Tier2 Gold Kill (review 10-02)
        own = words(rest) - GENERIC_WORDS - rules.ALIAS_WORDS
        # the pairs a disagreement is judged on: outside parentheses, and a real change — "changed from
        # 0.2s cast delay to 0.2s post cast time" moves a value to another property, 0.2 = 0.2
        said = [(a, b) for a, b in parse_pairs(_PARENS.sub(' ', rest)) if a != b] if not granted else []
        top = [c for s, c in scored
               if num(c.old) is not None and mismatch_field(c, lw, own, _tokens(rest))
               and (not ability_hits or ent_key(c) in ability_hits)
               and half_match(c, said)]
        # not for a name found inside the line: by now its pool may be the whole patch
        # nor for "now / no longer grants +N": its other side (0) is ours, not Valve's — the property is
        # often reused ("No longer grants +15% Spirit Lifesteal as base stat" while the field went 15 -> 16)
        if subject and subject.kind != 'name_inline' and top and not granted:
            c = top[0]
            if c.status == 'hidden':
                c.status = 'described'
            c.lines.append(text)
            result['status'] = 'mismatch'
            result['changes'] = [c.key]
            result['data'] = data_values(c, pairs)
            return result
    ln.pool, ln.ability_hits = pool, ability_hits         # a pass over the whole patch keeps its pool
    return None


def _line_words(ln: _Line) -> dict:
    """A line the numbers did not settle: its subject's fields by the words they share with it (a tier's, a
    component list, a removal, the ability it names), else its mechanics."""
    text, by_ent, idx, cat, subject, rest, lw = ln.text, ln.by_ent, ln.idx, ln.cat, ln.subject, ln.rest, ln.lw
    pairs, by_pct, tier, result = ln.pairs, ln.by_pct, ln.tier, ln.result
    pool, ability_hits, by_name = ln.pool, ln.ability_hits, ln.by_name
    if not subject:
        return _fix_or(result, text)
    if _FIX_RE.search(text):
        return _fix_or(result, text)
    specific = lw - GENERIC_WORDS

    def on_topic(c: MChange) -> bool:
        """The field shares a specific word with the line (not just 'bullet' or 'damage'), or a flag that
        came or went names it ("Decay: No longer interrupts sliding" = DONT_INTERRUPT_SLIDE_ON_CAST)."""
        flags = flag_words(c) & specific
        # a hero line's flags: of the ability it names ("Viscous: Can now use down dash during Goo Ball" is
        # not The Cube's behaviour)
        if flags and subject.kind == 'hero' and ability_hits and ent_key(c) not in ability_hits:
            flags = set()
        if _STATE_MASK.search(c.path):
            return bool(flags)
        own = topic_words(c)
        wide = label_words(c) if '›' not in (c.label or '') else rules.expand_label_words(own)
        return bool(own & specific) or bool(wide & specific - SYNONYM_ONLY) or bool(flags)

    def came(c: MChange) -> bool:
        """An item's field that came, by a word's stem — only when no field shares a word (`on_topic`): "Healbane:
        Stacks now diminish 20% more aggressively" is its new Stacking Penalty Anchor 80%, "Toxic Bullets: Now scales
        with Spirit Power (0.005%)" its new spirit scaling (2026-11-04); "Headhunter: Heal now scales with spirit power"
        has its heal field and is not the bonus damage's new scaling."""
        return (subject.kind == 'item' and c.op == 'add' and not _STATE_MASK.search(c.path)
                and bool((_stems(topic_words(c)) - GENERIC_WORDS) & (_stems(specific) - GENERIC_WORDS)))

    def named_whole(c: MChange) -> bool:
        """Every word of the label is in the line, common ones too: "Fury Trance: Active Bullet Resistance
        changed to Spirit Resistance" names Bullet Resist and Spirit Resist. The subject's own fields only
        (a hero line: the ability it names)."""
        core = words(c.label or '') - _LABEL_FILLER
        # two words at least, or one of its own: "Bullet Damage" is just "bullet" (Afterburn "… each bullet")
        enough = (len(core) >= 2 or bool(core - GENERIC_WORDS)) and not _STATE_MASK.search(c.path)
        return (enough and all(w in lw or rules.expand_label_words({w}) & lw for w in core)
                and (subject.kind != 'hero' or ent_key(c) in ability_hits))

    if subject.kind in ('alias_inline', 'name_inline'):
        # a unit merely named inside a sentence: link only on the field's own words (not a synonym:
        # "Continuous interior from jungle area to the walker" is not the aura radius) and never from
        # a line about sounds or looks ("Updated Mo & Krill Burrow … end sounds" is not falloff end)
        if pairs or _PRESENTATION_LINE.search(text):
            return result
        linked = [c for c in pool if words(c.label) & specific and not _STATE_MASK.search(c.path)]
        return _link(result, linked, text, 'described') if linked else result
    # 3: "T2 changed from 'A' to 'B'" / "T3 also increases radius": that tier's fields of the ability
    if tier is not None:
        scope = [c for c in pool if (not ability_hits or ent_key(c) in ability_hits)
                 and re.match(rf'T{tier}:', c.label)]
        topical = [c for c in scope if on_topic(c)]
        whole_tier = re.search(r'changed from|reworked|replaced|swapped', text, re.I)
        # "T3 no longer has 'Ink is no longer destroyed'": what that tier lost (its Destroy On Damage, 2026-10-30)
        gone = [c for c in scope if c.op == 'remove'] if _NO_LONGER.search(text) else []
        chosen = topical or (scope if whole_tier else gone)
        if chosen and _OLD_TIER.search(text):
            # "Now grants the old T2 barrier in the base ability": the base took what the tier had — its fields that
            # came from nothing (Traveler's Barrier 0 → 400, Buff Duration 0s → 12s, 2026-10-30)
            abil = {ent_key(c) for c in chosen}
            chosen = chosen + [c for c in pool if ent_key(c) in abil and not re.match(r'T[1-3]:', c.label)
                               and (c.op == 'add' or num(c.old) == 0) and c not in chosen]
        if chosen:
            return _link(result, chosen, text, 'described')
    # 2: "Now builds from Sprint Boots": component list of the item
    if rules.COMPONENT_RE.search(text):
        comp = [c for c in pool if 'ComponentItems' in c.path]
        if comp:
            linked = comp + [c for c in pool if c not in comp and on_topic(c)]
            return _link(result, linked, text, 'described')
        # "Berserker: Now builds into Frenzy": the list that moved is Frenzy's
        into = [c for k in inline_names(rest, idx, cat, by_ent) - set(subject.ids)
                for c in by_ent.get(k, ()) if 'ComponentItems' in c.path]
        if into:
            return _link(result, into, text, 'described')
    # textual line: link changes of the subject that share a specific word with the line; failing
    # that, a line naming an ability describes that ability's MECHANICS (flags, targets, behaviour) —
    # never its numbers, and never from a line about how it looks or sounds ("Storm Cloud audio is
    # clearer" had claimed its cooldown 180 → 148; 468 changes were "described" only that way)
    fallback = []
    if ability_hits and subject.kind == 'hero' and not _PRESENTATION_LINE.search(text):
        # (a modifier's states only when a state a player plays with moved: not "has fire beetles debuff")
        fallback = [c for c in pool if ent_key(c) in ability_hits and c.cat == 'mechanic'
                    and (not _STATE_MASK.search(c.path) or flag_rules.is_gameplay(c.path, c.old, c.new))]
    if _REMOVED_LINE.search(text):
        # "Soul Rebirth: Removed from the game" is its Disabled false -> true
        gone = [c for c in pool if c.cat == 'availability'
                and (subject.kind != 'hero' or not ability_hits or ent_key(c) in ability_hits)]
        if gone:
            return _link(result, gone, text, 'described')
    linked = [c for c in pool if on_topic(c) or named_whole(c)] or [c for c in pool if came(c)]
    # the ability the line names, when it has such a field: "Siphon Life range now scales…" is not
    # Seismic Impact's collide radius
    named = [c for c in linked if ent_key(c) in ability_hits]
    if by_name and not pairs:
        # the named ability's fields by a word's stem: "Scrap Grenade - Fixed some bugs with bouncing targeting" is its
        # Bounce Target Distance Check / Power and Bounce Max Horizontal Speed (they kept the eye, review 2026-10-17)
        stems = _stems(specific) - GENERIC_WORDS
        named += [c for c in pool if ent_key(c) in by_name and c not in named and not _STATE_MASK.search(c.path)
                  and (_stems(topic_words(c)) - GENERIC_WORDS) & stems]
    # a line that names an ability or gun by its name is about it, never the hero's base stats: "Strix Salvo -
    # Cooldown from 30s to 25s" took Danny's Stamina Cooldown 4.5s → 5s, "Chimera Mk1 - Slow effectiveness in air
    # reduced by 15%" his Air Dash Duration (data review 2026-10-17)
    linked = named or ([] if by_name else linked)
    if linked and pairs:
        # the line's numbers must agree with the field: one side of a pair within the notes' rounding, or the same
        # way up (30 → 25 is not 4.5 → 5); a field without numbers (a flag, a class) is judged by its words
        said = [(a, b) for a, b in parse_pairs(_PARENS.sub(' ', rest)) if a != b] or pairs
        linked = [c for c in linked if not _numeric(c) or half_match(c, said) or _same_way(c, said)]
    if linked and (pairs or by_pct is not None):
        # a line with numbers no field matched: the fields that share the MOST of its words ("Bullet
        # damage growth reduced by 18%" is the bullet growth, not the health growth)
        # (not the words in parentheses: "(affects base damage, AP and spirit scaling)" names no field)
        core = expand_words(words(_PARENS.sub(' ', rest)))
        most = max(len(label_words(c) & core) for c in linked)
        linked = [c for c in linked if len(label_words(c) & core) == most]
    if linked and fallback and all(c.cat == 'mechanic' and ent_key(c) in ability_hits for c in linked):
        # only the named ability's flags spoke: its other mechanics stay described as before
        linked = linked + [c for c in fallback if c not in linked]
    linked = linked or fallback
    if not linked and by_name and not pairs:
        # a words line whose one number is a value the named ability's field had or took: "Guided Owl - Now launches in
        # the exact direction you're aiming (previously always launched at least 45° upward)" is its Arrow Initial
        # Pitch -45 → 89 (2026-10-30)
        # (in the field's unit — "-20s cd" is no Fire Rate 20% — and of the tier the line names, if it names one)
        said = {(abs(float(m.group('v'))), m.group('u') or '')
                for m in re.finditer(rf'(?P<v>{_NUM})\s*(?P<u>%|s\b|m\b)?', _TIER_NAME.sub(' ', rest))}
        tiers = set(re.findall(r'\bT([1-3])\b', rest))

        def says(c: MChange) -> bool:
            t = re.match(r'T([1-3]):', c.label)
            if (t.group(1) if t else None) not in (tiers or {None}):
                return False            # a line without a tier is about the base ("Afterburn (20% for light melee)")
            vals = {abs(v) for v in (num(c.old), num(c.new)) if v}
            unit = (c.unit or '')[:1]
            return any(v in vals and (not u or not unit or u == unit) for v, u in said)
        linked = [c for c in pool if ent_key(c) in by_name and not _STATE_MASK.search(c.path) and says(c)]
    if linked:
        return _link(result, linked, text, 'described')
    return result


# a modifier's states: its label is the modifier's container ("Holding Idol › Applies"), so a line links it
# only by the states that came or went ("not disarmed or silenced"), never by the container's words ("Please
# continue to give feedback on the Urn" took the Urn runner's states, 2026-10-04)
_STATE_MASK = re.compile(r'\.m_nEnabledStateMask$')
_FLAG_WORD_FIELDS = {'m_AbilityBehaviorsBits', 'm_nAbilityBehaviors', 'm_nAbilityTargetTypes', 'm_nAbilityTargetFlags',
                     'm_bitsInterruptingStates', 'm_nBehaviors', 'm_eAbilityTargetingLocation',
                     'm_eAbilityTargetingShape', 'm_nAttributes', 'm_nEnabledStateMask', 'm_nDisabledStateMask'}
_REMOVED_LINE = re.compile(r'\b(removed from the (game|shop)|(is|are|now) disabled|no longer (available|in the shop))\b',
                           re.I)
_FLAG_PREFIX = re.compile(r'^(CITADEL_ABILITY_BEHAVIOR_|CITADEL_UNIT_TARGET_|CITADEL_|MODIFIER_STATE_|MODIFIER_)')


def flag_words(c: MChange) -> set[str]:
    """The words of the flags a flag field gained or lost (Behaviour, Can target, Interrupted by…)."""
    leaf = c.path.rsplit('.', 1)[-1]
    # a modifier's attributes too: "Multiple instances stack" = MODIFIER_ATTRIBUTE_MULTIPLE (Slice and Dice);
    # bit sets only (not the enums and switches FLAG_FIELDS also names)
    if leaf not in _FLAG_WORD_FIELDS:
        return set()
    split = lambda v: {f.strip() for f in str(v or '').split('|') if f.strip()}      # noqa: E731
    moved = split(c.old) ^ split(c.new)
    out = set().union(*(words(_FLAG_PREFIX.sub('', f).replace('_', ' ')) for f in moved)) if moved else set()
    # a state is named by its -ing form, a line by the verb: MODIFIER_STATE_SLIDING_DISABLED is "Restored being able
    # to slide while using Bullet Dance" (2026-04-30; the line had gone to Bullet Dance's channel move speed)
    out |= {v for w in out if w.endswith('ing') and len(w) > 5 for v in (w[:-3], w[:-3] + 'e')}
    return out - _FLAG_FILLER


# flag words every behaviour list repeats: they name no behaviour of their own
_FLAG_FILLER = {'can', 'use', 'cast', 'ability', 'target', 'unit', 'set', 'dont', 'allow', 'while', 'during',
                'displays', 'damage', 'impact', 'friendly', 'enemy', 'all', 'hero', 'heroe', 'ui', 'instant',
                'attribute'}


_PRESENTATION_LINE = re.compile(r'\b(sounds?|audio|sfx|vfx|visuals?|effects?|particles?|animations?|anims?|models?|'
                                r'icons?|ui|hud|tooltips?|indicators?|music|voice|crosshair|readability)\b', re.I)


def _link(result: dict, changes: list[MChange], text: str, status: str) -> dict:
    for c in changes:
        if c.status == 'hidden':
            c.status = 'described'
        c.lines.append(text)
    result['status'] = status
    result['changes'] = [c.key for c in changes]
    return result


def _fix_or(result: dict, text: str) -> dict:
    """Bug-fix lines rarely change data: tag them instead of calling them unmatched."""
    if result['status'] == 'unmatched' and _FIX_RE.search(text):
        result['status'] = 'fix'
    return result


def _old_from_notes(c: MChange, pairs: list[tuple[float, float]], text: str = '',
                    siblings: list[MChange] | None = None) -> None:
    """A field that appeared with the value Valve says it was raised TO: before, the game used its
    default, and the notes name it ("Headshot stack count increased from +2 to +3" while the files
    only gained HeadshotStacks = 3). The line's old value makes it a change (BUFF/NERF), not a NEW.
    Not on a line that swaps one bonus for another ('T2 changed from "-12s Cooldown" to …'), nor when
    the entity lost a field holding that old value — then A belonged to the other field (audit
    2026-10-01: ~25 invented "was → now" such as "T2: Cooldown 12 → −15")."""
    if c.op != 'add' or c.old is not None or c.meters or num(c.new) is None or _SWAP_LINE.search(text) \
            or _CHANGED_FROM.search(text):
        return
    # a value the files write with its unit ("16m", Street Brawl radii) takes the old one in the same unit: a bare 20
    # was read as engine units and shown 0.508m (Rule, Ratannia!, 2026-10-30)
    suffix = re.sub(rf'^\s*{_NUM}\s*', '', c.new) if isinstance(c.new, str) else ''
    if _METRES_ON_LINE.search(text) and suffix != 'm':
        return
    removed_values = {num(s.old) for s in siblings or () if s.eid == c.eid and s.op == 'remove' and num(s.old) is not None}
    olds = {a for a, b in pairs if abs(b - num(c.new)) < 1e-9 and a != b}
    if len(olds) == 1 and not any(abs(a - r) < 1e-9 for a in olds for r in removed_values):
        old = olds.pop()
        c.old = f'{old:g}{suffix}' if suffix else old
        c.op = 'change'
