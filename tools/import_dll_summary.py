"""Copy the per-build DLL function summary into data/dll_changes.json for the build pages.

The summary comes from a separate research tool that downloads every Steam build's binaries and diffs them
function by function; it is not public, so the site keeps a copy and this step runs by hand after that tool
has processed new builds. The input holds no code, addresses or paths: per build, counts of changed / new /
removed functions in client.dll and server.dll, up to 30 named ones by weight, and the other DLLs whose hash
changed. Two Steam builds under one tracker build are merged.

    python tools/import_dll_summary.py <summary.json>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.strings_diff import demangle  # noqa: E402

OUT = ROOT / 'data' / 'dll_changes.json'
TOP = 30
_COUNTS = ('changed', 'added', 'removed', 'unnamed')


def readable(name: str) -> str:
    """An anchor's parts with MSVC type names spelled out (`.?AVCFoo@@` -> CFoo)."""
    return ' | '.join(_spell(p.strip()) for p in name.split(' | '))


def _spell(part: str) -> str:
    part = demangle(part)
    if part.startswith('.?A'):              # a template with numeric arguments: name its first class argument
        m = re.search(r'\$(\w+)@.*?@V(\w+)@@', part)
        return f'{m.group(1)}<{m.group(2)}>' if m else part
    return part


def _merge_dll(a: dict | None, b: dict) -> dict:
    """Counts add up; functions with one name (two functions anchored alike) keep the higher weight."""
    a = a or {**{k: 0 for k in _COUNTS}, 'functions': []}
    best: dict[str, int] = {}
    for f in a['functions'] + [{**f, 'name': readable(f['name'])} for f in b.get('functions', [])]:
        best[f['name']] = max(best.get(f['name'], 0), f['weight'])
    funcs = sorted(({'name': n, 'weight': w} for n, w in best.items()), key=lambda f: (-f['weight'], f['name']))
    return {**{k: a[k] + b.get(k, 0) for k in _COUNTS}, 'functions': funcs[:TOP]}


def convert(rows: list[dict]) -> dict[str, dict]:
    """{build: {'dlls': {module: {...}}, 'other': [module, ...]}}; builds without any change are left out."""
    out: dict[str, dict] = {}
    for r in rows:
        build = str(r.get('build', ''))
        if not build.isdigit():
            continue
        cur = out.setdefault(build, {'dlls': {}, 'other': []})
        for mod, d in sorted((r.get('dlls') or {}).items()):
            cur['dlls'][mod] = _merge_dll(cur['dlls'].get(mod), d)
        cur['other'] = sorted(set(cur['other']) | set(r.get('other_dlls_changed') or ()))
    return {b: v for b, v in sorted(out.items(), key=lambda kv: int(kv[0]))
            if v['other'] or any(d['changed'] or d['added'] or d['removed'] for d in v['dlls'].values())}


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    rows = json.loads(Path(argv[1]).read_text(encoding='utf-8'))
    data = convert(rows)
    text = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    if ':\\' in text or 'buildworker' in text:
        raise SystemExit('the summary holds a local path; fix the source, nothing written')
    OUT.write_text(text, encoding='utf-8')
    print(f'{len(data)} builds -> {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
