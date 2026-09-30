"""Dump a patch's notes and its 'hidden' changes as plain text for auditing.

    python tools/dump_hidden.py <patch-id> [out.txt]

Used to check that hidden changes are really absent from the notes and not
described in other words (the matcher's blind spots).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import jsonio  # noqa: E402


def dump(pid: str) -> str:
    p = jsonio.load(ROOT / 'data' / 'patches' / f'{pid}.json.gz')
    out = [f'# {p["title"]} ({p["date"]}) counts={p["counts"]}', '', '## NOTES (status | text)']
    for s in p['sections']:
        out.append(f'### {s["title"]}')
        for ln in s['lines']:
            out.append(f'[{ln["status"]}] {ln["text"]}')
    out += ['', '## HIDDEN CHANGES (entity | kind | label | old -> new | path)']
    for e in p['entities']:
        hid = [c for c in e['changes'] if c['status'] == 'hidden' and c['cat'] in ('balance', 'mechanic', 'availability')]
        if not hid:
            continue
        owner = f' (owner {e["owner"]})' if e.get('owner') else ''
        out.append(f'### {e["name"]} [{e.get("kind")}]{owner}')
        for c in hid:
            out.append(f'- {c["label"]}: {c.get("old_s", "")} -> {c.get("new_s", "")}   [{c["op"]}] {c["path"]}')
    return '\n'.join(out) + '\n'


if __name__ == '__main__':
    text = dump(sys.argv[1])
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(text, encoding='utf-8', newline='\n')
    else:
        sys.stdout.write(text)
