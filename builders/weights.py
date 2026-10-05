"""How much a set of changes helped or hurt what they changed: (net, volume), as Sloppy weighs a patch (its
patch/weights.py: weight(type) × size × direction). One function for every place that says "net buff / nerf"
(`net_of`) — the change matrices' "Buff vs nerf" colours counted a majority (one +50% buff lost to two −10% nerfs;
review 2026-10-05).

A BUFF / NERF row weighs its size: min(|%|, 60) / 20 (a row without a % weighs 1); a NEW thing +1 and a removed
one −1; reworks, mechanics and plain UP / DOWN add volume only. Calibration is open: the weights are Sloppy's
shape, not fitted to Deadlock's patches yet."""
from __future__ import annotations

PCT_CAP = 60.0
PCT_UNIT = 20.0
MIX_NET = 0.25            # |net| below this is a mix
MIX_SHARE = 0.2           # …and so is a net under this share of the volume


def row_score(c: dict) -> tuple[float, float]:
    """(signed weight, volume) of one change row."""
    from .render import tag_of
    tag = tag_of(c)[0]
    pct = c.get('pct')
    size = min(abs(pct), PCT_CAP) / PCT_UNIT if isinstance(pct, (int, float)) and pct else 1.0
    if tag == 'buff':
        return size, size
    if tag == 'nerf':
        return -size, size
    if tag == 'new':
        return 1.0, 1.0
    if tag == 'del':
        return -1.0, 1.0
    return 0.0, 1.0


def band_score(rows: list[dict]) -> tuple[float, float]:
    net = vol = 0.0
    for c in rows:
        s, v = row_score(c)
        net += s
        vol += v
    return round(net, 2), round(vol, 2)


def net_class(net: float, volume: float) -> str:
    """'net-buff' / 'net-nerf' / 'net-mix' by the weighed sum."""
    if abs(net) < MIX_NET or (volume and abs(net) / volume < MIX_SHARE):
        return 'net-mix'
    return 'net-buff' if net > 0 else 'net-nerf'


NET_WORDS = {'buff': 'net buff', 'nerf': 'net nerf', 'mix': 'mixed'}


def weighed_rows(rows, in_dev: bool = False) -> list[dict]:
    """The rows a net mark weighs — what a band counts: a rule for every hero / ability (shared_rows.is_every) is
    counted apart everywhere, and work before release only on the page of an entity still in development. The change
    matrices weighed both and disagreed with the band in 44 hero cells (Nano 2024-09-26: band "net nerf", tile buff
    — eleven buffs of abilities still in development; review 2026-10-05)."""
    from .shared_rows import is_every
    return [c for c in rows if not is_every(c) and (in_dev or c.get('status') != 'unreleased')]


def net_of(rows, in_dev: bool = False) -> str:
    """THE net mark of what one patch did to one entity: 'buff' / 'nerf' / 'mix' by the weighed sum (net_class) of its
    `weighed_rows`, '' when none of them takes a side (only reworks, mechanics, plain changes, or nothing released:
    nothing to weigh). Every place that says it reads this: a history band's banner, a strip tile's and a home feed
    icon's hover card, a change-matrix tile's "Buff vs nerf" colour and its card (review 2026-10-05: the matrices
    weighed, the rest of the site did not say)."""
    rows = weighed_rows(rows, in_dev)
    if not any(row_score(c)[0] for c in rows):
        return ''
    return net_class(*band_score(rows)).removeprefix('net-')


def net_chip(mark: str) -> str:
    """The banner's one quiet chip for a net mark (styles.css .net-chip, in the tag colours); '' for no mark."""
    return f'<span class="net-chip net-{mark}">{NET_WORDS[mark]}</span>' if mark else ''
