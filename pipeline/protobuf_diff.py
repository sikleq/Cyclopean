"""What changed in the game's network / game-coordinator messages (the tracker's Protobufs/*.proto).

A field removed from a message is often the only trace of a dropped feature: build 6810 (2026-10-22) took
`is_high_skill_range_party` out of the matchmaking messages, with no word in the notes. The files are compared
by meaning, not by line: each one is read into {scope: {name: definition}} (scope = Message.Nested, name = field
or enum value), so a moved or re-indented line is no change.
"""
from __future__ import annotations

import re

from . import tracker

PREFIX = 'Protobufs/'
LIMIT = 300                     # rows per build; a whole new protocol file is one 'added' row per message
_OPEN = re.compile(r'^(message|enum|oneof|service)\s+(\w+)\s*\{')
_ITEM = re.compile(r'^(?:(?:optional|required|repeated)\s+)?(?:[\w.<>, ]+\s+)?(\w+)\s*=\s*-?\w+')
_COMMENT = re.compile(r'//.*$')


def parse(text: str) -> dict[str, dict[str, str]]:
    """{scope: {item name: normalized definition}}; every message / enum shows up as a scope even when empty."""
    out: dict[str, dict[str, str]] = {}
    stack: list[str] = []
    # one statement per line whatever the layout (`message M { optional uint32 id = 1; }`)
    code = '\n'.join(_COMMENT.sub('', raw) for raw in text.splitlines())
    code = re.sub(r'([{;])', '\\1\n', code).replace('}', '\n}\n')
    for raw in code.splitlines():
        line = ' '.join(raw.split())
        if not line:
            continue
        m = _OPEN.match(line)
        if m:
            # a oneof's fields belong to the message around it
            if m.group(1) != 'oneof':
                stack.append(m.group(2))
                out.setdefault('.'.join(stack), {})
            else:
                stack.append('')
            continue
        if line.startswith('}'):
            if stack:
                stack.pop()
            continue
        scope = '.'.join(s for s in stack if s)
        if not scope or not line.endswith(';'):
            continue
        m = _ITEM.match(line)
        if m:
            out.setdefault(scope, {})[m.group(1)] = line.rstrip(';').strip()
    return out


def diff_file(name: str, old: str, new: str) -> list[dict]:
    a, b = parse(old), parse(new)
    rows: list[dict] = []
    for scope in sorted(a.keys() - b.keys()):
        if '.' not in scope or scope.rsplit('.', 1)[0] in b:      # a nested type inside a removed one goes with it
            rows.append({'file': name, 'scope': scope, 'op': 'removed', 'item': None})
    for scope in sorted(b.keys() - a.keys()):
        if '.' not in scope or scope.rsplit('.', 1)[0] in a:
            rows.append({'file': name, 'scope': scope, 'op': 'added', 'item': None})
    for scope in sorted(a.keys() & b.keys()):
        old_items, new_items = a[scope], b[scope]
        for item in sorted(old_items.keys() | new_items.keys()):
            o, n = old_items.get(item), new_items.get(item)
            if o == n:
                continue
            op = 'added' if o is None else 'removed' if n is None else 'changed'
            rows.append({'file': name, 'scope': scope, 'op': op, 'item': item, 'old': o, 'new': n})
    return rows


def protobuf_diff(prev: str, cur: str) -> list[dict]:
    """Rows for every .proto file whose content differs between two tracker commits (a new or removed file is
    all its messages added / removed)."""
    before, after = tracker.tree_blobs(prev, PREFIX), tracker.tree_blobs(cur, PREFIX)
    rows: list[dict] = []
    for path in sorted(before.keys() | after.keys()):
        if not path.endswith('.proto') or before.get(path) == after.get(path):
            continue
        old = tracker.read_blob(before[path]).decode('utf-8', 'replace') if path in before else ''
        new = tracker.read_blob(after[path]).decode('utf-8', 'replace') if path in after else ''
        rows += diff_file(path[len(PREFIX):], old, new)
    for r in rows:                                   # value None keys add nothing to a stored record
        for k in ('item', 'old', 'new'):
            if r.get(k) is None:
                r.pop(k, None)
    return rows[:LIMIT]
