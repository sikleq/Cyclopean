"""Rendering of one change: its tag, its values, flags and lists as words, the order of rows."""
from builders.render import fold_tier_swaps, sort_changes, tag_of

from tests.helpers import ch


def test_tags():
    # no percentage in the badge: the value cell already shows it
    assert tag_of(ch()) == ('nerf', 'NERF')
    assert tag_of(ch(op='add'))[0] == 'new'
    assert tag_of(ch(op='remove'))[0] == 'del'
    assert tag_of(ch(cat='mechanic', dir='changed', pct=None)) == ('mech', 'MECH')
    assert tag_of(ch(dir='changed', pct=None)) == ('changed', 'CHANGED')


def test_a_corrupted_version_is_one_row():
    from builders.render import fold_corrupted
    p = 'm_CorruptedItemInfo.m_Upgrade.m_vecPropertyUpgrades{%s}.m_strBonus'
    rows = [{'op': 'add', 'path': p % 'AbilityCooldown', 'label': 'Corrupted: Cooldown', 'new_s': '-4', 'status': 'hidden'},
            {'op': 'add', 'path': p % 'BonusHealth', 'label': 'Corrupted: Base Health', 'new_s': '10', 'status': 'hidden'},
            {'op': 'add', 'path': p % 'X' + '.m_bFixedCorruptedBonus', 'label': 'Corrupted: X › Fixed Corrupted Bonus',
             'new_s': 'yes', 'status': 'hidden'},
            {'op': 'change', 'path': 'm_mapAbilityProperties.Radius.m_strValue', 'label': 'Radius', 'old_s': '5', 'new_s': '6'}]
    out = fold_corrupted(rows)
    assert len(out) == 2 and out[1]['label'] == 'Radius'
    # Broker's trade (City Never Sleeps): one NEW row, the bonuses listed, how they roll left out
    assert (out[0]['op'], out[0]['label'], out[0]['new_s']) == ('add', 'Corrupted version', 'Cooldown -4, Base Health +10')
    assert tag_of(out[0])[0] == 'new'
    # a later tweak of one or two bonuses stays row by row
    assert fold_corrupted(rows[:2]) == rows[:2]


def test_a_corrupted_version_names_its_penalties_and_tells_namesakes_apart(monkeypatch):
    """Review 2026-10-05: Unstoppable 'Excluded Penalties TechDuration, Bonus Health +175…'; Toxic Bullets
    'Incoming Healing -25%, Incoming Healing -25%'; one shared bonus made the row 'shared ×10 items'."""
    from builders import render
    monkeypatch.setattr(render, '_penalty_names', lambda: {'TechDuration': 'Ability Duration', 'FireRate': 'Fire Rate'})
    p = 'm_CorruptedItemInfo.m_Upgrade.m_vecPropertyUpgrades{%s}.m_strBonus'
    rows = [{'op': 'add', 'path': 'm_CorruptedItemInfo.m_vecExcludedPenalties', 'label': 'Corrupted: Excluded Penalties',
             'new_s': 'TechDuration, FireRate'},
            {'op': 'add', 'path': p % 'BonusHealth', 'label': 'Corrupted: Bonus Health', 'new_s': '175',
             'shared': True, 'shared_n': 10, 'shared_what': 'items'},
            {'op': 'add', 'path': p % 'HealAmpReceivePenaltyPercent', 'label': 'Corrupted: Incoming Healing', 'new_s': '-25%'},
            {'op': 'add', 'path': p % 'HealAmpRegenPenaltyPercent', 'label': 'Corrupted: Incoming Healing', 'new_s': '-25%'}]
    [row] = render.fold_corrupted(rows)
    assert row['new_s'] == ('Bonus Health +175, Incoming Healing · receive -25%, Incoming Healing · regen -25%'
                            ' · never rolls: Ability Duration, Fire Rate')
    assert 'shared_n' not in row and not row['shared']
    # the row of a later tweak reads the game's names too
    one = {'op': 'add', 'cat': 'balance', 'path': 'm_CorruptedItemInfo.m_vecExcludedPenalties', 'new_s': 'TechDuration'}
    assert render.vals_text(one) == ('', 'Ability Duration')


def test_rows_cards_and_matrix_cards_print_values_alike():
    """Review 2026-10-05: vals_text and the matrices' _sample_values were hand copies of vals_html (840 rows apart)."""
    from builders.dynamics_page import _sample_values
    from builders.render import vals_html, vals_text
    cases = [ch(path='m_mapAbilityProperties.AbilityCooldownBetweenCharge.m_strValue', old_s='0s', new_s='-1',
                pct=None, dir='changed'),
             ch(path='m_vecAbilityUpgrades[0].m_vecPropertyUpgrades{AbilityCooldown}.m_strBonus', old_s='-1s',
                new_s='-20s'),
             ch(path='x.m_strValue', old_s='-0.5m/s', new_s='-1m/s'),
             ch(path='y', old_s='30%', new_s='2', unit_switch=True, pct=None, dir='changed')]
    for c in cases:
        old, new = vals_text(c)
        html = vals_html(c)
        assert f'>{old}<' in html and f'>{new}<' in html, (c, old, new, html)
        assert _sample_values(c) == (old, new)
    assert vals_text(cases[0]) == ('0s', 'default')
    assert vals_text(cases[1]) == ('-1s', '-20s')
    assert vals_text(cases[3]) == ('30%', '2')


def test_an_enhanced_version_is_one_row():
    """Old Gods, New Blood: an item's Enhanced version that appears whole is ONE row and one change (452 NEW rows
    under one line of the notes); on the item page, inside its "Enhanced version" group, the row is "Bonuses"."""
    from builders.render import fold_versions
    p = 'm_vecAbilityUpgrades[0].m_vecPropertyUpgrades{%s}.m_strBonus'
    key = 'abilities.vdata:upgrade_active_reload:'
    rows = [{'op': 'add', 'path': p % x, 'key': key + p % x, 'label': f'Enhanced: {lab}', 'new_s': v, 'status': 'described'}
            for x, lab, v in (('BonusClipSizePercent', 'Max Ammo', '10%'), ('BonusFireRate', 'Fire Rate', '15%'),
                              ('BonusMoveSpeed', 'Move Speed', '3m/s'))]
    out = fold_versions(rows + [ch(label='Cooldown', key=key + 'cd')])
    assert len(out) == 2
    assert (out[0]['label'], out[0]['new_s'], out[0]['folded']) == ('Enhanced version',
                                                                     'Max Ammo +10%, Fire Rate +15%, Move Speed +3m/s', 3)
    stripped = [{**c, 'label': c['label'].removeprefix('Enhanced: ')} for c in rows]
    assert fold_versions(stripped)[0]['label'] == 'Bonuses'
    # a hero's T1 bonuses sit on the same path, but are no Enhanced version
    t1 = [{**c, 'key': 'abilities.vdata:ability_x:' + c['path'], 'label': 'T1: ' + c['label'][10:]} for c in rows]
    assert fold_versions(t1) == t1
    # a later tweak of a few Enhanced bonuses stays row by row
    assert fold_versions(rows[:2]) == rows[:2]


def test_availability_tags_follow_field_meaning():
    # 'Disabled: no -> yes' switches OFF, 'Player Selectable: no -> yes' switches ON
    assert tag_of(ch(cat='availability', label='Disabled', new_s='yes')) == ('off', 'OFF')
    assert tag_of(ch(cat='availability', label='In Development', new_s='no')) == ('on', 'ON')
    assert tag_of(ch(cat='availability', label='Player Selectable', new_s='yes')) == ('on', 'ON')
    assert tag_of(ch(cat='availability', label='State', new_s='EHeroDevState_PreRelease')) == ('off', 'OFF')
    assert tag_of(ch(cat='availability', label='State', new_s='EHeroDevState_Release')) == ('on', 'ON')


def test_order_new_buff_nerf_del_changed():
    order = [tag_of(c)[0] for c in sort_changes([
        ch(cat='mechanic', dir='changed', label='a'), ch(op='remove', label='b'), ch(dir='nerf', label='c'),
        ch(dir='buff', label='d'), ch(op='add', label='e'), ch(dir='changed', label='f')])]
    assert order == ['new', 'buff', 'nerf', 'del', 'mech', 'changed']


def test_tier_swap_folds_into_one_rework_row():
    rows = fold_tier_swaps([
        ch(op='remove', label='T2: Buff Duration', old_s='25', new_s=None, status='described'),
        ch(op='remove', label='T2: Fire Rate', old_s='14', new_s=None, status='described'),
        ch(op='add', label='T2: Stun Duration', old_s=None, new_s='0.6', status='hidden'),
        ch(op='add', label='T3: Impact Radius', old_s=None, new_s='6', status='documented'),
        ch(label='Damage', old_s='75', new_s='100', dir='buff', status='documented'),
    ])
    rework = [r for r in rows if r['op'] == 'rework']
    assert len(rework) == 1 and rework[0]['label'] == 'T2 upgrade'
    assert rework[0]['old_s'] == 'Buff Duration 25, Fire Rate 14' and rework[0]['new_s'] == 'Stun Duration 0.6'
    assert rework[0]['status'] == 'hidden'          # the least documented part decides
    assert {r['label'] for r in rows} == {'T2 upgrade', 'T3: Impact Radius', 'Damage'}   # T3 only added: kept


def test_flag_lists_show_only_the_difference():
    from builders.render import vals_html
    html = vals_html(ch(cat='mechanic', old_s='CITADEL_ABILITY_BEHAVIOR_A | CITADEL_ABILITY_BEHAVIOR_B',
                        new_s='CITADEL_ABILITY_BEHAVIOR_B | CITADEL_ABILITY_BEHAVIOR_MOVEMENT', dir='changed', pct=None))
    assert '+movement' in html and '−a' in html and 'CITADEL' not in html


def test_pct_pill_strength_follows_size():
    from builders.render import pct_grade, vals_html
    assert [pct_grade(x) for x in (2, -7, 20, -45, 122)] == [1, 2, 3, 4, 5]
    assert 'data-g="3"' in vals_html(ch(old_s='40', new_s='32', pct=-20.0))


def test_engine_values_read_as_words():
    from builders.render import readable_value
    assert readable_value('EHeroDevState_PreRelease') == 'Pre Release'
    assert readable_value('CITADEL_UNIT_TARGET_NEUTRAL') == 'Neutral'
    assert readable_value('file://{images}/events/voting_sept2026/sticker_baba.psd') == 'sticker_baba'
    assert readable_value('12.5') == '12.5' and readable_value('Splatter') == 'Splatter'


def test_number_lists_read_as_ranges_and_moved_positions():
    """Review 2026-10-05: 229 rows of bare number lists ("Aiming Move Spread Penalty 0, 0.15 → —", "Horizontal
    Recoil -0.4, 0.4 → 0, 0", item prices by tier)."""
    from builders.render import vals_html, vals_text
    row = lambda path, a, b: {'op': 'change', 'cat': 'balance', 'path': path, 'old_s': a, 'new_s': b}  # noqa: E731
    assert vals_text(row('m_AimingMoveSpreadPenalty', '0, 0.15', '—')) == ('0–0.15', '—')
    assert vals_text(row('m_mapAbilityProperties.x.m_HorizontalRecoil', '-0.4, 0.4', '0, 0')) == ('±0.4', 'none')
    html = vals_html(row('m_nItemPricePerTier', '0, 500, 1250, 3000', '0, 800, 1250, 3200'))
    assert '#2 500 → 800 · #4 3000 → 3200' in html and '#1' not in html
    assert vals_text(row('m_flRadius', '5m', '6m')) == ('5m', '6m')          # a plain value is no list
    # an enum's "none" is no value, not "Ability Targeting Location None"
    loc = row('m_eAbilityTargetingLocation', 'CITADEL_ABILITY_TARGETING_LOCATION_NONE',
              'CITADEL_ABILITY_TARGETING_LOCATION_UNIT')
    assert vals_text(loc) == ('—', 'unit')


def test_number_lists_are_values_not_flags():
    from builders.render import shown_pair
    # a recoil range or prices by tier keep their order: no "+-0.1 +0.1" chips (314 rows, 2026-10-02)
    assert shown_pair({'old_s': '', 'new_s': '-0.1, 0.1'})[0] != 'flags'
    assert shown_pair({'old_s': '0, 500, 1200', 'new_s': '0, 500, 1250'})[0] != 'flags'
    assert shown_pair({'old_s': 'A | B', 'new_s': 'A | B | C'}) == ('flags', [('+c', 'add')])


def test_no_limit_reads_as_no_limit():
    from builders.cards import is_noop
    from builders.render import shown_value
    # one wording for 9999 and -1 (audit 2026-10-04: "∞ → no limit" read as a change)
    assert shown_value('9999') == 'no limit' and shown_value('99999') == 'no limit' and shown_value('9999m') == 'no limit'
    assert shown_value('999') == '999'
    # the spellings of "no limit" are one value
    assert is_noop({'op': 'change', 'old_s': '9999', 'new_s': '99999'})
    assert is_noop({'op': 'change', 'old_s': '9999', 'new_s': '-1',
                    'path': 'm_mapAbilityProperties.ChannelMoveSpeed.m_strValue'})


def test_flags_written_without_spaces_read_as_words():
    from builders.render import readable_value, shown_pair
    v = 'CITADEL_ABILITY_BEHAVIOR_CHANNELLED|CITADEL_ABILITY_BEHAVIOR_NO_TARGET'
    assert readable_value(v) == 'Channelled | No Target'
    assert ('+channelled', 'add') in shown_pair({'old_s': '', 'new_s': v})[1]


def test_values_say_no_limit_and_carry_their_unit_on_both_sides():
    """Advisor round 3, 2026-10-03: "Channel Move Speed 8m → −1", "Weapon Damage 20% →", "50 → 20m"."""
    from builders.render import vals_html
    assert 'no limit' in vals_html(ch(old_s='8m', new_s='-1', pct=None))
    assert '>—<' in vals_html(ch(old_s='20%', new_s='', pct=None))
    assert '>50m<' in vals_html(ch(old_s='50', new_s='20m'))
    assert '>-1%<' in vals_html(ch(old_s='-2%', new_s='-1%'))           # a real penalty stays a number
