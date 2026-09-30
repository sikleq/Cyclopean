"""Fast KV3 (text) parser for Deadlock .vdata files.

The reference parser (`keyvalues3` on PyPI) needs ~17 s for abilities.vdata;
we parse every tracked build, so this one tokenizes with a single regex and
walks the token stream iteratively (~10x faster).

Flagged values (`resource_name:"x"`, `subclass:{...}`, `soundevent:"x"`) are
returned as their inner value — the flag carries no balance information.
"""
from __future__ import annotations

import re

_TOKEN = re.compile(
    r'''
    (?:\s+|//[^\n]*|/\*.*?\*/)                    # skipped: whitespace, comments
    |(?P<ml>"""[\s\S]*?""")                        # multi-line string
    |(?P<str>"(?:[^"\\]|\\.)*")                    # string
    |(?P<flag>[A-Za-z_]\w*):(?=\s*["{\[#\w-])      # value flag, e.g. subclass:
    |(?P<num>-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)(?![\w.])
    |(?P<id>[A-Za-z_][\w.]*)                       # identifier / bare word
    |(?P<blob>\#\[[^\]]*\])                        # binary blob
    |(?P<p>[{}\[\]=,])                             # punctuation
    ''',
    re.X | re.S,
)

_HEADER = re.compile(r'\A﻿?\s*<!--.*?-->', re.S)
_ESCAPES = {'"': '"', '\\': '\\', 'n': '\n', 't': '\t', 'r': '\r'}
_ESC_RE = re.compile(r'\\(.)')


class KV3Error(ValueError):
    pass


def _unescape(s: str) -> str:
    if '\\' not in s:
        return s
    return _ESC_RE.sub(lambda m: _ESCAPES.get(m.group(1), '\\' + m.group(1)), s)


def _tokens(text: str):
    pos = 0
    n = len(text)
    for m in _TOKEN.finditer(text):
        if m.start() != pos:
            raise KV3Error(f'unexpected input at {pos}: {text[pos:pos + 40]!r}')
        pos = m.end()
        kind = m.lastgroup
        if kind is None or kind == 'flag':
            continue
        yield kind, m.group(kind)
    if pos != n:
        raise KV3Error(f'unexpected input at {pos}: {text[pos:pos + 40]!r}')


def _scalar(kind: str, raw: str):
    if kind == 'str':
        return _unescape(raw[1:-1])
    if kind == 'ml':
        body = raw[3:-3]
        return body[1:] if body.startswith('\n') else body
    if kind == 'num':
        if any(c in raw for c in '.eE'):
            return float(raw)
        return int(raw)
    if kind == 'id':
        if raw == 'true':
            return True
        if raw == 'false':
            return False
        if raw == 'null':
            return None
        return raw
    if kind == 'blob':
        return raw
    raise KV3Error(f'bad scalar {kind} {raw!r}')


def loads(text: str):
    """Parse KV3 text and return the root value (normally a dict)."""
    text = _HEADER.sub('', text, count=1)
    toks = list(_tokens(text))
    root = None
    # stack entries: [container, pending_key]
    stack: list[list] = []
    i = 0
    n = len(toks)
    while i < n:
        kind, raw = toks[i]
        top = stack[-1] if stack else None
        if kind == 'p':
            if raw == '{' or raw == '[':
                new = {} if raw == '{' else []
                _attach(stack, new)
                if top is None:
                    root = new
                stack.append([new, None])
            elif raw == '}' or raw == ']':
                if not stack:
                    raise KV3Error('unbalanced close')
                stack.pop()
            elif raw == ',' or raw == '=':
                pass
            i += 1
            continue
        # scalar token
        if top is not None and isinstance(top[0], dict) and top[1] is None:
            # a key; the next token must be '='
            top[1] = _scalar(kind, raw) if kind in ('str', 'ml') else raw
            i += 1
            continue
        _attach(stack, _scalar(kind, raw))
        i += 1
    if stack:
        raise KV3Error('unterminated structure')
    return root


def _attach(stack, value):
    if not stack:
        return
    cont, key = stack[-1]
    if isinstance(cont, list):
        cont.append(value)
    else:
        if key is None:
            raise KV3Error('value without key')
        cont[key] = value
        stack[-1][1] = None


def load(path) -> dict:
    with open(path, encoding='utf-8-sig') as f:
        return loads(f.read())
