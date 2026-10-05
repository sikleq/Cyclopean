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
# words, punctuation marks and runs of space as tokens of their own: with "\S+\s*" "Rate " and "Rate, " differed and
# Active Reload 2025-05-19 struck "Rate, Bullet Lifesteal." to re-add the same words (review 2026-10-05)
_TOKEN = re.compile(r'\w+|[^\w\s]|\s+')
_SHORT_EQUAL = re.compile(r'^(?:\s+|[^\w\s]+|\w{1,3})$')
SHORT_DIFF = 300          # descriptions this short open on their old and new text
# key bindings Valve wrote two ways over the years ("[[Iv attack]]" → "[Attack]"; 2025-05-08): one name each
_KEY_NAMES = (('iv attack2', 'ads'), ('iv attack', 'attack'), ('in mantle', 'mantle'), ('key duck', 'crouch'),
              ('key forward', 'moveforward'), ('key innate 1', 'roll'), ('key reload', 'reload'),
              ('key alt cast', 'altcast'), ('alt cast', 'altcast'), ('alt-cast', 'altcast'))
_BRACKET = re.compile(r'\[\[?([^\[\]]+)\]?\]')


_HERO_TOKEN = re.compile(r'^hero_?name$', re.I)
_BINDING_TOKEN = re.compile(r'^(?:iv|in|key)_', re.I)          # "{s:iv_attack}": a key binding, read "[Iv Attack]"


def unfilled(raw, hero: str | None = None) -> bool:
    """Does the game's text hold a value it fills in when it shows it ("{s:AbilityCooldown}", read "[Ability
    Cooldown]")? A hero's page fills its own name in; a key binding is no value. Such a text stays folded: open, 552
    of 980 rows showed "[Ability Cooldown]s Cooldown · Applies [Fixation Stacks] Fixation Stacks" (review
    2026-10-05)."""
    from .patches_pages import _VALUE_TOKEN
    return any(not (hero and _HERO_TOKEN.match(n)) and not _BINDING_TOKEN.match(n)
               for n in _VALUE_TOKEN.findall(str(raw or '')))


def _plain(s) -> str:
    from .patches_pages import _plain as plain     # the archive's reading of loc text: markup out, [Tokens]
    return plain(s, None)


def _canon_key(m: re.Match) -> str:
    name = m.group(1).strip().lower()
    for a, b in _KEY_NAMES:
        if name == a:
            return f'[{b}]'
    name = re.sub(r'^in ability(\d)$', r'ability\1', name)
    return f'[{re.sub(r"[^a-z0-9]", "", name)}]'


def wording(s: str) -> str:
    """A text as its words read: case, punctuation, spacing and how a key binding is written do not count."""
    s = _BRACKET.sub(_canon_key, s.lower())
    return ' '.join(re.findall(r'[a-z0-9%+\-\[\]]+', s))


def cosmetic(a: str, b: str) -> bool:
    """The two texts read the same: a case, comma, space or key-binding spelling changed ("infront" → "in front"
    still differs). 88 of 980 text rows changed nothing a player reads (review 2026-10-05)."""
    return wording(a) == wording(b)


def _marked(a: str, b: str) -> tuple[str, str]:
    """(old html, new html): the words only the old text has in <del>, only the new one's in <ins>. Compared
    without case; a space, a comma or a short word between two changed stretches joins them, so the result reads
    "−and +, … and Move Speed" rather than confetti; a lone space or mark is never wrapped."""
    ta, tb = _TOKEN.findall(a), _TOKEN.findall(b)
    ops = difflib.SequenceMatcher(a=[t.lower() for t in ta], b=[t.lower() for t in tb], autojunk=False).get_opcodes()
    merged: list[list] = []
    for i, (op, i1, i2, j1, j2) in enumerate(ops):
        short = op == 'equal' and 0 < i < len(ops) - 1 and _SHORT_EQUAL.match(''.join(ta[i1:i2]))
        if (op != 'equal' or short) and merged and merged[-1][0] != 'equal':
            merged[-1][2], merged[-1][4] = i2, j2
            continue
        merged.append(['replace' if short else op, i1, i2, j1, j2])
    old, new = [], []
    for op, i1, i2, j1, j2 in merged:
        x, y = ''.join(ta[i1:i2]), ''.join(tb[j1:j2])
        if op == 'equal':
            old.append(esc(x))
            new.append(esc(y))
            continue
        old.append(f'<del>{esc(x)}</del>' if x.strip() and re.search(r'\w', x) else esc(x))
        new.append(f'<ins>{esc(y)}</ins>' if y.strip() and re.search(r'\w', y) else esc(y))
    return ''.join(old), ''.join(new)


def text_kind(texts: list[dict]) -> str | None:
    """The band banner's word for an entity's text changes ("renamed" / "description"), None when there are none or
    they only fix the wording."""
    real = [t for t in texts if _plain(t.get('old')) and _plain(t.get('new'))
            and not cosmetic(_plain(t.get('old')), _plain(t.get('new')))]
    if any(t['part'] == 'name' for t in real):
        return 'renamed'
    return 'description changed' if real else None


_HERO_NAME = re.compile(r'\[hero ?name\]', re.I)


def text_rows(texts: list[dict], hero: str | None = None) -> str:
    """The rows of one entity's text changes in one patch, names first. `hero`: the page's hero, whose name the game
    fills into "[Hero name]" (61 rows showed the token; review 2026-10-05)."""
    from .cards import row
    out = []
    for t in sorted(texts, key=lambda t: list(PART_LABEL).index(t['part']) if t['part'] in PART_LABEL else 9):
        a, b = _plain(t.get('old')), _plain(t.get('new'))
        if hero:
            a, b = _HERO_NAME.sub(hero, a), _HERO_NAME.sub(hero, b)
        if not a or not b or a == b:
            continue
        label = PART_LABEL.get(t['part'], 'Text changed')
        if t['part'] == 'name':
            vals = (f'<span class="vals wrap"><span class="old">{esc(a)}</span><span class="arrow">→</span>'
                    f'<span class="new">{esc(b)}</span></span>')
            out.append(row('text', '', esc(label), vals))
            continue
        old, new = _marked(a, b)
        if cosmetic(a, b):
            # the wording only ("infront" → "in front", a key binding spelled the new way): one quiet line, still
            # there — the owner wants every change, but it is no description change
            label = label.replace('description changed', 'wording fixed').replace('Description changed', 'Wording fixed')
        head = row('text', '', esc(label), '')
        # a short text opens on its old and new versions, like a tooltip card side by side — not one with values the
        # game fills in (`unfilled`): its "[Sleep Duration]" placeholders are no reading
        opened = (' open' if len(a) <= SHORT_DIFF and len(b) <= SHORT_DIFF
                  and not unfilled(t.get('old'), hero) and not unfilled(t.get('new'), hero) else '')
        out.append(f'<details class="txt"{opened}><summary>{head}</summary><div class="txt-diff">'
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
