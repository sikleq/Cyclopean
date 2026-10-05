"""Preview the site's pixel icons at 10/14/20/40 px on the site's panel colour.

    python tools/pixel_icons_preview.py <out.html>

Open the file (or screenshot it) and check every icon at every size: distinct silhouettes,
no lone pixels at 10px, the same visual weight across the set (see the pixel-icons skill).

Each icon is drawn the way the site draws it: a CSS mask (pixel_icons.svg_mask) on an element
painted in its colour — tag badges and counters (TAG_ART), status marks (common.MARK_ART) and
category glyphs (common.GLYPHS)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from builders.common import GLYPHS, MARK_ART  # noqa: E402
from builders.pixel_icons import TAG_ART, svg_mask, tag_mask  # noqa: E402

COLORS = {'buff': '#86c95f', 'nerf': '#e0604f', 'new': '#e8c35a', 'del': '#d4587e', 'rework': '#a98be0',
          'mech': '#5fb5c9', 'changed': '#b9b4a6', 'on': '#86c95f', 'off': '#8a8f8c'}
SIZES = (10, 14, 20, 40)


def masks() -> list[tuple[str, str, str]]:
    """(family, name, CSS mask url) of every icon, in the site's own encoding."""
    out = [('tag', t, tag_mask(t)) for t in TAG_ART]
    out += [('mark', m, svg_mask(d)) for m, d in MARK_ART.items()]
    out += [('glyph', g, svg_mask(d, evenodd=True)) for g, d in GLYPHS.items()]
    return out


def page() -> str:
    css, rows = [], []
    for i, (family, name, url) in enumerate(masks()):
        css.append(f'.i{i}{{--m:{url}}}')
        cells = ''.join(f'<td><span class="ic i{i}" style="width:{s}px;height:{s}px;color:{COLORS.get(name, "#ddd")}">'
                        f'</span></td>' for s in SIZES)
        rows.append(f'<tr><th>{family}</th><th>{name}</th>{cells}</tr>')
    return ('<!doctype html><meta charset="utf-8"><style>body{background:#0f1716;color:#ddd;font:14px sans-serif;'
            'padding:16px}td,th{padding:8px 14px;background:#16201e;text-align:left}td{font-size:0}'
            '.ic{display:inline-block;background:currentColor;-webkit-mask:var(--m) center/100% 100% no-repeat;'
            'mask:var(--m) center/100% 100% no-repeat}' + ''.join(css) + '</style><table>'
            '<tr><th></th><th></th>' + ''.join(f'<th>{s}</th>' for s in SIZES) + '</tr>' + ''.join(rows) + '</table>')


def main(out: str) -> None:
    Path(out).write_text(page(), encoding='utf-8')
    print(out)


if __name__ == '__main__':
    main(sys.argv[1])
