"""Street Brawl's rows (pipeline/classify.py's 'streetbrawl' category) on the site (concept audit 2026-11-13: 1,166 rows
were on no page).

- The mode's own rules — its item draft rounds (how many rare / enhanced items a round offers), the tier buckets, the
  backdoor protection against players — are gameplay rows like any other (`is_gameplay`, `gameplay_rows`): Game ›
  Modes, the patch pages, every counter. Their labels read as words (`rule_label`: "Round 1 draft: 3 rare items
  (weight)", not "Chance Rare › Outcomes To Weights › 3"), so the 2026-09-29 re-keying of the rounds (69 fields gone,
  69 come with the same values) is one field each and no change.
- The heroes' item draft weights (heroes.vdata m_mapItemDraftWeights, 971 rows, most in '@shared' blocks) are never
  rows of a hero page: a patch's weights are ONE row of Game › Modes (`draft_row`), "Item draft weights: 18 heroes, 140
  items", folded, listing hero(es) → item → old → new, and one change for every counter."""
from __future__ import annotations

import re

from pipeline.classify import GAMEPLAY_CATS

STREET_BRAWL = 'streetbrawl'
DRAFT_FIELD = 'm_mapItemDraftWeights'
DRAFT_SUBJECT = 'brawl:draft_weights'          # its Game place (data/overrides/game_systems.json, part modes.brawl)
DRAFT_KEY = f'{DRAFT_SUBJECT}:@drafts'
MANY_HEROES = 6            # a draft line over more heroes says how many, not their names

_ROUND = re.compile(r'^m_vecItemDraftRoundsPerGameRound\[(\d+)\]\.m_chance(Rare|Enhanced)\.(?:m_mapOutcomesToWeights\.)?(\d+)$')
_PICK = re.compile(r'^m_vecItemDraftRoundsPerGameRound\[(\d+)\]\.m_vecItemDraftRounds\[(\d+)\]\.m_DraftParams\.m_str(\w+)$')
_BUCKET = re.compile(r'^m_mapItemTierToItemDraftBuckets\.EModTier_(\d+)\.(?:m_mapBuckets\.(\w+)|m_str(BucketName))$')
_SPLIT = re.compile(r'(?<=[a-z])(?=[A-Z])')


def is_draft_weight(c: dict) -> bool:
    return c.get('cat') == STREET_BRAWL and DRAFT_FIELD in str(c.get('path') or '')


def is_gameplay(c: dict) -> bool:
    """A row a player reads: the gameplay categories and Street Brawl's own rules (not the heroes' draft weights)."""
    cat = c.get('cat')
    return cat in GAMEPLAY_CATS or (cat == STREET_BRAWL and not is_draft_weight(c))


def rule_label(c: dict) -> str:
    """A Street Brawl rule's label in words: the draft rounds by round and outcome, the tier buckets by tier."""
    path = str(c.get('path') or '')
    m = _ROUND.match(path)
    if m:
        items = 'item' if m.group(3) == '1' else 'items'
        return f'Round {int(m.group(1)) + 1} draft: {m.group(3)} {m.group(2).lower()} {items} (weight)'
    m = _PICK.match(path)
    if m:
        what = _SPLIT.sub(' ', m.group(3)).lower()
        return f'Round {int(m.group(1)) + 1} draft, pick {int(m.group(2)) + 1}: {what}'
    m = _BUCKET.match(path)
    if m:
        return f'Draft of tier {m.group(1)} items: ' + (f'{m.group(2)} bucket (weight)' if m.group(2) else 'bucket name')
    label = str(c.get('label') or '')
    # "Backdoor Protection › Backdoor Protection Damage Mitigation From Players Streetbrawl"
    head, sep, leaf = label.rpartition(' › ')
    if head and leaf.startswith(head + ' '):
        leaf = leaf[len(head) + 1:]
    brawl = bool(re.search(r'[ _]?Streetbrawl$', leaf))
    leaf = re.sub(r'[ _]?Streetbrawl$', '', leaf)
    leaf = (leaf[:1].upper() + leaf[1:].lower() if sep else leaf) + (' (Street Brawl)' if brawl else '')
    return f'{head}{sep}{leaf}'


def _numeric(c: dict) -> bool:
    for v in (c.get('new'), c.get('old')):
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return True
    return False


def as_gameplay(c: dict) -> dict:
    """A copy of a Street Brawl rule row as a gameplay row (its category by its value, its label in words); any other
    row is returned as it is (the same dict: `cards.player_facing` memoises on identity)."""
    if c.get('cat') != STREET_BRAWL:
        return c
    return {**c, 'cat': 'balance' if _numeric(c) or str(c.get('new_s') or c.get('old_s') or '')[:1].isdigit()
            else 'mechanic', 'label': rule_label(c), 'brawl': True}


def gameplay_rows(changes: list[dict]) -> list[dict]:
    """The rows of `changes` a player reads (`is_gameplay`), Street Brawl's rules as gameplay rows, list rows' labels
    in words (list_labels)."""
    from .list_labels import relabel
    return [relabel(as_gameplay(c)) for c in changes if is_gameplay(c)]


# ---- the heroes' item draft weights: one row a patch --------------------------------------------------------------

def _item_of(c: dict) -> str:
    return str(c.get('path') or '').partition(DRAFT_FIELD + '.')[2]


def _real_heroes(ids: list[str]) -> list[str]:
    """The heroes among an edit's targets: not the hero template or the target dummy (catalog 'template')."""
    try:
        from .shared_rows import catalog
        cat = catalog()
    except (OSError, ValueError):
        return ids
    real = [h for h in ids if not (cat.get(f'heroes.vdata:{h}') or {}).get('template')]
    return real or ids


def draft_lines(entities: list[dict]) -> list[tuple[list[str], str, str, str, str]]:
    """([hero ids], item id, old, new, status) of a patch's item draft weight rows: a hero's own row, an '@shared'
    block's row with its targets (`target_keys`, templates out)."""
    out = []
    for e in entities:
        for c in e.get('changes') or ():
            if not is_draft_weight(c):
                continue
            if e.get('id') == '@shared':
                heroes = _real_heroes([k.partition(':')[2] for k in e.get('target_keys') or ()]
                                      or [str(c.get('key') or '').split(':')[1]])
            else:
                heroes = [e['id']]
            out.append((heroes, _item_of(c), str(c.get('old_s') or ''), str(c.get('new_s') or ''),
                        str(c.get('status') or 'hidden')))
    return out


def draft_row(p: dict) -> dict | None:
    """A patch's item draft weights as ONE row (None when it moved none): its tag by what happened to them (all came:
    NEW, all went: DEL, else CHANGED), its status the most hidden of theirs, `drafts` the lines its fold lists."""
    from .render import HIDDEN_LIKE
    lines = draft_lines(p.get('entities') or ())
    if not lines:
        return None
    ops = {'add' if not old or old == '—' else 'remove' if not new or new == '—' else 'change'
           for _, _, old, new, _ in lines}
    op = next(iter(ops)) if len(ops) == 1 else 'change'
    heroes = {h for hs, *_ in lines for h in hs}
    items = {it for _, it, *_ in lines}
    status = min((s for *_, s in lines), key=lambda s: s not in HIDDEN_LIKE)
    builds = sorted({b for e in p.get('entities') or () for c in e.get('changes') or () if is_draft_weight(c)
                     for b in c.get('builds') or ()})
    from .common import plural
    return {'key': DRAFT_KEY, 'file': 'brawl', 'id': '@drafts', 'path': '@drafts', 'op': op, 'cat': 'balance',
            'dir': 'changed', 'pct': None, 'status': status, 'builds': builds,
            'label': f'Item draft weights: {plural(len(heroes), "hero", "heroes")}, {plural(len(items), "item")}',
            'old_s': '', 'new_s': '', 'drafts': lines}


DRAFT_ENTITY = {'file': 'brawl', 'id': '@drafts', 'key': DRAFT_KEY, 'name': 'Street Brawl', 'kind': 'rules'}


def _name(eid: str) -> str:
    from .common import names_by_id, pretty_id
    return names_by_id().get(eid.lower()) or pretty_id(eid, title=True)


def drafts_html(c: dict) -> str:
    """The fold in a draft row's values (a full-width line under its label, `.erow.rw`): a line per hero (or the
    heroes one edit shared) and item, old → new. Names, never ids."""
    from .common import esc, plural
    lines = []
    every = {h for hs, *_ in c.get('drafts') or () for h in hs}
    # an edit over many heroes reads as their number, not a wall of 50 names (the one-hero lines name theirs)
    for heroes, item, old, new, _ in sorted(c.get('drafts') or (),
                                            key=lambda x: (len(x[0]) > MANY_HEROES, sorted(map(_name, x[0])), _name(x[1]))):
        who = (('All heroes' if set(heroes) >= every else plural(len(set(heroes)), 'hero', 'heroes'))
               if len(set(heroes)) > MANY_HEROES else ', '.join(sorted({_name(h) for h in heroes})))
        olds = '' if old in ('', '—') else f'<span class="old">{esc(old)}</span><span class="arrow">→</span>'
        news = '—' if new in ('', '—') else new
        lines.append(f'<li><span class="lbl">{esc(who)} › {esc(_name(item))}</span>'
                     f'<span class="vals">{olds}<span class="new">{esc(news)}</span></span></li>')
    return (f'<details class="drafts"><summary>{esc(plural(len(lines), "weight"))}</summary>'
            f'<ul class="change-list">{"".join(lines)}</ul></details>')
