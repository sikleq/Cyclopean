"""data/events.json: the seasonal events the game defines (events/events.vdata, Halloween 2026 since build 6826): when
each starts for players, when Valve's own test of it started, whether it ends in the files, whether it must be owned.
The Game section's Seasonal events page shows them (builders/game_now.py); no patch note says the test date."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from . import jsonio, kv3, tracker

PATH = 'game/citadel/pak01_dir/events/events.vdata'
OUT = Path(__file__).resolve().parent.parent / 'data' / 'events.json'
PREFIX = 'EVENT_ID_'


def _when(value) -> str | None:
    """A Unix time in the game's field as 'YYYY-MM-DD HH:MM'; "none" or 0 = not set."""
    if not isinstance(value, int) or value <= 0:
        return None
    return datetime.fromtimestamp(value, timezone.utc).strftime('%Y-%m-%d %H:%M')


def parse(text: str) -> list[dict]:
    rows = []
    for key, e in kv3.loads(text).items():
        if key.startswith(PREFIX) and isinstance(e, dict):
            rows.append({'id': key, 'name': key[len(PREFIX):].replace('_', ' ').title(),
                         'start': _when(e.get('m_rtEventStartTime')), 'test_start': _when(e.get('m_rtEventStartTimeDev')),
                         'end': _when(e.get('m_rtEventEndTime')), 'must_be_owned': bool(e.get('m_bMustBeOwned'))})
    return rows


def build() -> None:
    text = tracker.read('HEAD', PATH)
    jsonio.dump(OUT, parse(text) if text else [], indent=1)
