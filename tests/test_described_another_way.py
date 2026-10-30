"""Owner 2026-10-30: many "not in the patch notes" changes of the Halloween 2026 update were in them, written
another way. "Baba's Brew - No longer has an initial brew time" is also its three Lock Times removed; the post's
"Street Brawl:" line heads that mode's lines; "Now travels 40% faster" is a projectile's Speed; "Mid-Boss:" lines
about its Rejuvenator; "Haunts … Damage output increased by 10%" is their DPS too."""
import gzip
import json
from pathlib import Path

import pytest

from pipeline.match import MChange, post_pass

PATCH = Path(__file__).resolve().parent.parent / 'data' / 'patches' / '2026-10-30.json.gz'
needs_patch = pytest.mark.skipif(not PATCH.exists(), reason='no 2026-10-30 patch record')


def _mc(path, old, new, op, label, status='hidden', lines=None) -> MChange:
    return MChange('abilities.vdata', 'ability_x', path, op, old, new, 'balance', 'ability', 'hero_x', label, False,
                   status=status, lines=list(lines or []))


def _by_ent(cs):
    return {'abilities.vdata:ability_x': cs}


def test_a_rework_told_in_words_takes_the_fields_that_went_with_it():
    line = "Baba: Baba's Brew - No longer has an initial brew time"
    brew = _mc('m_mapAbilityProperties.BrewTime.m_strValue', '1.5', '0', 'change', 'Initial Brew Time',
               status='described', lines=[line])
    lock = _mc('m_mapAbilityProperties.FireLockTime.m_strValue', '4.5', None, 'remove', 'Fire Lock Time')
    tuned = _mc('m_mapAbilityProperties.Radius.m_strValue', '5', '6', 'change', 'Radius')
    post_pass([brew, lock, tuned], _by_ent([brew, lock, tuned]))
    assert lock.status == 'described' and line in lock.lines
    assert tuned.status == 'hidden'                    # a tuned number stays hidden


def test_a_new_number_beside_a_words_line_stays_hidden():
    """The audit's real finds: Walker's new 30% trooper factor, Kinetic Pulse's new T2 +8s."""
    said = _mc('m_mapAbilityProperties.Charge.m_strValue', '1', '2', 'change', 'Charge', status='described',
               lines=['X: Ability - Now charges up before firing'])
    new = _mc('m_mapAbilityProperties.TrooperFactor.m_strValue', None, '0.3', 'add', 'Trooper Factor')
    flag = _mc('m_bHomes', None, 'true', 'add', 'Homes')
    post_pass([said, new, flag], _by_ent([said, new, flag]))
    assert new.status == 'hidden'
    assert flag.status == 'described'                  # a field with no number of its own is the rework's


@pytest.fixture(scope='module')
def patch():
    return json.load(gzip.open(PATCH))


def _rows(patch, key_end):
    return {c['label']: c for e in patch['entities'] if e['key'].endswith(key_end) for c in e['changes']}


def _line(patch, start):
    return next(ln for s in patch['sections'] for ln in s['lines'] if ln['text'].startswith(start))


@needs_patch
def test_babas_lock_times_are_the_no_initial_brew_time_line(patch):
    rows = _rows(patch, 'ability_baba_hexing_brew')
    assert {rows[k]['status'] for k in ('Barrier Lock Time', 'Fire Lock Time', 'Silence Lock Time')} == {'described'}


@needs_patch
def test_the_street_brawl_line_heads_that_modes_lines(patch):
    assert _line(patch, 'Street Brawl:')['status'] == 'heading'
    assert _line(patch, 'Rat King: Scrap Grenade - Radius reduced from 8m to 6m')['status'] != 'unmatched'
    assert _rows(patch, 'ability_ratking_scrap_grenade')['Detonation Radius (Street Brawl)']['status'] != 'hidden'


@needs_patch
def test_faster_is_speed_and_mid_boss_lines_reach_its_rejuvenator(patch):
    flask = _rows(patch, 'ability_warden_crowd_control')       # Warden: Alchemical Flask
    assert flask['Projectile Infos › primary › Speed']['status'] != 'hidden'
    assert _rows(patch, 'm_RejuvParams')['Rejuvinator Drop Duration']['status'] == 'documented'
    assert _line(patch, 'Mid-Boss: Rejuvenator crystal drop time')['status'] != 'unmatched'


@needs_patch
def test_haunts_damage_output_is_their_dps_too(patch):
    beam = _rows(patch, 'citadel_neutral_laser_beam_theater')
    assert beam['Beam DPS']['status'] != 'hidden'
