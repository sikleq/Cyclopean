"""Entity cards: the one component every change list uses (patch notes, all changes,
build pages, hero / item / unit history). A card = framed 48px icon, name, subtitle,
tag counters and the strip of history squares; inside it optional ability sub-headers
and rows on a fixed grid: status | tag | text | old -> new."""
from __future__ import annotations

import re

from .brawl import drafts_html, gameplay_rows, is_gameplay  # noqa: F401 (THE gameplay rule of every builder)
from .common import esc, mark, plural, visual, wbr_ids
from .evidence import row_evidence, row_source
from .render import (HIDDEN_LIKE, NOT_IN_NOTES, fold_tier_swaps, fold_versions, folded_source, not_in_notes, sort_changes,
                     tag_badge, tag_html, tag_of, tag_summary, vals_html)
from .shared_rows import is_every

# split 2026-11-13: the row rules (renames, moves, engine plumbing, no-ops, the counting rule player_facing) are
# builders/row_rules.py, re-exported here for their callers
from .row_rules import (FACING_CACHE_MAX, NOTED, RENAME_RATIO, RENAME_RATIO_CHANGED, _ENGINE_LABEL, _ENGINE_PATH,  # noqa: F401
                        _ENGINE_TOKENS, _ENGINE_VALUE, _FACING, _FIELD_PREFIX, _LABEL_DIGITS, _LABEL_WORD, _LETTERS,
                        _LEVEL_ROW, _LEVEL_WORDS, _NOT_WORD, _NPC_AI_LABEL, _NUM, _PCT_NAME, _PELLETS, _PLUMBING_PATH,
                        _PROPERTY_WIRING, _PROP_KEY, _PROP_PATH, _UNIT_FILES, _UNIT_OF, _ZERO, _ZERO_RE, _alike,
                        _arrives, _entity_of, _last_seg, _leaves, _merge_moves, _moved, _num, _player_facing, _prop_of,
                        _rename_key, _renamed_add, _respelt, _same, _same_shown, _same_value, _unit_of, _unit_side,
                        _words, combine_levels, facing_scope, gameplay_entities, is_engine, is_noop, merge_renames,
                        merge_variants, player_facing)

# documented is the normal case: no mark (a quiet row); every other status is an exception. A notes line no change
# was found for ('unmatched') says nothing either: its grey "?" on most "Additional update notes" rows read as a broken
# icon, the key to it being in the summary only (review 2026-10-17) — the summary still counts those lines
ROW_MARKS = ('rounded', 'described', 'mismatch', 'fix', 'untracked', 'nodata', 'repeated',
             'hidden', 'unreleased', 'unannounced')


def is_hidden(changes: list[dict]) -> bool:
    """Something here was not in the patch notes (the eye; `render.NOT_IN_NOTES`)."""
    return any(c.get('status', 'hidden') in NOT_IN_NOTES for c in changes)


def card_head(name: str, icon_url: str | None, glyph: str, counted: list[dict], sub: str = '', trail: str = '',
              href: str = '') -> str:
    nm = f'<a href="{esc(href)}">{esc(name)}</a>' if href else esc(name)
    sub_html = f'<div class="sub">{esc(sub)}</div>' if sub else ''
    counted = player_facing(counted)
    counters = tag_summary(counted) if counted else ''
    return (f'<header class="ecard-h"><span class="ei">{visual(icon_url, glyph)}</span>'
            f'<div class="en"><div class="nm">{nm}</div>{sub_html}</div>'
            f'<div class="er">{counters}{trail}</div></header>')


def card(head: str, body: str, *, hidden: bool = False, dev: bool = False, search: str = '', anchor: str = '',
         extra: str = '') -> str:
    cls = 'ecard' + (' has-hidden' if hidden else '') + (' dev' if dev else '') + (f' {extra}' if extra else '')
    ds = f' data-search="{esc(search)}"' if search else ''
    aid = f' id="{esc(anchor)}"' if anchor else ''
    return f'<article class="{cls}"{aid}{ds}>{head}<div class="eb">{body}</div></article>'


def ability_plate(icon_url: str | None, glyph: str, ult: bool = False) -> str:
    """An ability's icon on a framed dark plate (the game's white glyphs read bare on the panel, owner
    2026-10-04), drawn smooth — no pixelated downscale of the 128px art; the ultimate gets a corner mark, no
    tooltip (its name is written beside it; AGENTS.md: tooltips only on text-less chips)."""
    return f'<span class="ab-ic{" ult" if ult else ""}">{visual(icon_url, glyph, "si2")}</span>'


def sub_head(name: str, icon_url: str | None, glyph: str, counted: list[dict], hidden: bool = False,
             icon: bool = True) -> str:
    """An ability inside its hero's card. `icon=False`: the caller puts the plate in its own column (an
    entity page's history: the icon anchors all of the ability's rows, like Sloppy's)."""
    counted = player_facing(counted)
    counters = tag_summary(counted) if counted else ''
    cls = 'esub' + (' has-hidden' if hidden else '')
    plate = ability_plate(icon_url, glyph) if icon else ''
    return f'<div class="{cls}">{plate}<span class="nm">{esc(name)}</span>{counters}</div>'


def row(status: str, tag: str, text_html: str, values_html: str = '', extra: str = '', attrs: str = '',
        tip: str | None = None, href: str | None = None, late: bool | None = None) -> str:
    """One change row. `tip` / `href`: the eye's own words and the build page it opens (evidence.row_evidence);
    `late`: it came in a later build, after the patch (None: when it has words of its own). A linked eye is in the tab
    order: the keyboard reaches each row's proof (review 2026-10-17; only the bands a reader opened hold rows)."""
    m = mark(status, tip, href) if status in ROW_MARKS else ''
    # a row that came after the patch, in a later build, keeps its full eye where a band's rows dim theirs (styles.css
    # .all-hidden): its words are the proof
    late = bool(tip) if late is None else late
    hid = (' is-hidden' if status in NOT_IN_NOTES else '') + (' late' if late and m else '')
    return (f'<div class="erow st-{esc(status)}{hid}{(" " + extra) if extra else ""}"{attrs}><span class="st">{m}</span>'
            f'<span class="tg">{tag}</span><span class="tx">{text_html}</span><span class="vv">{values_html}</span></div>')


def change_row(c: dict, source: bool = True) -> str:
    # a replaced tier lists both bonus sets: they go on their own full-width line under the
    # label (two lines at most, click to expand) instead of a tall right-aligned column
    extra = 'rw' if c.get('op') == 'rework' or c.get('bonus_list') else ''
    tip, href, late = row_evidence(c)        # the eye names the build it came in and opens it
    if c.get('drafts'):                      # Street Brawl's draft weights of a patch: one row, its lines folded in it
        return row(c.get('status', 'hidden'), tag_html(c), esc(c.get('label')), drafts_html(c), 'rw', tip=tip,
                   href=href, late=late)
    # a long console variable's name breaks after its underscores, not mid-word (common.wbr_ids)
    html = row(c.get('status', 'hidden'), tag_html(c), wbr_ids(esc(c.get('label'))) + shared_chip(c) + revert_chip(c),
               vals_html(c), extra, tip=tip, href=href, late=late)
    # a build page's row: its source a click away and its anchor (the eye on an entity page lands here)
    aid, src = row_source(c) if source else (None, '')
    if not src:
        return html
    ident = f' id="{aid}"' if aid else ''
    return f'<details class="src"{ident}><summary>{html}</summary>{src}</details>'


def revert_chip(c: dict) -> str:
    """'reverts 2026-06-30' after a row that puts its field back where that update took it from (builders/reverts.py)."""
    from .reverts import revert_date             # it reads the archive, which reads this module
    date = revert_date(c)
    return f' <span class="chip shr">reverts {esc(date)}</span>' if date else ''


def shared_chip(c: dict) -> str:
    """'shared ×9 heroes' after a row that one edit made in several entities at once (shared_rows.spread); a rule
    for all of them sits in its own fold instead (`every_rows`)."""
    if not c.get('shared_n') or is_every(c):
        return ''
    if c.get('shared_every'):        # the Game section lists a rule for all of them as its own row
        return f' <span class="chip shr">all {c["shared_n"]} {esc(c.get("shared_what") or "")}</span>'
    return f' <span class="chip shr">shared ×{c["shared_n"]} {esc(c.get("shared_what") or "")}</span>'


# A table edited row by row (souls per level 19-36, investment steps, the shotgun's pellet offsets)
# reads as one change: one summary row, the rows behind a click (audit 2026-10-01: ~700 rows in patches)
FAMILY_MIN = 4
# a number in a label, thousands separators included: "at 6,400 souls" is one number (the fold read
# "Vitality investment at 6–28,200 souls", review 2026-10-04)
_NUM_IN_LABEL = re.compile(r'\d{1,3}(?:,\d{3})+|\d+')


def _family(label: str) -> str:
    return _NUM_IN_LABEL.sub('N', label)


def _span(nums: list[int]) -> str:
    lo, hi = min(nums), max(nums)
    return f'{lo:,}' if lo == hi else f'{lo:,}–{hi:,}'


def family_rows(rows: list[dict]) -> str:
    rows = combine_levels(rows)
    fams: dict[str, list[dict]] = {}
    for c in rows:
        fams.setdefault(_family(str(c.get('label', ''))), []).append(c)
    html, done = [], set()
    for c in rows:
        fam = _family(str(c.get('label', '')))
        group = fams[fam]
        if len(group) < FAMILY_MIN:
            html.append(change_row(c))
            continue
        if fam in done:
            continue
        done.add(fam)
        html.append(_family_row(fam, group))
    return ''.join(html)


def _family_row(fam: str, group: list[dict]) -> str:
    """'Level 19–36: souls needed · 12 rows', tag of the group (mixed directions -> REWORK) and the
    range of % changes; the rows themselves fold under it."""
    from .render import tag_of
    first_nums = [int(m.group().replace(',', '')) for c in group for m in [_NUM_IN_LABEL.search(str(c.get('label', '')))] if m]
    base = str(group[0].get('label', ''))
    label = _NUM_IN_LABEL.sub(_span(first_nums), base, count=1) if first_nums else base
    kinds = {tag_of(c)[0] for c in group}
    rep = group[0] if len(kinds) == 1 else {'op': 'rework', 'grad': 6}
    pcts = [c['pct'] for c in group if isinstance(c.get('pct'), (int, float))]
    span = ''
    if pcts:
        lo, hi = min(pcts), max(pcts)
        span = f'{lo:+.0f}%' if round(lo) == round(hi) else f'{lo:+.0f}% … {hi:+.0f}%'
    status = min((c.get('status', 'hidden') for c in group), key=lambda s: s not in HIDDEN_LIKE)
    inner = ''.join(change_row(c) for c in group)
    vals = f'<span class="vals fam-span">{esc(span)}</span>' if span else ''
    # the summary's eye names the builds its rows not in the notes came in; it links nothing (a click on a summary
    # folds the rows, whose own eyes link their build)
    out = [c for c in group if c.get('status', 'hidden') in NOT_IN_NOTES]
    tip, href, late = (row_evidence({**out[0], 'status': status, **folded_source(out)}, link=False) if out
                       else (None, None, False))
    head = row(status, tag_html(rep), f'{esc(label)} <span class="fam-n">· {len(group)} rows</span>', vals, 'fam-head',
               tip=tip, href=href, late=late)
    hid = ' has-hidden' if is_hidden(group) else ''
    return f'<details class="fam{hid}"><summary>{head}</summary>{inner}</details>'


# A newly added entity arrives with every field it has (Baba in build 6711: 218 rows, most of them
# the level table and item-cost curves every hero shares). What a reader wants is what it IS: the
# stats a player compares and its own abilities; the rest folds under "All fields".
ADDED_KEY = re.compile(
    r'^m_mapStartingStats\.E(MaxHealth|BaseHealthRegen|MaxMoveSpeed|SprintSpeed|Stamina|LightMeleeDamage|'
    r'HeavyMeleeDamage|BulletArmorDamageReduction|TechArmorDamageReduction)$'
    r'|^m_mapBoundAbilities\.ESlot_(Signature_\d|Weapon_Primary)$'
    r'|^m_eHeroDevelopmentState$'
    r'|^m_mapAbilityProperties\.[^.]+\.m_strValue$'
    r'|^m_(nMaxHealth|iMaxHealth|flMaxHealth|nCost|iItemTier|eItemSlotType)$')
ADDED_KEY_LIMIT = 12


def _added_split(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    key = [c for c in rows if ADDED_KEY.search(str(c.get('path') or '')) and str(c.get('new_s', '')) not in ('0', '')]
    keep = key[:ADDED_KEY_LIMIT]
    kept = {id(c) for c in keep}
    return keep, [c for c in rows if id(c) not in kept]


_CAMEL = re.compile(r'[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+')
_HINT_SKIP = {'percent', 'pct', 'value', 'bonus', 'amount', 'base', 'max', 'm', 'str', 'fl', 'amp', 'penalty', 'power'}


def history_hints(changes: list[dict]) -> dict[tuple[str, str], str]:
    """(label, property) -> its hint over an entity's WHOLE history, so a row reads the same in every
    patch: Puddle Punch's T3 "Damage · base" also where the heavy-melee one did not move (2026-10-03)."""
    props: dict[str, list[str]] = {}
    for c in changes:
        p = _prop_of(c)
        if p and not is_noop(c) and not is_engine(c) and p not in props.setdefault(str(c.get('label')), []):
            props[str(c.get('label'))].append(p)
    out: dict[tuple[str, str], str] = {}
    for lab, ps in props.items():
        if len(ps) > 1:
            out |= {(lab, p): h for p, h in zip(ps, _group_hints(lab, ps)) if h}
    return out


def disambiguate(rows: list[dict], known: dict[tuple[str, str], str] | None = None) -> list[dict]:
    """Two fields of one entity under one label ("Healing Reduction" for both the receive and the regen
    penalty, Puddle Punch's two "T3: Damage" with opposite tags — 104 pairs, advisor round 3): each gets
    the words of its property name the label lacks, "Healing Reduction · receive". `known`: the
    entity's history_hints, which win so a row reads alike across patches."""
    known = known or {}
    groups: dict[str, list[tuple[int, str]]] = {}
    for i, c in enumerate(rows):
        prop = _prop_of(c)
        if prop:
            groups.setdefault(str(c.get('label')), []).append((i, prop))
    hint_of: dict[int, str] = {}
    for lab, members in groups.items():
        if len(members) > 1:
            hs = _group_hints(lab, [p for _, p in members])
            if not any(hs):     # one stat under two names ("TechPower" 7 → 0 beside a new "SpiritPower" 8)
                hs = [_moved_hint(rows[i]) for i, _ in members]
            hint_of |= dict(zip((i for i, _ in members), hs))
        hint_of |= {i: known[(lab, p)] for i, p in members if (lab, p) in known}
    return [{**c, 'label': f'{c.get("label")} · {hint_of[i]}'} if hint_of.get(i) else c for i, c in enumerate(rows)]


def _group_hints(label: str, props: list[str]) -> list[str]:
    """One hint per namesake. A bare one beside hinted ones gets a word too (Puddle Punch's T3: "Damage
    −50" beside "Damage · heavy melee +50" read as one stat twice, advisor round 4): its skipped words
    ("bonus"), else "base"; two alike hints keep their skipped words too ("base attack" / "attack bonus")."""
    hs = [_hint(label, p) for p in props]
    hs = [h or _hint(label, p, skip=frozenset()) for p, h in zip(props, hs)]
    hs = [_hint(label, p, skip=frozenset()) if hs.count(h) > 1 else h for p, h in zip(props, hs)]
    return [h or 'base' for h in hs] if any(hs) else hs


def _moved_hint(c: dict) -> str:
    if c.get('op') == 'add':
        return 'new field'
    return 'old field' if c.get('op') == 'remove' or str(c.get('new_s')) in ('0', '—', '', 'None') else ''


def _hint(label: str, prop: str, skip: frozenset[str] | set[str] = _HINT_SKIP) -> str:
    """The words of a property name its label lacks: 'HealAmpRegenPenaltyPercent' under "Healing
    Reduction" -> "regen"; Spirit is Tech in the files ("Spirit Power · tech" said nothing)."""
    have = {w.lower() for w in re.findall(r'[A-Za-z]+', label)}
    if 'spirit' in have:
        have.add('tech')

    def said(w: str) -> bool:               # "heal" is in "Healing"
        return w in have or any(len(w) >= 4 and (h.startswith(w) or w.startswith(h)) for h in have if len(h) >= 4)
    return ' '.join(w for w in (x.lower() for x in _CAMEL.findall(prop))
                    if not said(w) and w not in skip and w not in _HINT_NEVER)


# words a hint never is, even when nothing else tells two namesakes apart ("Incoming Damage Deferred · pct";
# review 2026-10-05): the unit or the container a field name carries, not what it is about
_HINT_NEVER = frozenset({'pct', 'percent', 'percentage', 'value', 'values', 'fl', 'str', 'm'})


def entity_rows(changes: list[dict], known: dict[tuple[str, str], str] | None = None, every_href=None) -> str:
    """The rows of one entity in one patch on its own page (owner, 2026-10-03): what a player reads —
    no "Technical" fold (engine plumbing stays in data/, not on the page), and a newly added entity is
    its NEW head and key fields only, without "All fields". `known`: history_hints of the entity. A rule for every
    entity of its kind (shared_rows.is_every) is one link row after the entity's own (`every_rows`); `every_href`:
    system id -> the Game page's band of this patch."""
    every = [c for c in changes if is_every(c)]
    if every:
        own = [c for c in changes if not is_every(c)]
        return (entity_rows(own, known) if own else '') + every_rows(every, every_href)
    rows = disambiguate([c for c in sort_changes(fold_tier_swaps(fold_versions(merge_renames(changes))))
                         if not is_noop(c) and not is_engine(c)], known)
    # a new entity's many fields: its head and key fields. Not console variables (13 new ones read "Console variables
    # 13 · Added to the game" over nothing) and not when no field is a key one (Nox Nostra's 15 new T1-T3 bonuses on
    # build-6801: a head over nothing) — those rows are listed (concept audit 2026-11-13)
    keep = (_added_split(rows)[0] if len(rows) > ADDED_KEY_LIMIT and all(c.get('op') == 'add' for c in rows)
            and not any(c.get('convar') for c in rows) else [])
    if keep:
        head = row('hidden' if is_hidden(rows) else rows[0].get('status', 'hidden'),
                   tag_badge('new', 'NEW'), 'Added to the game', attrs=behind_attr(changes, keep))
        return head + ''.join(change_row(c) for c in keep)
    return family_rows(rows)


def every_rows(changes: list[dict], every_href=None) -> str:
    """A rule for (almost) every entity of a kind on one of them — the level curve, the investment bonuses, a
    default of every melee attack — as ONE row per Game system that lists it: "All heroes: 35 changes · Hero
    progression ›" with its tag counters, a link to that system's band of the patch (coverage audit 2026-10-05:
    spread over the heroes, 35 level-curve rows drowned a hero's own patch). The rows themselves are on the Game
    page only: folded on every hero page they grew heroes/ from 13 to 37 MB (Haze 295 → 755 KB; review
    2026-10-05). Counted apart from the entity's own changes (history_view); `shr-all`: no tag or eye filter keeps
    the row, no band recount counts it (scripts.js hist-filter)."""
    rows = [c for c in sort_changes(fold_tier_swaps(fold_versions(merge_renames(changes))))
            if not is_noop(c) and not is_engine(c)]
    return every_links(rows, every_href)


def every_key(c: dict) -> tuple[str, str]:
    """(Game system, noun) of a row of a rule for all: one link row each, so a link names what the reader finds
    there ("All melee attacks" never merges into "All abilities & items", review 2026-10-05)."""
    from .game_systems import place_all_row
    return place_all_row(str(c.get('file') or ''), c)[0], str(c.get('shared_what') or 'entities')


def every_links(rows: list[dict], every_href=None) -> str:
    """The link rows of rules for all, from rows already as the counters count them (`player_facing`, one per
    rule: history_view dedupes the copies a rule leaves on each of the entity's abilities)."""
    from .game_systems import system
    by_sys: dict[tuple[str, str], list[dict]] = {}
    for c in rows:
        by_sys.setdefault(every_key(c), []).append(c)
    out = []
    for (sid, what), got in by_sys.items():
        # plain words: "15 changes for all heroes · see Hero progression ›" ("All heroes: 15 changes · Hero
        # progression ›" read as a code; visual pass 2026-10-17, round 2)
        text = f'{plural(len(got), "change")} for all {esc(what)}'
        name = esc(system(sid).name)
        go = (f' <a class="shr-go" href="{esc(every_href(sid))}">see {name} ›</a>' if every_href
              else f' <span class="shr-go">in {name}</span>')
        # no status mark: the rows' own marks are on the Game page; here it is a way there, not a change
        out.append(row('shared', '', f'<span class="shr-t">{text}</span>{go}', tag_summary(got), 'shr-all'))
    return ''.join(out)


def behind_attr(changes: list[dict], listed: list[dict]) -> str:
    """' data-n="new:57:40 on:1:1"' — the counted changes (player_facing, what the band's counters count) a
    head row stands for without listing them, as tag:changes:hidden. A filter recounts a band from its shown
    rows (scripts.js `hist-filter`); without this a new unit's band read NEW 71 built and 60 under a filter
    that kept every row (Old Gods, 2026-10-04)."""
    shown ={(c.get('key'), c.get('path')) for c in listed}
    per: dict[str, list[int]] = {}
    for c in player_facing(changes):
        if (c.get('key'), c.get('path')) in shown:
            continue
        n = per.setdefault(tag_of(c)[0], [0, 0])
        n[0] += 1
        n[1] += not_in_notes(c)
    return ' data-n="' + (' '.join(f'{t}:{n}:{h}' for t, (n, h) in per.items()) or 'new:0:0') + '"'


def change_rows(changes: list[dict], added: bool = False) -> str:
    rows, first, second = _layout(changes, added)
    if added:
        head = row('hidden' if is_hidden(rows) else rows[0].get('status', 'hidden') if rows else 'hidden',
                   tag_badge('new', 'NEW'),
                   f'Added to the game files · {len(rows)} fields')
        html = head + ''.join(change_row(c) for c in first)
        if second:
            # a new entity's every field (a new hero: ~200): no source per row — the build page grew 2.0 -> 4.2 MB;
            # its key rows have theirs, the head links the file's diff (review 2026-10-17)
            inner = ''.join(change_row(c, source=False) for c in second)
            html += f'<details class="tech"><summary>All fields ({len(second)})</summary>{inner}</details>'
        return html
    html = family_rows(first)
    if second:
        inner = ''.join(change_row(c) for c in second)
        hid = ' has-hidden' if is_hidden(second) else ''
        html += f'<details class="tech{hid}"><summary>Technical ({len(second)})</summary>{inner}</details>'
    return html


def _layout(changes: list[dict], added: bool) -> tuple[list[dict], list[dict], list[dict]]:
    """How `change_rows` lays an entity's rows out — (its rows, the first list, the second): a new entity's key rows
    and its other fields ("All fields", no source); else the player rows, whole levels as one row (`combine_levels`:
    `family_rows` finds nothing more to combine), and the engine plumbing ("Technical"). No-ops are dropped."""
    rows = sort_changes(fold_tier_swaps(fold_versions(merge_renames(changes))))
    if added:
        return (rows, *_added_split(rows))
    main, tech = [], []
    for c in rows:                                # one is_engine call a row (it ran twice)
        if not is_noop(c):
            (tech if is_engine(c) else main).append(c)
    return rows, combine_levels(main), tech


def writes_rows(changes: list[dict], added: bool = False) -> bool:
    """Whether `change_rows` writes any row: a card whose rows are all no-ops ("Duration Reducible no" added, a field
    re-keyed with its value) was a name over an empty body — 35 on build pages, 50 on patch pages (22 on build-6801:
    Parry, Cold Front, Cursed Relic; concept audit 2026-11-13). A new entity always writes its head."""
    if added:
        return True
    _, first, second = _layout(changes, added)
    return bool(first or second)


def listed_rows(changes: list[dict], added: bool = False) -> list[dict]:
    """Every row `change_rows` writes with `change_row` and its source (`_layout`, the one plan of both) — the rows a
    build page gives a source and an anchor (builds_pages.shown_keys)."""
    _, first, second = _layout(changes, added)
    return first if added else first + second
