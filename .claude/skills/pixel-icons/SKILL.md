---
name: pixel-icons
description: Draw or change Cyclopean's own pixel icons (tag icons BUFF/NERF/NEW/DEL/REWORK/MECH/CHANGED/ON/OFF, category glyphs) as ASCII grids that become crisp SVG. Use when a tag or UI marker needs an icon, an icon reads badly at small size, or a font glyph (▲ ✦ ⟳ ◆) shows up in the site's HTML.
---

# Pixel icons for Cyclopean

The site never uses font glyphs for meaning-bearing symbols: fallback fonts differ per platform
(⟳ rendered as a "C", ✦ changed size). Every such symbol is drawn once on a pixel grid.

## Where they live

- `builders/pixel_icons.py` — `TAG_ART` (10×10 ASCII grids, `#` ink, `.` empty), `art_path()` turns
  rows into one SVG path of horizontal runs, `tag_svg(tag)` returns the inline `<svg class="ti">`.
- `builders/render.py` — `pip(cls, n)` (icon + count) and `tag_html` (icon + word) use them;
  plain-text places (tooltips, `<title>`) use words (`render.TAG_WORDS`, `counts_text`), never glyphs.
- Category glyphs for rows without game art: `builders/common.py` `GLYPHS` (16×16 paths, evenodd).
- Colours: only `currentColor`; the tag colour comes from CSS (`.tag.buff`, `.pip.nerf` set `--c`).

## Drawing rules

1. **Grid 10×10**, every row exactly 10 characters (a test checks this). Keep a 1-cell margin when
   the shape allows; full-bleed only for wide symbols (arrows, X).
2. **Silhouette first.** Each icon must be recognisable in black at 10px without colour — colour-blind
   readers and the faint grade-1 pills rely on shape alone. Neighbours in the same row of counters
   (buff/nerf/new/del/rework) must differ in outline, not only in rotation.
3. **Strokes 2 cells** for anything that must survive 10px; 1-cell strokes only as detail.
4. **No lone pixels** (an isolated `#` with no neighbour) — they blur or vanish at 10–12px.
5. **Same visual weight** across the set: compare ink area; a much lighter icon looks disabled.
6. Shapes, by meaning: up arrow = higher is better and went up (BUFF); down arrow = NERF; four-point
   star = NEW; X = DEL; two opposed arrows = REWORK (replaced); gear = MECH (behaviour switch);
   two-headed arrow = CHANGED (moved, no better/worse); checked box = ON; crossed box = OFF.

## Review loop (always)

```bash
python tools/pixel_icons_preview.py <scratchpad>/icons.html
```

Screenshot the page (Playwright, `channel='msedge'`, headless) and look at every icon at 10, 14, 20
and 40px on the panel colour. Fix, re-render, look again. Then rebuild the site and check the icons
in context: a card header (`.tsum`), a row tag (`.tag`), the patches index counters (`.ixs`), the
patch summary hero chips (`.hchip`, 8px icons — the tightest place).

## Adding an icon

1. Add the grid to `TAG_ART` (or a new dict for another family) with a comment saying what it means.
2. Run `python -m pytest tests/test_builders.py -q` (grid shape test) and the review loop above.
3. Use it through `tag_svg` / `pip`; never paste the SVG into templates by hand.
4. Note the meaning in `docs/architecture.md` (Tags) if it is a new tag.
