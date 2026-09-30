"""Regression guard: the matcher against the audited 'hidden' changes.

tests/fixtures/audit_verdicts.jsonl = ~1000 changes judged by hand-style audit
(COVERED / TRUE_HIDDEN / NOT_GAMEPLAY). Uses the committed data/patches.
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))

from audit_score import FIXTURE, current_status  # noqa: E402


def _table():
    verdicts = [json.loads(x) for x in FIXTURE.read_text(encoding='utf-8').splitlines() if x.strip()]
    patches: dict = {}
    table: dict[str, Counter] = {}
    for v in verdicts:
        table.setdefault(v['verdict'], Counter())[current_status(patches, v)] += 1
    return table


def test_matcher_covers_what_the_notes_describe_and_keeps_real_hidden():
    t = _table()
    cov = t['COVERED']
    coverage = sum(n for k, n in cov.items() if k != 'hidden') / sum(cov.values())
    th = t['TRUE_HIDDEN']
    kept = th['hidden'] / sum(th.values())
    assert coverage >= 0.70, coverage
    assert kept >= 0.85, kept
