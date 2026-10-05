"""Score the matcher against a human-style audit of 'hidden' changes.

tests/fixtures/audit_verdicts.jsonl holds verdicts for changes that an earlier
matcher version called hidden: COVERED (a note line describes it), TRUE_HIDDEN,
NOT_GAMEPLAY, UNSURE. After a matcher change, a good matcher:
  - no longer calls COVERED changes hidden          (coverage)
  - still calls TRUE_HIDDEN changes hidden           (keeps real finds)
  - does not count NOT_GAMEPLAY as gameplay at all   (filtering)

    python tools/audit_score.py
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import jsonio  # noqa: E402

FIXTURE = ROOT / 'tests' / 'fixtures' / 'audit_verdicts.jsonl'
GAMEPLAY = ('balance', 'mechanic', 'availability')


def current_status(patches: dict, v: dict) -> str:
    p = patches.get(v['patch'])
    if p is None:
        p = patches[v['patch']] = jsonio.load(ROOT / 'data' / 'patches' / f'{v["patch"]}.json.gz')
    for e in p['entities']:
        if e['name'] != v['entity'] and e['name'].split(' (')[0] != v['entity']:
            continue
        for c in e['changes']:
            if c['path'] == v['path']:
                return c['status'] if c['cat'] in GAMEPLAY else 'not_gameplay'
    return 'gone'          # no longer listed as a gameplay change of that entity


def main() -> int:
    verdicts = [json.loads(line) for line in FIXTURE.read_text(encoding='utf-8').splitlines() if line.strip()]
    patches: dict = {}
    table: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for v in verdicts:
        table[v['verdict']][current_status(patches, v)] += 1
    for verdict in ('COVERED', 'TRUE_HIDDEN', 'NOT_GAMEPLAY', 'UNSURE'):
        c = table.get(verdict, collections.Counter())
        total = sum(c.values()) or 1
        print(f'{verdict:13s} n={sum(c.values()):4d}  ' + '  '.join(f'{k}={n} ({n / total:.0%})' for k, n in c.most_common()))
    cov = table['COVERED']
    good_cov = sum(n for k, n in cov.items() if k != 'hidden') / (sum(cov.values()) or 1)
    th = table['TRUE_HIDDEN']
    kept = th.get('hidden', 0) / (sum(th.values()) or 1)
    ng = table['NOT_GAMEPLAY']
    filt = sum(n for k, n in ng.items() if k in ('not_gameplay', 'gone')) / (sum(ng.values()) or 1)
    print(f'\ncoverage {good_cov:.0%} · real hidden kept {kept:.0%} · non-gameplay filtered {filt:.0%}'
          f' · eye precision {eye_precision(table):.0%}')
    return 0


def eye_precision(table: dict[str, collections.Counter]) -> float:
    """Of the audited changes the matcher still calls hidden, the share that IS hidden (TRUE_HIDDEN): how often
    the eye is right. Coverage and 'kept' alone let the eye sit on announced features (review 2026-10-05: 28%,
    City Never Sleeps and Old Gods had no verdicts at all)."""
    still = sum(c.get('hidden', 0) for c in table.values())
    return table.get('TRUE_HIDDEN', collections.Counter()).get('hidden', 0) / (still or 1)


if __name__ == '__main__':
    raise SystemExit(main())
