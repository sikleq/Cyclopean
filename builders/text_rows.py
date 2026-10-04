"""Name and description changes of an ability, item or hero as rows of its history (coverage audit 2026-10-05,
finding 7: 938 such changes were only in the patch archive's "Text & tooltips" tab). The pipeline keeps them per
patch (`pipeline/entity_texts.py`, extras.texts); `entities_pages._history` files them under 'text:<entity key>'
beside the entity's changes, and `history_view` adds them to the entity's group of that patch:

- a rename is one row "Name  Old → New";
- a description (or an upgrade tier's) is a folded row "Description changed" that opens on the old text and the new
  one, the words that went struck through and the words that came highlighted.

They are text, not changes the counters count: no tag, no eye, never a band's counters or its strip tile; a tag or
"not in patch notes" filter hides them (scripts.js `hist-filter`: `.st-text`)."""
from __future__ import annotations

import difflib
import re

from .common import esc

TEXT_PREFIX = 'text:'
PART_LABEL = {'name': 'Name', 'desc': 'Description changed', 't1': 'T1 description changed',
              't2': 'T2 description changed', 't3': 'T3 description changed'}
_WORD = re.compile(r'\S+\s*')


def _plain(s) -> str:
    from .patches_pages import _plain as plain     # the archive's reading of loc text: markup out, [Tokens]
    return plain(s, None)


def _marked(a: str, b: str) -> tuple[str, str]:
    """(old html, new html): the words only the old text has in <del>, only the new one's in <ins>."""
    wa, wb = _WORD.findall(a), _WORD.findall(b)
    old, new = [], []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=wa, b=wb, autojunk=False).get_opcodes():
        x, y = esc(''.join(wa[i1:i2])), esc(''.join(wb[j1:j2]))
        if op == 'equal':
            old.append(x)
            new.append(y)
            continue
        if x:
            old.append(f'<del>{x}</del>')
        if y:
            new.append(f'<ins>{y}</ins>')
    return ''.join(old), ''.join(new)


def text_rows(texts: list[dict]) -> str:
    """The rows of one entity's text changes in one patch, names first."""
    from .cards import row
    out = []
    for t in sorted(texts, key=lambda t: list(PART_LABEL).index(t['part']) if t['part'] in PART_LABEL else 9):
        a, b = _plain(t.get('old')), _plain(t.get('new'))
        if not a or not b or a == b:
            continue
        label = PART_LABEL.get(t['part'], 'Text changed')
        if t['part'] == 'name':
            vals = (f'<span class="vals wrap"><span class="old">{esc(a)}</span><span class="arrow">→</span>'
                    f'<span class="new">{esc(b)}</span></span>')
            out.append(row('text', '', esc(label), vals))
            continue
        old, new = _marked(a, b)
        head = row('text', '', esc(label), '')
        out.append(f'<details class="txt"><summary>{head}</summary><div class="txt-diff">'
                   f'<p class="txt-old">{old}</p><p class="txt-new">{new}</p></div></details>')
    return ''.join(out)


def former_names(by_ent: dict, key: str, name: str) -> list[str]:
    """The names an entity had before (a hero renamed in development: Slork → Fathom), oldest first."""
    seen: list[str] = []
    for _, texts in by_ent.get(TEXT_PREFIX + key, ()):
        for t in texts:
            if t['part'] == 'name':
                old = _plain(t.get('old'))
                if old and old != name and old not in seen:
                    seen.append(old)
    return seen
