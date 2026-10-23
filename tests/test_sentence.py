"""The patch archive's line for a change (match.sentence): a field kept without its value (a sound, look or interface
field, diff.VALUELESS_CATS) says only that it went or came — Hat Trick 2024-08-01 read "removed (was —)" after a
rebuild of the records (2026-10-23)."""
from pipeline.match import sentence


def test_removed_field_without_value_has_no_was():
    c = {'op': 'remove', 'label': 'Speed To Pitch Remap', 'old_s': None, 'new_s': None}
    assert sentence('Hat Trick', c) == 'Hat Trick: Speed To Pitch Remap removed'


def test_added_field_without_value_has_no_brackets():
    c = {'op': 'add', 'label': 'Beam Start Search Pos', 'old_s': '—', 'new_s': '—'}
    assert sentence('Laser', c) == 'Laser: Beam Start Search Pos added'


def test_values_kept_when_known():
    assert sentence('Hat Trick', {'op': 'remove', 'label': 'Damage', 'old_s': '50'}) == 'Hat Trick: Damage removed (was 50)'
    assert sentence('Hat Trick', {'op': 'add', 'label': 'Damage', 'new_s': '50'}) == 'Hat Trick: Damage added (50)'
