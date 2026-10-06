"""Pixel icons drawn as ASCII grids ('#' = ink, '.' = empty) and turned into crisp SVG paths.

Font glyphs (▲ ✦ ⟳ ◆) come from whatever fallback font the visitor has: ⟳ rendered as a
"C", ▲ and ✦ changed size between platforms. These icons are the site's own, on a 10x10 grid,
drawn once and rendered with `currentColor` at any size (keep sizes multiples of 10px for
sharp pixels: 10, 20; 12/14/16 are fine for counters with crispEdges).

How to add one: see .claude/skills/pixel-icons/SKILL.md (grid rules, review at 1x and 2x)."""
from __future__ import annotations

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
    # shared objects (troopers, guardians, camps, rules): the number went up / down, no better/worse
    'up': (
        '..........',
        '..........',
        '....##....',
        '...####...',
        '..##..##..',
        '.##....##.',
        '##......##',
        '#........#',
        '..........',
        '..........',
    ),
    'down': (
        '..........',
        '..........',
        '#........#',
        '##......##',
        '.##....##.',
        '..##..##..',
        '...####...',
        '....##....',
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


# the site's eye for a 12px square (an ability card's trail, history_view / trail.py): the 16-grid eye
# (`--mask-eye`) at 12px loses pixels, this one is drawn 1:1 at 10px on a dark plate, the square's tag colour left
# as a bar above and below (review 2026-10-06, #44: the trail squares had no eye)
EYE_SMALL: tuple[str, ...] = (
    '..........',
    '..........',
    '...####...',
    '.##....##.',
    '#...##...#',
    '#...##...#',
    '.##....##.',
    '...####...',
    '..........',
    '..........',
)


def eye_small_mask() -> str:
    """EYE_SMALL as a CSS mask: the `--mask-eye-sm` token in styles.css (tests/test_eye_evidence.py keeps them equal)."""
    return svg_mask(art_path(EYE_SMALL), GRID)


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


def svg_mask(d: str, view: int = 16, evenodd: bool = False) -> str:
    """A pixel shape (an SVG path on a view x view grid) as a CSS mask image: the page draws it with ::before
    in currentColor, so a page carries no inline SVG per icon (owner 2026-10-04: Calico's page held ~600
    copies of ten tag shapes; Nano's 650 inline SVGs of 12 shapes were 150 KB, perf track 2026-10-05)."""
    rule = "fill-rule='evenodd' " if evenodd else ''
    return ("url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
            f"viewBox='0 0 {view} {view}' shape-rendering='crispEdges'%3E%3Cpath {rule}d='{d}'/%3E%3C/svg%3E\")")


def tag_mask(tag: str) -> str:
    """The tag's icon as a CSS mask, written into styles.css as `.tag.<t>, .pip.<t> { --ti-content: ""; --ti: … }`
    (not :root): a tag badge and a counter draw it with ::before in their colour. tests/test_entity_page.py keeps
    those rules in sync with TAG_ART."""
    return svg_mask(art_path(TAG_ART[tag]), GRID)
