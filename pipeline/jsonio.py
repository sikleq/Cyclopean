"""JSON read/write; files ending in .gz are gzip-compressed.

Build records are stored as .json.gz: they are rewritten whenever the
enrichment format changes, and plain JSON made every such rewrite a ~40 MB
git commit. Index files stay plain JSON so they remain readable on GitHub.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path


def dump(path: Path, obj, indent: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, ensure_ascii=False, indent=indent,
                      separators=None if indent else (',', ':'), default=str)
    tmp = path.with_name(path.name + '.tmp')
    if path.name.endswith('.gz'):
        # mtime=0 keeps the bytes identical for identical content (no git noise)
        with open(tmp, 'wb') as raw, gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0, compresslevel=9) as f:
            f.write(text.encode('utf-8'))
    else:
        tmp.write_text(text, encoding='utf-8')
    tmp.replace(path)


def load(path: Path):
    if path.name.endswith('.gz'):
        with gzip.open(path, 'rt', encoding='utf-8') as f:
            return json.load(f)
    return json.loads(path.read_text(encoding='utf-8'))
