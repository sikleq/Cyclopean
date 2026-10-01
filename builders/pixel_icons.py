"""Pixel icons drawn as ASCII grids ('#' = ink, '.' = empty) and turned into crisp SVG paths.

Font glyphs (▲ ✦ ⟳ ◆) come from whatever fallback font the visitor has: ⟳ rendered as a
"C", ▲ and ✦ changed size between platforms. These icons are the site's own, on a 10x10 grid,
drawn once and rendered with `currentColor` at any size (keep sizes multiples of 10px for
sharp pixels: 10, 20; 12/14/16 are fine for counters with crispEdges).

How to add one: see .claude/skills/pixel-icons/SKILL.md (grid rules, review at 1x and 2x)."""
from __future__ import annotations

from functools import lru_cache

GRID = 10

# tag icons: one shape per tag, readable at 10-14px, distinct silhouettes (not colour alone)
TAG_ART: dict[str, tuple[str, ...]] = {
    'buff': (
        '..........',
        '....##....',
        '...####...',
        '..######..',
        '.########.',
        '##########',
        '...####...',
        '...####...',
        '...####...',
        '..........',
    ),
    'nerf': (
        '..........',
        '...####...',
        '...####...',
        '...####...',
        '##########',
        '.########.',
        '..######..',
        '...####...',
        '....##....',
        '..........',
    ),
    'new': (
        '....##....',
        '....##....',
        '...####...',
        '..######..',
        '##########',
        '##########',
        '..######..',
        '...####...',
        '....##....',
        '....##....',
    ),
    'del': (
        '##......##',
        '###....###',
        '.###..###.',
        '..######..',
        '...####...',
        '...####...',
        '..######..',
        '.###..###.',
        '###....###',
        '##......##',
    ),
    # a replaced tier / reworked mechanic: two arrows swapping places
    'rework': (
        '.....##...',
        '.....###..',
        '#########.',
        '.....###..',
        '.....##...',
        '...##.....',
        '..###.....',
        '.#########',
        '..###.....',
        '...##.....',
    ),
    # a behaviour switch (gear)
    'mech': (
        '...####...',
        '.#.####.#.',
        '.########.',
        '####..####',
        '###....###',
        '###....###',
        '####..####',
        '.########.',
        '.#.####.#.',
        '...####...',
    ),
    # a value without a known better/worse direction: two-way arrow
    'changed': (
        '..........',
        '..........',
        '..#....#..',
        '.##....##.',
        '##########',
        '##########',
        '.##....##.',
        '..#....#..',
        '..........',
        '..........',
    ),
    'on': (
        '..........',
        '.########.',
        '.#......#.',
        '.#....###.',
        '.##..###.#',
        '.#####..#.',
        '.#.##...#.',
        '.#......#.',
        '.########.',
        '..........',
    ),
    'off': (
        '..........',
        '.########.',
        '.##....##.',
        '.#.#..#.#.',
        '.#..##..#.',
        '.#..##..#.',
        '.#.#..#.#.',
        '.##....##.',
        '.########.',
        '..........',
    ),
}


def art_path(rows: tuple[str, ...]) -> str:
    """Horizontal runs of '#' as one SVG path ('M x y h w v 1 h -w z' per run)."""
    parts = []
    for y, line in enumerate(rows):
        x = 0
        while x < len(line):
            if line[x] == '#':
                start = x
                while x < len(line) and line[x] == '#':
                    x += 1
                parts.append(f'M{start} {y}h{x - start}v1h-{x - start}z')
            else:
                x += 1
    return ''.join(parts)


@lru_cache(maxsize=None)
def tag_svg(tag: str) -> str:
    """Inline SVG for a tag class ('buff', 'nerf', …); '' for an unknown one."""
    rows = TAG_ART.get(tag)
    if not rows:
        return ''
    return (f'<svg class="ti" viewBox="0 0 {GRID} {GRID}" shape-rendering="crispEdges" aria-hidden="true">'
            f'<path fill="currentColor" d="{art_path(rows)}"/></svg>')
