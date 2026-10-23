"""A hero's model rebuilt, as a row of its history: the model's file in the game grew or shrank several times over
(pipeline.extras.size_jumps; Doorman's luggage trolley 1.68 MB → 0.17 MB in build 6815, 2026-10-22, the fix of a cart
drawn twice that no patch note told). The pipeline keeps them per patch (extras.models); `entities_pages._history`
files them under 'model:<hero key>' and `history_view` adds them to the hero's group of that patch.

A size is no counted change: a neutral MODEL badge, the eye of a change the notes left out, never a band's counters
(scripts.js `countRows` skips `.model-row`)."""
from __future__ import annotations

import re

from .common import esc

MODEL_PREFIX = 'model:'
# the copy of a model the other team sees ("_friendly") is the same model: one row
_SIDE = re.compile(r'_(?:friendly|enemy)$')
_REDO = re.compile(r'_v\d+$')
TIP = 'Not in patch notes'


def model_name(path: str) -> str:
    """'models/heroes_wip/doorman/doorman_luggagetrolley.vmdl_c' -> 'luggagetrolley' (the hero's folder name off)."""
    parts = path.split('/')
    folder = _REDO.sub('', parts[-2]) if len(parts) > 1 else ''
    name = _SIDE.sub('', parts[-1].rsplit('.', 1)[0])
    if folder and name.startswith(folder + '_'):
        name = name[len(folder) + 1:]
    return name.replace('_', ' ')


def size_text(n: int) -> str:
    return f'{n / 1e6:.2f} MB' if n >= 1e6 else f'{n / 1e3:.0f} KB'


def ratio_text(old: int, new: int) -> str:
    if new < old:
        return f'{old / new:.0f}× smaller'
    return f'{new / old:.0f}× bigger'


def model_window(models: list[dict]) -> list[dict]:
    """One model per patch: its first size to its last, at its last build; none when it came back (Graves' torso
    piece 34 KB -> 2 KB -> 34 KB inside 2026-01-22) or moved less than SIZE_JUMP in all."""
    from pipeline.extras import SIZE_JUMP
    by_name: dict[str, dict] = {}
    for m in sorted(models, key=lambda m: (m.get('build') or 0, m['path'])):
        name = model_name(m['path'])
        first = by_name.get(name)
        by_name[name] = {**m, 'old': first['old']} if first else dict(m)
    return [m for m in by_name.values() if max(m['old'], m['new']) / min(m['old'], m['new']) >= SIZE_JUMP]


def model_rows(models: list[dict]) -> str:
    from .cards import row
    from .evidence import build_evidence
    from .render import note_badge
    tag = note_badge('MODEL')
    out = []
    for m in model_window(models):
        name = model_name(m['path'])
        vals = (f'<span class="vals"><span class="old">{esc(size_text(m["old"]))}</span><span class="arrow">→</span>'
                f'<span class="new">{esc(size_text(m["new"]))}</span>'
                f'<span class="muted">&nbsp;· {esc(ratio_text(m["old"], m["new"]))}</span></span>')
        # the eye names the build and opens its page, as a field change's does (evidence.row_evidence)
        tip, href, late = build_evidence(m['build']) if m.get('build') else (None, None, False)
        out.append(row('hidden', tag, esc(f'Model {name}: file size'), vals, extra='model-row', tip=tip or TIP,
                       href=href, late=late))
    return ''.join(out)
