"""A Fixed note line's "was first reported 18 days before" (owner 2026-11-03): a number and nothing else, no link and no
thread. data/fix_reports.json comes from tools/import_fix_reports.py."""
from __future__ import annotations

from functools import lru_cache

from .common import DATA, load_json


@lru_cache(maxsize=None)
def fix_reports() -> dict:
    """{update: {note line: days}}; {} before the first import."""
    return load_json('fix_reports.json') if (DATA / 'fix_reports.json').exists() else {}


def reported_words(days: int) -> str:
    return f'was first reported {days} day{"" if days == 1 else "s"} before'


def reported_chip(update: str, text: str) -> str:
    days = fix_reports().get(update, {}).get(text.strip())
    return f' <span class="reported">{reported_words(days)}</span>' if days is not None else ''
