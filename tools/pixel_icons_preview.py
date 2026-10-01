"""Preview the site's pixel icons at 10/14/20/40 px on the site's panel colour.

    python tools/pixel_icons_preview.py <out.html>

Open the file (or screenshot it) and check every icon at every size: distinct silhouettes,
no lone pixels at 10px, the same visual weight across the set (see the pixel-icons skill)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from builders.pixel_icons import TAG_ART, tag_svg  # noqa: E402

COLORS = {'buff': '#86c95f', 'nerf': '#e0604f', 'new': '#e8c35a', 'del': '#d4587e', 'rework': '#a98be0',
          'mech': '#5fb5c9', 'changed': '#b9b4a6', 'on': '#86c95f', 'off': '#8a8f8c'}


def main(out: str) -> None:
    rows = []
    for tag in TAG_ART:
        cells = ''.join(f'<td style="font-size:0"><span style="display:inline-block;width:{s}px;height:{s}px;'
                        f'color:{COLORS.get(tag, "#ddd")}">{tag_svg(tag).replace("<svg ", "<svg width=100% height=100% ")}'
                        f'</span></td>' for s in (10, 14, 20, 40))
        rows.append(f'<tr><th>{tag}</th>{cells}</tr>')
    html = ('<!doctype html><meta charset="utf-8"><style>body{background:#0f1716;color:#ddd;font:14px sans-serif;padding:16px}'
            'td,th{padding:8px 14px;background:#16201e;text-align:left}</style><table>'
            '<tr><th></th><th>10</th><th>14</th><th>20</th><th>40</th></tr>' + ''.join(rows) + '</table>')
    Path(out).write_text(html, encoding='utf-8')
    print(out)


if __name__ == '__main__':
    main(sys.argv[1])
