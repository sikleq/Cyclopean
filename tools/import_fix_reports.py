"""Write data/fix_reports.json: how long before each Fixed note line the bug was first reported by players.

The pairs of a note line and its reports come from a separate, private reading of the game's forum; it runs by hand and
its input is not public. The site keeps a number per line and nothing else (owner 2026-11-03: no link, no thread, no
words of a player), so no report can be traced from here. A line the patch's notes do not hold is an error of the input:
it is counted and left out.

    python tools/import_fix_reports.py <pairs.jsonl> [more pairs.jsonl ...]
"""
from __future__ import annotations

import gzip
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'fix_reports.json'
PATCHES = ROOT / 'data' / 'patches'


def days_before(pairs: list[dict]) -> dict[str, dict[str, int]]:
    """{update: {note line: days from its earliest report to the update}}. A pair is a note line (`line`, or `row` of type
    `note`) with `update`, `reported` and the update's day (`fixed_on`, or `update` itself when it is a date); a hidden
    row has no line to stand on."""
    out: dict[str, dict[str, int]] = {}
    for p in pairs:
        text = p.get('line') or (p.get('row') if p.get('row_type') == 'note' else None)
        if not text:
            continue
        day = date.fromisoformat(p.get('fixed_on') or p['update'][:10])
        days = (day - date.fromisoformat(p['reported'])).days
        if days <= 0:           # a report of the update's own day can be a complaint about that very update
            continue
        lines = out.setdefault(p['update'], {})
        lines[text.strip()] = max(lines.get(text.strip(), 0), days)
    return out


def note_texts(update: str) -> set[str]:
    with gzip.open(PATCHES / f'{update}.json.gz', 'rt', encoding='utf-8') as f:
        patch = json.load(f)
    return {ln['text'].strip() for s in patch.get('sections') or () for ln in s.get('lines') or ()}


def known_only(days: dict[str, dict[str, int]], texts_of=note_texts) -> tuple[dict[str, dict[str, int]], int]:
    """Only the lines the update's notes hold, and how many were dropped."""
    out, dropped = {}, 0
    for update, lines in sorted(days.items()):
        texts = texts_of(update)
        kept = {t: d for t, d in sorted(lines.items()) if t in texts}
        dropped += len(lines) - len(kept)
        if kept:
            out[update] = kept
    return out, dropped


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    pairs = [json.loads(x) for path in sys.argv[1:] for x in Path(path).read_text(encoding='utf-8').splitlines() if x.strip()]
    days, dropped = known_only(days_before(pairs))
    OUT.write_text(json.dumps(days, ensure_ascii=False, indent=0, sort_keys=True) + '\n', encoding='utf-8')
    print(f'{sum(map(len, days.values()))} lines in {len(days)} updates, {dropped} not in the notes')
    return 0


if __name__ == '__main__':
    sys.exit(main())
