"""The patch strip of an entity's page: one tile per patch (`patch_strip`), its tag bar (`strip_bar`) and colour
(`tile_colour`), the hover cards' data blob (`strip_data`, `tile_card`) and the month / year cues under the
tiles (`month_cues`)."""
from __future__ import annotations

import json

from .common import EYE_MARK, esc, patch_name, patch_title_text


# the latest patches in the strip: one row that never scrolls, scripts.js strip-end shows the newest that fit whole
# (owner 2026-10-21: 40 filled half the head of a 1680px page)
STRIP_MAX = 80


TILE_SAMPLES = 6          # a strip tile's hover card lists the patch's biggest changes…


GROUP_SAMPLES = 3         # …and keeps an ability's own biggest ones for its trail squares' card


WHOLE_TAGS = ('new', 'rework', 'del')   # a thing added, reworked or removed: no %, but as big as 100%


WHOLE_PCT = 100.0


def _rank(c: dict) -> tuple:
    """The hover cards' order of "biggest" (strip tile, trail square, home feed icon): the size of the change,
    then the tag order. A NEW / REWORK / DEL row has no % and counts as 100%: a hero's release card listed two
    small base-stat NERFs ahead of its 14 new things (Rat King, review 2026-10-04). The change matrices keep
    their own order (dynamics_page._collect: the owner's call)."""
    from .render import TAG_ORDER, tag_of
    tag = tag_of(c)[0]
    pct = c.get('pct')
    size = abs(pct) if isinstance(pct, (int, float)) else WHOLE_PCT if tag in WHOLE_TAGS else 0.0
    return (-size, TAG_ORDER.get(tag, 9))


def tile_card(groups: list[tuple[tuple, list[dict]]]) -> list[list]:
    """One strip tile's hover card: per group (ability, gun, base stats) [ref, {tag: n}, hidden, samples], a
    sample = [label, old, new, tag, hidden 0/1, rank in the patch]. A group keeps its GROUP_SAMPLES biggest
    rows and any row among the patch's TILE_SAMPLES biggest, so the strip card (top rows across the patch)
    and a trail square's card (one ability) both come from it. `groups`: [(ref, its counted rows)]."""
    from .render import not_in_notes, tag_of, vals_text
    from .shared_rows import is_every
    # a rule for every hero ranks after the entity's own changes: the card is about what changed on THIS one
    flat = sorted((c for _, cs in groups for c in cs), key=lambda c: (is_every(c), *_rank(c)))
    # one slot is the eye's: a card that says "2 not in patch notes" lists one of them (review 2026-10-05: Haze
    # 2026-04-10's six samples were all in the notes — the biggest by %)
    if flat and not any(not_in_notes(c) for c in flat[:TILE_SAMPLES]):
        i = next((i for i, c in enumerate(flat) if not_in_notes(c)), None)
        if i is not None:
            flat.insert(min(TILE_SAMPLES, len(flat)) - 1, flat.pop(i))
    rank = {id(c): r for r, c in enumerate(flat)}
    out = []
    for ref, cs in groups:
        if not cs:
            continue
        mine = sorted(cs, key=lambda c: rank[id(c)])
        first_hidden = next((c for c in mine if not_in_notes(c)), None)
        keep = [c for i, c in enumerate(mine) if i < GROUP_SAMPLES or rank[id(c)] < TILE_SAMPLES or c is first_hidden]
        counts: dict[str, int] = {}
        for c in cs:
            counts[tag_of(c)[0]] = counts.get(tag_of(c)[0], 0) + 1
        hidden = sum(1 for c in cs if not_in_notes(c))
        out.append([ref, counts, hidden, [[str(c.get('label') or ''), *vals_text(c), tag_of(c)[0],
                                           int(not_in_notes(c)), rank[id(c)]] for c in keep]])
    return out


def strip_data(items: list[tuple]) -> dict:
    """The page's hover-card data for its strip tiles and trail squares: t = tiles in strip order,
    [patch id, title, named?, {tag: n}, hidden, [[group, {tag: n}, hidden, samples], …], net mark (weights.net_of:
    'buff' / 'nerf' / 'mix' / '')]; g = the groups
    [name ('' for the page's own rows), icon url, entity ids, ultimate 0/1, a rule for all 0/1 (counted apart: the card
    gives it its own number)]; the tags' icons and words; top /
    per = how many rows the strip card / a trail card lists. The counters' icons are CSS (`.pip.<tag>`)."""
    from .render import TAG_WORD_ONE, TAG_WORDS
    from .weights import NET_WORDS
    refs: dict[tuple, int] = {}
    tiles = []
    for pid, hdr, tally, hidden, card, *rest in items[:STRIP_MAX]:
        groups = []
        for ref, counts, hid, samples in card:
            groups.append([refs.setdefault(ref, len(refs)), counts, hid, samples])
        tiles.append([pid, patch_title_text(hdr), bool(patch_name(hdr['title'])), tally, hidden, groups,
                      rest[0] if rest else ''])
    return {'t': tiles, 'g': [list(r) for r in refs], 'words': TAG_WORDS, 'word1': TAG_WORD_ONE, 'eye': EYE_MARK,
            'top': TILE_SAMPLES, 'per': GROUP_SAMPLES + 1, 'nets': NET_WORDS}


def patch_strip(items: list[tuple]) -> str:
    """The entity's patches as ONE row of tiles, oldest → newest: the newest on the right, as in the change
    matrices and the trail squares (owner 2026-10-05: "новые справа везде"; data-k still indexes the
    newest-first blob). Stripes in tag colours, the number of changes, the eye when something was not in
    the notes; a tile opens that patch below (#p-<patch>), its hover card says what it changed. The row
    never scrolls: tiles shrink to fit the column, a phone shows the newest ones (styles.css).
    The data blob comes even without a strip (one patch): the ability cards' trail squares read it too."""
    from .common import plural
    from .dynamics_page import stripes
    if not items:
        return ''
    from .dynamics_page import cap_key
    shown = items[:STRIP_MAX] if len(items) > 1 else []
    # the month under the first tile of each month, oldest left (review 2026-10-17: a row of tiles with no date)
    cues = month_cues([str(hdr.get('date') or '') for _, hdr, *_ in reversed(shown)])[::-1]
    tiles = []
    for k, (pid, hdr, tally, hidden, _card, *rest) in enumerate(shown):
        text = f'{patch_title_text(hdr)}: {plural(sum(tally.values()), "change")}'
        if hidden:
            text += f', {hidden} not in patch notes'
        cls = ' hid' if hidden else ''
        cue = f' data-m="{esc(cues[k])}"' if cues[k] else ''
        tiles.append(f'<a class="ps-tile c-{tile_colour(tally, rest[0] if rest else "")}{cls}" href="#p-{esc(pid)}" '
                     f'data-k="{k}"{cue} aria-label="{esc(text)}" style="--st:{strip_bar(stripes(tally))}">'
                     f'<span class="dn">{sum(tally.values())}</span></a>')
    tiles.reverse()                                        # oldest left, newest right
    # JSON inside a script element: "</" would end it early
    blob = json.dumps(strip_data(items), ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    strip = f'<div class="patch-strip">{"".join(tiles)}</div>' if tiles else ''
    # the orange top in words, once, under the strip that shows it (dynamics_page.cap_key)
    key = f'<div class="hs-key">{cap_key()}</div>' if any(it[3] for it in shown) else ''
    return f'{strip}{key}<script type="application/json" class="strip-data">{blob}</script>'


def strip_bar(gradient: str) -> str:
    """A strip tile's tags as a bar across its foot, left to right, under the count it shows at rest (owner 2026-11-13:
    24px squares of top-to-bottom stripes were too small, nothing fit, the colours read only on hover). The change
    matrices keep their squares (`stripes`)."""
    return gradient.replace('linear-gradient(', 'linear-gradient(90deg,', 1) if gradient else ''


_NET_COLOUR = {'buff': 'buff', 'nerf': 'nerf', 'mix': 'changed'}


def tile_colour(tally: dict[str, int], net: str) -> str:
    """A strip tile's one colour at rest (owner 2026-10-21, question 2: Sloppy's cells — a colour, the details on
    hover): what the patch did on balance (weights.net_of), else its most counted tag (the first by TAG_ORDER on a
    tie). Hover shows the tag stripes and the count."""
    from .dynamics_page import STRIPE_COLOUR, TAG_ORDER
    if net in _NET_COLOUR:
        return _NET_COLOUR[net]
    tags = [t for t in tally if tally[t]]
    if not tags:
        return 'changed'
    top = min(tags, key=lambda t: (-tally[t], TAG_ORDER.get(t, 9)))
    return STRIPE_COLOUR.get(top, top)


CUE_GAP = 2               # tiles from one month label to the next at least


def month_cues(dates: list[str]) -> list[str]:
    """A label per tile, oldest first: "Oct" under the first tile of a month, the year ("2026") under the first of a
    year, '' elsewhere; labels at least CUE_GAP tiles apart (a year's wins over the month's before it). The hover card
    and the tile's label carry the whole date."""
    from .dynamics_page import MONTH_ABBR
    out = [''] * len(dates)
    last, last_year = -CUE_GAP, False
    for i, d in enumerate(dates):
        if len(d) < 7 or not d[5:7].isdigit() or (i and d[:7] == dates[i - 1][:7]):
            continue
        year = bool(i) and d[:4] != dates[i - 1][:4]
        if i - last < CUE_GAP:
            if not year or last_year:
                continue
            out[last] = ''                       # the year's label takes the month's place before it
        out[i] = d[:4] if year else MONTH_ABBR[int(d[5:7]) - 1]
        last, last_year = i, year
    return out
